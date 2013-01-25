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


class Aggregate(GENIObjectWithURN):
    '''Aggregate'''
    ## FIX ME check url is actually a url
    __simpleProps__ = [ ['url', str], ['inProcess', bool], ['completed', bool], ['userRequested', bool]]

    def __init__(self, id, urn=None, url=None, inProcess=None, completed=None, userRequested=None):
        super(Aggregate, self).__init__(id, urn=urn)
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


class Path(GENIObjectWithURN):
    '''Path'''
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

class Hop(GENIObjectWithURN):
    '''Hop'''
    __simpleProps__ = [ ['index', int] ]

    def __init__(self, id, urn=None, index=None):
        super(Hop, self).__init__(id, urn=urn)
        self.index = index

            

