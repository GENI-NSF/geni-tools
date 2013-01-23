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

import json
import logging
import sys

import omni

# Useful bits of code....
#         self.logger = omni.configure_logging(self.options_copy)
#        parser.remove_option("-t")
#        parser.set_defaults(logoutput='acceptance.log')
# See omni_unittest.py#unittest_parser

def mustCallSCS(logger, request):
 # >=1 link in main body with >= 2 diff component_manager names and no shared_vlan extension
    return True

def confirmSliceOK(logger, args, options, config, slicename):
    # FIXME: I need to get the framework and use it to do getslicecred, etc.

    # Get slice URN from name
    # return error on error
    # Get slice cred
    # return error on error
    # Ensure slice not expired
    # return error on error
    pass

def doStitching(logger, options, config, args):
#[whatever my algorithm is from below]
    # Get request RSpec
    request = None
    command = None
    slicename = None
    if len(args) == 0:
        logger.error("Expected 3 args: <command = createsliver or allocate> <slice name> <rspec file path/url>")
    elif len(args) == 1:
        command = args[0]
    elif len(args) == 2:
        command = args[0]
        request = args[1]
        # FIXME: Create a slice
        omniargs = ["createslice", "stitcher"]
        (slicename, message) = omni.call(omniargs, options)
    else:
        command = args[0]
        slicename = args[1]
        request = args[2]
        if len(args) > 3:
            logger.warn("Arguments %s ignored", args[3:])
    logger.info("Command=%s, slice=%s, rspec=%s", command, slicename, request)

    # Read in the rspec as a string
    # FIXME
    requestString = ""

    # confirmGoodRequest
    # -- FIXME: this should be a function in rspec_util: is a request (schema, type), is parsable xml, passes rspeclint?

    # parseRequest
    # -- FIXME: As elementTree stuff?
#    requestStruct = parseRequest(requestString, logger)
    requestStruct = None

    # If this is not a real stitching thing, just let Omni handle this.
    if not mustCallSCS(logger, requestStruct):
        return omni.call(args, options)
        # return omni.call

    confirmSliceOK(logger, args, options, config, slicename)

    # constructSCSArgs: slice_urn, rspec, options

    # callSCS (which method will make the call, or read result if fakeMode)

    # If error, return
    # save expanded RSpec
    # parseRequest
    # parseWorkflow
    # includes creating structs for AMs and hops
    # Includes checking each AM reachable and we know the URL/API version to use
    # Construct AM dependency struct and list of AMs with no unsatisfied dependencies
    # if notScript, print AM dependency tree
    # Do Main loop (below)
    # Do cleanup if any, construct return, return to stitcher.main (see above)
    return ""

def main(argv=None):

    print "This is stitcher.py"
    # FIXME: Print other header stuff?
    result = call(argv)
    # FIXME: If called from a script, then anything here?
#    if options.script:
        # return json
#        return result
#    else:
    prettyResult = json.dumps(result, ensure_ascii=True, indent=2)
    print prettyResult
    return

def call(argv=None):
# read config file
# extend Omni parser & parse args
# init logger (takes a log config file that might push to a file with custom name)
# set debug level possible
# call doStitching

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
                    default="http://oingo.dragon.maxgigapop.net:8081/geni/xmlrpc")
#  parser.add_option("--script",
#                    help="If supplied, a script is calling this",
#                    action="store_true", default=False)

  # Put our logs in a different file by default
  parser.set_defaults(logoutput='stitcher.log')

  # options is an optparse.Values object, and args is a list
  options, args = parser.parse_args(sys.argv[1:])

  # Set up the logger
  omni.configure_logging(options)
  logger = logging.getLogger("stitcher")

  # We use the omni config file
  config = omni.load_config(options, logger)

  logger.info("Using AM API version %d", options.api_version)

  if options.fakeModeDir:
      logger.info("Got Fake Mode Dir %s", options.fakeModeDir)
      if not os.path.isDir(options.fakeModeDir):
          logger.error("But that is not a directory!")
          # FIXME: how handle errors?
          raise

  if options.debug:
      logger.info(omni.getSystemInfo())

  return doStitching(logger, options, config, args)


if __name__ == "__main__":
  sys.exit(main())
