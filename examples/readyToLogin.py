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
from optparse import OptionParser
import omnilib.util.omnierror as omnierror
import xml.etree.ElementTree as etree
import re

################################################################################
# Requires that you have omni installed or the path to gcf/src in your
# PYTHONPATH.
#
# For example put the following in your bashrc:
#     export PYTHONPATH=${PYTHONPATH}:path/to/gcf/src
#
################################################################################

#Global variables
options = None
slicename = None
config = None
NSPrefix = None

def setNSPrefix(prefix):
  ''' Helper function for parsing rspecs. It sets the global variabl NSPrefix to
  the currently parsed rspec namespace. 
  '''
  global NSPrefix
  NSPrefix = prefix

def tag(tag):
  ''' Helper function for parsing rspecs. It gets a tag and uses the global
  NSPrefix to return the full name
  '''
  return "%s%s" %(NSPrefix,tag)

def getInfoFromManifest(manifestStr):
  ''' Function that takes as input a manifest rspec in a string and parses the
  services tag to extract login information. 
  This function returns a list of dictionaries, each dictionary contains 
  login information
  '''
  dom = etree.fromstring(manifestStr) 
  setNSPrefix(re.findall(r'\{.*\}', dom.tag)[0])
  loginInfo = []
  for node_el in dom.findall(tag("node")):
    for serv_el in node_el.findall(tag("services")):
      loginInfo.append(serv_el.find(tag("login")).attrib)
  
  return loginInfo

def findUsersAndKeys( ):
    """Look in omni_config for user and key information of the public keys that
    are installed in the nodes. It uses the global variable config and returns
    keyList which is a dictionary of keyLists per user"""
    keyList = {}
    for user in config['users']:
        # convert strings containing public keys (foo.pub) into
        # private keys (foo)
        username = user['urn'].split('+')[-1]
        keyList[username] = []
        privuserkeys = string.replace(user['keys'].replace(" ",""), ".pub","")
        privuserkeys = privuserkeys.split(",")
        for key in privuserkeys:
            if not os.path.exists(os.path.expanduser(key)):
                print "Key file [%s] does NOT exist." % key
            else:
                keyList[username].append(key)
    return keyList

def getInfoFromListResources( amUrl ) :
    tmpoptions = copy.deepcopy(options)
    tmpoptions.aggregate = [amUrl]

    # Run the equivalent of 'omni.py listresources <slicename>'
    argv = ['listresources', slicename]
    try:
      text, listresources = omni.call( argv, options )
    except omnierror.AMAPIError:
      print "ERROR: There was an error executing listresources, review the logs."
      sys.exit(-1)
    print listresources

    # Parse rspec
    try:
      manifest = listresources[amUrl]["value"]
    except :
      print "Error getting the manifest from %s" % amUrl
      return []

    return getInfoFromManifest(manifest)

def getInfoFromSliverStatusPG( sliverStat ):

    loginInfo = []
    pgKeyList = {}
    for userDict in sliverStat['users'] :
      pgKeyList[userDict['login']] = [] 
      for k in userDict['keys']:
          #XXX nriga Keep track of keys, in the future we can verify what key goes with
          # which private key
          pgKeyList[userDict['login']].append(k['key'])

    for resourceDict in sliverStat['geni_resources']: 
      for children1 in resourceDict['pg_manifest']['children']:
        for children2 in children1['children']:
          child = children2['attributes']
          if (not child.has_key('hostname')):
            continue
          for user, keys in pgKeyList.items():
            loginInfo.append({'authentication':'ssh-keys', 
                              'hostname':child['hostname'],
                              'client_id': resourceDict['pg_manifest']['attributes']['client_id'],
                              'port':child['port'],
                              'username':user,
                              'keys' : keys,
                              'geni_status':resourceDict['geni_status'],
                              'am_status':resourceDict['pg_status']
                             })
    return loginInfo
     

def getInfoFromSliverStatusPL( sliverStat ):

    loginInfo = []
    for resourceDict in sliverStat['geni_resources']: 
      if (not sliverStat['pl_login']) or (not resourceDict['pl_hostname']):
          continue
      loginInfo.append({'authentication':'ssh-keys', 
                          'hostname':resourceDict['pl_hostname'],
                          'client_id':resourceDict['pl_hostname'],
                          'port':'22',
                          'username':sliverStat['pl_login'],
                          'geni_status':resourceDict['geni_status'],
                          'am_status':resourceDict['pl_boot_state']
                       })
    return loginInfo

def getInfoFromSliverStatus( amUrl, amType ) :
    tmpoptions = copy.deepcopy(options)
    tmpoptions.aggregate = [amUrl]
        
    # Run equivalent of 'omni.py sliverstatus username'
    argv = ['sliverstatus', slicename]
    try:
      text, sliverStatus = omni.call( argv, tmpoptions )
    except omnierror.AMAPIError:
      print "ERROR: There was an error executing sliverstatus, review the logs."
      sys.exit(-1)

    if amType == 'sfa' : 
      loginInfo = getInfoFromSliverStatusPL(sliverStatus[amUrl])
    if amType == 'protogeni' : 
      loginInfo = getInfoFromSliverStatusPG(sliverStatus[amUrl])
      
    return loginInfo

def getAMTypeFromGetVersionOut(amUrl, amOutput) :
  if amOutput.has_key("code") and amOutput["code"].has_key("am_type"):
    return amOutput["code"]["am_type"].strip()
  # Older version of SFA do not have the code field, do a hack and check if
  # testbed is there
  if amOutput.has_key("testbed"):
    return "sfa"
  # FOAM does not have a code field, use foam_version
  if amOutput.has_key("foam_version"):
    return "foam"
  # FOAM does not have a code field, use foam_version
  if amOutput.has_key("foam_version"):
    return "foam"
  # XXX Fixme : test whether orca has the am_type, if not use orca_version
  return None
  
def parseArguments( argv=None ) :
  global slicename, options, config

  parser = omni.getParser()
  # Parse Options
  usage = "\n\tTypically: \treadyToLogin.py slicename"
  parser.set_usage(usage)

  parser.add_option("-x", "--xterm", dest="xterm",
                    action="store_false", 
                    default=True,
                    help="do NOT add xterm")
  parser.add_option( "--readyonly", dest="readyonly",
                    action="store_true", 
                    default=False,
                    help="Only print nodes in ready state")
  (options, args) = parser.parse_args()
  
  if len(args) > 0:
      slicename = args[0]
  else:
      sys.exit("Must pass in slicename as argument of script.\nRun '%s -h' for more information."%sys.argv[0])


def addNodeStatus(amUrl, amType, amLoginInfo):
  ''' This function is intended to get the node status from SliverStatus, in
  case the login information comes from the manifest rspec that does not contain
  status information
  '''
  print "NOT IMPLEMENTED YET"

def getKeysForUser( amType, username, keyList ):
  '''Returns a list of keys for the provided user based on the
     list from omni_config file that is saved at keyList
  '''
  userKeyList = []
  for user,keys in keyList.items() :
    #ProtoGENI actually creates accounts per user so check the username
    # before adding the key. ORCA and PL just add all the keys to one
    # user
    if amType == "protogeni" and user != username :
      continue
    for k in keys:
      userKeyList.append(k)

  return userKeyList
    
def printLoginInfo( loginInfoDict, keyList ) :
  '''Prints the Login Information from all AMs, all Users and all hosts '''
  for amUrl, amInfo in loginInfoDict.items() :
    print ""
    print "="*80
    print "LOGIN INFO for AM: %s" % amUrl
    print "="*80
    for item in amInfo["info"] :
      output = ""
      if options.readyonly :
        try:
          if item['geni_status'] != "ready" :
            continue
        except KeyError:
          print "There is no status information for node %s. Print login info."
      # If there are status info print it, if not just skip it
      try:
        output += "\n%s's geni_status is: %s (am_status:%s) \n" % (item['client_id'], item['geni_status'],item['am_status'])
          # Check if node is in ready state
      except KeyError:
        pass

      keys = getKeysForUser(amInfo["amType"], item["username"], keyList)

      output += "User %s logins to %s using:\n" % (item['username'], item['client_id'])
      for key in keys: 
        output += "\t"
        if options.xterm :
            output += "xterm -e "
        if str(item['port']) != '22' : 
            output += " -p %s " % item['port']
        output += "ssh -i %s %s@%s" % ( key, item['username'], item['hostname'])
        if options.xterm :
            output += " &"
        output += "\n"
      print output


def printSSHConfigInfo( loginInfoDict, keyList ) :
  '''Prints the SSH config Information from all AMs, all Users and all hosts '''

  sshConfList={}
  for amUrl, amInfo in loginInfoDict.items() :
    for item in amInfo["info"] :
      output = ""
      if options.readyonly :
        try:
          if item['geni_status'] != "ready" :
            continue
        except KeyError:
          print "There is no status information for node %s. Print login info."
      # If there are status info print it, if not just skip it

      keys = getKeysForUser(amInfo["amType"], item["username"], keyList)

      output = """ 
Host %(client_id)s
  Port %(port)s
  HostName %(hostname)s
  User %(username)s """ % item

      for key in keys: 
        output +="""
  IdentityFile %s """ % key

      try:
        sshConfList[item["username"]].append(output)
      except KeyError:
        sshConfList[item["username"]] = []
        sshConfList[item["username"]].append(output)
  
  for user, conf in sshConfList.items():
    print "="*80
    print "SSH CONFIGURATION INFO for User %s" % user
    print "="*80
    for c in conf:
      print c
      print "\n"


def main(argv=None):
    global slicename, options, config

    parseArguments(argv=argv)

    # Call omni.initialize so that we get the config structure that
    # contains the configuration parameters from the omni_config file
    # We need them to get the ssh keys per user
    framework, config, args, opts = omni.initialize( [], options )

    keyList = findUsersAndKeys( )
    if sum(len(val) for val in keyList.itervalues())== 0:
      output = "ERROR:There are no keys. You can not login to your nodes.\n"
      sys.exit(-1)

    # Run equivalent of 'omni.py getversion'
    argv = ['getversion']
    try:
      text, getVersion = omni.call( argv, options )
    except omnierror.AMAPIError:
      print "ERROR: There was an error executing getVersion, review the logs."

    loginInfoDict = {}
    for amUrl, amOutput in getVersion.items() :
      if not amOutput :
        print "%s returned an error on getVersion, skip!"
        continue
      amType = getAMTypeFromGetVersionOut(amUrl, amOutput) 

      if amType == "foam" :
        print "No login information for FOAM! Skip %s" %amUrl
        continue
      # XXX Although ProtoGENI returns the service tag in the manifest
      # it does not contain information for all the users, so we will 
      # stick with the sliverstatus until this is fixed
      if amType == "sfa" or amType == "protogeni" :
        amLoginInfo = getInfoFromSliverStatus(amUrl, amType)
        if len(amLoginInfo) > 0 :
          loginInfoDict[amUrl] = {'amType' : amType,
                                  'info' : amLoginInfo
                                 }
        continue
      if amType == "orca":
        amLoginInfo = getInfoFromListResources(amUrl)
        # Get the status only if we care
        if len(amLoginInfo) > 0 :
          if options.readyonly:
            amLoginInfo = addNodeStatus(amUrl, amType, amLoginInfo)
          loginInfoDict[amUrl] = {'amType':amType,
                                  'info':amLoginInfo
                                 }
    printSSHConfigInfo(loginInfoDict, keyList)
    printLoginInfo(loginInfoDict, keyList)
        
if __name__ == "__main__":
    sys.exit(main())
