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
import logging
import omni

from omnilib.util import OmniError
from omnilib.util.files import readFile
import omnilib.stitch.scs as scs

class StitchingError(OmniError):
    '''Errors due to stitching problems'''
    pass

# The main stitching class. Holds all the state about our attempt at doing stitching.
class StitchingHandler(object):
    def __init__(self, opts, config, logger):
        # FIXME: Do I need / want a framework here? Should main get it?
#        self.framework = framework
        self.logger = logger
        config['logger'] = logger
        self.omni_config = config['omni']
        self.config = config
        # FIXME: Duplicate the options like am_api_accept does?
        self.opts = opts # command line options as parsed
#        self.GetVersionCache = None # The cache of GetVersion info in memory

    def doStitching(self, args):
        # Get request RSpec
        request = None
        command = None
        slicename = None
        if len(args) == 0:
            self._raise_omni_error("Expected 3 args: <command = createsliver or allocate> <slice name> <rspec file path/url>")
        elif len(args) == 1:
            command = args[0]
        elif len(args) == 2:
            command = args[0]
            slicename = args[1]
        else:
            command = args[0]
            slicename = args[1]
            request = args[2]
            if len(args) > 3:
                self.logger.warn("Arguments %s ignored", args[3:])
        self.logger.info("Command=%s, slice=%s, rspec=%s", command, slicename, request)

        # Read in the rspec as a string
        # FIXME
        requestString = ""

        if request:
            try:
                # read the rspec into a string, and add it to the rspecs dict
                requestString = readFile(request)
            except Exception, exc:
                msg = 'Unable to read rspec file %s: %s' % (request, str(exc))
                raise OmniError(msg)

            #    # Test if the rspec is really json containing an RSpec, and pull out the right thing
            #    requestString = amhandler.self._maybeGetRSpecFromStruct(requestString)

            # confirmGoodRequest
            # -- FIXME: this should be a function in rspec_util: is a request (schema, type), is parsable xml, passes rspeclint?
            
            # parseRequest
            # -- FIXME: As elementTree stuff?
            #    requestStruct = parseRequest(requestString, logger)
        requestStruct = True
            
        # If this is not a real stitching thing, just let Omni handle this.
        if not self.mustCallSCS(requestStruct):
            return omni.call(args, self.opts)
        # return omni.call

        sliceurn = self.confirmSliceOK(slicename)
    
        scsService = scs.Service(self.opts.scsURL)
        options = {} # No options for now.
        try:
            scsResponse = scsService.ComputePath(sliceurn, requestString,
                                                 options)
        except Exception as e:
            self.logger.error("Error from slice cmoputation service:", e)
            # What to return to signal error?
            return

        self.logger.info("SCS successfully returned.");
        scsResponse.dump_workflow_data()

        # If error, return
        # save expanded RSpec
        expandedRSpec = scsResponse.rspec()
        #print "%r" % (expandedRSpec)
        # parseRequest
        # parseWorkflow
        workflow = scsResponse.workflow_data()
        #print "%r" % (workflow)
          # parse list of AMs, URNs, URLs - creating structs for AMs and hops
          # check each AM reachable, and we know the URL/API version to use
          # parse hop dependency tree, giving each hop an explicit hop#
          # Construct AM dependency tree
            # If hop1 depends on hop2 and hop1 AM != hop2 AM then hop1 AM depends on hop2 AM
              # Also hop1 AM depends on all AMs that hop2 AM depends on
            # Do that for all paths, for all hops

        # Mark on each hop which hop# it imports VLANs from, if any. For each hop
          # set min_distance = MAX_INTEGER
          # set import_vlans_from_hop#=None
          # if import_vlans=0, done
          # for each hop it depends on:
            # if on same domain, skip
            # If this diff-domain hop has # whose distance from orig hop is less than previous saved #, then set min_distance and import_vlans_from_hop#
          # If this hop has 0 dependencies but there are other hops at this AM in same path and AM does not do translation, then
            # set this hop import_vlans_from_hop# to the value from the other hop if it has a value

        # Check for AM dependency loops
        # Check SCS output consistency in a subroutine:
          # In each path: An AM with 1 hop must either _have_ dependencies or _be_ a dependency
          # All AMs must be listed in workflow data at least once per path they are in

        # Construct list of AMs with no unsatisfied dependencies
        # if notScript, print AM dependency tree
        # Do Main loop (below)
          # Are all AMs marked reserved/done? Exit main loop
          # Any AMs marked should-delete? Do Delete 1 AM
          # Any AMs have all dependencies satisfied? For each, do Reserve 1 AM
        # Do cleanup if any, construct return, return to stitcher.main (see above)
          # Construct a unified manifest
          # include AMs, URLs, API versions
          # use code/value/output struct
          # If error and have an expanded rquest from SCS, include that in output.
          #   Or if particular AM had errors, ID the AMe and errors
        return ""

    def mainStichingLoop(self):
        # FIXME: Need to put this in an object where I can get to a bunch of data objects?

        # Check if done? (see elsewhere)
        # Check threads exited
        # Check for AMs with delete pending
          # Construct omni args
          # Mark delete in process
          # omni.newthread_call
        # Check for threads exited
        # Check for AMs with redo pending
          # FIXME: Is this a thing? Or is this same as reserve?
        # Construct omni args
        # Mark redo in process
        # omni.newthread_call
        # Check for threads exited
        # Check for AMs to reserve, no remaining dependencies
          # Construct omni args
          # Mark reserve in process
          # Omni.newthread_call
        # Any ops in process?
          # Since when op finishes we go to top of loop, and loop spawns things, then if not we must be done
            # Confirm no deletes pending, redoes, or AMs not reserved
            # Go to end state section
        pass

    def mustCallSCS(self, request):
        # >=1 link in main body with >= 2 diff component_manager names and no shared_vlan extension
        if request:
            return True
        else:
            return False

    def confirmSliceOK(self, slicename):
        # FIXME: I need to get the framework and use it to do getslicecred, etc.
        fw = omni.load_framework(self.config, self.opts)
        
        # Get slice URN from name
        sliceurn = fw.slice_name_to_urn(slicename)
        # return error on error
        # Get slice cred
        # FIXME: Maybe use handler_utils._get_slice_cred
        #    slice_cred = fw.get_slice_cred(sliceurn)
        # return error on error
        # Ensure slice not expired
        # handler_utils._print_slice_expiration(sliceurn, slicecred)
        # amhandler._has_slice_expired(slice_cred) (which uses credutils.get_cred_exp)
        # return error on error

        # Maybe if the slice doesn't exist, create it?
        # omniargs = ["createslice", slicename]
        # try:
        #     (slicename, message) = omni.call(omniargs, self.opts)
        # except:
        #     pass

        
        # return the slice urn
        return sliceurn

    def _raise_omni_error( self, msg, err=OmniError, triple=None ):
        msg2 = msg
        if triple is not None:
            msg2 += " "
            msg2 += str(triple)
        self.logger.error( msg2 )
        if triple is None:
            raise err, msg
        else: 
            raise err, (msg, triple)

