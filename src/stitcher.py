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

import json
import logging
import os
import sys

import omni
from omnilib.util import OmniError
from omnilib.stitchhandler import StitchingError, StitchingHandler
import optparse 

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
                      default="http://oingo.dragon.maxgigapop.net:8081/geni/xmlrpc")
    #  parser.add_option("--script",
    #                    help="If supplied, a script is calling this",
    #                    action="store_true", default=False)
    
    # Put our logs in a different file by default
    parser.set_defaults(logoutput='stitcher.log')
    
    # options is an optparse.Values object, and args is a list
    options, args = parser.parse_args(argv)

    # Set up the logger
    omni.configure_logging(options)
    logger = logging.getLogger("stitcher")

    # We use the omni config file
    config = omni.load_config(options, logger)

    logger.info("Using AM API version %d", options.api_version)

    if options.fakeModeDir:
        logger.info("Got Fake Mode Dir %s", options.fakeModeDir)
        if not os.path.isdir(options.fakeModeDir):
            logger.error("But that is not a directory!")
            raise StitchingError("Fake Mod path not a directory: %s" % options.fakeModeDir)
        else:
            logger.info("Running in fake mode")

    if options.debug:
        logger.info(omni.getSystemInfo())
            
    handler = StitchingHandler(options, config, logger)    
    return handler.doStitching(args)

# Goal of main is to call the 'call' method and print the result
def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    print "This is stitcher.py"
    # FIXME: Print other header stuff?
    try:
        result = call(argv)
    # FIXME: If called from a script, then anything here?
#    if options.script:
        # return json
#        return result
#    else:
        prettyResult = json.dumps(result, ensure_ascii=True, indent=2)
        print prettyResult
    except OmniError, oe:
        sys.exit(oe)

if __name__ == "__main__":
  sys.exit(main())
