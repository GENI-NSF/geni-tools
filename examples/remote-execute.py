#!/usr/bin/env python

#----------------------------------------------------------------------
# Copyright (c) 2011-2015 Raytheon BBN Technologies
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and/or hardware specification (the "Work") to
# deal in the Work without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Work, and to permit persons to whom the Work
# is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Work.
#
# THE WORK IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE WORK OR THE USE OR OTHER DEALINGS
# IN THE WORK.
#----------------------------------------------------------------------

import copy
import string
import sys
import os.path
import time

import readyToLogin

import gcf.oscript as omni

################################################################################
# Requires that you have omni installed and add the paths to gcf/src and
# gcf/examples in your PYTHONPATH.
#
# For example put the following in your bashrc:
#     export PYTHONPATH=${PYTHONPATH}:path/to/gcf/src:path/to/gcf/exmples
#
# USE: This script is to help you execute commands in your GENI compute
# resources from your local computer using ssh. The script uses readyToLogin.py
# and omni.py as a library to figure out the login commands for your hosts. It
# takes the same command line arguments as omni.py and readyToLogin.py. It also
# takes two additional arguments (--command (-m) and --host). The typical
# execution of the script is :
# remote-execute.py <slicename> -a <AMURL1> -a <AMURL2> -m '<command>'
#
################################################################################

#Global variables
options = None
slicename = None
config = None

def getLoginCommands( loginInfoDict, keyList, forwardAgent=False ):
  loginCommands = {}
  for amUrl, amInfo in loginInfoDict.items() :
    for item in amInfo["info"] :
      try:
        if item['geni_status'] != "ready" :
          print "Not all the nodes are ready. Can't run the experiment exit!"
          sys.exit(-1)
      except KeyError:
          print "There is no status information for a node. This script might fail. "

      keys = readyToLogin.getKeysForUser(amInfo["amType"], item["username"], keyList)
      if len(keys) == 0:
        continue
      clientid = item['client_id']
      if not loginCommands.has_key(clientid) : 
        loginCommands[clientid] = {}
      elif loginCommands[clientid]['username'] == item["username"]:
        print "More than one nodes have the same client id or the sliver is configured for multiple users. Exit!"
        sys.exit(-1)
      else:
        # ignore subsequent usernames for the same client_id
        continue
      # Use only the first key
      output = "ssh"
      if forwardAgent:
            output += " -A "
      
      if str(item['port']) != '22' : 
            output += " -p %s " % item['port']
      output += " -i %s %s@%s" % ( keys[0], item['username'], item['hostname'])

      loginCommands[clientid]['command'] = output
      loginCommands[clientid]['username'] = item["username"]
  
  return loginCommands

def modifyToIgnoreHostChecking(loginCommands) :

  for k,c in loginCommands.items():
    c = loginCommands[k]['command']
    loginCommands[k]['command'] = c.replace("ssh ", "ssh -q -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no ")

def executeCommand( loginCommands, host, command) :
  print "2. Send command '%s' to %s\n" % (command, host)
  finalCommand = loginCommands[host]["command"] + " '" + command +"'"
  os.system(finalCommand)
  print "... Done with command '%s' at %s" % (command, host)
  time.sleep(5)

def getParser() : 
  parser = readyToLogin.getParser()
  # Parse Options
  usage = "\n\tTypically: \t%s slicename -m '<COMMAND>'" % os.path.basename(sys.argv[0])
  parser.set_usage(usage)

  parser.add_option("-m", "--command", dest="command",
                    default="",
                    help="[REQUIRED]Command to execute in all remote hosts.")

  parser.add_option("--host", dest="host",
                    default=[], action="append",
                    help="Specify in which host you would like the command to be executed. This has to be the clientId. If omitted the command will be ran in all hosts. --host may be used multiple times on the same call.")
  parser.add_option("-A", "--forwardAgent",
                    dest="forward_agent",
                    help="Forward the SSH agent.  Exactly like using '-A' with ssh.",
                    action="store_true", default=False)  

  return parser


def parseArguments( argv=None ) :
  global  slicename, options, config

  if options is not None:
        # The caller, presumably a script, gave us an optparse.Values storage object.
        # Passing this object to parser.parse_args replaces the storage - it is pass
        # by reference. Callers may not expect that. In particular, multiple calls in
        # separate threads will conflict.
        # Make a deep copy
        options = copy.deepcopy(options)
        argv = []

  parser = getParser()
  (options, args) = omni.parse_args(argv, options, parser=parser)

  
  if len(args) > 0:
      slicename = args[0]
  else:
      sys.exit("Must pass in slicename as argument of script.\nRun '%s -h' for more information."%os.path.basename(sys.argv[0]))

  # Check if a command was given
  if options.command == '':
      sys.exit("Must use the -m parameter to pass the command to be executed.\nRun '%s -h' for more information."%os.path.basename(sys.argv[0]))
   

def main(argv=None):
  
  if not argv:
    argv = sys.argv[1:]

  parseArguments(argv=argv)
  print "1. Find login Info for hosts in slice %s" % slicename
  loginInfoDict, keyList = readyToLogin.main_no_print(argv=argv, opts=options, slicen = slicename)
  loginCommands = getLoginCommands(loginInfoDict, keyList, options.forward_agent)
  modifyToIgnoreHostChecking(loginCommands)
  # If the user explicitly passed a host then use only that to execute the
  # command
  # First check if the specified host exists
  if len(options.host) != 0:
      for host in options.host:
          if not loginCommands.has_key(host):
              sys.exit("No host with clientId '%s' in slice %s and AMs %s" %(host,
                                            slicename, str(loginInfoDict.keys())))
  if len(options.host) != 0:
    hosts = options.host
  else :
    hosts = loginCommands.keys()

  for h in hosts : 
    executeCommand( loginCommands, h, options.command) 
    

if __name__ == "__main__":
    sys.exit(main())

