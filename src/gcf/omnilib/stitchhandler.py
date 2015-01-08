#!/usr/bin/env python

from __future__ import absolute_import

#----------------------------------------------------------------------
# Copyright (c) 2013-2015 Raytheon BBN Technologies
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
'''Main stitching workhorse. Handles calling the stitching service, orchestrating
parsing RSpecs and creating objects. See doStitching().'''
import copy
import datetime
import json
import logging
import os
import string
import sys
import time

from .. import oscript as omni
from .util import OmniError, naiveUTC
from .util import credparsing as credutils
from .util.files import readFile
from .util import handler_utils
from .util.json_encoding import DateTimeAwareJSONEncoder

from . import stitch
from .stitch import defs
from .stitch.ManifestRSpecCombiner import combineManifestRSpecs
from .stitch.objects import Aggregate, Link, Node, LinkProperty
from .stitch.RSpecParser import RSpecParser
from .stitch import scs
from .stitch.workflow import WorkflowParser
from .stitch.utils import StitchingError, StitchingCircuitFailedError, stripBlankLines, isRSpecStitchingSchemaV2, prependFilePrefix
from .stitch.VLANRange import *

from ..geni.util import rspec_schema
from ..geni.util.rspec_util import is_rspec_string, is_rspec_of_type, rspeclint_exists, validate_rspec

from ..sfa.trust import gid
from ..sfa.util.xrn import urn_to_hrn, get_leaf

DCN_AM_TYPE = 'dcn' # geni_am_type value from AMs that use the DCN codebase
ORCA_AM_TYPE = 'orca' # geni_am_type value from AMs that use the Orca codebase
PG_AM_TYPE = 'protogeni' # geni_am_type / am_type from ProtoGENI based AMs
GRAM_AM_TYPE = 'gram' # geni_am_type value from AMs that use the GRAM codebase

# Max # of times to call the stitching service
MAX_SCS_CALLS = 5

# File in which we save the slice cred so omni calls don't have to keep re-fetching it
# Valid substitutions: %username, %slicename, %slicehrn
SLICECRED_FILENAME = 'slice-%slicehrn-for-%username-cred.xml'

def urn_to_clean_hrn( urn ):
    hrn, type = urn_to_hrn( urn )
    hrn = handler_utils.remove_bad_characters( hrn )
    return hrn, type

# The main stitching class. Holds all the state about our attempt at doing stitching.
class StitchingHandler(object):
    '''Workhorse class to do stitching. See doStitching().'''

    def __init__(self, opts, config, logger):
        self.logger = logger
        config['logger'] = logger
        self.omni_config = config['omni']
        self.config = config
        self.parsedSCSRSpec = None
        self.lastException = None
        self.ams_to_process = []
        self.opts = opts # command line options as parsed
        self.slicecred = None # Cached slice credential to avoid re-fetching
        self.savedSliceCred = None # path to file with slice cred if any

        # Get the framework
        if not self.opts.debug:
            # First, suppress all but WARN+ messages on console
            lvl = logging.INFO
            handlers = logger.handlers
            if len(handlers) == 0:
                handlers = logging.getLogger().handlers
            for handler in handlers:
                if isinstance(handler, logging.StreamHandler):
                    lvl = handler.level
                    handler.setLevel(logging.WARN)
                    break
        self.framework = omni.load_framework(self.config, self.opts)
        if not self.opts.debug:
            handlers = logger.handlers
            if len(handlers) == 0:
                handlers = logging.getLogger().handlers
            for handler in handlers:
                if isinstance(handler, logging.StreamHandler):
                    handler.setLevel(lvl)
                    break

        # FIXME: How many times is right to go back to the SCS
        self.maxSCSCalls = MAX_SCS_CALLS

        # Remember we got the extra info for this AM
        self.amURNsAddedInfo = []

        if self.opts.timeout == 0:
            self.config['timeoutTime'] = datetime.datetime.max
            self.logger.debug("Requested no timeout for stitcher.")
        else:
            self.config['timeoutTime'] = datetime.datetime.utcnow() + datetime.timedelta(minutes=self.opts.timeout)
            self.logger.debug("Stitcher run will timeout at %s UTC.", self.config['timeoutTime'])

    def doStitching(self, args):
        '''Main stitching function.'''
        # Get request RSpec
        request = None
        command = None
        self.slicename = None
        if len(args) > 0:
            command = args[0]
        if not command or command.strip().lower() not in ('createsliver', 'allocate'):
            # Stitcher only handles createsliver or allocate
            if self.opts.fakeModeDir:
                msg = "In fake mode. Otherwise would call Omni with args %r" % args
                self.logger.info(msg)
                return (msg, None)
            else:
                self.logger.debug("Passing call to Omni")
                # Add -a options from the saved file, if none already supplied
                self.addAggregateOptions(args)

                # Try to force a call that falls through to omni to log at info level,
                # or whatever level the main stitcher is using on the console
                ologger = logging.getLogger("omni")
                myLevel = logging.INFO
                handlers = self.logger.handlers
                if len(handlers) == 0:
                    handlers = logging.getLogger().handlers
                for handler in handlers:
                    if isinstance(handler, logging.StreamHandler):
                        myLevel = handler.level
                        break
                for handler in ologger.handlers:
                    if isinstance(handler, logging.StreamHandler):
                        handler.setLevel(myLevel)
                        break

                return omni.call(args, self.opts)

        if len(args) > 1:
            self.slicename = args[1]
        if len(args) > 2:
            request = args[2]

        if len(args) > 3:
            self.logger.warn("Arguments %s ignored", args[3:])
        #self.logger.debug("Command=%s, slice=%s, rspec=%s", command, self.slicename, request)

        # Parse the RSpec
        requestString = ""
        self.rspecParser = RSpecParser(self.logger)
        self.parsedUserRequest = None
        if request:
            try:
                # read the rspec into a string, and add it to the rspecs dict
                requestString = handler_utils._derefRSpecNick(self, request)
            except Exception, exc:
                msg = "Unable to read rspec file '%s': %s" % (request, str(exc))
                if self.opts.devmode:
                    self.logger.warn(msg)
                else:
                    raise OmniError(msg)

            #    # Test if the rspec is really json containing an RSpec, and pull out the right thing
            #    requestString = amhandler.self._maybeGetRSpecFromStruct(requestString)

            # confirmGoodRequest
            self.confirmGoodRSpec(requestString)
            self.logger.debug("Valid GENI v3 request RSpec")
            
            # parseRequest
            self.parsedUserRequest = self.rspecParser.parse(requestString)
        else:
            raise OmniError("No request RSpec found, or slice name missing!")

        self.isStitching = self.mustCallSCS(self.parsedUserRequest)
        self.isGRE = self.hasGRELink(self.parsedUserRequest)
        self.isMultiAM = False
        # If any node is unbound, then all AMs will try to allocate it. So bail
        unboundNode = self.getUnboundNode()

        self.isBound = (unboundNode is None)
        if self.isBound:
            self.logger.debug("Request appears to be fully bound")
        if (self.isGRE or self.isStitching) and not self.isMultiAM:
            self.logger.debug("Nodes seemed to list <2 AMs, but rspec appears GRE or stitching, so it is multi AM")
            self.isMultiAM = True

        # FIXME:
        # If it is bound, make sure all the implied AMs are known (have a URL)

        # FIXME:
        # If any node is unbound: Check that there is exactly 1 -a AM that is not one of the AMs a node is bound to, and then 
        # edit the request to bind the nodes to that AM.

        # If this is not a bound multi AM RSpec, just let Omni handle this.
        if not self.isBound or not self.isMultiAM:
            self.logger.info("Not a bound multi-aggregate request - let Omni handle this.")
            if unboundNode is not None:
                self.logger.info("Node '%s' is unbound in request - all nodes must be bound for stitcher, as all aggregates get the same request RSpec" % unboundNode)

            if self.isBound:
                if self.opts.aggregate is None or len(self.opts.aggregate) == 0:
                    # A bound non multi AM RSpec but no AM specified. Fill in the -a appropriately
                    if self.parsedUserRequest.amURNs and len(self.parsedUserRequest.amURNs) > 0:
                        amURN = self.parsedUserRequest.amURNs.pop()
                        (nick, url) = handler_utils._lookupAggNickURLFromURNInNicknames(self.logger, self.config, amURN)
                        if url and url.strip() != '':
                            self.logger.debug("Setting -a argument for Omni: Found RSpec AM %s in omni_config AM nicknames: %s", amURN, nick)
                            self.opts.aggregate = [nick]
                        else:
                            self.logger.debug("Could not find AM from RSpec for URN %s - Omni will have no -a argument", amURN)
                    #else:
                        # weird and really shouldn't happen
                elif len(self.opts.aggregate) == 1:
                    # If the AM specified is not what it is bound to, then what? complain? fix it? do it anyhow?
                    # else this is good
                    if self.parsedUserRequest.amURNs and len(self.parsedUserRequest.amURNs) > 0:
                        amURN = self.parsedUserRequest.amURNs.pop()
                        (nick, url) = handler_utils._lookupAggNickURLFromURNInNicknames(self.logger, self.config, amURN)
                        amNick = None
                        amURL = None
                        if url and url.strip() != '':
                            self.logger.debug("Found RSpec AM %s in omni_config AM nicknames: %s", amURN, nick)
                            amNick = nick
                            amURL = url

                        if not self.opts.debug:
                            # Suppress most log messages on the console for doing the nickname lookup
                            lvl = logging.INFO
                            handlers = self.logger.handlers
                            if len(handlers) == 0:
                                handlers = logging.getLogger().handlers
                            for handler in handlers:
                                if isinstance(handler, logging.StreamHandler):
                                    lvl = handler.level
                                    handler.setLevel(logging.WARN)
                                    break

                        url1,urn1 = handler_utils._derefAggNick(self, self.opts.aggregate[0])

                        if not self.opts.debug:
                            handlers = self.logger.handlers
                            if len(handlers) == 0:
                                handlers = logging.getLogger().handlers
                            for handler in handlers:
                                if isinstance(handler, logging.StreamHandler):
                                    handler.setLevel(lvl)
                                    break

                        if (amNick and amNick == self.opts.aggregate[0]) or (amURL and amURL == url1) or (amURN == urn1):
                            self.logger.debug("Supplied -a matches the AM found in the RSpec: %s=%s", amURN, self.opts.aggregate[0])
                        elif amNick and url1:
                            # A valid comparison that didn't find anything
                            self.logger.warn("RSpec appears bound to a different AM than you are submitting it to. RSpec specifies AM %s (%s) but -a argument specifies %s (%s)! Continuing anyway....", amURN, amNick, self.opts.aggregate[0], url1)
                            # FIXME: Correct it? Bail?
                        # else:
                            # Didn't get all the values for a proper comparison
                    # else:
                        # No AMs parsed out of the RSpec. I don't think this should happen
                else:
                    # the RSpec appeared to be single AM but multiple AMs specified.
                    # Perhaps check if the bound AM is at least one of them?
                    # Complain? Bail? Fix it? Continue?
                    self.logger.debug("RSpec appeared bound to a single AM but multiple -a arguments specified?")

                    if self.parsedUserRequest.amURNs and len(self.parsedUserRequest.amURNs) > 0:
                        amURN = self.parsedUserRequest.amURNs.pop()
                        (nick, url) = handler_utils._lookupAggNickURLFromURNInNicknames(self.logger, self.config, amURN)
                        amNick = None
                        amURL = None
                        if url and url.strip() != '':
                            self.logger.debug("Found RSpec AM %s URL from omni_config AM nicknames: %s", amURN, nick)
                            amNick = nick
                            amURL = url
                        found = False
                        for dasha in self.opts.aggregate:
                            if not self.opts.debug:
                                # Suppress most log messages on the console for doing the nickname lookup
                                lvl = logging.INFO
                                handlers = self.logger.handlers
                                if len(handlers) == 0:
                                    handlers = logging.getLogger().handlers
                                for handler in handlers:
                                    if isinstance(handler, logging.StreamHandler):
                                        lvl = handler.level
                                        handler.setLevel(logging.WARN)
                                        break

                            url1,urn1 = handler_utils._derefAggNick(self, dasha)

                            if not self.opts.debug:
                                handlers = self.logger.handlers
                                if len(handlers) == 0:
                                    handlers = logging.getLogger().handlers
                                for handler in handlers:
                                    if isinstance(handler, logging.StreamHandler):
                                        handler.setLevel(lvl)
                                        break

                            if (amNick and amNick == dasha) or (amURL and amURL == url1) or (amURN == urn1):
                                self.logger.debug("1 of the supplied -a args matches the AM found in the RSpec: %s", amURN)
                                found = True
                                break
                        if not found:
                            self.logger.warn("RSpec appears bound to a different AM than the multiple AMs you are submitting it to. RSpec specifies AM %s (%s) but -a argument specifies %s! Continuing anyway....", amURN, amNick, self.opts.aggregate)
                        else:
                            self.logger.warn("RSpec appeared bound to a single AM (%s) but multiple -a arguments specified? %s", amURN, self.opts.aggregate)
                            self.logger.info("... continuing anyway")
                            # FIXME: Correct it? Bail?

            if self.opts.noReservation:
                self.logger.info("Not reserving resources")
                sys.exit()

            # Try to force a call that falls through to omni to log at info level,
            # or whatever level the main stitcher is using on the console
            ologger = logging.getLogger("omni")
            myLevel = logging.INFO
            handlers = self.logger.handlers
            if len(handlers) == 0:
                handlers = logging.getLogger().handlers
            for handler in handlers:
                if isinstance(handler, logging.StreamHandler):
                    myLevel = handler.level
                    break
            for handler in ologger.handlers:
                if isinstance(handler, logging.StreamHandler):
                    handler.setLevel(myLevel)
                    break

            # Warning: If this is createsliver and you specified multiple aggregates,
            # then omni only contacts 1 aggregate. That is likely not what you wanted.
            return omni.call(args, self.opts)

#        self.logger.debug("Edited request RSpec: %s", self.parsedUserRequest.getLinkEditedDom().toprettyxml())

        if self.opts.explicitRSpecVersion:
            self.logger.info("All manifest RSpecs will be in GENI v3 format")
            self.opts.explicitRSpecVersion = False
            self.opts.rspectype = ["GENI", '3']

        # FIXME: Confirm request is not asking for any loops
        self.confirmSafeRequest()

        # Remove any -a arguments from the opts so that when we later call omni
        # the right thing happens
        self.opts.aggregate = []

        # FIXME: Maybe use threading to parallelize confirmSliceOK and the 1st SCS call?

        # Get username for slicecred filename
        self.username = get_leaf(handler_utils._get_user_urn(self.logger, self.framework.config))
        if not self.username:
            raise OmniError("Failed to find your username to name your slice credential")

        # Ensure the slice is valid before all those Omni calls use it
        (sliceurn, sliceexp) = self.confirmSliceOK()

        # Here is where we used to add the expires attribute. No
        # longer necessary (or a good idea).

        if self.isStitching:
            if not "oingo.dragon.maxgigapop.net:8443" in self.opts.scsURL:
                self.logger.info("Using SCS at %s", self.opts.scsURL)
            self.scsService = scs.Service(self.opts.scsURL, key=self.framework.key, cert=self.framework.cert, timeout=self.opts.ssltimeout, verbose=self.opts.verbosessl)
        self.scsCalls = 0

        # Compare the list of AMs in the request with AMs known
        # to the SCS. Any that the SCS does not know means the request
        # cannot succeed if those are AMs in a stitched link
#        self.checkSCSAMs()

        # Call SCS and then do reservations at AMs, deleting or retrying SCS as needed
        lvl = None
        try:
            # Passing in the request as a DOM - after allowing edits as necessary. OK?
            lastAM = self.mainStitchingLoop(sliceurn, self.parsedUserRequest.getLinkEditedDom())

            # Construct a unified manifest
            # include AMs, URLs, API versions
            # Avoid EG manifests - they are incomplete
            # Avoid DCN manifests - they do funny things with namespaces (ticket #549)
            # GRAM AMs seems to also miss nodes. Avoid if possible.
            if lastAM.isEG or lastAM.dcn or lastAM.isGRAM:
                self.logger.debug("Last AM was an EG or DCN or GRAM AM. Find another for the template.")
                i = 1
                while (lastAM.isEG or lastAM.dcn or lastAM.isGRAM) and i <= len(self.ams_to_process):
                    # This has lost some hops and messed up hop IDs. Don't use it as the template
                    # I'd like to find another AM we did recently
                    lastAM = self.ams_to_process[-i]
                    i = i + 1
                if lastAM.isEG or lastAM.dcn or lastAM.isGRAM:
                    self.logger.debug("Still had an EG or DCN or GRAM template AM - use the raw SCS request")
                    lastAM = None
            combinedManifest = self.combineManifests(self.ams_to_process, lastAM)

            # FIXME: Handle errors. Maybe make return use code/value/output struct
            # If error and have an expanded request from SCS, include that in output.
            #   Or if particular AM had errors, ID the AMs and errors

            # FIXME: This prepends a header on an RSpec that might already have a header
            # -- maybe replace any existing header

            # FIXME: We force -o here and keep it from logging the
            # RSpec. Do we need an option to not write the RSpec to a file?

            ot = self.opts.output
            if not self.opts.tostdout:
                self.opts.output = True

            if not self.opts.debug:
                # Suppress all but WARN on console here
                lvl = self.logger.getEffectiveLevel()
                handlers = self.logger.handlers
                if len(handlers) == 0:
                    handlers = logging.getLogger().handlers
                for handler in handlers:
                    if isinstance(handler, logging.StreamHandler):
                        lvl = handler.level
                        handler.setLevel(logging.WARN)
                        break

            retVal, filename = handler_utils._writeRSpec(self.opts, self.logger, combinedManifest, self.slicename, 'multiam-combined', '', None)
            if not self.opts.debug:
                handlers = self.logger.handlers
                if len(handlers) == 0:
                    handlers = logging.getLogger().handlers
                for handler in handlers:
                    if isinstance(handler, logging.StreamHandler):
                        handler.setLevel(lvl)
                        break
            self.opts.output = ot

            # Print something about sliver expiration times

            # FIXME: 15min? 30min?
            # FIXME: Old code printed per agg exp at debug level

            sortedAggs = Aggregate.sortAggsByExpirations(15) # 15min apart counts as same
            firstTime = None
            firstCount = 0
            firstLabel = ""
            secondTime = None
            secondCount = 0
            secondLabel = ""
            noPrint = False
            msgAdd = ''
            msg = None
            if len(sortedAggs) == 0:
                msg = "No aggregates"
                self.logger.debug("Got no aggregates?")
                noPrint = True
            else:
                self.logger.debug("AMs expire at %d time(s).", len(sortedAggs))
                firstSlotTimes = sortedAggs[0][0].sliverExpirations
                skipFirst = False
                if firstSlotTimes is None or len(firstSlotTimes) == 0:
                    skipFirst = True
                    if len(sortedAggs) == 1:
                        msg = "Aggregates did not report sliver expiration"
                        self.logger.debug("Only expiration timeslot has an agg with no expirations")
                        noPrint = True
                    else:
                        msgAdd = "Resource expiration unknown at %d aggregate(s)" % len(sortedAggs[0])
                        self.logger.debug("First slot had no times, but there are other slots")
                ind = -1
                for slot in sortedAggs:
                    ind += 1
                    if skipFirst and ind == 0:
                        continue
                    if firstTime is None:
                        firstTime = slot[0].sliverExpirations[0]
                        firstCount = len(slot)
                        firstLabel = str(slot[0])
                        if len(sortedAggs) > 1:
                            self.logger.debug("First expiration is at %s UTC at %s, at %d total AM(s).", firstTime.isoformat(), firstLabel, firstCount)
                        else:
                            self.logger.debug("Resource expiration is at %s UTC, at %d total AM(s).", firstTime.isoformat(), firstCount)
                        if firstCount == 1:
                            continue
                        elif firstCount == 2:
                            firstLabel += " and " + str(slot[1])
                        else:
                            firstLabel += " and %d other AM(s)" % (firstCount - 1)
                        continue
                    elif secondTime is None:
                        secondTime = slot[0].sliverExpirations[0]
                        secondCount = len(slot)
                        secondLabel = str(slot[0])
                        self.logger.debug("Second expiration at %s UTC at %s, at %d total AM(s)", secondTime.isoformat(), secondLabel, secondCount)
                        if secondCount == 1:
                            break
                        elif secondCount == 2:
                            secondLabel += " and " + str(slot[1])
                        else:
                            secondLabel += " and %d other AM(s)" % (secondCount - 1)
                        break
                # Done looping over agg exp times in sortedAggs
            # Done handling sortedAggs
            if not noPrint:
                if len(sortedAggs) == 1:
                    msg = "Your resources expire at %s (UTC). %s" % (firstTime.isoformat(), msgAdd)
                else:
                    msg = "Your resources expire at %d different times. The first resources expire at %s (UTC) at %s. The second expiration time is %s (UTC) at %s. %s" % (len(sortedAggs), firstTime.isoformat(), firstLabel, secondTime.isoformat(), secondLabel, msgAdd)

            if msg:
                self.logger.info(msg)
                retVal += msg + "\n"

            if filename:
                msg = "Saved combined reservation RSpec at %d AMs to file '%s'" % (len(self.ams_to_process), os.path.abspath(filename))
                self.logger.info(msg)
                retVal += msg

        except KeyboardInterrupt:
            if lvl:
                self.logger.setLevel(lvl)
            msg = 'Stitching interrupted!'
            if self.lastException:
                msg += ' ' + str(self.lastException)
            self.logger.error(msg)


            if self.ams_to_process is not None:
                class DumbLauncher():
                    def __init__(self, agglist):
                        self.aggs = agglist

                result = self.deleteAllReservations(DumbLauncher(self.ams_to_process))

                for am in self.ams_to_process:
                    if am.manifestDom:
                        self.logger.warn("You have a reservation at %s", am)
            sys.exit(-1)
        except StitchingError, se:
            if lvl:
                self.logger.setLevel(lvl)
            # FIXME: Return anything different for stitching error?
            # Do we want to return a geni triple struct?
            if self.lastException:
                msg = "Stitching Failed. %s" % str(se)
                if str(self.lastException) not in str(se):
                    msg += ". Root cause error: %s" % str(self.lastException)
                self.logger.error(msg)
                newError = StitchingError(msg)
                se = newError
            if "Requested no reservation" in str(se):
                print str(se)
                self.logger.debug(se)
                sys.exit(0)
            else:
                raise se
        finally:
            # Save a file with the aggregates used in this slice
            self.saveAggregateList(sliceurn)

            # Clean up temporary files
            self.cleanup()

            self.dump_objects(self.parsedSCSRSpec, self.ams_to_process)

        # Construct return
        amcnt = len(self.ams_to_process)
        scs_added_amcnt = 0
        pathcnt = 0
        grecnt = 0
        if self.parsedSCSRSpec and self.parsedSCSRSpec.stitching:
            pathcnt = len(self.parsedSCSRSpec.stitching.paths)
        if self.parsedSCSRSpec and self.parsedSCSRSpec.links:
            for link in self.parsedSCSRSpec.links:
                if link.typeName in (link.GRE_LINK_TYPE, link.EGRE_LINK_TYPE):
                    grecnt += 1
        for am in self.ams_to_process:
            if not am.userRequested:
                scs_added_amcnt = scs_added_amcnt + 1
        greStr = ""
        if grecnt > 0:
            greStr = ", creating %d GRE link(s)" % grecnt
        stitchStr = ""
        if pathcnt > 0:
            stitchStr = ", creating %d stitched link(s)" % pathcnt
        if scs_added_amcnt > 0:
            retMsg = "Success: Reserved resources in slice %s at %d Aggregates (including %d intermediate aggregate(s) not in the original request)%s%s." % (self.slicename, amcnt, scs_added_amcnt, greStr, stitchStr)
        else:
            retMsg = "Success: Reserved resources in slice %s at %d Aggregates%s%s." % (self.slicename, amcnt, greStr, stitchStr)
 
        # FIXME: What do we want to return?
# Make it something like createsliver / allocate, with the code/value/output triple plus a string
# On success
#  Request from SCS that worked? Merged request as I modified?
#  Merged manifest
#  List of AMs, the URLs, and their API versions?
#  Some indication of the slivers and their status and expiration at each AM?
#    In particular, which AMs need a provision and poa geni_start
#  ?? Stuff parsed from manifest?? EG some representation of each path with node list/count at each AM and VLAN tag for each link?, maybe list of the AMs added by the SCS?
#On error
#  Error code / message (standard GENI triple)
#  If the error was after SCS, include the expanded request from the SCS
#  If particular AMs had errors, ID those AMs and the errors
        self.logger.debug(retMsg)
        return (retMsg, combinedManifest)

    # Compare the list of AMs in the request with AMs known
    # to the SCS. Any that the SCS does not know means the request
    # cannot succeed if those are AMs in a stitched link
    def checkSCSAMs(self):
        # FIXME: This takes time. If this can't block a more expensive later operation, why bother?
        scsAggs = {}
        try:
            scsAggs = self.scsService.ListAggregates(False, self.opts.ssltimeout)
        except Exception, e:
            self.logger.debug("SCS ListAggregates failed: %s", e)
        if scsAggs and isinstance(scsAggs, dict) and len(scsAggs.keys()) > 0:
            if scsAggs.has_key('value') and scsAggs['value'].has_key('geni_aggregate_list'):
                scsAggs = scsAggs['value']['geni_aggregate_list']
#                self.logger.debug("Got geni_agg_list from scs: %s", scsAggs)
                # Now sanity check AMs requested
                # Note that this includes AMs that the user does not
                # want to stitch - so we cannot error out early
                # FIXME: Can we ID from the request which are AMs that need a stitch?
                for reqAMURN in self.parsedUserRequest.amURNs:
                    found = False
                    for sa in scsAggs.keys():
                        if scsAggs[sa]['urn'] == reqAMURN:
                            self.logger.debug("Requested AM URN %s is listed by SCS with URL %s", reqAMURN, scsAggs[sa]['url'])
                            found = True
                            break
                    if not found:
                        self.logger.warn("Your request RSpec specifies the aggregate (component manager) '%s' for which there are no stitching paths configured. If you requested a stitched link to this aggregate, it will fail.", reqAMURN)


    def cleanup(self):
        '''Remove temporary files if not in debug mode'''
        if self.opts.debug:
            return
        
        scsres = prependFilePrefix(self.opts.fileDir, Aggregate.FAKEMODESCSFILENAME)
        if os.path.exists(scsres):
            os.unlink(scsres)

        if self.savedSliceCred and os.path.exists(self.opts.slicecredfile):
            os.unlink(self.opts.slicecredfile)

        if not self.ams_to_process:
            return

        for am in self.ams_to_process:
            # Remove getversion files
            # Note the AM URN here may not be right, so we might miss a file
            filename = handler_utils._construct_output_filename(self.opts, None, am.url, am.urn, "getversion", ".json", 1)
#            self.logger.debug("Deleting AM getversion: %s", filename)
            if os.path.exists(filename):
                os.unlink(filename)

            # Remove any per AM request RSpecs
            if am.rspecfileName and not self.opts.output:
#                self.logger.debug("Deleting AM request: %s", am.rspecfileName)
                if os.path.exists(am.rspecfileName):
                    os.unlink(am.rspecfileName)

            # v2.5 left these manifest & status files there. Leave them still? Remove them?

            # Now delete the per AM saved manifest rspec file
            if not self.opts.output:
                manfile = handler_utils._construct_output_filename(self.opts, self.slicename, am.url, am.urn, "manifest-rspec", ".xml", 1)
#                self.logger.debug("Deleting AM manifest: %s", manfile)
                if os.path.exists(manfile):
                    os.unlink(manfile)

                # Now delete per AM saved status files
                statusfilename = handler_utils._construct_output_filename(self.opts, self.slicename, am.url, am.urn, "sliverstatus", ".json", 1)
#                self.logger.debug("Deleting AM status: %s", statusfilename)
                if os.path.exists(statusfilename):
                    os.unlink(statusfilename)

    def mainStitchingLoop(self, sliceurn, requestDOM, existingAggs=None):
        # existingAggs are Aggregate objects

        if datetime.datetime.utcnow() >= self.config['timeoutTime']:
            msg = "Reservation attempt timed out after %d minutes." % self.opts.timeout
            self.logger.warn("%s Deleting any reservations...")
            class DumbLauncher():
                def __init__(self, agglist):
                    self.aggs = agglist
            try:
                result = self.deleteAllReservations(DumbLauncher(existingAggs))
                if not result:
                    for am in existingAggs:
                        if am.manifestDom:
                            self.logger.warn("You have a reservation at %s", am)
            except KeyboardInterrupt:
                self.logger.error('... deleting interrupted!')
                for am in existingAggs:
                    if am.manifestDom:
                        self.logger.warn("You have a reservation at %s", am)
            raise SticherError(msg)

        self.scsCalls = self.scsCalls + 1
        if self.isStitching:
            if self.scsCalls == 1:
                self.logger.info("Calling SCS...")
            else:
                thStr = 'th'
                if self.scsCalls == 2:
                    thStr = 'nd'
                elif self.scsCalls == 3:
                    thStr = 'rd'
                if self.scsCalls == self.maxSCSCalls:
                    self.logger.info("Calling SCS for the %d%s and last time...", self.scsCalls, thStr)
                else:
                    self.logger.info("Calling SCS for the %d%s time...", self.scsCalls, thStr)

            scsResponse = self.callSCS(sliceurn, requestDOM, existingAggs)
        self.lastException = None # Clear any last exception from the last run through

        if self.scsCalls > 1 and existingAggs:
            # We are doing another call.
            # Let AMs recover. Is this long enough?
            # If one of the AMs is a DCN AM, use that sleep time instead - longer
            sTime = Aggregate.PAUSE_FOR_AM_TO_FREE_RESOURCES_SECS
            for agg in existingAggs:
                if agg.dcn and agg.triedRes:
                    # Only need to sleep this much longer time
                    # if this is a DCN AM that we tried a reservation on (whether it worked or failed)
                    if sTime == Aggregate.PAUSE_FOR_AM_TO_FREE_RESOURCES_SECS:
                        self.logger.debug("Must sleep longer cause had a previous reservation attempt at a DCN AM: %s", agg)
                    sTime = Aggregate.PAUSE_FOR_DCN_AM_TO_FREE_RESOURCES_SECS
                # Reset whether we've tried this AM this time through
                agg.triedRes = False

            if datetime.datetime.utcnow() + datetime.timedelta(seconds=sTime) >= self.config['timeoutTime']:
                # We'll time out. So quit now.
                self.logger.debug("After planned sleep for %d seconds we will time out", sTime)
                msg = "Reservation attempt timing out after %d minutes." % self.opts.timeout
                self.logger.warn("%s Deleting any reservations...")
                class DumbLauncher():
                    def __init__(self, agglist):
                        self.aggs = agglist
                try:
                    result = self.deleteAllReservations(DumbLauncher(existingAggs))
                    if not result:
                        for am in existingAggs:
                            if am.manifestDom:
                                self.logger.warn("You have a reservation at %s", am)
                except KeyboardInterrupt:
                    self.logger.error('... deleting interrupted!')
                    for am in existingAggs:
                        if am.manifestDom:
                            self.logger.warn("You have a reservation at %s", am)
                raise SticherError(msg)

            self.logger.info("Pausing for %d seconds for Aggregates to free up resources...\n\n", sTime)
            time.sleep(sTime)

        # Parse SCS Response, constructing objects and dependencies, validating return
        if self.isStitching:
            self.parsedSCSRSpec, workflow_parser = self.parseSCSResponse(scsResponse)
            scsResponse = None # Just to note we are done with this here (keep no state)
        else:
            # FIXME: with the user rspec
            try:
                xmlreq = requestDOM.toxml()
            except Exception, xe:
                self.logger.debug("Failed to XMLify requestDOM for parsing: %s", xe)
                self._raise_omni_error("Malformed request RSpec: %s" % xe)

            self.parsedSCSRSpec = self.rspecParser.parse(xmlreq)
            workflow_parser = WorkflowParser(self.logger)

            # Parse the workflow, creating Path/Hop/etc objects
            # In the process, fill in a tree of which hops depend on which,
            # and which AMs depend on which
            # Also mark each hop with what hop it imports VLANs from,
            # And check for AM dependency loops
            workflow_parser.parse({}, self.parsedSCSRSpec)
#            self.logger.debug("Did fake workflow parsing")

        if existingAggs:
            # Copy existingAggs.hops.vlans_unavailable to workflow_parser.aggs.hops.vlans_unavailable? Other state?
            self.saveAggregateState(existingAggs, workflow_parser.aggs)
            existingAggs = None # Now done

        # FIXME: if notScript, print AM dependency tree?

        # Ensure we are processing all the workflow aggs plus any aggs in the RSpec not in
        # the workflow
        self.ams_to_process = copy.copy(workflow_parser.aggs)

        if self.isStitching:
            self.logger.debug("SCS workflow said to include resources from these aggregates:")
            for am in self.ams_to_process:
                self.logger.debug("\t%s", am)

        addedAMs = []
        for amURN in self.parsedSCSRSpec.amURNs:
#            self.logger.debug("Looking at SCS returned amURN %s", amURN)
            found = False
            for agg in self.ams_to_process:
                if agg.urn == amURN:
                    found = True
#                    self.logger.debug(" .. was already in ams_to_process")
                    break
                # For EG there are multiple URNs that are really the same
                # If find one, found them all
                for urn2 in agg.urn_syns:
                    if urn2 == amURN:
#                        self.logger.debug(" .. was in ams_to_process under synonym. Ams_to_process had %s", agg.urn)
                        found = True
                        break
            if found:
                continue
            else:
                # AM URN was not in the workflow from the SCS
#                # If this URN was on a stitching link, then this isn't going to work
#                for link in self.parsedSCSRSpec.links:
#                    if len(link.aggregates) > 1 and not link.hasSharedVlan and link.typeName == link.VLAN_LINK_TYPE:
#                        # This is a link that needs stitching
#                        for linkagg in link.aggregates:
#                            if linkagg.urn == amURN or amURN in linkagg.urn_syns:
#                                self.logger.debug("Found AM %s on stitching link %s that is not in SCS Workflow. URL: %s", amURN, link.id, linkagg.url)
#                                stitching = self.parsedSCSRSpec.stitching
#                                slink = None
#                                if stitching:
#                                    slink = stitching.find_path(link.id)
#                                if not slink:
#                                    self.logger.debug("No path in stitching section of rspec for link %s that seems to need stitching", link.id)
#                                raise StitchingError("SCS did not handle link %s - perhaps AM %s is unknown?", link.id, amURN)

                am = Aggregate.find(amURN)
                addedAMs.append(am)
                if not am.url:
                    # FIXME: Avoid apparent v1 URLs
                    for urn in am.urn_syns:
                        (nick, url) = handler_utils._lookupAggNickURLFromURNInNicknames(self.logger, self.config, urn)
                        if url and url.strip() != '':
                            self.logger.debug("Found AM %s URL using URN %s from omni_config AM nicknames: %s", amURN, urn, nick)
                            am.url = url
                            am.nick = nick
                            break

                if not am.url:
                    # Try asking our CH for AMs to get the URL for the
                    # given URN
                    fw_ams = dict()
                    try:
                        fw_ams = self.framework.list_aggregates()
                        for fw_am_urn in fw_ams.keys():
                            if fw_am_urn and fw_am_urn.strip() in am.urn_syns and fw_ams[fw_am_urn].strip() != '':
                                am.url = fw_ams[fw_am_urn]
                                self.logger.debug("Found AM %s URL from CH ListAggs: %s", amURN, am.url)
                                break
                    except:
                        pass
                if not am.url:
                    raise StitchingError("RSpec requires AM '%s' which is not in workflow and URL is unknown!" % amURN)
                else:
                    self.logger.debug("Adding am to ams_to_process from URN %s, with url %s", amURN, am.url)
                    self.ams_to_process.append(am)
        # Done adding user requested non linked AMs to list of AMs to
        # process

        # Add extra info about the aggregates to the AM objects
        self.add_am_info(self.ams_to_process)

        # If using speaks for and have OESS in the list, bail
        haveOESS = None
        for am in self.ams_to_process:
            if am.isOESS:
                haveOESS = am
                break
        if haveOESS and self.opts.speaksfor:
            self.logger.debug("%s required, is AL2S, but 'speaksfor' option specified", haveOESS)
            raise StitchingError("Request requires AL2S but uses 'Speaks For' which is not supported (yet) at AL2S.")

        # FIXME: check each AM reachable, and we know the URL/API version to use

        # If requesting from >1 ExoGENI AM, then use ExoSM. And use ExoSM only once.
        self.ensureOneExoSM()

        self.dump_objects(self.parsedSCSRSpec, self.ams_to_process)

        self.logger.info("Multi-AM reservation will include resources from these aggregates:")
        for am in self.ams_to_process:
            self.logger.info("\t%s", am)

        # If we said this rspec needs a fixed / fake endpoint, add it here - so the SCS and other stuff
        # doesn't try to do anything with it
        if self.opts.fixedEndpoint:
            self.addFakeNode()

        # Change the requested VLAN tag to 'any' where we can, allowing
        # The AM to pick from the currently available tags
        self.changeRequestsToAny()

        for am in self.ams_to_process:
            if self.slicecred:
                # Hand each AM the slice credential, so we only read it once
                am.slicecred = self.slicecred
            # Also hand the timeout time
            am.timeoutTime = self.config['timeoutTime']

        if self.opts.noReservation:
            self.logger.info("Not reserving resources")

            # Write the request rspec to a string that we save to a file
            try:
                requestString = self.parsedSCSRSpec.dom.toxml(encoding="utf-8")
            except Exception, xe:
                self.logger.debug("Failed to XMLify parsed SCS request RSpec for saving: %s", xe)
                self._raise_omni_error("Malformed SCS expanded request RSpec: %s" % xe)

            header = "<!-- Expanded Resource request for:\n\tSlice: %s -->" % (self.slicename)
            if requestString is not None:
                content = stripBlankLines(string.replace(requestString, "\\n", '\n'))
            else:
                self.logger.debug("None expanded request RSpec?")
                content = ""
            filename = None

            ot = self.opts.output
            if not self.opts.tostdout:
                self.opts.output = True

            if self.opts.output:
                filename = handler_utils._construct_output_filename(self.opts, self.slicename, '', None, "expanded-request-rspec", ".xml", 1)
            if filename:
                self.logger.info("Saving expanded request RSpec to file: %s", os.path.abspath(filename))
            else:
                self.logger.info("Expanded request RSpec:")

            if not self.opts.debug:
                # Suppress all but WARN on console here
                lvl = self.logger.getEffectiveLevel()
                handlers = self.logger.handlers
                if len(handlers) == 0:
                    handlers = logging.getLogger().handlers
                for handler in handlers:
                    if isinstance(handler, logging.StreamHandler):
                        lvl = handler.level
                        handler.setLevel(logging.WARN)
                        break

            # Create FILE
            # This prints or logs results, depending on whether filename is None
            handler_utils._printResults(self.opts, self.logger, header, content, filename)
            if not self.opts.debug:
                handlers = self.logger.handlers
                if len(handlers) == 0:
                    handlers = logging.getLogger().handlers
                for handler in handlers:
                    if isinstance(handler, logging.StreamHandler):
                        handler.setLevel(lvl)
                        break
            self.opts.output = ot

            raise StitchingError("Requested no reservation")

        # Check current VLAN tag availability before doing allocations
        ret = self.updateAvailRanges(sliceurn, requestDOM)
        if ret is not None:
            return ret

        if self.opts.genRequest:
            # Write the fully expanded/updated request RSpec to a file

            self.logger.debug("Generating updated combined request RSpec")
            combinedRequestDom = combineManifestRSpecs(self.ams_to_process, self.parsedSCSRSpec.dom, useReqs=True)

            try:
                reqString = combinedRequestDom.toprettyxml(encoding="utf-8")
            except Exception, xe:
                self.logger.debug("Failed to XMLify combined Request RSpec: %s", xe)
                self._raise_omni_error("Malformed combined request RSpec: %s" % xe)
            reqString = stripBlankLines(reqString)

            # set rspec to be UTF-8
            if isinstance(reqString, unicode):
                reqString = reqString.encode('utf-8')
                self.logger.debug("Combined request RSpec was unicode")

            # FIXME: Handle errors. Maybe make return use code/value/output struct
            # If error and have an expanded request from SCS, include that in output.
            #   Or if particular AM had errors, ID the AMs and errors

            # FIXME: This prepends a header on an RSpec that might already have a header
            # -- maybe replace any existing header

            # FIXME: We force -o here and keep it from logging the
            # RSpec. Do we need an option to not write the RSpec to a file?

            ot = self.opts.output
            if not self.opts.tostdout:
                self.opts.output = True

            if not self.opts.debug:
                # Suppress all but WARN on console here
                lvl = self.logger.getEffectiveLevel()
                handlers = self.logger.handlers
                if len(handlers) == 0:
                    handlers = logging.getLogger().handlers
                for handler in handlers:
                    if isinstance(handler, logging.StreamHandler):
                        lvl = handler.level
                        handler.setLevel(logging.WARN)
                        break

            retVal, filename = handler_utils._writeRSpec(self.opts, self.logger, reqString, None, '%s-expanded-request'%self.slicename, '', None)
            if not self.opts.debug:
                handlers = self.logger.handlers
                if len(handlers) == 0:
                    handlers = logging.getLogger().handlers
                for handler in handlers:
                    if isinstance(handler, logging.StreamHandler):
                        handler.setLevel(lvl)
                        break
            self.opts.output = ot

            if filename:
                msg = "Saved expanded request RSpec at %d AMs to file '%s'" % (len(self.ams_to_process), os.path.abspath(filename))
                self.logger.info(msg)
            raise StitchingError("Requested to only generate and save the expanded request")
        # End of block to save the expanded request and exit

        # The launcher handles calling the aggregates to do their allocation
        launcher = stitch.Launcher(self.opts, self.slicename, self.ams_to_process, self.config['timeoutTime'])
        try:
            # Spin up the main loop
            lastAM = launcher.launch(self.parsedSCSRSpec, self.scsCalls)
# for testing calling the SCS only many times
#            raise StitchingCircuitFailedError("testing")

        except StitchingCircuitFailedError, se:
            self.lastException = se
            if self.scsCalls == self.maxSCSCalls:
                self.logger.error("Stitching max circuit failures reached - will delete and exit.")
                try:
                    result = self.deleteAllReservations(launcher)
                    if not result:
                        for am in launcher.aggs:
                            if am.manifestDom:
                                self.logger.warn("You have a reservation at %s", am)
                except KeyboardInterrupt:
                    self.logger.error('... deleting interrupted!')
                    for am in launcher.aggs:
                        if am.manifestDom:
                            self.logger.warn("You have a reservation at %s", am)
                raise StitchingError("Stitching reservation failed %d times. Last error: %s" % (self.scsCalls, se))
            self.logger.warn("Stitching failed but will retry: %s", se)
            success = False
            try:
                success = self.deleteAllReservations(launcher)
            except KeyboardInterrupt:
                self.logger.error('... deleting interrupted!')
                for am in launcher.aggs:
                    if am.manifestDom:
                        self.logger.warn("You have a reservation at %s", am)
            if not success:
                raise StitchingError("Stitching failed. Would retry but delete had errors. Last Stitching error: %s" % se)

            # Flush the cache of aggregates. Loses all state. Avoids
            # double adding hops to aggregates, etc. But we lose the vlans_unavailable. And ?
            aggs = copy.copy(self.ams_to_process)
            self.ams_to_process = None # Clear local memory of AMs to avoid issues
            Aggregate.clearCache()

            # construct new SCS args
            # redo SCS call et al
            # FIXME: aggs.hops have loose tag: mark the hops in the request as explicitly loose
            # FIXME: Here we pass in the request to give to the SCS. I'd like this
            # to be modified (different VLAN range? Some hops marked loose?) in future
            lastAM = self.mainStitchingLoop(sliceurn, requestDOM, aggs)
        except StitchingError, se:
            self.logger.error("Stitching failed with an error: %s", se)
            if self.lastException:
                self.logger.error("Root cause error: %s", self.lastException)
                newError = StitchingError("%s which caused %s" % (str(self.lastException), str(se)))
                se = newError
            try:
                result = self.deleteAllReservations(launcher)
                if not result:
                    for am in launcher.aggs:
                        if am.manifestDom:
                            self.logger.warn("You have a reservation at %s", am)
            except KeyboardInterrupt:
                self.logger.error('... deleting interrupted!')
                for am in launcher.aggs:
                    if am.manifestDom:
                        self.logger.warn("You have a reservation at %s", am)
                #raise
            raise se
        return lastAM

    def updateAvailRanges(self, sliceurn, requestDOM):
        # Check current VLAN tag availability before doing allocations
        # Loop over AMs. If I update an AM, then go to AMs that depend on it and intersect there (but don't redo avail query), and recurse.
        for am in self.ams_to_process:
            # If doing the avail query at this AM doesn't work or wouldn't help or we did it recently, move on
            if not am.doAvail(self.opts):
                self.logger.debug("Not checking VLAN availability at %s", am)
                continue

            self.logger.debug("Checking current availabilty at %s", am)
            madeChange = False
            try:
                madeChange = am.updateWithAvail(self.opts)

                if madeChange:
                    # Must intersect the new ranges with others in the chain
                    # We have already updated avail and checked request at this AM
                    for hop in am.hops:
                        self.logger.debug("Applying updated availability up the chain for %s", hop)
                        while hop.import_vlans:
                            newHop = hop.import_vlans_from
                            oldRange = newHop._hop_link.vlan_range_request
                            newHop._hop_link.vlan_range_request = newHop._hop_link.vlan_range_request.intersection(hop._hop_link.vlan_range_request)
                            if oldRange != newHop._hop_link.vlan_range_request:
                                self.logger.debug("Reset range of %s to '%s' from %s", newHop, newHop._hop_link.vlan_range_request, oldRange)
                            else:
                                self.logger.debug("Availability unchanged at %s", newHop)
                            if len(newHop._hop_link.vlan_range_request) <= 0:
                                self.logger.debug("New available range is empty!")
                                raise StitchingCircuitFailedError("No VLANs possible at %s based on latest availability; Try again from the SCS" % newHop.aggregate)
                            if newHop._hop_link.vlan_suggested_request != VLANRange.fromString("any") and not newHop._hop_link.vlan_suggested_request <= newHop._hop_link.vlan_range_request:
                                self.logger.debug("Suggested (%s) is not in reset available range - mark it unavailable and raise an error!", newHop._hop_link.vlan_suggested_request)
                                newHop.vlans_unavailable = newHop.vlans_unavailable.union(newHop._hop_link.vlan_suggested_request)
                                raise StitchingCircuitFailedError("Requested VLAN unavailable at %s based on latest availability; Try again from the SCS" % newHop)
                            else:
                                self.logger.debug("Suggested (%s) still in reset available range", newHop._hop_link.vlan_suggested_request)
                            hop = newHop
                        # End of loop up the imports chain for this hop
                    # End of loop over all hops on this AM where we just updated availability
                    self.logger.debug("Done applying updated availabilities from %s", am)
                else:
                    self.logger.debug("%s VLAN availabilities did not change. Done with this AM", am)
                # End of block to only update avails up the chain if we updated availability on this AM
            except StitchingCircuitFailedError, se:
                self.lastException = se
                if self.scsCalls == self.maxSCSCalls:
                    self.logger.error("Stitching max circuit failures reached")
                    raise StitchingError("Stitching reservation failed %d times. Last error: %s" % (self.scsCalls, se))
                # FIXME: If we aren't doing stitching so won't be calling the SCS, then does it ever make sense
                # to try this again here? For example, EG Embedding workflow ERROR?
#                if not self.isStitching:
#                    self.logger.error("Reservation failed and not reasonable to retry - not a stitching request.")
#                    raise StitchingError("Multi AM reservation failed. Not stitching so cannot retry with new path. %s" % se)

                self.logger.warn("Stitching failed but will retry: %s", se)

                # Flush the cache of aggregates. Loses all state. Avoids
                # double adding hops to aggregates, etc. But we lose the vlans_unavailable. And ?
                aggs = copy.copy(self.ams_to_process)
                self.ams_to_process = None # Clear local memory of AMs to avoid issues
                Aggregate.clearCache()

                # construct new SCS args
                # redo SCS call et al
                return self.mainStitchingLoop(sliceurn, requestDOM, aggs)
            # End of exception handling block
        # End of loop over AMs getting current availability
        return None # Not an AM return so don't return it in the main block

    def changeRequestsToAny(self):
        # Change requested VLAN tags to 'any' where appropriate

        # Check the AMs: For each hop that says it is a VLAN producer / imports no VLANs, lets change the suggested request to "any".
        # That should ensure that that hop succeeds the first time through. Hopefully the SCS has set up the avail ranges to work throughout
        # the path, so everything else will just work as well.

        # In APIv3, a failure later is just a negotiation case (we'll get a new tag to try). In APIv2, a later failure is a pseudo negotiation case.
        # That is, we can go back to the 'any' hop and exclude the failed tag, deleting that reservation, and try again.

        # FIXME: In schema v2, the logic for where to figure out if it is a consumer or producer is more complex. But for now, the hoplink says,
        # and the hop indicates if it imports vlans.

        # While doing this, make sure the tells for whether we can tell the hop to pick the tag are consistent.
        if self.opts.useSCSSugg:
            self.logger.info("Per option, requesting SCS suggested VLAN tags")
            return

        for am in self.ams_to_process:
            if self.opts.useSCSSugg:
                #self.logger.info("Per option, requesting SCS suggested VLAN tags")
                continue
            if not am.supportsAny():
                self.logger.debug("%s doesn't support requesting 'any' VLAN tag - move on", am)
                continue
            # Could a complex topology have some hops producing VLANs and some accepting VLANs at the same AM?
#            if len(am.dependsOn) == 0:
#                self.logger.debug("%s says it depends on no other AMs", am)
            for hop in am.hops:
                # Init requestAny so we never request 'any' when option says not or it is one of the non-supported AMs
                requestAny = not self.opts.useSCSSugg and am.supportsAny()
                if not requestAny:
                    continue
                isConsumer = False
                isProducer = False
                imports = False
                if hop._hop_link.vlan_consumer:
#                    self.logger.debug("%s says it is a vlan consumer. In itself, that is OK", hop)
                    isConsumer = True
                if hop._import_vlans:
                    if hop.import_vlans_from._aggregate != hop._aggregate:
                        imports = True
                        self.logger.debug("%s imports VLANs from another AM, %s. Don't request 'any'.", hop, hop.import_vlans_from)
                        if len(am.dependsOn) == 0:
                            self.logger.warn("%s imports VLANs from %s but the AM says it depends on no AMs?!", hop, hop.import_vlans_from)
                        requestAny = False
                    else:
                        # This hop imports tags from another hop on the same AM.
                        # So we want this hop to do what that other hop does. So if that other hop is changing to any, this this
                        # hop should change to any.
                        hop2 = hop.import_vlans_from
                        if hop2._import_vlans and hop2.import_vlans_from._aggregate != hop2._aggregate:
                            imports = True
                            requestAny = False
                            self.logger.debug("%s imports VLANs from %s which imports VLANs from a different AM (%s) so don't request 'any'.", hop, hop2, hop2._import_vlans_from)
                        elif not hop2._hop_link.vlan_producer:
                            self.logger.debug("%s imports VLANs from %s which does not say it is a vlan producer. Don't request 'any'.", hop, hop2)
                            requestAny = False
                        else:
                            self.logger.debug("%s imports VLANs from %s which is OK to request 'any', so this hop should request 'any'.", hop, hop2)
                if not hop._hop_link.vlan_producer:
                    if not imports and not isConsumer:
                        # See http://groups.geni.net/geni/ticket/1263 and http://groups.geni.net/geni/ticket/1262
                        if not am.supportsAny():
                            self.logger.debug("%s doesn't import VLANs and not marked as either a VLAN producer or consumer. But it is an EG or GRAM or OESS or DCN AM, where we cannot assume 'any' works.", hop)
                            requestAny = False
                        else:
                            # If this hop doesn't import and isn't explicitly marked as either a consumer or a producer, then
                            # assume it is willing to produce a VLAN tag
                            self.logger.debug("%s doesn't import and not marked as either a VLAN producer or consumer. Assuming 'any' is OK.", hop)
                            requestAny = True
                    else:
                        if requestAny:
                            self.logger.debug("%s does not say it is a vlan producer. Don't request 'any'.", hop)
                            requestAny = False
                        else:
                            self.logger.debug("%s does not say it is a vlan producer. Still not requesting 'any'.", hop)
                else:
                    isProducer = True
                    self.logger.debug("%s marked as a VLAN producer", hop)
                if not requestAny and not imports and not isConsumer and not isProducer:
                    if not am.supportsAny():
                        self.logger.debug("%s doesn't import VLANs and not marked as either a VLAN producer or consumer. But it is an EG or GRAM or OESS or DCN AM, where we cannot assume 'any' works.", hop)
                    else:
                        # If this hop doesn't import and isn't explicitly marked as either a consumer or a producer, then
                        # assume it is willing to produce a VLAN tag
                        self.logger.debug("%s doesn't import VLANs and not marked as either a VLAN producer or consumer. Assuming 'any' is OK.", hop)
                        requestAny = True
                if self.opts.useSCSSugg and requestAny:
                    self.logger.info("Would request 'any', but user requested to stick to SCS suggestions.")
                elif requestAny:
                    if len(am.dependsOn) != 0:
                        self.logger.debug("%s appears OK to request tag 'any', but the AM says it depends on other AMs?", hop)
                    if hop._hop_link.vlan_suggested_request != VLANRange.fromString("any"):
                        self.logger.debug("Changing suggested request tag from %s to 'any' on %s", hop._hop_link.vlan_suggested_request, hop)
                        hop._hop_link.vlan_suggested_request = VLANRange.fromString("any")
#                    else:
#                        self.logger.debug("%s suggested request was already 'any'.", hop)
            # End of loop over hops in AM
        # End of loop over AMs to process

    def deleteAllReservations(self, launcher):
        '''On error exit, ensure all outstanding reservations are deleted.'''
        ret = True
        loggedDeleting = False
        for am in launcher.aggs:
            if am.manifestDom:
                if not loggedDeleting:
                    loggedDeleting = True
                    self.logger.info("Deleting existing reservations...")
                self.logger.debug("Had reservation at %s", am)
                try:
                    am.deleteReservation(self.opts, self.slicename)
                    self.logger.info("Deleted reservation at %s.", am)
                except StitchingError, se2:
                    self.logger.warn("Failed to delete reservation at %s: %s", am, se2)
                    ret = False
        return ret

    def confirmGoodRSpec(self, requestString, rspecType=rspec_schema.REQUEST, doRSpecLint=True):
        '''Ensure an rspec is valid'''
        typeStr = 'Request'
        if rspecType == rspec_schema.MANIFEST:
            typeStr = 'Manifest'
        # Confirm the string is a request rspec, valid
        if requestString is None or str(requestString).strip() == '':
            raise OmniError("Empty %s rspec" % typeStr)
        if not is_rspec_string(requestString, None, None, logger=self.logger):
            raise OmniError("%s RSpec file did not contain an RSpec" % typeStr)
#        if not is_rspec_of_type(requestString, rspecType):
#        if not is_rspec_of_type(requestString, rspecType, "GENI 3", False, logger=self.logger):
        # FIXME: ION does not support PGv2 schema RSpecs. Stitcher doesn't mind, and PG AMs don't mind, but
        # this if the request is PGv2 and crosses ION this may cause trouble.
        if not (is_rspec_of_type(requestString, rspecType, "GENI 3", False) or is_rspec_of_type(requestString, rspecType, "ProtoGENI 2", False)):
            if self.opts.devmode:
                self.logger.info("RSpec of wrong type or schema, but continuing...")
            else:
                raise OmniError("%s RSpec file did not contain a %s RSpec (wrong type or schema)" % (typeStr, typeStr))

        # Run rspeclint
        if doRSpecLint:
            try:
                rspeclint_exists()
            except:
                self.logger.debug("No rspeclint found")
                return
            # FIXME: Make this support GENIv4+? PGv2?
            schema = rspec_schema.GENI_3_REQ_SCHEMA
            if rspecType == rspec_schema.MANIFEST:
                schema = rspec_schema.GENI_3_MAN_SCHEMA
            if not validate_rspec(requestString, rspec_schema.GENI_3_NAMESPACE, schema):
                raise OmniError("%s RSpec does not validate against its schemas" % typeStr)

    def confirmSliceOK(self):
        '''Ensure the given slice name corresponds to a current valid slice,
        and return the Slice URN and expiration datetime.'''

        self.logger.info("Reading slice %s credential...", self.slicename)

        # Get slice URN from name
        try:
            sliceurn = self.framework.slice_name_to_urn(self.slicename)
        except Exception, e:
            self.logger.error("Could not determine slice URN from name %s: %s", self.slicename, e)
            raise StitchingError(e)

        self.slicehrn = urn_to_clean_hrn(sliceurn)[0]

        if self.opts.fakeModeDir:
            self.logger.info("Fake mode: not checking slice credential")
            return (sliceurn, naiveUTC(datetime.datetime.max))

        if self.opts.noReservation:
            self.logger.info("Requested noReservation: not checking slice credential")
            return (sliceurn, naiveUTC(datetime.datetime.max))

        if self.opts.genRequest:
            self.logger.info("Requested only generate request: not checking slice credential")
            return (sliceurn, naiveUTC(datetime.datetime.max))

        # Get slice cred
        (slicecred, message) = handler_utils._get_slice_cred(self, sliceurn)

        if not slicecred:
            # FIXME: Maybe if the slice doesn't exist, create it?
            # omniargs = ["createslice", self.slicename]
            # try:
            #     (slicename, message) = omni.call(omniargs, self.opts)
            # except:
            #     pass
            raise StitchingError("Could not get a slice credential for slice %s: %s" % (sliceurn, message))

        self.slicecred = slicecred

        self.savedSliceCred = False

        # Force the slice cred to be from a saved file if not already set
        if not self.opts.slicecredfile:
            self.opts.slicecredfile = os.path.join(os.getenv("TMPDIR", os.getenv("TMP", "/tmp")), SLICECRED_FILENAME)
            if "%username" in self.opts.slicecredfile:
                self.opts.slicecredfile = string.replace(self.opts.slicecredfile, "%username", self.username)
            if "%slicename" in self.opts.slicecredfile:
                self.opts.slicecredfile = string.replace(self.opts.slicecredfile, "%slicename", self.slicename)
            if "%slicehrn" in self.opts.slicecredfile:
                self.opts.slicecredfile = string.replace(self.opts.slicecredfile, "%slicehrn", self.slicehrn)
            self.opts.slicecredfile = os.path.normpath(self.opts.slicecredfile)
            if self.opts.fileDir:
                self.opts.slicecredfile = prependFilePrefix(self.opts.fileDir, self.opts.slicecredfile)
            trim = -4
            if self.opts.slicecredfile.endswith("json"):
                trim = -5
            # -4 is to cut off .xml. It would be -5 if the cred is json
            handler_utils._save_cred(self, self.opts.slicecredfile[:trim], slicecred)
            self.savedSliceCred = True

        # Ensure slice not expired
        sliceexp = credutils.get_cred_exp(self.logger, slicecred)
        sliceexp = naiveUTC(sliceexp)
        now = datetime.datetime.utcnow()
        shorthours = 3
        middays = 1
        if sliceexp <= now:
            # FIXME: Maybe if the slice doesn't exist, create it?
            # omniargs = ["createslice", self.slicename]
            # try:
            #     (slicename, message) = omni.call(omniargs, self.opts)
            # except:
            #     pass
            raise StitchingError("Slice %s expired at %s" % (sliceurn, sliceexp))
        elif sliceexp - datetime.timedelta(hours=shorthours) <= now:
            self.logger.warn('Slice %s expires in <= %d hours on %s UTC' % (sliceurn, shorthours, sliceexp))
            self.logger.debug('It is now %s UTC' % (datetime.datetime.utcnow()))
        elif sliceexp - datetime.timedelta(days=middays) <= now:
            self.logger.info('Slice %s expires within %d day on %s UTC' % (sliceurn, middays, sliceexp))
        else:
            self.logger.info('Slice %s expires on %s UTC' % (sliceurn, sliceexp))

        # return the slice urn, slice expiration (datetime)
        return (sliceurn, sliceexp)

    # Ensure the link has 2 well formed property elements each with a capacity
    def addCapacityOneLink(self, link):
        # look for property elements
        if len(link.properties) > 2:
            raise StitchingError("Your request RSpec is malformed: include either 2 or 0 property elements on link '%s'" % link.id)
        # Get the 2 node IDs
        ifcs = link.interfaces
        if len(ifcs) < 2:
            self.logger.debug("Link '%s' doesn't have at least 2 interfaces? Has %d", link.id, len(ifcs))
            return
        if len(ifcs) > 2:
            self.logger.debug("Link '%s' has more than 2 interfaces (%d). Picking source and dest from the first 2 on different AMs.", link.id, len(ifcs))
        node1ID = ifcs[0].client_id
        node1AM = None
        for node in self.parsedUserRequest.nodes:
            if node1ID in node.interface_ids:
                node1AM = node.amURN
                break

        # Now find a 2nd interface on a different AM
        node2ID = None
        node2AM = None
        for ifc in ifcs:
            if ifc.client_id == node1ID:
                continue
            node2ID = ifc.client_id
            node2AM = None
            for node in self.parsedUserRequest.nodes:
                if node2ID in node.interface_ids:
                    node2AM = node.amURN
                    break
            if node2AM == node1AM:
                node2ID = None
                node2AM = None
                continue
            else:
                break
        if node2AM is None:
            # No 2nd interface on different AM found
            self.logger.debug("Link '%s' doesn't have interfaces on more than 1 AM ('%s')?" % (link.id, node1AM))
        else:
            self.logger.debug("Link '%s' properties will be from '%s' to '%s'", link.id, node1ID, node2ID)

        # If there are no property elements
        if len(link.properties) == 0:
            self.logger.debug("Link '%s' had no properties - must add them", link.id)
            # Then add them
            s_id = node1ID
            d_id = node2ID
            s_p = LinkProperty(s_id, d_id, None, None, self.opts.defaultCapacity)
            s_p.link = link
            d_p = LinkProperty(d_id, s_id, None, None, self.opts.defaultCapacity)
            d_p.link = link
            link.properties = [s_p, d_p]
            return

        # If the elements are there, error check them, adding property if necessary
        if len(link.properties) == 2:
            props = link.properties
            prop1S = props[0].source_id
            prop1D = props[0].dest_id
            prop2S = props[1].source_id
            prop2D = props[1].dest_id
            if prop1S is None or prop1S == "":
                raise StitchingError("Malformed property on link '%s' missing source_id attribute" % link.id)
            if prop1D is None or prop1D == "":
                raise StitchingError("Malformed property on link '%s' missing dest_id attribute" % link.id)
            if prop1D == prop1S:
                raise StitchingError("Malformed property on link '%s' has matching source and dest_id: %s" % (link.id, prop1D))
            if prop2S is None or prop2S == "":
                raise StitchingError("Malformed property on link '%s' missing source_id attribute" % link.id)
            if prop2D is None or prop2D == "":
                raise StitchingError("Malformed property on link '%s' missing dest_id attribute" % link.id)
            if prop2D == prop2S:
                raise StitchingError("Malformed property on link '%s' has matching source and dest_id: %s" % (link.id, prop2D))
            # FIXME: Compare to the interface_refs
            if prop1S != prop2D or prop1D != prop2S:
                raise StitchingError("Malformed properties on link '%s': source and dest tags are not reversed" % link.id)
            if props[0].capacity and not props[1].capacity:
                props[1].capacity = props[0].capacity
            if props[1].capacity and not props[0].capacity:
                props[0].capacity = props[1].capacity
            for prop in props:
                if prop.capacity is None or prop.capacity == "":
                    prop.capacity = self.opts.defaultCapacity
                # FIXME: Warn about really small or big capacities?
            return

        # There is a single property tag
        prop = link.properties[0]
        if prop.source_id is None or prop.source_id == "":
            raise StitchingError("Malformed property on link '%s' missing source_id attribute" % link.id)
        if prop.dest_id is None or prop.dest_id == "":
            raise StitchingError("Malformed property on link '%s' missing dest_id attribute" % link.id)
        if prop.dest_id == prop.source_id:
            raise StitchingError("Malformed property on link '%s' has matching source and dest_id: '%s'" % (link.id, prop.dest_id))
        # FIXME: Compare to the interface_refs
        if prop.capacity is None or prop.capacity == "":
            prop.capacity = self.opts.defaultCapacity
        # FIXME: Warn about really small or big capacities?
        # Create the 2nd property with the source and dest reversed
        prop2 = LinkProperty(prop.dest_id, prop.source_id, prop.latency, prop.packet_loss, prop.capacity)
        link.properties = [prop, prop2]
        self.logger.debug("Link '%s' added missing reverse property", link.id)

    # Ensure all implicit AMs (from interface_ref->node->component_manager_id) are explicit on the link
    def ensureLinkListsAMs(self, link, requestRSpecObject):
        if not link:
            return

        ams = []
        for ifc in link.interfaces:
            found = False
            for node in requestRSpecObject.nodes:
                if ifc.client_id in node.interface_ids:
                    if node.amURN is not None and node.amURN not in ams:
                        ams.append(node.amURN)
                    found = True
                    self.logger.debug("Link '%s' interface '%s' found on node '%s'", link.id, ifc.client_id, node.id)
                    break
            if not found:
                self.logger.debug("Link '%s' interface '%s' not found on any node", link.id, ifc.client_id)
                # FIXME: What would this mean?

        for amURN in ams:
            am = Aggregate.find(amURN)
            if am not in link.aggregates:
                self.logger.debug("Adding missing AM %s to link '%s'", amURN, link.id)
                link.aggregates.append(am)

    def hasGRELink(self, requestRSpecObject):
        isGRE = False

        # Make sure links explicitly lists all its aggregates, so this test is valid
        if requestRSpecObject:
            for link in requestRSpecObject.links:
                self.ensureLinkListsAMs(link, requestRSpecObject)

        # has a link that has 2 interface_refs and has a link type of *gre_tunnel and endpoint nodes are PG
        if requestRSpecObject:
            for link in requestRSpecObject.links:
                if not (link.typeName == link.GRE_LINK_TYPE or link.typeName == link.EGRE_LINK_TYPE):
                    # Not GRE
#                    self.logger.debug("Link %s not GRE but %s", link.id, link.typeName)
                    continue
                if len(link.aggregates) != 2:
                    self.logger.warn("Link '%s' is a GRE link with %d AMs?", link.id, len(link.aggregates))
                    continue
                if len(link.interfaces) != 2:
                    self.logger.warn("Link '%s' is a GRE link with %d interfaces?", link.id, len(link.interfaces))
                    continue
                isGRE = True
                for ifc in link.interfaces:
                    found = False
                    for node in requestRSpecObject.nodes:
                        if ifc.client_id in node.interface_ids:
                            found = True
                            # This is the node

                            # I'd like to ensure the node is a PG node.
                            # But at this point we haven't called getversion yet
                            # So we don't really know if this is a PG node
#                            am = Aggregate.find(node.amURN)
#                            if not am.isPG:
#                                self.logger.warn("Bad GRE link %s: interface_ref %s is on a non PG node: %s", link.id, ifc.client_id, am)
#                                isGRE = False

                            # We do not currently parse sliver-type off of nodes to validate that
                            break
                    if not found:
                        self.logger.warn("GRE link '%s' has unknown interface_ref '%s' - assuming it is OK", link.id, ifc.client_id)
                if isGRE:
                    self.logger.debug("Link '%s' is GRE", link.id)

        # Extra: ensure endpoints are xen for link type egre, openvz or rawpc for gre

        return isGRE

    def mustCallSCS(self, requestRSpecObject):
        '''Does this request actually require stitching?
        Check: >=1 link in main body with >= 2 diff component_manager
        names and no shared_vlan extension and no non-VLAN link_type
        '''
        needSCS = False
        # Make sure links explicitly lists all its aggregates, so this test is valid
        if requestRSpecObject:
            for link in requestRSpecObject.links:
                self.ensureLinkListsAMs(link, requestRSpecObject)

        if requestRSpecObject:
            for link in requestRSpecObject.links:
                if len(link.aggregates) > 1 and not link.hasSharedVlan and link.typeName == link.VLAN_LINK_TYPE:
                    # Ensure this link has 2 well formed property elements with explicity capacities
                    self.addCapacityOneLink(link)
                    self.logger.debug("Requested link '%s' is stitching", link.id)

                    # Links that are ExoGENI only use ExoGENI stitching, not the SCS
                    # So only if the link includes anything non-ExoGENI, we use the SCS
                    egOnly = True
                    for am in link.aggregates:
                        # I wish I could do am.isEG but we don't get that info until later.
                        # Hack!
                        if 'exogeni' not in am.urn:
                            needSCS = True
                            egOnly = False
                            break

                    if egOnly:
                        self.logger.debug("Link '%s' is only ExoGENI, so can use ExoGENI stitching.", link.id)
                        if needSCS:
                            self.logger.debug("But we already decided we need the SCS.")
                        elif self.opts.noEGStitching and not needSCS:
                            self.logger.info("Using GENI stitching instead of ExoGENI stitching")
                            needSCS = True

                    # FIXME: If the link includes the openflow rspec extension marking a desire to make the link
                    # be OF controlled, then use the SCS and GENI stitching?

            # FIXME: Can we be robust to malformed requests, and stop and warn the user?
                # EG the link has 2+ interface_ref elements that are on 2+ nodes belonging to 2+ AMs?
                # Currently the parser only saves the IRefs on Links - no attempt to link to Nodes
                # And for Nodes, we don't even look at the Interface sub-elements

        return needSCS

    def callSCS(self, sliceurn, requestDOM, existingAggs):
        '''Construct SCS args, call the SCS service'''

        requestString, scsOptions = self.constructSCSArgs(requestDOM, existingAggs)
        existingAggs = None # Clear to note we are done
        self.scsService.result = None # Avoid any unexpected issues

        self.logger.debug("Calling SCS with options %s", scsOptions)
        if self.opts.savedSCSResults:
            self.logger.debug("** Not actually calling SCS, using results from '%s'", self.opts.savedSCSResults)
        try:
            scsResponse = self.scsService.ComputePath(sliceurn, requestString, scsOptions, self.opts.savedSCSResults)
        except StitchingError as e:
            self.logger.debug("Error from slice computation service: %s", e)
            raise 
        except Exception as e:
            # FIXME: If SCS used dossl then that might handle many of these errors.
            # Alternatively, the SCS could handle these itself.
            excName = e.__class__.__name__
            strE = str(e)
            if strE == '':
                strE = excName
            elif strE == "''":
                strE = "%s: %s" % (excName, strE)
            if strE.startswith('BadStatusLine'):
                # Did you call scs with http when https was expected?
                url = self.opts.scsURL.lower()
                if '8443' in url and not url.startswith('https'):
                    strE = "Bad SCS URL: Use https for a SCS requiring SSL (running on port 8443). (%s)" % strE
            elif 'unknown protocol' in strE:
                url = self.opts.scsURL.lower()
                if url.startswith('https'):
                    strE = "Bad SCS URL: Try using http not https. (%s)" % strE
            elif '404 Not Found' in strE:
                strE = 'Bad SCS URL (%s): %s' % (self.opts.scsURL, strE)
            elif 'Name or service not known' in strE:
                strE = 'Bad SCS host (%s): %s' % (self.opts.scsURL, strE)
            elif 'alert unknown ca' in strE:
                try:
                    certObj = gid.GID(filename=self.framework.cert)
                    certiss = certObj.get_issuer()
                    certsubj = certObj.get_urn()
                    self.logger.debug("SCS gave exception: %s", strE)
                    strE = "SCS does not trust the CA (%s) that signed your (%s) user certificate! Use an account at another clearinghouse or find another SCS server." % (certiss, certsubj)
                except:
                    strE = 'SCS does not trust your certificate. (%s)' % strE
            self.logger.error("Exception from slice computation service: %s", strE)
            import traceback
            self.logger.debug("%s", traceback.format_exc())
            raise StitchingError("SCS gave error: %s" % strE)

        self.logger.debug("SCS successfully returned.");

        if self.opts.debug:
            scsresfile = prependFilePrefix(self.opts.fileDir, "scs-result.json")
            self.logger.debug("Writing SCS result JSON to %s" % scsresfile)
            with open (scsresfile, 'w') as file:
                file.write(stripBlankLines(str(json.dumps(self.scsService.result, encoding='ascii', cls=DateTimeAwareJSONEncoder))))

        self.scsService.result = None # Clear memory/state
        return scsResponse

    def constructSCSArgs(self, requestDOM, existingAggs=None):
        '''Build and return the string rspec request and options arguments'''
        # return requestString and options

        options = {}
        # options is a struct

        # Supply the SCS option that requests the
        # '##all_paths_merged##' path in the workflow.
        # Doing so forces SCS to detect cross path workflow loops for
        # us.
        # Note that in omnilib/stitch/workflow we ignore that "path"
        # currently, and construct our own workflow
        options[scs.GENI_PATHS_MERGED_TAG] = True

        # To exclude a hop, add a geni_routing_profile struct
        # This in turn should have a struct per path whose name is the path name
        # Each shuld have a hop_exclusion_list array, containing the names of hops
        # If you append '=<VLANRange>' to the hop URN, that means to exclude
        # that set of VLANs from consideration on that hop, but don't entirely exclude
        # the hop.

#        exclude = "urn:publicid:IDN+instageni.gpolab.bbn.com+interface+procurve2:5.24=3747-3748"
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

        profile = {}
        if existingAggs and len(existingAggs) > 0:
            for agg in existingAggs:
                for hop in agg.hops:
                    if hop.excludeFromSCS or (hop.vlans_unavailable and len(hop.vlans_unavailable) > 0):
                        # get path and ensure a pathStruct object
                        path = hop._path.id
                        if profile.has_key(path):
                            pathStruct = profile[path]
                        else:
                            pathStruct = {}

                        # Get hop_exclusion_list
                        if pathStruct.has_key(scs.HOP_EXCLUSION_TAG):
                            excludes = pathStruct[scs.HOP_EXCLUSION_TAG]
                        else:
                            excludes = []

                        # get hop URN
                        urn = hop.urn

                        # Add to the excludes list
                        if hop.excludeFromSCS:
                            excludes.append(urn)
                        elif hop.vlans_unavailable and len(hop.vlans_unavailable) > 0:
                            excludes.append(urn + "=" + str(hop.vlans_unavailable))

                        # Put the new objects in the struct
                        pathStruct[scs.HOP_EXCLUSION_TAG] = excludes
                        profile[path] = pathStruct

        # Exclude any hops given as an option from _all_ hops
        links = None
        if (self.opts.excludehop and len(self.opts.excludehop) > 0) or (self.opts.includehop and len(self.opts.includehop) > 0) or \
                (self.opts.includehoponpath and len(self.opts.includehoponpath) > 0):
            links = requestDOM.getElementsByTagName(defs.LINK_TAG)
        if links and len(links) > 0:
            if not self.opts.excludehop:
                self.opts.excludehop = []
            if not self.opts.includehop:
                self.opts.includehop = []
            if not self.opts.includehoponpath:
                self.opts.includehoponpath= []
            self.logger.debug("Got links and option to exclude hops: %s, include hops: %s, include hops on paths: %s", self.opts.excludehop, self.opts.includehop, self.opts.includehoponpath)
            for exclude in self.opts.excludehop:
                # For each path
                for link in links:
                    path = link.getAttribute(Link.CLIENT_ID_TAG)
                    path = str(path).strip()
                    if profile.has_key(path):
                        pathStruct = profile[path]
                    else:
                        pathStruct = {}

                    # Get hop_exclusion_list
                    if pathStruct.has_key(scs.HOP_EXCLUSION_TAG):
                        excludes = pathStruct[scs.HOP_EXCLUSION_TAG]
                    else:
                        excludes = []

                    excludes.append(exclude)
                    self.logger.debug("Excluding %s from path %s", exclude, path)

                    # Put the new objects in the struct
                    pathStruct[scs.HOP_EXCLUSION_TAG] = excludes
                    profile[path] = pathStruct

            for include in self.opts.includehop:
                # For each path
                for link in links:
                    path = link.getAttribute(Link.CLIENT_ID_TAG)
                    path = str(path).strip()
                    if profile.has_key(path):
                        pathStruct = profile[path]
                    else:
                        pathStruct = {}

                    # Get hop_inclusion_list
                    if pathStruct.has_key(scs.HOP_INCLUSION_TAG):
                        includes = pathStruct[scs.HOP_INCLUSION_TAG]
                    else:
                        includes = []

                    includes.append(include)
                    self.logger.debug("Including %s on path %s", include, path)

                    # Put the new objects in the struct
                    pathStruct[scs.HOP_INCLUSION_TAG] = includes
                    profile[path] = pathStruct

            for (includehop, includepath) in self.opts.includehoponpath:
                # For each path
                for link in links:
                    path = link.getAttribute(Link.CLIENT_ID_TAG)
                    path = str(path).strip()
                    if not path.lower() == includepath.lower():
                        continue
                    if profile.has_key(path):
                        pathStruct = profile[path]
                    else:
                        pathStruct = {}

                    # Get hop_inclusion_list
                    if pathStruct.has_key(scs.HOP_INCLUSION_TAG):
                        includes = pathStruct[scs.HOP_INCLUSION_TAG]
                    else:
                        includes = []

                    includes.append(includehop)
                    self.logger.debug("Including %s on path %s", includehop, path)

                    # Put the new objects in the struct
                    pathStruct[scs.HOP_INCLUSION_TAG] = includes
                    profile[path] = pathStruct

        if profile != {}:
            options[scs.GENI_PROFILE_TAG] = profile
        self.logger.debug("Sending SCS options %s", options)

        try:
            xmlreq = requestDOM.toprettyxml(encoding="utf-8")
        except Exception, xe:
            self.logger.debug("Failed to XMLify requestDOM for sending to SCS: %s", xe)
            self._raise_omni_error("Malformed request RSpec: %s" % xe)

        return xmlreq, options
        
    def parseSCSResponse(self, scsResponse):

        expandedRSpec = scsResponse.rspec()

        if self.opts.debug or self.opts.fakeModeDir or self.logger.isEnabledFor(logging.DEBUG):

            if isRSpecStitchingSchemaV2(expandedRSpec):
                self.logger.debug("SCS RSpec uses v2 stitching schema")

            # Write the RSpec the SCS gave us to a file
            header = "<!-- SCS expanded stitching request for:\n\tSlice: %s\n -->" % (self.slicename)
            if expandedRSpec and is_rspec_string( expandedRSpec, None, None, logger=self.logger ):
                content = stripBlankLines(string.replace(expandedRSpec, "\\n", '\n'))
            else:
                content = "<!-- No valid RSpec returned. -->"
                if expandedRSpec is not None:
                    content += "\n<!-- \n" + expandedRSpec + "\n -->"

        if self.opts.debug or self.opts.fakeModeDir:
            # Set -o to ensure this goes to a file, not logger or stdout
            opts_copy = copy.deepcopy(self.opts)
            opts_copy.output = True
            scsreplfile = prependFilePrefix(self.opts.fileDir, Aggregate.FAKEMODESCSFILENAME)
            handler_utils._printResults(opts_copy, self.logger, header, \
                                            content, \
                                            scsreplfile)

            # In debug mode, keep copies of old SCS expanded requests
            if self.opts.debug:
                handler_utils._printResults(opts_copy, self.logger, header, content, scsreplfile + str(self.scsCalls))

            self.logger.debug("Wrote SCS expanded RSpec to %s", \
                                  scsreplfile)

        # A debugging block: print out the VLAN tag the SCS picked for each hop, independent of objects
        if self.logger.isEnabledFor(logging.DEBUG):
            start = 0
            while True:
                if not content.find("<link id=", start) >= start:
                    break
                hopIdStart = content.find('<link id=', start) + len('<link id=') + 1
                hopIdEnd = content.find(">", hopIdStart)-1
                # Print the link ID
                hop = content[hopIdStart:hopIdEnd]
                # find suggestedVLANRange
                suggestedStart = content.find("suggestedVLANRange>", hopIdEnd) + len("suggestedVLANRange>")
                suggestedEnd = content.find("</suggested", suggestedStart)
                suggested = content[suggestedStart:suggestedEnd]
                # find vlanRangeAvailability
                availStart = content.find("vlanRangeAvailability>", hopIdEnd) + len("vlanRangeAvailability>")
                availEnd = content.find("</vlanRange", availStart)
                avail = content[availStart:availEnd]
                # print that
                self.logger.debug("SCS gave hop %s suggested VLAN %s, avail: '%s'", hop, suggested, avail)
                start = suggestedEnd

       # parseRequest
        parsed_rspec = self.rspecParser.parse(expandedRSpec)
#        self.logger.debug("Parsed SCS expanded RSpec of type %r",
#                          type(parsed_rspec))

        # parseWorkflow
        workflow = scsResponse.workflow_data()
        scsResponse = None # once workflow extracted, done with that object

        # Dump the formatted workflow at debug level
        import pprint
        pp = pprint.PrettyPrinter(indent=2)
        self.logger.debug("SCS workflow:\n" + pp.pformat(workflow))

        workflow_parser = WorkflowParser(self.logger)

        # Parse the workflow, creating Path/Hop/etc objects
        # In the process, fill in a tree of which hops depend on which,
        # and which AMs depend on which
        # Also mark each hop with what hop it imports VLANs from,
        # And check for AM dependency loops
        workflow_parser.parse(workflow, parsed_rspec)

        # FIXME: Check SCS output consistency in a subroutine:
          # In each path: An AM with 1 hop must either _have_ dependencies or _be_ a dependency
          # All AMs must be listed in workflow data at least once per path they are in

        return parsed_rspec, workflow_parser

    def ensureOneExoSM(self):
        '''If 2 AMs in ams_to_process are ExoGENI and share a path and no noEG Stitching, ensure we use the ExoSM. If 2 AMs use the ExoSM URL, combine them into a single AM.'''
        if len(self.ams_to_process) < 2:
            return
        exoSMCount = 0
        exoSMs = []
        nonExoSMs = []
        egAMCount = 0
        egAMs = []
        for am in self.ams_to_process:
            if am.isExoSM:
                egAMCount += 1
                exoSMCount += 1
                exoSMs.append(am)
                self.logger.debug("%s is ExoSM", am)
            else:
                nonExoSMs.append(am)
                if am.isEG:
                    egAMs.append(am)
                    egAMCount += 1

        if egAMCount == 0:
            return

        if egAMCount > 1:
            self.logger.debug("Request includes more than one ExoGENI AM.")
            # If there is a stitched link between 2 EG AMs and no noEGStitching, then we
            # must change each to be the ExoSM so we use EG stitching for those AMs / links.
            # If there is no stitched link between the 2 EG AMs or the user specified noEGStitching,
            # then we do not change them to be the ExoSM.

            if self.opts.noEGStitching:
                self.logger.debug("Requested no EG stitching. Will edit requests to let this work later")
                # And do not force the AMs to be the ExoSM
            else:
                self.logger.debug("Will use EG stitching where applicable. Must go through the ExoSM.")
                if self.opts.noExoSM:
                    # We want to use EG stitching (default), but user asked for noExoSM.
                    # I think that means do not force AMs to be the ExoSM
                    self.logger.debug("Requested noExoSM. So not changing EG AMs to be the ExoSM. So using GENI stitching.")
                else:
                    for anEGAM in egAMs:
                        # Only make this AM the ExoSM if it has a link to another EG AM
                        # so that EG stitching applies.

                        # Note: If we get here we said use EG stitching
                        # So we may not have called the SCS (check self.isStitching)
                        # So we may have no paths from the workflow
                        # But also that would mean GENI Stitching is not an option

                        if not self.opts.useExoSM and self.isStitching:
                            # FIXME: If isStitching we still don't have paths for any EG only links.
                            # And we said we want to use EG stitching but didn't say use the ExoSM everywhere.
                            # So the goal here is to only change selected EG AMs into the ExoSM - only
                            # those EG AMs that have a link so we need EG stitching and need the ExoSM.
                            # HOWEVER, EG links are not (necessarily) in the paths,
                            # So the code looking at paths is (likely) wrong.
                            # The question is whether the SCS gives paths using GENI that I want to ignore.
                            # If so, then I need to be careful - here, or earlier.
                            # If not, then this should be fine (I think).

                            # So look at the main body links.
                            hasEGLink = False
                            for link in self.parsedSCSRSpec.links:
                                hasThisAgg = False
                                hasOtherEGAgg = False
                                hasNonEGAgg = False
                                for agg in link.aggregates:
                                    if anEGAM == agg:
                                        hasThisAgg=True
                                    elif agg.isEG:
                                        hasOtherEGAgg = True
                                    else:
                                        hasNonEGAgg = True
                                if hasThisAgg and hasOtherEGAgg:
                                    # then this AM has an EG link
                                    # Or FIXME, must it also not hasNonEGAgg?
                                    self.logger.debug("Looking at links, %s uses this %s and also another EG AM", link.id, anEGAM)
                                    if hasNonEGAgg:
                                        self.logger.debug("FIXME: Also has a non EG AM. Should this case avoid setting hasEGLink to true and use GENI stitching? Assuming so...")
                                    else:
                                        hasEGLink = True
                                        break

                            if not hasEGLink:
                                # We called the SCS, so we know paths
                                # And so using GENI stitching is an option still
                                for path in anEGAM.paths:
                                    self.logger.debug("Looking at %s on %s", path, anEGAM)
                                    for am in path.aggregates:
                                        self.logger.debug("Looking at %s on %s", am, path)
                                        if am != anEGAM and am.isEG:
                                            self.logger.debug("%s linked to other EG AM %s via %s", anEGAM, am, path)
                                            hasEGLink = True
                                            break
                                    if hasEGLink:
                                        break

                            if not hasEGLink:
                                self.logger.debug("%s is EG but has no links to EG AMs, so no need to make it the ExoSM", anEGAM)
                                continue
                            self.logger.debug("%s has a link that includes another EG AM. To use EG stitching between them, make this the ExoSM.", anEGAM)
                        elif not self.opts.useExoSM:
                            # If we didn't call the SCS, then we can't use GENI stitching, and so
                            # whether or not a path has another EG AM is irrelevant to whether we make the AM the ExoSM
                            # If we got here, they didn't set noExoSM.

                            # If useExoSM then do the change
                            # If there are links among EG AMs, then we need the change
                            # safest though is just to always do the change
                            # Else if an EG AM has a link
                            self.logger.debug("Not a GENI stitching request. Make this the EG ExoSM AM.")
                        else:
                            self.logger.debug("Asked to use the ExoSM for all EG AMs.")

                        # Make anEGAM the ExoSM
                        self.logger.debug("Making %s the ExoSM", anEGAM)
                        anEGAM.alt_url = anEGAM.url
                        anEGAM.url = defs.EXOSM_URL
                        anEGAM.isExoSM = True
                        anEGAM.nick = handler_utils._lookupAggNick(self, anEGAM.url)
                        exoSMCount += 1
                        exoSMs.append(anEGAM)
                        nonExoSMs.remove(anEGAM)

        if exoSMCount == 0:
            self.logger.debug("Not using ExoSM")
            return

        exoSM = None
        if exoSMCount > 0:
            exoSM = exoSMs[0]
            exoSMURN = handler_utils._lookupAggURNFromURLInNicknames(self.logger, self.config, defs.EXOSM_URL)
            # Ensure standard ExoSM URN is the URN and old URN is in urn_syns
            if exoSM.urn not in exoSM.urn_syns:
                exoSM.urn_syns.append(exoSM.urn)
            if exoSMURN != exoSM.urn:
                exoSM.urn = exoSMURN
            if exoSMURN not in exoSM.urn_syns:
                exoSM.urn_syns += Aggregate.urn_syns(exoSMURN)

        if exoSMCount < 2:
            self.logger.debug("Only %d ExoSMs", exoSMCount)
            return

        for am in exoSMs:
            if am == exoSM:
                continue
            self.logger.debug("Merge AM %s (%s, %s) into %s (%s, %s)", am.urn, am.url, am.alt_url, exoSM, exoSM.url, exoSM.alt_url)

            # Merge urn_syns
            if exoSM.urn != am.urn and am.urn not in exoSM.urn_syns:
                exoSM.urn_syns.append(am.urn)
            for urn in am.urn_syns:
                if urn not in exoSM.urn_syns:
                    exoSM.urn_syns.append(urn)

            # Merge _dependsOn
            if am in exoSM.dependsOn:
                exoSM._dependsOn.discard(am)
            if exoSM in am.dependsOn:
                am._dependsOn.discard(exoSM)
            exoSM._dependsOn.update(am._dependsOn)

            # If both am and exoSM are in dependsOn or isDependencyFor for some other AM, then remove am
            for am2 in self.ams_to_process:
                if am2 in exoSMs:
                    continue
                if am2 == am:
                    continue
                if am2 == exoSM:
                    continue
                if am in am2.dependsOn:
                    self.logger.debug("Removing dup ExoSM %s from %s.dependsOn", am, am2)
                    am2._dependsOn.discard(am)
                    if not exoSM in am2.dependsOn:
                        self.logger.debug("Adding real ExoSM %s to %s.dependsOn", exoSM, am2)
                        am2._dependsOn.add(exoSM)
                if am in am2.isDependencyFor:
                    self.logger.debug("Removing dup ExoSM %s from %s.isDependencyFor", am, am2)
                    am2.isDependencyFor.discard(am)
                    if not exosM in am2.isDependencyFor:
                        self.logger.debug("Adding real ExosM %s to %s.isDependencyFor", exoSM, am2)
                        am2.isDependencyFor.add(exoSM)

            # merge isDependencyFor
            if am in exoSM.isDependencyFor:
                exoSM.isDependencyFor.discard(am)
            if exoSM in am.isDependencyFor:
                am.isDependencyFor.discard(exoSM)
            exoSM.isDependencyFor.update(am.isDependencyFor)

            # merge _paths
            # Path has hops and aggregates 
            # Fix the list of aggregates to drop the aggregate being merged away
            # What happens when a path has same aggregate at 2 discontiguous hops?
            for path in am.paths:
                path._aggregates.remove(am)
                if not exoSM in path.aggregates:
                    path._aggregates.add(exoSM)
                if not path in exoSM.paths:
                    self.logger.debug("Merging in path %s", path)
                    exoSM._paths.add(path)

            # FIXME: What does it mean for the same path to be on both aggregates? What has to be merged?

            # merge _hops
            # Hop points back to aggregate. Presumably these pointers must be reset
            for hop in am.hops:
                hop._aggregate = exoSM
                if not hop in exoSM.hops:
                    self.logger.debug("Merging in hop %s", hop)
                    exoSM._hops.add(hop)

            # merge userRequested
            #  - If 1 was user requested and 1 was not, whole thing is user requested
            if am.userRequested:
                exoSM.userRequested = True

            # merge alt_url
            if exoSM.alt_url and handler_utils._extractURL(self.logger, exoSM.alt_url) == handler_utils._extractURL(self.logger, exoSM.url):
                if handler_utils._extractURL(self.logger, exoSM.alt_url) != handler_utils._extractURL(self.logger, am.url):
                    exoSM.alt_url = am.alt_url

        # ensure only one in cls.aggs
        newaggs = dict()
        for (key, agg) in Aggregate.aggs.items():
            if not (agg.isExoSM and agg != exoSM):
                newaggs[key] = agg
        Aggregate.aggs = newaggs

        nonExoSMs.append(exoSM)
        self.ams_to_process = nonExoSMs

    def add_am_info(self, aggs):
        '''Add extra information about the AMs to the Aggregate objects, like the API version'''
        options_copy = copy.deepcopy(self.opts)
        options_copy.debug = False
        options_copy.info = False

        aggsc = copy.copy(aggs)

        for agg in aggsc:
            # Don't do an aggregate twice
            if agg.urn in self.amURNsAddedInfo:
                continue
#            self.logger.debug("add_am_info looking at %s", agg)

            # Note which AMs were user requested
            if agg.urn in self.parsedUserRequest.amURNs:
                agg.userRequested = True
            else:
                for urn2 in agg.urn_syns:
                    if urn2 in self.parsedUserRequest.amURNs:
                        agg.userRequested = True

            # FIXME: Better way to detect this?
            if handler_utils._extractURL(self.logger, agg.url) in defs.EXOSM_URL:
                agg.isExoSM = True
#                self.logger.debug("%s is the ExoSM cause URL is %s", agg, agg.url)

            # EG AMs in particular have 2 URLs in some sense - ExoSM and local
            # So note the other one, since VMs are split between the 2
            for (amURN, amURL) in self.config['aggregate_nicknames'].values():
                if amURN.strip() in agg.urn_syns:
                    hadURL = handler_utils._extractURL(self.logger, agg.url)
                    newURL = handler_utils._extractURL(self.logger, amURL)
                    if hadURL != newURL and not hadURL in newURL and not newURL in hadURL and not newURL.strip == '':
                        agg.alt_url = amURL.strip()
                        break
#                    else:
#                        self.logger.debug("Not setting alt_url for %s. URL is %s, alt candidate was %s with URN %s", agg, hadURL, newURL, amURN)
#                elif "exogeni" in amURN and "exogeni" in agg.urn:
#                    self.logger.debug("Config had URN %s URL %s, but that URN didn't match our URN synonyms for %s", amURN, newURL, agg)

            if "exogeni" in agg.urn and not agg.alt_url:
#                self.logger.debug("No alt url for Orca AM %s (URL %s) with URN synonyms:", agg, agg.url)
#                for urn in agg.urn_syns:
#                    self.logger.debug("\t%s", urn)
                if not agg.isExoSM:
                    agg.alt_url = defs.EXOSM_URL

            # Try to get a URL from the CH? Do we want/need this
            # expense? This is a call to the CH....
            # Comment this out - takes too long, not clear
            # it is needed.
#            if not agg.alt_url:
#                fw_ams = dict()
#                try:
#                    fw_ams = self.framework.list_aggregates()
#                    for fw_am_urn in fw_ams.keys():
#                        if fw_am_urn and fw_am_urn.strip() in am.urn_syns and fw_ams[fw_am_urn].strip() != '':
#                            cand_url = fw_ams[fw_am_urn]
#                            if cand_url != am.url and not am.url in cand_url and not cand_url in am.url:
#                                am.alt_url = cand_url
#                                self.logger.debug("Found AM %s alternate URL from CH ListAggs: %s", am.urn, am.alt_url)
#                                break
#                except:
#                    pass

            if agg.isExoSM and agg.alt_url and self.opts.noExoSM:
                self.logger.warn("%s used ExoSM URL. Changing to %s", agg, agg.alt_url)
                amURL = agg.url
                agg.url = agg.alt_url
                agg.alt_url = amURL
                agg.isExoSM = False

# For using the test ION AM
#            if 'alpha.dragon' in agg.url:
#                agg.url =  'http://alpha.dragon.maxgigapop.net:12346/'

            # Use GetVersion to determine AM type, AM API versions spoken, etc
            if options_copy.warn:
                omniargs = ['--ForceUseGetVersionCache', '-a', agg.url, 'getversion']
            else:
                omniargs = ['--ForceUseGetVersionCache', '-o', '--warn', '-a', agg.url, 'getversion']

            try:
                self.logger.debug("Getting extra AM info from Omni for AM %s", agg)
                (text, version) = omni.call(omniargs, options_copy)
                aggurl = agg.url
                if isinstance (version, dict) and version.has_key(aggurl) and isinstance(version[aggurl], dict) \
                        and version[aggurl].has_key('value') and isinstance(version[aggurl]['value'], dict):
                    if version[aggurl]['value'].has_key('geni_am_type') and isinstance(version[aggurl]['value']['geni_am_type'], list):
                        if DCN_AM_TYPE in version[aggurl]['value']['geni_am_type']:
                            self.logger.debug("AM %s is DCN", agg)
                            agg.dcn = True
                        elif ORCA_AM_TYPE in version[aggurl]['value']['geni_am_type']:
                            self.logger.debug("AM %s is Orca", agg)
                            agg.isEG = True
                        elif PG_AM_TYPE in version[aggurl]['value']['geni_am_type']:
                            self.logger.debug("AM %s is ProtoGENI", agg)
                            agg.isPG = True
                        elif GRAM_AM_TYPE in version[aggurl]['value']['geni_am_type']:
                            self.logger.debug("AM %s is GRAM", agg)
                            agg.isGRAM = True
                    elif version[aggurl]['value'].has_key('geni_am_type') and ORCA_AM_TYPE in version[aggurl]['value']['geni_am_type']:
                            self.logger.debug("AM %s is Orca", agg)
                            agg.isEG = True
                    # This code block looks nice but doesn't work - the version object is not the full triple
#                    elif version[aggurl].has_key['code'] and isinstance(version[aggurl]['code'], dict) and \
#                            version[aggurl]['code'].has_key('am_type') and str(version[aggurl]['code']['am_type']).strip() != "":
#                        if version[aggurl]['code']['am_type'] == PG_AM_TYPE:
#                            self.logger.debug("AM %s is ProtoGENI", agg)
#                            agg.isPG = True
#                        elif version[aggurl]['code']['am_type'] == ORCA_AM_TYPE:
#                            self.logger.debug("AM %s is Orca", agg)
#                            agg.isEG = True
#                        elif version[aggurl]['code']['am_type'] == DCN_AM_TYPE:
#                            self.logger.debug("AM %s is DCN", agg)
#                            agg.dcn = True
                    if version[aggurl]['value'].has_key('geni_api_versions') and isinstance(version[aggurl]['value']['geni_api_versions'], dict):
                        maxVer = 1
                        hasV2 = False
                        v2url = None
                        for key in version[aggurl]['value']['geni_api_versions'].keys():
                            if int(key) == 2:
                                hasV2 = True
                                v2url = version[aggurl]['value']['geni_api_versions'][key]
                                # Ugh. Why was I changing the URL based on the Ad? Not needed, Omni does this.
                                # And if the AM says the current URL is the current opts.api_version OR the AM only lists 
                                # one URL, then changing the URL makes no sense. So if I later decide I need this
                                # for some reason, only do it if len(keys) > 1 and [value][geni_api] != opts.api_version
                                # Or was I trying to change to the 'canonical' URL for some reason?
#                                # Change the stored URL for this Agg to the URL the AM advertises if necessary
#                                if agg.url != version[aggurl]['value']['geni_api_versions'][key]:
#                                    agg.url = version[aggurl]['value']['geni_api_versions'][key]
                                # The reason to do this would be to
                                # avoid errors like:
#16:46:34 WARNING : Requested API version 2, but AM https://clemson-clemson-control-1.clemson.edu:5001 uses version 3. Same aggregate talks API v2 at a different URL: https://clemson-clemson-control-1.clemson.edu:5002
#                                if len(version[aggurl]['value']['geni_api_versions'].keys()) > 1 and \
#                                        agg.url != version[aggurl]['value']['geni_api_versions'][key]:
#                                    agg.url = version[aggurl]['value']['geni_api_versions'][key]
                            if int(key) > maxVer:
                                maxVer = int(key)

                        # This code is just to avoid ugly WARNs from Omni about changing URL to get the right API version.
                        # Added it for GRAM. But GRAM is manually fixed at the SCS now, so no need.
#                        if self.opts.api_version == 2 and hasV2 and agg.url != v2url:
#                            if agg.isEG and "orca/xmlrpc" in agg.url and "orca/geni" in v2url:
#                                # EGs ad lists the wrong v2 URL
#                                #self.logger.debug("Don't swap at EG with the wrong URL")
#                                pass
#                            else:
#                                self.logger.debug("%s: Swapping URL to v2 URL. Change from %s to %s", agg, agg.url, v2url)
#                                if agg.alt_url is None:
#                                    agg.alt_url = agg.url
#                                agg.url = v2url

                        # Stitcher doesn't really know how to parse
                        # APIv1 return structs
                        if maxVer == 1:
                            msg = "%s speaks only AM API v1 - not supported!" % agg
                            #self.logger.error(msg)
                            raise StitchingError(msg)
                        # Hack alert: v3 AM implementations don't work even if they exist
                        if not hasV2:
                            msg = "%s does not speak AM API v2 (max is V%d). APIv2 required!" % (agg, maxVer)
                            #self.logger.error(msg)
                            raise StitchingError(msg)
#                        if maxVer != 2:
#                            self.logger.debug("%s speaks AM API v%d, but sticking with v2", agg, maxVer)

#                        if self.opts.fakeModeDir:
#                            self.logger.warn("Testing v3 support")
#                            agg.api_version = 3
#                        agg.api_version = maxVer
                    if version[aggurl]['value'].has_key('GRAM_version'):
                        agg.isGRAM = True
                        self.logger.debug("AM %s is GRAM", agg)
                    if version[aggurl]['value'].has_key('foam_version') and 'oess' in agg.url:
                        agg.isOESS = True
                        self.logger.debug("AM %s is OESS", agg)
                    if version[aggurl]['value'].has_key('geni_request_rspec_versions') and \
                            isinstance(version[aggurl]['value']['geni_request_rspec_versions'], list):
                        for rVer in version[aggurl]['value']['geni_request_rspec_versions']:
                            if isinstance(rVer, dict) and rVer.has_key('type') and rVer.has_key('version') and \
                                    rVer.has_key('extensions') and rVer['type'].lower() == 'geni' and str(rVer['version']) == '3' and \
                                    isinstance(rVer['extensions'], list):
                                v2 = False
                                v1 = False
                                for ext in rVer['extensions']:
                                    if defs.STITCH_V1_BASE in ext:
                                        v1 = True
                                    if defs.STITCH_V2_BASE in ext:
                                        v2 = True
                                if v2:
                                    self.logger.debug("%s supports stitch schema v2", agg)
                                    agg.doesSchemaV2 = True
                                if not v1:
                                    self.logger.debug("%s does NOT say it supports stitch schema v1", agg)
                                    agg.doesSchemaV1 = False
                            # End of if block
                        # Done with loop over versions
                    if not agg.doesSchemaV2 and not agg.doesSchemaV1:
                        self.logger.debug("%s doesn't say whether it supports either stitching schema, so assume v1", agg)
                        agg.doesSchemaV1 = True
            except StitchingError, se:
                # FIXME: Return anything different for stitching error?
                # Do we want to return a geni triple struct?
                raise
            except Exception, e:
                self.logger.debug("Got error extracting extra AM info: %s", e)
                import traceback
                self.logger.debug(traceback.format_exc())
                pass
#            finally:
#                logging.disable(logging.NOTSET)

            if agg.isEG and self.opts.useExoSM and not agg.isExoSM:
                agg.alt_url = defs.EXOSM_URL
                self.logger.info("%s is an EG AM and user asked for ExoSM. Changing to %s", agg, agg.alt_url)
                amURL = agg.url
                agg.url = agg.alt_url
                agg.alt_url = amURL
                agg.isExoSM = True
                aggsc.append(agg)
                continue
#            else:
#                self.logger.debug("%s is EG: %s, alt_url: %s, isExo: %s", agg, agg.isEG, agg.alt_url, agg.isExoSM)

            # Save off the aggregate nickname if possible
            agg.nick = handler_utils._lookupAggNick(self, agg.url)

            if not agg.isEG and not agg.isGRAM and not agg.dcn and "protogeni/xmlrpc" in agg.url:
                agg.isPG = True

 #           self.logger.debug("Remembering done getting extra info for %s", agg)

            # Remember we got the extra info for this AM
            self.amURNsAddedInfo.append(agg.urn)
        # Done loop over aggs

    def dump_objects(self, rspec, aggs):
        '''Print out the hops, aggregates, and dependencies'''
        if rspec and rspec.stitching:
            stitching = rspec.stitching
            self.logger.debug( "\n===== Hops =====")
            for path in stitching.paths:
                self.logger.debug( "Path %s" % (path.id))
                for hop in path.hops:
                    self.logger.debug( "  Hop %s" % (hop))
                    if hop.globalId:
                        self.logger.debug( "    GlobalId: %s" % hop.globalId)
                    if hop._hop_link.isOF:
                        self.logger.debug( "    An Openflow controlled hop")
                        if hop._hop_link.controllerUrl:
                            self.logger.debug( "      Controller: %s", hop._hop_link.controllerUrl)
                        if hop._hop_link.ofAMUrl:
                            self.logger.debug( "      Openflow AM URL: %s", hop._hop_link.ofAMUrl)
                    if len(hop._hop_link.capabilities) > 0:
                        self.logger.debug( "    Capabilities: %s", hop._hop_link.capabilities)
                    # FIXME: don't use the private variable
                    self.logger.debug( "    VLAN Suggested (requested): %s" % (hop._hop_link.vlan_suggested_request))
                    self.logger.debug( "    VLAN Available Range (requested): %s" % (hop._hop_link.vlan_range_request))
                    if hop._hop_link.vlan_suggested_manifest:
                        self.logger.debug( "    VLAN Suggested (manifest): %s" % (hop._hop_link.vlan_suggested_manifest))
                    if hop._hop_link.vlan_range_manifest:
                        self.logger.debug( "    VLAN Available Range (manifest): %s" % (hop._hop_link.vlan_range_manifest))
                    if hop.vlans_unavailable and len(hop.vlans_unavailable) > 0:
                        self.logger.debug( "    VLANs found UN Available: %s" % hop.vlans_unavailable)
                    self.logger.debug( "    Import VLANs From: %s" % (hop.import_vlans_from))
                    deps = hop.dependsOn
                    if deps:
                        self.logger.debug( "    Dependencies:")
                        for h in deps:
                            self.logger.debug( "      Hop %s" % (h))

        if aggs and len(aggs) > 0:
            self.logger.debug( "\n===== Aggregates =====")
            for agg in aggs:
                self.logger.debug( "\nAggregate %s" % (agg))
                if agg.userRequested:
                    self.logger.debug("   (User requested)")
                else:
                    self.logger.debug("   (SCS added)")
                if agg.dcn:
                    self.logger.debug("   A DCN Aggregate")
                if agg.isPG:
                    self.logger.debug("   A ProtoGENI Aggregate")
                if agg.isGRAM:
                    self.logger.debug("   A GRAM Aggregate")
                if agg.isOESS:
                    self.logger.debug("   An OESS Aggregate")
                if agg.isEG:
                    self.logger.debug("   An Orca Aggregate")
                if agg.isExoSM:
                    self.logger.debug("   The ExoSM Aggregate")
                if agg.alt_url:
                    self.logger.debug("   Alternate URL: %s", agg.alt_url)
                self.logger.debug("   Using AM API version %d", agg.api_version)
                if agg.manifestDom:
                    self.logger.debug("   Have a reservation here (%s)!", agg.url)
                if not agg.doesSchemaV1:
                    self.logger.debug("   Does NOT support Stitch Schema V1")
                if agg.doesSchemaV2:
                    self.logger.debug("   Supports Stitch Schema V2")
                if agg.pgLogUrl:
                    self.logger.debug("   PG Log URL %s", agg.pgLogUrl)
                if agg.sliverExpirations is not None:
                    if len(agg.sliverExpirations) > 1:
                        # More than 1 distinct sliver expiration found
                        # Sort and take first
                        outputstr = agg.sliverExpirations[0].isoformat()
                        self.logger.debug("   Resources here expire at %d different times. First expiration is %s UTC" % (len(agg.sliverExpirations), outputstr))
                    elif len(agg.sliverExpirations) == 1:
                        outputstr = agg.sliverExpirations[0].isoformat()
                        self.logger.debug("   Resources here expire at %s UTC" % (outputstr))
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

    def combineManifests(self, ams, lastAM):
        '''Produce a single combined manifest string from the reservation results at each aggregate.
        lastAM is the last reservation that completed, for use as a template.'''
        # Nodes and hops come from the AM that owns those
        # interface_ref elements on link elements also come from the responsible AM
        # Top level link element is effectively arbitrary, but with comments on what other AMs said
        lastDom = None
        if lastAM is None:
            self.logger.debug("Combined manifest will start from expanded request RSpec")
            lastDom = self.parsedSCSRSpec.dom
            # Change that dom to be a manifest RSpec
            # for each attribute on the dom root node, change "request" to "manifest"
            doc_root = lastDom.documentElement
            for i in range(doc_root.attributes.length):
                attr = doc_root.attributes.item(i)
                doingChange = False
                ind = attr.value.find('request')
                if ind > -1:
                    doingChange = True
                while ind > -1:
                    attr.value = attr.value[:ind] + 'manifest' + attr.value[ind+len('request'):]
                    ind = attr.value.find('request', ind+len('request'))
                if doingChange:
                    self.logger.debug("Reset original request rspec attr %s='%s'", attr.name, attr.value)
#            self.logger.debug(stripBlankLines(lastDom.toprettyxml(encoding="utf-8")))
        else:
            lastDom = lastAM.manifestDom
        combinedManifestDom = combineManifestRSpecs(ams, lastDom)

        try:
            manString = combinedManifestDom.toprettyxml(encoding="utf-8")
        except Exception, xe:
            self.logger.debug("Failed to XMLify combined Manifest RSpec: %s", xe)
            self._raise_omni_error("Malformed combined manifest RSpec: %s" % xe)

        # set rspec to be UTF-8
        if isinstance(manString, unicode):
            manString = manString.encode('utf-8')
            self.logger.debug("Combined manifest RSpec was unicode")

        # FIXME
        # For fake mode this is really a request, but should be treating it as a manifest
        # For now, SCS gives us stitchSchemaV2 stuff, so rspeclint fails
        try:
            if self.opts.fakeModeDir:
                self.confirmGoodRSpec(manString, rspec_schema.REQUEST, False)
            else:
                self.confirmGoodRSpec(manString, rspec_schema.MANIFEST, False)
        except OmniError, oe:
            # If there is an EG AM in the mix, then we expect an error
            # like:
#Manifest RSpec file did not contain a Manifest RSpec (wrong type or schema)
            hasEG = False
            for am in ams:
                if am.isEG:
                    hasEG = True
                    break
            if hasEG and "Manifest RSpec file did not contain a Manifest RSpec (wrong type or schema)" in str(oe):
                self.logger.debug("EG AM meant manifest does not validate: %s", oe)
        except Exception, e:
            self.logger.error(e)

        return stripBlankLines(manString)

    def saveAggregateList(self, sliceurn):
        '''Save a file with the list of aggregates used. Used as input
        to later stitcher calls, e.g. to delete from all AMs.'''
        # URN to hrn
        (slicehrn, stype) = urn_to_clean_hrn(sliceurn)
        if not slicehrn or slicehrn.strip() == '' or not stype=='slice':
            self.logger.warn("Couldn't parse slice HRN from URN %s",
                             sliceurn)
            return
        # ./$slicehrn-amlist.txt
        fname = prependFilePrefix(self.opts.fileDir, "~/.gcf/%s-amlist.txt" % slicehrn)
        if not self.ams_to_process or len(self.ams_to_process) == 0:
            self.logger.debug("No AMs in AM list to process, so not creating amlist file")
            return

        listdir = os.path.abspath(os.path.expanduser(os.path.dirname(fname)))
        if not os.path.exists(listdir):
            try:
                os.makedirs(listdir)
            except Exception, e:
                self.logger.warn("Failed to create dir '%s' to save list of used AMs: %s", listdir, e)

        # URL,URN
        with open (fname, 'w') as file:
            file.write("# AM List for multi-AM slice %s\n" % sliceurn)
            file.write("# Slice allocated at %s\n" % datetime.datetime.utcnow().isoformat())
            for am in self.ams_to_process:
                file.write("%s,%s\n" % (am.url, am.urn) )
                # Include am.userRequested? am.api_version? len(am._hops)?
#                file.write("%s,%s,%s,%d,%d\n" % (am.url, am.urn, am.userRequested,
#                           am.api_version, len(am._hops)))


    def addAggregateOptions(self, args):
        '''Read a file with a list of aggregates, adding those as -a
        options. Allows stitcher to delete from all AMs. Note that
        extra aggregate options are added only if no -a options are
        already supplied.'''
        # Find slice name from args[1]
        if not args or len(args) < 2:
            self.logger.debug("Cannot find slice name")
            return
        slicename = args[1]

        # get slice URN
        # Get slice URN from name
        try:
            sliceurn = self.framework.slice_name_to_urn(slicename)
        except Exception, e:
            self.logger.warn("Could not determine slice URN from name %s: %s", slicename, e)
            return

        if not sliceurn or sliceurn.strip() == '':
            self.logger.warn("Could not determine slice URN from name %s", slicename)
            return

        # get slice HRN
        (slicehrn, stype) = urn_to_clean_hrn(sliceurn)
        if not slicehrn or slicehrn.strip() == '' or not stype=='slice':
            self.logger.warn("Couldn't parse slice HRN from URN %s",
                             sliceurn)
            return

        # ./$slicehrn-amlist.txt
        fname = prependFilePrefix(self.opts.fileDir, "~/.gcf/%s-amlist.txt" % slicehrn)

        # look to see if $slicehrn-amlist.txt exists
        if not os.path.exists(fname) or not os.path.getsize(fname) > 0:
            self.logger.debug("File of AMs for slice %s not found or empty: %s", slicename, fname)
            return

        self.logger.info("Reading slice %s aggregates from file %s", slicename, fname)

        self.opts.ensure_value('aggregate', [])
        addOptions = True
        if len(self.opts.aggregate) > 0:
            addOptions = False
        with open(fname, 'r') as file:
        # For each line:
            for line in file:
                line = line.strip()
                # Skip if starts with # or is empty
                if line == '' or line.startswith('#'):
                    continue
                # split on ,
                (url,urn) = line.split(',')
#                (url,urn,userRequested,api_version,numHops) = line.split(',')
                url = url.strip()
                # If first looks like a URL, log
                if not url == '':
                    # add -a option
                    # Note this next doesn't avoid the dup of a nickname
                    if not url in self.opts.aggregate:
                        if addOptions:
                            self.logger.debug("Adding aggregate option %s (%s)", url, urn)
                            self.opts.aggregate.append(url)
                        else:
                            self.logger.debug("NOTE not adding aggregate %s", url)

    def addExpiresAttribute(self, rspecDOM, sliceexp):
        '''Set the expires attribute on the rspec to the slice
        expiration. DCN AMs used to not support renew, but this is no
        longer true, so this should not be necessary. Additionally,
        some AMs treat this as a strict requirement and if this
        exceeds local policy for maximum sliver, the request will fail.'''
        if not rspecDOM:
            return
        if not sliceexp or str(sliceexp).strip() == "":
            return

        rspecs = rspecDOM.getElementsByTagName(defs.RSPEC_TAG)
        if not rspecs or len(rspecs) < 1:
            return

        if rspecs[0].hasAttribute(defs.EXPIRES_ATTRIBUTE):
            self.logger.debug("Not over-riding expires %s", rspecs[0].getAttribute(defs.EXPIRES_ATTRIBUTE))
            return

        # Some PG based AMs cannot handle fractional seconds, and
        # erroneously treat expires as in local time. So (a) avoid
        # microseconds, and (b) explicitly note this is in UTC.
        # So this is sliceexp.isoformat() except without the
        # microseconds and with the Z. Note that PG requires exactly
        # this format.
        rspecs[0].setAttribute(defs.EXPIRES_ATTRIBUTE, sliceexp.strftime('%Y-%m-%dT%H:%M:%SZ'))
        self.logger.debug("Added expires %s", rspecs[0].getAttribute(defs.EXPIRES_ATTRIBUTE))
 
    def getUnboundNode(self):
        '''Set self.isMultiAM by looking at Node component_manager_id fields. Also return at most 1 node without such a field.'''
        # If any node is unbound, then all AMs will try to allocate it.
        amURNs = []
        unboundNode = None
        for node in self.parsedUserRequest.nodes:
            if node.amURN is None:
                if self.opts.devmode:
                    # Note that SCS likely will fail with something like:
                    # code 65535: std::exception
                    self.logger.warn("Node %s is unbound in request", node.id)
                else:
                    self.logger.debug("Node %s is unbound in request", node.id)
                    unboundNode = node.id
            else:
#                self.logger.debug("Node %s is on AM %s", node.id, node.amURN)
                if node.amURN not in amURNs:
                    amURNs.append(node.amURN)
        self.logger.debug("Request RSpec binds nodes to %d AMs", len(amURNs))
        if len(amURNs) > 1:
            self.isMultiAM = True
        return unboundNode

    def confirmSafeRequest(self):
        '''Confirm this request is not asking for a loop. Bad things should
        not be allowed, dangerous things should get a warning.'''

        # FIXME FIXME - what other checks go here?

        # Ticket #570: to stitch multiple VMs at same PG AM on same VLAN, ensure component IDs are eth0-3 on interfaces
        # to force it to go through hardware

        # for link in self.parsedUserRequest.links:
        # Only care about stitching links with more than 2 interfaces
        #  if len(link.aggregates) > 1 and not link.hasSharedVlan and link.typeName == link.VLAN_LINK_TYPE and len(link.interfaces) > 2:
        #   ifcsByNode = {}
        #   for ifc in link.interfaces:
        #       theNode = None
        #       for node in self.parseUserRequest.nodes:
        #            if ifc in node.interface_ids
        #               theNode = node
        #               break
        #       if theNode is None:
        #            error
        #       ifcsByNode[theNode] = [ifc]
        #   for node in ifcsByNode.keys():
        #       if len(ifcsByNode[node] < 2:
        #           continue
        #       agg = Aggregate.find(theNode.amURN)
        #       if not agg.isPG:
        #           self.logger.warn("%s is not a PG AM and may not support stitching multiple Nodes on same link", agg)
        #           continue
        #       # Now we have a PG node with >2 interfaces on the same stitched link
        #       # Find the node in the rspec XML
        #       # find the interface
        #       # Add the component_id if it is not already there
        #          # FIXME: If some ifc on the node has the component_id, then I need to avoid using the same ones!
        #          #      Maybe for now, if any ifc has a component_id in the original rspec, skip this node?
# FIXME: we call rspec.getLinkEditedDom() to build what we send to the SCS. So the object / dom there needs to put the 
# component_id in in the right way. So probably I need to do this via objects.
# So: objects.py class Node: store the interface_ref as an object that has both client_id (the id) and component_id.
# Make that class have a toDOM method that writes in the correct interface_ref sub-elements as needed, and call that method
# from clas RSpec.getLinkEditedDom

            # ethcnt = 0
            # For each ifc
            #   If ifc in the current link, then add component_id attribute using ethcnt, and then increment

        pass

    def saveAggregateState(self, oldAggs, newAggs):
        '''Save state from old aggregates for use with new aggregates from later SCS call'''
        for agg in newAggs:
            for oldAgg in oldAggs:
                # FIXME: Correct to compare urn_syns too?
                if agg.urn == oldAgg.urn or agg.urn in oldAgg.urn_syns or oldAgg.urn in agg.urn_syns:
                    for hop in agg.hops:
                        for oldHop in oldAgg.hops:
                            if hop.urn == oldHop.urn:
                                if oldHop.excludeFromSCS:
                                    self.logger.warn("%s had been marked to exclude from SCS, but we got it again", oldHop)
                                hop.vlans_unavailable = hop.vlans_unavailable.union(oldHop.vlans_unavailable)
                                break

                    # FIXME: agg.allocateTries?
                    agg.dcn = oldAgg.dcn
                    agg.isOESS = oldAgg.isOESS
                    agg.isGRAM = oldAgg.isGRAM
                    agg.isPG = oldAgg.isPG
                    agg.isEG = oldAgg.isEG
                    agg.isExoSM = oldAgg.isExoSM
                    agg.userRequested = oldAgg.userRequested
                    agg.alt_url = oldAgg.alt_url
                    agg.api_version = oldAgg.api_version
                    agg.nick = oldAgg.nick
                    agg.doesSchemaV1 = oldAgg.doesSchemaV1
                    agg.doesSchemaV2 = oldAgg.doesSchemaV2
                    agg.slicecred = oldAgg.slicecred

                    # FIXME: correct?
                    agg.url = oldAgg.url
                    agg.urn_syns = copy.deepcopy(oldAgg.urn_syns)
                    break

    # If we said this rspec needs a fake endpoint, add it here - so the SCS and other stuff
    # doesn't try to do anything with it
    def addFakeNode(self):
        fakeNode = self.parsedSCSRSpec.dom.createElement(defs.NODE_TAG)
        fakeInterface = self.parsedSCSRSpec.dom.createElement("interface")
        fakeInterface.setAttribute(Node.CLIENT_ID_TAG, "fake:if0")
        fakeNode.setAttribute(Node.CLIENT_ID_TAG, "fake")
        fakeNode.setAttribute(Node.COMPONENT_MANAGER_ID_TAG, "urn:publicid:IDN+fake+authority+am")
        fakeCM = self.parsedSCSRSpec.dom.createElement(Link.COMPONENT_MANAGER_TAG)
        fakeCM.setAttribute(Link.NAME_TAG, "urn:publicid:IDN+fake+authority+am")
        fakeNode.appendChild(fakeInterface)
        fakeiRef = self.parsedSCSRSpec.dom.createElement(Link.INTERFACE_REF_TAG)
        fakeiRef.setAttribute(Node.CLIENT_ID_TAG, "fake:if0")
        # Find the rspec element from parsedSCSRSpec.dom
        rspecs = self.parsedSCSRSpec.dom.getElementsByTagName(defs.RSPEC_TAG)
        if rspecs and len(rspecs):
            rspec = rspecs[0]
            # Add a node to the dom
            self.logger.info("Adding fake Node endpoint")
            rspec.appendChild(fakeNode)

            # Also find all links and add an interface_ref
            for child in rspec.childNodes:
                if child.localName == defs.LINK_TAG:
                    linkName = child.getAttribute(Node.CLIENT_ID_TAG)
                    ifcCount = 0
                    ifcAMCount = 0 # Num AMs the interfaces are at
                    propCount = 0
                    ifc1Name = None
                    ifcAuths = []
                    for c2 in child.childNodes:
                        if c2.localName == Link.INTERFACE_REF_TAG:
                            ifcCount += 1
                            ifc1Name = c2.getAttribute(Node.CLIENT_ID_TAG)
                            for node in self.parsedSCSRSpec.nodes:
                                if ifc1Name in node.interface_ids:
                                    ifcAuth = node.amURN
                                    if not ifcAuth in ifcAuths:
                                        ifcAuths.append(ifcAuth)
                                        ifcAMCount += 1
                                    break
                        if c2.localName == Link.PROPERTY_TAG:
                            propCount += 1
                    if ifcAMCount == 1:
                        self.logger.info("Adding fake interface_ref endpoint on link %s", linkName)
                        child.appendChild(fakeiRef)
                        child.appendChild(fakeCM)
                        if propCount == 0:
                            # Add the 2 property elements
                            self.logger.debug("Adding property tags to link %s to fake node", linkName)
                            sP = self.parsedSCSRSpec.dom.createElement(Link.PROPERTY_TAG)
                            sP.setAttribute(LinkProperty.SOURCE_TAG, ifc1Name)
                            sP.setAttribute(LinkProperty.DEST_TAG, "fake:if0")
                            sP.setAttribute(LinkProperty.CAPACITY_TAG, str(self.opts.defaultCapacity))
                            dP = self.parsedSCSRSpec.dom.createElement(Link.PROPERTY_TAG)
                            dP.setAttribute(LinkProperty.DEST_TAG, ifc1Name)
                            dP.setAttribute(LinkProperty.SOURCE_TAG, "fake:if0")
                            dP.setAttribute(LinkProperty.CAPACITY_TAG, str(self.opts.defaultCapacity))
                            child.appendChild(sP)
                            child.appendChild(dP)
                        else:
                            self.logger.debug("Link %s had only interfaces at 1 am (%d of them), so added the fake interface - but it has %d properties already?", linkName, ifcCount, propCount)
                    else:
                        self.logger.debug("Not adding fake endpoint to link %s with %d interfaces at %d AMs", linkName, ifcCount, ifcAMCount)
#        self.logger.debug("\n" + self.parsedSCSRSpec.dom.toxml())
