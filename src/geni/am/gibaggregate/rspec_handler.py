
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
    componentManagerIdTag = "component_manager_id"  # tag used for component manager attributes on nodes
    sliverTypeTag       = "sliver_type"             # tag used for defining a sliver type on a host
    diskImageTag        = "disk_image"              # tag used for defining the type of image on a host
    servicesTag         = "services"                # tag used for defining services on a host node
    nameTag             = "name"                    # tag used for naming attributes
    hostTag             = "host"                    # used for identifying host elements under node elements
    rsVnodeTag          = "rs:vnode"                # used for identifying rs:vnode elements
    webpage             = "http://www.protogeni.net/resources/rspec/0.1"
    
    
    """\
    Initializes a new instance of GeniManifest.
    
    This constructor expects the request rspec has already
    been parsed and the structure is already set up.
    """
    def __init__(self, sliceName, rspec, experimentHosts, experimentLinks, experimentNICs) :
        self.sliceName = sliceName
        self.rspec = rspec
        self.hosts = experimentHosts
        self.links = experimentLinks
        self.NICs = experimentNICs
        self.validUntil = datetime.datetime.today() + datetime.timedelta(days = 365)
    
    
    """\
    Creates a manifest rspec file to the given file name.
    """
    def create(self) :
        
        # parse the original document and then set up the children nodes
        originalRspec = parseString(self.rspec).childNodes[0]
        
        # create the document and the main header/wrapper portion
        manifest = Document()
        manifest.appendChild(originalRspec)
        originalRspec.setAttribute(GeniManifest.typeTag, "manifest")
        
        # go through every child node within the rspec and
        # set the appropriate values for known node elements
        # and copy over the others that are not known
        for rspecChild in originalRspec.childNodes :

            # skip any test nodes, formatting is taken care
            # of just before the final manifest is written,
            # WARNING: minidom has weird behaviors when text
            # nodes are included, they must be excluded for
            # proper functioning of the xml parser
            if rspecChild.nodeType == rspecChild.TEXT_NODE :
                continue
            
            # if a link element then go through and set the correct values such as ip address and mac addresses
            if rspecChild.nodeName == GeniManifest.linkTag and rspecChild.hasAttribute(GeniManifest.clientIdTag):
                    
                for linkChild in rspecChild.childNodes :
                    
                    if linkChild.nodeType == linkChild.TEXT_NODE :
                        continue
                    
                    # if the child node is a component manager element
                    # then set the name to be geni-in-a-box specific
                    if linkChild.nodeName == GeniManifest.componentManagerTag :
                        linkChild.setAttribute(GeniManifest.nameTag, "urn:publicid:geni-in-a-box.net+authority+cm")
                        
                    # if the child node is an interface reference
                    # then set the appropriate component id
                    elif linkChild.nodeName == GeniManifest.interfaceRefTag and linkChild.hasAttribute(GeniManifest.clientIdTag):
                        # find the NIC object that goes with this interface reference element
                        if linkChild.attributes[GeniManifest.clientIdTag].value in self.NICs.keys() :
                            clientId = linkChild.attributes[GeniManifest.clientIdTag].value
                            componentId = "urn:publicid:geni-in-a-box.net+interface+{0}:eth{1}".format(self.NICs[clientId].myHost.nodeName, self.NICs[clientId].deviceNumber)
                            linkChild.setAttribute(GeniManifest.componentIdTag, componentId)
                    
                    
            
            # if a node element then go through and set the correct values
            if rspecChild.nodeName == GeniManifest.nodeTag and rspecChild.hasAttribute(GeniManifest.clientIdTag) :
                rspecChild.setAttribute(GeniManifest.exclusiveTag, "false") # no container is exclusive in geni-in-a-box
                
                # find the host object associated with this node
                currentHost = None
                for hostName in self.hosts.keys() :
                    if self.hosts[hostName].nodeName == rspecChild.attributes[GeniManifest.clientIdTag].value :
                        currentHost = self.hosts[hostName]
                        break
                
                # there needs to be a host associated with this node otherwise it is invalid
                if currentHost != None :
                    rspecChild.setAttribute(GeniManifest.componentManagerIdTag, "urn:publicid:geni-in-a-box.net+authority+cm")
                    rspecChild.setAttribute(GeniManifest.componentIdTag, "urn:publicid:geni-in-a-box.net+node+pc{0}".format(currentHost.containerName))
                        
                    for nodeChild in rspecChild.childNodes :
                        
                        if nodeChild.nodeType == nodeChild.TEXT_NODE :
                            continue
                        
                        # if the child node is a sliver type element
                        # then set the correct sliver type
                        if nodeChild.nodeName == GeniManifest.sliverTypeTag :
                            nodeChild.setAttribute(GeniManifest.nameTag, "virtual-pc")
                            
                            # go through and find the children of the sliver type element,
                            # specifically look for disk images and set the correct type
                            for sliverTypeChild in nodeChild.childNodes :
                                if sliverTypeChild.nodeName == GeniManifest.diskImageTag :
                                    sliverTypeChild.setAttribute(GeniManifest.nameTag, "urn:publicid:geni-in-a-box.net+image+emulab-ops//" + config.distro)
                    
                        # if the child node is an interface
                        # then set up the ip and mac addresses
                        elif nodeChild.nodeName == GeniManifest.interfaceTag :
                            # find the NIC object that goes with this interface element
                            if nodeChild.attributes[GeniManifest.clientIdTag].value in self.NICs.keys() :
                                nic = self.NICs[nodeChild.attributes[GeniManifest.clientIdTag].value]
                            
                                nodeChild.setAttribute(GeniManifest.clientIdTag, nic.nicName)
                                nodeChild.setAttribute(GeniManifest.componentIdTag, "urn:publicid:geni-in-a-box.net+interface+{0}:eth{1}".format(nic.myHost.nodeName, nic.deviceNumber))
                                nodeChild.setAttribute(GeniManifest.macTag, nic.macAddress)
        
                                # set the ip address, for now this is a sub-element of the
                                # interface element this could also possibly be an attribute
                                ipAddress = manifest.createElement(GeniManifest.ipTag)
                                ipAddress.setAttribute(GeniManifest.addressTag, nic.ipAddress)
                                nodeChild.appendChild(ipAddress)

                        # if a host element then set the correct host name
                        elif nodeChild.nodeName == GeniManifest.hostTag :
                            nodeChild.setAttribute(GeniManifest.nameTag, currentHost.nodeName + "." + self.sliceName + ".geni-in-a-box.net")
                        
                        # if a rs:vnode element then set the correct name with container number
                        elif nodeChild.nodeName == GeniManifest.rsVnodeTag :
                            nodeChild.setAttribute(GeniManifest.nameTag, "pc" + str(currentHost.containerName))
        
        
        # print the rspec to the terminal for display and debugging,
        # this can be removed later on
        manifestXml = manifest.toprettyxml(indent = "  ");
        finalManifest = ""
        
        # clean up some of the spacing that happens from minidom
        for line in manifestXml.split('\n'):
            if line.strip():
                finalManifest += line + '\n'
                
        print finalManifest
        
        # Create the file into which the manifest will be written
        pathToFile = config.sliceSpecificScriptsDir + '/' + config.manifestFile
        try:
            manFile = open(pathToFile, 'w')
        except IOError:
            config.logger.error("Failed to open file that creates sliver: ",
                                pathToFile)
            return None

        manFile.write(finalManifest)
        manFile.close()
        return 0;
