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
import random
import time
from GENIObject import *
from VLANRange import *

# FIXME: As in RSpecParser, check use of getAttribute vs getAttributeNS and localName vs nodeName

class Path(GENIObject):
    '''Path'''
    __ID__ = validateText
#    __simpleProps__ = [ ['id', int] ]

    # XML tag constants
    ID_TAG = 'id'
    HOP_TAG = 'hop'

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

    @property
    def hops(self):
        return self._hops

    @property
    def aggregates(self):
        return self._aggregates

    @hops.setter
    def hops(self, hopList):
#DELETE        self._setListProp('hops', hopList, Hop, '_path')
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

    @classmethod
    def find(cls, urn):
        if not urn in cls.aggs:
            m = cls(urn)
            cls.aggs[urn] = m
        return cls.aggs[urn]

    @classmethod
    def all_aggregates(cls):
        return cls.aggs.values()

    def __init__(self, urn, url=None):
        self.urn = urn
        self.url = url
        self.inProcess = False
        self.completed = False
        self.userRequested = False
        self._hops = set()
        self._paths = set()
        self._dependsOn = set()
        self.isDependencyFor = set() # AMs that depend on this: for ripple down deletes
        self.logger = logging.getLogger('stitch.Aggregate')
        self.requestDom = None # the DOM as constructed to submit in request to this AM
        self.manifestDom = None # the DOM as we got back from the AM

    def __str__(self):
        return "<Aggregate %s>" % (self.urn)

    def __repr__(self):
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

    def allocate(self, opts, slicename, rspec):
        if self.inProcess:
            self.logger.warn("Called allocate on AM already in process: %s", self)
            return
        # Confirm all dependencies still done
        if not self.dependencies_complete:
            self.logger.warn("Cannot allocate AM %s: dependencies not ready", self)
            return
        if self.completed:
            self.logger.warn("Called allocate on AM already maked complete", self)
            return

        # FIXME: If we are quitting, return (important when threaded)

        # Import VLANs, noting if we need to delete an old reservation at this AM first
        mustDelete, alreadyDone = self.copyVLANsAndDetectRedo()

        if mustDelete:
            self.logger.warn("Must delete previous reservation for AM %s", self)
            alreadyDone = False
            self.deleteReservation(opts, slicename)
        # end of block to delete a previous reservation

        if alreadyDone:
            # we did a previous upstream delete and worked our way down to here, but this AM is OK
            self.completed = True
            self.logger.info("AM %s had previous result we didn't need to redo. Done", self)
            return

        # FIXME: Check for all hops have reasonable vlan inputs?

        self.completed = False

        # Mark AM is busy
        self.inProcess = True

        # Save out the rspec to a temp file
        rspecfileName = None
        # FIXME FIXME

        # FIXME: Do we do something with log level or log format or file for omni calls?
        # FIXME: Ensure we have the right URL / API version / command combo
        # IF this AM does APIv3, I'd like to use it
        # But the caller needs to know if we used APIv3 so they know whether to call provision later
        omniargs = ['a', self.url, 'createsliver', slicename, rspecfileName]
        self.logger.info("\nDoing CreateSliver at %s", self.url)

        # FIXME: If fakeMode do a fake thing
        if opts.fakeModeDir:
            self.logger.info("Doing fake allocation")
            time.sleep(random.randrange(1, 6))
            for hop in self.hops:
                hop._hop_link.vlan_suggested_manifest = hop._hop_link.vlan_suggested_request
                hop._hop_link.vlan_range_manifest = hop._hop_link.vlan_range_request
        else:
            try:
                (test, result) = omni.call(omniargs, opts)
            except OmniError, e:
                self.logger.error("Failed to reserve at %s: %s", self.url, e)
                # FIXME: call self.handleAllocateError
                raise StitchingError(e)

        # Mark AM not busy
        self.inProcess = False

        self.logger.info("Allocation at %s complete (NOT)", self)

        # FIXME: implement all this....
        # if omni returned error code  
            # call self.handleAllocateError
             # this should include noticing AM busy
        # parse manifest (includes saving vlan ranges away)
        # if APIv2 and manifest missing specific suggested tags on this AMs hops
          # call sliverStatus. Wait till ready - with some timeout
          # call listResources
          # parse manifest
        # for each hop
          # if suggested in request not any and suggested manfiest != suggested in request
            # call self.suggestedDifferent(hop)
        # :DONE
        # for each hop
          # mark complete

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
                continue

            # Calculate the new suggested/avail for this hop
            if not hop.import_vlans_from:
                self.logger.warn("Hop %s imports vlans but has no import from?", hop)
                continue

            new_suggested = hop._hop_link.vlan_suggested_request or VLANRange.fromString("any")
            if hop.import_vlans_from._hop_link.vlan_suggested_manifest:
                # FIXME: Need deep copy?
                new_suggested = hop.import_vlans_from._hop_link.vlan_suggested_manifest.copy()
            else:
                self.logger.warn("Hop %s's import_from %s had no suggestedVLAN manifest", hop, hop.import_vlans_from)
            int1 = VLANRange.fromString("any")
            int2 = VLANRange.fromString("any")
            if hop.import_vlans_from._hop_link.vlan_range_manifest:
                int1 = hop.import_vlans_from._hop_link.vlan_range_manifest
            else:
                self.logger.warn("Hop %s's import_from %s had no avail VLAN manifest", hop, hop.import_vlans_from)
            if hop._hop_link.vlan_range_request:
                int2 = hop._hop_link.vlan_range_request
            else:
                self.logger.warn("Hop %s had no avail VLAN request", hop, hop.import_vlans_from)
            new_avail = int1 & int2

            # If we have a previous manifest, we might be done or might need to delete a previous reservation
            if hop._hop_link.vlan_suggested_manifest:
                if not hadPreviousManifest:
                    raise StitchingError("AM %s had no previous manifest, but its hop %s did", self, hop)
                if hop._hop_link.vlan_suggested_request != new_suggested:
                    # If we already have a result but used different input, then this result is suspect. Redo.
                    self.logger.warn("AM %s had previous manifest and used different suggested VLAN for hop %s (old request %s != new request %s)", self, hop, hop._hop_link.vlan_suggested_request, new_suggested)
                    hop._hop_link.vlan_suggested_request = new_suggested
                    # if however the previous suggested_manifest == new_suggested, then maybe this is OK?
                    if hop._hop_link.vlan_suggested_manifest == new_suggested:
                        self.logger.info("But hop %s VLAN suggested manifest is the new request, so leave it alone", hop)
                    else:
                        mustDelete = True
                        alreadyDone = False
                else:
                    self.logger.info("AM %s had previous manifest and used same suggested VLAN for hop %s (%s)", self, hop, hop._hop_link.vlan_suggested_request)
                    # So for this hop at least, we don't need to redo this AM
            else:
                alreadyDone = False
                # No previous result
                if hadPreviousManifest:
                    raise StitchingError("AM %s had a previous manifest but hop %s did not", self, hop)
                if hop._hop_link.vlan_suggested_request != new_suggested:
                    self.logger.debug("Hop %s changing VLAN suggested from %s to %s", hop, hop._hop_link.vlan_suggested_request, new_suggested)
                    hop._hop_link.vlan_suggested_request = new_suggested
                else:
                    self.logger.debug("Hop %s already had VLAN suggested %s", hop, hop._hop_link.vlan_suggested_request)

            # Now check the avail range as we did for suggested
            if hop._hop_link.vlan_range_manifest:
                if not hadPreviousManifest:
                    self.logger.error("AM %s had no previous manifest, but its hop %s did", self, hop)
                if hop._hop_link.vlan_range_request != new_avail:
                    # If we already have a result but used different input, then this result is suspect. Redo?
                    self.logger.warn("AM %s had previous manifest and used different avail VLAN range for hop %s (old request %s != new request %s)", self, hop, hop._hop_link.vlan_range_request, new_avail)
                    if hop._hop_link.vlan_suggested_manifest and hop._hop_link.vlan_suggested_manifest not in new_avail:
                        # new avail doesn't contain the previous manifest suggested. So new avail would have precluded
                        # using the suggested we picked before. So we have to redo
                        mustDelete = True
                        alreadyDone = False
                        self.logger.warn("Hop %s previous manifest suggested %s not in new avail %s - redo this AM", hop, hop._hop_link.vlan_suggested_manifest, new_avail)
                    else:
                        # what we picked before still works, so leave it alone
                        self.logger.debug("Hop %s had avail range manifest %s, and previous avail range request (%s) != new (%s), but previous suggested manifest %s is in the new avail range, so it is still good", hop, hop._hop_link.vlan_range_manifest, hop._hop_link.vlan_range_request, new_avail, hop._hop_link.vlan_suggested_manifest)

                    # Either way, record what we want the new request to be, so later if we redo we use the right thing
                    hop._hop_link.vlan_range_request = new_avail
                else:
                    self.logger.info("AM %s had previous manifest and used same avail VLAN range for hop %s (%s)", self, hop, hop._hop_link.vlan_range_request)
            else:
                alreadydone = False
                # No previous result
                if hadPreviousManifest:
                    raise StitchingError("AM %s had a previous manifest but hop %s did not", self, hop)
                if hop._hop_link.vlan_range_request != new_avail:
                    self.logger.debug("Hop %s changing avail VLAN from %s to %s", hop, hop._hop_link.vlan_range_request, new_avail)
                    hop._hop_link.vlan_range_request = new_avail
                else:
                    self.logger.debug("Hop %s already had avail VLAN %s", hop, hop._hop_link.vlan_range_request)
        # End of loop over hops to copy VLAN tags over and see if this is a redo or we need to delete
        return mustDelete, alreadyDone

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

        if not opts.fakeModeDir:
            # Delete the previous reservation
            # omni.call() # FIXME FIXME FIXME
            # note omniargs is wrong: need to do delete or deletesliver as appropriate
            # if command was allocate, command now is delete
            # else if command was createsliver, command now is deletesliver
            # FIXME: Do we do something with log level or log format or file for omni calls?
            # add the needed -a AM.url
            omniargs = ['-a', self.url, 'deletesliver', slicename]
            self.logger.info("Doing DeleteSliver at %s", self.url)
            try:
                (text, (successList, fail)) = omni.call(omniargs, opts)
                if not self.url in successList:
                    raise StitchingError("Failed to delete prior reservation at %s: %s", self.url, text)
                else:
                    self.logger.debug("Result: %s", text)
            except OmniError, e:
                self.logger.error("Failed to deletesliver: %s", e)
                raise StitchingError(e)

        # FIXME: Set a flag marking this AM was deleted?
        return

class Hop(object):
    # A hop on a path in the stitching element
    # Note this is path specific (and has a path reference)

    # XML tag constants
    ID_TAG = 'id'
    LINK_TAG = 'link'
    NEXT_HOP_TAG = 'nextHop'

    @classmethod
    def fromDOM(cls, element):
        """Parse a stitching hop from a DOM element."""
        # FIXME: getAttributeNS?
        id = element.getAttribute(cls.ID_TAG)
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
        # FIXME: export_vlans_to too?
        self.import_vlans_from = None # a pointer to another hop
        # FIXME: depended_on_by?

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

class RSpec(GENIObject):
    '''RSpec'''
    __simpleProps__ = [ ['stitching', Stitching] ]

    def __init__(self, stitching=None): 
        super(RSpec, self).__init__()
        self.stitching = stitching
        self._nodes = []
        self._links = [] # Main body links
        self.dom = None
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


class Node(GENIObject):
    CLIENT_ID_TAG = 'client_id'
    COMPONENT_MANAGER_ID_TAG = 'component_manager_id'
    @classmethod
    def fromDOM(cls, element):
        """Parse a Node from a DOM element."""
        # FIXME: getAttributeNS?
        client_id = element.getAttribute(cls.CLIENT_ID_TAG)
        amID = element.getAttribute(cls.COMPONENT_MANAGER_ID_TAG)
        return Node(client_id, amID)

    def __init__(self, client_id, amID):
        super(Node, self).__init__()
        self.id = client_id
        self.amURN = amID

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

    @classmethod
    def fromDOM(cls, element):
        """Parse a Link from a DOM element."""
        # FIXME: getAttributeNS?
        client_id = element.getAttribute(cls.CLIENT_ID_TAG)
        refs = []
        aggs = []
        hasSharedVlan = False
        for child in element.childNodes:
            if child.localName == cls.COMPONENT_MANAGER_TAG:
                name = child.getAttribute(cls.NAME_TAG)
                agg = Aggregate.find(name)
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
        link = Link(client_id)
        link.aggregates = aggs
        link.interfaces = refs
        link.hasSharedVlan = hasSharedVlan
        return link

    def __init__(self, client_id):
        super(Link, self).__init__()
        self.id = client_id
        self._aggregates = []
        self._interfaces = []
        self.hasSharedVlan = False

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
        return hoplink

    def __init__(self, urn):
        self.urn = urn
        self.vlan_xlate = False
        self.vlan_range_request = ""
        self.vlan_suggested_request = None
        self.vlan_range_manifest = ""
        self.vlan_suggested_manifest = None
