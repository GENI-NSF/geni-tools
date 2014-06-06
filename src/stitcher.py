#!/usr/bin/env python

#----------------------------------------------------------------------
# Copyright (c) 2013-2014 Raytheon BBN Technologies
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
import logging.handlers
import optparse 
import os
import sys

import gcf.oscript as omni
from gcf.omnilib.util import OmniError, AMAPIError
from gcf.omnilib.stitchhandler import StitchingHandler
from gcf.omnilib.stitch.utils import StitchingError, prependFilePrefix
from gcf.omnilib.stitch.objects import Aggregate
import gcf.omnilib.stitch.objects
#from gcf.omnilib.stitch.objects import DCN_AM_RETRY_INTERVAL_SECS as objects.DCN_AM_RETRY_INTERVAL_SECS

# URL of the SCS service
SCS_URL = "http://oingo.dragon.maxgigapop.net:8081/geni/xmlrpc"

DEFAULT_CAPACITY = 20000 # in Kbps

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
    parser.set_usage("\n" + "GENI Omni Stitching Tool\n" + "Copyright (c) 2014 Raytheon BBN Technologies\n" + 
                     omni_usage+
                     "\nstitcher.py does stitching if the call is createsliver or allocate, else it just calls Omni.\n")

   ##############################################################################
    # Add additional optparse.OptionParser style options
    # Be sure not to re-use options already in use by omni for
    # different meanings, otherwise you'll raise an OptionConflictError
    ##############################################################################
    parser.add_option("--defaultCapacity", default=DEFAULT_CAPACITY,
                      type="int", help="Default stitched link capacity in Kbps - default is 20000 meaning ~20Mbps")
    parser.add_option("--excludehop", metavar="HOP_EXCLUDE", action="append",
                      help="Hop URN to exclude from any path")
    parser.add_option("--includehop", metavar="HOP_INCLUDE", action="append",
                      help="Hop URN to include on every path - use with caution")
    parser.add_option("--fixedEndpoint", default=False, action="store_true",
                      help="RSpec uses a static endpoint - add a fake node with an interface on every link")
    parser.add_option("--noExoSM", default=False, action="store_true",
                      help="Always use local ExoGENI racks, not the ExoSM, where possible (default %default)")
    parser.add_option("--useExoSM", default=False, action="store_true",
                      help="Always use the ExoGENI ExoSM, not the individual EG racks, where possible (default %default)")
    parser.add_option("--fileDir", default=None,
                      help="Directory for all output files generated. By default some files go in /tmp, some in the CWD, some in ~/.gcf.")
    parser.add_option("--logFileCount", default=5, type="int",
                      help="Number of backup log files to keep, Default %default")
    parser.add_option("--ionRetryIntervalSecs", type="int", 
                      help="Seconds to sleep before retrying at ION (default: %default)",
                      default=gcf.omnilib.stitch.objects.DCN_AM_RETRY_INTERVAL_SECS)
    parser.add_option("--ionStatusIntervalSecs", type="int", 
                      help="Seconds to sleep between sliverstatus calls at ION (default %default)",
                      default=30)
    parser.add_option("--noReservation", default=False, action="store_true",
                      help="Do no reservations: just generate the expanded request RSpec (default %default)")
    parser.add_option("--scsURL",
                      help="URL to the SCS service. Default: %default",
                      default=SCS_URL)
    parser.add_option("--fakeModeDir",
                      help="If supplied, use canned server responses from this directory",
                      default=None)
    parser.add_option("--savedSCSResults", default=None,
                      help="Developers only: Use this saved file of SCS results instead of calling SCS (saved previously using --debug)")
    #  parser.add_option("--script",
    #                    help="If supplied, a script is calling this",
    #                    action="store_true", default=False)

    # Put our logs in a different file by default
    parser.set_defaults(logoutput='stitcher.log')

    # Configure stitcher with a specific set of configs by default
    parser.set_defaults(logconfig=os.path.join(sys.path[0], os.path.join("gcf","stitcher_logging.conf")))

    # Have omni use our parser to parse the args, manipulating options as needed
    options, args = omni.parse_args(argv, parser=parser)

    # Create the dirs for fileDir option as needed
    if options.fileDir:
        fpDir = os.path.normpath(os.path.expanduser(options.fileDir))
        if fpDir and fpDir != "":
            if not fpDir.endswith(os.sep):
                fpDir += os.sep
            fpd2 = os.path.abspath(fpDir)
            if not os.path.exists(fpd2):
                try:
                    os.makedirs(fpd2)
                except Exception, e:
                    sys.exit("Failed to create '%s' for saving files per --fileDir option: %s" % (fpd2, e))
            if not os.path.isdir(fpd2):
                sys.exit("Path specified in '--fileDir' is not a directory: %s" % fpd2)
            testfile = None
            try:
                import tempfile
                handle, testfile = tempfile.mkstemp(dir=fpDir)
            except Exception, e:
                sys.exit("Cannot write to directory '%s' specified by '--fileDir': %s" % (fpDir, e))
            finally:
                try:
                    os.unlink(testfile)
                except:
                    pass
        options.fileDir = fpDir
        options.logoutput = os.path.normpath(os.path.join(options.fileDir, options.logoutput))

    # Set up the logger
    # First, rotate the logfile if necessary
    if options.logoutput:
        options.logoutput = os.path.normpath(os.path.expanduser(options.logoutput))
    if options.logoutput and os.path.exists(options.logoutput) and options.logFileCount > 0:
        backupCount = options.logFileCount
        bfn = options.logoutput
        # Code from python logging.handlers.RotatingFileHandler.doRollover()
        for i in range(backupCount - 1, 0, -1):
            sfn = "%s.%d" % (bfn, i)
            dfn = "%s.%d" % (bfn, i + 1)
            if os.path.exists(sfn):
                if os.path.exists(dfn):
                    os.remove(dfn)
                os.rename(sfn, dfn)
        dfn = bfn + ".1"
        if os.path.exists(dfn):
            os.remove(dfn)
        if os.path.exists(bfn):
            os.rename(bfn, dfn)

    omni.configure_logging(options)

    # Now that we've configured logging, reset this to None to avoid later log messages about configuring logging
    options.logconfig = None

    logger = logging.getLogger("stitcher")

    if options.fileDir:
        logger.info("All files will be saved in the directory '%s'", os.path.abspath(options.fileDir))

    # We use the omni config file
    # First load the agg nick cache

    # First, suppress all but WARN+ messages on console
    if not options.debug:
        lvl = logging.INFO
        handlers = logger.handlers
        if len(handlers) == 0:
            handlers = logging.getLogger().handlers
        for handler in handlers:
            if isinstance(handler, logging.StreamHandler):
                lvl = handler.level
                handler.setLevel(logging.WARN)
                break

    config = omni.load_agg_nick_config(options, logger)
    config = omni.load_config(options, logger, config)

    if not options.debug:
        handlers = logger.handlers
        if len(handlers) == 0:
            handlers = logging.getLogger().handlers
        for handler in handlers:
            if isinstance(handler, logging.StreamHandler):
                handler.setLevel(lvl)
                break

    #logger.info("Using AM API version %d", options.api_version)

    # Make any file prefix be part of the output file prefix so files go in the right spot
    if options.prefix and options.fileDir:
        pIsDir = (options.prefix and options.prefix.endswith(os.sep))
        if not os.path.isabs(options.prefix):
            options.prefix = os.path.normpath(os.path.join(options.fileDir, options.prefix))
        else:
            # replace any directory in prefix and use the fileDir
            options.prefix = prependFilePrefix(options.fileDir, options.prefix)
        if pIsDir:
            options.prefix += os.sep
    elif options.fileDir:
        options.prefix = options.fileDir

#    logger.debug("--prefix is now %s", options.prefix)

    # Create the dirs needed for options.prefix if specified
    if options.prefix:
        fpDir = os.path.normpath(os.path.expanduser(os.path.dirname(options.prefix)))
        if fpDir and fpDir != "" and not os.path.exists(fpDir):
            try:
                os.makedirs(fpDir)
            except Exception, e:
                sys.exit("Failed to create '%s' for saving files per --prefix option: %s" % (fpDir, e))

    if options.fakeModeDir:
        if not os.path.isdir(options.fakeModeDir):
            logger.error("Got Fake Mode Dir %s that is not a directory!", options.fakeModeDir)
            raise StitchingError("Fake Mod path not a directory: %s" % options.fakeModeDir)
        else:
            logger.info("Running with Fake Mode Dir %s", options.fakeModeDir)

    Aggregate.PAUSE_FOR_DCN_AM_TO_FREE_RESOURCES_SECS = options.ionRetryIntervalSecs
    Aggregate.SLIVERSTATUS_POLL_INTERVAL_SEC = options.ionStatusIntervalSecs

    nondefOpts = omni.getOptsUsed(parser, options)
    if options.debug:
        logger.info(omni.getSystemInfo() + "\nStitcher: " + omni.getOmniVersion())
        logger.info("Running stitcher ... %s Args: %s" % (nondefOpts, " ".join(args)))
    else:
        # Force this to the debug log file only
        logger.debug(omni.getSystemInfo() + "\nStitcher: " + omni.getOmniVersion())
        logger.debug("Running stitcher ... %s Args: %s" % (nondefOpts, " ".join(args)))

    if options.defaultCapacity < 1:
        logger.warn("Specified a tiny default link capacity of %dKbps!", options.defaultCapacity)
    # FIXME: Warn about really big capacities too?
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
