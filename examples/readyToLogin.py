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

import string
import sys
import omni
import os.path
from optparse import OptionParser

################################################################################
# Requires that you have omni installed or the path to gcf/src in your
# PYTHONPATH.
#
# For example put the following in your bashrc:
#     export PYTHONPATH=${PYTHONPATH}:path/to/gcf/src
#
################################################################################

def findUsersAndKeys( config ):
    """Look in omni_config for user and key information to pass to ssh"""
    keyList = []
    for user in config['users']:
        # convert strings containing public keys (foo.pub) into
        # private keys (foo)
        privuserkeys = string.replace(user['keys'].replace(" ",""), ".pub","")
        privuserkeys = privuserkeys.split(",")
        for key in privuserkeys:
            if not os.path.exists(os.path.expanduser(key)):
                print "Key file [%s] does NOT exist." % key
            else:
                keyList.append(key)
    return keyList

def sshIntoNodes( sliverStat, inXterm=True, keyList="" , readyOnly=False):
    """Wrapper to determine type of node (PL, PG) and ssh into it."""

    if type(sliverStat) != type({}):
        print "sliverStat is not a dictionary"
        return 

    for aggName, aggStat in sliverStat.items():
        # PlanetLab sliverstatus
        try:
            aggStat['pl_expires']
            print ""
            print "="*80
            # In PlanetLAB after you delete a silver you get an empty sliver, i.e. a sliver
            # with no resources, so check whether there are any resources listed in siverstatus
            # to determin whether this is actually a sliver or not
            if len(aggStat['geni_resources']) > 0 :
                print "Aggregate [%s] has a PlanetLab sliver." % aggName
                login = loginToPlanetlab( aggStat, inXterm, keyList=keyList, readyOnly=readyOnly )

                if login is not None:
                    print login
            else :
                print "Aggregate [%s] has No PlanetLab sliver." % aggName
            print "="*80
            print ""
        except:
            pass

        # ProtoGENI sliverstatus
        try:
            aggStat['pg_expires']
            print ""
            print "="*80
            print "Aggregate [%s] has a ProtoGENI sliver.\n" % aggName
            login = loginToProtoGENI( aggStat, inXterm, keyList=keyList, readyOnly=readyOnly )
            if login is not None:
                print login
            print "="*80
            print ""
        except:
            pass

def loginToPlanetlab( sliverStat, inXterm=True, keyList=[], readyOnly=False ):
    """Print command to ssh into a PlanetLab host."""
    output = ""
    for resourceDict in sliverStat['geni_resources']: 
        # If the user only wants the nodes that are in ready state, skip over all 
        # nodes that are not ready
        if (not sliverStat['pl_login']) or (not resourceDict['pl_hostname']):
            return None
        if (readyOnly is True and resourceDict['geni_status'].strip() != "ready") :
          continue
        output += "\n%s's geni_status is: %s (pl_boot_state:%s) \n" % (resourceDict['pl_hostname'], resourceDict['geni_status'],resourceDict['pl_boot_state'])
        # Check if node is in ready state
        output += "Login using:\n"

        if len(keyList) == 0:
            output = "There are no keys. You can not login to your nodes.\n"
        for key in keyList:
            output += "\t"
            if inXterm is True:
                output += "xterm -e "
            output += "ssh -i %s %s@%s" % ( key, sliverStat['pl_login'], resourceDict['pl_hostname'])
            if inXterm is True:
                output += " &"
            output += "\n"
    return output

def loginToProtoGENI( sliverStat, inXterm=True, keyList=[], readyOnly=False ):
    """Print command to ssh into a ProtoGENI host."""
    output = ""
    for resourceDict in sliverStat['geni_resources']: 
        # If the user only wants the nodes that are in ready state, skip over all 
        # nodes that are not ready
        if (readyOnly is True and resourceDict['geni_status'].strip() != "ready") :
          continue
        for children1 in resourceDict['pg_manifest']['children']:
            for children2 in children1['children']:
                child = children2['attributes']
                if (not child.has_key('username')) or (not child.has_key('hostname')):
                    continue
                output += "\n%s's geni_status is: %s\n" % (child['hostname'],resourceDict['geni_status'])
                output += "Login using:\n"

                if len(keyList) == 0:
                    output = "There are no keys. You can not login to your nodes.\n"

                for key in keyList:
                    output += "\t"
                    if inXterm is True:
                        output += "xterm -e "
                    output += "ssh -i %s %s@%s" % ( key, child['username'], child['hostname'])
                    if inXterm is True:
                        output += " &"
                    output += "\n"
    return output
def main(argv=None):
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
    
    # Run equivalent of 'omni.py sliverstatus username'
    argv = ['sliverstatus', slicename]
    text, sliverStatus = omni.call( argv, options )

    framework, config, args, opts = omni.initialize( argv, options )
    keyList = findUsersAndKeys( config )

    # Do Real Work
    # Determine how to SSH into nodes
    sshIntoNodes( sliverStatus, inXterm=options.xterm, keyList=keyList ,readyOnly=options.readyonly)
        
if __name__ == "__main__":
    sys.exit(main())
