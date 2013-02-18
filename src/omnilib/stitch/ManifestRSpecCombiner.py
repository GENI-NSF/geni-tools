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
        pass

    # Combine the manifest, replacing elements in the dom_template
    # with the approapriate pieces from the manifests
    # Arguments:
    #    ams_list is a list of Aggregate objects
    #    dom_template is a dom object into which to replace selected
    #      components from the aggregate doms
    def combine(self, ams_list, dom_template):
        mans_list = [am.manifestDom for am in ams_list]
        self.combineNodes(mans_list, dom_template)
        self.combineLinks(mans_list, dom_template)
        self.combineHops(ams_list, dom_template)
        return dom_template

    # Replace the 'node' section of the dom_template with 
    # a list of all node sections from the manifests
    def combineNodes(self, mans_list, dom_template):

        # Remove the 'node' element from template
        doc_root = dom_template.documentElement
        children = doc_root.childNodes
        for child in children:
            if child.nodeType == Node.ELEMENT_NODE and \
                    child.nodeName == 'node':
                client_id = child.getAttribute('client_id')
                doc_root.removeChild(child)
#                print "Removing " + str(child) + " " + client_id

        for man in mans_list:
            urn = man[0]
            dom = man[1]
            dom_doc_root = dom.documentElement
            children = dom_doc_root.childNodes
            for child in children:
                if child.nodeType == Node.ELEMENT_NODE and \
                        child.nodeName == 'node':
                    client_id = child.getAttribute('client_id')
                    doc_root.appendChild(child)
#                    print "Adding " + str(child) + " " + client_id

    # Add a unique copy of each link from each file (only one per urn)
    def combineLinks(self, mans_list, dom_template):

        # Remove the 'link' elements from template
        doc_root = dom_template.documentElement
        children = doc_root.childNodes
        for child in children:
            if child.nodeType == Node.ELEMENT_NODE and \
                    child.nodeName == 'link':
                sliver_id = child.getAttribute('sliver_id')
                doc_root.removeChild(child)
#                print "Removing " + str(child) + " " + sliver_id

        unique_slivers = {}
        for man in mans_list:
            urn = man[0]
            dom = man[1]
            dom_doc_root = dom.documentElement
            children = dom_doc_root.childNodes
            for child in children:
                if child.nodeType == Node.ELEMENT_NODE and \
                        child.nodeName == 'link':
                    sliver_id = child.getAttribute('sliver_id')
                    # Add only one copy of the link per sliver_id
                    if not unique_slivers.has_key(sliver_id):
#                        print "Adding " + str(child) + " " + sliver_id
                        doc_root.appendChild(child)
                    unique_slivers[sliver_id] = True
                        

    # Take a list of ams 
    # and replace the hop in the dom_template with the appropriate
    # hop from the list of hops of the matching am
    # An aggregate has a list of hops and a manifestDom
    # A hop has a hop_link which has an ID which matches the ID of the
    # hop in the template dom
    def combineHops(self, ams_list, dom_template):

        doc_root = dom_template.document_element
        children = doc_root.childNodes
        for child in children:
            if child.nodeType == Node.ELEMENT_NODE and \
                    child.nodeName == 'stitching':
                stitching_node = child
                path_node = stitching_node.childNodes[0]
                print "SN = " + str(stitching_node)
                print "PN = " + str(path_node)

def createAggregateFromDom(manifest_dom, agg_urn):
    doc_root = manifest_dom.documentElement
    children = doc_root.childNodes
    agg = Aggregate(urn)
    agg.manifestDom = manifest_dom
    for child in children:
        if child.nodeType == Node.ELEMENT_NODE and \
                child.nodeName == 'stitching':
            stitching_node = child
            path_node = child.childNodes[0]
            hops = [Hop.fromDOM(hop_node) for hop_node in path_node.childNodes]
            agg._hops = hops
    return agg

def combineManifestRSpecs(ams_list, dom_template):
    mrc = ManifestRSpecCombiner()
    return mrc.combine(ams_list, dom_template)

if __name__ == "__main__":


    prefix = "/Users/mbrinn/geni/gcf/stitcherTestFiles/"
    filenames_by_urn = {
        "urn:publicid:IDN+emulab.net+authority+cm": 
        prefix+"ahtest-manifest-rspec-emulab-net-protogeniv2.xml",
        "urn:publicid:IDN+ion.internet2.edu+authority+cm": 
        prefix+"ahtest-manifest-rspec-geni-am-net-internet2-edu.xml",
        "urn:publicid:IDN+instageni.gpolab.bbn.com+authority+cm": 
        prefix+"ahtest-manifest-rspec-instageni-gpolab-bbn-com-protogeniv2.xml", 
        "urn:publicid:IDN+utah.geniracks.net+authority+cm":
            prefix+"ahtest-manifest-rspec-utah-geniracks-net-protogeniv2.xml"
        }


    ams_list = list()
    dom_template = None
    for urn in filenames_by_urn.keys():
        filename = filenames_by_urn[urn]
        file = open(filename, 'r')
        data = file.read()
        file.close()
        try:
            dom = parseString(data)
            am = createAggregateFromDom(dom, urn)
            ams_list.append(am)
            # Arbitrarily pick the first one as the 'template'
            if not dom_template:
                dom_template = parseString(data)
        except Exception, e:
            msg = "Failed to parse rspec: %s %s" % (filename, e)
            self.logger.error(msg)
            raise StitchingError(msg)


#     for mans in mans_list:
#         urn = mans[0]
#         dom = mans[1]
#         print urn + " " + str(dom)
#     print "TEMPLATE = " + str(dom_template)

    mrc = ManifestRSpecCombiner()
    revised_dom_template = mrc.combine(ams_list, dom_template)

#    print "RESULT: " + revised_dom_template.toprettyxml()
