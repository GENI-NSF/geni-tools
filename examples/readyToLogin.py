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
import sys, platform
import os.path
from optparse import OptionParser
import xml.etree.ElementTree as etree
import re
import getpass

import gcf.oscript as omni
import gcf.omnilib.util.omnierror as oe
from gcf.omnilib.handler import CallHandler
from gcf.omnilib.util.handler_utils import _lookupAggNickURLFromURNInNicknames as lookupURL

################################################################################
# Requires that you have omni installed and add the path to gcf/src in your
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
geni_username = None
NSPrefix = None
VALID_NS = ['{http://www.geni.net/resources/rspec/3}',
            '{http://www.protogeni.net/resources/rspec/2}'
           ]

def getYNAns(question):
    valid_ans=['','y', 'n']
    answer = raw_input("%s [Y,n]?" % question).lower()
    while answer not in valid_ans:
        answer = raw_input("Your input has to be 'y' or <ENTER> for yes, 'n' for no:").lower()
    if answer == 'n':
        return False
    return True


def getFileName(filename, defaultAnswer):
    """ This function takes as input a filename and if it already 
        exists it will ask the user whether to replace it or not 
        and if the file shouldn't be replaced it comes up with a
        unique name
    """
    # If the file exists ask the # user to replace it or not
    filename = os.path.expanduser(filename)
    filename = os.path.abspath(filename)
    if os.path.exists(filename):
        (basename, extension) = os.path.splitext(filename)
        question = "File " + filename + " exists, do you want to replace it "
        ans = defaultAnswer
        if ans is None:
          ans = getYNAns(question)
        if not ans:
            i = 1
            if platform.system().lower().find('darwin') != -1 :
                tmp_pk_file = basename + '(' + str(i) + ')' + extension
            else :
                tmp_pk_file = basename + '-' + str(i) + extension
            
            while os.path.exists(tmp_pk_file):
                i = i+1
                if platform.system().lower().find('darwin') != -1 :
                    tmp_pk_file = basename + '(' + str(i) + ')' + extension
                else :
                    tmp_pk_file = basename + '-' + str(i) + extension
            filename = tmp_pk_file
    return filename


def setNSPrefix(prefix):
  ''' Helper function for parsing rspecs. It sets the global variabl NSPrefix to
  the currently parsed rspec namespace. 
  '''
  global NSPrefix
  if prefix not in VALID_NS:
    print "Listresources namespace %s is not valid. Exit!" % prefix
    sys.exit(-1)

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
  try:
    dom = etree.fromstring(manifestStr) 
  except Exception, e:
    print "Couldn't parse the manifest RSpec."
    sys.exit(-1)

  setNSPrefix(re.findall(r'\{.*\}', dom.tag)[0])
  gsiNS = "{http://groups.geni.net/exogeni/attachment/wiki/RspecExtensions/sliver-info/1}" # Use to look up sliverstatus in RSpec for EG
  loginInfo = []
  for node_el in dom.findall(tag("node")):
    # Try to get the per node status from the EG specific geni_sliver_info RSpec extension
    geni_status = "unknown"
    for gsi_el in node_el.findall("%s%s" % (gsiNS, "geni_sliver_info")):
        if 'state' in gsi_el.keys():
            # print "Got a geni_sliver_info that says state is: %s" % (gsi_el.attrib['state'])
            geni_status = gsi_el.attrib['state']
    for serv_el in node_el.findall(tag("services")):
      for login_el in serv_el.findall(tag("login")):
         # print "Looking in login tag: %s with attribute %s in node %s" % (login_el, login_el.attrib, node_el.attrib["client_id"])
         try:
           loginInfo.append(login_el.attrib)
           loginInfo[-1]["client_id"] = node_el.attrib["client_id"]
           loginInfo[-1]["sliver_urn"] = node_el.attrib["sliver_id"]
         except AttributeError, ae:
           print "Couldn't get login information, maybe your sliver is not ready.  Run sliverstatus."
           print "Error: %s" % ae
           sys.exit(-1)
         if not loginInfo[-1].has_key("geni_status"):
             loginInfo[-1]["geni_status"] = geni_status #From the geni_sliver_info sub element
         if not loginInfo[-1].has_key("am_status"):
             loginInfo[-1]["am_status"] = geni_status #From the geni_sliver_info sub element
  return loginInfo

def findUsersAndKeys( ):
    """Look in omni_config for user and key information of the public keys that
    are installed in the nodes. It uses the global variable config and returns
    keyList which is a dictionary of keyLists per user"""
    keyList = {}
    if not config.has_key('users'):
      print "Your omni_config is missing the 'users' attribute."
      return keyList

    for user in config['users']:
        # convert strings containing public keys (foo.pub) into
        # private keys (foo)
        username = user['urn'].split('+')[-1]
        keyList[username] = []
        privuserkeys = string.replace(user['keys'], ".pub","")
        privuserkeys = privuserkeys.split(",")
        for key in privuserkeys:
            key = key.strip()
            if not os.path.exists(os.path.expanduser(key)):
                if options.include_keys:
                    print "Key file [%s] does NOT exist." % key
            else:
                keyList[username].append(key)
        #print "Found %d keys for %s" % (len(keyList[username]), username)
    return keyList

def getInfoFromSliceManifest( amUrl ) :
    tmpoptions = copy.deepcopy(options)
    tmpoptions.aggregate = [amUrl]

    
    # Run the equivalent of 'omni.py listresources <slicename>'
    if tmpoptions.api_version >= 3:
      apicall = 'describe'
    else :
      apicall = 'listresources'

    argv = [apicall, slicename]
    try:
      text, apicallout = omni.call( argv, tmpoptions )
    except (oe.AMAPIError, oe.OmniError) as err:
      print "ERROR: There was an error executing %s, review the logs." % apicall
      #print "error was: %s" % err
      return []
    key = amUrl
    if tmpoptions.api_version == 1:
      # Key is (urn,url)
      key = ("unspecified_AM_URN", amUrl)

    if not apicallout.has_key(key):
      if len(apicallout.keys()) == 1 :
        newkey = apicallout.keys()[0]
        print "WARN: Got result for AM URL %s instead of %s - did Omni redirect you?" % (newkey, key)
        key = newkey
      else:
        print "ERROR: No manifest found from %s at %s; review the logs." % \
        sys.exit(-1)

    if tmpoptions.api_version == 1:
      manifest = apicallout[key]
    else:
      if not apicallout[key].has_key("value"):
        print "ERROR: No value slot in return from %s from %s; review the logs."\
              % (apicall, amUrl)
        return []
      if not apicallout[key].has_key('code') or not isinstance(apicallout[key]['code'], dict) or not apicallout[key]['code'].has_key('geni_code') or apicallout[key]['code']['geni_code'] != 0:
          msg = "ERROR: Failed to get manifest from %s call at %s; " % (apicall, amUrl)
          if apicallout[key].has_key('output') and str(apicallout[key]['output']).strip() != "":
              msg += apicallout[key]['output']
          else:
              msg += "review the logs"
          print msg
          return []
      value = apicallout[key]["value"]

      if tmpoptions.api_version == 2:
        manifest = value
      else:
        if tmpoptions.api_version == 3:
            if not (isinstance(value, dict) and value.has_key('geni_rspec')):
                print "ERROR: Malformed return from %s at %s - no rspec found" % (apicall, amUrl)
                return []
            manifest = value['geni_rspec']
        else:
          print "ERROR: API v%s not yet supported" %tmpoptions.api_version
          return []          

    maniInfo = getInfoFromManifest(manifest)
    return maniInfo 



def getInfoFromSliverStatusPL( sliverStat ):

    loginInfo = []
    if not sliverStat or not sliverStat.has_key('geni_resources'):
      print "ERROR: Empty Sliver Status, or no geni_resources listed"
      return loginInfo

    for resourceDict in sliverStat['geni_resources']: 
      if (not sliverStat.has_key('pl_login') or not sliverStat['pl_login']) or (not resourceDict.has_key('pl_hostname') or not resourceDict['pl_hostname']):
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

def getSliverStatus( amUrl, amType ) :
    tmpoptions = copy.deepcopy(options)
    tmpoptions.aggregate = [amUrl]
        
    # Run equivalent of 'omni.py sliverstatus username'
    if tmpoptions.api_version >=3:
        # For AM API v3 and later:
        #   Run equivalent of 'omni.py status slicename'
        argv = ['status', slicename]
    else: 
        # For AM API v1 or v2:
        #   Run equivalent of 'omni.py sliverstatus slicename'
        argv = ['sliverstatus', slicename]
        
    try:
      text, sliverStatus = omni.call( argv, tmpoptions )
    except (oe.AMAPIError, oe.OmniError) :
      print "ERROR: There was an error executing sliverstatus, review the logs."
      sys.exit(-1)

    if not sliverStatus:
      print "ERROR: Got no SliverStatus for AM %s; check the logs. Message: %s" % (amUrl, text)
      sys.exit(-1)

    if not sliverStatus.has_key(amUrl):
      if len(sliverStatus.keys()) == 1 :
        newAmUrl = sliverStatus.keys()[0]
        print "WARN: Got result for AM URL %s instead of %s - did Omni redirect you?" % (newAmUrl, amUrl)
        amUrl = newAmUrl
      else:
        print "ERROR: Got no SliverStatus for AM %s; check the logs." % (amUrl)
        sys.exit(-1)
    return sliverStatus[amUrl]

def getInfoFromSliverStatus( amUrl, amType ) :
    sliverStatus = getSliverStatus( amUrl, amType )
    if amType == 'sfa' : 
      loginInfo = getInfoFromSliverStatusPL(sliverStatus)
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
  # ORCA does not have a code field, use orca_version
  if amOutput.has_key("value") and amOutput["value"].has_key("orca_version"):
    return "orca"
  return None
  
def getParser() : 
  parser = omni.getParser()

  usage = "\n\tTypically: \t%s slicename --useSliceAggregates" % os.path.basename(sys.argv[0]).split(".")[0]
  usage += "\n\nReports the status of nodes and the ssh command to login to them."
  usage += "\nTry the --no-keys and -o options."
  usage += "\nIn addition, takes the same options as omni (-c, -a, -V, etc)."
 
  usage += "\n\n== Providing a private key to ssh ==\nIn order to ssh, you will need to supply a private key.\nThere are three options for doing so:\n\t1) always append the -i option to the ssh command: \n\t\t$ ssh -i <path to private key> ...\n\t2) run an ssh agent and add your private key to that agent: \n\t\t$ ssh-add <path to private key>\n\t\t$ ssh ...\n\t3) create an ssh config file using the -o option:\n\t\t$ readyToLogin.py ... -o\n\t\tSSH Config saved at: .../sshconfig.txt\n\t\tLogin info saved at: .../logininfo.txt\n\t\t$ mv sshconfig.txt ~/.ssh/config\n"
  parser.set_usage(usage)
  
  # Parse Options
  parser.add_option("-x", "--xterm", dest="xterm",
                    action="store_true", 
                    default=False,
                    help="add xterm in the SSH commands")
  parser.add_option( "--readyonly", dest="readyonly",
                    action="store_true", 
                    default=False,
                    help="Only print nodes in ready state")
  parser.add_option( "--do-not-overwrite", dest="donotoverwrite",
                    action="store_true", 
                    default=False,
                    help="If '-o' is set do not overwrite files")

  parser.add_option("--no-keys", 
                    dest="include_keys",
                    help="Do not include ssh keys in output",
                    action="store_false", default=True)
  parser.add_option("--fallbackToStatusForPG",
                    dest="fallback_status_PG",
                    help="For ProtoGENI/InstaGENI nodes, fallback to querying login info from SliverStatus if it contains login info not found in the manifest.",
                    action="store_true", default=False)
  parser.add_option("--ansible-inventory",
                    dest="ansible_inventory",
                    help="Create an ansible inventory containing a single line for each host in your slice.",
                    action="store_true", default=False)
  parser.add_option("--ansible-username",
                    dest="ansible_username",
                    action="store", type="string", 
                    help="Specify the username to use in ansible.")
  parser.add_option("--no-ansible-username",
                    dest="no_ansible_username",
                    help="Never include the username to use in the ansible inventory file.",
                    action="store_true", default=False)
  return parser


def parseArguments( argv=None, opts=None ) :
  global slicename, options, config

  if opts is not None:
        # The caller, presumably a script, gave us an optparse.Values storage object.
        # Passing this object to parser.parse_args replaces the storage - it is pass
        # by reference. Callers may not expect that. In particular, multiple calls in
        # separate threads will conflict.
        # Make a deep copy
        options = copy.deepcopy(opts)
        argv = []

  parser = getParser()
  (options, args) = omni.parse_args(argv, options, parser=parser)

  if len(args) > 0:
      slicename = args[0]
  elif slicename == None:
      sys.exit("Must pass in slicename as argument of script.\nRun '%s -h' for more information."%sys.argv[0])


def addNodeStatus(amUrl, amType, amLoginInfo):
  ''' This function is intended to get the node status from SliverStatus, in
  case the login information comes from the manifest rspec that does not contain
  status information
  '''
  # Call SliverStatus
  sliverStatus = getSliverStatus( amUrl, amType )
  if not sliverStatus:
      print "ERROR: empty sliver status!"
      return amLoginInfo
  try:
      amSliverStat = sliverStatus
  except:
      print "ERROR: empty aggregate sliver status!"
      return amLoginInfo      
  if not isinstance(amSliverStat, dict) or not amSliverStat.has_key('geni_resources'):
      print "ERROR: aggregate sliver status lists no geni_resources!"
      return amLoginInfo
  if amType == "protogeni":
    amLoginInfo = addNodeStatusPG( amLoginInfo, amSliverStat )
    # 10/9/13 PG code is switching to include login info in manifest
    # a future release should remove the following line so that we don't fall back to SliverStatus
    if options.fallback_status_PG:
        print "Looking for information in the result of SliverStatus/Status"
        amLoginInfo = addNodeStatusCheckForPGFallback( amLoginInfo, amSliverStat )
  elif amType == "GRAM":
      amLoginInfo = addNodeStatusGRAM( amLoginInfo, amSliverStat )
  else:
      print "NOT IMPLEMENTED YET"
  return amLoginInfo

def addNodeStatusPG( amLoginInfo, amSliverStat ):
    for resourceDict in amSliverStat['geni_resources']:
      sliver_urn = ""
      if resourceDict.has_key("geni_urn"):
         sliver_urn = resourceDict["geni_urn"]
      geni_status = ""
      if resourceDict.has_key("geni_status"):
         geni_status = resourceDict["geni_status"]
      am_status = ""
      if resourceDict.has_key("pg_status"):
         am_status = resourceDict["pg_status"]
      for userLoginInfo in amLoginInfo:
         if userLoginInfo['sliver_urn'] != sliver_urn:
            continue
         userLoginInfo['geni_status'] = geni_status
         userLoginInfo['am_status'] = am_status
    return amLoginInfo

def addNodeStatusGRAM( amLoginInfo, amSliverStat ):
    for resourceDict in amSliverStat['geni_resources']:
      client_id = ""
      if resourceDict.has_key("geni_sliver_urn"):
         sliver_id = resourceDict["geni_sliver_urn"]
      geni_status = ""
      if resourceDict.has_key("geni_status"):
         geni_status = resourceDict["geni_status"]
      for userLoginInfo in amLoginInfo:
         if userLoginInfo['sliver_urn'] != sliver_id:
            continue
         userLoginInfo['geni_status'] = geni_status
    return amLoginInfo

def addNodeStatusCheckForPGFallback( userLoginInfo, sliverStat ):
    '''Not all PG AMs may provide login info in the manifest until they update their code.
    If this is the case, fall back to looking in SliverStatus.
    10/9/13 PG code is switching to include login info in manifest.
    A future release should remove the following line so that we don't fall back to SliverStatus.
    '''
    loginInfo = []
    pgKeyList = {}
    if not sliverStat:
      print "ERROR: empty sliver status!"
      return loginInfo

    if not sliverStat.has_key("users"):
      print "ERROR: No 'users' key in sliver status!"
      return loginInfo

    if not sliverStat.has_key('geni_resources'):
      print "ERROR: Sliver Status lists no resources"
      return loginInfo

    for userDict in sliverStat['users'] :
      if not userDict.has_key('login'):
        print "User entry had no 'login' key"
        continue
      pgKeyList[userDict['login']] = [] 
      if not userDict.has_key("keys"):
        print "User entry for %s had no keys" % userDict['login']
        continue
      for k in userDict['keys']:
          #XXX nriga Keep track of keys, in the future we can verify what key goes with
          # which private key
          pgKeyList[userDict['login']].append(k['key'])  
    for resourceDict in sliverStat['geni_resources']:
      if not resourceDict.has_key("pg_manifest"):
        print "No pg_manifest in this entry"
        continue
      sliver_urn = ""
      if resourceDict.has_key("geni_urn"):
         sliver_urn = resourceDict["geni_urn"]

      if not resourceDict['pg_manifest'].has_key('children'):
        print "pg_manifest entry has no children"
        continue
      for children1 in resourceDict['pg_manifest']['children']:
        if not children1.has_key('children'):
          #print "No child in resource[pg_man][children]"
          continue
        for children2 in children1['children']:
          if not children2.has_key("attributes"):
            #print "No attributes on child under pg_man/children"
            continue
          child = children2['attributes']
          port = ""
          hostname = ""
          if child.has_key("hostname"):
            hostname = child["hostname"]
          else:
            #print "No hostname"
            continue
          if child.has_key("port"):
            port = child["port"]
          client_id = ""
          if resourceDict["pg_manifest"].has_key("attributes") and resourceDict["pg_manifest"]["attributes"].has_key("client_id"):
            client_id = resourceDict["pg_manifest"]["attributes"]["client_id"]
          #else:
          #    print "Got no client_id from pg_man/attribs"
          geni_status = ""
          if resourceDict.has_key("geni_status"):
            geni_status = resourceDict["geni_status"]
          am_status = ""
          if resourceDict.has_key("pg_status"):
            am_status = resourceDict["pg_status"]

          ## Fallback to getting login info from SliverStatus ##
          # Keep track of which usernames we already have info for
          userLoginInfo_usernames = set()
          for item in userLoginInfo:
              if item['client_id'] != client_id :
                  continue
              userLoginInfo_usernames.add(item['username'])

          for user, keys in pgKeyList.items():
            if user in userLoginInfo_usernames:
                # skip users for whom we already have login info
                continue
            # add info for users not listed in the manifest
            userLoginInfo.append({'authentication':'ssh-keys',
                              'hostname':hostname,
                              'client_id': client_id,
                              'sliver_urn': sliver_urn,
                              'port':port,
                              'username':user,
                              'keys' : keys,
                              'geni_status':geni_status,
                              'am_status':am_status
                             })
    return userLoginInfo
  

def getKeysForUser( amType, username, keyList ):
  '''Returns a list of keys for the provided user based on the
     list from omni_config file that is saved at keyList
  '''
  userKeyList = []
  if not keyList:
    return userKeyList

  for user,keys in keyList.items() :
    #ProtoGENI actually creates accounts per user so check the username
    # before adding the key. ORCA and PL just add all the keys to one
    # user
    if amType in ["protogeni","orca"] and user != username :
        #print "Skipping keys for %s that is not %s" % (user, username)
        continue
    for k in keys:
      userKeyList.append(k)

  return userKeyList
    
def printLoginInfo( loginInfoDict, keyList ) :
  global options
  '''Prints the Login Information from all AMs, all Users and all hosts '''
  
  # Check if the output option is set
  defaultAnswer = not options.donotoverwrite
  prefix = ""
  if options.prefix and options.prefix.strip() != "":
    prefix = options.prefix.strip() + "-"
  if options.output :
    filename = getFileName(prefix+"logininfo.txt", defaultAnswer)
    f = open(filename, "w")
    print "Login info saved at: %s" % filename
  else :
    f = sys.stdout

  firstTime = {}

  for amUrl, amInfo in loginInfoDict.items() :
    f.write("\n")
    f.write("="*80+"\n")
    f.write("LOGIN INFO for AM: %s\n" % amUrl)
    f.write("="*80+"\n")

    f.write( "\nFor more login info, see the section entitled:\n\t 'Providing a private key to ssh' in 'readyToLogin.py -h'\n")

    sortedAMInfo = {}
    for item in amInfo['info']:
      if not sortedAMInfo.has_key( item['client_id'] ):
          sortedAMInfo[ item['client_id'] ] = []
      sortedAMInfo[ item['client_id'] ].append(item)

    for client_id, itemList in sortedAMInfo.items():
      for item in itemList:
          if not firstTime.has_key( amUrl ):
              firstTime[amUrl] = {}
          if not firstTime[amUrl].has_key( item['client_id'] ):
              firstTime[amUrl][item['client_id'] ] = True
          #    print "This is first time for %s" % item['client_id']
          output = ""
          if options.readyonly :
            try:
              if item['geni_status'] != "ready" :
                  #print "%s is not ready: %s" % (item['client_id'], item['geni_status'])
                  continue
            except KeyError:
              sys.stderr.write("There is no status information for node %s. Print login info." % item['client_id'])
          # If there are status info print it, if not just skip it
          try:
            if firstTime[amUrl][item['client_id'] ]:
                gsOut = ""
                amsOut = ""
                if item.has_key('geni_status') and item['geni_status'].strip()!="":
                    gsOut = "geni_status is: %s" % item['geni_status']
                if item.has_key('am_status') and item['am_status'].strip()!="":
                    amsOut = "am_status: %s" % item['am_status']
                if gsOut:
                    # if amsOut:
                    #    output += "\n%s's geni_status is: %s (am_status:%s) \n" % (item['client_id'], item['geni_status'], item['am_status'])
                    #else:
                    output += "\n%s's geni_status is: %s \n" % (item['client_id'], item['geni_status'])
                elif amsOut:
                        output += "\n%s's am_status is: %s \n" % (item['client_id'], item['am_status'])
                else:
                        output += "\n%s's geni_status is: unknown \n" % (item['client_id'])
                # Check if node is in ready state
            firstTime[amUrl][ item['client_id'] ]=False
          except KeyError as ke:
              #print "Got error looking in firstTime for %s: %s" % (item['client_id'], ke)
              pass

          keys = getKeysForUser(amInfo["amType"], item["username"], keyList)
          usrLoginMsg = "User %s logs in to %s using:\n" % (item['username'], item['client_id'])      
          if options.include_keys:
              if len(keys)>0:
                  output += usrLoginMsg
              #else:
              #    print "User %s has no keys" % item['username']
              for key in keys: 
                  output += printLoginInfoForOneUser( item, key=key )

          else:
              output += usrLoginMsg
              output += printLoginInfoForOneUser( item )

          f.write(output)
    if options.include_keys:
        f.write("\nNOTE: If your user is not listed, try using the --no-keys option.\n")

def printLoginInfoForOneUser( item, key=None ):
    output = "\t"
    if options.xterm :
        output += "xterm -e ssh"
    else :
        output += "ssh"

    if str(item['port']) != '22' : 
        output += " -p %s " % item['port']
    if key is not None:
        output += " -i %s" % ( key )
    output += " %s@%s" % ( item['username'], item['hostname'])
    if options.xterm :
        output += " &"
    output += "\n"
    return output

def printSSHConfigInfo( loginInfoDict, keyList ) :
  '''Prints the SSH config Information from all AMs, all Users and all hosts '''

# Check if the output option is set
  defaultAnswer = not options.donotoverwrite
  prefix = ""
  if options.prefix and options.prefix.strip() != "":
    prefix = options.prefix.strip() + "-"
  if options.output :
    filename = getFileName(prefix+"sshconfig.txt", defaultAnswer)
    f = open(filename, "w")
    print "SSH Config saved at: %s" % filename
  else :
    f = sys.stdout

  sshConfList={}
  for amUrl, amInfo in loginInfoDict.items() :
    for item in amInfo["info"] :
      output = ""
      if options.readyonly :
        try:
          if item['geni_status'] != "ready" :
            continue
        except KeyError:
          sys.stderr.write("There is no status information for node %s. Print login info.")
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
    f.write("#"+"="*40+"\n")
    f.write("#SSH CONFIGURATION INFO for User %s\n" % user)
    f.write("#"+"="*40+"\n")
    for c in conf:
      f.write(c)
      f.write("\n")

def get_geni_username( handler, framework):
    from gcf.omnilib.util.handler_utils import _get_user_urn
    from gcf.sfa.util.xrn import get_leaf
    username = get_leaf(_get_user_urn(handler.logger, framework.config))
    if not username:
        print "readyToLogin failed to find your GENI username.  Please supply it with the --ansible-username option."
        sys.exit(-1)
    return username


def main_no_print(argv=None, opts=None, slicen=None):
  global slicename, options, config, geni_username

  slicename = slicen
  parseArguments(argv=argv, opts=opts)

  # Call omni.initialize so that we get the config structure that
  # contains the configuration parameters from the omni_config file
  # We need them to get the ssh keys per user
  # Set loglevel to WARN to supress any normal printout
  options.warn = True
  framework, config, args, opts = omni.initialize( [], options )
  handler = CallHandler(framework,config,options)
  
  # If creating an ansible inventory don't check the keys
  if options.ansible_inventory:
      options.include_keys = False
      geni_username = get_geni_username( handler, framework )

  keyList = findUsersAndKeys( )
  if options.include_keys and sum(len(val) for val in keyList.itervalues())== 0:
    print "ERROR: There are no keys. You can not login to your nodes."
    sys.exit(-1)

  aggregateURNs = []
  if options.useSliceAggregates:
      # Find aggregates which have resources in this slice
      # Run equivalent of 'omni.py listslivers'
      argv = ['listslivers', slicename]
      try:
          text, slivers = omni.call( argv, options )
      except (oe.AMAPIError, oe.OmniError) :
          print "ERROR: There was an error executing listslivers, review the logs."
          sys.exit(-1)

      aggregateURNs = slivers.keys()
  if len(aggregateURNs) == 0 and (not options.aggregate or (len(options.aggregate) == 0)):
      if not options.useSliceAggregates:
          print "ERROR: You must specify which aggregates to check. Try using '--useSliceAggregates' to check all aggregates known to have resources for this slice, or '-a' to specify one or more specific aggregates."
      else:
          print "ERROR: There are no known resources at any aggregates. Try using '-a' to specify an aggregate."
      sys.exit(-1)

  # construct a list of aggregates to 
  newAggURLs = [ lookupURL( handler.logger, config, urn )[1] for urn in aggregateURNs ] 
  if options.aggregate:
      options.aggregate = options.aggregate + newAggURLs
  else:
      options.aggregate = newAggURLs

  # Disable useSliceAggregates at this point, because we already have the list - don't fetch it again
  options.useSliceAggregates = False
      
  # Run equivalent of 'omni.py getversion'
  argv = ['--ForceUseGetVersionCache', 'getversion']
  try:
    text, getVersion = omni.call( argv, options )
  except (oe.AMAPIError, oe.OmniError) :
    print "ERROR: There was an error executing getVersion, review the logs."
    sys.exit(-1)

  if not getVersion:
    print "ERROR: Got no GetVersion output; review the logs."
    sys.exit(-1)

  loginInfoDict = {}
  for amUrl, amOutput in getVersion.items() :
    if not amOutput :
      print "%s returned an error on getVersion, skip!" % amUrl
      continue
    amType = getAMTypeFromGetVersionOut(amUrl, amOutput) 

    if amType == "foam" :
      print "No login information for FOAM! Skip %s" %amUrl
      continue
    # XXX Although ProtoGENI returns the service tag in the manifest
    # it does not contain information for all the users, so we will 
    # stick with the sliverstatus until this is fixed
    if amType == "sfa": 
      amLoginInfo = getInfoFromSliverStatus(amUrl, amType)
      if len(amLoginInfo) > 0 :
        loginInfoDict[amUrl] = {'amType' : amType,
                                'info' : amLoginInfo
                               }
      continue
    else:
      # Getting login info from manifest"
      amLoginInfo = getInfoFromSliceManifest(amUrl)
      # Get the status only if we care
      if len(amLoginInfo) > 0 :
        if options.readyonly or (amType == "protogeni") or (amType == "GRAM"):
          amLoginInfo = addNodeStatus(amUrl, amType, amLoginInfo)
        loginInfoDict[amUrl] = {'amType':amType,
                                'info':amLoginInfo
                               }
      #else:
      #    print "Not getting node status for %s" % amUrl
        
  return loginInfoDict, keyList

def createAnsibleInventory(loginInfoDict, keyList):
  global options, geni_username
  '''List the Login Information from all AMs and all hosts '''

  # Check if the output option is set
  defaultAnswer = not options.donotoverwrite
  prefix = ""
  if options.prefix and options.prefix.strip() != "":
    prefix = options.prefix.strip() + "-"
  if options.output :
    filename = getFileName(prefix+"inventory", defaultAnswer)
    f = open(filename, "w")
    print "Host info saved in inventory file: %s" % filename
  else :
    f = sys.stdout

  firstTime = {}

  try:
      local_username = getpass.getuser()
  except:
      local_username = None

  include_username = None
  if options.ansible_username:
      include_username = options.ansible_username
  elif options.no_ansible_username:
      pass
  elif (geni_username is not None) and (local_username != geni_username):
      include_username = geni_username
  
  for amUrl, amInfo in loginInfoDict.items() :
    sortedAMInfo = {}
    for item in amInfo['info']:
      if not sortedAMInfo.has_key( item['client_id'] ):
          sortedAMInfo[ item['client_id'] ] = []
      sortedAMInfo[ item['client_id'] ].append(item)

    for client_id, itemList in sortedAMInfo.items():
      for item in itemList:
          output = ""
          if not firstTime.has_key( amUrl ):
              firstTime[amUrl] = {}
          if not firstTime[amUrl].has_key( item['client_id'] ):
              firstTime[amUrl][item['client_id'] ] = {}
              output += inventoryInfoForOneUser( item, username=include_username )
          f.write(output)

def inventoryInfoForOneUser( item, key=None, username=None ):
    output = "%s " % item['client_id']
    output += " ansible_ssh_host=%s " % item['hostname']
    if str(item['port']) != '22' :
        output += " ansible_ssh_port=%s " % item['port']
    if username:
        output += " ansible_ssh_user=%s " % username
    output += "\n"
    return output

def main(argv=None):
    if not argv:
        argv = sys.argv[1:]
    loginInfoDict, keyList = main_no_print(argv=argv)

    if not options.ansible_inventory:
        printSSHConfigInfo(loginInfoDict, keyList)
        #    for am, amInfo in loginInfoDict.items():
        #        print "+++ "+am+" +++"
        #        for info in amInfo["info"]:
        #            print "+++ "+ info['username']+" on "+ info['hostname']+":"+info['port'] +" +++"
        printLoginInfo(loginInfoDict, keyList)
    else:
        createAnsibleInventory(loginInfoDict, keyList)
    if not loginInfoDict:
      print "No login information found!!"
    if not keyList:
      print "No keys found!!"

if __name__ == "__main__":
    sys.exit(main())
