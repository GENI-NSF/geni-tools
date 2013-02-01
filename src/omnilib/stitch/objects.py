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
from GENIObject import *

def createElementAndText(doc, element_name, child_text):
    child_node = doc.createElement(element_name)
    txt_node = doc.createTextNode(str(child_text))
    child_node.appendChild(txt_node)
    return child_node

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
        id = element.getAttribute(cls.ID_TAG)
        path = Path(id)
        for child in element.childNodes:
            if child.nodeName == cls.HOP_TAG:
                hop = Hop.fromDOM(child)
                hop.path = path
                path.hops.append(hop)
        return path

    def __init__(self, id):
        super(Path, self).__init__()
        self.id = id
        self._hops = []
        self._aggregates = []

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

    @aggregates.setter
    def aggregates(self, aggList):
        self._setListProp('aggregates', aggList, Aggregate)

    def find_hop(self, hop_urn):
        for hop in self.hops:
            if hop.urn == hop_urn:
                return hop
        # Fail -- no hop matched the given URN
        return None


class Stitching(GENIObject):
    __simpleProps__ = [ ['last_update_time', str] ] #, ['path', Path[]]]

    def __init__(self, last_update_time=None, paths=None):
        super(Stitching, self).__init__()
        self.last_update_time = str(last_update_time)
        self.paths = paths

    def find_path(self, link_id):
        if self.paths:
            for path in self.paths:
                if path.id == link_id:
                    return path
        else:
            return None


class Aggregate(GENIObjectWithIDURN):
    '''Aggregate'''
    __ID__ = validateURN
    ## FIX ME check url is actually a url
    __simpleProps__ = [ ['url', str], ['inProcess', bool], ['completed', bool], ['userRequested', bool]]

    # id IS URN?????
    def __init__(self, urn, url=None, inProcess=None, completed=None, userRequested=None):
        super(Aggregate, self).__init__(urn, urn)
        self.url = url
        self.inProcess = inProcess
        self.completed = completed
        self.userRequested = userRequested
        self._hops = []
        self._dependedOnBy = []
        self._dependsOn = []
        self.paths = []

    def __str__(self):
        return "<Aggregate %r>" % (self.urn)

    @property
    def hops(self):
        return self._hops

    @property
    def dependsOn(self):
        return self._dependsOn

    @property
    def dependedOnBy(self):
        return self._dependedOnBy
            
    @hops.setter
    def hops(self, hopList):
#DELETE        self._setListProp('hops', hopList, Hop, '_path')
        self._setListProp('hops', hopList, Hop)

    @dependsOn.setter
    def dependsOn(self, aggList):
        self._setListProp('dependsOn', aggList, Aggregate)

    @dependedOnBy.setter
    def dependedOnBy(self, aggList):
        self._setListProp('dependedOnBy', aggList, Aggregate)

    def add_hop(self, hop):
        if hop in self.hops:
            raise Exception("adding hop %s twice to aggregate %s"
                            % (hop.urn, self.urn))
        #print "Aggregate %s adding hop %s" % (self.urn, hop.urn)
        self.hops.append(hop)

    def add_path(self, path):
        if path in self.paths:
            raise Exception("adding path %s twice to aggregate %s"
                            % (path.id, self.urn))
        #print "Aggregate %s adding path %s" % (self.urn, path.id)
        path.add_aggregate(self)
        self.paths.append(path)

    def add_dependency(self, agg):
        # FIXME use a set instead of a list
        if not agg in self._dependsOn:
            self._dependsOn.append(agg)


class Hop(object):

    # XML tag constants
    ID_TAG = 'id'
    LINK_TAG = 'link'
    NEXT_HOP_TAG = 'nextHop'

    @classmethod
    def fromDOM(cls, element):
        """Parse a stitching hop from a DOM element."""
        id = element.getAttribute(cls.ID_TAG)
        hop_link = None
        next_hop = None
        for child in element.childNodes:
            if child.nodeName == cls.LINK_TAG:
                hop_link = HopLink.fromDOM(child)
            elif child.nodeName == cls.NEXT_HOP_TAG:
                next_hop_text = child.firstChild.nodeValue
                if next_hop_text != 'null':
                    next_hop = int(next_hop_text)
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
        self._links = []
        self.dom = None

    @property
    def nodes(self):
        return self._nodes

    @nodes.setter
    def nodes(self, nodeList):
        self._setListProp('nodes', nodeList, Node)

    @property
    def links(self):
        return self._links

    @links.setter
    def links(self, linkList):
        self._setListProp('links', linkList, Link)

    def find_path(self, link_id):
        """Find the link with the given id and return it. If no link
        matches the given id, return None.
        """
        return self.stitching and self.stitching.find_path(link_id)

    def find_hop(self, hop_urn):
        """Find the link with the given id and return it. If no link
        matches the given id, return None.
        """
        for link in self._links:
            if link.id == link_id:
                return link
        return None


class Link(GENIObject):
    __ID__ = validateTextLike
    __simpleProps__ = [ ['client_id', str]]

    # XML tag constants
    CLIENT_ID_TAG = 'client_id'
    COMPONENT_MANAGER_TAG = 'component_manager'
    INTERFACE_REF_TAG = 'interface_ref'
    NAME_TAG = 'name'

    @classmethod
    def fromDOM(cls, element):
        """Parse a Link from a DOM element."""
        client_id = element.getAttribute(cls.CLIENT_ID_TAG)
        refs = []
        aggs = []
        hasSharedVlan = False
        for child in element.childNodes:
            if child.nodeName == cls.COMPONENT_MANAGER_TAG:
                name = child.getAttribute(cls.NAME_TAG)
                agg = Aggregate(name)
                aggs.append(agg)
            elif child.nodeName == cls.INTERFACE_REF_TAG:
                c_id = child.getAttribute(cls.CLIENT_ID_TAG)
                ir = InterfaceRef(c_id)
                refs.append(ir)
            # FIXME: If the link has the shared_vlan extension, note this
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


class HopLink(GENIObject):

    # XML tag constants
    ID_TAG = 'id'
    HOP_TAG = 'hop'
    VLAN_TRANSLATION_TAG = 'vlanTranslation'
    VLAN_RANGE_TAG = 'vlanRangeAvailability'
    VLAN_SUGGESTED_TAG = 'suggestedVLANRange'

    @classmethod
    def fromDOM(cls, element):
        """Parse a stitching path from a DOM element."""
        id = element.getAttribute(cls.ID_TAG)
        vlan_xlate = element.getElementsByTagName(cls.VLAN_TRANSLATION_TAG)
        if vlan_xlate:
            x = vlan_xlate[0].firstChild.nodeValue
            vlan_translate = x.lower() in ('true')
        vlan_range = element.getElementsByTagName(cls.VLAN_RANGE_TAG)
        if vlan_range:
            vlan_range = vlan_range[0].firstChild.nodeValue
        vlan_suggested = element.getElementsByTagName(cls.VLAN_SUGGESTED_TAG)
        if vlan_suggested:
            vlan_suggested = vlan_suggested[0].firstChild.nodeValue
        hoplink = HopLink(id)
        hoplink.vlan_xlate = vlan_translate
        hoplink.vlan_range = vlan_range
        hoplink.vlan_suggested = vlan_suggested
        return hoplink

    def __init__(self, id):
        super(HopLink, self).__init__()
        self._id = id
        self.vlan_xlate = False
        self.vlan_range = ""
        self.vlan_suggested = None

    @property
    def urn(self):
        return self._id
