#!/usr/bin/python

#----------------------------------------------------------------------
# Copyright (c) 2011 Raytheon BBN Technologies
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
import omni
import os.path
import time
import readyToLogin

def getLoginCommands( loginInfoDict, keyList ):
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

      clientid = item['client_id']
      if loginCommands.has_key(clientid) : 
        print "More than one nodes have the same client id or the sliver is configured for multiple users. Exit!"
        sys.exit(-1)
      # Use only the first key
      output = "ssh"
      if str(item['port']) != '22' : 
            output += " -p %s " % item['port']
      output += " -i %s %s@%s" % ( keys[0], item['username'], item['hostname'])
      loginCommands[clientid] = output
  
  return loginCommands

def modifyToIgnoreHostChecking(loginCommands) :

  for k,c in loginCommands.items():
    loginCommands[k] = c.replace("ssh ", "ssh -q -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no ")

def executeCommand( loginCommands, host, command) :
  print "Send command %s to %s" % (command, host)
  finalCommand = loginCommands[host] + " '" + command +"'"
  os.system(finalCommand)
  print "Done with command %s to %s" % (command, host)
  time.sleep(5)

def runtransfers(loginCommands) :
  command = "/local/get_udt_file.sh med.100M"
  executeCommand(loginCommands, 'PC2', command)
  command = "/local/get_ftp_file.sh med.100M"
  executeCommand(loginCommands, 'PC2', command)
  #command = "/local/get_both_file.sh med.100M"
  #executeCommand(loginCommands, 'PC2', command)


def setLinkParams(loginCommands, bandwidth, delay, loss) :
  command = "sudo ipfw pipe 60111 config bw %s delay %d plr %f; " % (bandwidth, delay, loss)
  command += "sudo ipfw pipe 60121 config bw %s delay %d plr %f" % (bandwidth, delay, loss)
  executeCommand(loginCommands, 'delay', command)

def main(argv=None):
  
  loginInfoDict, keyList = readyToLogin.main_no_print(argv=argv)
  loginCommands = getLoginCommands(loginInfoDict, keyList)
  modifyToIgnoreHostChecking(loginCommands)
  #for b in ["0M", "500M", "100M", "50M", "10M"] :
  for b in ["0M"] :
    #for l in [0, 0.0001, 0.001, 0.005] :
    for l in [0] :
      for d in [0, 25, 50, 100, 150, 200] :
      #for d in [0]:
        setLinkParams(loginCommands, b, d, l)
        runtransfers(loginCommands)

if __name__ == "__main__":
    sys.exit(main())

