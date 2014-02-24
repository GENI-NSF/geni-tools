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
'''Objects representing RSpecs, Aggregates, Hops, Paths. Includes the main workhorse
functions for doing allocationg and deletions at aggregates.'''

from __future__ import absolute_import

import copy
import datetime
import dateutil
import json
import logging
import os
import random
import string
import time
from xml.dom.minidom import parseString, Node as XMLNode

from . import defs
from .GENIObject import *
from .VLANRange import *
from .utils import *

from ... import oscript as omni

from ..util import naiveUTC
from ..util.handler_utils import _construct_output_filename, _writeRSpec, _getRSpecOutput, _printResults
from ..util.dossl import is_busy_reply
from ..util.omnierror import OmniError, AMAPIError
from ...geni.util import rspec_schema, rspec_util

# Seconds to pause between calls to a DCN AM (ie ION)
DCN_AM_RETRY_INTERVAL_SECS = 10 * 60 # Xi and Chad say ION routers take a long time to reset

# FIXME: As in defs, check use of getAttribute vs getAttributeNS and localName vs nodeName
# FIXME: Merge RSpec element/attribute name constants into defs

class Path(GENIObject):
    '''Path in stitching aka a Link'''
    __ID__ = validateText

    # XML tag constants
    ID_TAG = 'id'
    HOP_TAG = 'hop'
    GLOBAL_ID_TAG = 'globalId'

    @classmethod
    def fromDOM(cls, element):
        """Parse a stitching path from a DOM element."""
        # FIXME: Do we need getAttributeNS?
        id = element.getAttribute(cls.ID_TAG)
        path = Path(id)
        for child in element.childNodes:
            if child.localName == cls.HOP_TAG:
                hop = Hop.fromDOM(child)
                hop.path = path
                hop.idx = len(path.hops)
                path.hops.append(hop)
            elif child.localName == cls.GLOBAL_ID_TAG:
                globID = str(child.firstChild.nodeValue).strip()
                path.globalId = globId

        for hop in path.hops:
            next_hop = path.find_hop(hop._next_hop)
            if next_hop:
                hop._next_hop = next_hop
        return path

    def __init__(self, id):
        super(Path, self).__init__()
        self.id = id
        self._hops = []
        self._aggregates = set()
        self.globalId = None

    def __str__(self):
        return "<Path %s with %d hops across %d AMs>" % (self.id, len(self._hops), len(self._aggregates))

    @property
    def hops(self):
        return self._hops

    @property
    def aggregates(self):
        return self._aggregates

    @hops.setter
    def hops(self, hopList):
        self._setListProp('hops', hopList, Hop)

    def find_hop(self, hop_urn):
        for hop in self.hops:
            if hop.urn == hop_urn:
                return hop
        # Fail -- no hop matched the given URN
        return None

    def find_hop_idx(self, hop_idx):
        '''Find a hop in this path by its index, or None'''
        for hop in self.hops:
            if hop.idx == hop_idx:
                return hop
        # Fail -- no hop matched the given index
        return None

    def editChangesIntoDom(self, pathDomNode):
        '''Edit any changes made in this element into the given DomNode'''
        # Note the parent RSpec element's dom is not touched, unless the given node is from that document
        # Here we just find all the Hops and let them do stuff

        # Incoming node should be the node for this path
        nodeId = pathDomNode.getAttribute(self.ID_TAG)
        if nodeId != self.id:
            raise StitchingError("Path %s given Dom node with different Id: %s" % (self, nodeId))

        # For each of this path's hops, find the appropriate Dom element, and let Hop edit itself in
        domHops = pathDomNode.getElementsByTagName(self.HOP_TAG)
        for hop in self.hops:
            domHopNode = None
            if domHops:
                for hopNode in domHops:
                    hopNodeId = hopNode.getAttribute(self.ID_TAG)
                    if hopNodeId == hop._id:
                        domHopNode = hopNode
                        break
            if domHopNode is None:
                # Couldn't find this Hop in the dom
                # FIXME: Create it?
                raise StitchingError("Couldn't find Hop %s in given Dom node to edit in changes" % hop)
            hop.editChangesIntoDom(domHopNode)
        # End of loop over hops
        return

class Stitching(GENIObject):
    __simpleProps__ = [ ['last_update_time', str] ] #, ['path', Path[]]]

    def __init__(self, last_update_time=None, paths=None):
        super(Stitching, self).__init__()
        self.last_update_time = str(last_update_time)
        self.paths = paths

    # Arg of link_id: this is the client_id of the main body link, or the path ID
    def find_path(self, link_id):
        if self.paths:
            for path in self.paths:
                if path.id == link_id:
                    return path
        else:
            return None

class Aggregate(object):
    '''Aggregate'''

    # Hold all instances. One instance per URN.
    aggs = dict()

    # FIXME: Move these constants up higher
    MAX_TRIES = 10 # Max times to try allocating here. Compare with allocateTries
    BUSY_MAX_TRIES = 5 # dossl does 3
    BUSY_POLL_INTERVAL_SEC = 10 # dossl does 10
    SLIVERSTATUS_MAX_TRIES = 10
    SLIVERSTATUS_POLL_INTERVAL_SEC = 30 # Xi says 10secs is short if ION is busy; per ticket 1045, even 20 may be too short
    PAUSE_FOR_AM_TO_FREE_RESOURCES_SECS = 30
    # See DCN_AM_RETRY_INTERVAL_SECS for the DCN AM equiv of PAUSE_FOR_AM_TO_FREE...
    PAUSE_FOR_DCN_AM_TO_FREE_RESOURCES_SECS = DCN_AM_RETRY_INTERVAL_SECS # Xi and Chad say ION routers take a long time to reset
    MAX_AGG_NEW_VLAN_TRIES = 50 # Max times to locally pick a new VLAN
    MAX_DCN_AGG_NEW_VLAN_TRIES = 3 # Max times to locally pick a new VLAN

    # Constant name of SCS expanded request (for use here and elsewhere)
    FAKEMODESCSFILENAME = '/tmp/stitching-scs-expanded-request.xml'

    # Directory to store request rspecs - must be universally writable
    REQ_RSPEC_DIR = '/tmp'

    @classmethod
    def find(cls, urn):
        if not urn in cls.aggs:
            syns = Aggregate.urn_syns(urn)
            found = False
            for urn2 in syns:
                if urn2 in cls.aggs:
                    found = True
                    urn = urn2
                    break
            if not found:
                m = cls(urn)
                cls.aggs[urn] = m
        return cls.aggs[urn]

    @classmethod
    def all_aggregates(cls):
        return cls.aggs.values()

    @classmethod
    def clearCache(cls):
        cls.aggs = dict()

    @classmethod
    def urn_syns_helper(cls, urn, urn_syns):
        urn_syns.append(urn)

        import re
        urn2 = urn[:-2] + 'cm'
        if urn2 == urn:
            urn2 = urn[:-2] + 'am'
        urn_syns.append(urn2)

        urn2 = re.sub("vmsite", "Net", urn)
        if urn2 == urn:
            urn2 = re.sub("Net", "vmsite", urn)
        urn_syns.append(urn2)

        urn3 = urn2[:-2] + 'cm'
        if urn3 == urn2:
            urn3 = urn2[:-2] + 'am'
        urn_syns.append(urn3)
        return urn_syns

    # Produce a list of URN synonyms for the AM
    # IE don't get caught by cm/am differences
    # Also, EG AMs have both a vmsite and a Net bit that could be in component_manager_ids
    @classmethod
    def urn_syns(cls, urn):
        urn_syns = list()
        urn = urn.strip()
        wasUni = False
        if isinstance(urn, unicode):
            wasUni = True

        urn_syns = cls.urn_syns_helper(urn, urn_syns)

        if wasUni:
            urn = str(urn)
        else:
            urn = unicode(urn)
        urn_syns = cls.urn_syns_helper(urn, urn_syns)

        return urn_syns

    def __init__(self, urn, url=None):
        self.urn = urn

        # Produce a list of URN synonyms for the AM
        # IE don't get caught by cm/am differences
        # Also, EG AMs have both a vmsite and a Net bit that could be in component_manager_ids
        self.urn_syns = Aggregate.urn_syns(urn)

        self.url = url
        self.alt_url = None # IE the rack URL vs the ExoSM URL
        self.nick = None
        self.inProcess = False
        self.completed = False
        self.userRequested = False
        self._hops = set()
        self._paths = set()
        self._dependsOn = set() # of Aggregate objects
        self.rspecfileName = None
        self.isDependencyFor = set() # AMs that depend on this: for ripple down deletes
        self.logger = logging.getLogger('stitch.Aggregate')
        # Note these are sort of RSpecs but not RSpec objects, to avoid a loop
        self.requestDom = None # the DOM as constructed to submit in request to this AM
        self.manifestDom = None # the DOM as we got back from the AM
        self.api_version = 2 # Set from stitchhandler.parseSCSResponse
        self.dcn = False # DCN AMs require waiting for sliverstatus to say ready before the manifest is legit
        self.isEG = False # Handle EG AMs differently - manifests are different
        self.isExoSM = False # Maybe we need to handle the ExoSM differently too?
        self.isPG = False
        # reservation tries since last call to SCS
        self.allocateTries = 0 # see MAX_TRIES
        self.localPickNewVlanTries = 1 # see MAX_AGG_NEW_VLAN_TRIES

        self.pgLogUrl = None # For PG AMs, any log url returned by Omni that we could capture

    def __str__(self):
        if self.nick:
            if self.logger.isEnabledFor(logging.DEBUG):
                return "<Aggregate %s: %s>" % (self.nick, self.url)
            else:
                return "<Aggregate %s>" % (self.nick)
        else:
            if self.logger.isEnabledFor(logging.DEBUG):
                return "<Aggregate %s: %s>" % (self.urn, self.url)
            else:
                return "<Aggregate %s>" % (self.urn)

    def __repr__(self):
        if self.nick:
            return "Aggregate(%r)" % (self.nick)
        else:
            return "Aggregate(%r)" % (self.urn)

    @property
    def hops(self):
        return list(self._hops)

    @property
    def paths(self):
        return list(self._paths)

    @property
    def dependsOn(self):
        return list(self._dependsOn)

    def add_hop(self, hop):
        self._hops.add(hop)
#        self.logger.debug("%s now has %d hops", self, len(self._hops))

    def add_path(self, path):
        self._paths.add(path)

    def add_dependency(self, agg):
        self._dependsOn.add(agg)

    def add_agg_that_dependsOnThis(self, agg):
        self.isDependencyFor.add(agg)

    @property
    def dependencies_complete(self):
        """Dependencies are complete if there are no dependencies
        or if all dependencies are completed.
        """
        return (not self._dependsOn
                or reduce(lambda a, b: a and b,
                          [agg.completed for agg in self._dependsOn]))

    @property
    def ready(self):
        return not self.completed and not self.inProcess and self.dependencies_complete

    def allocate(self, opts, slicename, rspecDom, scsCallCount):
        '''Main workhorse function. Build the request rspec for this AM,
        and make the reservation. On error, delete and signal failure.'''

        if self.inProcess:
            self.logger.warn("Called allocate on AM already in process: %s", self)
            return
        # Confirm all dependencies still done
        if not self.dependencies_complete:
            self.logger.warn("Cannot allocate at %s: dependencies not ready", self)
            return
        if self.completed:
            self.logger.warn("Called allocate on AM already marked complete: %s", self)
            return

        # FIXME: If we are quitting, return (important when threaded)

        # Import VLANs, noting if we need to delete an old reservation at this AM first
        mustDelete, alreadyDone = self.copyVLANsAndDetectRedo()

        if mustDelete:
            self.logger.info("Must delete previous reservation for %s", self)
            alreadyDone = False
            self.deleteReservation(opts, slicename)

            # FIXME: Need to sleep so AM has time to put those resources back in the pool
            # But really should do this on the AMs own thread to avoid blocking everything else
            sleepSecs = self.PAUSE_FOR_AM_TO_FREE_RESOURCES_SECS 
            if self.dcn:
                sleepSecs = self.PAUSE_FOR_DCN_AM_TO_FREE_RESOURCES_SECS
            self.logger.info("Pause %d seconds to let aggregate free resources...", sleepSecs)
            time.sleep(sleepSecs)
        # end of block to delete a previous reservation

        if alreadyDone:
            # we did a previous upstream delete and worked our way down to here, but this AM is OK
            self.completed = True
            self.logger.info("%s had previous result we didn't need to redo. Done", self)
            return

        # Check that all hops have reasonable vlan inputs
        for hop in self.hops:
            if not hop._hop_link.vlan_suggested_request <= hop._hop_link.vlan_range_request:
                raise StitchingError("%s hop %s suggested %s not in avail %s" % (self, hop, hop._hop_link.vlan_suggested_request, hop._hop_link.vlan_range_request))

        # Check that if a hop has the same URN as another on this AM, that it has a different VLAN tag
        tagByURN = dict()
        hopByURN = dict()
        for hop in self.hops:
            if hop.urn in tagByURN.keys():
                tags = tagByURN[hop.urn]
                if hop._hop_link.vlan_suggested_request in tags:
                    # This could happen due to an apparent SCS bug (#1100). I suppose I could treat this as VLANUnavailable?
                    raise StitchingError("%s %s has request tag %s that is already in use by %s" % (self, hop, hop._hop_link.vlan_suggested_request, hopByURN[hop.urn][tags.index(hop._hop_link.vlan_suggested_request)]))
                else:
                    self.logger.debug("%s %s has same URN as other hop(s) on this AM %s. But this hop uses request tag %s, that hop(s) used %s", self, hop, str(hopByURN[hop.urn][0]), hop._hop_link.vlan_suggested_request, str(tagByURN[hop.urn][0]))
                    tagByURN[hop.urn].append(hop._hop_link.vlan_suggested_request)
                    hopByURN[hop.urn].append(hop)
            else:
                tagByURN[hop.urn] = list()
                tagByURN[hop.urn].append(hop._hop_link.vlan_suggested_request)
                hopByURN[hop.urn] = list()
                hopByURN[hop.urn].append(hop)

            # Ticket #355: If this is PG/IG, then complain if any hop on a different path uses the same VLAN tag
            if self.isPG:
                for hop2 in self.hops:
                    if hop2.path.id != hop.path.id and hop2._hop_link.vlan_suggested_request == hop._hop_link.vlan_suggested_request:
                        raise StitchingError("%s is a ProtoGENI AM and %s is requesting the same tag (%s) as a hop on a different path %s" % \
                                                 (self, hop, hop._hop_link.vlan_suggested_request, hop2))

        if self.allocateTries == self.MAX_TRIES:
            self.logger.warn("Doing allocate on %s for %dth time!", self, self.allocateTries)

        self.completed = False

        # Mark AM is busy
        self.inProcess = True

        # Generate the new request Dom
        self.requestDom = self.getEditedRSpecDom(rspecDom)

        # Get the manifest for this AM
        # result is a manifest RSpec string. Errors wouuld be raised
        # This method handles fakeMode, retrying on BUSY, polling SliverStatus for DCN AMs,
        # VLAN_UNAVAILABLE errors, other errors
        manifestString = self.doReservation(opts, slicename, scsCallCount)

        # Save it on the Agg
        try:
            self.manifestDom = parseString(manifestString)

            # FIXME: Do this? We get the same info on the combined manifest already
            # Put the AM reservation info in a comment on the per AM manifest
#            commentText = "AM %s at %s reservation using APIv%d. " % (self.urn, self.url, self.api_version)
#            if self.pgLogUrl:
#                commentText = commentText + "PG Log URL: %s" % self.pgLogUrl
#            logComment = self.manifestDom.createComment(commentText)
#            first_non_comment_element = None
#            for elt in dom_self.manifestDom.childNodes:
#                if elt.nodeType != Node.COMMENT_NODE:
#                    first_non_comment_element = elt;
#                    break
#                self.manifestDom.insertBefore(comment_element, first_non_comment_element)
        except Exception, e:
            self.logger.error("Failed to parse %s reservation result as DOM XML RSpec: %s", self, e)
            raise StitchingError("%s manifest rspec not parsable: %s" % (self, e))

        hadSuggestedNotRequest = False

        # Parse out the VLANs we got, saving them away on the HopLinks
        # Note and complain if we didn't get VLANs or the VLAN we got is not what we requested
        for hop in self.hops:
            # 7/12/13: FIXME: EG Manifests reset the Hop ID. So you have to look for the link URN
            if self.isEG:
                self.logger.debug("Parsing EG manifest with special method")
                range_suggested = self.getEGVLANRangeSuggested(self.manifestDom, hop._hop_link.urn, hop.path.id)
            else:
                range_suggested = self.getVLANRangeSuggested(self.manifestDom, hop._id, hop.path.id)

            pathGlobalId = None

            if range_suggested[0] is not None:
                pathGlobalId = str(range_suggested[0]).strip()
            rangeValue = str(range_suggested[1]).strip()
            suggestedValue = str(range_suggested[2]).strip()
            if pathGlobalId and pathGlobalId is not None and pathGlobalId != "None" and pathGlobalId != '':
                if hop.path.globalId and hop.path.globalId is not None and hop.path.globalId != "None" and hop.path.globalId != pathGlobalId:
                    self.logger.warn("Changing Path %s global ID from %s to %s", hop.path.id, hop.path.globalId, pathGlobalId)
                hop.path.globalId = pathGlobalId

            if not suggestedValue:
                self.logger.error("Didn't find suggested value in rspec for hop %s", hop)
                # Treat as error? Or as vlan unavailable? FIXME
                self.handleVlanUnavailable("reservation", ("No suggested value element on hop %s" % hop), hop, True)
            elif suggestedValue in ('null', 'None', 'any'):
                self.logger.error("Hop %s Suggested invalid: %s", hop, suggestedValue)
                # Treat as error? Or as vlan unavailable? FIXME
                self.handleVlanUnavailable("reservation", ("Invalid suggested value %s on hop %s" % (suggestedValue, hop)), hop, True)
            else:
                suggestedObject = VLANRange.fromString(suggestedValue)
            # If these fail and others worked, this is malformed
            if not rangeValue:
                self.logger.error("Didn't find vlanAvailRange element for hop %s", hop)
                raise StitchingError("%s didn't have a vlanAvailRange in manifest" % hop)
            elif rangeValue in ('null', 'None', 'any'):
                self.logger.error("Hop %s availRange invalid: %s", hop, rangeValue)
                raise StitchingError("%s had invalid availVlanRange in manifest: %s" % (hop, rangeValue))
            else:
                rangeObject = VLANRange.fromString(rangeValue)

            # If got here the manifest values are OK - save them away
            self.logger.debug("Hop %s manifest had suggested %s, avail %s", hop, suggestedValue, rangeValue)
            hop._hop_link.vlan_suggested_manifest = suggestedObject
            hop._hop_link.vlan_range_manifest = rangeObject

            if not suggestedObject <= hop._hop_link.vlan_suggested_request:
                self.logger.error("%s gave VLAN %s for hop %s which is not in our request %s", self, suggestedObject, hop, hop._hop_link.vlan_suggested_request)
                # This is sug != requested case
                self.handleSuggestedVLANNotRequest(opts, slicename)
                hadSuggestedNotRequest = True

        # Mark AM not busy
        self.inProcess = False

        self.logger.info("Allocation at %s complete.", self)

        if not hadSuggestedNotRequest:
            # mark self complete
            self.completed = True

    def copyVLANsAndDetectRedo(self):
        '''Copy VLANs to this AMs hops from previous manifests. Check if we already had manifests.
        If so, but the inputs are incompatible, then mark this to be deleted. If so, but the
        inputs are compatible, then an AM upstream was redone, but this is alreadydone.'''

        hadPreviousManifest = self.manifestDom != None
        mustDelete = False # Do we have old reservation to delete?
        alreadyDone = hadPreviousManifest # Did we already complete this AM? (and this is just a recheck)
        for hop in self.hops:
            if not hop.import_vlans:
                if not hop._hop_link.vlan_suggested_manifest:
                    alreadyDone = False
#                    self.logger.debug("%s hop %s does not import vlans, and has no manifest yet. So AM is not done.", self, hop)
                continue

            # Calculate the new suggested/avail for this hop
            if not hop.import_vlans_from:
                self.logger.warn("%s imports vlans but has no import from?", hop)
                continue

            new_suggested = hop._hop_link.vlan_suggested_request or VLANRange.fromString("any")
            if hop.import_vlans_from._hop_link.vlan_suggested_manifest:
                new_suggested = hop.import_vlans_from._hop_link.vlan_suggested_manifest.copy()
            else:
                self.logger.warn("%s's import_from %s had no suggestedVLAN manifest", hop, hop.import_vlans_from)
                raise StitchingError("%s's import_from %s had no suggestedVLAN manifest" % (hop, hop.import_vlans_from))

            # If we've noted VLANs we already tried that failed (cause of later failures
            # or cause the AM wouldn't give the tag), then be sure to exclude those
            # from new_suggested - that is, if new_suggested would be in that set, then we have
            # an error - gracefully exit, either to SCS excluding this hop or to user
            if new_suggested <= hop.vlans_unavailable:
                # FIXME: use handleVlanUnavailable? Is that right?
                self.handleVlanUnavailable("reserve", "Calculated new_suggested for %s of %s is in set of VLANs we know won't work" % (hop, new_suggested))
#                raise StitchingError("%s picked new_suggested %s that is in the set of VLANs that we know won't work: %s" % (hop, new_suggested, hop.vlans_unavailable))

            int1 = VLANRange.fromString("any")
            int2 = VLANRange.fromString("any")
            if hop.import_vlans_from._hop_link.vlan_range_manifest:
                # FIXME: vlan_range_manifest on EG AMs is junk and we should use the vlan_range_request maybe? Or maybe the Ad?
                if hop.import_vlans_from._aggregate.isEG:
                    self.logger.debug("Hop %s imports from %s on an EG AM. It lists manifest vlan_range %s, request vlan_range %s, request vlan suggested %s", hop, hop.import_vlans_from, hop.import_vlans_from._hop_link.vlan_range_manifest, hop.import_vlans_from._hop_link.vlan_range_request, hop.import_vlans_from._hop_link.vlan_suggested_request)
#                    int1 = hop.import_vlans_from._hop_link.vlan_range_request
#                else:
#                    int1 = hop.import_vlans_from._hop_link.vlan_range_manifest
                int1 = hop.import_vlans_from._hop_link.vlan_range_manifest
            else:
                self.logger.warn("%s's import_from %s had no avail VLAN manifest", hop, hop.import_vlans_from)
            if hop._hop_link.vlan_range_request:
                int2 = hop._hop_link.vlan_range_request
            else:
                self.logger.warn("%s had no avail VLAN request", hop, hop.import_vlans_from)
            new_avail = int1 & int2

            # FIXME: Limit new_avail to exclude any request_manifest on any other hops with same URN? Or should that have been done in handleVU?

            # If we've noted VLANs we already tried that failed (cause of later failures
            # or cause the AM wouldn't give the tag), then be sure to exclude those
            # from new_avail. And if new_avail is now empty, that is
            # an error - gracefully exit, either to SCS excluding this hop or to user
            new_avail2 = new_avail - hop.vlans_unavailable
            if new_avail2 != new_avail:
                self.logger.debug("%s computed vlanRange %s smaller due to excluding known unavailable VLANs. Was otherwise %s", hop, new_avail2, new_avail)
                new_avail = new_avail2
            if len(new_avail) == 0:
                # FIXME: Do I go to SCS? treat as VLAN Unavailable? I don't think this should happen.
                # But if it does, it probably means I need to exclude this AM at least?
                self.logger.error("%s computed availVlanRange is empty" % hop)
                raise StitchingError("%s computed availVlanRange is empty" % hop)

            if not new_suggested <= new_avail:
                # We're somehow asking for something not in the avail range we're asking for.
                self.logger.error("%s Calculated suggested %s not in available range %s", hop, new_suggested, new_avail)
                raise StitchingError("%s could not be processed: calculated a suggested VLAN of %s that is not in the calculated available range %s" % (hop, new_suggested, new_avail))

            # If we have a previous manifest, we might be done or might need to delete a previous reservation
            if hop._hop_link.vlan_suggested_manifest:
                if not hadPreviousManifest:
                    raise StitchingError("%s had no previous manifest, but its hop %s did" % (self, hop))
                if hop._hop_link.vlan_suggested_request != new_suggested:
                    # If we already have a result but used different input, then this result is suspect. Redo.
                    hop._hop_link.vlan_suggested_request = new_suggested
                    # if however the previous suggested_manifest == new_suggested, then maybe this is OK?
                    if hop._hop_link.vlan_suggested_manifest == new_suggested:
                        self.logger.info("%s VLAN suggested request %s != new request %s, but had manifest that is the new request, so leave it alone", hop, hop._hop_link.vlan_suggested_request, new_suggested)
                    else:
                        self.logger.info("Redo %s: had previous different suggested VLAN for hop %s (old request/manifest %s != new request %s)", self, hop, hop._hop_link.vlan_suggested_request, new_suggested)
                        mustDelete = True
                        alreadyDone = False
                else:
                    self.logger.debug("%s had previous manifest and used same suggested VLAN for hop %s (%s) - no need to redo", self, hop, hop._hop_link.vlan_suggested_request)
                    # So for this hop at least, we don't need to redo this AM
            else:
                alreadyDone = False
                # No previous result
                if hadPreviousManifest:
                    raise StitchingError("%s had a previous manifest but hop %s did not" % (self, hop))
                if hop._hop_link.vlan_suggested_request != new_suggested:
                    # FIXME: Comment out this log statement?
                    self.logger.debug("%s changing VLAN suggested from %s to %s", hop, hop._hop_link.vlan_suggested_request, new_suggested)
                    hop._hop_link.vlan_suggested_request = new_suggested
                else:
                    # FIXME: Comment out this log statement?
                    self.logger.debug("%s already had VLAN suggested %s", hop, hop._hop_link.vlan_suggested_request)

            # Now check the avail range as we did for suggested
            if hop._hop_link.vlan_range_manifest:
                if not hadPreviousManifest:
                    self.logger.error("%s had no previous manifest, but its hop %s did", self, hop)
                if hop._hop_link.vlan_range_request != new_avail:
                    # If we already have a result but used different input, then this result is suspect. Redo?
                    self.logger.debug("%s had previous manifest and used different avail VLAN range for hop %s (old request %s != new request %s)", self, hop, hop._hop_link.vlan_range_request, new_avail)
                    if hop._hop_link.vlan_suggested_manifest and hop._hop_link.vlan_suggested_manifest not in new_avail:
                        # new avail doesn't contain the previous manifest suggested. So new avail would have precluded
                        # using the suggested we picked before. So we have to redo
                        mustDelete = True
                        alreadyDone = False
                        self.logger.warn("%s previous availRange %s not same as new, and previous manifest suggested %s not in new avail %s - redo this AM", hop, hop._hop_link.vlan_range_request, hop._hop_link.vlan_suggested_manifest, new_avail)
                    else:
                        # what we picked before still works, so leave it alone
                        self.logger.info("%s had manifest suggested %s that works with new/different availRange %s - don't redo", hop, hop._hop_link.vlan_suggested_manifest, new_avail)
                        #self.logger.debug("%s had avail range manifest %s, and previous avail range request (%s) != new (%s), but previous suggested manifest %s is in the new avail range, so it is still good - no redo", hop, hop._hop_link.vlan_range_manifest, hop._hop_link.vlan_range_request, new_avail, hop._hop_link.vlan_suggested_manifest)

                    # Either way, record what we want the new request to be, so later if we redo we use the right thing
                    hop._hop_link.vlan_range_request = new_avail
                else:
                    # FIXME: move to debug?
                    self.logger.info("%s had previous manifest range and used same avail VLAN range request %s - no redo", hop, hop._hop_link.vlan_range_request)
            else:
                alreadydone = False
                # No previous result
                if hadPreviousManifest:
                    raise StitchingError("%s had a previous manifest but hop %s did not" % (self, hop))
                if hop._hop_link.vlan_range_request != new_avail:
                    self.logger.debug("%s changing avail VLAN from %s to %s", hop, hop._hop_link.vlan_range_request, new_avail)
                    hop._hop_link.vlan_range_request = new_avail
                else:
                    self.logger.debug("%s already had avail VLAN %s", hop, hop._hop_link.vlan_range_request)
        # End of loop over hops to copy VLAN tags over and see if this is a redo or we need to delete
        return mustDelete, alreadyDone

    def getEditedRSpecDom(self, originalRSpec):
        # For each path on this AM, get that Path to write whatever it thinks necessary into a
        # deep clone of the incoming RSpec Dom
        requestRSpecDom = originalRSpec.cloneNode(True)

        # This block no longer necessary. If stitchhandler sets the
        # expires attribute, then this is true. Otherwise, don't do
        # this, as it's a strange thing for the tool to know AM sliver
        # lifetime policies.
#        # If this is a PG AM and the rspec has an expires attribute
#        # and the value is > 7200min/5days from now, reset expires to
#        # 7200min/5 days from now -- PG sets a max for slivers of
#        # 7200, and fails your request if it is more
#        # symptom is this error from createsliver: 
#        # "expiration is greater then the maximum number of minutes 7200"
#        # FIXME: Need a check for isPG to do this!
#        if self.urn == "urn:publicid:IDN+emulab.net+authority+cm":
#            rspecs = requestRSpecDom.getElementsByTagName(defs.RSPEC_TAG)
#            if rspecs and len(rspecs) > 0 and rspecs[0].hasAttribute(defs.EXPIRES_ATTRIBUTE):
#                expires = rspecs[0].getAttribute(defs.EXPIRES_ATTRIBUTE)
#                expiresDT = naiveUTC(dateutil.parser.parse(expires)) # produce a datetime
#                now = naiveUTC(datetime.datetime.utcnow())
#                pgmax = datetime.timedelta(minutes=(7200-20)) # allow 20 minutes slop time to get the request RSpec to the AM
#                if expiresDT - now > pgmax:
##                    self.logger.warn("Now: %s, expiresDT: %s", now, expiresDT)
#                    newExpiresDT = now + pgmax
#                    # Some PG based AMs cannot handle fractional seconds, and
#                    # erroneously treat expires as in local time. So (a) avoid
#                    # microseconds, and (b) explicitly note this is in UTC.
#                    # So this is .isoformat() except without the
#                    # microseconds and with the Z
#                    newExpires = naiveUTC(newExpiresDT).strftime('%Y-%m-%dT%H:%M:%SZ')
#                    self.logger.warn("Slivers at PG Utah may not be requested initially for > 5 days. PG Utah slivers " +
#                                     "will expire earlier than at other aggregates - requested expiration being reset from %s to %s", expires, newExpires)
#                    rspecs[0].setAttribute(defs.EXPIRES_ATTRIBUTE, newExpires)

        stitchNodes = requestRSpecDom.getElementsByTagName(defs.STITCHING_TAG)
        if stitchNodes and len(stitchNodes) > 0:
            stitchNode = stitchNodes[0]
        else:
            raise StitchingError("Couldn't find stitching element in rspec for %s request" % self)

        domPaths = stitchNode.getElementsByTagName(defs.PATH_TAG)
#        domPaths = stitchNode.getElementsByTagNameNS(rspec_schema.STITCH_SCHEMA_V1, defs.PATH_TAG)
#        domPaths = stitchNode.getElementsByTagNameNS(rspec_schema.STITCH_SCHEMA_V2, defs.PATH_TAG)
        for path in self.paths:
            #self.logger.debug("Looking for node for path %s", path)
            domNode = None
            if domPaths:
                for pathNode in domPaths:
                    pathNodeId = pathNode.getAttribute(Path.ID_TAG)
                    if pathNodeId == path.id:
                        domNode = pathNode
                        #self.logger.debug("Found node for path %s", path.id)
                        break
            if domNode is None:
                raise StitchingError("Couldn't find Path %s in stitching element of RSpec for %s request" % (path, self))
            #self.logger.debug("Doing path.editChanges for path %s", path.id)
            path.editChangesIntoDom(domNode)
        return requestRSpecDom

    # For a given hop, extract from the Manifest DOM a tuple (pathGlobalId, vlanRangeAvailability, suggestedVLANRange)
    def getVLANRangeSuggested(self, manifest, hop_id, path_id):
        vlan_range_availability = None
        suggested_vlan_range = None

        rspec_node = None
        stitching_node = None
        path_node = None
        this_path_id = ""
        hop_node = None
        link_node = None
        link_id = ""
        this_hop_id = ""
        scd_node = None
        scsi_node = None
        scsil2_node = None
        path_globalId = None

        # FIXME: Call once for all hops

        for child in manifest.childNodes:
            if child.nodeType == XMLNode.ELEMENT_NODE and \
                    child.localName == defs.RSPEC_TAG:
                rspec_node = child
                break

        if rspec_node:
            for child in rspec_node.childNodes:
                if child.nodeType == XMLNode.ELEMENT_NODE and \
                        child.localName == defs.STITCHING_TAG:
                    stitching_node = child
                    break
        else:
            raise StitchingError("%s: No rspec element in manifest" % self)

        if stitching_node:
            for child in stitching_node.childNodes:
                if child.nodeType == XMLNode.ELEMENT_NODE and \
                        child.localName == defs.PATH_TAG:
                    this_path_id = child.getAttribute(Path.ID_TAG)
                    if this_path_id == path_id:
                        path_node = child
                        break
        else:
            raise StitchingError("%s: No stitching element in manifest" % self)

        if path_node:
#            self.logger.debug("%s Found rspec manifest stitching path %s (id %s)" % (self, path_node, this_path_id))
            for child in path_node.childNodes:
                if child.nodeType == XMLNode.ELEMENT_NODE and \
                        child.localName == Path.HOP_TAG:
                    this_hop_id = child.getAttribute(Hop.ID_TAG)
                    if this_hop_id == hop_id:
                        hop_node = child
                        break
                elif child.nodeType == XMLNode.ELEMENT_NODE and \
                        child.localName == Path.GLOBAL_ID_TAG:
                    path_globalId = str(child.firstChild.nodeValue).strip()
        else:
            raise StitchingError("%s: No stitching path '%s' element in manifest" % (self, path_id))

        if hop_node:
#            self.logger.debug("Found hop %s (id %s)" % (hop_node, this_hop_id))
            for child in hop_node.childNodes:
                if child.nodeType == XMLNode.ELEMENT_NODE and \
                        child.localName == Hop.LINK_TAG:
                    link_node = child
                    break
        else:
            raise StitchingError("%s: Couldn't find hop '%s' in manifest rspec. Looking in path '%s' (id '%s')" % (self, hop_id, path_node, this_path_id))

        if link_node:
            link_id = link_node.getAttribute(HopLink.ID_TAG)
#            self.logger.debug("Hop had link %s", link_id)
            for child in link_node.childNodes:
                if child.nodeType == XMLNode.ELEMENT_NODE and \
                        child.localName == HopLink.SCD_TAG:
                    scd_node = child
                    break
        else:
            raise StitchingError("%s: Couldn't find link in hop '%s' in manifest rspec" % (self, hop_id))

        if scd_node:
            for child in scd_node.childNodes:
                if child.nodeType == XMLNode.ELEMENT_NODE and \
                        child.localName == HopLink.SCSI_TAG:
                    scsi_node = child
                    break
        else:
            raise StitchingError("%s: Couldn't find switchingCapabilityDescriptor in hop '%s' in link '%s' in manifest rspec" % (self, hop_id, link_id))

        if scsi_node:
            for child in scsi_node.childNodes:
                if child.nodeType == XMLNode.ELEMENT_NODE and \
                        child.localName == HopLink.SCSI_L2_TAG:
                    scsil2_node = child
                    break
        else:
            raise StitchingError("%s: Couldn't find switchingCapabilitySpecificInfo in hop '%s' in manifest rspec" % (self, hop_id))

        if scsil2_node:
            for child in scsil2_node.childNodes:
                if child.nodeType == XMLNode.ELEMENT_NODE:
                    child_text = child.childNodes[0].nodeValue
                    if child.localName == HopLink.VLAN_RANGE_TAG:
                        vlan_range_availability = child_text
                    elif child.localName == HopLink.VLAN_SUGGESTED_TAG:
                        suggested_vlan_range = child_text
        else:
            raise StitchingError("%s: Couldn't find switchingCapabilitySpecificInfo_L2sc in hop '%s' in manifest rspec" % (self, hop_id))

        return (path_globalId, vlan_range_availability, suggested_vlan_range)

    # EG Manifest have only some hops and wrong hop ID. So search by the HopLink ID (URN)
    def getEGVLANRangeSuggested(self, manifest, link_id, path_id):
        vlan_range_availability = None
        suggested_vlan_range = None

        rspec_node = None
        stitching_node = None
        path_node = None
        this_path_id = ""
        hop_node = None
        hop_id = ""
        link_node = None
        this_link_id = ""
        scd_node = None
        scsi_node = None
        scsil2_node = None
        path_globalId = None

        # FIXME: Call once for all hops

        for child in manifest.childNodes:
            if child.nodeType == XMLNode.ELEMENT_NODE and \
                    child.localName == defs.RSPEC_TAG:
                rspec_node = child
                break

        if rspec_node:
            for child in rspec_node.childNodes:
                if child.nodeType == XMLNode.ELEMENT_NODE and \
                        child.localName == defs.STITCHING_TAG:
                    stitching_node = child
                    break
        else:
            raise StitchingError("%s: No rspec element in manifest" % self)

        if stitching_node:
            for child in stitching_node.childNodes:
                if child.nodeType == XMLNode.ELEMENT_NODE and \
                        child.localName == defs.PATH_TAG:
                    this_path_id = child.getAttribute(Path.ID_TAG)
                    if this_path_id == path_id:
                        path_node = child
                        break
        else:
            raise StitchingError("%s: No stitching element in manifest" % self)

        if path_node:
#            self.logger.debug("%s Found rspec manifest stitching path %s (id %s)" % (self, path_node, this_path_id))
            for child in path_node.childNodes:
                if child.nodeType == XMLNode.ELEMENT_NODE and \
                        child.localName == Path.HOP_TAG:

                    hop_id = child.getAttribute(Hop.ID_TAG)
                    hop_node = child
                    link_node = None
                    for child in hop_node.childNodes:
                        if child.nodeType == XMLNode.ELEMENT_NODE and \
                                child.localName == Hop.LINK_TAG:
                            this_link_id = child.getAttribute(HopLink.ID_TAG)
                            if this_link_id == link_id:
                                link_node = child
                                break
                    if link_node:
                        break
                            
        if link_node:
            self.logger.debug("Hop '%s' had link '%s'", hop_id, link_id)
            for child in link_node.childNodes:
                if child.nodeType == XMLNode.ELEMENT_NODE and \
                        child.localName == HopLink.SCD_TAG:
                    scd_node = child
                    break
        else:
            self.logger.info("%s: Couldn't find link '%s' in path '%s' in EG manifest rspec (usually harmless; 2 or 3 of these may happen)" % (self, link_id, path_id))
            # SCS adds EG internal hops - to get from the VLAN component to the VM component.
            # But EG does not include those in the manifest.
            # FIXME: Really, the avail/sugg here should be those reported by that hop. And we should only do this
            # fake thing if those are hops we can't find.

            # fake avail and suggested
            fakeAvail = "2-4094"
            fakeSuggested = ""
            # Find the HopLink on this AM with the given link_id
            for hop in self.hops:
                if hop.urn == link_id:
                    fakeSuggested = hop._hop_link.vlan_suggested_request
                    break
            self.logger.info(" ... returning Fake avail/suggested %s, %s", fakeAvail, fakeSuggested)
            return (path_globalId, fakeAvail, fakeSuggested)
            #raise StitchingError("%s: Couldn't find link %s in path %s in manifest rspec" % (self, link_id, path_id))


        if scd_node:
            for child in scd_node.childNodes:
                if child.nodeType == XMLNode.ELEMENT_NODE and \
                        child.localName == HopLink.SCSI_TAG:
                    scsi_node = child
                    break
        else:
            raise StitchingError("%s: Couldn't find switchingCapabilityDescriptor in link '%s' in manifest rspec" % (self, link_id))

        if scsi_node:
            for child in scsi_node.childNodes:
                if child.nodeType == XMLNode.ELEMENT_NODE and \
                        child.localName == HopLink.SCSI_L2_TAG:
                    scsil2_node = child
                    break
        else:
            raise StitchingError("%s: Couldn't find switchingCapabilitySpecificInfo in link '%s' in manifest rspec" % (self, link_id))

        if scsil2_node:
            for child in scsil2_node.childNodes:
                if child.nodeType == XMLNode.ELEMENT_NODE:
                    child_text = child.childNodes[0].nodeValue
                    if child.localName == HopLink.VLAN_RANGE_TAG:
                        vlan_range_availability = child_text
                    elif child.localName == HopLink.VLAN_SUGGESTED_TAG:
                        suggested_vlan_range = child_text
        else:
            raise StitchingError("%s: Couldn't find switchingCapabilitySpecificInfo_L2sc in link '%s' in manifest rspec" % (self, link_id))

        return (path_globalId, vlan_range_availability, suggested_vlan_range)

    def doReservation(self, opts, slicename, scsCallCount):
        '''Reserve at this AM. Construct omni args, save RSpec to a file, call Omni,
        handle raised Exceptions, DCN AMs wait for status ready, and return the manifest
        '''

        # Ensure we have the right URL / API version / command combo
        # If this AM does APIv3, I'd like to use it
        # But the caller needs to know if we used APIv3 so they know whether to call provision later
        opName = 'createsliver'
        if self.api_version > 2:
            opName = 'allocate'

        self.allocateTries = self.allocateTries + 1

        # Write the request rspec to a string that we save to a file
        requestString = self.requestDom.toxml(encoding="utf-8")
        header = "<!-- Resource request for stitching for:\n\tSlice: %s\n\t at AM:\n\tURN: %s\n\tURL: %s\n -->" % (slicename, self.urn, self.url)
        if requestString and rspec_util.is_rspec_string( requestString, None, None, logger=self.logger ):
            # This line seems to insert extra \ns - GCF ticket #202
#            content = rspec_util.getPrettyRSpec(requestString)
            content = stripBlankLines(string.replace(requestString, "\\n", '\n'))
        else:
            raise StitchingError("%s: Constructed request RSpec malformed? Begins: %s" % (self, requestString[:100]))
        self.rspecfileName = _construct_output_filename(opts, slicename, self.url, self.urn, \
                                                       opName + '-request-'+str(scsCallCount) + str(self.allocateTries), '.xml', 1)

        # Put request RSpecs in /tmp - ensure writable
        # FIXME: Commandline users would prefer something else?
        self.rspecfileName = Aggregate.REQ_RSPEC_DIR + "/" + self.rspecfileName

        # Set -o to ensure this request RSpec goes to a file, not logger or stdout
        opts_copy = copy.deepcopy(opts)
        opts_copy.output = True

        _printResults(opts_copy, self.logger, header, content, self.rspecfileName)
        self.logger.debug("Saved AM %s new request RSpec to file %s", self.urn, self.rspecfileName)

        # Set opts.raiseErrorOnV2AMAPIError so we can see the error codes and respond directly
        # In WARN mode, do not write results to a file. And note results also won't be in log (they are at INFO level)
        if opts.warn:
            # FIXME: Clear opts.debug, .info, .tostdout?
            omniargs = ['--raise-error-on-v2-amapi-error', '-V%d' % self.api_version, '-a', self.url, opName, slicename, self.rspecfileName]
        else:
            omniargs = ['-o', '--raise-error-on-v2-amapi-error', '-V%d' % self.api_version, '-a', self.url, opName, slicename, self.rspecfileName]
            
        self.logger.info("\n\tStitcher doing %s at %s", opName, self.url)
        self.logger.debug("omniargs: %r", omniargs)

        result = None

        try:
            # FIXME: Is that the right counter there?
            self.pgLogUrl = None

#            # Test code to force Utah to say it couldn't give the VLAN tag requested
#            if "emulab.net" in self.url:
#                self.logger.debug("Forcing %s to report an error", self)
#                ret = dict()
#                ret["code"] = dict()
#                ret["code"]["geni_code"] = 2
#                ret["code"]["am_code"] = 2
#                ret["code"]["am_type"] = "protogeni"
#                ret["output"] = "*** ERROR: mapper: Reached run limit. Giving up."
#                raise AMAPIError("test", ret)

            # FIXME: Try disabling all but WARN log messages? But I lose PG Log URL? 
            (text, result) = self.doAMAPICall(omniargs, opts, opName, slicename, self.allocateTries, suppressLogs=True)
            self.logger.debug("%s %s at %s got: %s", opName, slicename, self, text)
            if "PG log url" in text:
                pgInd = text.find("PG log url - look here for details on any failures: ")
                self.pgLogUrl = text[pgInd + len("PG log url - look here for details on any failures: "):text.find(")", pgInd)]
                self.logger.debug("Had PG log url in return text and recorded: %s", self.pgLogUrl)
                if not self.isPG and not self.dcn and not self.isEG:
                    self.isPG = True
            elif result and isinstance(result, dict) and len(result.keys()) == 1 and \
                    result.itervalues().next().has_key('code') and \
                    isinstance(result.itervalues().next()['code'], dict):
                code = result.itervalues().next()['code']
                try:
                    self.pgLogUrl = code["protogeni_error_url"]
                    self.logger.debug("Got PG Log url from return struct %s", self.pgLogUrl)
                    if not self.isPG and not self.dcn and not self.isEG:
                        self.isPG = True
                except:
                    pass
            elif self.api_version >= 3 or result is None:
                # malformed result
                msg = "%s got Malformed return from %s: %s" % (self, opName, text)
                self.logger.error(msg)
                # FIXME: Retry before going to the SCS? Or bail altogether?
                self.inProcess = False
                raise StitchingError(msg)


            # For testing VLAN Unavailable code, for the right AM, raise an AM API Error with code=24
#            if self.nick == "utah-pg":
#                # FIXME: Could try other codes/messages for other way to detect the failed hop
#                errStruct = {"code": {"geni_code": 24, "am_code": 24, "am_type": 'protogeni'}, "output": "Could not reserve vlan tags"}
#                raise AMAPIError("Fake VLAN Unavailable error at %s" % self.nick, errStruct)

            # May have changed URL versions - if so, save off the corrected URL?
            if result and self.api_version > 2:
                url = result.iterkeys().next()
                if str(url) != str(self.url):
                    self.logger.debug("%s found URL for API version is %s", self, url)
                    # FIXME: Safe to change the local URL to the corrected one?
#                    self.url = url

            if self.api_version == 2 and result:
                if self.isEG:
                    import re
                    # EG inserts a geni_sliver_info tag on nodes or links that gives the sliverstatus. It sometimes says failed.
                    # FIXME: Want to say cannot have /node> or /link> before the geni_sliver_info
                    match = re.search(r"<(node|link).+client_id=\"([^\"]+)\".+geni_sliver_info error=\"Reservation .* \(Slice urn:publicid:IDN\+.*%s\) is in state \[Failed.*Last ticket update: (\S[^\n\r]*)" % slicename, result, re.DOTALL)
                    if match:
                        msg="Error in manifest: %s '%s' had error: %s" % (match.group(1), match.group(2), match.group(3))
                        self.logger.debug("EG AM %s reported %s", self, msg)
                        raise AMAPIError(text + "; " + match.group(3), dict(code=dict(geni_code=-2,am_type='orca',am_code='2'),value=result,output=msg))

                # Success in APIv2
                pass
            elif self.api_version >= 3 and result and isinstance(result, dict) and len(result.keys()) == 1 and \
                    result.itervalues().next().has_key("code") and \
                    isinstance(result.itervalues().next()["code"], dict) and \
                    result.itervalues().next()["code"].has_key("geni_code"):
                if result.itervalues().next()["code"]["geni_code"] != 0:
                    #self.logger.debug("APIv3 result struct OK but non 0")
                    # The struct in the AMAPIError is just the return value and not by URL
                    raise AMAPIError(text, result.itervalues().next())
                elif self.isEG:
                    import re
                    # EG inserts a geni_sliver_info tag on nodes or links that gives the sliverstatus. It sometimes says failed.
                    # FIXME: Want to say cannot have /node> or /link> before the geni_sliver_info
                    match = re.search(r"<(node|link).+client_id=\"([^\"]+)\".+geni_sliver_info error=\"Reservation .* \(Slice urn:publicid:IDN\+.*%s\) is in state \[Failed.*Last ticket update: (\S[^\n\r]*)" % slicename, result, re.DOTALL)
                    if match:
                        msg="Error in manifest: %s '%s' had error: %s" % (match.group(1), match.group(2), match.group(3))
                        self.logger.debug("EG AM %s reported %s", self, msg)
                        raise AMAPIError(text + "; " + match.group(3), dict(code=dict(geni_code=-2,am_type='orca',am_code='2'),value=result,output=msg))

                # Else this is success
                #self.logger.debug("APIv3 proper result struct - success")
            else:
                if self.api_version == 2:
                    msg = "%s got Empty v2 return from %s: %s" % (self, opName, text)
                else:
                    msg = "%s got Malformed v3+ return from %s: %s" % (self, opName, text)
                self.logger.error(msg)
                # FIXME: Retry before going to the SCS? Or bail altogether?
                self.inProcess = False
                raise StitchingError(msg)

        except AMAPIError, ae:
            didInfo = False
#            self.logger.info("Got AMAPIError doing %s %s at %s: %s", opName, slicename, self, ae)

            if self.isEG:
                didInfo = True
                self.logger.info("Got AMAPIError doing %s %s at %s: %s", opName, slicename, self, ae)
                # deleteReservation
                opName = 'deletesliver'
                if self.api_version > 2:
                    opName = 'delete'
                if opts.warn:
                    omniargs = ['--raise-error-on-v2-amapi-error', '-V%d' % self.api_version, '-a', self.url, opName, slicename]
                else:
                    omniargs = ['--raise-error-on-v2-amapi-error', '-o', '-V%d' % self.api_version, '-a', self.url, opName, slicename]
                try:
                    # FIXME: right counter?
                    (text, delResult) = self.doAMAPICall(omniargs, opts, opName, slicename, self.allocateTries, suppressLogs=True)
                    self.logger.debug("doAMAPICall on EG AM where res had AMAPIError: %s %s at %s got: %s", opName, slicename, self, text)
                except Exception, e:
                    self.logger.warn("Failed to delete failed (AMAPIError) reservation at EG AM %s: %s", self, e)

            if ae.returnstruct and isinstance(ae.returnstruct, dict) and ae.returnstruct.has_key("code") and \
                    isinstance(ae.returnstruct["code"], dict) and ae.returnstruct["code"].has_key("geni_code"):

                # Try to get PG log url:
                try:
                    if ae.returnstruct["code"]["am_type"] == "protogeni":
                        if not self.isPG and not self.dcn and not self.isEG:
                            self.isPG = True
                        self.pgLogUrl = ae.returnstruct["code"]["protogeni_error_url"]
                except:
                    pass

                if ae.returnstruct["code"]["geni_code"] == 24:
                    if not didInfo:
                        self.logger.info("Got AMAPIError doing %s %s at %s: %s", opName, slicename, self, ae)
                        didInfo = True
                    # VLAN_UNAVAILABLE
                    self.logger.debug("Got VLAN_UNAVAILABLE from %s %s at %s", opName, slicename, self)
                    # FIXME FIXME FIXME
                    self.handleVlanUnavailable(opName, ae)
                else:
                    # some other AMAPI error code
                    # FIXME: Try to parse the am_code or the output message to decide if this is 
                    # a stitching error (go to SCS) vs will never work (go to user)?
                    # This is where we have to distinguish node unavailable vs VLAN unavailable vs something else

                    isVlanAvailableIssue = False
                    isFatal = False # Is this error fatal at this AM, so we should give up
                    fatalMsg = "" # Message to return if this is fatal

                    # PG based AMs seem to return a particular error code and string when the VLAN isn't available
                    try:
                        code = ae.returnstruct["code"]["geni_code"]
                        amcode = ae.returnstruct["code"]["am_code"]
                        amtype = ae.returnstruct["code"]["am_type"]
                        msg = ae.returnstruct["output"]
                        val = None
                        if ae.returnstruct.has_key("value"):
                            val = ae.returnstruct["value"]
#                        self.logger.debug("Error was code %s (am code
#                        %s): %s", code, amcode, msg)

                        # 2/11/14: JonD says the below error should be
                        # rare and means something deeper/bad is
                        # wrong. Report it to Jon if it gets common.
                        # But maybe sometime soon make this a vlanAvailableIssue
                        # ("Error reserving vlan tag for link" in msg
                        # and code==2 and amcode==2 and amtype=="protogeni")

                        # FIXME: Add support for EG specific vlan unavail errors
                        # FIXME: Add support for EG specific fatal errors

                        if (("Could not reserve vlan tags" in msg or "Error reserving vlan tag for " in msg) and \
                                code==2 and amcode==2 and amtype=="protogeni") or \
                                ('vlan tag ' in msg and ' not available' in msg and code==1 and amcode==1 and amtype=="protogeni"):
#                            self.logger.debug("Looks like a vlan availability issue")
                            isVlanAvailableIssue = True
                        elif amtype == "protogeni":
                            if code == 2 and amcode == 2 and (val == "Could not map to resources" or msg.startswith("*** ERROR: mapper") or 'Could not verify topo' in msg or 'Inconsistent ifacemap' in msg):
                                self.logger.debug("Fatal error from PG AM")
                                isFatal = True
                                fatalMsg = "Reservation request impossible at %s: %s..." % (self, str(ae)[:120])
                            elif code == 6 and amcode == 6 and msg.startswith("Hostname > 63 char"):
                                self.logger.debug("Fatal error from PG AM")
                                isFatal = True
                                fatalMsg = "Reservation request impossible at %s: %s..." % (self, str(ae)[:120])
                            elif code == 1 and amcode == 1 and msg.startswith("Duplicate link "):
                                self.logger.debug("Fatal error from PG AM")
                                isFatal = True
                                fatalMsg = "Reservation request impossible at %s: %s..." % (self, str(ae)[:120])
                            elif code == 7 and amcode == 7 and msg.startswith("Must delete existing sli"):
                                self.logger.debug("Fatal error from PG AM")
                                isFatal = True
                                fatalMsg = "Reservation request impossible at %s: You already have a reservation in slice %s at this aggregate - delete it first or use another aggregate. %s..." % (self, slicename, str(ae)[:120])
                        elif self.isEG:
                            # AM said success but manifest said failed
                            # FIXME: Other fatal errors?
                            if "edge domain does not exist" in msg or "check_image_size error" in msg or "incorrect image URL in ImageProxy" in msg:
                                isFatal = True
                                fatalMsg = "Reservation request impossible at %s: geni_sliver_info contained error: %s..." % (self, msg)
                            # FIXME: Detect error on link only

                            # If the problem is resource allocation at ExoSM vs local and we have
                            # an alternative, try the alternative
                            if "Insufficient numCPUCores" in msg:
                                if self.alt_url is not None and self.allocateTries < self.MAX_TRIES:
                                    msg = "Retrying reservation at %s at URL %s instead of %s to resolve error: %s" % (self, self.alt_url, self.url, msg)
                                    self.logger.info(msg)
                                    oldURL = self.url
                                    self.url = self.alt_url
                                    self.alt_url = oldURL
                                    # put the agg back in the queue to try again, but only do this trick once
                                    self.allocateTries = self.MAX_TRIES
                                    self.inProcess = False
                                    raise StitchingRetryAggregateNewVlanError(msg)
                                else:
                                    isFatal = True
                                    fatalMsg = "Reservation request impossible at %s: geni_sliver_info contained error: %s..." % (self, msg)

                            pass
                        elif self.dcn:
                            if "AddPersonToSite: Invalid argument: No such site" in msg and self.allocateTries < 2:
                                # This happens at an SFA AM the first time it sees your project. If it happens a 2nd time that is something else.
                                # Raise a special error that says don't sleep before retrying
                                self.inProcess = False
                                raise StitchingRetryAggregateNewVlanImmediatelyError("SFA based %s had not seen your project before. Try again. (Error was %s)" % (self, msg))
                            elif code == 7 and amcode == 7 and "CreateSliver: Existing record" in msg:
                                self.logger.debug("Fatal error from DCN AM")
                                isFatal = True
                                fatalMsg = "Reservation request impossible at %s: %s..." % (self, str(ae)[:120])
                            elif code == 5 and amcode == 5 and "AddSite: Invalid argument: Login base must be specified" in msg:
                                self.logger.debug("Fatal error from DCN AM")
                                isFatal = True
                                # FIXME: Find out the real rule from Tony/Xi and say something better here
                                fatalMsg = "Project name or slice name too long? At %s: %s..." % (self, str(ae)[:120])

                    except Exception, e:
                        if isinstance(e, StitchingError):
                            raise e
#                        self.logger.debug("Apparently not a vlan availability issue. Back to the SCS")

                    if isVlanAvailableIssue:
                        if not didInfo:
                            self.logger.info("Got AMAPIError doing %s %s at %s: %s", opName, slicename, self, ae)
                            didInfo = True
                        self.handleVlanUnavailable(opName, ae)
                    else:
                        if isFatal and self.userRequested:
                            # if it was not user requested, then going to the SCS to avoid that seems right
                            raise StitchingError(fatalMsg)

                        # Exit to SCS
                        if not self.userRequested:
                            # If we've tried this AM a few times, set its hops to be excluded
                            if self.allocateTries > self.MAX_TRIES:
                                self.logger.debug("%s allocation failed %d times - try excluding its hops", self, self.allocateTries)
                                for hop in self.hops:
                                    hop.excludeFromSCS = True

                            if isFatal:
                                self.logger.debug("%s allocation failed fatally - exclude its hops. Got %s", self, fatalMsg)
                                for hop in self.hops:
                                    hop.excludeFromSCS = True
                        # This says always go back to the SCS
                        # This is dangerous - we could thrash
                        # FIXME: go back a limited # of times
                        # FIXME: Uncomment below code so only errors at SCS AMs cause us to go back to SCS?
                        self.inProcess = False
                        if isFatal:
                            errormsg = fatalMsg
                        else:
                            errormsg = "Circuit reservation failed at %s (%s). Try again from the SCS" % (self, ae)
                        raise StitchingCircuitFailedError(errormsg)

#                        if not self.userRequested:
#                            # Exit to SCS
#                            # If we've tried this AM a few times, set its hops to be excluded
#                            if self.allocateTries > self.MAX_TRIES:
#                                self.logger.debug("%s allocation failed %d times - try excluding its hops", self, self.allocateTries)
#                                for hop in self.hops:
#                                    hop.excludeFromSCS = True
#                            self.inProcess = False
#                            raise StitchingCircuitFailedError("Circuit failed at %s (%s). Try again from the SCS" % (self, ae))
#                        else:
#                            # Exit to User
#                            raise StitchingError("Stitching failed trying %s at %s: %s" % (opName, self, ae))
            else:
                # Malformed AMAPI return struct
                # Exit to User
                raise StitchingError("Stitching failed: Malformed error struct doing %s at %s: %s" % (opName, self, ae))
        except Exception, e:
            # Some other error (OmniError, StitchingError)

            if self.isEG:
                # deleteReservation
                opName = 'deletesliver'
                if self.api_version > 2:
                    opName = 'delete'
                if opts.warn:
                    omniargs = ['--raise-error-on-v2-amapi-error', '-V%d' % self.api_version, '-a', self.url, opName, slicename]
                else:
                    omniargs = ['--raise-error-on-v2-amapi-error', '-o', '-V%d' % self.api_version, '-a', self.url, opName, slicename]
                try:
                    # FIXME: right counter?
                    (text, delResult) = self.doAMAPICall(omniargs, opts, opName, slicename, self.allocateTries, suppressLogs=True)
                    self.logger.debug("doAMAPICall on EG AM where res had Exception: %s %s at %s got: %s", opName, slicename, self, text)
                except Exception, e:
                    self.logger.warn("Failed to delete failed (Exception) reservation at EG AM %s: %s", self, e)

            # Exit to user
            raise StitchingError(e) # FIXME: right way to re-raise?

        # Pull actual manifest out of result
        # If v2, this already is the manifest
        if self.api_version > 2:
            try:
                result = result.itervalues().next()['value']['geni_rspec']
            except Exception, e:
                # FIXME: Do this even if not fakeModeDir?
                if (isinstance(result, str) or isinstance(result, unicode)) and opts.fakeModeDir:
                    # Well OK then
                    pass
                else:
                    msg = "Malformed return struct from %s at %s: %s (result: %s)" % (opName, self, e, result)
                    self.logger.warn(msg)
                    raise StitchingError("Stitching failed - got %s" % msg)

        # Handle DCN AMs
        if self.dcn:
            # FIXME: right counter?
            (text, result) = self.handleDcnAM(opts, slicename, self.allocateTries)

        if self.isEG:
            # FIXME: A later manifest will have more information, like login information
            # Also, by watching sliver status, we can detect if the provisioning fails
            # Specifically, if the link sliver is the only thing that fails, then it is
            # handleVlanUnavailable
            self.logger.debug("Got an EG AM: FIXME: It could still fail, and this manifest lacks some info.")

        # Caller handles saving the manifest, comparing man sug with request, etc
        # FIXME: Not returning text here. Correct?
        return result

    def handleDcnAM(self, opts, slicename, ctr):
        # DCN based AMs cannot really tell you if they succeeded until sliverstatus is ready or not
        # So wait for that, then get the listresources manifest and use that as the manifest

        self.logger.info("DCN AM %s: must wait for status ready....", self)

        # FIXME: Add a maxtime to wait as well
        tries = 0
        status = 'unknown'
        while tries < self.SLIVERSTATUS_MAX_TRIES:
            # Pause before calls to sliverstatus
            self.logger.info("Pause %d seconds to let circuit become ready...", self.SLIVERSTATUS_POLL_INTERVAL_SEC)
            time.sleep(self.SLIVERSTATUS_POLL_INTERVAL_SEC)

            # generate args for sliverstatus
            if self.api_version == 2:
                opName = 'sliverstatus'
            else:
                opName = 'status'
            if opts.warn:
                omniargs = [ '-V%d' % self.api_version, '--raise-error-on-v2-amapi-error', '-a', self.url, opName, slicename]
            else:
                omniargs = ['-o', '-V%d' % self.api_version, '--raise-error-on-v2-amapi-error', '-a', self.url, opName, slicename]
            result = None
            try:
                tries = tries + 1
                # FIXME: shouldn't ctr be based on tries here?
                # FIXME: Big hack!!!
                if not opts.fakeModeDir:
                    (text, result) = self.doAMAPICall(omniargs, opts, opName, slicename, ctr, suppressLogs=True)
                    self.logger.debug("handleDcn %s %s at %s got: %s", opName, slicename, self, text)
            except Exception, e:
                # exit gracefully
                # FIXME: to SCS excluding this hop? to user? This could be some transient thing, such that redoing
                # circuit as is would work. Or it could be something permanent. How do we know?
                raise StitchingError("%s %s failed at %s: %s" % (opName, slicename, self, e))

            dcnErrors = dict() # geni_error by geni_urn of individual resource
            circuitIDs = dict() # DCN circuit ID by geni_urn (one parse from the other)
            statuses = dict() # per sliver status

            # Parse out sliver status / status
            if isinstance(result, dict) and result.has_key(self.url) and result[self.url] and \
                    isinstance(result[self.url], dict):
                if self.api_version == 2:
                    if result[self.url].has_key("geni_status"):
                        status = result[self.url]["geni_status"]
                    else:
                        # else malformed
                        raise StitchingError("%s had malformed %s result in handleDCN" % (self, opName))
                    # Get any geni_error string
                    if result[self.url].has_key("geni_resources") and \
                            isinstance(result[self.url]["geni_resources"], list) and \
                            len(result[self.url]["geni_resources"]) > 0:
                        for resource in result[self.url]["geni_resources"]:
                            if not isinstance(resource, dict) and not resource.has_key("geni_urn"):
                                self.logger.debug("Malformed sliverstatus - resource not a dict or has no geni_urn: %s", str(resource))
                                continue
                            urn = resource["geni_urn"]
                            if urn:
                                circuitid = None
                                import re
                                match = re.match("^urn:publicid:IDN\+[^\+]+\+sliver\+.+_vlan_[^\-]+\-(\d+)$", urn)
                                if match:
                                    circuitid = match.group(1).strip()
                                    self.logger.debug("Found circuit '%s'", circuitid)
                                else:
                                    self.logger.debug("Found no geni_urn match? URN: %s", urn)
                                circuitIDs[urn] = circuitid
                                if resource.has_key("geni_error"):
                                    dcnErrors[urn] = resource["geni_error"]
                                    self.logger.debug("Found geni_error '%s' for circuit %s", dcnErrors[urn], circuitid)
                                else:
                                    self.logger.debug("Malformed sliverstatus missing geni_error tag: %s", str(resource))
                                    dcnErrors[urn] = None

                                if resource.has_key("geni_status"):
                                    statuses[urn] = resource["geni_status"]
                                    self.logger.debug("Found status '%s' for sliver %s (circuit %s)", statuses[urn], urn, circuitid)
                                else:
                                    self.logger.debug("Malformed sliverstatus missing geni_status: %s", str(resource))
                                    statuses[urn] = status
                            else:
                                self.logger.debug("Malformed sliverstatus has empty geni_urn: %s", str(resource))
                else:
                    if result[self.url].has_key("value") and isinstance(result[self.url]["value"], dict) and \
                            result[self.url]["value"].has_key("geni_slivers") and isinstance(result[self.url]["value"]["geni_slivers"], list):
                        for sliver in result[self.url]["value"]["geni_slivers"]:
                            if isinstance(sliver, dict) and sliver.has_key("geni_allocation_status"):
                                status = sliver["geni_allocation_status"]
                                dcnerror = None
                                if sliver.has_key("geni_error"):
                                    dcnerror = sliver["geni_error"]
                                if sliver.has_key("geni_sliver_urn"):
                                    urn = sliver["geni_sliver_urn"]
                                    if urn:
                                        import re
                                        statuses[urn] = status
                                        circuitid = None
                                        match = re.match("^urn:publicid:IDN\+[^\+]+\+sliver\+.+_vlan_[^\-]+\-(\d+)$", urn)
                                        if match:
                                            circuitid = match.group(1).strip()
                                            self.logger.debug("Found circuit '%s'", circuitid)
                                        else:
                                            self.logger.debug("Found no geni_urn match? URN: %s", urn)
                                        circuitIDs[urn] = circuitid
                                        dcnErrors[urn] = dcnerror
                                    else:
                                        self.logger.debug("Malformed sliverstatus has empty sliver_urn: %s", str(sliver))
                                else:
                                    self.logger.debug("Malformed sliverstatus has no geni_sliver_urn: %s", str(sliver))

                                break # FIXME: This stops at the first sliver. Can we do better? Ticket 261
                            else:
                                self.logger.debug("Malformed sliverstatus has non dict sliver entry or entry with no geni_allocation_status: %s", str(sliver))
                        # FIXME: Which sliver(s) do I look at?
                        # 1st? look for any not ready and take that?
                        # And pull out any geni_error
                        # FIXME FIXME
                        # FIXME: I don't really know how AMs will do v3 status' so wait
                    else:
                        # malformed
                        raise StitchingError("%s had malformed %s result in handleDCN" % (self, opName))
            else:
                # FIXME FIXME Big hack
                if not opts.fakeModeDir:
                    # malformed
                    raise StitchingError("%s had malformed %s result in handleDCN" % (self, opName))

            # FIXME: Big hack!!!
            if opts.fakeModeDir:
                status = 'ready'

            status = str(status).lower().strip()
            if status in ('failed', 'ready', 'geni_allocated', 'geni_provisioned', 'geni_failed', 'geni_notready', 'geni_ready'):
                break
            for entry in circuitIDs.keys():
                circuitid = circuitIDs[entry]
                dcnerror = dcnErrors[entry]
                status = statuses[entry]
                if dcnerror and dcnerror.strip() != '':
                    if circuitid:
                        self.logger.info("%s: %s is (still) %s at %s. Had error message: %s", opName, circuitid, status, self, dcnerror)
                    else:
                        self.logger.info("%s is (still) %s at %s. Had error message: %s", opName, status, self, dcnerror)
        # End of while loop getting sliverstatus

        if status not in ('ready', 'geni_allocated', 'geni_provisioned', 'geni_ready'):
            for entry in circuitIDs.keys():
                circuitid = circuitIDs[entry]
                dcnerror = dcnErrors[entry]
                status = statuses[entry]
                if (status not in ('ready', 'geni_allocated', 'geni_provisioned', 'geni_ready') or dcnerror is not None):
                    if circuitid:
                        self.logger.warn("%s: %s is (still) %s at %s. Delete and retry.", opName, circuitid, status, self)
                    else:
                        self.logger.warn("%s is (still) %s at %s. Delete and retry.", opName, status, self)
                    if dcnerror and dcnerror.strip() != '':
                        self.logger.warn("  Status had error message: %s", dcnerror)

            # deleteReservation
            opName = 'deletesliver'
            if self.api_version > 2:
                opName = 'delete'
            if opts.warn:
                omniargs = ['--raise-error-on-v2-amapi-error', '-V%d' % self.api_version, '-a', self.url, opName, slicename]
            else:
                omniargs = ['--raise-error-on-v2-amapi-error', '-o', '-V%d' % self.api_version, '-a', self.url, opName, slicename]
            try:
                # FIXME: right counter?
                (text, delResult) = self.doAMAPICall(omniargs, opts, opName, slicename, ctr, suppressLogs=True)
                self.logger.debug("handleDCN %s %s at %s got: %s", opName, slicename, self, text)
            except Exception, e:
                # Exit to user
                raise StitchingError("Failed to delete reservation at DCN AM %s that was %s: %s" % (self, status, e))

            # FIXME: Check the return from delete for errors. If there are errors, raise StitchingError? Really I want to treat this like we had a previous sliver here

            msg = None
            for entry in circuitIDs.keys():
                circuitid = circuitIDs[entry]
                dcnerror = dcnErrors[entry]
                status = statuses[entry]
                if msg == None:
                    msg = ""
                else:
                    msg = msg + ".\n"
                if circuitid:
                    msg = msg + "Sliver status for circuit %s was (still): %s" % (circuitid, status)
                else:
                    msg = msg + "Sliver status was (still): %s" % status
                if dcnerror and dcnerror.strip() != '':
                    msg = msg + ": " + dcnerror

            if msg is None:
                msg = "Sliver status was (still): %s (and no circuits listed in status)" % status

            # ION failures are sometimes transient. If we haven't retried too many times, just try again
            # But if we have retried a bunch already, treat it as VLAN Unavailable - which will exclude the VLANs
            # we used before and go back to the SCS
            if self.localPickNewVlanTries >= self.MAX_DCN_AGG_NEW_VLAN_TRIES:
                # Treat as VLAN was Unavailable - note it could have been a transient circuit failure or something else too
                self.handleVlanUnavailable(opName, msg)
            else:
                self.localPickNewVlanTries = self.localPickNewVlanTries + 1
                self.inProcess = False
                raise StitchingRetryAggregateNewVlanError(msg)

        else:
            for entry in circuitIDs.keys():
                circuitid = circuitIDs[entry]
                dcnerror = dcnErrors[entry]
                if circuitid:
                    self.logger.info("DCN circuit %s is ready", circuitid)

            # Status is ready
            # generate args for listresources
            if self.api_version == 2:
                opName = 'listresources'
            else:
                opName = 'describe'
            # FIXME: Big hack!!!
            if opts.fakeModeDir:
                if self.api_version == 2:
                    opName = 'createsliver'
                else:
                    opName = 'allocate'
                self.logger.info("Will look like %s, but pretending to do listresources", opName)
            if opts.warn:
                omniargs = ['--raise-error-on-v2-amapi-error', '-V%d' % self.api_version, '-a', self.url, opName, slicename]
            else:
                omniargs = ['-o', '--raise-error-on-v2-amapi-error', '-V%d' % self.api_version, '-a', self.url, opName, slicename]
            try:
                # FIXME: Suppressing all but WARN messages, but I'll lose PG log URL?
                (text, result) = self.doAMAPICall(omniargs, opts, opName, slicename, ctr, suppressLogs=True)
                self.logger.debug("%s %s at %s got: %s", opName, slicename, self, text)
            except Exception, e:
                # Note this could be an AMAPIError. But what AMAPIError could this be that we could handle?
                # Exit gracefully
                raise StitchingError("Stitching failed in handleDcn trying %s at %s: %s" % (opName, self, e))

            # Get the single manifest out of the result struct
            try:
                if self.api_version == 2:
                    oneResult = result.values()[0]["value"]
                elif self.api_version == 1:
                    oneResult = result.values()[0]
                else:
                    oneResult = result.values()[0]["value"]["geni_rspec"]
            except Exception, e:
                if (isinstance(result, str) or isinstance(result, unicode)) and opts.fakeModeDir:
                    oneResult = result
                else:
                    raise StitchingError("Malformed return from %s at %s: %s" % (opName, self, e))
            return (text, oneResult)

    def handleSuggestedVLANNotRequest(self, opts, slicename):
        # FIXME FIXME FIXME
        # Ticket 261

        # note what we tried that failed (ie what was requested but not given at this hop)
        for hop in self.hops:
            if hop._hop_link.vlan_suggested_manifest and len(hop._hop_link.vlan_suggested_manifest) > 0 and \
                    hop._hop_link.vlan_suggested_request != hop._hop_link.vlan_suggested_manifest:
                self.logger.debug("handleSuggVLANNotRequest: On %s adding last request %s to unavailable VLANs", hop, hop._hop_link.vlan_suggested_request)
                hop.vlans_unavailable = hop.vlans_unavailable.union(hop._hop_link.vlan_suggested_request)

#      find an AM to redo
#        note VLAN tags in manifest that don't work later as vlan_unavailable on that AM
#           FIXME: Or separate that into vlan_unavailable and vlan_tried?
#        FIXME: AMs need a redo or reservation counter maybe, to avoid thrashing?
#        FIXME: mark that we are redoing?
#            idea: do we need this in allocate() on the AM we are redoing?
#        delete that AM
#            thatAM.deleteReservation(opts, slicename)
#        set request VLAN tags on that AM
            # See logic in copyVLANsAndDetectRedo
#            thatAM.somehop.hop_link.vlan_suggested_request = self.someOtherHop.hop_link.vlan_suggested_manifest
#         In avail, be sure not to include VLANs we already had once that clearly failed (see vlans_unavailable)
#        exit from this AM without setting complete, so we recheck VLAN tag consistency later
#      else (no AM to redo) gracefully exit: raiseStitchingCircuitFailedError

# From wiki
# This is where suggested was single and man != request. Find the AM that picked the regjected tag if any, and redo that AM: delete
# the existing reservation, set its requested = this manifest, excluding from its avail the requested suggested here that we didn't pick

# Also add to hop.vlan_unavailable the suggested we didnt pick

# If not hop.import_vlans: no prior AMs need to agree, so return as though this succeeded
# Set flag for in process stuff to pause
# go to the hop.import_Vlans_from hop. Call that hop2
# if hop2 requested == manifest, recurse to its import_from
# (possible extraneous else: hop2 is same AM as hop1 and hop2 request = hop1 request and hop2 man == hop1 man, then recurse)
# else if hop2 same AM as hop1 - huh? raise StitchingError to go to user
# else if requested == 'any', then this AM picked the offending tag
#  thatAM.deleteReservation
#  set hop2.suggested_request = hop1.suggested_manifest
#  set hop2.range_request -= hop1.suggested_request
#  return
# else: huh? raise StitchingError
# else can't find an AM to start over from: raise StitchingCircuitFailedError
        pass

    def handleVlanUnavailable(self, opName, exception, failedHop=None, suggestedWasNull=False):
#        FIXME: See logic on wiki
#        remember unavailable vlanRangeAvailability on the hop
#        may need to mark hop explicity loose or add to hop_exclusion list for next SCS request
#        may need to go back to SCS or go back to user
#        if negotiate:
#           don't mark this AM complete, so dependencies don't start going
#           find AM to redo from
#            note VLAN tags in manifest that don't work later as vlan_unavailable
#              FIXME: Or separate that into vlan_unavailable and vlan_tried?
#            FIXME: AMs need a redo or reservation counter maybe, to avoid thrashing?
#            FIXME: mark that we are redoing?
#                idea: do we need this in allocate() on the AM we are redoing?
#            delete reservation at that AM, and exit out from this AM in a graceful way (not setting .complete)

# Wiki logic
# Remember which tag was unavailable in hop.vlans_unavailable if I can tell. Plan to exclude that from SCS vlanRangeAvailability,
# if SCS supports that.

        if not failedHop and len(self.hops) == 1:
            failedHop = iter(self.hops).next()
#            self.logger.debug("handleVlanUnavail got no specific failed hop, but AM only has hop %s", failedHop)

        # PG Error messages sometimes indicate the failed path, so we might be able to ID the failed hop.
        # That would let us be more conservative in what we mark unavailable.
        if not failedHop:
            if isinstance(exception, AMAPIError) and exception.returnstruct:
                #self.logger.debug("handleVU: No failed hop, >1 paths. If this is a PG error that names the link, I should be able to set the failedHop")
                try:
                    code = exception.returnstruct["code"]["geni_code"]
                    amcode = exception.returnstruct["code"]["am_code"]
                    amtype = exception.returnstruct["code"]["am_type"]
                    msg = exception.returnstruct["output"]

                    if 'Error reserving vlan tag for ' in msg and code==2 and amcode==2 and amtype=='protogeni':
                        import re
                        match = re.match("^Error reserving vlan tag for '(.+)'", msg)
                        if match:
                            failedPath = match.group(1).strip()
                            failedHopsnoXlate = []
                            for hop in self.hops:
                                if hop.path.id == failedPath:
                                    if not hop._hop_link.vlan_xlate:
                                        failedHopsnoXlate.append(hop)
                            if len(failedHopsnoXlate) >= 1:
                                # When PG U is transit net, the count will be 2. If I pick one to be the failed hop, I believe the right thing happens
                                # Hence I can pick any of these hops
                                failedHop = failedHopsnoXlate[0]
                                self.logger.debug("Based on parsed error message: %s, setting failed hop to %s", msg, failedHop)
                            else:
                                self.logger.debug("Cannot set failedHop from parsed error message: %s: Got %d failed hops that don't do translation", msg, len(failedHopsnoXlate))
                        else:
                            self.logger.debug("Failed to parse failed from PG message: %s", msg)
                    elif 'vlan tag ' in msg and ' not available' in msg and code==1 and amcode==1 and amtype=="protogeni":
                        #self.logger.debug("This was a PG error message that names the failed link/tag")
                        # Parse out the tag and link name
                        import re
                        match = re.match("^vlan tag (\d+) for '(.+)' not available", msg)
                        if match:
                            failedPath = match.group(2).strip()
                            failedTag = match.group(1).strip()
                            failedHopsnoXlate = []
                            for hop in self.hops:
                                if hop.path.id == failedPath:
                                    if not VLANRange.fromString(failedTag) <= hop._hop_link.vlan_suggested_request:
                                        self.logger.debug("%s is on PG reported failed path %s but its sug request was %s, not reported unavail %s", hop, failedPath, hop._hop_link.vlan_suggested_request, failedTag)
                                    else:
                                        if not hop._hop_link.vlan_xlate:
                                            failedHopsnoXlate.append(hop)
                                        hop.vlans_unavailable = hop.vlans_unavailable.union(VLANRange.fromString(failedTag))
                                        self.logger.debug("%s unavail adding PG reported failed tag %s", hop, failedTag)
                            if len(failedHopsnoXlate) >= 1:
                                # When PG U is transit net, the count will be 2. If I pick one to be the failed hop, I believe the right thing happens
                                # Hence I can pick any of these hops
                                failedHop = failedHopsnoXlate[0]
                                self.logger.debug("Based on parsed error message: %s, setting failed hop to %s", msg, failedHop)
                            else:
                                self.logger.debug("Cannot set failedHop from parsed error message: %s: Got %d failed hops that don't do translation", msg, len(failedHopsnoXlate))
                        else:
                            self.logger.debug("Failed to parse failed tag and link from PG message: %s", msg)
#                    else:
#                        self.logger.debug("This isn't the PG error message that lets me find the failed path")
                except Exception, e2:
                    # Could not get msg / AM type from exception. So cannot reset failedHop
                    self.logger.debug("Failed to parse message from AMAPIError: %s", e2)
                    pass
        # Done with block to find failed hop from PG

        # Make a list of all the hops we must treat as having failed
        failedHops = []
        if failedHop:
            # The failed hop failed
            failedHops.append(failedHop)
            # Any hop on the same path as the failed hops where one doesn't xlate is also failed
            for hop in self.hops:
                if hop != failedHop and hop.path.id == failedHop.path.id and (not hop._hop_link.vlan_xlate or not failedHop._hop_link.vlan_xlate):
                    self.logger.debug("%s on same path as failed %s so it failed", hop, failedHop)
                    failedHops.append(hop)
        else:
            # No single failed hop - must treat them all as failed
            failedHops = self.hops

        # For each failed hop (could be all), or hop on same path as failed hop that does not do translation, mark unavail the tag from before
        for hop in failedHops:
            if not hop._hop_link.vlan_suggested_request <= hop.vlans_unavailable:
                hop.vlans_unavailable = hop.vlans_unavailable.union(hop._hop_link.vlan_suggested_request)
                self.logger.debug("%s: This hop failed or does not do vlan translation and is on the failed path. Mark sugg %s unavail: %s", hop, hop._hop_link.vlan_suggested_request, hop.vlans_unavailable)
            # Must also remove this from its range request - done below
            # Find other failed hops with same URN. Those should also avoid this failed tag
            for hop2 in self.hops:
                # Used to only do this if the other hop also failed. Unless an AM says a hop failed cause you requested
                # it on another circuit, that seems wrong
                # FIXME: If I start having trouble consider removing this block
                if hop2 != hop and hop2.urn == hop.urn:
                    if not hop._hop_link.vlan_suggested_request <= hop2.vlans_unavailable:
                        hop2.vlans_unavailable = hop2.vlans_unavailable.union(hop._hop_link.vlan_suggested_request)
                        self.logger.debug("%s is same URN but diff than a failed hop. Marked failed sugg %s unavail here: %s", hop2, hop._hop_link.vlan_suggested_request, hop2.vlans_unavailable)
                    # Must also remove this from its range request - done below

# If this AM was a redo, this may be an irrecoverable failure. If vlanRangeAvailability was a range for the later AM, maybe.
  # Otherwise, raise StitchingCircuitFailedError to go back to the SCS and hope the SCS picks something else
# Set some kind of flag so in process stuff pauses (for threading)
# If APIv2 (and AM fails request if suggested unavail)
  # If suggested ANY then find AM where vlanRange was narrowed and redo there
  # Else suggested was single and vlanRange was a range --- FIXME

        canRedoRequestHere = True
        if (not self.dcn and self.localPickNewVlanTries > self.MAX_AGG_NEW_VLAN_TRIES) or (self.dcn and self.localPickNewVlanTries >= self.MAX_DCN_AGG_NEW_VLAN_TRIES):
            canRedoRequestHere = False
        else:
            self.localPickNewVlanTries = self.localPickNewVlanTries + 1

        if canRedoRequestHere:
            for hop in self.hops:
                if hop.import_vlans:
                    # Some hops here depend on other AMs. This is a negotiation kind of case
                    #                self.logger.debug("%s imports vlans - so cannot redo here", hop)
                    canRedoRequestHere = False
                    break
                if len(hop._hop_link.vlan_range_request) <= 1 and (not failedHop or hop == failedHop or ((not hop._hop_link.vlan_xlate or not failedHop._hop_link.vlan_xlate) and failedHop.path == hop.path)): # FIXME: And failedHop no xlate?
                    # Only the 1 VLAN tag was in the available range and we need a different tag
                    canRedoRequestHere = False
                    self.logger.info("Cannot redo request locally: %s available VLAN range too small: %s. VLANs unavailable: %s" % (hop, hop._hop_link.vlan_range_request, hop.vlans_unavailable))
                    break

        if canRedoRequestHere and not (failedHop and suggestedWasNull) and isinstance(exception, AMAPIError) and exception.returnstruct:
#            self.logger.debug("%s failed request. Does not depend on others so maybe redo?", self)
            # Does the error look like the particular tag just wasn't currently available?
            try:
                code = exception.returnstruct["code"]["geni_code"]
                amcode = exception.returnstruct["code"]["am_code"]
                amtype = exception.returnstruct["code"]["am_type"]
                msg = exception.returnstruct["output"]
                self.logger.debug("Error was code %d (am code %d): %s", code, amcode, msg)
#                # FIXME: If we got an empty / None / null suggested value on the failedHop
                # in a manifest, then we could also redo

                        # 2/11/14: JonD says the below error should be
                        # rare and means something deeper/bad is
                        # wrong. Report it to Jon if it gets common.
                        # But maybe sometime soon make this a vlanAvailableIssue
                        # ("Error reserving vlan tag for link" in msg
                        # and code==2 and amcode==2 and amtype=="protogeni")

                # FIXME Put in things for EG VLAN Unavail errors

                if code == 24 or (("Could not reserve vlan tags" in msg or "Error reserving vlan tag for " in msg) and \
                                      code==2 and amcode==2 and amtype=="protogeni") or \
                                      ('vlan tag ' in msg and ' not available' in msg and code==1 and amcode==1 and amtype=="protogeni"):
#                    self.logger.debug("Looks like a vlan availability issue")
                    pass
                else:
                    self.logger.debug("handleVU says this isn't a vlan availability issue. Got error %d, %d, %s", code, amcode, msg)
                    canRedoRequestHere = False


            except Exception, e2:
                canRedoRequestHere = False
                self.logger.debug("handleVU Exception getting msg/code from exception %s: %s", exception, e2)
#        else:
            # FIXME: If canRedoRequestHere does this still hold?

# Next criteria: If there are hops that depend on this 
# that do NOT do vlan translation AND have other hops that in turn depend on those hops, 
# then there are too many variables - give up.

        if canRedoRequestHere:
            for depAgg in self.isDependencyFor:
                aggOK = True
                for hop in depAgg.hops:
                    if hop._hop_link.vlan_xlate:
                        continue
                    if not hop.import_vlans:
                        continue
                    # If this hop does not depend on the self AM, continue
                    thisAM = False
                    if hop.dependsOn:
                        for depHop in hop.dependsOn:
                            if depHop.aggregate == self:
                                thisAM = True
                                # depHop is the local hop that hop imports from / depends on
                                if failedHop and failedHop != depHop:
                                    # FIXME FIXME: We see this debug printout in a pg utah to ig utah 2 link topology
                                    # Turn down the message?
                                    self.logger.debug("This %s is a dependency for another AM's hop (%s) because of local hop (%s), but my hop the other AM depends on is not the single failed hop. Treating it as OK for local redo", self, hop, depHop)
                                    # But it isn't the failed hop that is a problem. Does this mean this is OK?
                                    # FIXME FIXME
                                break
                    if not thisAM:
                        # Can this be? For a particular hop, maybe. But not for all
                        continue

                    # OK so we found a hop that depends on this Aggregate and does not do vlan translation
                    # Like PG-Utah depending on IG-Utah.
#                    self.logger.debug("%s does not do VLAN xlate and depends on this AM", depAgg)

                    # That's OK if that's it. But if that aggregate has other dependencies, then
                    # this is too complicated. It could still be OK, but it's too complicated
                    if hop.aggregate.isDependencyFor and len(hop.aggregate.isDependencyFor) > 0 \
                            and iter(hop.aggregate.isDependencyFor).next():
                        self.logger.debug("dependentAgg %s's hop %s's Aggregate is a dependency for others - cannot redo here", depAgg, hop)
                        canRedoRequestHere=False
                        aggOK = False
                        break
                # End of loop over hops in the dependent agg
                if not aggOK:
#                    self.logger.debug("depAgg %s has an issue - cannot redo here", depAgg)
                    canRedoRequestHere=False
                    break
            # end of loop over Aggs that depend on self
        # End of block to check if can redo request here

# Here is the new code block
        if canRedoRequestHere:
            self.logger.debug("Using NEW code block for picking new tag")
#            self.logger.debug("After all checks looks like we can locally redo request for %s", self)

            # For each failed hop
            # Last sug is now unavail
            # request range exclude last sug (or whole unavail?)
            # store a new thing: next request range = request range (as just edited) - (all tags other hops with same urn on diff paths are requesting)
            # Other hops same URN diff path should also not use the failed tag: exclude it from request and add it to unavail

            # By hop this is the range to pick a new suggested from. It is the range request 
            # - modified to exclude unavail
            # But it also excludes tags in use by other hops with the same URN. We don't mark those unavail or take out of request range,
            # we just avoid picking them
            # Note that I need to add to this dict the new tags I pick for failed hops
            nextRequestRangeByHop = dict()

            # Record by hop the new and old suggested tags
            newSugByHop = dict()
            oldSugByHop = dict()

            # For hops we are not changing, note the new and old suggested and the new request range
            for hop in self.hops:
                if hop not in failedHops:
                    self.logger.debug("Non failed %s. Old Sug: %s; Avail: %s", hop, hop._hop_link.vlan_suggested_request, hop._hop_link.vlan_range_request)
                    newSugByHop[hop] = hop._hop_link.vlan_suggested_request
                    oldSugByHop[hop] = hop._hop_link.vlan_suggested_request
                    nextRequestRangeByHop[hop] = hop._hop_link.vlan_range_request
                else:
                    self.logger.debug("Failed %s. Old Sug: %s; Avail: %s", hop, hop._hop_link.vlan_suggested_request, hop._hop_link.vlan_range_request)

            # FIXME: for at least some cases (2 transit links both failed),
            # Having each failed hop exclude hop.vlans_unavailable from its request ranges here would be more efficient.
            # Then since each printout below only prints it if had to do something, logs might look cleaner

            # For each failed hop, make sure the failed tag is properly excluded everywhere
            for hop in failedHops:
                # Remember the tag we used before
                oldSugByHop[hop] = hop._hop_link.vlan_suggested_request

                # Exclude the failed hops here
                # Already done above
#                hop.vlans_unavailable = hop.vlans_unavailable.union(hop._hop_link.vlan_suggested_request)
                if hop._hop_link.vlan_suggested_request <= hop._hop_link.vlan_range_request:
                    hop._hop_link.vlan_range_request = hop._hop_link.vlan_range_request - hop._hop_link.vlan_suggested_request
                    self.logger.debug("%s removed failed %s from range request. New range request %s", hop, hop._hop_link.vlan_suggested_request, hop._hop_link.vlan_range_request)
                if hop.vlans_unavailable <= hop._hop_link.vlan_range_request:
                    hop._hop_link.vlan_range_request = hop._hop_link.vlan_range_request - hop.vlans_unavailable
                    self.logger.debug("%s removed unavails from range request. Unavails %s; New range request %s", hop, hop.vlans_unavailable, hop._hop_link.vlan_range_request)
                # Old code intersected other hops no xlate same path, which I think was too restrictive.
                # This is a key difference between old code and new
                nextRequestRangeByHop[hop] = hop._hop_link.vlan_range_request 

                # Now for all hops on the AM make sure tags are excluded as needed
                for hop2 in self.hops:
                    # Hop with same URN on different path must exclude the failed tag
                    if hop2.urn == hop.urn and hop2.path.id != hop.path.id and hop2 != hop:
                        didRemove = False
                        if hop2._hop_link.vlan_suggested_request != VLANRange.fromString('any') and \
                                hop2._hop_link.vlan_suggested_request <= nextRequestRangeByHop[hop]:
                            didRemove = True
                            # Exclude tag on other paths same hop URN whether they failed or not.
                            # If they failed then I think they're bad here too
                            # If that hop did not fail, then we'll be using that tag agin
                            nextRequestRangeByHop[hop] = nextRequestRangeByHop[hop] - hop2._hop_link.vlan_suggested_request

                        # Tell this other hop not to use this tag that failed
                        # FIXME: If I start having problems with hops out of tags, try removing this
                        if hop._hop_link.vlan_suggested_request <= hop2._hop_link.vlan_range_request:
                            didRemove = True
                            hop2._hop_link.vlan_range_request = hop2._hop_link.vlan_range_request - hop._hop_link.vlan_suggested_request
                        # Already done above
#                        hop2.vlans_unavailable = hop2.vlans_unavailable.union(hop._hop_link.vlan_suggested_request)
                        if didRemove:
                            # The printout of new range request looks ugly here if it contains my new unavail, so update it now
                            hop2._hop_link.vlan_range_request = hop2._hop_link.vlan_range_request - hop2.vlans_unavailable
                            self.logger.debug("%s same URN as a failed hop, so excluding its failed tag %s. Also telling failed hop to not use my tag %s. My new unavail %s; new range request %s", hop2, hop._hop_link.vlan_suggested_request, hop2._hop_link.vlan_suggested_request, hop2.vlans_unavailable, hop2._hop_link.vlan_range_request)
                    # make all hops on same path no xlate exclude the failed hop
                    elif hop2.path.id == hop.path.id and hop2 != hop and (not hop2._hop_link.vlan_xlate or not hop._hop_link.vlan_xlate):
                        if hop2 not in failedHops:
                            self.logger.debug("%s on same path as failed %s and one doesn't xlate but is not failed?!", hop2, hop)
                        if hop2._hop_link.vlan_suggested_request != hop._hop_link.vlan_suggested_request:
                            self.logger.debug("%s same path as failed %s and one doesn't xlate but had diff vlan sug %s != %s!!", hop2, hop, hop2._hop_link.vlan_suggested_request, hop._hop_link.vlan_suggested_request)

                        # Since both should be failed with same tag, further actions shouldn't be needed but are also harmless
                        # FIXME: If I start having problems with hops out of tags, try removing this block

                        # edit hop2 range request and unavail to exclude the failed hop's tag
                        if not hop._hop_link.vlan_suggested_request <= hop2.vlans_unavailable or \
                                hop._hop_link.vlan_suggested_request <= hop2._hop_link.vlan_range_request or \
                                not hop2._hop_link.vlan_suggested_request <= hop.vlans_unavailable or \
                                hop2._hop_link.vlan_suggested_request <= hop._hop_link.vlan_range_request or \
                                hop2._hop_link.vlan_suggested_request <= nextRequestRangeByHop[hop]:
                            hop2.vlans_unavailable = hop2.vlans_unavailable.union(hop._hop_link.vlan_suggested_request)
                            hop2._hop_link.vlan_range_request = hop2._hop_link.vlan_range_request - hop2.vlans_unavailable
                            if nextRequestRangeByHop.has_key(hop2):
                                nextRequestRangeByHop[hop2] = nextRequestRangeByHop[hop2] - hop._hop_link.vlan_suggested_request

                            # edit hop range request and unavail to add hop2 prev sug
                            hop.vlans_unavailable = hop.vlans_unavailable.union(hop2._hop_link.vlan_suggested_request)
                            hop._hop_link.vlan_range_request = hop._hop_link.vlan_range_request - hop.vlans_unavailable
                            nextRequestRangeByHop[hop] = nextRequestRangeByHop[hop] - hop.vlans_unavailable
                            self.logger.debug("%s on same path as %s with no xlate, so each will probably exclude the others prev suggested (%s, %s). Hop1 new unavail: %s, range: %s. Hop2 New unavail: %s, range: %s", hop, hop2, hop._hop_link.vlan_suggested_request, hop2._hop_link.vlan_suggested_request, hop.vlans_unavailable, hop._hop_link.vlan_range_request, hop2.vlans_unavailable, hop2._hop_link.vlan_range_request)

                self.logger.debug("%s next request will be from %s", hop, nextRequestRangeByHop[hop])
            # End of initial loop over failed hops

            # FIXME: Old code made nextRequestRange... intersect with the vlan_range_requests of other hops no xlate on the same path
                # Plus 2: of course removing each such failed hop's previous suggested
                # Plus 3: exclude the vlans_unavailable for each hop on that path (if hop no xlate)
                # I like #2 & 3. But #1: I wonder if that is too restrictive?
                # Note also that new code creates a request range by hop, where old did it by path
                # It is true I want all hops in path no xlate to get the same new tag
                # And it may be true I want their request ranges to match

            # Then for each hop
                # skip hops that didn't fail
                # If this is a hop that doexn't xlate, use that overallRange I gathered above as the new range_request
                # Else (this xlates) the new range request is the old less the previous suggested AND any unavails
                # For each hop we already did:
                    # If same URN diff hop, take the new done suggested out of this hop's range request
                    # FIXME: I think I need to append a hop I'm not changing to the resetHops list, so we also exclude tags
                    # being requested by hops that didn't fail

                    # Edit doneHop range request to exclude this hop's suggested if this hop failed. 

            # Pick a new tag For each failed hop
            newSugByPath = dict() # To store the tag for a path to make sure it is re-used as necessary
            for hop in failedHops:
                # For PG AMs, do not pick a tag that a hop on a different path is using
                if self.isPG:
                    for hop2 in newSugByHop.keys():
                        if hop2.path.id != hop.path.id:
                            if newSugByHop[hop2] <= nextRequestRangeByHop[hop] and newSugByHop[hop2] != VLANRange.fromString('any'):
                                nextRequestRangeByHop[hop] = nextRequestRangeByHop[hop] - newSugByHop[hop2]
                                self.logger.debug("For PG AM %s avoiding %s being used by %s", hop, newSugByHop[hop2], hop2)

                # Some error checking
                if len(hop._hop_link.vlan_range_request) == 0:
                    self.logger.debug("%s request_range was empty with unavail %s", hop, hop._hop_link.vlan_range_request, hop.vlans_unavailable)
                    self.inProcess = False
                    raise StitchingCircuitFailedError("Circuit reservation failed at %s and not enough available VLAN tags at %s to try again locally. Try again from the SCS" % (self, hop))

                pick = VLANRange.fromString('any')

                # If we have a tag for this path and this hop doesn't translate, then re-use that tag
                # FIXME: Really it's if this hop does not xlate or the next hop in the path on same AM does not xlate
                if newSugByPath.has_key(hop.path) and newSugByPath[hop.path] is not None and not hop._hop_link.vlan_xlate:
                    pick = newSugByPath[hop.path]
                    self.logger.debug("%s re-using already picked tag %s", hop, pick)
                else:
                    # Pick a new tag if we can
                    if hop._hop_link.vlan_producer:
                        self.logger.debug("%s is a vlan producer, so after all that let it pick any tag", hop)
                    elif len(nextRequestRangeByHop[hop]) == 0:
                        self.inProcess = False
                        self.logger.debug("%s nextRequestRange was empty but vlan_range_request was %s", hop, hop._hop_link.vlan_range_request)
                        raise StitchingCircuitFailedError("Circuit reservation failed at %s and not enough available VLAN tags at %s to try again locally. Try again from the SCS" % (self, hop))
                    else:
                        import random
                        pick = random.choice(list(nextRequestRangeByHop[hop]))
                        newSugByPath[hop.path]=VLANRange(pick)
                        self.logger.debug("%s picked new tag %s from range %s", hop, pick, nextRequestRangeByHop[hop])

                for hop2 in failedHops:
                    # For other failed hops with the same URN, make sure they cannot pick the tag we just picked
                    if hop2.urn == hop.urn and hop2.path.id != hop.path.id and hop2 != hop and pick != VLANRange.fromString('any') and \
                            VLANRange(pick) <= nextRequestRangeByHop[hop2]:
                        if hop2 in newSugByHop.keys():
                            # This other hop already picked!
                            if newSugByHop[hop2] == VLANRange(pick):
                                # duplicate pick
                                raise StitchingError("%s picked same new suggested VLAN tag %s at %s and %s" % (self, hop._hop_link.vlan_suggested_request, hop, hop2))
                            else:
                                self.logger.debug("%s already picked! Thankfully, a different tag", hop2)
                        nextRequestRangeByHop[hop2] = nextRequestRangeByHop[hop2] - VLANRange(pick)
                        self.logger.debug("%s telling %s not to pick its tag %s", hop, hop2, pick)

                        # Must also tell other failed hops on same path as this other hop2 to not pick my tag
                        for hop3 in failedHops:
                            if hop3.path.id == hop2.path.id and (not hop2._hop_link.vlan_xlate or not hop3._hop_link.vlan_xlate) and \
                                    VLANRange(pick) <= nextRequestRangeByHop[hop3]:
                                if hop3 in newSugByHop.keys():
                                    # This other hop already picked!
                                    if newSugByHop[hop3] == VLANRange(pick):
                                        # duplicate pick
                                        raise StitchingError("%s picked same new suggested VLAN tag %s at %s and %s" % (self, hop._hop_link.vlan_suggested_request, hop, hop3))
                                    else:
                                        self.logger.debug("%s already picked! Thankfully, a different tag", hop3)
                                nextRequestRangeByHop[hop3] = nextRequestRangeByHop[hop3] - VLANRange(pick)
                                self.logger.debug("%s telling %s not to pick its tag %s", hop, hop3, pick)

                self.logger.debug("handleUn on %s doing local retry: set Avail=%s, Sug=%s (Sug was %s)", hop, hop._hop_link.vlan_range_request, pick, hop._hop_link.vlan_suggested_request)
                newSugByHop[hop] = VLANRange(pick)
                hop._hop_link.vlan_suggested_request = VLANRange(pick)

                # Now error check against hops for which we already have a tag
                # For each hop we already picked a suggested for
                for hop2 in newSugByHop.keys():
                    # If it is same URN
                    if hop != hop2 and hop2.urn == hop.urn:
                        # And we didn't pick 'any'
                        if hop._hop_link.vlan_suggested_request != VLANRange.fromString("any"):
                            # If we picked the same tag, that's an error
                            if hop2._hop_link.vlan_suggested_request == hop._hop_link.vlan_suggested_request:
                                raise StitchingError("%s picked same new suggested VLAN tag %s at %s and %s" % (self, hop._hop_link.vlan_suggested_request, hop, hop2))
#                            # If we picked a tag that is in the range of tags to pick from for the other hop
#                            if hop._hop_link.vlan_suggested_request <= hop2._hop_link.vlan_range_request:
#                                # FIXME: Really? Exclude? Or does that over constrain me in future?
#                                hop2._hop_link.vlan_range_request = hop2._hop_link.vlan_range_request - hop._hop_link.vlan_suggested_request
#                                self.logger.debug("%s range request used to include new suggested %s for %s. New: %s", hop2, hop._hop_link.vlan_suggested_request, hop, hop2._hop_link.vlan_range_request)
#                            else:
#                                self.logger.debug("%s range request already excluded new suggested %s for %s: %s", hop2, hop._hop_link.vlan_suggested_request, hop, hop2._hop_link.vlan_range_request)

                    # Ticket #355: For PG/IG, ensure that other hops on other paths exclude newly picked tag from their range request
                    if self.isPG:
                        if hop != hop2 and hop.path.id != hop2.path.id:
                            # If we picked the same tag, that's an error
                            if hop2._hop_link.vlan_suggested_request == hop._hop_link.vlan_suggested_request and hop._hop_link.vlan_suggested_request != VLANRange.fromString('any'):
                                raise StitchingError("%s (PG AM) picked same new suggested VLAN tag %s at %s and %s" % (self, hop._hop_link.vlan_suggested_request, hop, hop2))

            # End loop over failed hops

            self.inProcess = False
            if self.localPickNewVlanTries == 1:
                timeStr = "1st"
            elif self.localPickNewVlanTries == 2:
                timeStr = "2nd"
            elif self.localPickNewVlanTries == 3:
                timeStr = "3rd"
            else:
                timeStr = "%dth" % self.localPickNewVlanTries
            if failedHop:
                msg = "Retry %s %s time with %s new suggested %s (not %s)" % (self, timeStr, failedHop, newSugByHop[failedHop], oldSugByHop[failedHop])
            else:
                msg = "Retry %s %s time with new suggested VLANs" % (self, timeStr)
            # This error is caught by Launcher, causing this AM to be put back in the ready pool
            raise StitchingRetryAggregateNewVlanError(msg)

        # End canDoRequestHere block to handle the vlan unavailable locally

# # The old code:
#         if False and canRedoRequestHere:
#             self.logger.debug("Trying OLD code block for picking new tag")
# #            self.logger.debug("After all checks looks like we can locally redo request for %s", self)
# 
#             hop = None
#             newSugByPath = dict()
#             oldSugByPath = dict()
# 
#             # FIXME Ticket #486
#             # On all paths for a given hop, exclude the tag that failed
#             #    And other hops at this AM on same path if no translation
#             # On any given path, exclude all tags marked unavailable for this hop on other paths
#             #    And other hops on same path if no translation
#             # On any given path for given hop, exclude tags in use by other paths
#             #    And other hops at this AM on same path if no translation
#             #    THIS IS THE BUG happening now
# 
#             # BUG happens for example with 2 links across a transit net: When picking a new tag for a hop,
#             # The code does not exclude tags already picked by other circuits at same hop
# 
#             # If # hops > 1 and hops do not do translation, then I need to pick a tag that all hops can use and set it on all the hops
#             # EG A transit network that does not do translation
# 
#             # Init some vars
#             newTagByPath = dict() # tag picked on a path with no xlation, by path
#             overallRangeByPath = dict() # new range request for failed hops
#             hopsNoXlateByPath = dict() # list of hops on a path with no xlation
#             resetHops = list() # done hops
#             for path in self.paths:
#                 newSugByPath[path] = VLANRange.fromString("any")
#                 oldSugByPath[path] = VLANRange.fromString("any")
#                 newTagByPath[path] = None # Tag to use on all such hops
#                 overallRangeByPath[path] = VLANRange.fromString("any")  # new request range to use on all such hops
#                 hopsNoXlateByPath[path] = [] # hops that don't do xlation
# 
#             # Gather the hops that don't do VLAN translation and the overall new request range to use for them
#             for hop in self.hops:
#                 path = hop.path
#                 if not hop._hop_link.vlan_xlate:
#                     hopsNoXlateByPath[path].append(hop)
#                     # New request range will be the intersection of the existing request ranges
#                     # FIXME: This may be a problem? Too restrictive?
#                     overallRangeByPath[path] = overallRangeByPath[path].intersection(hop._hop_link.vlan_range_request)
#                     # only subtract the request from last time if this hop is considered a failure
#                     if not failedHop or hop == failedHop or (hop.path == failedHop.path and (not hop._hop_link.vlan_xlate or not failedHop._hop_link.vlan_xlate)):
#                         self.logger.debug("Overall range for %s will exclude %s previous suggested %s", path, hop, hop._hop_link.vlan_suggested_request)
#                         overallRangeByPath[path] = overallRangeByPath[path] - hop._hop_link.vlan_suggested_request
# # This next elif is new.
#                     elif failedHop and failedHop.urn == hop.urn and failedHop != hop and hop.path != failedHop.path:
#                         # This hop didn't fail. But failed hop should exclude my suggested (since I'll keep it) and I should exclude
#                         # the hop that failed for the failed hop
#                         self.logger.debug("Overall range for %s will exclude %s previous suggested %s", failedHop.path, hop, hop._hop_link.vlan_suggested_request)
#                         overallRangeByPath[failedHop.path] = overallRangeByPath[failedHop.path] - hop._hop_link.vlan_suggested_request
# 
#                         self.logger.debug("Overall range for %s will exclude %s previous suggested %s", path, failedHop, failedHop._hop_link.vlan_suggested_request)
#                         overallRangeByPath[path] = overallRangeByPath[path] - failedHop._hop_link.vlan_suggested_request
# 
#                     # Exclude known unavails from this hop
#                     overallRangeByPath[path] = overallRangeByPath[path] - hop.vlans_unavailable
# 
#             for path in self.paths:
#                 self.logger.debug("New overallrange for %s: %s", path, overallRangeByPath[path])
# 
#             # FIXME: Should other hops exclude from their availRange a tag that another hop is using for its suggested (if a diff path)
# 
#             for hop in self.hops:
#                 path = hop.path
#                 # Edit vlan ranges only for the failed hop if set, plus other hops impacted by that
#                 if failedHop and hop != failedHop and (hop._hop_link.vlan_xlate or hop.path != failedHop.path or failedHop._hop_link.vlan_xlate):
#                     self.logger.debug("Not changing suggested /range requested for non failed %s", hop)
#                     resetHops.append(hop)
#                     # Must exclude this hop's suggested from the range the failed hop picks from
#                     # if the failed hop has the same URN
#                     # And if this is PG, must do that even if failed hop has diff URN
#                     # But I think that should happen below
#                     continue
# 
#                 # If we get here then this hop failed
# 
#                 # FIXME: If there is xlation on the path then this is not right for all hops on the path
#                 oldSugByPath[path] = hop._hop_link.vlan_suggested_request
# 
#                 # Set the new request range
#                 if len(hopsNoXlateByPath[path]) > 1 and hop in hopsNoXlateByPath[path]:
#                     # Use the intersection from above
#                     self.logger.debug("%s is a transit AM. Use same request range on all hops: %s", self, overallRangeByPath[path])
#                     hop._hop_link.vlan_range_request = overallRangeByPath[path]
#                 else:
#                     # pull old suggested out of range
#                     hop._hop_link.vlan_range_request = hop._hop_link.vlan_range_request - hop._hop_link.vlan_suggested_request
#                     # Also pull out any known unavail tags
#                     hop._hop_link.vlan_range_request = hop._hop_link.vlan_range_request - hop.vlans_unavailable
# 
#                 # If this hop has same URN as another hop on this AM but diff path, and that other hop has a newSug, then exclude from this range that newSug
#                 for doneHop in resetHops:
#                     if doneHop.urn == hop.urn and doneHop != hop and doneHop.path == hop.path:
#                         self.logger.warn("%s already handled and has same URN as %s and same path", doneHop, hop)
#                     if doneHop.urn == hop.urn and doneHop != hop and doneHop._hop_link.vlan_suggested_request != VLANRange.fromString("any"):
#                         if doneHop._hop_link.vlan_suggested_request <= hop._hop_link.vlan_range_request:
#                             # FIXME: If I start having problems running out of tags, this may be part of the issue
#                             # This is where having a nextRequestRange helps the new code path - I can exclude
#                             # a tag from picking it without taking it out of the request range
#                             hop._hop_link.vlan_range_request = hop._hop_link.vlan_range_request - doneHop._hop_link.vlan_suggested_request
#                             self.logger.debug("%s range request used to include new suggested %s for %s. New: %s", hop, doneHop._hop_link.vlan_suggested_request, doneHop, hop._hop_link.vlan_range_request)
#                         else:
#                             self.logger.debug("%s range request already excluded new suggested %s for %s: %s", hop, doneHop._hop_link.vlan_suggested_request, doneHop, hop._hop_link.vlan_range_request)
#                     # If this hop/tag failed, then exclude that failed tag from other hops with same URN
#                     if doneHop.urn == hop.urn and doneHop != hop and (not failedHop or hop == failedHop or (hop.path==failedHop.path and (not hop._hop_link.vlan_xlate or not failedHop._hop_link.vlan_xlate))):
#                         if doneHop._hop_link.vlan_suggested_request<=hop._hop_link.vlan_suggested_request:
#                             self.logger.debug("%s failed and previously used %s, but other hop %s is now trying it. FIXME!", hop, hop._hop_link.vlan_suggested_request, doneHop)
# 
#                         doneHop._hop_link.vlan_range_request = doneHop._hop_link.vlan_range_request - hop._hop_link.vlan_suggested_request
#                         self.logger.debug("Reset %s range request to exclude %s previous failed tag %s. New: %s", doneHop, hop, hop._hop_link.vlan_suggested_request, doneHop._hop_link.vlan_range_request)
# 
#                     # Ticket #355: If this is PG/IG, then any hop on a different path: it's new suggested should not be in the new range request here
#                     if self.isPG:
#                         if doneHop.path.id != hop.path.id:
#                             if doneHop._hop_link.vlan_suggested_request != VLANRange.fromString('any') and \
#                                     doneHop._hop_link.vlan_suggested_request <= hop._hop_link.vlan_range_request:
#                                 # FIXME: If I start having problems running out of tags, this may be part of the issue
#                                 # This is where having a nextRequestRange helps the new code path - I can exclude
#                                 # a tag from picking it without taking it out of the request range
#                                 hop._hop_link.vlan_range_request = hop._hop_link.vlan_range_request - doneHop._hop_link.vlan_suggested_request
#                                 self.logger.debug("PG %s now excluding %s suggested %s from request range: %s", hop, doneHop, \
#                                                       doneHop._hop_link.vlan_suggested_request, hop._hop_link.vlan_range_request)
# 
#                 # end of loop over done hops
# 
#                 # Now ready to pick a new tag for this hop
# 
#                 # If self is a VLAN producer, then set newSug to VLANRange('any') and let it pick?
#                 if hop._hop_link.vlan_producer:
#                     newSugByPath[path] = VLANRange.fromString('any')
#                 elif len(hop._hop_link.vlan_range_request) == 0:
#                     self.inProcess = False
#                     raise StitchingCircuitFailedError("Circuit reservation failed at %s and not enough available VLAN tags at %s to try again locally. Try again from the SCS" % (self, hop))
#                 else:
#                     # Pick a random tag from range
#                     import random
#                     newSugByPath[path] = VLANRange(random.choice(list(hop._hop_link.vlan_range_request)))
# 
#                     # FIXME: Make sure that newSug is not the pick on another hop on this AM on diff path with same URN
#                     # And make sure it is excluded from the range_request on other such hops
#                     # I _think_ that is covered by the above doneHops loop, but a check here wouldn't hurt
# 
#                 # If EG this is a transit AM not doing xlation, then keep the previously selected
#                 # new tag if any, or save the one we just picked here to use on the other hops at this AM
#                 if len(hopsNoXlateByPath[path]) > 1 and hop in hopsNoXlateByPath[path]:
#                     if newTagByPath[path]:
#                         self.logger.debug("%s is a transit network. Don't use selected tag %s, but use tag picked for other hop %s", self, newSugByPath[path], newTagByPath[path])
#                         newSugByPath[path] = newTagByPath[path]
#                     else:
#                         self.logger.debug("%s is a transit network. Save selected tag %s for other hops", self, newSugByPath[path])
#                         newTagByPath[path] = newSugByPath[path]
# 
#                 # Set that as suggested
#                 hop._hop_link.vlan_suggested_request = VLANRange(newSugByPath[path])
#                 self.logger.debug("handleUn on %s doing local retry: set Avail=%s, Sug=%s (Sug was %s)", hop, hop._hop_link.vlan_range_request, newSugByPath[path], oldSugByPath[path])
# 
#                 # FIXME: Set hops that depend on this hop to the proper values, or let those happen naturally?
# 
#                 # Make sure any other hops on same Link exclude from their range request the VLAN suggested here
#                 for doneHop in resetHops:
#                     if doneHop.urn == hop.urn and doneHop._hop_link.vlan_suggested_request == hop._hop_link.vlan_suggested_request and hop._hop_link.vlan_suggested_request != VLANRange.fromString("any"):
#                         raise StitchingError("%s picked same new suggested VLAN tag %s at %s and %s" % (self, hop._hop_link.vlan_suggested_request, hop, doneHop))
# 
#                     # FIXME: Does this overconstrain things in future?
#                     # FIXME: If I start having problems running out of tags, this may be part of the issue
#                     # This is where having a nextRequestRange helps the new code path - I can exclude
#                     # a tag from picking it without taking it out of the request range
#                     if doneHop.urn == hop.urn and hop._hop_link.vlan_suggested_request != VLANRange.fromString("any"):
#                         if hop._hop_link.vlan_suggested_request <= doneHop._hop_link.vlan_range_request:
#                             doneHop._hop_link.vlan_range_request = doneHop._hop_link.vlan_range_request - hop._hop_link.vlan_suggested_request
#                             self.logger.debug("%s range request used to include new suggested %s for %s. New: %s", doneHop, hop._hop_link.vlan_suggested_request, hop, doneHop._hop_link.vlan_range_request)
#                         else:
#                             self.logger.debug("%s range request already excluded new suggested %s for %s: %s", doneHop, hop._hop_link.vlan_suggested_request, hop, doneHop._hop_link.vlan_range_request)
# 
#                     # Ticket #355: For PG/IG, ensure that other hops on other paths exclude newly picked tag from their range request
#                     if self.isPG:
#                         if doneHop.path.id != hop.path.id and hop._hop_link.vlan_suggested_request != VLANRange.fromString("any"):
#                             if doneHop._hop_link.vlan_suggested_request == hop._hop_link.vlan_suggested_request:
#                                 raise StitchingError("%s is a ProtoGENI AM and %s is requesting the same tag (%s) as a hop on a different path %s" % \
#                                                          (self, hop, hop._hop_link.vlan_suggested_request, doneHop))
#                             # FIXME: If I start having problems running out of tags, consider removing this block
#                             # This is where having a nextRequestRange helps the new code path - I can exclude
#                             # a tag from picking it without taking it out of the request range
#                             if hop._hop_link.vlan_suggested_request <= doneHop._hop_link.vlan_range_request:
#                                 doneHop._hop_link.vlan_range_request = doneHop._hop_link.vlan_range_request - hop._hop_link.vlan_suggested_request
#                                 self.logger.debug("PG AM: Must exclude %s sugg %s from %s range.", hop, hop._hop_link.vlan_suggested_request, doneHop)
#                 # End of loop over done Hops
#                 resetHops.append(hop)
#             # End of Loop over hops to set new suggested request and range request
# 
#             self.inProcess = False
#             if self.localPickNewVlanTries == 1:
#                 timeStr = "1st"
#             elif self.localPickNewVlanTries == 2:
#                 timeStr = "2nd"
#             elif self.localPickNewVlanTries == 3:
#                 timeStr = "3rd"
#             else:
#                 timeStr = "%dth" % self.localPickNewVlanTries
#             if failedHop:
#                 msg = "Retry %s %s time with %s new suggested %s (not %s)" % (self, timeStr, failedHop, newSugByPath[failedHop.path], oldSugByPath[failedHop.path])
#             else:
#                 msg = "Retry %s %s time with new suggested VLANs" % (self, timeStr)
#             # This error is caught by Launcher, causing this AM to be put back in the ready pool
#             raise StitchingRetryAggregateNewVlanError(msg)
# 
#         # End of block to handle redoing request locally

        # If we got here, we can't handle this locally
        self.logger.debug("%s failure could not be redone locally", self)

        if not self.userRequested:
            # Exit to SCS
            # If we've tried this AM a few times, set its hops to be excluded
            if self.allocateTries > self.MAX_TRIES:
                self.logger.debug("%s allocation failed %d times - try excluding its hops", self, self.allocateTries)
                for hop in self.hops:
                    self.logger.debug
                    hop.excludeFromSCS = True
            self.inProcess = False
            raise StitchingCircuitFailedError("Circuit reservation failed at %s. Try again from the SCS" % self)
        else:
            # Exit to User
            raise StitchingError("Stitching failed trying %s at %s: %s" % (opName, self, exception))
# FIXME FIXME: Go back to SCS here too? Or will that thrash?
#            self.inProcess = False
#            raise StitchingCircuitFailedError("Circuit failed at %s. Try again from the SCS" % self)

    def deleteReservation(self, opts, slicename):
        '''Delete any previous reservation/manifest at this AM'''
        self.completed = False
        
        # Clear old manifests
        self.manifestDom = None
        for hop in self.hops:
            hop._hop_link.vlan_suggested_manifest = None
            hop._hop_link.vlan_range_manifest = None

        # Now mark all AMs that depend on this AM as incomplete, so we'll try them again
        # FIXME: This makes everything in chain get redone. Could we mark only the immediate
        # children, so only if those get deleted do their children get marked? Note the cost
        # isn't so high - it means falling into this code block and doing the above logic
        # that discovers existing manifests
        for agg in self.isDependencyFor:
            agg.completed = False

        # FIXME: Set a flag marking it is being deleted? Set inProcess?

        # Delete the previous reservation
        # FIXME: Do we do something with log level or log format or file for omni calls?
        # FIXME: Supply --raiseErrorOnAMAPIV2Error?
        opName = 'deletesliver'
        if self.api_version > 2:
            opName = 'delete'
        if opts.warn:
            omniargs = ['-V%d' % self.api_version,'--raise-error-on-v2-amapi-error', '-a', self.url, opName, slicename]
        else:
            omniargs = ['-V%d' % self.api_version,'--raise-error-on-v2-amapi-error', '-o', '-a', self.url, opName, slicename]

        self.logger.info("Doing %s at %s", opName, self.url)
        if not opts.fakeModeDir:
            try:
                self.inProcess = True
#                (text, (successList, fail)) = self.doOmniCall(omniargs, opts)
                (text, result) = self.doAMAPICall(omniargs, opts, opName, slicename, 1, suppressLogs=True)
                self.inProcess = False
                if self.api_version == 2:
                    (successList, fail) = result
                    if not self.url in successList:
                        raise StitchingError("Failed to delete prior reservation at %s: %s" % (self.url, text))
                    else:
                        self.logger.debug("%s %s Result: %s", opName, self, text)
                else:
                    # API v3
                    retCode = 0
                    try:
                        retCode = result[self.url]["code"]["geni_code"]
                    except:
                        # Malformed return - treat as error
                        raise StitchingError("Failed to delete prior reservation at %s (malformed return): %s" % (self.url, text))
                    if retCode != 0:
                        raise StitchingError("Failed to delete prior reservation at %s: %s" % (self.url, text))
                    # need to check status of slivers to ensure they are all deleted
                    try:
                        for sliver in result[self.url]["value"]:
                            status = sliver["geni_allocation_status"]
                            if status != 'geni_unallocated':
                                if sliver.has_key("geni_error"):
                                    text = text + "; " + sliver["geni_error"]
                                raise StitchingError("Failed to delete prior reservation at %s for sliver %s: %s" % (self.url, sliver["geni_sliver_urn"], text))
                    except:
                        # Malformed return I think
                        raise StitchingError("Failed to delete prior reservation at %s (malformed return): %s" % (self.url, text))

            except OmniError, e:
                self.inProcess = False
                self.logger.error("Failed to %s at %s: %s", opName, self, e)
                raise StitchingError(e) # FIXME: Right way to re-raise?

        self.inProcess = False
        # FIXME: Fake mode delete results from a file?

        # FIXME: Set a flag marking this AM was deleted?
        return

    # This needs to handle createsliver, allocate, sliverstatus, listresources at least
    # suppressLogs makes Omni part log at WARN and up only
    def doAMAPICall(self, args, opts, opName, slicename, ctr, suppressLogs=False):
        # FIXME: Take scsCallCount as well?
        gotBusy = False
        busyCtr = 0
        text = ""
        result = None
        while busyCtr < self.BUSY_MAX_TRIES:
            try:
                ctr = ctr + 1
                if opts.fakeModeDir:
                    (text, result) = self.fakeAMAPICall(args, opts, opName, slicename, ctr)
                else:
                    (text, result) = self.doOmniCall(args, opts, suppressLogs)
                break # Not an error - breakout of loop
            except AMAPIError, ae:
                if is_busy_reply(ae.returnstruct):
                    self.logger.debug("%s got BUSY doing %s", self, opName)
                    time.sleep(self.BUSY_POLL_INTERVAL_SEC)
                    busyCtr = busyCtr + 1
                    if busyCtr == self.BUSY_MAX_TRIES:
                        raise ae
                    text = str(ae)
                else:
                    raise ae
        return (text, result)

    # suppressLogs makes Omni part log at WARN and up only
    def doOmniCall(self, args, opts, suppressLogs=False):
        # spawn a thread if threading
        if suppressLogs and not opts.debug:
            logging.disable(logging.INFO)
        res = None
        try:
            res = omni.call(args, opts)
        except:
            raise
        finally:
            if suppressLogs:
                logging.disable(logging.NOTSET)
        return res

    # This needs to handle createsliver, allocate, sliverstatus, listresources at least
    # FIXME FIXME: Need more fake result files and to clean this all up! ****
    def fakeAMAPICall(self, args, opts, opName, slicename, ctr):
        # FIXME: Take scsCallCount as well?
        self.logger.info("Doing FAKE %s at %s", opName, self)

        # FIXME: Maybe take the request filename and make a -p arg for finding the canned files?
        # Or if I really use the scs, save the SCS in a file with the -p so I can find it here?

        # derive filename
        # FIXME: Take the expanded request from the SCS and pretend it is the manifest
        # That way, we get the VLAN we asked for
        resultPath = Aggregate.FAKEMODESCSFILENAME

#        # For now, results file only has a manifest. No JSON
#        resultFileName = _construct_output_filename(opts, slicename, self.url, self.urn, opName+'-result'+str(ctr), '.json', 1)
#        resultPath = os.path.join(opts.fakeModeDir, resultFileName)
#        if not os.path.exists(resultPath):
#            resultFileName = _construct_output_filename(opts, slicename, self.url, self.urn, opName+'-result'+str(ctr), '.xml', 1)
#            resultPath = os.path.join(opts.fakeModeDir, resultFileName)
        if not resultPath or not os.path.exists(resultPath):
            if opName in ("allocate", "createsliver"):
                # Fallback fake mode behavior
                time.sleep(random.randrange(1, 6))
                for hop in self.hops:
                    hop._hop_link.vlan_suggested_manifest = hop._hop_link.vlan_suggested_request
                    hop._hop_link.vlan_range_manifest = hop._hop_link.vlan_range_request
                self.logger.warn("Did fallback fake mode allocate")
                msg = "Did fallback fake %s" % opName
                return (msg, msg)
            else:
                raise StitchingError("Failed to find fake results file using %s" % resultFileName)

        self.logger.info("Reading FAKE %s results from %s", opName, resultPath)
        resultJSON = None
        result = None
        # Read in the file, trying as JSON
        try:
            with open(resultPath, 'r') as file:
                resultsString = file.read()
            try:
                resultJSON = json.loads(resultsString, encoding='ascii')
            except Exception, e2:
#                self.logger.debug("Failed to read fake results as json: %s", e2)
                result = resultsString
        except Exception, e:
            self.logger.error("Failed to read result string from %s: %s", resultPath, e)
            # FIXME
            raise e
        if resultJSON:
            # Got JSON - check for normal return struct
            if isinstance(resultJSON, dict) and resultJSON.has_key("code") and isinstance(resultJSON["code"], dict) and \
                    resultJSON["code"].has_key("geni_code"):
                # If success, return the value as the result
                if resultJSON["code"]["geni_code"] == 0:
                    if resultJSON["code"].has_key("value"):
                        result = resultJSON["code"]["value"]
                    else:
                        raise StitchingError("Malformed result struct from %s claimed success but had no value" % resultPath)
                else:
                    # Not success - raise it as an AMAPIError
                    raise AMAPIError("Fake failure doing %s at %s from file %s" % (opName, self.url, resultPath), resultJSON)
            else:
                # Malformed struct - maybe this is a real result as is
                result = resultJSON
        else:
            # Not JSON - return as real result
            result = resultsString
        return ("Fake %s at %s from file %s" % (opName, self.url, resultPath), result)

class Hop(object):
    # A hop on a path in the stitching element
    # Note this is path specific (and has a path reference)

    # XML tag constants
    ID_TAG = 'id'
    TYPE_TAG = 'type'
    LINK_TAG = 'link'
    NEXT_HOP_TAG = 'nextHop'

    @classmethod
    def fromDOM(cls, element):
        """Parse a stitching hop from a DOM element."""
        # FIXME: getAttributeNS?
        id = element.getAttribute(cls.ID_TAG)
        isLoose = False
        if element.hasAttribute(cls.TYPE_TAG):
            hopType = element.getAttribute(cls.TYPE_TAG)
            if hopType.lower().strip() == 'loose':
                isLoose = True
        hop_link = None
        next_hop = None
        for child in element.childNodes:
            if child.localName == cls.LINK_TAG:
                hop_link = HopLink.fromDOM(child)
            elif child.localName == cls.NEXT_HOP_TAG:
                next_hop = child.firstChild.nodeValue
                if next_hop == 'null':
                    next_hop = None
        hop = Hop(id, hop_link, next_hop)
        if isLoose:
            hop.loose = True
        return hop

    def __init__(self, id, hop_link, next_hop):
        self._id = id
        self._hop_link = hop_link
        self._next_hop = next_hop
        self._path = None
        self._aggregate = None
        self._import_vlans = False
        self._dependencies = []
        self.idx = None
        self.logger = logging.getLogger('stitch.Hop')
        self.import_vlans_from = None # a pointer to another hop

        # If True, then next request to SCS should explicitly
        # mark this hop as loose
        self.loose = False

        # Set to true so later call to SCS will explicitly exclude this Hop
        self.excludeFromSCS = False

        # VLANs we know are not possible here - cause of VLAN_UNAVAILABLE
        # or cause a suggested was not picked.
        # Use this to avoid picking these later
        self.vlans_unavailable = VLANRange()

    def __str__(self):
        return "<Hop %r on path %r>" % (self.urn, self._path.id)

    @property
    def urn(self):
        return self._hop_link and self._hop_link.urn

    @property
    def aggregate(self):
        return self._aggregate

    @property
    def path(self):
        return self._path

    @path.setter
    def path(self, path):
        self._path = path

    @aggregate.setter
    def aggregate(self, agg):
        self._aggregate = agg

    @property
    def import_vlans(self):
        return self._import_vlans

    @import_vlans.setter
    def import_vlans(self, value):
        self._import_vlans = value

    @property
    def dependsOn(self):
        return self._dependencies

    def add_dependency(self, hop):
        self._dependencies.append(hop)

    def editChangesIntoDom(self, domHopNode):
        '''Edit any changes made in this element into the given DomNode'''
        # Note the parent RSpec object's dom is not touched, unless the given node is from that document
        # Here we just like the HopLink do its thing

        # Incoming node should be the node for this hop
        nodeId = domHopNode.getAttribute(self.ID_TAG)
        if nodeId != self._id:
            raise StitchingError("%s given Dom node with different Id: %s" % (self, nodeId))

        # Mark hop explicitly loose if necessary
        if self.loose:
            domHopNode.setAttribute(self.TYPE_TAG, 'loose')

        for child in domHopNode.childNodes:
            if child.localName == self.LINK_TAG:
#                self.logger.debug("%s editChanges calling _hop_link with node %r", self, child)
                self._hop_link.editChangesIntoDom(child)

class RSpec(GENIObject):
    '''RSpec'''
    __simpleProps__ = [ ['stitching', Stitching] ]

    def __init__(self, stitching=None): 
        super(RSpec, self).__init__()
        self.stitching = stitching
        self._nodes = []
        self._links = [] # Main body links
        # DOM used to construct this: edits to objects are not reflected here
        self.dom = None
        # Note these are not Aggregate objects to avoid any loops
        self.amURNs = set() # AMs mentioned in the RSpec

    @property
    def nodes(self):
        return self._nodes

    @nodes.setter
    def nodes(self, nodeList):
        self._setListProp('nodes', nodeList, Node)

    @property
    def links(self):
        # Gets main body link elements
        return self._links

    @links.setter
    def links(self, linkList):
        self._setListProp('links', linkList, Link)

    def find_path(self, link_id):
        """Find the stitching path with the given id and return it. If no path
        matches the given id, return None.
        """
        return self.stitching and self.stitching.find_path(link_id)

    def find_link(self, hop_urn):
        """Find the main body link with the given id and return it. If no link
        matches the given id, return None.
        """
        for link in self._links:
            if link.id == link_id:
                return link
        return None

    # Get a DOM version of this RSpec that includes any edits to link -> property elements
    def getLinkEditedDom(self):
        # find all link nodes in dom
        dom = self.dom.cloneNode(True)
        rspecs = dom.getElementsByTagName(defs.RSPEC_TAG)
        # Gather the link nodes
        linkNodes = []
        if not rspecs or len(rspecs) == 0:
            return dom

        for link in self._links:
            domNode = link.findDomNode(rspecs[0])

            # Make sure we have a component_manager element for all implicit AMs on the link
            cms = []
            for child in domNode.childNodes:
                if child.localName == Link.COMPONENT_MANAGER_TAG:
                    cms.append(child.getAttribute(Link.NAME_TAG))
            for agg in link.aggregates:
                if agg.urn not in cms:
                    cme = domNode.ownerDocument.createElement(Link.COMPONENT_MANAGER_TAG)
                    cme.setAttribute(Link.NAME_TAG, agg.urn)
                    domNode.appendChild(cme)

            # Make sure we have the 2 property elements
#            print "Outputting link %s with %d props" % (link.id, len(link.properties))
            for prop in link.properties:
                prop.addOrEditIntoLinkDom(domNode)
        return dom

class Node(GENIObject):
    CLIENT_ID_TAG = 'client_id'
    COMPONENT_MANAGER_ID_TAG = 'component_manager_id'
    INTERFACE_TAG = "interface"

    @classmethod
    def fromDOM(cls, element):
        """Parse a Node from a DOM element."""
        # FIXME: getAttributeNS?
        client_id = element.getAttribute(cls.CLIENT_ID_TAG)
        amID = element.getAttribute(cls.COMPONENT_MANAGER_ID_TAG)
        # Get the interfaces. Need those to get the client_id so from the link I can find the AM
        ifcs = []
        for child in element.childNodes:
            if child.localName == cls.INTERFACE_TAG:
                if child.hasAttribute(cls.CLIENT_ID_TAG):
                    ifcs.append(child.getAttribute(cls.CLIENT_ID_TAG))
        return Node(client_id, amID, ifcs)

    def __init__(self, client_id, amID, ifc_ids = []):
        super(Node, self).__init__()
        self.id = client_id
        self.amURN = amID
        self.interface_ids = ifc_ids

class LinkProperty(GENIObject):
    # A property element inside a main body link
    CAPACITY_TAG = "capacity"
    DEST_TAG = "dest_id" # node interface or 1 of the interface_ref elements
    LATENCY_TAG = "latency" # 0
    PACKETLOSS_TAG = "packet_loss" # 0
    SOURCE_TAG = "source_id"

    def __init__(self, s_id, d_id, lat=None, pl=None, cap=None):
        self.source_id = s_id
        self.dest_id = d_id
        self.latency = lat
        self.packet_loss = pl
        self.capacity = cap
        self.link = None

    def addOrEditIntoLinkDom(self, linkNode):
        if not linkNode:
            return
        found = False
        for child in linkNode.childNodes:
            if child.localName == Link.PROPERTY_TAG:
                d_id = child.getAttribute(LinkProperty.DEST_TAG)
                s_id = child.getAttribute(LinkProperty.SOURCE_TAG)
                if d_id == self.dest_id and s_id == self.source_id:
                    self.editChangesIntoDom(child)
                    found = True
                    break
        if not found:
            self.addDomNode(linkNode)

    def addDomNode(self, linkNode):
        selfNode = linkNode.ownerDocument.createElement(Link.PROPERTY_TAG)
        selfNode.setAttribute(self.SOURCE_TAG, self.source_id)
        selfNode.setAttribute(self.DEST_TAG, self.dest_id)
        self.editChangesIntoDom(selfNode)
        linkNode.appendChild(selfNode)

    def editChangesIntoDom(self, propertyDomNode):
        if propertyDomNode.hasAttribute(self.SOURCE_TAG):
            s_id = propertyDomNode.getAttribute(self.SOURCE_TAG)
            if s_id != self.source_id:
                raise StitchingError("LinkProperty got wrong dom node. DOM source %s != My %s" % (s_id, self.source_id))
        if propertyDomNode.hasAttribute(self.DEST_TAG):
            d_id = propertyDomNode.getAttribute(self.DEST_TAG)
            if d_id != self.dest_id:
                raise StitchingError("LinkProperty got wrong dom node. DOM dest %s != My %s" % (d_id, self.dest_id))

        # Now set or add attributes for each of lat, cap, pl if they are not None
        if self.latency is not None:
            propertyDomNode.setAttribute(self.LATENCY_TAG, str(self.latency))
        if self.packet_loss is not None:
            propertyDomNode.setAttribute(self.PACKETLOSS_TAG, str(self.packet_loss))
        if self.capacity is not None:
            propertyDomNode.setAttribute(self.CAPACITY_TAG, str(self.capacity))

class Link(GENIObject):
    # A link from the main body of the rspec
    # Note the link client_id matches the hop_urn from the workflow matches the HopLink ID

    __ID__ = validateTextLike
    __simpleProps__ = [ ['client_id', str]]

    # XML tag constants
    CLIENT_ID_TAG = 'client_id'
    COMPONENT_MANAGER_TAG = 'component_manager'
    INTERFACE_REF_TAG = 'interface_ref'
    NAME_TAG = 'name'
    SHARED_VLAN_TAG = 'link_shared_vlan'
    LINK_TYPE_TAG = 'link_type'
    VLAN_LINK_TYPE = 'vlan'
    PROPERTY_TAG = 'property'

    @classmethod
    def fromDOM(cls, element):
        """Parse a Link from a DOM element."""
        # FIXME: getAttributeNS?
        client_id = element.getAttribute(cls.CLIENT_ID_TAG)
        refs = []
        aggs = []
        props = []
        hasSharedVlan = False
        typeName = cls.VLAN_LINK_TYPE
        for child in element.childNodes:
            if child.localName == cls.COMPONENT_MANAGER_TAG:
                name = child.getAttribute(cls.NAME_TAG)
                agg = Aggregate.find(name)
                if not agg in aggs:
                    aggs.append(agg)
            elif child.localName == cls.INTERFACE_REF_TAG:
                # FIXME: getAttributeNS?
                c_id = child.getAttribute(cls.CLIENT_ID_TAG)
                ir = InterfaceRef(c_id)
                refs.append(ir)
            # If the link has the shared_vlan extension, note this - not a stitching reason
            elif child.localName == cls.SHARED_VLAN_TAG:
#                print 'got shared vlan'
                hasSharedVlan = True
            elif child.localName == cls.LINK_TYPE_TAG:
                name = child.getAttribute(cls.NAME_TAG)
                typeName = str(name).strip().lower()
            elif child.localName == cls.PROPERTY_TAG:
                d_id = None
                s_id = None
                lat = None
                pl = None
                cap = None
                if child.hasAttribute(LinkProperty.DEST_TAG):
                    d_id = child.getAttribute(LinkProperty.DEST_TAG)
                if child.hasAttribute(LinkProperty.SOURCE_TAG):
                    s_id = child.getAttribute(LinkProperty.SOURCE_TAG)
                if child.hasAttribute(LinkProperty.LATENCY_TAG):
                    lat = child.getAttribute(LinkProperty.LATENCY_TAG)
                if child.hasAttribute(LinkProperty.PACKETLOSS_TAG):
                    pl = child.getAttribute(LinkProperty.PACKETLOSS_TAG)
                if child.hasAttribute(LinkProperty.CAPACITY_TAG):
                    cap = child.getAttribute(LinkProperty.CAPACITY_TAG)
#                print "Link %s Parsed property s %s d %s cap %s" % (client_id, s_id, d_id, cap)
                prop = LinkProperty(s_id, d_id, lat, pl, cap)
                props.append(prop)
        link = Link(client_id)
        link.aggregates = aggs
        link.interfaces = refs
        for prop in props:
            prop.link = link
        link.properties = props
        link.hasSharedVlan = hasSharedVlan
        link.typeName = typeName
        return link

    def __init__(self, client_id):
        super(Link, self).__init__()
        self.id = client_id
        self._aggregates = []
        self._interfaces = []
        self._props = []
        self.hasSharedVlan = False
        self.typeName = self.VLAN_LINK_TYPE

    @property
    def interfaces(self):
        return self._interfaces

    @interfaces.setter
    def interfaces(self, interfaceList):
        self._setListProp('interfaces', interfaceList, InterfaceRef)

    @property
    def aggregates(self):
        return self._aggregates

    @aggregates.setter
    def aggregates(self, aggregateList):
        self._setListProp('aggregates', aggregateList, Aggregate)

    @property
    def properties(self):
        return self._props

    @properties.setter
    def properties(self, propertyList):
        self._setListProp('props', propertyList, LinkProperty)

    def findDomNode(self, parentNode):
        if parentNode is None:
            return None
        for child in parentNode.childNodes:
            if child.localName == defs.LINK_TAG:
                client_id = child.getAttribute(Link.CLIENT_ID_TAG)
                if client_id == self.id:
                    return child
        return None


class InterfaceRef(object):
     def __init__(self, client_id):
         self.client_id = client_id


class HopLink(object):
    # From the stitching element, the link on the hop on a path
    # Note this is Path specific

    # XML tag constants
    ID_TAG = 'id'
    HOP_TAG = 'hop'
    VLAN_TRANSLATION_TAG = 'vlanTranslation'
    VLAN_RANGE_TAG = 'vlanRangeAvailability'
    VLAN_SUGGESTED_TAG = 'suggestedVLANRange'
    SCD_TAG = 'switchingCapabilityDescriptor'
    SCSI_TAG = 'switchingCapabilitySpecificInfo'
    SCSI_L2_TAG = 'switchingCapabilitySpecificInfo_L2sc'
    CAPABILITIES_TAG = 'capabilities'
    CAPABILITY_TAG = 'capability'

    @classmethod
    def fromDOM(cls, element):
        """Parse a stitching path from a DOM element."""
        # FIXME: getAttributeNS?
        id = element.getAttribute(cls.ID_TAG)
        # FIXME: getElementsByTagNameNS?
        vlan_xlate = element.getElementsByTagName(cls.VLAN_TRANSLATION_TAG)
        if vlan_xlate:
            # If no firstChild or no nodeValue, assume false
            if len(vlan_xlate) > 0 and vlan_xlate[0].firstChild:
                x = vlan_xlate[0].firstChild.nodeValue
            else:
                x = 'False'
            vlan_translate = x.lower() in ('true')
        vlan_range = element.getElementsByTagName(cls.VLAN_RANGE_TAG)
        if vlan_range:
            # vlan_range may have no child or no nodeValue. Meaning would then be 'any'
            if len(vlan_range) > 0 and vlan_range[0].firstChild:
                vlan_range_value = vlan_range[0].firstChild.nodeValue
            else:
                vlan_range_value = "any"
            vlan_range_obj = VLANRange.fromString(vlan_range_value)
        else:
            vlan_range_obj = VLANRange()            
        vlan_suggested = element.getElementsByTagName(cls.VLAN_SUGGESTED_TAG)
        if vlan_suggested:
            # vlan_suggested may have no child or no nodeValue. Meaning would then be 'any'
            if len(vlan_suggested) > 0 and vlan_suggested[0].firstChild:
                vlan_suggested_value = vlan_suggested[0].firstChild.nodeValue
            else:
                vlan_suggested_value = "any"                
            vlan_suggested_obj = VLANRange.fromString(vlan_suggested_value)
        else:
            vlan_suggested_obj = VLANRange()            
        hoplink = HopLink(id)
        hoplink.vlan_xlate = vlan_translate
        hoplink.vlan_range_request = vlan_range_obj
        hoplink.vlan_suggested_request = vlan_suggested_obj

        # Extract the advertised capabilities
        capabilities = element.getElementsByTagName(cls.CAPABILITIES_TAG)
        if capabilities and len(capabilities) > 0 and capabilities[0].childNodes:
            hoplink.vlan_producer = False
            hoplink.vlan_consumer = False
            capabilityNodes = capabilities[0].getElementsByTagName(cls.CAPABILITY_TAG)
            if capabilityNodes and len(capabilityNodes) > 0:
                for capability in capabilityNodes:
                    if capability.firstChild:
                        cap = str(capability.firstChild.nodeValue).strip().lower()
                        hoplink.capabilities.append(cap)
                        if cap == defs.PRODUCER_VALUE or cap == defs.VLANPRODUCER_VALUE:
                            hoplink.vlan_producer = True
                        elif cap == defs.CONSUMER_VALUE or cap == defs.VLANCONSUMER_VALUE:
                            hoplink.vlan_consumer = True
        return hoplink

    def __init__(self, urn):
        self.urn = urn
        self.vlan_xlate = False

        self.vlan_range_request = ""
        self.vlan_suggested_request = None
        self.vlan_range_manifest = ""
        self.vlan_suggested_manifest = None

        # If nothing advertised, assume AM only accepts tags
        self.vlan_producer = False
        self.vlan_consumer = True
        self.capabilities = [] # list of string capabilities

        self.logger = logging.getLogger('stitch.HopLink')

    def editChangesIntoDom(self, domNode, request=True):
        '''Edit any changes made in this element into the given DomNode'''
        # Note that the parent RSpec object's dom is not touched, unless this domNode is from that
        # Here we edit in the new vlan_range and vlan_available
        # If request is False, use the manifest values. Otherwise, use requested.

        # Incoming node should be the node for this hop
        nodeId = domNode.getAttribute(self.ID_TAG)
        if nodeId != self.urn:
            raise StitchingError("Hop Link %s given Dom node with different Id: %s" % (self, nodeId))

        if request:
            newVlanRangeString = str(self.vlan_range_request).strip()
            newVlanSuggestedString = str(self.vlan_suggested_request).strip()
        else:
            newVlanRangeString = str(self.vlan_range_manifest).strip()
            newVlanSuggestedString = str(self.vlan_suggested_manifest).strip()

        vlan_range = domNode.getElementsByTagName(self.VLAN_RANGE_TAG)
        if vlan_range and len(vlan_range) > 0:
            # vlan_range may have no child or no nodeValue. Meaning would then be 'any'
            if vlan_range[0].firstChild:
                # Set the value
                vlan_range[0].firstChild.nodeValue = newVlanRangeString
#                self.logger.debug("Set vlan range on node %r: %s", vlan_range[0], vlan_range[0].firstChild.nodeValue)
            else:
                vlan_range[0].appendChild(domNode.ownerDocument.createTextNode(newVlanRangeString))
        else:
            vlanRangeNode = domNode.ownerDocument.createElement(self.VLAN_RANGE_TAG)
            vlanRangeNode.appendChild(domNode.ownerDocument.createTextNode(newVlanRangeString))
            # Find the switchingCapabilitySpecificInfo_L2sc node and append it there
            l2scNodes = domNode.getElementsByTagName('switchingCapabilitySpecificInfo_L2sc')
            if l2scNodes and len(l2scNodes) > 0:
                l2scNodes[0].appendChild(vlanRangeNode)

        vlan_suggested = domNode.getElementsByTagName(self.VLAN_SUGGESTED_TAG)
        if vlan_suggested and len(vlan_suggested) > 0:
            # vlan_suggested may have no child or no nodeValue. Meaning would then be 'any'
            if vlan_suggested[0].firstChild:
                # Set the value
                vlan_suggested[0].firstChild.nodeValue = newVlanSuggestedString
#                self.logger.debug("Set vlan suggested on node %r: %s", vlan_suggested[0], vlan_suggested[0].firstChild.nodeValue)
            else:
                vlan_suggested[0].appendChild(domNode.ownerDocument.createTextNode(newVlanSuggestedString))
        else:
            vlanSuggestedNode = domNode.ownerDocument.createElement(self.VLAN_RANGE_TAG)
            vlanSuggestedNode.appendChild(domNode.ownerDocument.createTextNode(newVlanSuggestedString))
            # Find the switchingCapabilitySpecificInfo_L2sc node and append it there
            l2scNodes = domNode.getElementsByTagName('switchingCapabilitySpecificInfo_L2sc')
            if l2scNodes and len(l2scNodes) > 0:
                l2scNodes[0].appendChild(vlanSuggestedNode)

