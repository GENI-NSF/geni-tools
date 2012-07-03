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
Contains classes representing Ad, Request, and Manifest RSpecs.
These classes handle parsing rspecs, deriving restrictions and dependencies, 
calling Omni to submit requests to aggregates, and processing the returned manifests.
'''

import copy
import inspect
import logging
from lxml import etree as ElementTree ##lxml instead
import re
import time

import omni

#custom files
from defs import *
from exception import *
from stitchsession import *
import util


##Wrapper class for an Advertisement RSpec
#
class AdRSpec(object):
    ## Overridden obj creation function. Suppports dynamic subclassing
    #
    #   @param cls - See __new__ definition in python documentation
    #   @param rspecStr - The rspec XML string
    #   @param logger - The logging object to log output to
    #   @param *arguments - See __new__ definition in python documentation
    #   @param **keyword - See __new__ definition in python documentation
    #
    def __new__(cls, rspecStr, logger, *arguments, **keyword):
        rspecType = util.findRSpecFormat(rspecStr,logger)

        if rspecType is None:
            raise Exception, 'Unsupported RSpec format (none)!'

        # We really only support pgv2 or geniv3 types
        if rspecType != 'pgv2' and rspecType != 'geniv3':
            raise Exception, ('Unsupported RSpec format: %!' % rspecType)

        for subclass in AdRSpec.__subclasses__():
            if subclass.rspecType == rspecType:
                return super(cls, subclass).__new__(subclass, *arguments, **keyword)
            for subclass2 in subclass.__subclasses__():
                if subclass2.rspecType == rspecType:
                    return super(cls, subclass2).__new__(subclass2, *arguments, **keyword)

        raise Exception, ('Unsupported RSpec format %s!' % rspecType)


    ## The Constructor
    #
    #    @param rspecStr is the unprocessed XML string of an RSpec
    #    @param logger - The logging object to log output to
    # 
    def __init__(self, rspecStr, logger):
       
        self.logger = logger
        self.rspecStr = rspecStr
        ## @var self.rspecET - The ElementTree DOM for the XML string
        self.rspecET = ElementTree.fromstring(self.rspecStr)
        self.fromRSpec() 


    ## Returns the routes we learned after parsing this advertisement RSpec
    #
    #   @return Dictionary of interface->interface routes
    #
    def getRoutes(self):
        return self.routes


##Wrapper class for a PGV2 Ad RSpec
#
class PGV2AdRSpec(AdRSpec):
    rspecType = 'pgv2'
    ns_prefix = "{http://www.protogeni.net/resources/rspec/2}"
    stitch_ns_prefix = ns_prefix

    ## The Constructor
    #     
    #    @param rspecStr is the unprocessed XML string of an RSpec
    #    @param logger - The logging object to log output to
    # 
    def __init__(self, rspecStr, logger):
        super(PGV2AdRSpec,self).__init__(rspecStr,logger)


    ## Interprets the associated PGv2 Advert RSpec document.
    #
    # From the stitching element, find all Nodes in the Aggregate element
    # For each node, find the links and remotelinks
    # Save as a presetRoute for this AM URL, the link from that link ID (URN)
    # to the listed remotelink ID (URN)
    #
    #   @return True if success, False if failure
    #
    def fromRSpec(self):
        presetRoutes = {}
        ns_prefix=self.__class__.ns_prefix

        aggr_elems = self.rspecET.findall(self.stitch_ns_prefix+STCH_TAG+"/"+self.stitch_ns_prefix+AGGR_TAG)
        if len(aggr_elems)<1:
            raise  exception.TopologyCalculationException("Problem parsing advert: found no aggregate elements")
        
        for aggr_elem in aggr_elems:
            node_elems = aggr_elem.findall(self.stitch_ns_prefix+NODE_TAG)
            aggr_url = util.strifyEle(aggr_elem.get(URL_ID))

            presetRoutes[aggr_url]={}
            for node_elem in node_elems:
                link_elems = node_elem.findall(self.stitch_ns_prefix+PORT_TAG+"/"+self.stitch_ns_prefix+LINK_TAG)

                for link_elem in link_elems:
                    link_id = util.strifyEle(link_elem.get(ID_TAG))
                    remotelink_elem = link_elem.find(self.stitch_ns_prefix+RMOTLINK_TAG)

                    if remotelink_elem is None:
                        # FIXME: Exception or skip over this malformed element?
                        raise  exception.TopologyCalculationException("No RemoteLinkId found for link %s on node %s in Ad RSpec for AM at %s", str(link_id), str(node_elem), aggr_url)
        
                    remotelink_id = util.strifyEle(remotelink_elem.text)
                    presetRoutes[aggr_url][link_id]=remotelink_id
                    # A useful debug printout, but too verbose for most users?
                    #self.logger.debug("AM %s: Added presetRoute %s=%s", aggr_url, link_id, remotelink_id)

        self.routes = presetRoutes


##Wrapper class for a GENI3 Ad RSpec
#
class GENIV3AdRSpec(PGV2AdRSpec):
    rspecType = 'geniv3'
    ns_prefix = "{http://www.geni.net/resources/rspec/3}"
    stitch_ns_prefix = "{http://hpn.east.isi.edu/rspec/ext/stitch/0.1/}"

    ## The Constructor
    #
    #    @param rspecStr is the unprocessed XML string of an RSpec
    #    @param logger - The logging object to log output to
    #
    def __init__(self, rspecStr, logger):
        super(GENIV3AdRSpec,self).__init__(rspecStr,logger)


##Wrapper class for a Request RSpec
#
class ReqRSpec(object):

    ## Overridden obj creation function. Suppports dynamic subclassing
    #
    #   @param cls - See __new__ definition in python documentation
    #   @param rspecStr - The rspec XML string
    #   @param stitchSession - a query-able object, global to all RSpec objects
    #   @param logger - The logging object to log output to
    #   @param *arguments - See __new__ definition in python documentation
    #   @param **keyword - See __new__ definition in python documentation
    #
    def __new__(cls, rspecStr, stitchSession, logger, *arguments, **keyword):
        rspecType = util.findRSpecFormat(rspecStr,logger)

        if rspecType is None:
            raise Exception, 'Unsupported RSpec format (none)!'

        #print "From rspec starting with %s\n picked type %s" % (rspecStr[:150], rspecType)
        for subclass in ReqRSpec.__subclasses__(): 
            if rspecType == subclass.rspecType:
                #Use the correct subclass
                return super(cls, subclass).__new__(subclass, *arguments, **keyword) 
        raise Exception, 'Unsupported RSpec format %s!' % rspecType


    ## The Constructor
    #
    #    @param rspecStr is the unprocessed XML string of an RSpec
    #    @param stitchSession a query-able object, global to all RSpec objects
    #    @param logger - The logging object to log output to
    # 
    def __init__(self, rspecStr, stitchSession, logger):
        self.logger = logger
        ## @var self.dependsOn - A set of other ReqRSpecs that this one depends 
        #  on
        self.dependsOn = set()
        ## @var self.completed - Signifies when a ReqRSpec has been sent to 
        # aggregate and a manifest has been received
        self.completed = False
        ## @var self.started - Signifies when a ReqRSpec has started to be sent to 
        # an aggregate
        self.started = False
        ## @var self.rspecStr - A copy of the original ReqRSpec string
        self.rspecStr = rspecStr
        ## @var self.aggrURL - String URL of the aggregate manager
        self.aggrURL = util.stripHint(rspecStr)['url']
        ## @var self.fakeManifest - String path to a fake manifest to match this request
        fakeMan = util.findFakeManifest(rspecStr)
        if fakeMan:
            self.fakeManifestPath = fakeMan
        ## @var self.rspecET - The ElementTree DOM for the XML string
        self.rspecET = ElementTree.fromstring(self.rspecStr)
        ## @var self.manRSpec - A reference to this ReqRSpec's corresponding 
        # ManRSpec object after receipt from the aggregate
        self.manRSpec = None
        '''
        ## @var self.ifaceMap - Used by Max Manifest to map between internal and
        # demarcation ifaces #FIXME - Remove this eventually
        self.ifaceMap = {} 
        '''
        ## @var self.stitchSession - A reference to the global stitch session 
        # object
        self.stitchSession = stitchSession

        self.stitchSession.addAggregate(self) #register with the session

        ## @var self.rspecType - Signifies the type of the rspec 'pgv2', 'max'
        self.rspecType = self.__class__.rspecType 
        #Chris had this, which reset the var to MAX in the ION class
        # self.rspecType = self.stitchSession.getTypeFromAggrURL(self.aggrURL)

        ## @var self.restrictions - A dictionary of restrictions on this 
        # aggregate used to compute dependencies
        self.restrictions = Restrictions()

        ## @var self.requestedInterfaces - Dictionary by URN of properties of 
        # interfaces being requested, including:
        # [restrictions], [remoteIface], [remoteAggrURL]
        self.requestedInterfaces = {}

        # Parse bits out of the request Rspec XML
        self.fromRSpec()


    ## Outputs the ReqRSpec to an XML string
    #
    #   @return XML string of this ReqRSpec
    #
    def toRSpec(self):
        prefix = '<?xml version="1.0" encoding="UTF-8"?>\n' 
        #FIXME Not sure how to make ElementTree put this in for me...
        return prefix + ElementTree.tostring(self.rspecET,encoding="utf-8",method="xml")


    ## Determine which other RSpecs this one depends on.
    # This function is the heart of libstitch.
    #
    # If this AM does VLAN translation, and a neighbor does not,
    # then this AM depends on that neighbor
    # If neither does translation, and this AM is not already a dependency
    # of the neighbor, then calculate the intersection of the VLAN range,
    # add that restriction to both AMs, and make the neighbor a dependency
    # of this AM.
    #
    def calculateDeps(self):
        for iface in self.requestedInterfaces.keys():
            remoteAggrURL = self.requestedInterfaces[iface]['remoteAggrURL']
            remoteIface = self.requestedInterfaces[iface]['remoteIface']
            
            # If that remote AM is not one of the requestRSpecs on this session, 
            # then error/return
            if remoteAggrURL is None:
                self.logger.error("Request of %s lists interface %s at remote interface %s, but the remote AM URL is unknown!", self.aggrURL, iface, remoteIface)
                self.logger.debug("... one of your Ad RSpecs may have a typo in the remote interface name?")
                continue

            remoteAggrReqRSpec = self.stitchSession.getAggregate(remoteAggrURL)
            if not remoteAggrReqRSpec:
                self.logger.error("Request of %s lists interface %s that connects to AM at %s, interface %s. But we have no request RSpec for that remote aggregate!", self.aggrURL, iface, remoteAggrURL, remoteIface)
                continue
                # FIXME: Return? Raise?

            #If that remote AM is not one of my adjacent AMs, then
            # there is some kind of configuration error. log warning
            if not remoteAggrURL in self.stitchSession.aggrAdjMap[self.aggrURL]:
                self.logger.error("Request of %s lists interface %s that connects to AM at %s, interface %s. But our config doesn't show that AM as adjacent!", self.aggrURL, iface, remoteAggrURL, remoteIface)

            # If that remote interface is not in the requested interfaces
            # on the remote AM, then error/return
            if not remoteAggrReqRSpec.requestedInterfaces.has_key(remoteIface):
                self.logger.error("Request of %s lists interface %s that connects to AM at %s, interface %s. But the request RSpec for that AM doesn't request that interface!", self.aggrURL, iface, remoteAggrURL, remoteIface)


            # Now go through and user our rules to find dependencies.
            # Currently that means that of 2 neighbors, the one that does
            # VLAN translation depends on the one that does not.
            # If neither does translation, and we don't have a dependency rule
            # Then pick arbitrarily.
            # FIXME:
            # What if we aren't doing VLANs? What about other kinds of dependencies?

            # If this interface does translation,
            if self.getIfaceRestriction(iface, 'vlanTranslation') == False:
                # If the remote does not do translation, so is restricted
                if remoteAggrReqRSpec.getIfaceRestriction(remoteIface, 'vlanTranslation') == True:
                    # then remote AM depends on this AM
                    #self.logger.debug("AM %s Iface %s does VLAN Translation, neighbor iface %s does not. So neighbor %s depends on it", self.aggrURL, iface, remoteIface, remoteAggrURL)
                    self.addDependee(remoteAggrReqRSpec)
                else:
                    # This does translation, remote also does translation
                    # There is no dependency
                    #self.logger.debug("AM %s Iface %s does VLAN Translation, neighbor %s iface %s does too. So no dependency", self.aggrURL, iface, remoteAggrURL, remoteIface)
                    pass

            # Else if this interface does not do translation
            else:
                # If the remote does not do translation, so is restricted
                if remoteAggrReqRSpec.getIfaceRestriction(remoteIface, 'vlanTranslation') == True:
                    # and this AM is not a dependency of the other AM, 
                    if self.aggrURL not in remoteAggrReqRSpec.getDependencies():
                        #self.logger.debug("AM %s Iface %s does NOT do VLAN translation. Neighbor %s iface %s does not either, and doesn't depend on this AM. So add a dependency", self.aggrURL, iface, remoteAggrURL, remoteIface)

                        # then get intersection of vlanRanges on interfaces
                        # and set that as new restriction on both interfaces
                        #find common set of vlan ids
                        adjVlans = remoteAggrReqRSpec.getIFaceRestriction(remoteIface, 'vlanRange')
                        myVlans = self.getIfaceRestriction(iface, 'vlanRange')
                        newVlans = util.vlanListIntersection(adjVlans,myVlans)
                        # If new Vlans range is empty, then it's impossible
                        if len(newVlans) < 1:
                            self.logger.warn("Empty VLAN range intersection between this AM %s Iface %s and its neighbor %s IFace %s!", self.aggrURL, iface, remoteAggrURL, remoteIface)
                        self.setRestriction('vlanRange',newVlans)
                        remoteAggrReqRSpec.setRestriction('vlanRange',newVlans)
                        self.setIfaceRestriction(iface, 'vlanRange',newVlans)
                        remoteAggrReqRSpec.setIfaceRestriction(remoteIface, 'vlanRange',newVlans)
                        self.addDependee(remoteAggrReqRSpec)
                    else:
                        #self.logger.debug("AM %s Iface %s does NOT do VLAN translation. Neighbor %s iface %s does not either, but neighbor already depends on this. So DONT add a dependency", self.aggrURL, iface, remoteAggrURL, remoteIface)
                        pass
                else:
                    #self.logger.debug("AM %s iface %s does NOT do VLAN translation. Neighbor %s iface %s DOES, so the neighbor will depend on this. So DONT add a dependency", self.aggrURL, iface, remoteAggrURL, remoteIface)
                    pass

# Old code below, kept for now as a comment....
        '''
        # If this request is not restricted by VLAN Translation,
        # then it does VLAN translation. A neighbor that does
        # not do VLAN translation will have to go first. So
        # this ReqRSpec/AM will depend on the other
        if self.getRestriction('vlanTranslation') == False:
            for aggr in self.stitchSession.getAdjacentAggrList(self.aggrURL):
                if aggr.getRestriction('vlanTranslation') == True:
                    self.logger.debug("AM %s does VLAN Translation. So neighbor %s depends on it", self.aggrURL, aggr.aggrURL)
                    self.addDependee(aggr)
            
            #FIXME: Rule here should instead be: find all my interfaces in request
            # From presetRoutes, find remote AM and interface for each

            # To do this, ReqRSpec needs a dict of requestedInterfaces, with multiple
            # members: [restrictions], [remoteIface], [remoteAggrURL]

            # subclasses need to fill in restrictions

        elif self.getRestriction('vlanTranslation') == True:
            # This AM/ReqRSpec does not do VLAN Translation
            # It might depend on a neighbor if that neighbor
            # also doesn't do vlan translation
            for aggr in self.stitchSession.getAdjacentAggrList(self.aggrURL):
                if aggr.getRestriction('vlanTranslation') == True:
                    if self.aggrURL not in aggr.getDependencies():
                        self.logger.debug("AM %s does NOT do VLAN translation. Neighbor %s does not either, and doesn't depend on it. So add a dependency", self.aggrURL, aggr.aggrURL)
                        #find common set of vlan ids
                        adjVlans = aggr.getRestriction('vlanRange')
                        myVlans = self.getRestriction('vlanRange')
                        newVlans = util.vlanListIntersection(adjVlans,myVlans)
                        # If new Vlans range is empty, then it's impossible
                        if len(newVlans) < 1:
                            self.logger.warn("Empty VLAN range intersection between this AM %s and its neighbor %s!", self.aggrURL, aggr.aggrURL)
                        self.setRestriction('vlanRange',newVlans)
                        aggr.setRestriction('vlanRange',newVlans)
                        self.addDependee(aggr)
                    else:
                        self.logger.debug("AM %s does NOT do VLAN translation. Neighbor %s does not either, but neighbor already depends on this. So DONT add a dependency", self.aggrURL, aggr.aggrURL)
                else:
                    self.logger.debug("AM %s does NOT do VLAN translation. Neighbor %s DOES, so the neighbor will depend on this. So DONT add a dependency", self.aggrURL, aggr.aggrURL)
        '''

        ##TODO - Somewhere here is where we need to add negotiation 


    ## Set a restriction value in this RSpec. 
    # This function is basically a setter for a Dictionary value.  
    # 
    #     @param rest - The name of the restriction
    #     @param val - The value of the restriction 
    #     
    def setRestriction(self, rest, val):
        self.restrictions.setRestriction(rest,val)


    ## Get a restriction value from this RSpec.
    # This function is basically a getter for a Dictionary value.  
    #     
    #     @param rest - The name of the restriction
    #     @return The restriction value for the given restriction
    #     
    def getRestriction(self, rest):
        return self.restrictions.getRestriction(rest)


    ## Set a restriction value for a particular interface in this RSpec. 
    # This function is basically a setter for a Dictionary value.  
    # 
    #     @param iface - URN of the interface being restricted
    #     @param rest - The name of the restriction
    #     @param val - The value of the restriction 
    #     
    def setIfaceRestriction(self, iface, rest, val):
        if not self.requestedInterfaces.has_key(iface):
            self.requestedInterfaces[iface] = {}
        if not self.requestedInterfaces[iface].has_key('restrictions'):
            self.requestedInterfaces[iface]['restrictions'] = Restrictions()

        self.requestedInterfaces[iface]['restrictions'].setRestriction(rest,val)


    ## Get a restriction value from this RSpec for a particular interface URN
    # This function is basically a getter for a Dictionary value.  
    #     
    #     @param iface - URN of the interface being restricted
    #     @param rest - The name of the restriction
    #     @return The restriction value for the given restriction, interface
    #     
    def getIfaceRestriction(self, iface, rest):
        if not self.requestedInterfaces.has_key(iface):
            return Restrictions()
        if not self.requestedInterfaces[iface].has_key('restrictions'):
            self.requestedInterfaces[iface]['restrictions'] = Restrictions()

        return self.requestedInterfaces[iface]['restrictions'].getRestriction(rest)


    ## Add an RSpec object which this one depends on.
    #     
    #     @param aggr - An ReqRSpec object
    #     
    def addDependee(self, aggr):
        self.dependsOn = self.dependsOn.union(set([aggr]))
     
     
    ## Print out the dependencies which have been calculated.
    #     
    #     @return A list of Aggregate URL's this aggregate depends on     
    #     
    def getDependencies(self):

        deps = []
        for dep in self.dependsOn:
            deps.append(dep.aggrURL)
        return deps


    ## Tells whether this ReqRSpec has other ReqRSpecs it depends on
    #     
    #     @return True if this aggregate has a dependency, False otherwise     
    #     
    def hasDependencies(self):
        if len(self.dependsOn)>0:
            return True
        return False

    ## Simulate submission of this RSpec to its corresponding aggregate.
    # This function just uses manifests read in from files as 'responses'
    #     
    #     @param tmp_filename - The name of the temporary in which the XML RSpec
    #     sits
    #     @param options - The omni options to use in the submission 
    #     @return True if success, False if failure
    #     
    def doFakeRequest(self,tmp_filename,options):
        filename = ""
        if self.completed:
            self.logger.warn("Do not redo doFake %s: already marked completed", self.aggrURL)
            return True

        self.completed = True

        ##Find the path of this module
        mod = inspect.getmodule(self)
        path = os.path.dirname(mod.__file__)
        filename = os.path.join(path,self.fakeManifestPath)
        if not os.path.exists(filename):
            self.logger.error("Missing fake manifest file %s", filename)
            return False

        fh = open(filename)
        self.manRSpec = ManRSpec(fh.read(),self,self.stitchSession,self.logger)
        fh.close()
#        self.logger.debug("ReqRSpec of type %s using fakeManifest from %s, created ManRSpec of type %s", self.rspecType, self.fakeManifestPath, self.manRSpec.rspecType)
        self.logger.info("ReqRSpec of type %s using fakeManifest from %s", self.rspecType, self.fakeManifestPath)
        return True


##Wrapper class for a MAX Request RSpec
#
class MaxReqRSpec(ReqRSpec):
    rspecType = 'max'
#    fakeManifestPath = "../samples/max-manifest.xml"

    ## The Constructor
    #
    #    @param rspecStr is the unprocessed XML string of an RSpec.
    #    @param stitchSession is a dictionary of session information, global to
    #    all RSpec objects.
    #    @param logger - The logging object to log output to
    # 
    def __init__(self, rspecStr, stitchSession, logger):
        super(MaxReqRSpec,self).__init__(rspecStr,stitchSession,logger)


    ## Interprets the associated RSpec document as a Max-native format RSpec.
    # Scrape and fill in a few class variables based on the document contents.
    #     
    # Also insert the given slicename and update the timestamps in the dom
    #
    #   @return True if success, False if failure
    #
    def fromRSpec(self):

        self.logger.info("Using MAX native parser for this file for Agg "+str(self.aggrURL))
        self.insertSliceName()
        self.insertExpiry(defaultExpDuration)

        # calculateRestrictions fills in self.requestedInterfaces

        # Old code kept for now...
        '''
        ns_prefix = "{"+self.stitchSession.getNamespaceFromType(self.rspecType)+"}"
        comp_iface_elems = self.rspecET.findall(ns_prefix+RSPEC_TAG+"/"+ns_prefix+COMPRSRC_TAG+"/"+ns_prefix+PLABNODE_TAG+"/"+ns_prefix+NETIFACE_TAG)

        #Special step only for MAX
        # FIXME: Figure out the point of this and document it
        for comp_iface_elem in comp_iface_elems:
            iface_id = util.strifyEle(comp_iface_elem.get(ID_TAG))
 
            iface_urn_elems = self.rspecET.findall(ns_prefix+STCHRSRC_TAG+"/"+ns_prefix+NETIFACEURN_TAG)
            tmp = []
 
            for iface_urn_elem in iface_urn_elems:
                tmp.append(util.strifyEle(iface_urn_elem.text))

            if iface_id in tmp and len(tmp)>1: 
                #FIXME This is terribly arbitrary.

                if tmp.index(iface_id)>=len(tmp)-1:
                    self.ifaceMap[iface_id] = tmp[tmp.index(iface_id)-1] 
                else:
                    self.ifaceMap[iface_id] = tmp[tmp.index(iface_id)+1] 
            '''

        return True


    ## Calculate the restrictions on this Max RSpec/aggregate based on the 
    # information in it's DOM. This is the step before determining dependencies.
    #     
    #     @return True if success, False if failure
    #   
    def calculateRestrictions(self):
        #print "Max"

        # FIXME
        # MAX native requests show you the internal interface
        # to get to the host. From that,
        # you can get a vlanRange element, in the compResc section
        # try to use that?
        # link -> attachedLinkUrn that looks normal
        # and that attachedLinkUrn may be in the Ad (not my trimmed one)?
        # and also may be in a non trimmed stitching section?
        # For now we ignore requested interfaces in stitching section
        # that are not advertised, and similarly ignore compResc ifaces
        # that are not advertised and requested

        ns_prefix = "{"+self.stitchSession.getNamespaceFromType(self.rspecType)+"}"
        #Make a list of all stitching-related interface urns 
        stitch_network_iface_urn_elems = self.rspecET.findall(ns_prefix+RSPEC_TAG+"/"+ns_prefix+STCHRSRC_TAG+"/"+ns_prefix+NETIFACEURN_TAG)

        # Note here we do not error out if there are no such elements
        # The idea being that maybe you just reserved compute
        # resources here. Not much to stitch, but so be it.

        # For each stitching/net interface that we advertised
        # (which weeds out internal things like ...=eth1.any_stitching)
        # Put that in a dictionary of requested interfaces,
        # And note the advertised remote interface and aggregate,
        # and note that this interface does not do VLAN translation
        for stitch_network_iface_urn_elem in stitch_network_iface_urn_elems:

            ifaceURNStr = util.strifyEle(stitch_network_iface_urn_elem.text)
            #self.logger.debug("MAX req for stitch/netIface %s", ifaceURNStr)

            #If I own the interface continue
            if self.stitchSession.aggrHasIface(self.aggrURL,ifaceURNStr):
                remoteURN = self.stitchSession.getAggrURNRoute(self.aggrURL, ifaceURNStr)
                #self.logger.debug("... is advertised start to link to %s", remoteURN)
                if not self.requestedInterfaces.has_key(ifaceURNStr):
                    self.logger.debug("Adding Max requested interface %s", ifaceURNStr)
                    self.requestedInterfaces[ifaceURNStr] = {}
                self.requestedInterfaces[ifaceURNStr]['remoteIface']=remoteURN
                self.requestedInterfaces[ifaceURNStr]['remoteAggrURL']=self.stitchSession.getAggrURNRemoteAggr(self.aggrURL, ifaceURNStr)

                self.setIfaceRestriction(ifaceURNStr, 'vlanTranslation',True) 

                # Do MAX compute net interfaces not have the vlan_range
                # tag, like ION does? Guess not. For MAX we have
                # to match compute and stitching then

            else:
                # Not an interface we advertised. Maybe of the form ....=eth1.any_stitching?
                #self.logger.debug("... Not adding unadvertised but requested max stitch iface %s", ifaceURNStr)
                pass

        #######################################
        #Determine vlan range restrictions
        #######################################
        # VLAN ranges are in the compute/interface elements
        # So for each which represents a stitching requested and
        # advertised interface, put the requested vlan_range
        # as a restriction

        # Get compute elements' interfaces
        comp_iface_elems = self.rspecET.findall(ns_prefix+RSPEC_TAG+"/"+ns_prefix+COMPRSRC_TAG+"/"+ns_prefix+PLABNODE_TAG+"/"+ns_prefix+NETIFACE_TAG)

        # MAX only makes sense if you reserved a compute resource
        # FIXME: Must it have a net interface too? Or should I
        # skip this error?
        if len(comp_iface_elems)<1:
            self.logger.error("Problem parsing MAX! I didn't find the nodes I was expecting. No iface in rspec/compresource/plabnode/netiface")
            raise RSpecRestrictionException(self.aggrURL)

        #Look through those compute resource network interfaces
        for iface_elem in comp_iface_elems:
            
            #If a computeResource is being requested, it is implied that we own 
            #the resource so we don't need to check
            ifaceURNStr = iface_elem.get(ID_TAG)
            thisCleanURN = None
            if ifaceURNStr:
                thisCleanURN = util.strifyEle(ifaceURNStr)
                
            #self.logger.debug("Max comp iface ID %s", ifaceURNStr)
            if thisCleanURN and thisCleanURN in self.requestedInterfaces.keys():
                #self.logger.debug("%s is in the stitching section", ifaceURNStr)
                # Based on above, we know
                # We're requesting an interface we own, in our presetRoutes table
                # The AM on the other end of that link is a potential dependee
                
                #If the vlan has restrictions, set it as a vlan 
                #restriction
                vlan_range = iface_elem.find(ns_prefix+VLANRANG_TAG)
                if vlan_range is not None:
                    self.setRestriction('vlanRange',util.vlanListIntersection(util.vlanRangeToList(util.strifyEle(vlan_range.text)),self.getRestriction('vlanRange')))
                    self.setIfaceRestriction(thisCleanURN, 'vlanRange',util.vlanListIntersection(util.vlanRangeToList(util.strifyEle(vlan_range.text)),self.getIfaceRestriction(thisCleanURN, 'vlanRange')))
#                    self.logger.debug("Set vlanRange restriction using %s to %s", vlan_range.text, self.getIfaceRestriction(thisCleanURN, 'vlanRange'))
                    self.logger.debug("Set vlanRange restriction using %s", vlan_range.text)
                else:
                    self.logger.error("vlan_range is None on interface %s, aggregate URL %s", thisCleanURN, self.aggrURL)
                    raise RSpecRestrictionException(self.aggrURL)
            else:
                # ifaceURNStr is None or is an interface
                # not advertised by us or not in stitch/network interfaces
                # Comprsrch/plabnode/net iface listed a URN
                # That is not both advertised by this AM and in stitch/net iface,
                # or the URN was None

                # Is that a problem? This includes the MAX interface
                # urn:aggregate=geni.maxgigapop.net:rspec=bbn_ahtest:domain=dragon.maxgigapop.net:node=planetlab2:interface=eth1.any_stitching
                #self.logger.debug("AM %s requested com resource/plab/net IFace that was not both advertised and in stitch/network interfaces: %s", self.aggrURL, thisCleanURN)
#                raise RSpecRestrictionException(self.aggrURL)
                pass

        self.setRestriction('vlanTranslation',True) 
        #there is nothing about this in the schema right now

        return True


    ## Insert any relevant Vlan information into this RSpec
    # This function is not required at this time for Max, it is here for 
    # completions sake 
    #     
    #     @param vlan_map - A dictionary of interfaceUrn's -> Assigned Vlan Id's
    #     @return True if success, False if failure
    #     
    def insertVlanData(self, vlan_map):
        return True #Nothing to do here yet


    ## Insert a given expiry into the Max (and Ion) RSpec dom
    # This is mainly for the GEC11 Demo and should be removed when possible.
    #      
    #     @param duration - int duration in seconds to set the slice lifetime to
    #     in the RSpec
    #     @return True if success, False if failure
    #      
    def insertExpiry(self, duration):       
        ns_prefix = "{"+self.stitchSession.getNamespaceFromType(self.rspecType)+"}"

        ctrlplane_ns_prefix = "{"+self.stitchSession.getExtNamespaceFromType(self.rspecType,"ctrlplane")+"}"
        duration = int(duration)

        if duration < 0:
            self.logger.error("The given experiment duration is < 0")
            return False

        start = int(time.time())
        end = start+duration
        lifetime_elem = self.rspecET.find(ns_prefix+RSPEC_TAG+"/"+ns_prefix+LIFETIME_TAG)
        
        if lifetime_elem is None:
            self.logger.error("Unable to locate lifetime tag")
            return False

        start_elem = lifetime_elem.find(ctrlplane_ns_prefix+STRT_TAG)
        end_elem = lifetime_elem.find(ctrlplane_ns_prefix+END_TAG)

        if start_elem is None or end_elem is None:
            self.logger.error("Unable to locate start/end tag")
            return False

        start_elem.text=str(start)
        end_elem.text=str(end)
        lifetime_elem.set("id","time-"+str(start)+"-"+str(end))

        return True


    ## Insert the RSpec slicename into the Max (and Ion) RSpec dom
    # This is mainly for the GEC11 Demo and should be removed when possible.
    #      
    def insertSliceName(self):
        ns_prefix = "{"+self.stitchSession.getNamespaceFromType(self.rspecType)+"}"

        slice_name = self.stitchSession.getSiteNamePrefix()+self.stitchSession.getSliceName()

        inner_rspec = self.rspecET.find(ns_prefix+RSPEC_TAG)
        if inner_rspec is not None:
            inner_rspec.set(ID_TAG,slice_name) #rspec->id
        
        stitching_resource_elem = self.rspecET.find(ns_prefix+RSPEC_TAG+"/"+ns_prefix+STCHRSRC_TAG) #rspec/stitchingResource->id

        if stitching_resource_elem is not None:
            old_urn = util.strifyEle(stitching_resource_elem.get(ID_TAG))
            new_urn = re.sub(maxURNSliceNameRegex,"\\1"+slice_name+"\\3",old_urn)
            stitching_resource_elem.set(ID_TAG,new_urn)

            iface_urn_elems = stitching_resource_elem.findall(ns_prefix+NETIFACEURN_TAG) #rspec/stitchingResource/networkInterfaceUrn
            if len(iface_urn_elems)>0:
                for iface_urn_elem in iface_urn_elems:
                    old_urn = util.strifyEle(iface_urn_elem.text)
                    new_urn = re.sub(maxURNSliceNameRegex,"\\1"+slice_name+"\\3",old_urn)
                    iface_urn_elem.text = new_urn

        compute_resource_elem = self.rspecET.find(ns_prefix+RSPEC_TAG+"/"+ns_prefix+COMPRSRC_TAG) #rspec/computeResource->id
        if compute_resource_elem is not None:
            old_urn = util.strifyEle(compute_resource_elem.get(ID_TAG))
            new_urn = re.sub(maxURNSliceNameRegex,"\\1"+slice_name+"\\3",old_urn)
            compute_resource_elem.set(ID_TAG,new_urn)

            plab_resource_elems = compute_resource_elem.findall(ns_prefix+PLABNODE_TAG) #rspec/computeResource/planetlabNodeSliver[]->id
            if len(plab_resource_elems)>0:
                for plab_resource_elem in plab_resource_elems:
                    old_urn = util.strifyEle(plab_resource_elem.get(ID_TAG))
                    new_urn = re.sub(maxURNSliceNameRegex,"\\1"+slice_name+"\\3",old_urn)
                    plab_resource_elem.set(ID_TAG,new_urn)

                    iface_elems = plab_resource_elem.findall(ns_prefix+NETIFACE_TAG) #rspec/computeResource/planetlabNodeSliver[]/networkInterface[]->id
                    if len(iface_elems)>0:
                        for iface_elem in iface_elems:
                            old_urn = util.strifyEle(iface_elem.get(ID_TAG))
                            new_urn = re.sub(maxURNSliceNameRegex,"\\1"+slice_name+"\\3",old_urn)
                            iface_elem.set(ID_TAG,new_urn)


    ## Submit this RSpec to Max aggregate 
    # This function calls 'createsliver' once. 'createsliver' on Max does not at
    # this time repond with a manifest. After a successful sliver creation, it 
    # will continue to poll the  aggregate with 'sliverstatus' until it get's a
    # favourable 
    # response indicating that the sliver is ready. It then calls
    # 'listresources' which will repond with a manifest. 
    # The function will then store the Manifest and return.
    #     
    #     @param tmp_filename - The name of the temporary in which the XML RSpec
    #     sits
    #     @param options - The omni options to use in the submission 
    #     @return True if success, False if failure
    #      
    def doRequest(self, tmp_filename, options):
        # FIXME: Use GetVersion to determin API # and RSpec type
        omniargs = ["--api-version", "2", "-t", "SFA", "1", "-a",self.aggrURL,"-o","createsliver",self.stitchSession.getSliceName(), tmp_filename] 
        result = None
        text = ""
        try:
            text, result = omni.call(omniargs, options)
            #self.logger.debug("Omni createsliver call to %s returned", self.aggrURL)
        except:
            self.logger.error("Failed to createsliver %s at %s", self.stitchSession.getSliceName(), self.aggrURL, exc_info=True)
            return False

        #result should be the req rspec we just sent. 
        if result is None or str(result).strip() == "":
            self.logger.error("No ~manifest~ returned by MAX?! Got text %s", text)
            return False

        # - Need to poll with sliverstatus now and wait for 'ready'
        # - Once ready, use listresources <slivername> to get manifest
        ready = False
        result = ""
        for i in range(0,pollMaxAttempts):
            self.logger.info("Polling MAX for sliver status...")

            omniargs = ["--api-version", "2", "-t", "SFA", "1", "-a",self.aggrURL,"-o","sliverstatus",self.stitchSession.getSliceName()] 
            try:
                text, result = omni.call(omniargs, options)
            except:
                self.logger.error("Failed to get sliverstatus on %s at %s", self.stitchSession.getSliceName(), self.aggrURL, exc_info=True)
                # Hope that this is transient? alternative would be to break, assuming we've failed
#                time.sleep(aggrPollIntervalSec)
#                continue
                break

            if isinstance(result,dict) and result.has_key(self.aggrURL) and isinstance(result[self.aggrURL],dict) and result[self.aggrURL].has_key('geni_status'):
                if result[self.aggrURL]['geni_status'] == 'configuring':
                    time.sleep(aggrPollIntervalSec)
                    continue
                elif result[self.aggrURL]['geni_status'] == 'failed':
                    self.logger.error("Slice creation failed")
                    break
                elif result[self.aggrURL]['geni_status'] == 'unknown':
                    self.logger.error("Slice in Unknown State")
                    break
                elif result[self.aggrURL]['geni_status'] == 'ready':
                    ready = True
                    break
                else:
                    self.logger.error("Slice at MAX in Unknown State "+str(result[self.aggrURL]['geni_status']))
                    break
            else:
                self.logger.error("Return sliverstatus from MAX Aggregate was invalid: \n"+str(result))
                break

        if not ready:
            return ready

        self.logger.info("Slice created successfully at MAX, attempting to obtain manifest")

        omniargs = ["--api-version", "2", "-t", "SFA", "1", "-a",self.aggrURL,"-o","listresources",self.stitchSession.getSliceName()] 
        try:
            text, result = omni.call(omniargs, options)
        except:
            self.logger.error("Failed to listresources on %s at %s", self.stitchSession.getSliceName(), self.aggrURL, exc_info=True)
            return False

        if not (result != None and isinstance(result, dict) and len(result.keys()) == 1):
            self.logger.error("MAX Manifest Result wasnt a dictionary with 1 entry? "+ str(result))
            return False
        manspec_str = result.values()[0]
          
        try:
            self.manRSpec = ManRSpec(manspec_str,self,self.stitchSession, self.logger)
        except:
            import traceback
            traceback.print_exc()
            self.logger.error("The MAX manifest received was not formatted correctly: "+str(manspec_str))
            self.logger.error(text)
            self.logger.error("Omni ran with args: "+str(omniargs))
            return False

        return ready


##Wrapper class for an ION Request RSpec
#
class IonReqRSpec(ReqRSpec):
    # FIXME: Make this a subclass of MaxReqRSpec

    rspecType = 'ion'
#    fakeManifestPath = "../samples/ion-manifest.xml"

    ## The Constructor
    #     
    #    @param rspecStr is the unprocessed XML string of an RSpec
    #    @param stitchSession is a dictionary of session information, global to
    #    all RSpec objects
    #    @param logger - The logging object to log output to
    # 
    def __init__(self, rspecStr, stitchSession, logger):
        super(IonReqRSpec,self).__init__(rspecStr,stitchSession,logger)

    ## Interprets the associated RSpec document as an Ion-native format RSpec.
    # Scrape and fill in a few class variables based on the document contents.
    # Also insert the given slicename and update the timestamps in the dom.
    #
    #   @return True if success, False if failure
    #
    def fromRSpec(self):
        self.logger.info("Using Ion native parser for this file for Agg "+self.aggrURL)
        self.insertSliceName()
        self.insertExpiry(defaultExpDuration)

        # CalculateRestrictions fills in self.requestedInterfaces
        return True


    ## Calculate the restrictions on this Ion RSpec/aggregate based on the 
    # information in it's DOM. This is the step before determining dependencies.
    #     
    #     @return True if success, False if failure
    #   
    def calculateRestrictions(self):
        #print "Ion"

        ns_prefix = "{"+self.stitchSession.getNamespaceFromType(self.rspecType)+"}"
        #Make a list of all stitching-related interfaces
        stitch_network_iface_elems = self.rspecET.findall(ns_prefix+RSPEC_TAG+"/"+ns_prefix+STCHRSRC_TAG+"/"+ns_prefix+NETIFACE_TAG)

        # ION only makes sense when you request stitching bits
        if len(stitch_network_iface_elems)<1:
            self.logger.error("Problem parsing ION! I didn't find the nodes I was expecting. No iface in rspec/stitch/netiface")
            return False

        #######################################
        #Determine vlan range restrictions
        #######################################
        #Look through stitching ifaces. 
        for stitch_network_iface_elem in stitch_network_iface_elems:

            ifaceURNStr = util.strifyEle(stitch_network_iface_elem.get(ID_TAG))
            #self.logger.debug("ION stitch/netIface %s", ifaceURNStr)

            #If I own the interface continue
            if self.stitchSession.aggrHasIface(self.aggrURL,ifaceURNStr):
                # The Interface is a key in the ad presetRoutes, so I own it
                # the AM on the other end is a potential dependency/dependee
                remoteURN = self.stitchSession.getAggrURNRoute(self.aggrURL, ifaceURNStr)
                #self.logger.debug("... is advertised start to link to %s", remoteURN)
                if not self.requestedInterfaces.has_key(ifaceURNStr):
                    self.logger.debug("Adding ION requested interface %s", ifaceURNStr)
                    self.requestedInterfaces[ifaceURNStr] = {}
                self.requestedInterfaces[ifaceURNStr]['remoteIface']=remoteURN
                self.requestedInterfaces[ifaceURNStr]['remoteAggrURL']=self.stitchSession.getAggrURNRemoteAggr(self.aggrURL, ifaceURNStr)

                # Hard coded knowledge about the aggregate, ugly
                self.setIfaceRestriction(ifaceURNStr, 'vlanTranslation',False) 

                # Note for ION we get the vlan_range from the stitching
                # network interface, where for MAX we get the requested
                # interfaces from the compute, but get the 
                # vlan_range from the stitching element

                #If the vlan has restrictions, set it as a vlan restriction
                vlan_range = stitch_network_iface_elem.find(ns_prefix+VLANRANG_TAG)
                if vlan_range is not None:
                    self.setRestriction('vlanRange',util.vlanListIntersection(util.vlanRangeToList(util.strifyEle(vlan_range.text)),self.getRestriction('vlanRange')))
                    self.setIfaceRestriction(ifaceURNStr, 'vlanRange',util.vlanListIntersection(util.vlanRangeToList(util.strifyEle(vlan_range.text)),self.getIfaceRestriction(ifaceURNStr, 'vlanRange')))
                    self.logger.debug("Set vlanRange restriction using %s", vlan_range.text)

                else:
                    # vlan_range was none
                    self.logger.error("vlan_range is None on interface %s, aggregate URL %s", ifaceURNStr, self.aggrURL)
                    raise RSpecRestrictionException(self.aggrURL)
            else:
                # Not an advertised interface
                # FIXME: Error?
                self.logger.debug("Not an advertised interface but requested: %s", ifaceURNStr)
                #pass

        self.setRestriction('vlanTranslation',False) 
        #there is nothing about this in the schema right now

        return True


    ## Insert any relevant Vlan information into this RSpec
    # This function searches in vlan_map for any interface urn's contained in
    # this RSpec and updates the RSpec with any Vlans that were assigned to 
    # those interfaces
    #     
    #     @param vlan_map - A dictionary of interfaceUrn's -> Assigned Vlan Id's
    #     @return True if success, False if failure
    #     
    def insertVlanData(self, vlan_map):
        if vlan_map is None or len(vlan_map.keys()) < 1:
            return True

        ns_prefix = "{"+self.stitchSession.getNamespaceFromType(self.rspecType)+"}"
        stitch_network_iface_elems = self.rspecET.findall(ns_prefix+RSPEC_TAG+"/"+ns_prefix+STCHRSRC_TAG+"/"+ns_prefix+NETIFACE_TAG)

        if len(stitch_network_iface_elems)<1:
            self.logger.error("Problem parsing ION! I didn't find the nodes I was expecting. No iface in rspec/stitch/netiface")
            return False

        for stitch_network_iface_elem in stitch_network_iface_elems:
            iface_id = util.strifyEle(stitch_network_iface_elem.get(ID_TAG))

            ##If a vlan was assigned to this iface, insert it into this RSpec
            if vlan_map.has_key(iface_id):
                vlan_rang_elem = stitch_network_iface_elem.find(ns_prefix+VLANRANG_TAG)

                # If we found a vlan element and the interface URN is a route advertised
                # by this aggregate, then we'll stick that vlan ID for that interface
                # here in this element
                if vlan_rang_elem is not None and self.stitchSession.aggrHasRouteURN(self.aggrURL,iface_id):
                    self.logger.info(" ---> Inserting Vlan: "+str(vlan_map[iface_id])+" for Interface: "+iface_id)
                    vlan_rang_elem.text = vlan_map[iface_id] 
                    #Here we actually write the given vlans into the request rspec
                else:
                    self.logger.debug("vlan_map had key %s in our request, but....", iface_id)
                    if vlan_range_elem is None:
                        self.logger.debug("found no vlan_rang_elem")
                    else:
                        self.logger.debug("No advertised route from that interface")

        return True


    ## Insert a given expiry into the Max (and Ion) RSpec dom. 
    # This is mainly for the GEC11 Demo and should be removed when possible.
    #      
    #     @param duration - int duration in seconds to set the slice lifetime to
    #     in the RSpec
    #     @return True if success, False if failure
    #      
    def insertExpiry(self, duration):
        ns_prefix = "{"+self.stitchSession.getNamespaceFromType(self.rspecType)+"}"
        ctrlplane_ns_prefix = "{"+self.stitchSession.getExtNamespaceFromType(self.rspecType,"ctrlplane")+"}"
        duration = int(duration)

        if duration < 0:
            self.logger.error("The given experiment duration is < 0")
            return False

        start = int(time.time())
        end = start+duration
        lifetime_elem = self.rspecET.find(ns_prefix+RSPEC_TAG+"/"+ns_prefix+LIFETIME_TAG)
 
        if lifetime_elem is None:
            self.logger.error("Unable to locate lifetime tag")
            return False

        start_elem = lifetime_elem.find(ctrlplane_ns_prefix+STRT_TAG)
        end_elem = lifetime_elem.find(ctrlplane_ns_prefix+END_TAG)

        if start_elem is None or end_elem is None:
            self.logger.error("Unable to locate start/end tag")
            return False

        start_elem.text=str(start)
        end_elem.text=str(end)
        lifetime_elem.set("id","time-"+str(start)+"-"+str(end))

        return True


    ## Insert the RSpec slicename into the Max (and Ion) RSpec dom
    # This is mainly for the GEC11 Demo and should be removed when possible.
    #      
    def insertSliceName(self):
        ns_prefix = "{"+self.stitchSession.getNamespaceFromType(self.rspecType)+"}"

        slice_name = self.stitchSession.getSiteNamePrefix()+self.stitchSession.getSliceName()

        inner_rspec = self.rspecET.find(ns_prefix+RSPEC_TAG)
        if inner_rspec is not None:
            inner_rspec.set(ID_TAG,slice_name) #rspec->id
 
        stitching_resource_elem = self.rspecET.find(ns_prefix+RSPEC_TAG+"/"+ns_prefix+STCHRSRC_TAG) #rspec/stitchingResource->id

        if stitching_resource_elem is not None:
            old_urn = util.strifyEle(stitching_resource_elem.get(ID_TAG))
            new_urn = re.sub(maxURNSliceNameRegex,"\\1"+slice_name+"\\3",old_urn)
            stitching_resource_elem.set(ID_TAG,new_urn)
            iface_urn_elems = stitching_resource_elem.findall(ns_prefix+NETIFACEURN_TAG) #rspec/stitchingResource/networkInterfaceUrn

            if len(iface_urn_elems)>0:
                for iface_urn_elem in iface_urn_elems:
                    old_urn = util.strifyEle(iface_urn_elem.text)
                    new_urn = re.sub(maxURNSliceNameRegex,"\\1"+slice_name+"\\3",old_urn)
                    iface_urn_elem.text = new_urn

            '''
            ext_iface_urn_elems = stitching_resource_elem.findall(ns_prefix+EXTRSRCID_TAG) #rspec/stitchingResource/externalResourceId
            if len(ext_iface_urn_elems)>0:
                for ext_iface_urn_elem in ext_iface_urn_elems:
                    old_urn = ext_iface_urn_elem.text
                    new_urn = re.sub(maxURNSliceNameRegex,"\\1"+slice_name+"\\3",old_urn)
                    ext_iface_urn_elem.text = new_urn
            '''

        compute_resource_elem = self.rspecET.find(ns_prefix+RSPEC_TAG+"/"+ns_prefix+COMPRSRC_TAG) #rspec/computeResource->id
        if compute_resource_elem is not None:
            old_urn = util.strifyEle(compute_resource_elem.get(ID_TAG))
            new_urn = re.sub(maxURNSliceNameRegex,"\\1"+slice_name+"\\3",old_urn)
            compute_resource_elem.set(ID_TAG,new_urn)

            plab_resource_elems = compute_resource_elem.findall(ns_prefix+PLABNODE_TAG) #rspec/computeResource/planetlabNodeSliver[]->id
            if len(plab_resource_elems)>0:
                for plab_resource_elem in plab_resource_elems:
                    old_urn = util.strifyEle(plab_resource_elem.get(ID_TAG))
                    new_urn = re.sub(maxURNSliceNameRegex,"\\1"+slice_name+"\\3",old_urn)
                    plab_resource_elem.set(ID_TAG,new_urn)

                    iface_elems = plab_resource_elem.findall(ns_prefix+NETIFACE_TAG) #rspec/computeResource/planetlabNodeSliver[]/networkInterface[]->id
                    if len(iface_elems)>0:
                        for iface_elem in iface_elems:
                            old_urn = util.strifyEle(iface_elem.get(ID_TAG))
                            new_urn = re.sub(maxURNSliceNameRegex,"\\1"+slice_name+"\\3",old_urn)
                            iface_elem.set(ID_TAG,new_urn)



    ## Submit this RSpec to Ion aggregate 
    # This function calls 'createsliver' once. 'createsliver' on Ion does not at
    # this time repond with a manifest. After a successful sliver creation, it 
    # will continue to poll the  aggregate with 'sliverstatus' until it get's a
    # favourable  response indicating that the sliver is ready. It then calls
    # 'listresources' which will repond with a manifest. The function will then 
    # store the Manifest and return.
    #     
    #     @param tmp_filename - The name of the temporary in which the XML RSpec
    #     sits
    #     @param options - The omni options to use in the submission 
    #     @return True if success, False if failure
    #     
    def doRequest(self, tmp_filename, options):
        # FIXME: Use GetVersion to determin API # and RSpec type
        omniargs = ["--api-version", "2", "-t", "SFA", "1", "-a",self.aggrURL,"-o","createsliver",self.stitchSession.getSliceName(), tmp_filename]
        result = None
        text = ""
        try:
            text, result = omni.call(omniargs, options)
        except:
            self.logger.error("Failed to createsliver %s at %s", self.stitchSession.getSliceName(), self.aggrURL, exc_info=True)
            return False

        #result should be the req rspec we just sent. 
        if result is None or str(result).strip() == "":
            self.logger.error("No ~manifest~ returned by ION?! Got text %s", text)
            return False

        # - Need to poll with sliverstatus now and wait for 'ready'
        # - Once ready, use listresources <slivername> to get manifest
        ready = False
        result = ""
        for i in range(0,pollMaxAttempts):
            self.logger.info("Polling ION for sliver status...")

            omniargs = ["--api-version", "2", "-t", "SFA", "1", "-a",self.aggrURL,"-o","sliverstatus",self.stitchSession.getSliceName()] 
            try:
                text, result = omni.call(omniargs, options)
            except:
                self.logger.error("Failed to get sliverstatus on %s at %s", self.stitchSession.getSliceName(), self.aggrURL, exc_info=True)
                # Hope that this is transient? Or fail?
                break

            if isinstance(result,dict) and result.has_key(self.aggrURL) and isinstance(result[self.aggrURL],dict) and result[self.aggrURL].has_key('geni_status'):
                if result[self.aggrURL]['geni_status'] == 'configuring':
                    time.sleep(aggrPollIntervalSec)
                    continue
                elif result[self.aggrURL]['geni_status'] == 'failed':
                    self.logger.error("Slice creation failed")
                    break
                elif result[self.aggrURL]['geni_status'] == 'unknown':
                    self.logger.error("Slice in Unknown State")
                    break
                elif result[self.aggrURL]['geni_status'] == 'ready':
                    ready = True
                    break
                else:
                    self.logger.error("Slice at ION in Unknown State "+str(result[self.aggrURL]['geni_status']))
                    break
            else:
                self.logger.error("Return sliverstatus from ION Aggregate was invalid: \n"+str(result))
                break

        if not ready:
            return ready

        self.logger.info("Slice created successfully at ION, attempting to obtain manifest")

        omniargs = ["--api-version", "2", "-t", "SFA", "1", "-a",self.aggrURL,"-o","listresources",self.stitchSession.getSliceName()] 
        try:
            text, result = omni.call(omniargs, options)
        except:
            self.logger.error("Failed to listresources on %s at %s", self.stitchSession.getSliceName(), self.aggrURL, exc_info=True)
            return False

        if not (result != None and isinstance(result, dict) and len(result.keys()) == 1):
            self.logger.error("ION Manifest Result wasnt a dictionary with 1 entry? "+str(result))
            return False
        manspec_str = result.values()[0]

        try:
            self.manRSpec = ManRSpec(manspec_str,self,self.stitchSession, self.logger)
        except:
            import traceback
            traceback.print_exc()
            self.logger.error("The ION manifest recieved was not formatted correctly: "+str(manspec_str))
            self.logger.error(text)
            self.logger.error("Omni ran with args: "+str(omniargs))
            return False

        return ready


##Wrapper class for a PGV2 formatted Request RSpec
#
class PGV2ReqRSpec(ReqRSpec):
    rspecType = 'pgv2'
#    fakeManifestPath = '../samples/utah-manifest.xml'

    pathList = ()
    
    # path: 
    #  ID
    #  hop list (ordered)
    #    hop: id, type, nextHopID, nextHopObj, link
    #     link has
    #      ID
    #      switchingCapabilityDescriptor
    #        type
    #        encodingType
    #        switchCapabilitySpecifyInfo
    #          if type was l2sc:
    #            vlanRangeAvailability
    #            suggestedVLANRange

    ## The Constructor
    #
    #    @param rspecStr is the unprocessed XML string of an RSpec
    #    @param stitchSession is a dictionary of session information, global to
    #    all RSpec objects
    #    @param logger - The logging object to log output to
    # 
    def __init__(self, rspecStr, stitchSession, logger):
        super(PGV2ReqRSpec,self).__init__(rspecStr,stitchSession,logger)


    ## Interprets the associated RSpec document as an Protogeni V2 format RSpec.
    # Nothing much is done here, but it exists for completions sake 
    #
    #   @return True if success, False if failure
    #
    def fromRSpec(self):
        self.logger.info("Using PGV2 parser for this file for Agg "+self.aggrURL)
        # Note that unlike MAX/ION, there is not slicename/expiry to do

        # Fill in requestedInterfaces during calculateRestrictions

        # PGV2 Specific stuff here
        # For now, this is just sample code
        ns_prefix = "{"+self.stitchSession.getNamespaceFromType(self.rspecType)+"}"
        path_elems = self.rspecET.findall(ns_prefix+STCH_TAG+"/"+ns_prefix+PATH_TAG)
        hop_elems = self.rspecET.findall(ns_prefix+STCH_TAG+"/"+ns_prefix+PATH_TAG+"/"+ns_prefix+HOP_TAG)

        if len(path_elems)<1:
            # Switch to inner namespace
            ns_prefix = "{"+self.stitchSession.getExtNamespaceFromType(self.rspecType,"stitch")+"}" 
            path_elems = self.rspecET.findall(ns_prefix+STCH_TAG+"/"+ns_prefix+PATH_TAG)
            hop_elems = self.rspecET.findall(ns_prefix+STCH_TAG+"/"+ns_prefix+PATH_TAG+"/"+ns_prefix+HOP_TAG)

        for path in path_elems:
            path_id = util.strifyEle(path.get(ID_TAG))
            self.logger.debug("%s request specifies stitching path %s with %d hops", self.aggrURL, path_id, len(hop_elems))

        self.path_list = path_elems

        return True


    ## Calculate the restrictions on this Protogeni V2 RSpec/aggregate based on
    # the information in it's dom. This is the step before determining 
    # dependencies. Because so much of the topology information is stored in the
    # PGv2 RSpec, we actually use it to find restrictions on some of the other 
    # RSpecs/aggregates.
    # FIXME This function could be refactored to be cleaner and more readable
    #
    #     @return True if success, False if failure
    #   
    def calculateRestrictions(self):
        #print "pg"

        # In stitching element, go through each hop
        # Each hope has a link. If that link interface URN
        # is advertised by this AM, then extract vlan range/translation
        # restrictions, and fill them in to self.requestedInterfaces

        ns_prefix = "{"+self.stitchSession.getNamespaceFromType(self.rspecType)+"}"
        hop_elems = self.rspecET.findall(ns_prefix+STCH_TAG+"/"+ns_prefix+PATH_TAG+"/"+ns_prefix+HOP_TAG)

        if len(hop_elems)<1:
            ns_prefix = "{"+self.stitchSession.getExtNamespaceFromType(self.rspecType,"stitch")+"}" #Switch to inner namespace
            hop_elems = self.rspecET.findall(ns_prefix+STCH_TAG+"/"+ns_prefix+PATH_TAG+"/"+ns_prefix+HOP_TAG)
        

        if len(hop_elems)<1:
            self.logger.error("Problem parsing PG! I didn't find the nodes I was expecting. No hops in stitch/path/hop")
            return False

        # In stitching element, go through each hop
        # Each hope has a link. If that link interface URN
        # is advertised by this AM, then extract vlan range/translation
        # restrictions, and fill them in to self.requestedInterfaces
        for hop_elem in hop_elems:
            link_elem = hop_elem.find(ns_prefix+LINK_TAG)
            link_id = util.strifyEle(link_elem.get(ID_TAG))
            #self.logger.debug("PG Req stitch section hop/link %s", link_id)

            # If this is a local interface
            if self.stitchSession.aggrHasIface(self.aggrURL,link_id):
                # This is our interface from the ad,
                # Apparently we are requesting it
                remoteURN = self.stitchSession.getAggrURNRoute(self.aggrURL, link_id)
                #self.logger.debug("    Is advertised locally, with remote end %s", remoteURN)
                if not self.requestedInterfaces.has_key(link_id):
                    self.logger.debug("Adding PGV2 requested interface %s", link_id)
                    self.requestedInterfaces[link_id] = {}
                self.requestedInterfaces[link_id]['remoteIface']=remoteURN
                self.requestedInterfaces[link_id]['remoteAggrURL']=self.stitchSession.getAggrURNRemoteAggr(self.aggrURL, link_id)

                #######################################
                #Determine vlan range restrictions
                #######################################
                vlan_range_avail_elem = hop_elem.find(ns_prefix+LINK_TAG+"/"+ns_prefix+SWTCCAPADESC_TAG+"/"+ns_prefix+SWTCCAPASPEC_TAG+"/"+ns_prefix+SWTCCAPASPEC_L2SC_TAG+"/"+ns_prefix+VLANRANGAVAI_TAG)
                if vlan_range_avail_elem is None:
                    vlan_range_avail_elem = hop_elem.find(ns_prefix+LINK_TAG+"/"+ns_prefix+SWTCCAPADESC_TAG+"/"+ns_prefix+SWTCCAPASPEC_TAG+"/"+ns_prefix+VLANRANGAVAI_TAG)

                if vlan_range_avail_elem is not None:
                    self.setIfaceRestriction(link_id, 'vlanRange',util.vlanListIntersection(util.vlanRangeToList(util.strifyEle(vlan_range_avail_elem.text)),self.getIfaceRestriction(link_id, 'vlanRange')))
#                    self.logger.debug("Got vlanRangeAvail %s to set restriction to %s", vlan_range_avail_elem.text, self.getIfaceRestriction(link_id, 'vlanRange'))
                    self.logger.debug("Got vlanRangeAvail %s to set restriction", vlan_range_avail_elem.text)
                else:
                    # Couldn't find the vlan_range element - malformed
                    self.logger.error("No vlanRange element for link %s on hop %s in request to AM at %s", link_id, hop_elem.get(ID_TAG), self.aggrURL)

                #######################################
                #Determine vlan translation restrictions
                #######################################          
                vlan_trans_elem = hop_elem.find(ns_prefix+LINK_TAG+"/"+ns_prefix+SWTCCAPADESC_TAG+"/"+ns_prefix+SWTCCAPASPEC_TAG+"/"+ns_prefix+SWTCCAPASPEC_L2SC_TAG+"/"+ns_prefix+VLANTRAN_TAG)

                if vlan_trans_elem is None:
                    vlan_trans_elem = hop_elem.find(ns_prefix+LINK_TAG+"/"+ns_prefix+SWTCCAPADESC_TAG+"/"+ns_prefix+SWTCCAPASPEC_TAG+"/"+ns_prefix+VLANTRAN_TAG)
           
                if vlan_trans_elem is not None:
                    #self.logger.debug("Got vlan_trans_elem to set restriction")
                    if util.strifyEle(vlan_trans_elem.text).lower() == 'false':
                        self.setRestriction('vlanTranslation',True)
                        self.setIfaceRestriction(link_id, 'vlanTranslation',True) 
                    else:
                        self.setRestriction('vlanTranslation',False)
                        self.setIfaceRestriction(link_id, 'vlanTranslation',False) 
                else:
                    # couldn't find vlan_trans_elem - malformed
                    self.logger.error("No vlanTranslation element for link %s on hop %s in request to AM at %s", link_id, hop_elem.get(ID_TAG), self.aggrURL)

            else:
                # the interface that starts this link is not local
                #self.logger.debug("PG Req stitch section hop/link %s NOT LOCALly advertised", link_id)
                pass

            ''' #We no longer set other's restrictions based on what we see in our RSpec
            print "1: "+self.aggrURL
            if vlan_trans_elem is not None and vlan_trans_elem.text == 'false':
                print "2: "+link_id
                for aggr in self.stitchSession.getPresetRouteAggrURLList():
                    one = self.stitchSession.aggrHasIface(aggr,link_id)
                    two = self.stitchSession.isValidAggrURL(aggr)
                    print str(one)+" : "+str(two)

                    if self.stitchSession.aggrHasIface(aggr,link_id) and self.stitchSession.isValidAggrURL(aggr):
                        print "4"
                        self.stitchSession.getAggregate(aggr).setRestriction('vlanTranslation',True)
            '''

        # end of loop over all hops in the stitching element
                      
        return True


    ## Insert any relevant Vlan information into this RSpec
    # This function is not required at this time for PGV2, it is here for 
    # completions sake 
    #     
    #     @param vlan_map - A dictionary of interfaceUrn's -> Assigned Vlan Id's
    #     @return True if success, False if failure
    #     
    def insertVlanData(self, vlan_map):
        # An AM that does vlan translation but talks PGV2 would require this
        # We'd want to fill in the suggestedVLANRange and vlanRangeAvailability
        # fields I believe
        
        # for each key in vlan_map
        # for each hop, get link_id
        # If link_id==key
        # set vlanRangeAvailability to the value in the map
        # FIXME: Is it vlanRangeAvailability or suggestedVLANRange or both?

        return True #Nothing to do here yet


    ## Submit this RSpec to GENI aggregate 
    # This function calls 'createsliver' repeatedly until it gets an accept or
    # until maximum attempts is reached. After a successful sliver creation, it
    # stores the Manifest.
    # Then it
    # will continue to poll the aggregate with 'sliverstatus' until it get's a
    # favourable response indicating that the sliver is ready. 
    # Then it returns.
    #     
    #     @param tmp_filename - The name of the temporary in which the XML RSpec
    #     sits
    #     @param options - The omni options to use in the submission 
    #     @return True if success, False if failure
    #     
    def doRequest(self, tmp_filename, options):
        # FIXME: Use GetVersion to determin API # and RSpec type
        omniargs = ["--api-version", "2", "-t", "ProtoGENI", "2", "-a",self.aggrURL,"-o","createsliver",self.stitchSession.getSliceName(), tmp_filename] 
        result = None
        text = ""

        # PG is really slow at demo time
        for i in range(0,pollMaxAttempts*2):
            try:
                text, result = omni.call(omniargs, options)
                #self.logger.debug("omni createsliver to %s returned", self.aggrURL)
            except:
                self.logger.error("Failed to createsliver %s at %s", self.stitchSession.getSliceName(), self.aggrURL, exc_info=True)
                # Hope that this is transient? Or fail?
                return False

            # PG actually returns a manifest
            if result is None or str(result).strip() == "" or not "<rspec" in result:
                # Error

                if "try again later" in text:
                    # Happens when PG is busy or slice is new
                    time.sleep(aggrPollIntervalSec)
                    continue

                self.logger.error("No manifest returned by PG?! Got return string: "+text)
                return False
            else:
                # Got the manifest, break out of loop retrying createSliver
                break

        try:
            self.manRSpec = ManRSpec(result,self,self.stitchSession, self.logger)
        except:
            import traceback
            self.logger.error("The PG manifest received was not formatted correctly")
            # Could print the result string, the malformed manifest
            traceback.print_exc()
            #self.logger.error(text)
            #self.logger.error("Omni ran with args: "+str(omniargs))
            return False

        ready = False
        # PG is really slow at demo time
        for i in range(0,pollMaxAttempts*3):
            self.logger.info("Polling PG for sliver status...")

            omniargs = ["--api-version", "2", "-t", "ProtoGENI", "2", "-a",self.aggrURL,"-o","sliverstatus",self.stitchSession.getSliceName()] 
            try:
                text, result = omni.call(omniargs, options)
            except:
                self.logger.error("Failed to get sliverstatus on %s at %s", self.stitchSession.getSliceName(), self.aggrURL, exc_info=True)
                # Hope that this is transient? Or fail?
                break

            if isinstance(result,dict) and result.has_key(self.aggrURL) and isinstance(result[self.aggrURL],dict) and result[self.aggrURL].has_key('geni_status'):
                if result[self.aggrURL]['geni_status'] == 'configuring':
                    time.sleep(aggrPollIntervalSec)
                    continue
                elif result[self.aggrURL]['geni_status'] == 'failed':
                    self.logger.error("Slice creation failed")
                    break
                elif result[self.aggrURL]['geni_status'] == 'unknown':
                    # I think PG marks the state unknown while it is in process
                    self.logger.info("Slice in Unknown State")
                    time.sleep(aggrPollIntervalSec)
                    continue
                elif result[self.aggrURL]['geni_status'] == 'ready':
                    ready = True
                    break
                else:
                    self.logger.error("Slice at PG in Unknown State "+str(result[self.aggrURL]['geni_status']))
                    break
            else:
                if "try again" in text:
                    # PG says it is busy
                    time.sleep(aggrPollIntervalSec)
                    continue

                self.logger.error("Return sliverstatus from PG Aggregate was invalid: \n"+str(result))
                break

        return ready


##Wrapper class for a GENIV3 formatted Request RSpec
#
class GENIV3ReqRSpec(ReqRSpec):
    rspecType = 'geniv3'
#    fakeManifestPath = '../samples/utah-manifest.xml'

    pathList = ()

    # path:
    #  ID
    #  hop list (ordered)
    #    hop: id, type, nextHopID, nextHopObj, link
    #     link has
    #      ID
    #      switchingCapabilityDescriptor
    #        type
    #        encodingType
    #        switchCapabilitySpecifyInfo
    #          if type was l2sc:
    #            vlanRangeAvailability
    #            suggestedVLANRange

    ## The Constructor
    #
    #    @param rspecStr is the unprocessed XML string of an RSpec
    #    @param stitchSession is a dictionary of session information, global to
    #    all RSpec objects
    #    @param logger - The logging object to log output to
    #
    def __init__(self, rspecStr, stitchSession, logger):
        super(GENIV3ReqRSpec,self).__init__(rspecStr,stitchSession,logger)


    ## Interprets the associated RSpec document as an GENI V3 format RSpec.
    # Nothing much is done here, but it exists for completions sake
    #
    #   @return True if success, False if failure
    #
    def fromRSpec(self):
        self.logger.info("Using GENIV3 parser for this file for Agg "+self.aggrURL)
        # Note that unlike MAX/ION, there is not slicename/expiry to do

        # Fill in requestedInterfaces during calculateRestrictions

        # GENIV3 Specific stuff here
        # For now, this is just sample code
        ns_prefix = "{"+self.stitchSession.getNamespaceFromType(self.rspecType)+"}"
        path_elems = self.rspecET.findall(ns_prefix+STCH_TAG+"/"+ns_prefix+PATH_TAG)
        hop_elems = self.rspecET.findall(ns_prefix+STCH_TAG+"/"+ns_prefix+PATH_TAG+"/"+ns_prefix+HOP_TAG)

        if len(path_elems)<1:
            # Switch to inner namespace
            ns_prefix = "{"+self.stitchSession.getExtNamespaceFromType(self.rspecType,"stitch")+"}" 
            path_elems = self.rspecET.findall(ns_prefix+STCH_TAG+"/"+ns_prefix+PATH_TAG)
            hop_elems = self.rspecET.findall(ns_prefix+STCH_TAG+"/"+ns_prefix+PATH_TAG+"/"+ns_prefix+HOP_TAG)

        for path in path_elems:
            path_id = util.strifyEle(path.get(ID_TAG))
            self.logger.debug("%s request specifies stitching path %s with %d hops", self.aggrURL, path_id, len(hop_elems))

        self.path_list = path_elems

        return True


    ## Calculate the restrictions on this GENI V3 RSpec/aggregate based on
    # the information in it's dom. This is the step before determining
    # dependencies. Because so much of the topology information is stored in the
    # GENIv3 RSpec, we actually use it to find restrictions on some of the other 
    # RSpecs/aggregates.
    # FIXME This function could be refactored to be cleaner and more readable
    #
    #     @return True if success, False if failure
    #
    def calculateRestrictions(self):
        #print "geniv3"

        # In stitching element, go through each hop
        # Each hope has a link. If that link interface URN
        # is advertised by this AM, then extract vlan range/translation
        # restrictions, and fill them in to self.requestedInterfaces

        ns_prefix = "{"+self.stitchSession.getNamespaceFromType(self.rspecType)+"}"
        hop_elems = self.rspecET.findall(ns_prefix+STCH_TAG+"/"+ns_prefix+PATH_TAG+"/"+ns_prefix+HOP_TAG)

        if len(hop_elems)<1:
            ns_prefix = "{"+self.stitchSession.getExtNamespaceFromType(self.rspecType,"stitch")+"}" #Switch to inner namespace
            hop_elems = self.rspecET.findall(ns_prefix+STCH_TAG+"/"+ns_prefix+PATH_TAG+"/"+ns_prefix+HOP_TAG)


        if len(hop_elems)<1:
            self.logger.error("Problem parsing GENIv3! I didn't find the nodes I was expecting. No hops in stitch/path/hop")
            return False

        # In stitching element, go through each hop
        # Each hope has a link. If that link interface URN
        # is advertised by this AM, then extract vlan range/translation
        # restrictions, and fill them in to self.requestedInterfaces
        for hop_elem in hop_elems:
            link_elem = hop_elem.find(ns_prefix+LINK_TAG)
            link_id = util.strifyEle(link_elem.get(ID_TAG))
            #self.logger.debug("GENIv3 Req stitch section hop/link %s", link_id)

            # If this is a local interface
            if self.stitchSession.aggrHasIface(self.aggrURL,link_id):
                # This is our interface from the ad,
                # Apparently we are requesting it
                remoteURN = self.stitchSession.getAggrURNRoute(self.aggrURL, link_id)
                #self.logger.debug("    Is advertised locally, with remote end %s", remoteURN)
                if not self.requestedInterfaces.has_key(link_id):
                    self.logger.debug("Adding GENIV3 requested interface %s", link_id)
                    self.requestedInterfaces[link_id] = {}
                self.requestedInterfaces[link_id]['remoteIface']=remoteURN
                self.requestedInterfaces[link_id]['remoteAggrURL']=self.stitchSession.getAggrURNRemoteAggr(self.aggrURL, link_id)

                #######################################
                #Determine vlan range restrictions
                #######################################
                vlan_range_avail_elem = hop_elem.find(ns_prefix+LINK_TAG+"/"+ns_prefix+SWTCCAPADESC_TAG+"/"+ns_prefix+SWTCCAPASPEC_TAG+"/"+ns_prefix+SWTCCAPASPEC_L2SC_TAG+"/"+ns_prefix+VLANRANGAVAI_TAG)
                if vlan_range_avail_elem is None:
                    vlan_range_avail_elem = hop_elem.find(ns_prefix+LINK_TAG+"/"+ns_prefix+SWTCCAPADESC_TAG+"/"+ns_prefix+SWTCCAPASPEC_TAG+"/"+ns_prefix+VLANRANGAVAI_TAG)

                if vlan_range_avail_elem is not None:
                    self.setIfaceRestriction(link_id, 'vlanRange',util.vlanListIntersection(util.vlanRangeToList(util.strifyEle(vlan_range_avail_elem.text)),self.getIfaceRestriction(link_id, 'vlanRange')))
#                    self.logger.debug("Got vlanRangeAvail %s to set restriction to %s", vlan_range_avail_elem.text, self.getIfaceRestriction(link_id, 'vlanRange'))
                    self.logger.debug("Got vlanRangeAvail %s to set restriction", vlan_range_avail_elem.text)
                else:
                    # Couldn't find the vlan_range element - malformed
                    self.logger.error("No vlanRange element for link %s on hop %s in request to AM at %s", link_id, hop_elem.get(ID_TAG), self.aggrURL)

                #######################################
                #Determine vlan translation restrictions
                #######################################
                vlan_trans_elem = hop_elem.find(ns_prefix+LINK_TAG+"/"+ns_prefix+SWTCCAPADESC_TAG+"/"+ns_prefix+SWTCCAPASPEC_TAG+"/"+ns_prefix+SWTCCAPASPEC_L2SC_TAG+"/"+ns_prefix+VLANTRAN_TAG)

                if vlan_trans_elem is None:
                    vlan_trans_elem = hop_elem.find(ns_prefix+LINK_TAG+"/"+ns_prefix+SWTCCAPADESC_TAG+"/"+ns_prefix+SWTCCAPASPEC_TAG+"/"+ns_prefix+VLANTRAN_TAG)

                if vlan_trans_elem is not None:
                    #self.logger.debug("Got vlan_trans_elem to set restriction")
                    if util.strifyEle(vlan_trans_elem.text).lower() == 'false':
                        self.setRestriction('vlanTranslation',True)
                        self.setIfaceRestriction(link_id, 'vlanTranslation',True) 
                    else:
                        self.setRestriction('vlanTranslation',False)
                        self.setIfaceRestriction(link_id, 'vlanTranslation',False) 
                else:
                    # couldn't find vlan_trans_elem - malformed
                    self.logger.error("No vlanTranslation element for link %s on hop %s in request to AM at %s", link_id, hop_elem.get(ID_TAG), self.aggrURL)

            else:
                # the interface that starts this link is not local
                #self.logger.debug("GENIv3 Req stitch section hop/link %s NOT LOCALly advertised", link_id)
                pass

            ''' #We no longer set other's restrictions based on what we see in our RSpec
            print "1: "+self.aggrURL
            if vlan_trans_elem is not None and vlan_trans_elem.text == 'false':
                print "2: "+link_id
                for aggr in self.stitchSession.getPresetRouteAggrURLList():
                    one = self.stitchSession.aggrHasIface(aggr,link_id)
                    two = self.stitchSession.isValidAggrURL(aggr)
                    print str(one)+" : "+str(two)

                    if self.stitchSession.aggrHasIface(aggr,link_id) and self.stitchSession.isValidAggrURL(aggr):
                        print "4"
                        self.stitchSession.getAggregate(aggr).setRestriction('vlanTranslation',True)
            '''

        # end of loop over all hops in the stitching element

        return True


    ## Insert any relevant Vlan information into this RSpec
    # This function is not required at this time for GENIV3, it is here for
    # completions sake
    #
    #     @param vlan_map - A dictionary of interfaceUrn's -> Assigned Vlan Id's
    #     @return True if success, False if failure
    #
    def insertVlanData(self, vlan_map):
        # An AM that does vlan translation but talks PGV2 would require this
        # We'd want to fill in the suggestedVLANRange and vlanRangeAvailability
        # fields I believe

        # for each key in vlan_map
        # for each hop, get link_id
        # If link_id==key
        # set vlanRangeAvailability to the value in the map
        # FIXME: Is it vlanRangeAvailability or suggestedVLANRange or both?

        return True #Nothing to do here yet


    ## Submit this RSpec to GENI aggregate
    # This function calls 'createsliver' repeatedly until it gets an accept or
    # until maximum attempts is reached. After a successful sliver creation, it
    # stores the Manifest.
    # Then it
    # will continue to poll the aggregate with 'sliverstatus' until it get's a
    # favourable response indicating that the sliver is ready. 
    # Then it returns.
    #
    #     @param tmp_filename - The name of the temporary in which the XML RSpec
    #     sits
    #     @param options - The omni options to use in the submission 
    #     @return True if success, False if failure
    #
    def doRequest(self, tmp_filename, options):
        # FIXME: Use GetVersion to determin API # and RSpec type
        omniargs = ["--api-version", "2", "-t", "GENI", "3", "-a",self.aggrURL,"-o","createsliver",self.stitchSession.getSliceName(), tmp_filename] 
        result = None
        text = ""

        # PG is really slow at demo time
        for i in range(0,pollMaxAttempts*2):
            try:
                text, result = omni.call(omniargs, options)
                #self.logger.debug("omni createsliver to %s returned", self.aggrURL)
            except:
                self.logger.error("Failed to createsliver %s at %s", self.stitchSession.getSliceName(), self.aggrURL, exc_info=True)
                # Hope that this is transient? Or fail?
                return False

            # PG actually returns a manifest
            if result is None or str(result).strip() == "" or not "<rspec" in result:
                # Error

                if "try again later" in text:
                    # Happens when PG is busy or slice is new
                    time.sleep(aggrPollIntervalSec)
                    continue

                self.logger.error("No manifest returned by AM?! Got return string: "+text)
                return False
            else:
                # Got the manifest, break out of loop retrying createSliver
                break

        try:
            self.logger.debug("Got GENIv3 Manifest RSpec from %s for slice %s:\n%s", self.aggrURL, self.stitchSession.getSliceName(), result)
            self.manRSpec = ManRSpec(result,self,self.stitchSession, self.logger)
        except:
            import traceback
            self.logger.error("The GENIv3 format manifest received was not formatted correctly")
            # Could print the result string, the malformed manifest
            traceback.print_exc()
            #self.logger.error(text)
            #self.logger.error("Omni ran with args: "+str(omniargs))
            return False

        ready = False
        # PG is really slow at demo time
        for i in range(0,pollMaxAttempts*3):
            self.logger.info("Polling GENI AM for sliver status...")

            omniargs = ["--api-version", "2", "-t", "GENI", "3", "-a",self.aggrURL,"-o","sliverstatus",self.stitchSession.getSliceName()] 
            try:
                text, result = omni.call(omniargs, options)
            except:
                self.logger.error("Failed to get sliverstatus on %s at %s", self.stitchSession.getSliceName(), self.aggrURL, exc_info=True)
                # Hope that this is transient? Or fail?
                break

            if isinstance(result,dict) and result.has_key(self.aggrURL) and isinstance(result[self.aggrURL],dict) and result[self.aggrURL].has_key('geni_status'):
                if result[self.aggrURL]['geni_status'] == 'configuring':
                    time.sleep(aggrPollIntervalSec)
                    continue
                elif result[self.aggrURL]['geni_status'] == 'failed':
                    self.logger.error("Slice creation failed")
                    break
                elif result[self.aggrURL]['geni_status'] == 'unknown':
                    # I think PG marks the state unknown while it is in process
                    self.logger.info("Slice in Unknown State")
                    time.sleep(aggrPollIntervalSec)
                    continue
                elif result[self.aggrURL]['geni_status'] == 'ready':
                    ready = True
                    break
                else:
                    self.logger.error("Slice at GENI AM in Unknown State "+str(result[self.aggrURL]['geni_status']))
                    break
            else:
                if "try again" in text:
                    # GENI am says it is busy
                    time.sleep(aggrPollIntervalSec)
                    continue

                self.logger.error("Return sliverstatus from PG Aggregate was invalid: \n"+str(result))
                break

        return ready


##Wrapper class for a Manifest RSpec
#
class ManRSpec(object):

    ## Overridden obj creation function. Suppports dynamic subclassing
    #
    #   @param cls - See __new__ definition in python documentation
    #   @param rspecStr - The rspec XML string
    #   @param reqRSpec is a reference to the corresponding Request RSpec object
    #   @param stitchSession - a query-able object, global to all RSpec objects
    #   @param logger - The logging object to log output to
    #   @param *arguments - See __new__ definition in python documentation
    #   @param **keyword - See __new__ definition in python documentation
    #
    def __new__(cls, rspecStr, reqRSpec, stitchSession, logger, *arguments, **keyword):
        for subclass in ManRSpec.__subclasses__(): 
            if reqRSpec.rspecType == subclass.rspecType:
                #Use the correct subclass
                return super(cls, subclass).__new__(subclass, *arguments, **keyword) 
        for subclass2 in subclass.__subclasses__(): 
            if reqRSpec.rspecType == subclass2.rspecType:
                #Use the correct subclass
                return super(cls, subclass2).__new__(subclass2, *arguments, **keyword) 

        raise Exception, 'Unsupported RSpec format %s!' % reqRSpec.rspecType


    ## The Constructor
    # 
    #    @param rspecStr - the unprocessed XML string of an RSpec
    #    @param reqRSpec - a reference to the corresponding Request RSpec 
    #           object
    #    @param stitchSession - a query-able object, global to all RSpec objects
    #    @param logger - The logging object to log output to
    # 
    def __init__(self, rspecStr, reqRSpec, stitchSession, logger):
        self.logger = logger
        ## @var self.rspecStr - A copy of the original ReqRSpec string
        self.rspecStr = rspecStr
        ## @var self.rspecType - Signifies the type of the rspec 'pgv2', 'max'
        self.rspecType = reqRSpec.rspecType
        ## @var self.definedVlans - A map of iface urns to assigned vlans. 
        # Used to make finding assignments easier for dependents
        # key is remote interface URN, value is VLAN ID
        self.definedVlans = {}
        ## @var self.reqRSpec - the corresponding ReqRSpec object
        self.reqRSpec = reqRSpec
        ## @var self.nodes - reserved hosts at this AM
        self.nodes = []
        ## @var self.rspecET - The ElementTree DOM for the XML string
        self.rspecET = ElementTree.fromstring(self.rspecStr)
        ## @var self.stitchSession - A reference to the global stitch session 
        self.stitchSession = stitchSession

        # Parse key data items from the RSpec
        self.fromRSpec()


    ## Getter for the local nodes (hosts) list
    #
    #   @return The list of local nodes (hosts reserved at this AM)
    #
    def getNodes(self):
        return self.nodes


    ## Getter for the dictionary of vlans which were assigned to local 
    # interfaces. Keys are the remote interface URN, value is VLAN ID
    #
    #   @return The dictionary of iface->vlans which were assigned by this 
    #   aggregate 
    #
    def getDefinedVlans(self):
        return self.definedVlans


##Wrapper class for a MAX Manifest RSpec
#
class MaxManRSpec(ManRSpec):
    rspecType = 'max'

    ## Interprets the associated RSpec document as a Max-native format RSpec.
    # Scrape and fill in a few class variables based on the document contents. 
    # The most important thing is any Vlans that were assigned to interfaces 
    # by the aggregate. We put these in self.definedVlans for easy access by 
    # other objects.
    #     
    #   @return True if success, False if failure
    #
    def fromRSpec(self):
        ns_prefix = ""
        comp_resc_elems = self.rspecET.findall(ns_prefix+NETW_TAG+"/"+ns_prefix+COMPRSRC_TAG)

        if len(comp_resc_elems)<1:
            self.logger.error("Problem parsing MAX manifest! I didn't find the nodes I was expecting. Found no compute resources in network section.")
            return False

        for comp_resc_elem in comp_resc_elems:
            #self.logger.debug("MAX man has comRsrc %s", util.strifyEle(comp_resc_elem.get(ID_TAG)))
            iface_elems = comp_resc_elem.findall(ns_prefix+STCHRSRC_TAG+"/"+ns_prefix+NETIFACE_TAG)
            if len(iface_elems)<1:
                self.logger.error("Problem parsing MAX manifest! I didn't find the nodes I was expecting. Found no net intfcs within stitch resource")
                return False

            for iface_elem in iface_elems:
                #self.logger.debug("Which has stitching/netIface %s", util.strifyEle(iface_elem.get(ID_TAG)))
                vlan_range_elem = iface_elem.find(ns_prefix+VLANRANG_TAG)
                if vlan_range_elem is None or len(util.strifyEle(vlan_range_elem.text))<1:
                    self.logger.warn("Found no vlan range in this netinterface %s in the stitch resource in MAX manifest", str(iface_elem))
                    continue

                iface_vlan = util.strifyEle(vlan_range_elem.text)
                #self.logger.debug("MAX man found vlan_range elem %s", iface_vlan)
               
                attached_link_urn_elem = iface_elem.find(ns_prefix+ATACHLINKURN_TAG)
                if attached_link_urn_elem is None or len(util.strifyEle(attached_link_urn_elem.text))<1:
                    self.logger.warn('Found no attached link urn on this net intfc %s in the stitch resource in MAX manifest', str(iface_elem))
                    continue

                iface_urn = util.strifyEle(attached_link_urn_elem.text)
                #self.logger.debug("MAX man had attached_link URN %s", iface_urn)

                try:
                    # Get routes this aggr advertises
                    routes = self.stitchSession.getPresetRouteDictForAggrURL(self.reqRSpec.aggrURL)
                except UnknownAggrURLException as e:
                    self.logger.error("Supplied aggregate %s is unknown (no presetRouteDict)", self.reqRSpec.aggrURL)
                    return False

                new_uri = None
                if routes.has_key(iface_urn):
                    # Get remote interface URN for Advertised route that starts from this interface
                    new_uri = routes[iface_urn]
                if new_uri is None or new_uri == '':
                    self.logger.warn("URI from presetRoutes for iface_urn "+str(iface_urn)+" was empty / not defined (couldnt find remote interface)")
                if new_uri is not None and new_uri != "None":
                    # Local vlan to new_uri has given #
                    self.definedVlans[new_uri] = iface_vlan
                    self.logger.info(" ---> Link from " + iface_urn + " to "+new_uri+" was assigned Vlan #"+iface_vlan)


        if len(self.definedVlans)<1:
            self.logger.warn('Had a netIntfc in a stitch but couldnt get the vlan')
            return False

        return True


    ## Collects node information from this Max RSpec dom
    # Scrape the dom and set self.nodes as a list of nodes and their information
    #     
    #   @return a list of Nodes and their metadata found in this manifest 
    #
    def collectInfo(self):
        self.nodes = []
        ns_prefix = "{"+self.stitchSession.getNamespaceFromType(self.rspecType)+"}"

        user_name = self.stitchSession.getSiteNamePrefix() + self.stitchSession.getSliceName()

        #Pull this info from the Request because it is more complete 
        plab_node_elems = self.reqRSpec.rspecET.findall(ns_prefix+RSPEC_TAG+"/"+ns_prefix+COMPRSRC_TAG+"/"+ns_prefix+PLABNODE_TAG)

        # for each plab style node we reserved
        for plab_node_elem in plab_node_elems:
            node_name = "unknown"
            ip = "unknown"

            # Get the node_name
            node_urn = util.strifyEle(plab_node_elem.get(ID_TAG))
            #self.logger.debug("Got node %s", node_urn)
            result = re.match(maxNodeNameRegex,node_urn)
            if result and result.group and result.groups>3: 
               domain_name = result.group(2)
               node_name = result.group(4)
               node_name += "." + domain_name
               #self.logger.debug("Pattern matched. group1: %s, group2 %s, group3 %s, group4 %s", result.group(1), result.group(2), result.group(3), result.group(4))
            else:
                self.logger.warn("Pattern did not match. %d groups", len(result.group))

# This pulls the external address
#            address_elem = plab_node_elem.find(ns_prefix+ADDR_TAG)
#            if address_elem is not None and len(util.strifyEle(address_elem.text))>0: 
#                self.logger.debug("Found external address %s", util.strifyEle(address_elem.text))
#            else:
#                self.logger.debug("Didn't find external address element")

            # Get the IP
            ipaddr_elem = plab_node_elem.find(ns_prefix+NETIFACE_TAG+"/"+ns_prefix+IPADDR_TAG)
            if ipaddr_elem is not None and len(util.strifyEle(ipaddr_elem.text))>0:
                #self.logger.debug("Found internal ip elem %s", util.strifyEle(ipaddr_elem.text))
                ip = re.sub(ipAddrExcludeSub,"\\1",util.strifyEle(ipaddr_elem.text))
                #self.logger.debug("Found internal ip %s", ip)
            else:
                self.logger.warn("No ipaddr_elem")

            # Record this node/host
            self.logger.debug("Adding node %s from AM %s", node_name, self.reqRSpec.aggrURL)
            self.nodes.append({'hostname':node_name,'int_ip':ip,'username':user_name})  

        return self.nodes


##Wrapper class for a ION Manifest RSpec
#
class IonManRSpec(ManRSpec):
    rspecType = 'ion'

    ## Interprets the associated RSpec document as a Ion-native format RSpec
    # Scrape and fill in a few class variables based on the document contents. 
    # The most important thing is any Vlan's that were assigned to interfaces by
    # the aggregate. We put these in self.definedVlans for easy access by other 
    # objects.
    #     
    #   @return True if success, False if failure
    #
    def fromRSpec(self):
        ns_prefix = ""
        comp_resc_elems = self.rspecET.findall(ns_prefix+NETW_TAG+"/"+ns_prefix+COMPRSRC_TAG)

        if len(comp_resc_elems)<1:
            self.logger.error("Problem parsing ION! I didn't find the nodes I was expecting. No comp resource in network section.")
            return False

        for comp_resc_elem in comp_resc_elems:
            #self.logger.debug("ION man has comRsrc %s", util.strifyEle(comp_resc_elem.get(ID_TAG)))           
            iface_elems = comp_resc_elem.findall(ns_prefix+STCHRSRC_TAG+"/"+ns_prefix+NETIFACE_TAG)
            if len(iface_elems) < 1:
                self.logger.error("Problem parsing ION manifest! I didn't find the nodes I was expecting. No interface elements in comp resc elem in stitch resource")
                return False

            for iface_elem in iface_elems:
                #self.logger.debug("Which has stitching/netIface %s", util.strifyEle(iface_elem.get(ID_TAG)))

                vlan_range_elem = iface_elem.find(ns_prefix+VLANRANG_TAG)
                if vlan_range_elem is None or len(util.strifyEle(vlan_range_elem.text))<1:
                    self.logger.warn("Found no vlan range in this netinterface %s in the stitch resource in ION manifest", str(iface_elem))
                    continue

                iface_vlan = util.strifyEle(vlan_range_elem.text)
                #self.logger.debug("ION man found vlan_range elem %s", iface_vlan)
           
                attached_link_urn_elem = iface_elem.find(ns_prefix+ATACHLINKURN_TAG)
                if attached_link_urn_elem is None or len(util.strifyEle(attached_link_urn_elem.text))<1:
                    self.logger.warn('Found no attached link urn on this net intfc %s in the stitch resource in ION manifest', str(iface_elem))
                    continue

                iface_urn = util.strifyEle(attached_link_urn_elem.text)
                #self.logger.debug("ION man had attached_link URN %s", iface_urn)

                # For ION, definedVlans has this local URN mapped to the VLAN
                # Direction could have gone either way for ION I guess
                self.definedVlans[iface_urn] = iface_vlan

                # MAX does this:
                try:
                    # Get routes this aggr advertises
                    routes = self.stitchSession.getPresetRouteDictForAggrURL(self.reqRSpec.aggrURL)
                except UnknownAggrURLException as e:
                    self.logger.error("Supplied aggregate %s is unknown (no presetRouteDict)", self.reqRSpec.aggrURL)
                    return False

                new_uri = None
                if routes.has_key(iface_urn):
                    # Get remote interface URN for Advertised route that starts from this interface
                    new_uri = routes[iface_urn]
                if new_uri is None or new_uri == '':
                    self.logger.warn("URI from presetRoutes for iface_urn "+str(iface_urn)+" was empty / not defined (couldnt find remote interface)")
                if new_uri is not None and new_uri != "None":
                    # Local vlan to new_uri has given #
#                    self.definedVlans[new_uri] = iface_vlan
                    self.logger.info(" ---> Link from " + iface_urn + " to "+new_uri+" was configured with Vlan #"+iface_vlan)


        if len(self.definedVlans)<1:
            self.logger.warn('Had a netIntfc in a stitch but couldnt get the vlan')
            return False

        return True


    ## Collects node information from this Ion RSpec DOM.
    # Scrape the DOM and set self.nodes as a list of nodes (hosts) and their 
    # information. This function has no implementation at the moment, it is here
    # for completion's sake. (ION gives no hosts.)
    #     
    #   @return a list of Nodes and their metadata found in this manifest 
    #  
    #   Note: Not implemented for this RSpec type
    #  
    def collectInfo(self):
        return []


##Wrapper class for a PGV2 Manifest RSpec
#
class PGV2ManRSpec(ManRSpec):
    rspecType = 'pgv2'

    ## Interprets the associated RSpec document as a PGV2 format RSpec.
    # Scrape and fill in a few class variables based on the document contents. 
    # The most important thing is any Vlans that were assigned to interfaces by
    # the aggregate. We put these in self.definedVlans for easy access by other 
    # objects.
    #     
    #   @return True if success, False if failure
    #
    def fromRSpec(self):
        ns_prefix = "{"+self.stitchSession.getNamespaceFromType(self.rspecType)+"}"
 
        stitch_elem = self.rspecET.find(ns_prefix+STCH_TAG)
        if stitch_elem is None:
            ns_prefix = "{"+self.stitchSession.getExtNamespaceFromType(self.rspecType,"stitch")+"}" #Switch to inner namespace
            stitch_elem = self.rspecET.find(ns_prefix+STCH_TAG)
            if stitch_elem is None:
                self.logger.error("Problem parsing PG/GENI Manifest! Didn't find stitch element: "+str(ns_prefix)+str(STCH_TAG))
                return False

        path_elem = stitch_elem.find(ns_prefix+PATH_TAG)
        if path_elem is None:
            self.logger.error("Problem parsing PG/GENI Manifest! Within Stitch tag "+str(ns_prefix)+str(STCH_TAG)+" didn't find path tag "+str(ns_prefix)+str(PATH_TAG))
            return False

        hop_elems = path_elem.findall(ns_prefix+HOP_TAG)

        if len(hop_elems)<1:
            self.logger.error("Problem parsing PG/GENI Manifest! I didn't find the nodes I was expecting. No hops ("+str(ns_prefix)+str(HOP_TAG)+") within "+str(ns_prefix)+str(STCH_TAG)+"/"+str(ns_prefix)+str(PATH_TAG))
            return False

        for hop_elem in hop_elems:
            link_elem = hop_elem.find(ns_prefix+LINK_TAG)
            link_id = util.strifyEle(link_elem.get(ID_TAG))

            vlan_avail_elem = link_elem.find(ns_prefix+SWTCCAPADESC_TAG+"/"+ns_prefix+SWTCCAPASPEC_TAG+"/"+ns_prefix+SWTCCAPASPEC_L2SC_TAG+"/"+ns_prefix+VLANRANGAVAI_TAG)
            if vlan_avail_elem is None: 
                vlan_avail_elem = link_elem.find(ns_prefix+SWTCCAPADESC_TAG+"/"+ns_prefix+SWTCCAPASPEC_TAG+"/"+ns_prefix+VLANRANGAVAI_TAG)

            # IF we found a vlan_avail_elem and this link is a route that this aggregate has,
            # then we'll store the VLAN ID as a definedVlan on this aggregate
            if vlan_avail_elem is not None and self.stitchSession.aggrHasRouteURN(self.reqRSpec.aggrURL,link_id):
                vlan_id = util.strifyEle(vlan_avail_elem.text)

                # Get the remote interface URN for the link with give ID/local interface URN,
                # from the Ad RSpecs
                new_uri = str(self.stitchSession.getAggrURNRoute(self.reqRSpec.aggrURL,link_id))
                # local VLAN with given ID to the given remote interface URN
                self.definedVlans[str(new_uri)]=str(vlan_id)
                if new_uri is not None and link_id is not None and new_uri != "None":
                    self.logger.info(" ---> Link from "+link_id+" to "+new_uri+" was assigned Vlan #"+vlan_id)
                else:
                    # Got no remote interface URN for link_id?
                    self.logger.warn("Couldnt get remote interface URN for local %s which got VLAN tag %s on AM %s", link_id, vlan_id, self.reqRSpec.aggrURL)
                    pass
            else:
                # got no vlan_avail elem or have no remote interface URN for link_ID?
                if vlan_avail_elem is None:
                    self.logger.warn("Got no vlan_avail elem in this link %s, from AM %s", link_id, self.reqRSpec.aggrURL)
                else:
                    # no remote interface URN - not an advertised link
                    # this is normal
                    pass
        # end of loop over hops

        if len(self.definedVlans)<1:
            # No VLANs assigned
            # Is this really bad? Theoretically we could reserve from PG
            # and not need any VLANs
            self.logger.warn("No VLAN assignments found in %d stitching hops for AM %s", len(hop_elems), self.reqRSpec.aggrURL)
            return False

        return True


    ## Collects node/host information from this PGV2 RSpec DOM.
    # Scrape the DOM and set self.nodes as a list of nodes and their information
    #     
    #   @return a list of Nodes and their metadata found in this manifest 
    #
    def collectInfo(self):
        ns_prefix = "{"+self.stitchSession.getNamespaceFromType(self.rspecType)+"}"
        node_elems = self.rspecET.findall(ns_prefix+NODE_TAG)
        # FIXME: we seem to call collectInfo 2x? Should only call 1x.
        # If we do we could try hard to avoid duplicating nodes,
        # like check if the nodes list has a node with that hostname
        if len(self.nodes) > 0:
            self.logger.debug("For AM %s clearing nodes list of %d nodes to refill", self.reqRSpec.aggrURL, len(self.nodes))
        self.nodes = []

        for node_elem in node_elems:
            client_id = util.strifyEle(node_elem.get("client_id"))
            component_id = util.strifyEle(node_elem.get("component_id"))
            component_manager_id = util.strifyEle(node_elem.get("component_manager_id"))
            #self.logger.debug("Client_id: %s, component_id: %s, comp_mgr_id: %s", client_id, component_id, component_manager_id)

            # Skip nodes not managed by the AM we contacted.
            # IE the RSpec from/to PG often lists all nodes, including those
            # not managed by this Node. So it won't have a hostname/ip
            # and should be added by that other AM
            # Here we extract the authority part of various URNs, comparing
            # components we requested from this AM with the authority of the component_manager_id
            # on this Node. Only if they are the same do we treat this as a locally
            # managed node and add it
            mine = True
            idnIx = component_manager_id.find('IDN+')
            cmAuth = component_manager_id[idnIx+len('IDN+'):component_manager_id[idnIx+len('IDN+'):].find('+')+idnIx+len('IDN+')]
            self.logger.debug("This node %s has is managed by an AM with authority %s", component_id, cmAuth)

            reqIfc1 = ""
            reqIfc2 = ""
            rIs = self.reqRSpec.requestedInterfaces.keys()
            if len(rIs) > 0:
                reqIfc1 = rIs[0]
            if len(rIs) > 1:
                reqIfc2 = rIs[1]

            if len(reqIfc1) > 0:
                idnIx = reqIfc1.find('IDN+')
                ri1Auth = reqIfc1[idnIx+len('IDN+'):reqIfc1[idnIx+len('IDN+'):].find('+')+idnIx+len('IDN+')]
                self.logger.debug("This AM requested interface %s with authority %s", reqIfc1, ri1Auth)
                if ri1Auth == cmAuth:
                    self.logger.debug("... which is same as this node's authority - local Node to add.")
                else:
                    self.logger.debug("... which is different than this node's authority. Skip it.")
                    mine = False

            # Do a 2nd requested interface (if any) to check for problems
            if len(reqIfc2) > 0:
                idnIx = reqIfc2.find('IDN+')
                ri2Auth = reqIfc2[idnIx+len('IDN+'):reqIfc2[idnIx+len('IDN+'):].find('+')+idnIx+len('IDN+')]
                self.logger.debug("This AM requested interface %s with authority %s", reqIfc2, ri2Auth)
                if ri2Auth == cmAuth:
                    self.logger.debug("... which is same as this node's authority - local node to add.")
                    if not mine:
                        self.logger.debug("... which disagrees with the first requested interface we checked!")
                else:
                    self.logger.debug("... which is different than this node's authority")
                    if mine:
                        self.logger.debug("... which disagrees with the first requested interface we checked!!")
            if not mine:
                continue

            hostname = "unknown"
            int_ip = "unknown"
            ip_elem = node_elem.find(ns_prefix+INTRFACE_TAG+"/"+ns_prefix+IP_TAG)

            if ip_elem is not None and ip_elem.get(ADDR_TAG):
                int_ip = util.strifyEle(ip_elem.get(ADDR_TAG))
                #FIXME Eventually want to use a regex to validate the IP
                #self.logger.debug("Found internal ip %s", int_ip)
            login_elem = node_elem.find(ns_prefix+SERVS_TAG+"/"+ns_prefix+LOGIN_TAG)
            if login_elem is not None and login_elem.get(HOSTNAME_TAG):
                hostname = util.strifyEle(login_elem.get(HOSTNAME_TAG))
            if login_elem is not None and login_elem.get('username'):
                username = util.strifyEle(login_elem.get('username'))
                if username != self.stitchSession.getUserName():
                    self.logger.warning("Manifest says username is %s, but stitchSession infers %s", username, self.stitchSession.getUserName())
            self.logger.debug("Adding node %s from AM %s", hostname, self.reqRSpec.aggrURL)
            self.nodes.append({'hostname':hostname,'int_ip':int_ip,'username':self.stitchSession.getUserName(),'client_id':client_id,'component_id':component_id}) 

        return self.nodes


##Wrapper class for a GENIV3 Manifest RSpec
#
class GENIV3ManRSpec(PGV2ManRSpec):
    rspecType = 'geniv3'

## Wrapper for a set of aggregate/hop restrictions
#
#
class Restrictions(object):
    
    ## The Constructor
    # 
    def __init__(self):
        self.restrictions = {
            'vlanRange':['*'], 
            'vlanTranslation':False #Reverse of what you think. False means this
            #is NOT a restriction ie. It supports vlan translation
        }


    ## Basically just a filter for the restrictions dictionary
    #     
    #    @param rest The string name of the restriction
    # 
    def getRestriction(self, rest):
        try:
            return self.restrictions[rest] 
        except:
            return None


    ## Basically just a filter for the restrictions dictionary
    #     
    #    @param rest The string name of the restriction
    #    @param val The desired value to be assigned
    #     
    def setRestriction(self, rest, val):
        self.restrictions[rest] = val
