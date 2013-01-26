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
from GENIObject import *

class Path(GENIObjectWithIDURN):
    '''Path'''
    __ID__ = validateText
#    __simpleProps__ = [ ['id', int] ]

    def __init__(self, id, urn=None):
        super(Path, self).__init__(id, urn=urn)
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


class Stitching(GENIObject):
    __simpleProps__ = [ ['last_update_time', str], ['path', Path]]

    def __init__(self, last_update_time=None, path=None):
        super(Stitching, self).__init__()
        self.last_update_time = str(last_update_time)
        self.path = path

class Aggregate(GENIObjectWithIDURN):
    '''Aggregate'''
    __ID__ = validateURN
    ## FIX ME check url is actually a url
    __simpleProps__ = [ ['url', str], ['inProcess', bool], ['completed', bool], ['userRequested', bool]]

    # id IS URN?????
    def __init__(self, urn, url=None, inProcess=None, completed=None, userRequested=None):
        super(Aggregate, self).__init__(urn)
        self.url = url
        self.inProcess = inProcess
        self.completed = completed
        self.userRequested = userRequested
        self._hops = []
        self._dependedOnBy = []
        self._dependsOn = []
        
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



class Hop(GENIObjectWithIDURN):
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


class Node(GENIObject):
    __ID__ = validateTextLike
    __simpleProps__ = [ ['client_id', str], ['exclusive', TrueFalse]]

    def __init__(self, client_id, aggregate=None, exclusive=None, interfaces=None):
        super(Node, self).__init__()
        self.id = str(client_id)
        self.aggregate = aggregate
        self.exclusive =  validateTrueFalse(exclusive)
        self._interfaces = []

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

# DELETE
class InterfaceRef(Interface):
    pass
#     __ID__ = validateURN
#     def __init__(self, client_id):
#         super(InterfaceRef, self).__init__(client_id)

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
                     switching_capability_descriptor):
        pass

class SwitchingCapabilityDescriptor(GENIObject):
    def __init__(self, switching_cap_type, coding_type, \
                     switching_capability_specific_info):
        pass

class SwitchingCapabilitySpecificInfo(GENIObject):
    def __init__(self, switching_capability_specific_info_l2sc):
        pass

class SwitchingCapabilitySpecificInfo_l2sc(GENIObject):
    def __init__(self, interface_mtu, vlan_range_avaiaiblity, \
                     suggested_vlan_range, vlan_translation):
        pass

