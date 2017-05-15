#!/usr/bin/env python

#----------------------------------------------------------------------
# Copyright (c) 2013-2016 Raytheon BBN Technologies
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
#from gcf.omnilib.stitch.objects import DCN_AM_RETRY_INTERVAL_SECS as DCN_AM_RETRY_INTERVAL_SECS

# URL of the SCS service
SCS_URL = "https://geni-scs.net.internet2.edu:8443/geni/xmlrpc"

DEFAULT_CAPACITY = 20000 # in Kbps

# Call is the way another script might call this.
# It initializes the logger, options, config (using omni functions),
# and then dispatches to the stitch handler
#def call(argv, options=None):

#    if options is not None and not options.__class__==optparse.Values:
#        raise OmniError("Invalid options argument to call: must be an optparse.Values object")

#    if argv is None or not type(argv) == list:
#        raise OmniError("Invalid argv argument to call: must be a list")

def getParser():
    ##############################################################################
    # Get a parser from omni that understands omni options
    ##############################################################################
    parser = omni.getParser()
    # update usage for help message
    omni_usage = parser.get_usage()
    parser.set_usage("\n" + "GENI Omni Stitching Tool\n" + "Copyright (c) 2013-2016 Raytheon BBN Technologies\n" + 
                     omni_usage+
                     "\nstitcher.py reserves multi-aggregate fully bound topologies, including stitching, if the call is createsliver or allocate; else it just calls Omni.\n")

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
    parser.add_option("--includehoponpath", metavar="HOP_INCLUDE PATH", action="append", nargs=2,
                      help="Hop URN to include and then path (link client_id) to include it on")
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
                      help="Seconds to sleep before retrying at DCN aggregates (default: %default)",
                      default=gcf.omnilib.stitch.objects.DCN_AM_RETRY_INTERVAL_SECS)
    parser.add_option("--ionStatusIntervalSecs", type="int", 
                      help="Seconds to sleep between sliverstatus calls at DCN aggregates (default %default)",
                      default=30)
    parser.add_option("--noReservation", default=False, action="store_true",
                      help="Do no reservations: just generate the expanded request RSpec (default %default)")
    parser.add_option("--scsURL",
                      help="URL to the SCS service. Default: Value of 'scs_url' in omni_config or " + SCS_URL,
                      default=None)
    parser.add_option("--timeout", default=0, type="int",
                      help="Max minutes to allow stitcher to run before killing a reservation attempt (default %default minutes, 0 means no timeout).")
    parser.add_option("--noAvailCheck", default=False, action="store_true",
                      help="Disable checking current VLAN availability where possible.")
    parser.add_option("--genRequest", default=False, action="store_true",
                      help="Generate and save an expanded request RSpec, but do no reservation.")
    parser.add_option("--noDeleteAtEnd", default=False, action="store_true",
                      help="On failure or Ctrl-C do not delete any reservations completed at some aggregates (default %default).")
    parser.add_option("--noTransitAMs", default=False, action="store_true",
                      help="Do not reserve resources at intermediate / transit aggregates; allow experimenter to manually complete the circuit (default %default).")
    parser.add_option("--noSCS", default=False, action="store_true",
                      help="Do not call the SCS to expand or add a stitching extension. Use this only if supplying any needed stitching extension and the SCS would fail your request. (default %default).")
    parser.add_option("--fakeModeDir",
                      help="Developers only: If supplied, use canned server responses from this directory",
                      default=None)
    parser.add_option("--savedSCSResults", default=None,
                      help="Developers only: Use this saved file of SCS results instead of calling SCS (saved previously using --debug)")
    parser.add_option("--useSCSSugg", default=False, action="store_true",
                      help="Developers only: Always use the VLAN tags the SCS suggests, not 'any'.")
    parser.add_option("--noEGStitching", default=False, action="store_true",
                      help="Developers only: Use GENI stitching, not ExoGENI stitching.")
    parser.add_option("--noEGStitchingOnLink", metavar="LINK_ID", action="append",
                      help="Developers only: Use GENI stitching on this particular link only, not ExoGENI stitching.")
    #  parser.add_option("--script",
    #                    help="If supplied, a script is calling this",
    #                    action="store_true", default=False)

    # Put our logs in a different file by default
    parser.set_defaults(logoutput='stitcher.log')

    # Configure stitcher with a specific set of configs by default

    # First, set the default logging config file
    lcfile = os.path.join(sys.path[0], os.path.join("gcf","stitcher_logging.conf"))

    # Windows & Mac binaries do not get the .conf file in the proper archive apparently
    # And even if they did, it appears the logging stuff can't readily read .conf files
    # from that archive.
    # Solution 1 that fails (no pkg_resources on windows so far, needs the file in the .zip)
    #    lcfile = pkg_resources.resource_filename("gcf", "stitcher_logging.conf")
    # Solution2 is to use pkgutil to read the file from the archive
    # And write it to a temp file that the logging stuff can use.
    # Note this requires finding some way to get the file into the archive
    # With whatever I do, I want to read the file direct from source per above if possible

    if not os.path.exists(lcfile):
        # File didn't exist as a regular file among python source
        # Try it where py2exe (Windows) puts resources (one directory up, parallel to zip). 
        lcfile = os.path.join(os.path.normpath(os.path.join(sys.path[0], '..')), os.path.join("gcf","stitcher_logging.conf"))

    if not os.path.exists(lcfile):
        # File didn't exist in dir parallel to zip of source
        # Try one more up, but no gcf sub-directory - where py2app (Mac) puts it.
        lcfile = os.path.join(os.path.normpath(os.path.join(os.path.join(sys.path[0], '..'), '..')), "stitcher_logging.conf")

    if not os.path.exists(lcfile):
        # Now we'll try a couple approaches to read the .conf file out of a source zip
        # And put it in a temp directory
        tmpdir = os.path.normpath(os.getenv("TMPDIR", os.getenv("TMP", "/tmp")))
        if tmpdir and tmpdir != "" and not os.path.exists(tmpdir):
            os.makedirs(tmpdir)
        lcfile = os.path.join(tmpdir, "stitcher_logging.conf")

        try:
            # This approach requires the .conf be in the source.zip (e.g. library.zip, python27.zip)
            # On Windows (py2exe) this isn't easy apparently. But it happens by default on Mac (py2app)
            # Note that could be a manual copy & paste possibly
            import pkgutil
            lconf = pkgutil.get_data("gcf", "stitcher_logging.conf")
            with open(lcfile, 'w') as file:
                file.write(lconf)
            #print "Read config with pkgutils %s" % lcfile
        except Exception, e:
            #print "Failed to read .conf file using pkgutil: %s" % e
            # If we didn't get the file in the archive, use the .py version
            # I find this solution distasteful
            from gcf import stitcher_logging_deft
            try:
                with open(lcfile, 'w') as file:
                    file.write(stitcher_logging_deft.DEFT_STITCHER_LOGGING_CONFIG)
            except Exception, e2:
                sys.exit("Error configuring logging: Could not write (from python default) logging config file %s: %s" % (lcfile, e2))
            #print "Read from logging config from .py into tmp file %s" % lcfile
    parser.set_defaults(logconfig=lcfile)

    return parser

# Call is the way another script might call this.
# It initializes the logger, options, config (using omni functions),
# and then dispatches to the stitch handler
def call(argv, options=None):

    script_mode = False
    if argv is None or not type(argv) == list:
        raise OmniError("Invalid argv argument to call: must be a list")

    if options is not None and not options.__class__== optparse.Values:
        raise OmniError("Invalid options argument to call: must be an optparse.Values object")
    elif(options is not None and options.__class__== optparse.Values):
        args = argv
        script_mode = True
    else:
        # We assume here that this routine has been called as a library
        # Have omni use our parser to parse the args, manipulating options as needed
        options, args = omni.parse_args(argv, parser=getParser())


    # If there is no fileDir, then we try to write to the CWD. In some installations, that will
    # fail. So test writing to CWD. If that fails, set fileDir to a temp dir to write files ther.
    if not options.fileDir:
        testfile = None
        handle = None
        try:
            import tempfile
            handle, testfile = tempfile.mkstemp(dir='.')
            #print "Can write to CWD: created %s" % testfile
            os.close(handle)
        except Exception, e:
            #print "Cannot write to CWD '%s' for output files: %s" % (os.path.abspath('.'), e)
            tmpdir = os.path.normpath(os.getenv("TMPDIR", os.getenv("TMP", "/tmp")))
            if tmpdir and tmpdir != "" and not os.path.exists(tmpdir):
                os.makedirs(tmpdir)
            testfile1 = None
            handle1 = None
            try:
                import tempfile
                handle1, testfile1 = tempfile.mkstemp(dir=tmpdir)
                os.close(handle1)
                options.fileDir = tmpdir
            except Exception, e1:
                sys.exit("Cannot write to temp directory '%s' for output files. Try setting `--fileDir` to point to a writable directory. Error: %s'" % (tmpdir, e1))
            finally:
                try:
                    os.unlink(testfile1)
                except Exception, e2:
                    pass
        finally:
            try:
                os.unlink(testfile)
            except Exception, e2:
                pass

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
            handle = None
            try:
                import tempfile
                handle, testfile = tempfile.mkstemp(dir=fpd2)
                os.close(handle)
            except Exception, e:
                sys.exit("Cannot write to directory '%s' specified by '--fileDir': %s" % (fpDir, e))
            finally:
                try:
                    os.unlink(testfile)
                except Exception, e2:
                    pass
        options.fileDir = fpDir
        options.logoutput = os.path.normpath(os.path.join(os.path.abspath(options.fileDir), options.logoutput))

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
            try:
                os.rename(bfn, dfn)
            except OSError, e:
                # Issue #824 partial solution
                if "being used by another process" in str(e):
                    # On Windows, when another stitcher instance running in same directory, so has stitcher.log open
                    # WindowsError: [Error 32] The process cannot access the file because it is being used by another process
                    sys.exit("Error: Is another stitcher process running in this directory? Run stitcher from a different directory, or re-run with the option `--fileDir <separate directory for this run's output files>`")
                else:
                    raise

    # Then have Omni configure the logger
    try:
        omni.configure_logging(options)
    except Exception, e:
        sys.exit("Failed to configure logging: %s" % e)

    # Now that we've configured logging, reset this to None 
    # to avoid later log messages about configuring logging
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
    # Load custom config _after_ system agg_nick_cache,
    # which also sets omni_defaults
    config = omni.load_config(options, logger, config)
    if config.has_key('omni_defaults') and config['omni_defaults'].has_key('scs_url'):
        if options.scsURL is not None:
            logger.debug("Ignoring omni_config default SCS URL of '%s' because commandline specified '%s'", config['omni_defaults']['scs_url'], options.scsURL)
        else:
            options.scsURL = config['omni_defaults']['scs_url']
            logger.debug("Using SCS URL from omni_config: %s", options.scsURL)
    else:
        if options.scsURL is None:
            options.scsURL = SCS_URL
            logger.debug("Using SCS URL default: %s", SCS_URL)
        else:
            logger.debug("Using SCS URL from commandline: %s", options.scsURL)

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

    if not script_mode:
      nondefOpts = omni.getOptsUsed(parser, options)
      if options.debug:
          logger.info(omni.getSystemInfo() + "\nStitcher: " + omni.getOmniVersion())
          logger.info("Running stitcher ... %s Args: %s" % (nondefOpts, " ".join(args)))
      else:
          # Force this to the debug log file only
          logger.debug(omni.getSystemInfo() + "\nStitcher: " + omni.getOmniVersion())
          logger.debug("Running stitcher ... %s Args: %s" % (nondefOpts, " ".join(args)))

    omni.checkForUpdates(config, logger)

    if options.defaultCapacity < 1:
        logger.warn("Specified a tiny default link capacity of %dKbps!", options.defaultCapacity)
    # FIXME: Warn about really big capacities too?

    if options.useExoSM and options.noExoSM:
        sys.exit("Cannot specify both useExoSM and noExoSM")

    if options.useExoSM and options.noEGStitching:
        sys.exit("Cannot specify both useExoSM and noEGStitching")

    if options.useExoSM and options.noEGStitchingOnLink:
        sys.exit("Cannot specify both useExoSM and noEGStitchingOnLink")

    if options.noExoSM:
        if not options.noEGStitching:
            logger.debug("Per options avoiding ExoSM. Therefore, not using EG Stitching")
            options.noEGStitching = True
            # Note that the converse is not true: You can require noEGStitching and still use
            # the ExoSM, assuming we edit the request to the ExoSM carefully.

    if options.noTransitAMs:
        logger.info("Per options not completing reservations at transit / SCS added aggregates")
        if not options.noDeleteAtEnd:
            logger.debug(" ... therefore setting noDeleteAtEnd")
            options.noDeleteAtEnd = True
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
