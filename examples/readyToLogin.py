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

import sys
import omni
from optparse import OptionParser

################################################################################
# Requires that you have omni installed or the path to gcf/src in your
# PYTHONPATH.
#
# For example put the following in your bashrc:
#     export PYTHONPATH=${PYTHONPATH}:path/to/gcf/src
#
################################################################################


def sshIntoNodes( sliverStat, inXterm=True ):
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
            print "Aggregate [%s] has a PlanetLab sliver." % aggName
            login = loginToPlanetlab( aggStat, inXterm )
            if login is not None:
                print login
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
            login = loginToProtoGENI( aggStat, inXterm )
            if login is not None:
                print login
            print "="*80
            print ""
        except:
            pass

def loginToPlanetlab( sliverStat, inXterm=True ):
    """Print command to ssh into a PlanetLab host."""
    output = ""
    for resourceDict in sliverStat['geni_resources']: 
        if (not sliverStat['pl_login']) or (not resourceDict['pl_hostname']):
            return None
        output += "%s's pl_boot_state is: \n\t%s\n" % (resourceDict['pl_hostname'],resourceDict['pl_boot_state'])
        output += "Login using:\n\t"

        if inXterm is True:
            output += "xterm -e "
        output += "ssh %s@%s" % ( sliverStat['pl_login'], resourceDict['pl_hostname'])
        if inXterm is True:
            output += " &"
        output += "\n"
    return output

#def loginToProtoGENI( sliverStat, inXterm=True ):
#    return "Parsing of ProtoGENI resources is not yet implemented at this time."

def loginToProtoGENI( sliverStat, inXterm=True ):
    """Print command to ssh into a ProtoGENI host."""
#    print sliverStat
#    for resource in sliverStat['geni_resources']:
#        print resource['pg_manifest']['attributes']['hostname']
#        print resource['pg_manifest']['name']
#        print resource['pg_manifest']

    output = ""
    for resourceDict in sliverStat['geni_resources']: 
        for children1 in resourceDict['pg_manifest']['children']:
            for children2 in children1['children']:
                child = children2['attributes']
                if (not child['username']) or (not child['hostname']):
                    return None
                output += "%s's geni_status is: \n\t%s\n" % (child['hostname'],resourceDict['geni_status'])
                output += "Login using:\n\t"

                if inXterm is True:
                    output += "xterm -e "
                output += "ssh %s@%s" % ( child['username'], child['hostname'])
                if inXterm is True:
                    output += " &"
        output += "\n"
    return output


    # for resource in resourceDict['geni_resources']: 
    #     output = ""
    #     for manifest in resource['pg_manifest']: 
    #         if inXterm is True:
    #             output = "xterm -e "
    #             output += "ssh %s@%s" % ( manifest['name'], manifest['attributes']['hostname'])
    #     if inXterm is True:
    #         output += " &"
    #     return output 


def stripExtraLines( sliverstatusList ):
    """Remove extraneous output"""
    for line in sliverstatusList:
        if not line.startswith("{"):
            sliverstatusList = sliverstatusList[1:]
        else:
            return sliverstatusList
    return sliverstatusList


def main(argv=None):
    parser = omni.getParser()
    # Parse Options
    usage = "\n\tTypically: \treadyToLogin.py slicename"
    parser.set_usage(usage)

    parser.add_option("-x", "--xterm", dest="xterm",
                      action="store_false", 
                      default=True,
                      help="do NOT add xterm")
    (options, args) = parser.parse_args()
    
    if len(args) > 0:
        slicename = args[0]
    else:
        sys.exit("Must pass in slicename as argument of script.\nRun '%s -h' for more information."%sys.argv[0])
    
    # Run equivalent of 'omni.py sliverstatus username'
    text, sliverStatus = omni.call( ['sliverstatus', slicename], options )
    
#    print sliverStatus

    # Do Real Work
    # Determine how to SSH into nodes
    sshIntoNodes( sliverStatus, inXterm=options.xterm )
        
if __name__ == "__main__":
    sys.exit(main())
