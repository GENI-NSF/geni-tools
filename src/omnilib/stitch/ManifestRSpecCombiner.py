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
'''
 Class to merge a set of individual manifest RSpecs received from
 individual allocate/provision calls and join them into a single
 manifest for the whole stitching operation
'''

import json
import logging
import sys
from xml.dom.minidom import getDOMImplementation, parseString, Node

import objects

# FIXME: As in RSpecParser, check use of getAttribute vs getAttributeNS and localName vs nodeName

class ManifestRSpecCombiner:

    # Constructor
    def __init__(self):
        self.logger = logging.getLogger('stitch.ManifestRSpecCombiner')

    # Combine the manifest, replacing elements in the dom_template
    # with the approapriate pieces from the manifests
    # Arguments:
    #    ams_list is a list of Aggregate objects
    #    dom_template is a dom object into which to replace selected
    #      components from the aggregate doms
    def combine(self, ams_list, dom_template):
        self.combineNodes(ams_list, dom_template)
        self.combineLinks(ams_list, dom_template)
        self.combineHops(ams_list, dom_template)
        self.addAggregateDetails(ams_list, dom_template)
        return dom_template

    # Replace the 'node' section of the dom_template with 
    # a list of all node sections from the manifests
    def combineNodes(self, ams_list, dom_template):

        # Set up a dictionary mapping node by component_manager_id
        template_nodes_by_cmid={}
        doc_root = dom_template.documentElement
        children = doc_root.childNodes
        for child in children:
            if child.nodeType == Node.ELEMENT_NODE and \
                    child.nodeName == 'node':
                cmid = child.getAttribute('component_manager_id')
                template_nodes_by_cmid[cmid] = child

#        print "DICT = " + str(template_nodes_by_cmid)
        
        # Replace a node when we find the matching manifest
        # Match the manifest from a given AMs manifest if that AM's urn is the 
        # component_manager_id attribute on that node
        # But only add a node once for a given component_manager_id
        unique_cmids = {}
        for am in ams_list:
            urn = am.urn
            am_manifest_dom = am.manifestDom
            if template_nodes_by_cmid.has_key(urn):
                template_node = template_nodes_by_cmid[urn]
                am_doc_root = am_manifest_dom.documentElement
                for child in am_doc_root.childNodes:
                    if child.nodeType == Node.ELEMENT_NODE and \
                            child.nodeName == 'node':
                        child_cmid = child.getAttribute('component_manager_id')
                        if child_cmid == urn and not unique_cmids.has_key(child_cmid):
                            self.logger.debug("Replacing " + str(template_node) + " with " + str(child) + " " + child_cmid)
                            doc_root.replaceChild(child, template_node)
                            unique_cmids[child_cmid] = True
                


    # Replace each link in dom_template with matching link from AM with same URN
    # 
    # For each link in dom_template
    # Find the first <component_manager> child element
    # Go to the am with that am.urn
    # Find the <link> element from that AM's manifest
    # Replace link element in template with that link element
    def combineLinks(self, ams_list, dom_template):

        template_links_by_cmid = {}

        # Gather each link in template by component_manager_id
        doc_root = dom_template.documentElement
        children = doc_root.childNodes
        for child in children:
            if child.nodeType == Node.ELEMENT_NODE and \
                    child.nodeName == 'link':
                link = child
                # Get first 'component_manager' child element
                component_manager_elements = link.getElementsByTagName('component_manager')
#                for cm in component_manager_elements: print "     " + str(cm) + " " + str(cm.getAttribute('name'))
                component_manager_element = link.getElementsByTagName('component_manager')[0]
                cmid = component_manager_element.getAttribute('name')
#                print "LINK = " + str(link) + " " + cmid
                template_links_by_cmid[cmid] = child

#        print "DICT = " + str(template_links_by_cmid)

        # Replace the link with the link from the manifest of the AM with the link's first component_manager
        for am in ams_list:
            urn = am.urn
            am_manifest_dom = am.manifestDom
            if template_links_by_cmid.has_key(urn):
                template_link = template_links_by_cmid[urn]
                am_doc_root = am_manifest_dom.documentElement
                for child in am_doc_root.childNodes:
                    if child.nodeType == Node.ELEMENT_NODE and \
                            child.nodeName == 'link':
                        doc_root.replaceChild(child, template_link)
                        child_cmid = link.getElementsByTagName('component_manager')[0].getAttribute('name')
                        self.logger.debug("Replacing " + str(template_link) + " with " + str(child) + " " + child_cmid)
                        break
                        

    # Take a list of ams 
    # and replace the hop in the dom_template with the appropriate
    # hop from the list of hops of the matching am
    # An aggregate has a list of hops and a manifestDom
    # A hop has a hop_link which has an ID which matches the ID of the
    # hop in the template dom
    def combineHops(self, ams_list, dom_template):
        template_stitching = self.getStitchingElement(dom_template)
        for am in ams_list:
            for hop in am.hops:
                hop_id = hop._id
                path_id = hop.path.id
                template_path = self.findPathByID(template_stitching, path_id)
#                print "AGG " + str(am) + " HID " + str(hop_id)
                self.replaceHopElement(template_path, self.getStitchingElement(am.manifestDom), hop_id, path_id)

    # Add details about allocations to each aggregate in a 
    # structured comment at root of DOM
    # Content for each component: 
    #   URN - URN of aggregate
    #   URL - URL of aggregate
    #   API_VERSION - Version of AM API supported by AM
    #   USER_REQUESTED - Boolean whether this agg was in the origin request RSPEC (or SCS added it)
    #   HOP_INFOs - List of HOP URN's and VLAN tags and HOP IDs and PATH ID's for that aggregate
    # Format is JSON
    # {
    #   {'urn':urn, 'url':url, 'api_version':api_version, 'user_requested':user_requested, 'hop_info':[{'urn':urn, 'id':hop_id, 'path_id':path_id, 'vlan_tag':vlan_tag}]}
    # }           
    def addAggregateDetails(self, ams_list, dom_template):
        doc_element = dom_template.documentElement
        comment_text = "\n" + "Aggregate Details" + "\n"
        for am in ams_list:
            am_details = self.computeAMDetails(am)
            am_details_text = json.dumps(am_details)
            comment_text = comment_text + am_details_text + "\n"
        comment_element = dom_template.createComment(comment_text)
        first_non_comment_element = None
        for elt in dom_template.childNodes:
            if elt.nodeType != Node.COMMENT_NODE:
                first_non_comment_element = elt;
                break
        dom_template.insertBefore(comment_element, first_non_comment_element)

    # Compute dictionary containing details about a particular aggregate 
    def computeAMDetails(self, am):
        urn = am.urn
        url = am.url
        api_version = am.api_version
        user_requested = am.userRequested
        hops_info = [{'urn':hop._hop_link.urn, 'vlan_tag':str(hop._hop_link.vlan_suggested_manifest), 'path_id':hop.path.id, 'id':hop._id}  for hop in am._hops]
        return {'urn':urn, 'url': url, 'api_version':api_version, 'user_requested':user_requested, 'hops_info':hops_info}

    # Replace the hop element in the template DOM with the hop element 
    # from the aggregate DOM that has the given HOP ID
    def replaceHopElement(self, template_path, am_stitching, hop_id, path_id):
        template_hop = None

        for child in template_path.childNodes:
            if child.nodeType == Node.ELEMENT_NODE and \
                    child.nodeName == 'hop' and \
                    child.getAttribute('id') == hop_id:
                template_hop = child
                break

        # Find the path for the given path_id (there may be more than one)
        am_path = self.findPathByID(am_stitching, path_id)

        am_hop = None
        if am_path:
            for child in am_path.childNodes:
                if child.nodeType == Node.ELEMENT_NODE and \
                        child.nodeName == 'hop' and \
                        child.getAttribute('id') == hop_id:
                    am_hop = child
                    break

        if am_hop and template_hop:
            self.logger.debug("Replacing " + str(template_hop) + " with " + str(am_hop))
            template_path.replaceChild(am_hop, template_hop)
        else:
            self.logger.error ("Can't replace hop in template: AM HOP %s TEMPLATE HOP %s" % (am_hop, template_hop))

    def findPathByID(self, stitching, path_id):
        path = None
        for child in stitching.childNodes:
            if child.nodeType == Node.ELEMENT_NODE and \
                    child.nodeName == 'path' and \
                    child.getAttribute('id') == path_id:
                path = child
                break
        return path

    def getStitchingElement(self, manifest_dom):
        rspec_node = None
        for child in manifest_dom.childNodes:
            if child.nodeType == Node.ELEMENT_NODE and \
                    child.nodeName == 'rspec':
                rspec_node = child
                break
        if rspec_node:
            for child in rspec_node.childNodes:
                if child.nodeType == Node.ELEMENT_NODE and \
                        child.nodeName == 'stitching':
                    return child
        return None

def combineManifestRSpecs(ams_list, dom_template):
    mrc = ManifestRSpecCombiner()
    return mrc.combine(ams_list, dom_template)

