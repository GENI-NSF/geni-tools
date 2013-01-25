# Parse a stitching enhanced rspec

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

import sys
import pdb
from xml.dom.minidom import parseString, Node

TEXT_NODE = Node.TEXT_NODE

# Node tags
RSPEC_TAG = 'rspec'
NODE_TAG = 'node'
INTERFACE_TAG = 'interface'
INTERFACE_REF_TAG = 'interface_ref'
COMPONENT_MANAGER_TAG = 'component_manager'
HOP_TAG = 'hop'
LINK_TAG = 'link'
STITCHING_TAG = 'stitching'
PATH_TAG = 'path'
TRAFFIC_ENGINEERING_METRIC_TAG = 'trafficEngineeringMetric'
CAPACITY_TAG = 'capacity'
SWITCHING_CAPABILITY_DESCRIPTOR_TAG = 'switchingCapabilityDescriptor'
SWITCHING_CAP_TYPE_TAG = 'switchingcapType'
ENCODING_TYPE_TAG = 'encodingType'
SWITCHING_CAPABILITY_SPECIFIC_INFO_TAG = 'switchingCapabilitySpecificInfo'
SWITCHING_CAPABILITY_SPECIFIC_INFO_L2SC_TAG = \
    'switchingCapabilitySpecificInfo_L2sc'
INTERFACE_MTU_TAG = 'interfaceMTU'
VLAN_RANGE_AVAILABILITY_TAG = 'vlanRangeAvailability'
SUGGESTED_VLAN_RANGE_TAG = 'suggestedVLANRange'
VLAN_TRANSLATION_TAG = 'vlanTranslation'
NEXT_HOP_TAG = 'nextHop'

# Attribute tags
CLIENT_ID_TAG = 'client_id'
EXCLUSIVE_TAG = 'exclusive'
LAST_UPDATE_TIME_TAG = "lastUpdateTime"
ID_TAG = 'id'
NAME_TAG = 'name'

class RSpecParser:

    def __init__(self, verbose=False):
        self._verbose = verbose

    def parse(self, data):
        dom = parseString(data)
        rspec_element = dom.childNodes[0]
        return self.parseRSpec(rspec_element)

    def parseRSpec(self, rspec_element):
        if rspec_element.nodeName != RSPEC_TAG: 
            print "Illegal head element: " + rspec_element
            return None
        nodes = []
        links = []
        stitching = None
        for child in rspec_element.childNodes:
            if child.nodeName == NODE_TAG:
                if self._verbose:
                    print "   " + str(child)
                node = self.parseNode(child)
                nodes.append(node)
            elif child.nodeName == LINK_TAG:
                if self._verbose:
                    print "   " + str(child)
                link = self.parseLink(child)
                links.append(link)
            elif child.nodeName == STITCHING_TAG:
                if self._verbose:
                    print "   " + str(child)
                stitching = self.parseStitching(child)
            elif child.nodeType == TEXT_NODE:
                pass
            else:
                print "UNKNOWN TAG FOR RSPEC: " + str(child)
        rspec = RSpec(nodes, links, stitching)
        return rspec
        

    def parseNode(self, node_element):
        client_id = node_element.getAttribute(CLIENT_ID_TAG)
        component_manager = node_element.getAttribute(COMPONENT_MANAGER_TAG)
        exclusive = node_element.getAttribute(EXCLUSIVE_TAG)
        if self._verbose:
            attribs = {CLIENT_ID_TAG:client_id, \
                           COMPONENT_MANAGER_TAG:component_manager, \
                           EXCLUSIVE_TAG: exclusive}
            print "      NODE: " + str(attribs)
        interfaces = []
        for child in node_element.childNodes:
            if child.nodeName == INTERFACE_TAG:
                if self._verbose:
                    print "      " + str(child)
                interface = self.parseInterface(child)
                interfaces.append(interface)
        node = Node(client_id, component_manager, exclusive, interfaces)

    def parseLink(self, link_element):
        client_id = link_element.getAttribute(CLIENT_ID_TAG)
        interface_refs = []
        component_managers = []
        if self._verbose:
            attribs = {CLIENT_ID_TAG : client_id}
            print "         LINK: " + str(attribs)
        for child in link_element.childNodes:
            if child.nodeName == COMPONENT_MANAGER_TAG:
                if self._verbose:
                    print "      " + str(child)
                component_manager = self.parseComponentManager(child)
                component_managers.append(component_manager)
            elif child.nodeName == INTERFACE_REF_TAG:
                if self._verbose:
                    print "      " + str(child)
                interface_ref = self.parseInterfaceRef(child)
                interface_refs.append(interface_ref)
            elif child.nodeType == TEXT_NODE:
                pass
            else:
                if self._verbose:
                    print "UNKNOWN TAG FOR LINK: " + str(child)
        link = Link(client_id, component_managers, interface_refs)
        return link

    def parseInterface(self, if_element):
        client_id = if_element.getAttribute(CLIENT_ID_TAG)
        if self._verbose:
            attribs = {CLIENT_ID_TAG : client_id}
            print "         INTERFACE: " + str(attribs)
        interface = Interface(client_id)
        return interface

    def parseComponentManager(self, cm_element):
        name = cm_element.getAttribute(NAME_TAG)
        if self._verbose:
            attribs = {NAME_TAG : name}
            print "         COMPONENT_MANAGER: " + str(attribs)
        component_manager = ComponentManager(name)
        return component_manager

    def parseInterfaceRef(self, ifr_element):
        client_id = ifr_element.getAttribute(CLIENT_ID_TAG)
        if self._verbose:
            attribs = {CLIENT_ID_TAG : client_id}
            print "         INTERFACE_REF: " + str(attribs)
        interface_ref = InterfaceRef(client_id)
        return interface_ref

    def parseStitching(self, stitching_element):
        last_update_time = stitching_element.getAttribute(LAST_UPDATE_TIME_TAG)
        path = None
        for child in stitching_element.childNodes:
            if child.nodeName == PATH_TAG:
                path = self.parsePath(child)
            elif child.nodeType == TEXT_NODE:
                pass
            else:
                print "UNKNOWN TAG FOR STITCHING: " + str(child)
        if self._verbose:
            attribs = {LAST_UPDATE_TIME_TAG:last_update_time}
            print "      STITCHING: " + str(attribs)
        stitching = Stitching(last_update_time, path)
        return stitching

    def parsePath(self, path_element):
        id = path_element.getAttribute(ID_TAG)
        hops = []
        for child in path_element.childNodes:
            if child.nodeName == HOP_TAG:
                hop = self.parseHop(child)
                hops.append(hop)
            elif child.nodeType == TEXT_NODE:
                pass
            else:
                print "UNKNOWN TAG FOR PATH: " + str(child)
        if self._verbose:
            attribs = {ID_TAG:id}
            print "      PATH: " + str(attribs)
        path = Path(id, hops)
        return path

    def parseHop(self, hop_element):
        id = hop_element.getAttribute(ID_TAG)
        hop_link = None
        next_hop = None
        for child in hop_element.childNodes:
            if child.nodeName == LINK_TAG:
                hop_link = self.parseHopLink(child)
            elif child.nodeName == NEXT_HOP_TAG:
                next_hop_text = child.firstChild.nodeValue
                if next_hop_text != 'null':
                    next_hop = int(next_hop_text)
            elif child.nodeType == TEXT_NODE:
                pass
            else:
                print "UNKNOWN CHILD FOR HOP: " + str(child)
        if self._verbose:
            attribs = {ID_TAG:id, NEXT_HOP_TAG: next_hop}
            print "      HOP: " + str(attribs)
        hop = Hop(id, hop_link, next_hop)
        return hop

    def parseHopLink(self, hop_link_element):
        id = hop_link_element.getAttribute(ID_TAG)
        traffic_engineering_metric = None
        capacity = None
        switching_capability_descriptor = None
        for child in hop_link_element.childNodes:
            if child.nodeName == TRAFFIC_ENGINEERING_METRIC_TAG:
                traffic_engineering_metric = int(child.firstChild.nodeValue)
            elif child.nodeName == CAPACITY_TAG:
                capacity = int(child.firstChild.nodeValue)
            elif child.nodeName == SWITCHING_CAPABILITY_DESCRIPTOR_TAG:
                switching_capabilty_descriptor = \
                    self.parseSwitchingCapabilityDescriptor(child)
            elif child.nodeType == TEXT_NODE:
                pass
            else:
                print " UNKNOWN CHILD FOR HOP_LINK: " + str(child)
        if self._verbose:
            attribs = {ID_TAG:id, \
                           TRAFFIC_ENGINEERING_METRIC_TAG: \
                           traffic_engineering_metric, \
                           CAPACITY_TAG:capacity}
            print "      HOP_LINK: " + str(attribs)
        hop_link = HopLink(id, traffic_engineering_metric, capacity, \
                               switching_capability_descriptor)
        return hop_link

    def parseSwitchingCapabilityDescriptor(self, scd_element):
        switching_cap_type = None
        encoding_type = None
        switching_capability_specific_info = None
        for child in scd_element.childNodes:
            if child.nodeName == SWITCHING_CAP_TYPE_TAG:
                switching_cap_type = child.firstChild.nodeValue
            elif child.nodeName == ENCODING_TYPE_TAG:
                encoding_type = child.firstChild.nodeValue
            elif child.nodeName == SWITCHING_CAPABILITY_SPECIFIC_INFO_TAG:
                switching_capability_specific_info = \
                    self.parseSwitchingCapabilitySpecificInfo(child)
            elif child.nodeType == TEXT_NODE:
                pass
            else:
                print "UNKNOWN CHILD FOR SCD: " + str(child)
            scd = \
                SwitchingCapabilityDescriptor(switching_cap_type,
                                              encoding_type, \
                                              switching_capability_specific_info)
        return scd

    def parseSwitchingCapabilitySpecificInfo(self, scsi_element):
        scsi_l2sc = None
        for child in scsi_element.childNodes:
            if child.nodeName == SWITCHING_CAPABILITY_SPECIFIC_INFO_L2SC_TAG:
                scsi_l2sc = \
                    self.parseSwitchingCapabilitySpecificInfo_l2sc(child)
            elif child.nodeType == TEXT_NODE:
                pass
            else:
                print "UNKNOWN CHILD FOR SCSI: " + str(child)
        scsi = SwitchingCapabilitySpecificInfo(scsi_l2sc)
        return scsi

    def parseSwitchingCapabilitySpecificInfo_l2sc(self, scsi_l2sc_element):
        interface_mtu = None
        vlan_range_availability = None
        suggested_vlan_range = None
        vlan_translation = None

        for child in scsi_l2sc_element.childNodes:
            if child.nodeName == INTERFACE_MTU_TAG:
                interface_mtu = int(child.firstChild.nodeValue)
            elif child.nodeName == VLAN_RANGE_AVAILABILITY_TAG:
                vlan_range_availability = child.firstChild.nodeValue
            elif child.nodeName == SUGGESTED_VLAN_RANGE_TAG:
                suggested_vlan_range = child.firstChild.nodeValue
            elif child.nodeName == VLAN_TRANSLATION_TAG:
                vlan_translation_text = child.firstChild.nodeValue
                vlan_translation = vlan_translation_text.lower() == 'true'
            elif child.nodeType == TEXT_NODE:
                pass
            else:
                print "UNKNOWN CHILD TIME FOR SCSI_L2SC: " + str(child)

        if self._verbose:
            attribs = {INTERFACE_MTU_TAG: interface_mtu, \
                       VLAN_RANGE_AVAILABILITY_TAG:vlan_range_availability, \
                       SUGGESTED_VLAN_RANGE_TAG:suggested_vlan_range, \
                           VLAN_TRANSLATION_TAG:vlan_translation}
            print "      SCSI_L2SC:: " + str(attribs)
        scsi_l2sc = \
            SwitchingCapabilitySpecificInfo_l2sc(interface_mtu, \
                                                     vlan_range_availability, \
                                                     suggested_vlan_range, \
                                                     vlan_translation)
        return scsi_l2sc
        

# To be replaced by real classes

class RSpec:
    def __init__(self, nodes, links, stitching): 
        pass

class Node:
    def __init__(self, client_id, component_manager, exclusive, interfaces):
        pass

class Link:
    def __init__(self, client_id, component_managers,interface_refs):
        pass

class Interface:
    def __init__(self, client_id):
        pass

class InterfaceRef:
    def __init__(self, client_id):
        pass

class ComponentManager:
    def __init__(self, name):
        pass

class Stitching:
    def __init__(self, last_update_time, path):
        pass

class Path:
    def __init__(self, id, hops):
        pass

class Hop:
    def __init__(self, id, hop_link, next_hop):
        pass

class HopLink:
    def __init__(self, id, traffic_engineering_metric, capacity, \
                     switching_capability_descriptor):
        pass

class SwitchingCapabilityDescriptor:
    def __init__(self, switching_cap_type, coding_type, \
                     switching_capability_specific_info):
        pass

class SwitchingCapabilitySpecificInfo:
    def __init__(self, switching_capability_specific_info_l2sc):
        pass

class SwitchingCapabilitySpecificInfo_l2sc:
    def __init__(self, interface_mtu, vlan_range_avaiaiblity, \
                     suggested_vlan_range, vlan_translation):
        pass



if __name__ == "__main__":
    if len(sys.argv) <= 1:
        print "Usage RspecParser <file.xml>"
        sys.exit()

    filename = sys.argv[1]
    print "FN = " + filename
    file = open(filename, 'r')
    data = file.read()
    file.close()
    parser = RSpecParser(verbose=True)
    rspec = parser.parse(data)
    print rspec
