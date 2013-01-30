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
#import GENIObject
#from GENIObject import GENIObject
import pdb
from GENIObject import *

def createElementAndText(doc, element_name, child_text):
    child_node = doc.createElement(element_name)
    txt_node = doc.createTextNode(str(child_text))
    child_node.appendChild(txt_node)
    return child_node

class Path(GENIObjectWithIDURN):
    '''Path'''
    __ID__ = validateText
#    __simpleProps__ = [ ['id', int] ]

    def __init__(self, id, urn=None):
        super(Path, self).__init__(id, urn=urn)
        self._hops = []
        self._aggregates = []

    def toXML(self, doc, parent):
        path_node = doc.createElement('path')
        parent.appendChild(path_node)
        path_node.setAttribute('id', self.id)
        for hop in self._hops:
            hop.toXML(doc, path_node)
        for agg in self._aggregates:
            agg.toXML(doc, path_node)

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
    __simpleProps__ = [ ['last_update_time', str], ['path', Path]]

    def __init__(self, last_update_time=None, path=None):
        super(Stitching, self).__init__()
        self.last_update_time = str(last_update_time)
        self.path = path

    def toXML(self, doc, parent):
        stitch_node = doc.createElement('stitching')
        parent.appendChild(stitch_node)
        stitch_node.setAttribute('lastUpdateTime', self.last_update_time)
        if self.path:
            self.path.toXML(doc, stitch_node)

    def find_path(self, link_id):
        if self.path and self.path.id == link_id:
            return self.path
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

    def __str__(self):
        return "<Aggregate %r>" % (self.urn)

    def toXML(self, doc, parent):
        agg_node = doc.createElement('component_manager')
        parent.appendChild(agg_node)
        agg_node.setAttribute('name', self.id)
        
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
        print "Aggregate %s adding hop %s" % (self.urn, hop.urn)
        self.hops.append(hop)

    def add_dependency(self, agg):
        # FIXME use a set instead of a list
        if not agg in self._dependsOn:
            self._dependsOn.append(agg)


class Hop(object):

    def __init__(self, id, hop_link, next_hop):
        self._id = id
        self._hop_link = hop_link
        self._next_hop = next_hop
        self._aggregate = None
        self._import_vlans = False
        self._dependencies = []

    def __str__(self):
        return "<Hop %r>" % (self.urn)

    def toXML(self, doc, parent):
        hop_node = doc.createElement('hop')
        parent.appendChild(hop_node)
        hop_node.setAttribute('id', self._id)
        if self._hop_link:
            self._hop_link.toXML(doc, hop_node)
        next_hop = self._next_hop or "null"
        hop_node.appendChild(createElementAndText(doc, 'nextHop', next_hop))

    @property
    def urn(self):
        return self._hop_link and self._hop_link.urn

    @property
    def aggregate(self):
        return self._aggregate

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


class Hop_Orig(GENIObjectWithIDURN):
    '''Hop'''
    __simpleProps__ = [ ['index', int], ['aggregate', Aggregate], ['path', Path], ['inProcess', bool], ['completed', bool], ['userRequested', bool] ]

    def __init__(self, id, urn=None, index=None, aggregate=None, path=None, inProcess=None, completed=None, userRequested=None):
        super(Hop, self).__init__(id, urn=urn)
        self.index = index
        self.aggregate = aggregate
        self.path = path
        self.inProcess = inProcess
        self.completed = completed
        self.userRequested = userRequested
        self._dependsOn = []
        self._copiesVlansTo = []

    def toXML(self, doc, parent):
        hop_node = doc.createElement('hop')
        parent.appendChild(hop_node)
        hop_node.setAttribute('id', self.id)
        if path:
            path.toXML(doc, hop_node)
            
    @property
    def dependsOn(self):
        return self._dependsOn

    @property
    def copiesVlansTo(self):
        return self._copiesVlansTo

    @dependsOn.setter
    def dependsOn(self, hopList):
        self._setListProp('dependsOn', hopList, Hop)

    @copiesVlansTo.setter
    def copiesVlansTo(self, hopList):
        self._setListProp('copiesVlansTo', hopList, Hop)


class RSpec(GENIObject):
    '''RSpec'''
    __simpleProps__ = [ ['stitching', Stitching] ]

    def __init__(self, stitching=None): 
        super(RSpec, self).__init__()
        self.stitching = stitching
        self._nodes = []
        self._links = []

    def toXML(self, doc, parent):
        parent.setAttribute('xmlns', 'http://www.geni.net/resources/rspec/3')
        parent.setAttribute('xmlns:xsi', 'http://www.w3.org/2001/XMLSchema-instance')
        schema_locations = "http://hpn.east.isi.edu/rspec/ext/stitch/0.1/ " + \
            "http://hpn.east.isi.edu/rspec/ext/stitch/0.1/stitch-schema.xsd " + \
            "http://www.geni.net/resources/rspec/3 " + \
            "http://www.geni.net/resources/rspec/3/request.xsd "
        parent.setAttribute('xsi:schemaLocation', schema_locations)
        parent.setAttribute('type', 'request')

        for node in self._nodes:
            node.toXML(doc, parent)
        for link in self._links:
            link.toXML(doc, parent)
        if self.stitching:
            self.stitching.toXML(doc, parent)

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


class Node(GENIObject):
    __ID__ = validateTextLike
    __simpleProps__ = [ ['client_id', str], ['exclusive', TrueFalse]]

    def __init__(self, client_id, aggregate=None, exclusive=None, interfaces=None):
        super(Node, self).__init__()
        self.id = str(client_id)
        self.aggregate = aggregate
        self.exclusive =  validateTrueFalse(exclusive)
        self._interfaces = []
        if interfaces: self._interfaces = interfaces

    def toXML(self, doc, parent):
        node_node = doc.createElement('node')
        parent.appendChild(node_node)
        node_node.setAttribute('client_id', self.id)
        node_node.setAttribute('component_manager_id', self.aggregate)
        node_node.setAttribute('exclusive', str(self.exclusive).lower())
        for interface in self._interfaces:
            interface.toXML(doc, node_node)

    @property
    def interfaces(self):
        return self._interfaces

    @interfaces.setter
    def interfaces(self, interfaceList):
        self._setListProp('interfaces', interfaceList, Interface)

    @property
    def aggregate(self):
        return self._aggregate

    @aggregate.setter
    def aggregate(self, agg):
        if agg is None:
            return None
        if type(agg) == Aggregate:
            self._aggregate = agg
        elif type(agg) == URN or type(agg) == str or  type(agg) == unicode:
            self._aggregate = validateURN(agg)
        else:
            raise TypeError("aggregate must be a valid Aggregate or a valid URN")

class Link(GENIObject):
    __ID__ = validateTextLike
    __simpleProps__ = [ ['client_id', str]]

#    def __init__(self, client_id, component_managers,interface_refs):
    def __init__(self, client_id):
        super(Link, self).__init__()
        self.id = client_id
        self._aggregates = []
        self._interfaces = []

    def toXML(self, doc, parent):
        link_node = doc.createElement('link')
        parent.appendChild(link_node)
        link_node.setAttribute('client_id', self.id)
        for agg in self._aggregates:
            agg.toXML(doc, link_node)
        for interface in self._interfaces:
            interface.toXML(doc, link_node)

    @property
    def interfaces(self):
        return self._interfaces

    @interfaces.setter
    def interfaces(self, interfaceList):
        self._setListProp('interfaces', interfaceList, Interface)

    @property
    def aggregates(self):
        return self._aggregates

    @aggregates.setter
    def aggregates(self, aggregateList):
        self._setListProp('aggregates', aggregateList, Aggregate)

class Interface(GENIObject):
#    __simpleProps__ = [ ['client_id', str]]
#    __simpleProps__ = [ ['client_id', TextLike]]
    __ID__ = validateTextLike
    def __init__(self, client_id):
        super(Interface, self).__init__()
        self.id = client_id

    def toXML(self, doc, parent):
        interface_node = doc.createElement('interface')
        parent.appendChild(interface_node)
        interface_node.setAttribute('client_id', self.id)

class InterfaceRef(Interface):

     __ID__ = validateURN
     def __init__(self, client_id):
         super(InterfaceRef, self).__init__(client_id)

     def toXML(self, doc, parent):
        interface_ref_node = doc.createElement('interface_ref')
        parent.appendChild(interface_ref_node)
        interface_ref_node.setAttribute('client_id', self.id)

# DELETE
class ComponentManager(Aggregate):
    pass
#     __ID__ = validateText
# #    __simpleProps__ = [ ['name', str]]
#     def __init__(self, name):
#         super(ComponentManager, self).__init__(name)
# #        self.name = name
        

class HopLink(GENIObject):
    def __init__(self, id, traffic_engineering_metric, capacity, \
                     switching_capability_descriptor, capabilities):
        super(HopLink, self).__init__()
        self._id = id
        self._traffic_engineering_metric = traffic_engineering_metric
        self._capacity = capacity
        self._switching_capability_descriptor = switching_capability_descriptor
        self._capabilities = capabilities

    def toXML(self, doc, parent):
        link_node = doc.createElement('link')
        link_node.setAttribute('id', self._id)
        parent.appendChild(link_node)
        link_node.appendChild(createElementAndText(doc,
                                                   'trafficEngineeringMetric',
                                                   self._traffic_engineering_metric))
        link_node.appendChild(createElementAndText(doc,
                                                   'capacity',
                                                   self._capacity))
        if self._switching_capability_descriptor:
            self._switching_capability_descriptor.toXML(doc, link_node)
        if self._capabilities:
            cs_node = doc.createElement('capabilities')
            for c in self._capabilities:
                cs_node.appendChild(createElementAndText(doc, 'capability', c))
            link_node.appendChild(cs_node)

    @property
    def urn(self):
        return self._id


class SwitchingCapabilityDescriptor(GENIObject):
    def __init__(self, switching_cap_type, coding_type, \
                     switching_capability_specific_info):
        super(SwitchingCapabilityDescriptor, self).__init__()
        self._switching_cap_type = switching_cap_type
        self._coding_type = coding_type
        self._switching_capability_specific_info = switching_capability_specific_info

    def toXML(self, doc, parent):
        scd_node = doc.createElement('switchingCapabilityDescriptor')
        parent.appendChild(scd_node)
        scd_node.appendChild(createElementAndText(doc,
                                                  'switchingcapType',
                                                  self._switching_cap_type))
        scd_node.appendChild(createElementAndText(doc,
                                                  'encodingType',
                                                  self._coding_type))
        if self._switching_capability_specific_info:
           self._switching_capability_specific_info.toXML(doc, scd_node)

class SwitchingCapabilitySpecificInfo(GENIObject):
    def __init__(self, switching_capability_specific_info_l2sc):
        super(SwitchingCapabilitySpecificInfo, self).__init__()
        self._switching_capability_specific_info_l2sc = switching_capability_specific_info_l2sc

    def toXML(self, doc, parent):
        scsi_node = doc.createElement('switchingCapabilitySpecificInfo')
        parent.appendChild(scsi_node)
        if self._switching_capability_specific_info_l2sc:
            self._switching_capability_specific_info_l2sc.toXML(doc, scsi_node)

class SwitchingCapabilitySpecificInfo_l2sc(GENIObject):
    def __init__(self, interface_mtu, vlan_range_availability, \
                     suggested_vlan_range, vlan_translation):
        super(SwitchingCapabilitySpecificInfo_l2sc, self).__init__()
        self._interface_mtu = interface_mtu
        self._vlan_range_availability = vlan_range_availability
        self._suggested_vlan_range = suggested_vlan_range
        self._vlan_translation = vlan_translation

    def toXML(self, doc, parent):
        scsi_l2sc_node = doc.createElement('switchingCapabilitySpecificInfo_L2sc')
        parent.appendChild(scsi_l2sc_node)
        scsi_l2sc_node.appendChild(createElementAndText(doc,
                                                        'interfaceMTU',
                                                        self._interface_mtu))

        scsi_l2sc_node.appendChild(createElementAndText(doc,
                                                        'vlanRangeAvailability',
                                                        self._vlan_range_availability))
        scsi_l2sc_node.appendChild(createElementAndText(doc,
                                                        'suggestedVLANRange',
                                                        self._suggested_vlan_range))
        # Convert bool string to lowercase
        vlan_translation = str(self._vlan_translation).lower()
        scsi_l2sc_node.appendChild(createElementAndText(doc,
                                                        'vlanTranslation',
                                                        vlan_translation))
