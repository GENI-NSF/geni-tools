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
import datetime
import logging

import omni
from omnilib.util import OmniError, naiveUTC
import omnilib.util.handler_utils as handler_utils
from omnilib.util.files import readFile
import omnilib.util.credparsing as credutils

import omnilib.stitch.scs as scs
import omnilib.stitch.RSpecParser
from omnilib.stitch.workflow import WorkflowParser
import omnilib.stitch as stitch
from omnilib.stitch.utils import StitchingError

from geni.util.rspec_util import is_rspec_string, is_rspec_of_type, rspeclint_exists, validate_rspec

# The main stitching class. Holds all the state about our attempt at doing stitching.
class StitchingHandler(object):
    '''Workhorse class to do stitching'''

    def __init__(self, opts, config, logger):
        self.logger = logger
        config['logger'] = logger
        self.omni_config = config['omni']
        self.config = config
        self.opts = opts # command line options as parsed
        self.framework = omni.load_framework(self.config, self.opts)

    def doStitching(self, args):
        # Get request RSpec
        request = None
        command = None
        slicename = None
        if len(args) > 0:
            command = args[0]
        if not command or command.strip().lower() not in ('createsliver', 'allocate'):
            # Stitcher only handles createsliver or allocate
            if self.opts.fakeModeDir:
                self.logger.info("In fake mode. Otherwise would call Omni with args %r", args)
                return
            else:
                self.logger.info("Passing call to Omni")
                return omni.call(args, self.opts)

        if len(args) > 1:
            slicename = args[1]
        if len(args) > 2:
            request = args[2]

        if len(args) > 3:
            self.logger.warn("Arguments %s ignored", args[3:])
        self.logger.info("Command=%s, slice=%s, rspec=%s", command, slicename, request)

        # Parse the RSpec
        requestString = ""
        self.rspecParser = omnilib.stitch.RSpecParser.RSpecParser(self.logger)
        self.parsedUserRequest = None
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
            self.confirmGoodRequest(requestString)
            self.logger.debug("Valid GENI v3 request RSpec")
            
            # parseRequest
            self.parsedUserRequest = self.rspecParser.parse(requestString)
            
        # If this is not a real stitching thing, just let Omni handle this.
        if not self.mustCallSCS(self.parsedUserRequest):
            # Warning: If this is createsliver and you specified multiple aggregates,
            # then omni only contacts 1 aggregate. That is likely not what you wanted.
            return omni.call(args, self.opts)

        # Remove any -a arguments from the opts so that when we later call omni
        # the right thing happens
        self.opts.aggregate = []

        # Ensure the slice is valid before all those Omni calls use it
        sliceurn = self.confirmSliceOK(slicename)
    
        self.scsService = scs.Service(self.opts.scsURL)

        scsResponse = self.callSCS(sliceurn, requestString)
#        scsResponse = self.callSCS(sliceurn, self.parsedUserRequest)

        # Parse SCS Response, constructing objects and dependencies, validating return
        parsed_rspec, workflow_parser = self.parseSCSResponse(scsResponse)

        # FIXME: if notScript, print AM dependency tree?

        # Do Main loop (below)
        self.mainStitchingLoop(workflow_parser.aggs, parsed_rspec)
          # Are all AMs marked reserved/done? Exit main loop
          # Any AMs marked should-delete? Do Delete 1 AM
          # Any AMs have all dependencies satisfied? For each, do Reserve 1 AM

        # FIXME: Do cleanup if any, construct return, return to stitcher.main (see above)
          # Construct a unified manifest
          # include AMs, URLs, API versions
          # use code/value/output struct
          # If error and have an expanded rquest from SCS, include that in output.
          #   Or if particular AM had errors, ID the AMe and errors

        return ""

    def mainStitchingLoop(self, aggs, rspec):

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
        launcher = stitch.Launcher(self.opts, aggs)
        launcher.launch(rspec)
        pass

    def confirmGoodRequest(self, requestString):
        # Confirm the string is a request rspec, valid
        if requestString is None or str(requestString).strip() == '':
            raise OmniError("Empty request rspec")
        if not is_rspec_string(requestString, self.logger):
            raise OmniError("Request RSpec file did not contain an RSpec")
        if not is_rspec_of_type(requestString):
            raise OmniError("Request RSpec file did not contain a request RSpec (wrong type or schema)")
        try:
            rspeclint_exists()
        except:
            self.logger.debug("No rspeclint found")
            return
        if not validate_rspec(requestString):
            raise OmniError("Request RSpec does not validate against its schemas")

    def confirmSliceOK(self, slicename):
        # Ensure the given slice name corresponds to a current valid slice

        # Get slice URN from name
        try:
            sliceurn = self.framework.slice_name_to_urn(slicename)
        except Exception, e:
            self.logger.error("Could not determine slice URN from name: %s", e)
            raise StitchingError(e)

        if self.opts.fakeModeDir:
            self.logger.info("Fake mode: not checking slice credential")
            return sliceurn

        # Get slice cred
        (slicecred, message) = handler_utils._get_slice_cred(self, sliceurn)
        if not slicecred:
            # FIXME: Maybe if the slice doesn't exist, create it?
            # omniargs = ["createslice", slicename]
            # try:
            #     (slicename, message) = omni.call(omniargs, self.opts)
            # except:
            #     pass
            raise StitchingError("Could not get a slice credential for slice %s: %s" % (sliceurn, message))

        # Ensure slice not expired
        sliceexp = credutils.get_cred_exp(self.logger, slicecred)
        sliceexp = naiveUTC(sliceexp)
        now = datetime.datetime.utcnow()
        if sliceexp <= now:
            # FIXME: Maybe if the slice doesn't exist, create it?
            # omniargs = ["createslice", slicename]
            # try:
            #     (slicename, message) = omni.call(omniargs, self.opts)
            # except:
            #     pass
            raise StitchingError("Slice %s expired at %s" % (sliceurn, sliceexp))
        
        # return the slice urn
        return sliceurn

    def mustCallSCS(self, requestRSpecObject):
        # Does this request actually require stitching?
        # Check: >=1 link in main body with >= 2 diff component_manager names and no shared_vlan extension
        if requestRSpecObject:
            for link in requestRSpecObject.links:
                # FIXME: hasSharedVlan is not correctly set yet
                if len(link.aggregates) > 1 and not link.hasSharedVlan:
                    return True
        return False

#    def callSCS(self, sliceurn, requestRSpecObject):
    def callSCS(self, sliceurn, requestString):
        try:
 #           request, scsOptions = self.constructSCSArgs(requestRSpecObject)
            request, scsOptions = self.constructSCSArgs(requestString)
            scsResponse = self.scsService.ComputePath(sliceurn, request, scsOptions)
        except Exception as e:
            self.logger.error("Error from slice computation service: %s", e)
            raise StitchingError("SCS gave error: %s" % e)

        self.logger.info("SCS successfully returned.");

        if self.opts.debug:
            self.logger.debug("Writing SCS result JSON to scs-result.json")
            with open ("scs-result.json", 'w') as file:
                file.write(str(self.scsService.result))

        return scsResponse

    def constructSCSArgs(self, request, hopObjectsToExclude=None):
        # Eventually take vlans to exclude as well
        # return requestString and options

        options = {} # No options for now.
        # options is a struct
        # To exclude a hop, add a geni_routing_profile struct
        # This in turn should have a struct per path whose name is the path name
        # Each shuld have a hop_exclusion_list array, containing the names of hops
#        exclude = "urn:publicid:IDN+utah.geniracks.net+interface+procurve2:1.19"
#        path = "link-utah-utah-ig"

#        path = "link-pg-utah1-ig-gpo1"
#        exclude = "urn:publicid:IDN+ion.internet2.edu+interface+rtr.atla:ge-7/1/6:protogeni"
#        excludes = []
#        excludes.append(exclude)
#        exclude = "urn:publicid:IDN+ion.internet2.edu+interface+rtr.hous:ge-9/1/4:protogeni"
#        excludes.append(exclude)
#        exclude = "urn:publicid:IDN+ion.internet2.edu+interface+rtr.losa:ge-7/1/3:protogeni"
#        excludes.append(exclude)
#        exclude = "urn:publicid:IDN+ion.internet2.edu+interface+rtr.salt:ge-7/1/2:*"
##        excludes.append(exclude)
#        exclude = "urn:publicid:IDN+ion.internet2.edu+interface+rtr.wash:ge-7/1/3:protogeni"
#        excludes.append(exclude)
#        profile = {}
#        pathStruct = {}
#        pathStruct["hop_exclusion_list"]=excludes
#        profile[path] = pathStruct
#        options["geni_routing_profile"]=profile

        if hopObjectsToExclude:
            profile = {}
            for hop in hopObjectsToExclude:
                # get path
                path = hop._path.id
                if profile.has_key(path):
                    pathStruct = profile[path]
                else:
                    pathStruct = {}

                # get hop URN
                urn = hop.urn
                if pathStruct.has_key("hop_exclusion_list"):
                    excludes = pathStruct["hop_exclusion_list"]
                else:
                    excludes = []
                excludes.append(urn)
                pathStruct["hop_exclusion_list"] = excludes
                profile[path] = pathStruct
            options["geni_routing_profile"] = profile

#        return request.toXML(), options
        return request, options
        
    def parseSCSResponse(self, scsResponse):
        # save expanded RSpec
        expandedRSpec = scsResponse.rspec()
        if self.opts.debug:
            self.logger.debug("Writing SCS expanded RSpec to expanded.xml")
            with open("expanded.xml", 'w') as file:
                file.write(expandedRSpec)

       # parseRequest
        parsed_rspec = self.rspecParser.parse(expandedRSpec)
        self.logger.debug("Parsed SCS expanded RSpec of type %r",
                          type(parsed_rspec))
        #with open('gen-rspec.xml', 'w') as f:
        #    f.write(parsed_rspec.dom.toxml())

        # parseWorkflow
        workflow = scsResponse.workflow_data()
        if self.opts.debug:
            import pprint
            pp = pprint.PrettyPrinter(indent=2)
            pp.pprint(workflow)

        workflow_parser = WorkflowParser()
        workflow_parser.parse(workflow, parsed_rspec)
        if self.opts.debug:
            self.dump_objects(parsed_rspec, workflow_parser.aggs)

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
        return parsed_rspec, workflow_parser

    def dump_objects(self, rspec, aggs):
        '''Print out the hops, aggregates, dependencies'''
        stitching = rspec.stitching
        self.logger.debug( "\n===== Hops =====")
        for path in stitching.paths:
            self.logger.debug( "Path %s" % (path.id))
            for hop in path.hops:
                self.logger.debug( "  Hop %s" % (hop))
                # FIXME: don't use the private variable
                self.logger.debug( "    VLAN Suggested %s" % (hop._hop_link.vlan_suggested))
                self.logger.debug( "    VLAN Range %s" % (hop._hop_link.vlan_range))
                deps = hop.dependsOn
                if deps:
                    self.logger.debug( "    Dependencies:")
                    for h in deps:
                        self.logger.debug( "      Hop %s" % (h))


        self.logger.debug( "\n===== Aggregates =====")
        for agg in aggs:
            self.logger.debug( "\nAggregate %s" % (agg))
            for h in agg.hops:
                self.logger.debug( "  Hop %s" % (h))
            for ad in agg.dependsOn:
                self.logger.debug( "  Depends on %s" % (ad))

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

