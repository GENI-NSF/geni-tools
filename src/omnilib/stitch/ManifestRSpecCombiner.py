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
 Class and function to merge a set of individual manifest RSpecs received from
 individual allocate/provision calls and join them into a single
 manifest for the whole stitching operation.
'''

import json
import logging
import sys
from xml.dom.minidom import getDOMImplementation, parseString, Node

import objects
import RSpecParser

# Constants for RSpec parsing -- FIXME: Merge into RSpecParser
COMPONENT_MGR_ID = 'component_manager_id'
COMP_MGR = 'component_manager'
COMP_MGR_NAME = 'name'
CLIENT_ID = 'client_id'
SLIVER_ID = 'sliver_id'
COMP_ID = 'component_id'
INTFC_REF = 'interface_ref'
VLANTAG = 'vlantag'
HOP = 'hop'
HOP_ID = 'id'
PATH_ID = 'id'

# FIXME: As in RSpecParser, check use of getAttribute vs getAttributeNS and localName vs nodeName

class ManifestRSpecCombiner:

    # Constructor
    def __init__(self):
        self.logger = logging.getLogger('stitch.ManifestRSpecCombiner')

    # Combine the manifest, replacing elements in the dom_template
    # with the appropriate pieces from the manifests
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

    def combineNodes(self, ams_list, dom_template):
        '''Replace the 'node' section of the dom_template with 
        the corresponding node from the manifest of the Aggregate with a matching 
        component_manager URN'''

        # Set up a dictionary mapping node by component_manager_id
        template_nodes_by_cmid={}
        doc_root = dom_template.documentElement
        children = doc_root.childNodes
        for child in children:
            if child.nodeType == Node.ELEMENT_NODE and \
                    child.localName == RSpecParser.NODE_TAG:
                cmid = child.getAttribute(COMPONENT_MGR_ID)
                # FIXME: This allows only one node per cmid. There can be multiple
                if not template_nodes_by_cmid.has_key(cmid):
                    template_nodes_by_cmid[cmid] = []
                template_nodes_by_cmid[cmid].append(child)

#        print "DICT = " + str(template_nodes_by_cmid)
        
        # Replace a node when we find the matching manifest
        # Match the manifest from a given AMs manifest if that AM's urn is the 
        # component_manager_id attribute on that node and the client_ids match
        for am in ams_list:
            urn = am.urn
            if template_nodes_by_cmid.has_key(urn):
                am_manifest_dom = am.manifestDom
                am_doc_root = am_manifest_dom.documentElement
                for template_node in template_nodes_by_cmid[urn]:
                    template_client_id = template_node.getAttribute(CLIENT_ID)
                    for child in am_doc_root.childNodes:
                        if child.nodeType == Node.ELEMENT_NODE and \
                                child.localName == RSpecParser.NODE_TAG:
                            child_cmid = child.getAttribute(COMPONENT_MGR_ID)
                            child_client_id = child.getAttribute(CLIENT_ID)
                            if child_cmid == urn and child_client_id == template_client_id:
                                #self.logger.debug("Replacing " + str(template_node) + " with " + str(child) + " " + child_cmid)
                                doc_root.replaceChild(child, template_node)

    def combineLinks(self, ams_list, dom_template):
        '''Replace each link in dom_template with matching link from (an) AM with same URN.
        Add comments noting the vlantag and sliver_id other AMs gave that link.
        Within that link, replace the interface_ref with the matching element from the AM that
        put a component_id / sliver_id on that element.'''

        # For each link in template by component_manager_id
        doc_root = dom_template.documentElement
        children = doc_root.childNodes
        for child in children:
            if child.nodeType == Node.ELEMENT_NODE and \
                    child.localName == RSpecParser.LINK_TAG:
                link = child
                # Get first 'component_manager' child element
#                print "LINK = " + str(link) + " " + cmid
                client_id = str(link.getAttribute(CLIENT_ID))
                needSwap = False
                if not link.hasAttribute(SLIVER_ID) and not link.hasAttribute(VLANTAG):
                    needSwap = True
#                    self.logger.debug("Link %s in template must be swapped", client_id)
                else:
#                    self.logger.debug("Link %s in template has a sliver_id or a vlantag", client_id)
                    pass

                # get list of all cmids on this link
                # Only look at AMs that match
                component_manager_elements = link.getElementsByTagName(COMP_MGR)
                cms = []
                for cme in component_manager_elements:
                   cms.append(str(cme.getAttribute(COMP_MGR_NAME)))
#                self.logger.debug("Ams in Link %s: %s", client_id, cms)

                # Get interface_ref elements that need to be swapped
                intfs = {}
                for intf in link.getElementsByTagName(INTFC_REF):
                    if not intf.hasAttribute(SLIVER_ID) and not intf.hasAttribute(COMP_ID):
                        intfs[str(intf.getAttribute(CLIENT_ID))] = intf
#                        self.logger.debug("intfc_ref %s has no sliver_id or component_id", intf.getAttribute(CLIENT_ID))
                    else:
                        sid = None
                        cid = None
                        if intf.hasAttribute(COMP_ID):
                            cid = intf.getAttribute(COMP_ID)
                        if intf.hasAttribute(SLIVER_ID):
                            sid = intf.getAttribute(SLIVER_ID)
#                        self.logger.debug("intfc_ref %s has sliver_id %s, component_id %s", intf.getAttribute(CLIENT_ID), sid, cid)

#                self.logger.debug("Interfaces we need to swap: %s", intfs)

                if len(intfs) == 0 and not needSwap:
                    continue

                for agg in ams_list:
                    if len(intfs) == 0 and not needSwap:
                        break
                    if agg.urn not in cms:
                        # Not a relevant aggregate
#                        self.logger.debug("Skipping AM %s not involved in link %s", agg.urn, client_id)
                        continue
#                    else:
#                        self.logger.debug("Looking at AM %s for link %s", agg.urn, client_id)
                    man = agg.manifestDom
                    link_elements = man.getElementsByTagName(RSpecParser.LINK_TAG)
                    for link2 in link_elements:
                        if len(intfs) == 0 and not needSwap:
                            break
                        # Get the link with a sliverid and the right client_id
                        if str(link2.getAttribute(CLIENT_ID)) == client_id and \
                                link2.hasAttribute(VLANTAG):
#                            self.logger.debug("Found AM %s link %s that has vlantag %s", agg.urn, client_id, link2.getAttribute('vlantag'))
                            if needSwap:
#                                self.logger.debug("Swapping link in template with this element")
                                doc_root.replaceChild(link2, link)
                                needSwap = False
                                # Need to pull out the irefs with a sliver id or component_id from link
                                # Before completing this swap
                                for intf in link.childNodes:
                                    if intf.nodeType == Node.ELEMENT_NODE and \
                                            intf.localName == INTFC_REF and \
                                            (intf.hasAttribute(SLIVER_ID) or intf.hasAttribute(COMP_ID)):
                                        for intf2 in link2.childNodes:
                                            if inf2.nodeType == Node.ELEMENT_NODE and \
                                                    intf2.localName == INTFC_REF and \
                                                    str(intf2.getAttribute(CLIENT_ID)) == str(intf.getAttribute(CLIENT_ID)) and \
                                                    (not intf2.hasAttribute(SLIVER_ID) and not intf2.hasAttribute(COMP_ID)):
#                                                self.logger.debug("from old template saving iref %s", intf2.getAttribute(CLIENT_ID))
                                                link2.replaceChild(intf, intf2)
                                                break

                                # Need to recreate intfs dict
                                # Get interface_ref elements that need to be swapped
                                intfs = {}
                                for intf in link2.getElementsByTagName(INTFC_REF):
                                    if not intf.hasAttribute(SLIVER_ID) and not intf.hasAttribute(COMP_ID):
                                        intfs[str(intf.getAttribute(CLIENT_ID))] = intf
#                                        self.logger.debug("intfc_ref %s has no sliver_id or component_id", intf.getAttribute(CLIENT_ID))
                                    else:
                                        sid = None
                                        cid = None
                                        if intf.hasAttribute(COMP_ID):
                                            cid = intf.getAttribute(COMP_ID)
                                        if intf.hasAttribute(SLIVER_ID):
                                            sid = intf.getAttribute(SLIVER_ID)
#                                        self.logger.debug("intfc_ref %s has sliver_id %s, component_id %s", intf.getAttribute(CLIENT_ID), sid, cid)
#                                self.logger.debug("Interfaces we need to swap: %s", intfs)

                                # Add a comment on link2 with link's sliver_id and vlan_tag
                                lsid = None
                                if link.hasAttribute(SLIVER_ID):
                                    lsid = link.getAttribute(SLIVER_ID)
                                lvt = link.getAttribute(VLANTAG)
                                comment_text = "AM %s: sliver_id=%s vlantag=%s" % (agg.urn, lsid, lvt)
                                comment_element = dom_template.createComment(comment_text)
                                link2.insertBefore(comment_element, link2.firstChild)

                                link = link2
                                break # out of loop over link2's in this inner AM looking for the right link

                            # Look at this version of the link's interface_refs. If any have
                            # a sliver_id or component_id, then this is the version with manifest info
                            # put it on the linke
                            for intf in link2.childNodes:
                                if intf.nodeType == Node.ELEMENT_NODE and \
                                        intf.localName == INTFC_REF and \
                                        (intf.hasAttribute(SLIVER_ID) or intf.hasAttribute(COMP_ID)):
                                    cid = str(intf.getAttribute(CLIENT_ID))
                                    if intfs.has_key(cid):
                                        sid = None
                                        compid = None
                                        if intf.hasAttribute(COMP_ID):
                                            compid = intf.getAttribute(COMP_ID)
                                        if intf.hasAttribute(SLIVER_ID):
                                            sid = intf.getAttribute(SLIVER_ID)
#                                        self.logger.debug("replacing iref cid %s, sid %s, comp_id %s: %s for old %s", cid, sid, compid, intf, intfs[cid])
                                        link.replaceChild(intf, intfs[cid])
#                                        self.logger.debug("Copied iref %s from AM %s", cid, agg.urn)
                                        del intfs[cid]
                                # End of loop over this Aggs link's children, looking for i_refs

                            # Add a comment on link with link2's sliver_id and vlan_tag
                            lsid = None
                            if link2.hasAttribute(SLIVER_ID):
                                lsid = link2.getAttribute(SLIVER_ID)
                            lvt = link2.getAttribute(VLANTAG)
                            comment_text = "AM %s: sliver_id=%s vlantag=%s" % (agg.urn, lsid, lvt)
                            comment_element = dom_template.createComment(comment_text)
                            link.insertBefore(comment_element, link.firstChild)

                            break # out of loop over Aggs' elements
#                        else:
#                            acid = str(link2.getAttribute(CLIENT_ID))
#                            self.logger.debug("In manifest for AM %s found link %s", agg.urn, acid)
#                            if acid == client_id:
#                                self.logger.debug("Found AM %s link %s that has no vlantag - so we skip", agg.urn, client_id)
#                            else:
#                                self.logger.debug("Found AM %s link %s (not the one I'm looking for)", agg.urn, acid)


                    # End of loop over this Aggs elements looking for the particular link
                # end of loop over aggs looking for manifest link entries
            # End of block handling link elements
        # end of loop over template manifest elements
    # end of combineLinks

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
        didFirst = False
        for am in ams_list:
            am_details = self.computeAMDetails(am)
            am_details_text = json.dumps(am_details, indent=2)
            if didFirst:
                comment_text = comment_text + "\n"
            comment_text = comment_text + am_details_text + "\n"
            didFirst = True
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
        hops_info = [{'urn':hop._hop_link.urn, 'vlan_tag':str(hop._hop_link.vlan_suggested_manifest), 'path_id':hop.path.id, 'path_global_id':hop.path.globalId, 'id':hop._id}  for hop in am._hops]
        ret = {'urn':urn, 'url': url, 'api_version':api_version, 'user_requested':user_requested, 'hops_info':hops_info}
        if am.pgLogUrl:
            ret["PG Log URL"] = am.pgLogUrl
        return ret

    # Replace the hop element in the template DOM with the hop element 
    # from the aggregate DOM that has the given HOP ID
    def replaceHopElement(self, template_path, am_stitching, hop_id, path_id):
        template_hop = None

        for child in template_path.childNodes:
            if child.nodeType == Node.ELEMENT_NODE and \
                    child.localName == HOP and \
                    child.getAttribute(HOP_ID) == hop_id:
                template_hop = child
                break

        # Find the path for the given path_id (there may be more than one)
        am_path = self.findPathByID(am_stitching, path_id)

        am_hop = None
        if am_path:
            for child in am_path.childNodes:
                if child.nodeType == Node.ELEMENT_NODE and \
                        child.localName == HOP and \
                        child.getAttribute(HOP_ID) == hop_id:
                    am_hop = child
                    break

        if am_hop and template_hop:
            #self.logger.debug("Replacing " + str(template_hop) + " with " + str(am_hop))
            template_path.replaceChild(am_hop, template_hop)
        else:
            self.logger.error ("Can't replace hop in template: AM HOP %s TEMPLATE HOP %s" % (am_hop, template_hop))

    def findPathByID(self, stitching, path_id):
        path = None
        for child in stitching.childNodes:
            if child.nodeType == Node.ELEMENT_NODE and \
                    child.localName == RSpecParser.PATH_TAG and \
                    child.getAttribute(PATH_ID) == path_id:
                path = child
                break
        return path

    def getStitchingElement(self, manifest_dom):
        rspec_node = None
        for child in manifest_dom.childNodes:
            if child.nodeType == Node.ELEMENT_NODE and \
                    child.localName == RSpecParser.RSPEC_TAG:
                rspec_node = child
                break
        if rspec_node:
            for child in rspec_node.childNodes:
                if child.nodeType == Node.ELEMENT_NODE and \
                        child.localName == RSpecParser.STITCHING_TAG:
                    return child
        return None

def combineManifestRSpecs(ams_list, dom_template):
    '''Combine the manifests from the given Aggregate objects into the given DOM template (a manifest). Return a DOM'''
    mrc = ManifestRSpecCombiner()
    return mrc.combine(ams_list, dom_template)

