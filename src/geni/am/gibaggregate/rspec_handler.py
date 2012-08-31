
import sys
from xml.dom.minidom import *
import datetime

import config
from resources import VMNode, NIC, Link, installItem, executeItem

def parseRequestRspec(rspec, experimentHosts, experimentLinks, \
                          experimentNICs) :
    """ This function parses a request Rspec and creates an in-memory 
        representation of the experimenter specified topology using 
        VMNode, NIC and Link objects.
    """
    # Parse the xml rspec
    rspec_dom = parseString(rspec)

    # Look for DOM objects tagged 'node'.  These are hosts requested by the 
    #    experimenter
    hostList = rspec_dom.getElementsByTagName('node')

    # For each host, extract experimenter specified information from DOM node
    hostCount = 0;      # Keep track of the number of hosts allocated
    for host in hostList : 
        hostCount += 1
        if hostCount >  VMNode.numVMs :
           print 'parseRequestRspec: Experimenter requested more nodes than we have'
           return None;   # failed to parse rspec

        # Create a VMNode object for this host and add it to our collection
        #    of hosts allocated to the experiment
        hostObject = VMNode(hostCount)
        experimentHosts[hostObject.containerName] = hostObject

        # Get information about the host from the rspec
        hostAttributes = host.attributes   # DOM attributes object 
                                           #    associated with the host
        if hostAttributes.has_key('client_id') :
            hostObject.nodeName = hostAttributes['client_id'].value

        # Get interfaces associated with the host
        netInterfaceList = host.getElementsByTagName('interface')
        interfaceCount = 0;   # Track num of interfaces requested for this node
        for netInterface in netInterfaceList :
            interfaceCount += 1
            if interfaceCount > 3 :
                print 'parseRequestRspec: Exceeded number of interfaces available on node'
                return None;    # failed to parse rspec
            
            # Create a NIC object for this interface and add it to the list 
            #    of NICs associated with this hostObject
            nicObject = NIC()
            hostObject.NICs = hostObject.NICs + [nicObject]
            nicObject.myHost = hostObject

            # Get information about the interface from the rspec
            nicAttributes = netInterface.attributes 
            if not nicAttributes.has_key('client_id') :
                print 'parseRequestRspec: Network interface does not have a name'
                return None

            nicObject.nicName = nicAttributes['client_id'].value
            experimentNICs[nicObject.nicName] = nicObject    # Add to 
                                  # collection of NICs used by this experiment

        # Get information on services to be performed on the host before
        #    it is ready for the experimenter.  
        servicesList = host.getElementsByTagName('services')
        for serviceElement in servicesList :
            installElements = serviceElement.getElementsByTagName('install')
            for item in installElements :
                installAttributes = item.attributes
                if not (installAttributes.has_key('url') and 
                        installAttributes.has_key('install_path')) :
                    print 'parseRequestRspec: Source URL or destination path missing for install element in request rspec'
                    return None
                
                instItem = installItem()
                instItem.sourceURL = installAttributes['url'].value
                instItem.destination = installAttributes['install_path'].value
                if installAttributes.has_key('file_type') :
                    instItem.fileType = installAttributes['file_type'].value
                hostObject.installList = hostObject.installList + [instItem]
                
        for serviceElement in servicesList :
            executeElements = serviceElement.getElementsByTagName('execute')
            for item in executeElements :
                executeAttributes = item.attributes
                if not executeAttributes.has_key('command') :
                    print 'parseRequestRspec: Command missing for execute element in request rspec'
                    return None
                
                execItem = executeItem()
                execItem.command = executeAttributes['command'].value
                if executeAttributes.has_key('shell') :
                    execItem.shell = executeAttributes['shell'].value
                hostObject.executeList = hostObject.executeList + [execItem]
                
    # Done getting information on hosts (nodes) requsted by experimenter.
    # Now get information about links.
    linksList = rspec_dom.getElementsByTagName('link')
    for link in linksList :
        linkObject = Link()    # Create a Link object for this link

        # Get attributes about this link from the rspec
        linkAttributes = link.attributes    # DOM attributes object 
                                            #    associated with link
        if not linkAttributes.has_key('client_id') :
            print 'parseRequestRspec: Link does not have a name'
            return None;
        linkObject.linkName = linkAttributes['client_id'].value
        experimentLinks.append(linkObject) # Add to collection of links 
                                           #    used by this experiment
        
        # Get the two end-points for this link.  
        endPoints = link.getElementsByTagName('interface_ref');
        for i in range(0, 2) :
            endPointAttributes = endPoints[i].attributes  # DOM attributes
                                           # object associated with end point
            interfaceName = endPointAttributes['client_id'].value  # Name of
                                    # the NIC that forms one end of this link
            
            # Find the NIC Object that corresponds to this interface name
            nicObject = experimentNICs[interfaceName]

            # Set the NIC Object to point to this link object
            nicObject.link = linkObject

            # Add this NIC Object to the list of end points for the link
            linkObject.endPoints = linkObject.endPoints + [nicObject]
            
    return   # What should we return on success?




"""\
Class for creating manifest files from a parsed request rspec.
"""
class GeniManifest :
    
    """\
    Static members of GeniManifest.
    
    These are used to specify various things about the manifest when it is
    created, typically the element tags, but also includes some hard coded
    element values such as the webpage
    """
    headerTag           = "rspec"                   # outer level node for the manifest file
    typeTag             = "type"                    # the type of manifest this was, only available is request
    xmlnsTag            = "xmlns"                   # tag used for the protogeni website
    expiresTag          = "expires"                 # the rpsec block specifying how long the manifest is good for
    nodeTag             = "node"                    # the tag for a node, or host element
    exclusiveTag        = "exclusive"               # tag for specifying exclusivity of a host
    interfaceRefTag     = "interface_ref"           # tag for creating an interface element for a link
    interfaceTag        = "interface"               # tag for creating interfaces for a host
    componentIdTag      = "component_id"            # component id for an interface that belongs to a host
    clientIdTag         = "client_id"               # the id element for hosts
    linkTag             = "link"                    # tag for links added to the manifest
    macTag              = "mac_address"             # tag for mac addresses on interfaces
    ipAddressTag        = "ip_address"              # the ip address for an interface reference
    ipTag               = "ip"                      # used for creating an ip element for a node
    addressTag          = "address"                 # used for creating an address for an ip for a node
    componentManagerTag = "component_manager"       # tag used for a component manager sub-element
    sliverTypeTag       = "sliver_type"             # tag used for defining a sliver type on a host
    diskImageTag        = "disk_image"              # tag used for defining the type of image on a host
    webpage             = "http://www.protogeni.net/resources/rspec/0.1"
    
    knownLinkSubElements = ["component_manager", "property", "interface_ref"]
    knownHostSubElements = ["services", "sliver_type"]
    

    
    """\
    Initializes a new instance of GeniManifest.
    
    This constructor expects the request rspec has already
    been parsed and the structure is already set up.
    """
    def __init__(self, rspec, experimentHosts, experimentLinks, experimentNICs) :
        self.rspec = rspec
        self.hosts = experimentHosts
        self.links = experimentLinks
        self.NICs = experimentNICs
        self.validUntil = datetime.datetime.today() + datetime.timedelta(days = 365)
    
    
    """\
    Creates a manifest rspec file to the given file name.
    """
    def create(self) :
        
        originalRspec = parseString(self.rspec)
        
        # create the document and the main header/wrapper portion
        manifest = Document()
        header = manifest.createElement(GeniManifest.headerTag)
        header.setAttribute(GeniManifest.typeTag, "manifest")
        header.setAttribute(GeniManifest.expiresTag, "{0}".format(self.validUntil))
        manifest.appendChild(header)
        
        # get the original link and host elements from the rspec
        # so misc information can be copied over to the manifest
        originalLinks = originalRspec.getElementsByTagName("link")
        originalHosts = originalRspec.getElementsByTagName("node")
        
        # go through and add all the interface links to the manifest,
        # these become the connections the allocated computers possess
        for i in xrange(0, len(self.links)) :
            
            # find the link in the original rspec that belongs to the current node being looked at,
            # then copy all the known information to the manifest, this must be done since the
            # 'currentLink' element cannot be added to the manifest directly
            currentLink = originalLinks[0]
            for nextLink in originalLinks :
                if nextLink.hasAttribute(GeniManifest.clientIdTag) and nextLink.attributes[GeniManifest.clientIdTag].value == self.links[i].linkName :
                    currentLink = nextLink
                    break
            
            link = manifest.createElement(GeniManifest.linkTag)
            link.setAttribute(GeniManifest.clientIdTag, self.links[i].linkName)
            
            # add each sub-element of the link that should be copied over to the manifest
            for currentSubElement in GeniManifest.knownLinkSubElements :
                subElements = currentLink.getElementsByTagName(currentSubElement)
                for subElement in subElements :
                    
                    # if the current sub element is a component manager
                    # then set it to be something special for geni-in-a-box
                    if subElement.nodeName == GeniManifest.componentManagerTag :
                        subElement.setAttribute("name", "urn:publicid:geni-in-a-box+authority+cm")
                    
                    # if the current sub element is an interface
                    # reference the component id needs to be set
                    elif subElement.nodeName == GeniManifest.interfaceRefTag :
                        interfaceRefClientId = subElement.attributes[GeniManifest.clientIdTag].value
                        componentId = "urn:publicid:geni-in-a-box.net+interface+{0}:eth{1}".format(\
                        self.NICs[interfaceRefClientId].myHost.nodeName,\
                        self.NICs[interfaceRefClientId].deviceNumber)
                        
                        # set the attribute for the component id
                        subElement.setAttribute(GeniManifest.componentIdTag, componentId)
                        
                    # append the sub element to the manifest file link node
                    link.appendChild(subElement)

            # add the link to the overall manifest file
            header.appendChild(link)
        
        
        # go through and add all of the host nodes to the manifest,
        # these become the computers the user wanted allocated
        hostNames = self.hosts.keys()
        for i in xrange(0, len(hostNames)) :
            # add the allocated computer to the manifest rspec
            node = manifest.createElement(GeniManifest.nodeTag)
            node.setAttribute(GeniManifest.exclusiveTag, "false")
            node.setAttribute(GeniManifest.clientIdTag, self.hosts[hostNames[i]].nodeName)
            
            # find the host in the original rspec that belongs to the current node being looked at,
            # then copy all of the known information to the manifest, this must be done since the
            # 'currentHost' element cannot be added to the manifest directly
            currentHost = originalHosts[0]
            for nextHost in originalHosts :
                if nextHost.hasAttribute(GeniManifest.clientIdTag) and nextHost.attributes[GeniManifest.clientIdTag].value == self.hosts[hostNames[i]].nodeName :
                    currentHost = nextHost
                    break
            
            # add each sub-element of the link that should be copied over to the manifest
            for currentSubElement in GeniManifest.knownHostSubElements :
                subElements = currentHost.getElementsByTagName(currentSubElement)
                for subElement in subElements :
                    
                    # if the sub-element is a sliver_type element then set the
                    # disk_image sub-element of sliver_type to be fedora15
                    if subElement.nodeName == GeniManifest.sliverTypeTag :
                        diskImageElements = subElement.getElementsByTagName(GeniManifest.diskImageTag)
                        for diskImageElement in diskImageElements :
                            diskImageElement.setAttribute("name", "urn:publicid:geni-in-a-box.net+image+emulab-ops//FEDORA15-STD")
                    
                    node.appendChild(subElement) # add the sub-element, TODO: FORMATTING ISSUES
            
            
            # go through each of this node's interfaces and create those elements
            for nic in self.hosts[hostNames[i]].NICs :
                interface = manifest.createElement(GeniManifest.interfaceTag)   # an interface element for the node
                interface.setAttribute(GeniManifest.clientIdTag, nic.nicName)
                interface.setAttribute(GeniManifest.componentIdTag, "urn:publicid:geni-in-a-box.net+interface+{0}:eth{1}".format(self.hosts[hostNames[i]].nodeName, nic.deviceNumber))
                interface.setAttribute(GeniManifest.macTag, nic.macAddress)

                # set the ip address, for now this is a sub-element of the interface element
                # this could also possibly be an attribute
                ipAddress = manifest.createElement(GeniManifest.ipTag)
                ipAddress.setAttribute(GeniManifest.addressTag, nic.ipAddress)
                interface.appendChild(ipAddress)

                node.appendChild(interface)
            
            header.appendChild(node)

        
        # print the rspec to the terminal for display and debugging,
        # this can be removed later on
        print manifest.toprettyxml(indent = "  ", newl = "\n");
        
        # Create the file into which the manifest will be written
        pathToFile = config.sliceSpecificScriptsDir + '/' + config.manifestFile
        try:
            manFile = open(pathToFile, 'w')
        except IOError:
            config.logger.error("Failed to open file that creates sliver: ",
                                pathToFile)
            return None

        manifest.writexml(manFile, addindent = "  ", newl = "\n")
        manFile.close()
        return 0;
