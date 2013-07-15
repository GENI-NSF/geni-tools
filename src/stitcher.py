#!/usr/bin/env python

#----------------------------------------------------------------------
# Copyright (c) 2013 Raytheon BBN Technologies
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
'''Stitching client: Call the Stitching Computation Service to expand a single request RSpec. 
Then use Omni to allocate / createsliver reservations at all necessary aggregates. Return 
the combined manifest RSpec.'''

# Call this just like omni:
#     $ python ./src/stitcher.py -o createsliver <valid slice name> <path to RSpec file>
# (assuming a valid omni_config in the usual spots)
# 'createsliver' or 'allocate' commands with an RSpec that requires stitching will be processed 
# by the stitcher code.
# All other calls will be passed directly to Omni.
# All calls are APIv2 (hard-coded) currently.
# Input request RSpec does _not_ need a stitching extension, but should
# be a single RSpec for all resources that you want in your slice.
# To create a request that needs stitching, include at least 1 <link> elements with 
# more than 1 different <component_manager> elements (and no
#     shared_vlan element or link_type of other than VLAN)

# Selected known issues / todos
# - Thread calls to omni
# - Support AM API v3
# - Consolidate constants
# - Fully handle a VLAN_UNAVAILABLE error from an AM
# - Fully handle negotiating among AMs for a VLAN tag to use
#    As in when the returned suggestedVLANRange is not what was requested
# - fakeMode is incomplete
# - Tune counters, sleep durations, etc
# - Return a struct with detailed results (not just comments in manifest)
# - Return a struct on errors
# - Get AM URLs from the Clearinghouse
# - Use Authentication with the SCS
# - Support Stitching schema v2
# - Time out omni calls in case an AM hangs
# - opts.warn is used to suppress omni output. Clean that up. A scriptMode option?
# - Implement confirmSafeRequest to ensure no dangerous requests are made
# - Handle known EG error messages
# - Loop checking to see if EG sliverstatus says success or failure

import json
import logging
import optparse 
import os
import sys

import omni
from omnilib.util import OmniError, AMAPIError
from omnilib.stitchhandler import StitchingHandler
from omnilib.stitch.utils import StitchingError
from omnilib.stitch.objects import Aggregate
import omnilib.stitch.objects
#from omnilib.stitch.objects import DCN_AM_RETRY_INTERVAL_SECS as objects.DCN_AM_RETRY_INTERVAL_SECS

# URL of the SCS service
SCS_URL = "http://oingo.dragon.maxgigapop.net:8081/geni/xmlrpc"

# Call is the way another script might call this.
# It initializes the logger, options, config (using omni functions),
# and then dispatches to the stitch handler
def call(argv, options=None):

    if options is not None and not options.__class__==optparse.Values:
        raise OmniError("Invalid options argument to call: must be an optparse.Values object")

    if argv is None or not type(argv) == list:
        raise OmniError("Invalid argv argument to call: must be a list")

    ##############################################################################
    # Get a parser from omni that understands omni options
    ##############################################################################
    parser = omni.getParser()
    # update usage for help message
    omni_usage = parser.get_usage()
    parser.set_usage("\n" + "GENI Omni Stitching Tool\n" + "Copyright (c) 2013 Raytheon BBN Technologies\n" + 
                     omni_usage+
                     "\nstitcher.py does stitching if the call is createsliver or allocate, else it just calls Omni.\n")

   ##############################################################################
    # Add additional optparse.OptionParser style options
    # Be sure not to re-use options already in use by omni for
    # different meanings, otherwise you'll raise an OptionConflictError
    ##############################################################################
    parser.add_option("--fakeModeDir",
                      help="If supplied, use canned server responses from this directory",
                      default=None)
    parser.add_option("--scsURL",
                      help="URL to the SCS service",
                      default=SCS_URL)
    parser.add_option("--excludehop", metavar="HOP_EXCLUDE", action="append",
                      help="Hop URN to exclude from any path")
    parser.add_option("--includehop", metavar="HOP_INCLUDE", action="append",
                      help="Hop URN to include on every path - use with caution")
    parser.add_option("--ionRetryIntervalSecs", type="int", 
                      help="Seconds to sleep before retrying at ION (default 10*60)",
                      default=omnilib.stitch.objects.DCN_AM_RETRY_INTERVAL_SECS)
    parser.add_option("--ionStatusIntervalSecs", type="int", 
                      help="Seconds to sleep between sliverstatus calls at ION (default 30)",
                      default=30)
    parser.add_option("--fakeEndpoint", default=False, action="store_true",
                      help="RSpec uses a static endpoint - add a fake node with an interface on every link")
    parser.add_option("--noExoSM", default=False, action="store_true",
                      help="Always use local ExoGENI racks, not the ExoSM, where possible (default False)")
    #  parser.add_option("--script",
    #                    help="If supplied, a script is calling this",
    #                    action="store_true", default=False)

    # Put our logs in a different file by default
    parser.set_defaults(logoutput='stitcher.log')

    # options is an optparse.Values object, and args is a list
    options, args = parser.parse_args(argv)

    # Set an option indicating if the user explicitly requested the RSpec version
    options.ensure_value('explicitRSpecVersion', False)
    options.explicitRSpecVersion = ('-t' in argv or '--rspectype' in argv)

    if options.outputfile:
        options.output = True

    # Set up the logger
    omni.configure_logging(options)
    logger = logging.getLogger("stitcher")

    # We use the omni config file
    config = omni.load_config(options, logger)

    #logger.info("Using AM API version %d", options.api_version)

    if options.fakeModeDir:
        if not os.path.isdir(options.fakeModeDir):
            logger.error("Got Fake Mode Dir %s that is not a directory!", options.fakeModeDir)
            raise StitchingError("Fake Mod path not a directory: %s" % options.fakeModeDir)
        else:
            logger.info("Running with Fake Mode Dir %s", options.fakeModeDir)

    Aggregate.PAUSE_FOR_DCN_AM_TO_FREE_RESOURCES_SECS = options.ionRetryIntervalSecs
    Aggregate.SLIVERSTATUS_POLL_INTERVAL_SEC = options.ionStatusIntervalSecs

    if options.debug:
        logger.info(omni.getSystemInfo())

    handler = StitchingHandler(options, config, logger)
    return handler.doStitching(args)

# Goal of main is to call the 'call' method and print the result
def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    # FIXME: Print other header stuff?
    try:
        text, item = call(argv)
    # FIXME: If called from a script, then anything here?
#    if options.script:
        # return json
#        return result
#    else:
        print text
    except AMAPIError, ae:
        if ae.returnstruct and isinstance(ae.returnstruct, dict) and ae.returnstruct.has_key('code'):
            if isinstance(ae.returnstruct['code'], int) or isinstance(ae.returnstruct['code'], str):
                sys.exit(int(ae.returnstruct['code']))
            if isinstance(ae.returnstruct['code'], dict) and ae.returnstruct['code'].has_key('geni_code'):
                sys.exit(int(ae.returnstruct['code']['geni_code']))
        sys.exit(ae)

    except OmniError, oe:
        sys.exit(oe)

if __name__ == "__main__":
  sys.exit(main())
