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

import logging
import sys
from xml.dom.minidom import getDOMImplementation, parseString, Node

import objects

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
        return dom_template

    # Replace the 'node' section of the dom_template with 
    # a list of all node sections from the manifests
    def combineNodes(self, ams_list, dom_template):


        # Remove the 'node' element from template
        doc_root = dom_template.documentElement
        children = doc_root.childNodes
        for child in children:
            if child.nodeType == Node.ELEMENT_NODE and \
                    child.nodeName == 'node':
                client_id = child.getAttribute('client_id')
                doc_root.removeChild(child)
#                print "Removing " + str(child) + " " + client_id

        unique_clients = {}

        for am in ams_list:
            urn = am.urn
            dom = am.manifestDom
            dom_doc_root = dom.documentElement
            children = dom_doc_root.childNodes
            for child in children:
                if child.nodeType == Node.ELEMENT_NODE and \
                        child.nodeName == 'node':
                    client_id = child.getAttribute('client_id')
                    if not unique_clients.has_key(client_id):
                        unique_clients[client_id] = True
                        doc_root.appendChild(child)
#                        print "Adding " + str(child) + " " + client_id



    # Add a unique copy of each link from each file (only one per urn)
    def combineLinks(self, ams_list, dom_template):

        # Remove the 'link' elements from template
        doc_root = dom_template.documentElement
        children = doc_root.childNodes
        for child in children:
            if child.nodeType == Node.ELEMENT_NODE and \
                    child.nodeName == 'link':
                client_id = child.getAttribute('client_id')
                doc_root.removeChild(child)
#                print "Removing " + str(child) + " " + client_id

        unique_clients = {}
        for am in ams_list:
            urn = am.urn
            dom = am.manifestDom
            dom_doc_root = dom.documentElement
            children = dom_doc_root.childNodes
            for child in children:
                if child.nodeType == Node.ELEMENT_NODE and \
                        child.nodeName == 'link':
                    client_id = child.getAttribute('client_id')
                    # Add only one copy of the link per client_id
                    if not unique_clients.has_key(client_id):
#                        print "Adding " + str(child) + " " + client_id
                        doc_root.appendChild(child)
                        unique_clients[client_id] = True



                        

    # Take a list of ams 
    # and replace the hop in the dom_template with the appropriate
    # hop from the list of hops of the matching am
    # An aggregate has a list of hops and a manifestDom
    # A hop has a hop_link which has an ID which matches the ID of the
    # hop in the template dom
    def combineHops(self, ams_list, dom_template):
        template_stitching = self.getStitchingElement(dom_template)
        template_path = template_stitching.childNodes[0]

        for am in ams_list:
            for hop in am.hops:
                hop_id = int(hop._id)
#                print "AGG " + str(am) + " HID " + str(hop_id)
                self.replaceHopElement(template_path, self.getStitchingElement(am.manifestDom), hop_id)

    # Replace the hop element in the template DOM with the hop element 
    # from the aggregate DOM that has the given HOP ID
    def replaceHopElement(self, template_path, am_stitching, hop_id):
        template_hop = None
        for child in template_path.childNodes:
            if child.nodeType == Node.ELEMENT_NODE and \
                    child.nodeName == 'hop' and \
                    int(child.getAttribute('id')) == hop_id:
                template_hop = child
                break

        am_path = am_stitching.childNodes[0]
        am_hop = None
        for child in am_path.childNodes:
            if child.nodeType == Node.ELEMENT_NODE and \
                    child.nodeName == 'hop' and \
                    int(child.getAttribute('id')) == hop_id:
                am_hop = child
                break

        if am_hop and template_hop:
#            print "T_HOP = " + str(template_hop) + " HID = " + str(hop_id) + " AM_HOP = " + str(am_hop)
            template_path.replaceChild(am_hop, template_hop)
        else:
            self.logger.error ("Can't replace hop in template: AM HOP %s TEMPLATE HOP %s" % (am_hop, template_hop))
                

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

