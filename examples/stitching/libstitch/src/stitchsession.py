#!/usr/bin/python
#----------------------------------------------------------------------
# Copyright (c) 2011 Raytheon BBN Technologies
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
'''
A Stitching session that covers the life of gathering relevant topology,
parsing and understanding user resource requests, deriving requirements
to meet those requests, and then making those reservations on behalf of
the user.
'''


import os

HASPGV=False
try:
    import pygraphviz
    HASPGV=True
except:
    pass

import util
import exception


## Class to represent a stitch session. A stitch session lives from the
# submission of some req rspecs, all the way until the successful (or failed)
# allocation of the requested resources as well as any which were requested on
# the user's behalf in order to create connectivity between them.
#
class StitchSession(object):

    ## The Constructor
    #    @param sliceNameStr - The name of the slice associated with this 
    #    session
    #    @param userNameStr - The user in the omni_config whose credentials will
    #    be used to request resources
    #    @param userKeyFileStr - The path of the keyfile for the user
    #    @param siteNamePrefixStr - The sitename_ prefix for SFA internal slicenames. May be empty.
    #    @param logger - The logging object to log output to
    # 
    def __init__(self, sliceNameStr, userNameStr, userKeyFileStr, siteNamePrefixStr, logger):
        self.logger = logger
        self.sliceNameStr = str(sliceNameStr)
        self.userNameStr = str(userNameStr)
        self.userKeyFileStr = str(userKeyFileStr)
        self.siteNamePrefixStr = str(siteNamePrefixStr)
        self.aggregateDict = {} # aggrURL -> ReqRSpec object
        # Advertised routes between aggregates, as pulled from Ad Rspecs
        # Dict: aggrURL -> Dict{local interface URN -> remote interface URN}
        self.presetRoutes = None 
        self.aggrAdjMap = None # aggrURL -> list of AM URLs on other end, pulled from presetRoutes
        self.rspecInfo = None # static RSpec type info
        self.threads = [] # for parallel reservations
        

    ## Starts the stitching session by beginning to parse input RSpecs.
    # For some of the items which might fail but might fit in the 
    # constructor,
    #
    #   @ return True if successful, False otherwise
    #
    def startSession(self):
        # Parse Ads to produce topology info
        self.presetRoutes,self.aggrAdjMap = util.getTopologyData(self.logger)
        # basic info about RSpec types, etc
        self.rspecInfo = util.getKnownAggregateData()
        if self.presetRoutes is None or self.aggrAdjMap is None or self.rspecInfo is None:
            return False
        return True


    ## Gets the name of the slice associated with this session
    #
    #   @return The slice name
    #
    def getSliceName(self):
        return self.sliceNameStr


    ## Gets the user in the omni_config whose credentials will be used
    # to request resources
    #
    #   @return The user name
    #
    def getUserName(self):
        return self.userNameStr


    ## Gets the path of the keyfile for the user
    #
    #   @return The keyfile path
    #
    def getUserKeyFile(self):
        return self.userKeyFileStr


    ## Gets the site name prefix for full SFA slice names, if any
    #
    #   @return The site name prefix
    #
    def getSiteNamePrefix(self):
        return self.siteNamePrefixStr


    ## Gets the ReqRSpec object associated with the given aggregate URL
    #
    #   @param aggrURL - A string aggregate URL
    #   @return A ReqRSpec object if exists, None otherwise
    #
    def getAggregate(self, aggrURL):
        # used from rspec.py to set restrictions
        try:
            return self.aggregateDict[aggrURL]
        except:
            return None


    ## Adds an aggregate to the session.
    #
    #   @param aggr - A ReqRSpec object
    #
    def addAggregate(self, aggr):
        # ReqRSpecs call this on themselves during init
        try:
            self.aggregateDict[aggr.aggrURL]=aggr
        except:
            self.logger.error("Unable to add aggregate to session", exc_info=True)


    ## Gets a list of associated ReqRSpec objects.
    #
    #   @return A list of ReqRSpec objects
    #
    def getAggregateList(self):
        return self.aggregateDict.values()


    ## Gets a dictionary by aggregate URL of associated ReqRSpec objects.
    #
    #   @return A dictionary of ReqRSpec objects with aggregate URLs as keys
    #
    def getAggregateDict(self):
        # Used by rspec.py calculateRestrictions
        return self.aggregateDict


    ## Tells which rspec format type is associated with the aggregate with the 
    # given URL
    #
    #   @param aggrURL - A string aggregate URL
    #   @return String RSpec type for the given aggregate URL, 
    #   ex: ion, max, pgv2. None if not found
    #
    def getTypeFromAggrURL(self, aggrURL):
        # From rspec init sequence, the rspecInfo is filled in
        # FIXME: that info is hardcoded in util
        # FIXME: Chris had no ION entry.
        # Only use was in ReqRSpec.init, and it had the effect
        # of over-riding the per subclass value
        for rspecType,val in self.rspecInfo.iteritems():
            aggrs = []
            if val.has_key('aggregates'):
                aggrs = val['aggregates']
            for aggr in aggrs:
                if aggr.has_key('aggrURL') and aggr['aggrURL']==aggrURL:
                    return rspecType
        return None


    ## Tells the XML Rspec namespace to use for a given format type
    #
    #   @param rspecType - A string type
    #   @return String default namespace URL for the given RSpec type
    #
    def getNamespaceFromType(self, rspecType):
        if self.rspecInfo.has_key(rspecType) and self.rspecInfo[rspecType].has_key('namespace'):
            return self.rspecInfo[rspecType]['namespace']
        return None


    ## Tells the XML Rspec extended namespace to use for a given format type 
    # based on name. EG use this to get the stitching namespace, or MAX
    # ctrlplane namespace.
    #
    #   @param rspecType - A string type
    #   @param name - The string name for the extension
    #   @return String secondary namespace URL of the given name for the given
    #   RSpec type
    #
    def getExtNamespaceFromType(self, rspecType, name):
        if self.rspecInfo.has_key(rspecType) and self.rspecInfo[rspecType].has_key('ext_namespaces') and self.rspecInfo[rspecType]['ext_namespaces'].has_key(name):
            return self.rspecInfo[rspecType]['ext_namespaces'][name]
        return None


    ## Determines whether or not the AdRSpec with the given URL is associated
    # with the given Interface URN (IE has a route from that link URN to some other Link URN)
    #
    #   @param aggrURL - A string aggregate URL
    #   @param urn - A string interface URN
    #   @return True if urn aggrURL has an interface with that urn, False otherwise
    #
    def aggrHasIface(self, aggrURL, urn):
        # Used by rspec.py calculateRestrictions to determine that a named interface
        # is owned by that AM
        if self.presetRoutes.has_key(aggrURL) and self.presetRoutes[aggrURL].has_key(urn):
            return True
        return False
    

    ## Determines whether or not the given aggregate URL is an aggregate URL we
    # know about
    #
    #   @param aggrURL - A string aggregate URL
    #   @return True if urn aggrURL is valid for this session, False otherwise
    #
    def isValidAggrURL(self, aggrURL):
        # Use is commented out in rspec.py PGV2 ReqRSpec.calculateRestrictions
        for rspecType,val in self.rspecInfo.iteritems():
            aggrs = []
            if val.has_key('aggregates'):
                aggrs = val['aggregates']
            for aggr in aggrs:
                if aggr.has_key('aggrURL') and aggr['aggrURL']==aggrURL:
                    return True
        return False


    ## Gets a list of all the Aggregate URLS in the presetRoutes map
    # In other words, this is all aggregate manager URLs for which we parsed 
    # Ad RSpecs and found routes between aggregates.
    #
    #   @return list of string AM urls
    #
    def getPresetRouteAggrURLList(self):
        # Only use is commented out in rspec.py PGV2Req calculateResctrictions
        return self.presetRoutes.keys()


    ## Gets a dictionary of advertised routes for the given aggrURL
    # Routes are of the form localLinkURN:remoteLinkURN
    #
    #   @param aggrURL - A string aggregate URL
    #   @return dictionary mapping link URNs, defining advertised routes
    #
    def getPresetRouteDictForAggrURL(self, aggrURL):
        # Used by rspec.py MaxManRSpec to find advertised routes' endpoing interfaces,
        # for filling in definedVlans
        try:
            return self.presetRoutes[aggrURL]
        except:
            raise exception.UnknownAggrURLException(aggrURL)


    ## Gets a list of ReqRSpec objects representing aggregates which are 
    # adjacent to the aggregate associated with the given aggregate URL,
    # according to their Ad RSpecs
    #
    #   @param aggrURL - A string aggregate URL
    #   @return list of ReqRSpecs
    #
    def getAdjacentAggrList(self, aggrURL):
        # Unused, was from rspec.py ReqRSpec.calculateDeps
        tmp = []
        if self.aggrAdjMap.has_key(aggrURL):
            for adjAggrURL in self.aggrAdjMap[aggrURL]:
                if self.aggregateDict.has_key(adjAggrURL):
                    tmp.append(self.aggregateDict[adjAggrURL])
        return tmp
 

    ## Tells whether or not a the given aggregate has an outgoing route 
    # associated with the given local link URN in its Ad RSpec
    # 
    #   @param aggrURL - A string aggregate URL
    #   @param urn - A string URN 
    #   @return True if yes, False if no
    #
    def aggrHasRouteURN(self, aggrURL, urn):
        # Used by PG and ION ManRSpecs to check that the given interface
        # is about a route that that aggregate advertises, for manipulating VLAN IDs
        if self.presetRoutes.has_key(aggrURL) and self.presetRoutes[aggrURL].has_key(urn):
            return True
        return False


    ## Get the remote link URN for the given aggregate's local link URN, 
    # if any, in its Ad RSpec
    #
    #   @param aggrURL - A string aggregate URL
    #   @param urn - A string URN 
    #   @return string remote link URN if any, else None
    #
    def getAggrURNRoute(self, aggrURL, urn):
        # Used by PGV2Man fromRspec to find the remote interface URN,
        # for filling definedVlans
        # Also below in graph generation
        if self.aggrHasRouteURN(aggrURL, urn):
            return self.presetRoutes[aggrURL][urn]
        return None


    ## Get the remote aggregate URL for the given aggregate's local link URN,
    # if any, in its Ad RSpec
    #
    #   @param aggrURL - A string aggregate URL
    #   @param urn - A string URN of an interface on that aggregate
    #   @return string remote aggregate URL connected to that interface 
    # if any, else None
    #
    def getAggrURNRemoteAggr(self, aggrURL, urn):
        remoteURN = self.getAggrURNRoute(aggrURL, urn)
        if not remoteURN:
            return None
        for aggr_url,iface_dict in self.presetRoutes.iteritems():
            if iface_dict.has_key(remoteURN) and iface_dict[remoteURN] == urn:
                return aggr_url
        return None


    ## Generate a .png graph of the resulting topology of what was allocated.
    #
    #   @param outputFolder - A string foldername to write the image file into
    #   @param outputFilename - A string filename to write the image file as
    #
    def generateGraph(self, outputFolder, outputFilename):
        '''Generate .png graph of reserved topology to given folder, filename'''

        if not HASPGV:
            self.logger.warn("Can't generate graph - missing library pygraphviz")
            return False

#        addedAggrList = []
        exp_graph = pygraphviz.AGraph()

        # For each request
        for aggrURL in self.aggregateDict:

            ##Aggregate Nodes and links
            exp_graph.add_node(aggrURL)
            vlan_tag="?" 

            for iface in self.aggregateDict[aggrURL].requestedInterfaces:
                adjAggrURL = self.aggregateDict[aggrURL].requestedInterfaces[iface]['remoteAggrURL']
                exp_graph.add_node(adjAggrURL)
                if self.aggregateDict[aggrURL].manRSpec is not None and self.aggregateDict[adjAggrURL].manRSpec is not None:
                    for iface in self.aggregateDict[aggrURL].manRSpec.definedVlans:
#                        self.logger.debug("Looking at %s iface %s", aggrURL, iface)
                        outer_iface = self.getAggrURNRoute(adjAggrURL,iface)
#                        self.logger.debug("Outer from %s is %s", adjAggrURL, outer_iface)

                        if outer_iface and outer_iface != 'None':
                            if self.aggregateDict[adjAggrURL].manRSpec.definedVlans.has_key(iface):
                                vlan_tag = self.aggregateDict[adjAggrURL].manRSpec.definedVlans[iface]
                                self.logger.debug("Found vlan %s", vlan_tag)
                                # FIXME: Could this also be aggDict[aggrURL].man.defined[outer_iface]?
                                # Are those the same?
#                            else:
#                                self.logger.debug("Didn't find a matching entry in the adjacent AM")
                            break
                        # else no remote iface for this - skip

                # Edges get added both directions - but only 1 direction has a VLAN tag usually
                # So if we already added this edge and last time had a VLAN tag, skip it
                prevEdge = None
                prevReversed = False
                addThis = True
                if exp_graph.has_edge(aggrURL,adjAggrURL):
                    prevEdge = exp_graph.get_edge(aggrURL,adjAggrURL)
                elif exp_graph.has_edge(adjAggrURL,aggrURL):
                    prevEdge = exp_graph.get_edge(adjAggrURL,aggrURL)
                    prevReversed = True

                if prevEdge:
                    if vlan_tag == "?" and not prevReversed:
                        self.logger.debug("Not re-adding edge from %s to %s where this time the vlan is ? and last was %s", aggrURL, adjAggrURL, prevEdge.attr['label'])
                        addThis = False
                    elif vlan_tag == "?" and prevReversed:
                        self.logger.debug("Not re-adding reversed edge from %s to %s where this time the vlan is ? and last was %s", adjAggrURL, aggrURL, prevEdge.attr['label'])
                        addThis = False
                    elif not prevReversed:
                        self.logger.debug("DO re-add edge from %s to %s where this time the vlan is NOT ? (%s) and last was %s", aggrURL, adjAggrURL, vlan_tag, prevEdge.attr['label'])
                        addThis = True
                    elif prevReversed:
                        self.logger.debug("DO re-add reversed edge from %s to %s where this time the vlan is NOT ? (%s) and last was %s", adjAggrURL, aggrURL, vlan_tag, prevEdge.attr['label'])
                        addThis = True
                    # else no previous edge - add it
                        
                if addThis:
                    exp_graph.add_edge(aggrURL,adjAggrURL,label=vlan_tag)


            ##Nodes and links to aggregates
            if self.aggregateDict[aggrURL].manRSpec is not None:
                for node in self.aggregateDict[aggrURL].manRSpec.nodes:
                    full_node_name = 'host: '+node['hostname']+'\\lip: '+node['int_ip']+'\\l'
                    exp_graph.add_node(full_node_name, color="blue", shape="box")
                    exp_graph.add_edge(aggrURL,full_node_name)
 
#            addedAggrList.append(self.aggregateDict[aggrURL])

        full_filename = outputFolder+"/"+outputFilename
        #print "Writing graph image to: "+full_filename
        exp_graph.draw(full_filename, 'png', 'dot')
        return True


    ## Create an output folder for generated files for a slice to go into.
    # The folder will be 'slicename_X' by default (where X is an integer 0 or 
    # higher). If the folder already exists 'slicename_(X+1)' will be used.
    #
    #   @return A string foldername that was created for use.
    #
    def createOutputFolder(self):
        pwd = os.getcwd()
        done = False
        count = 0

        while not done:
            fullPath = os.path.join(pwd,self.getSliceName()+"_"+str(count))
            if os.path.exists(fullPath):
                count+=1
                continue
            else:
                done=True
        
        try:
            os.mkdir(fullPath)
        except:
            self.logger.error("Unable to create output directory %s", fullPath, exc_info=True)
            return None
            
        return fullPath
