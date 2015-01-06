#----------------------------------------------------------------------
# Copyright (c) 2013-2015 Raytheon BBN Technologies
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

from __future__ import absolute_import

import json
import logging
import sys
from xml.dom.minidom import getDOMImplementation, Node

from . import objects
from . import defs
from .utils import stripBlankLines

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
LINK = 'link'
HOP_ID = 'id'
LINK_ID = 'id'
PATH_ID = 'id'

# FIXME: As in RSpecParser, check use of getAttribute vs getAttributeNS and localName vs nodeName

class ManifestRSpecCombiner:

    # Constructor
    def __init__(self, useReqs=False):
        self.logger = logging.getLogger('stitch.ManifestRSpecCombiner')
        self.useReqs = useReqs

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
        self.combineNSes(ams_list, dom_template)
        self.combineOthers(ams_list, dom_template)
        self.addAggregateDetails(ams_list, dom_template)
#        self.logger.debug("After addAggDets, man is %s", stripBlankLines(dom_template.toprettyxml(encoding="utf-8")))
        return dom_template

    def combineOthers(self, ams_list, dom_template):
        # Add to the base any top level elements not already there
        doc_root = dom_template.documentElement
        children = doc_root.childNodes
        template_kids = []
        # Find all the client_ids for nodes in the template too
        rspec_node = None
        if doc_root.nodeType == Node.ELEMENT_NODE and \
                doc_root.localName == defs.RSPEC_TAG:
            rspec_node = doc_root
        else:
            for child in children:
                if child.nodeType == Node.ELEMENT_NODE and \
                        child.localName == defs.RSPEC_TAG:
                    rspec_node = child
                    break
        if rspec_node is None:
            self.logger.debug("Couldn't find rspec in template!")
            return
        for child in rspec_node.childNodes:
            if child.localName in (defs.NODE_TAG, defs.LINK_TAG, defs.STITCHING_TAG):
                continue
            try:
                cstr = child.toxml(encoding="utf-8")
                if cstr:
                    cstr = cstr.strip()
            except Exception, xe:
                self.logger.debug("Failed to XMLify top level child '%s' - skipping: %s", child.nodeName, xe)
                cstr = ""
            if cstr == "":
                continue
            template_kids.append(cstr)
#            self.logger.debug("Template had element: '%s'...", cstr[:min(len(cstr), 60)])

        for am in ams_list:
            if self.useReqs:
                if not am.requestDom:
                    am.requestDom = am.getEditedRSpecDom(dom_template)
                am_manifest_dom = am.requestDom
            else:
                am_manifest_dom = am.manifestDom
            if am_manifest_dom == dom_template:
                continue
            am_doc_root = am_manifest_dom.documentElement
            am_rspec_node = None
            if am_doc_root.nodeType == Node.ELEMENT_NODE and \
                    am_doc_root.localName == defs.RSPEC_TAG:
                am_rspec_node = am_doc_root
            else:
                for child in am_doc_root.childNodes:
                    if child.nodeType == Node.ELEMENT_NODE and \
                            child.localName == defs.RSPEC_TAG:
                        am_rspec_node = child
                        break
            if am_rspec_node is None:
                self.logger.debug("Couldn't find %s rspec node!", am)
                continue
            for child in am_rspec_node.childNodes:
                if child.localName in (defs.NODE_TAG, defs.LINK_TAG, defs.STITCHING_TAG):
                    continue
                try:
                    cstr = child.toxml(encoding="utf-8")
                    if cstr:
                        cstr = cstr.strip()
                except Exception, xe:
                    self.logger.debug("Failed to XMLify top level child '%s' - skipping: %s", child.nodeName, xe)
                    cstr = ""
                if cstr == "":
                    continue
                self.logger.debug("%s manifest had new top level element: '%s'...", am, cstr[:min(len(cstr), 60)])
                if cstr not in template_kids:
                    rspec_node.appendChild(child)
                    self.logger.debug("... appended it")

    def combineNSes(self, ams_list, dom_template):
        # Ensure all the top-level rspec element attributes are combined. 
        # Specifically doing this to ensure we get all xmlns:* attributes

        doc_root = dom_template.documentElement
        children = doc_root.childNodes
        # Find all the client_ids for nodes in the template too
        rspec_node = None
        if doc_root.nodeType == Node.ELEMENT_NODE and \
                doc_root.localName == defs.RSPEC_TAG:
            rspec_node = doc_root
        else:
            for child in children:
                if child.nodeType == Node.ELEMENT_NODE and \
                        child.localName == defs.RSPEC_TAG:
                    rspec_node = child
                    break
        if rspec_node is None:
            self.logger.debug("Couldn't find rspec in template!")
            return
        for am in ams_list:
            if self.useReqs:
                if not am.requestDom:
                    am.requestDom = am.getEditedRSpecDom(dom_template)
                am_manifest_dom = am.requestDom
            else:
                am_manifest_dom = am.manifestDom
            if am_manifest_dom == dom_template:
                continue
            am_doc_root = am_manifest_dom.documentElement
            am_rspec_node = None
            if am_doc_root.nodeType == Node.ELEMENT_NODE and \
                    am_doc_root.localName == defs.RSPEC_TAG:
                am_rspec_node = am_doc_root
            else:
                for child in am_doc_root.childNodes:
                    if child.nodeType == Node.ELEMENT_NODE and \
                            child.localName == defs.RSPEC_TAG:
                        am_rspec_node = child
                        break
            if am_rspec_node is None:
                self.logger.debug("Couldn't find %s rspec node!", am)
                continue
            attrCnt = am_rspec_node.attributes.length
            self.logger.debug("%s rspec tag has %d attributes", am, attrCnt)
            if attrCnt == 0:
                continue
            for i in range(attrCnt):
                attr = am_rspec_node.attributes.item(i)
                #self.logger.debug("AM Attr %d is '%s'='%s'", i, attr.name, attr.value)
                matchingRAName = None
                if rspec_node.hasAttribute(attr.name):
                    matchingRAName = attr.name
#                    self.logger.debug("Template had attr with exact same name")
                else:
                    racnt = rspec_node.attributes.length
                    for j in range(racnt):
                        ra = rspec_node.attributes.item(j)
                        if ra.localName == attr.localName:
                            self.logger.debug("%s has attribute '%s' whose localName matches template attribute '%s'", am, attr.name, ra.name)
                            matchingRAName = ra.name
                            break
                if matchingRAName is not None:
                    #self.logger.debug("Template already had attr %s. Had val %s (%s had val %s)", matchingRAName, rspec_node.getAttribute(matchingRAName), am, attr.value)
                    if str(rspec_node.getAttribute(matchingRAName)) == str(attr.value):
#                        self.logger.debug("Template had attr with same name as %s: '%s'. And same value: '%s'", am, attr.name, attr.value)
                        continue
                    if "schemaLocation" == str(attr.localName):
                        # Split both old and new by space
                        oldVals = rspec_node.getAttribute(matchingRAName).split()
                        newVals = attr.value.split()
                        toAdd = []
                        for val in newVals:
                            if val in oldVals:
                                continue
                            toAdd.append(val)
                        for val in toAdd:
                            oldVals.append(val)
                        newSL = " ".join(oldVals)
                        self.logger.debug("'%s' was '%s'. AM had '%s'. Setting SL to '%s'", matchingRAName, rspec_node.getAttribute(matchingRAName), attr.value, newSL)
                        rspec_node.setAttribute(matchingRAName, newSL)
                    continue
                self.logger.debug("Adding to Template attr '%s' (val '%s') from %s", attr.name, attr.value, am)
                rspec_node.setAttribute(attr.name, attr.value)

    def combineNodes(self, ams_list, dom_template):
        '''Replace the 'node' section of the dom_template with 
        the corresponding node from the manifest of the Aggregate with a matching 
        component_manager URN'''

        # FIXME: Ticket #712: Look at the auth in the sliver_id
        # To see whose node this is, not component_manager_id.
        # That better handles the ExoSM where the compnent_manager_id
        # will be for a sub-AM / rack, but auth in the sliver_id
        # will be the ExoSM.
        # This also works now because I filled in all those URNs in am.urn_syns

        # Set up a dictionary mapping node by component_manager_id
        template_nodes_by_cmid={}
        template_node_cids=[]
        doc_root = dom_template.documentElement
        children = doc_root.childNodes
        # Find all the client_ids for nodes in the template too
        for child in children:
            if child.nodeType == Node.ELEMENT_NODE and \
                    child.localName == defs.NODE_TAG:
                cmid = child.getAttribute(COMPONENT_MGR_ID)
                if not template_nodes_by_cmid.has_key(cmid):
                    template_nodes_by_cmid[cmid] = []
                template_nodes_by_cmid[cmid].append(child)
                cid = child.getAttribute(CLIENT_ID)
                key = cid + cmid
                if not key in template_node_cids:
                    template_node_cids.append(key)

#        print "DICT = " + str(template_nodes_by_cmid)
        
        # Replace a node when we find the matching manifest
        # Match the manifest from a given AMs manifest if that AM's urn is the 
        # component_manager_id attribute on that node and the client_ids match
        for am in ams_list:
            if self.useReqs:
                if not am.requestDom:
                    am.requestDom = am.getEditedRSpecDom(dom_template)
                am_manifest_dom = am.requestDom
            else:
                am_manifest_dom = am.manifestDom
            am_doc_root = am_manifest_dom.documentElement

            # For each node in this AMs manifest for which this AM
            # is the component manager, if that client_id
            # was not in the template, then append this node
            for child in am_doc_root.childNodes:
                if child.nodeType == Node.ELEMENT_NODE and \
                        child.localName == defs.NODE_TAG:
                    cid = child.getAttribute(CLIENT_ID)
                    cmid = child.getAttribute(COMPONENT_MGR_ID)
                    key = cid + cmid
                    if not key in template_node_cids and cmid in am.urn_syns:
                        doc_root.appendChild(child)
            # Now do the node replacing as necessary
            for urn in am.urn_syns:
                if template_nodes_by_cmid.has_key(urn):
                    for template_node in template_nodes_by_cmid[urn]:
                        template_client_id = template_node.getAttribute(CLIENT_ID)
                        for child in am_doc_root.childNodes:
                            if child.nodeType == Node.ELEMENT_NODE and \
                                    child.localName == defs.NODE_TAG:
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
        # Collect the link client_ids in the template
        template_link_cids=[]
        for child in children:
            if child.nodeType == Node.ELEMENT_NODE and \
                    child.localName == defs.LINK_TAG:
                link = child
                # Get first 'component_manager' child element
#                print "LINK = " + str(link) + " " + cmid
                client_id = str(link.getAttribute(CLIENT_ID))
                template_link_cids.append(client_id)

        # loop over AMs. If an AM has a link client_id not in template_link_ids
        # and the link has that AM as a component_manager, then append this link to the template
        for agg in ams_list:
            if self.useReqs:
                if not agg.requestDom:
                    agg.requestDom = agg.getEditedRSpecDom(dom_template)
                man = agg.requestDom
            else:
                man = agg.manifestDom
            man_root = man.documentElement
            man_kids = man_root.childNodes
            for link2 in man_kids:
                if link2.nodeType != Node.ELEMENT_NODE or \
                        link2.localName != defs.LINK_TAG:
                    continue
                cid = link2.getAttribute(CLIENT_ID)
                # If the manifest has this link, then we're good
                if cid in template_link_cids:
                    continue

                # FIXME: If the link lists an interface_ref that points to a node that
                # belongs to this AM, then we should also treat this as myLink
                # In this case this is OK cause stitcher forces the link to list all
                # the component_managers
                myLink = False
                for cme in link.childNodes:
                    if cme.nodeType != Node.ELEMENT_NODE or cme.localName != COMP_MGR:
                        continue
                    cmid = str(cme.getAttribute(COMP_MGR_NAME))
                    if cmid in agg.urn_syns:
                        myLink = True
                        break
                if myLink:
#                    self.logger.debug("Adding link %s (%s)", cid, link2.toxml(encoding="utf-8"))
                    doc_root.appendChild(link2)
                    template_link_cids.append(cid)

        # Now go through the links in the template, swapping in info from the appropriate manifest RSpecs
        children = doc_root.childNodes
        for child in children:
            if child.nodeType == Node.ELEMENT_NODE and \
                    child.localName == defs.LINK_TAG:
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
                cms = []
                for cme in link.childNodes:
                    if cme.nodeType != Node.ELEMENT_NODE or cme.localName != COMP_MGR:
                        continue
                    cms.append(str(cme.getAttribute(COMP_MGR_NAME)))
#                self.logger.debug("Ams in Link %s: %s", client_id, cms)

                # Get interface_ref elements that need to be swapped
                intfs = {} # Hash by interface_ref client_id of iref elements to swap
                for intf in link.childNodes:
                    if intf.nodeType != Node.ELEMENT_NODE or intf.localName != INTFC_REF:
                        continue
                    if not intf.hasAttribute(SLIVER_ID) and not intf.hasAttribute(COMP_ID):
                        intfs[str(intf.getAttribute(CLIENT_ID))] = intf
#                        self.logger.debug("intfc_ref %s has no sliver_id or component_id", intf.getAttribute(CLIENT_ID))
#                    else:
#                        sid = None
#                        cid = None
#                        if intf.hasAttribute(COMP_ID):
#                            cid = intf.getAttribute(COMP_ID)
#                        if intf.hasAttribute(SLIVER_ID):
#                            sid = intf.getAttribute(SLIVER_ID)
#                        self.logger.debug("intfc_ref %s has sliver_id %s, component_id %s", intf.getAttribute(CLIENT_ID), sid, cid)

#                self.logger.debug("Interfaces we need to swap: %s", intfs)

                # If this is a manifest link and all irefs have
                # manifest info, then this link is done. Move on.
                # FIXME: This means we do not add the link sliver_id
                # & VLAN tag from other AMs on this link.
                if len(intfs) == 0 and not needSwap:
                    continue

                for agg in ams_list:
                    # If this is a manifest link and all irefs have
                    # manifest info, then this link is done. Move on.
                    # FIXME: This means we do not add the link sliver_id
                    # & VLAN tag from other AMs on this link.
                    if len(intfs) == 0 and not needSwap:
                        break

                    notIn = True # Is the AM involved in this link?
                    for urn in agg.urn_syns:
                        if urn in cms:
                            notIn = False
                            break
                    if notIn:
                        # Not a relevant aggregate
#                        self.logger.debug("Skipping AM %s not involved in link %s", agg.urn, client_id)
                        continue
#                    else:
#                        self.logger.debug("Looking at AM %s for link %s", agg.urn, client_id)

                    if self.useReqs:
                        if not agg.requestDom:
                            agg.requestDom = agg.getEditedRSpecDom(dom_template)
                        man = agg.requestDom
                    else:
                        man = agg.manifestDom
                    for link2 in man.documentElement.childNodes:
                        if link2.nodeType != Node.ELEMENT_NODE or \
                                link2.localName != defs.LINK_TAG:
                            continue
                        # If this is a manifest link and all irefs have
                        # manifest info, then this link is done. Move on.
                        # FIXME: This means we do not add the link sliver_id
                        # & VLAN tag from other AMs on this link.
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
                                            if intf2.nodeType == Node.ELEMENT_NODE and \
                                                    intf2.localName == INTFC_REF and \
                                                    str(intf2.getAttribute(CLIENT_ID)) == str(intf.getAttribute(CLIENT_ID)) and \
                                                    (not intf2.hasAttribute(SLIVER_ID) and not intf2.hasAttribute(COMP_ID)):
#                                                self.logger.debug("from old template saving iref %s", intf2.getAttribute(CLIENT_ID))
                                                link2.replaceChild(intf, intf2)
                                                break

                                # Need to recreate intfs dict
                                # Get interface_ref elements that need to be swapped
                                intfs = {}
                                for intf in link2.childNodes:
                                    if intf.nodeType != Node.ELEMENT_NODE or intf.localName != INTFC_REF:
                                        continue
                                    if not intf.hasAttribute(SLIVER_ID) and not intf.hasAttribute(COMP_ID):
                                        intfs[str(intf.getAttribute(CLIENT_ID))] = intf
#                                        self.logger.debug("intfc_ref %s has no sliver_id or component_id", intf.getAttribute(CLIENT_ID))
#                                    else:
#                                        sid = None
#                                        cid = None
#                                        if intf.hasAttribute(COMP_ID):
#                                            cid = intf.getAttribute(COMP_ID)
#                                        if intf.hasAttribute(SLIVER_ID):
#                                            sid = intf.getAttribute(SLIVER_ID)
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
                            # End of block to do swap of link

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
                            # Note we don't get here always - see
                            # FIXMEs above
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
            if am.dcn:
                self.logger.debug("Pulling hops from a DCN AM: %s", am)

            if self.useReqs:
                if not am.requestDom:
                    am.requestDom = am.getEditedRSpecDom(dom_template)
                am_manifest_dom = am.requestDom
            else:
                am_manifest_dom = am.manifestDom
            if am_manifest_dom == dom_template:
                self.logger.debug("AM %s's manifest is the dom_template- no need to do combineHops here.", am)
                continue

            # FIXME: Should this be am._hops or is am.hops OK as is?
            # In my testing, everything in _hops is in .hops
            for hop in am.hops:
                self.logger.debug("computeHops: replacing hop %s from am.hops", hop)
                hop_id = hop._id
                path_id = hop.path.id
                if hop_id is None:
                    self.logger.error("%s had am.hops entry with no ID: %s", am, hop)
                    continue
                if path_id is None:
                    self.logger.error("%s had am.hops entry %s with a path that has no ID: %s", am, hop, hop.path)
                    continue
                template_path = self.findPathByID(template_stitching, path_id)
                if template_path is None:
                    self.logger.error("Cannot find path %s in template manifest", path_id)
                    continue
                #self.logger.debug("Found path %s in template manifest: %s", path_id, template_path.toxml(encoding="utf-8"))
                #                print "AGG " + str(am) + " HID " + str(hop_id)
                if not am.isEG:
                    self.replaceHopElement(template_path, self.getStitchingElement(am_manifest_dom), hop_id, path_id)
#                    for child in template_path.childNodes:
#                        if child.nodeType == Node.ELEMENT_NODE and \
#                                child.localName == HOP and \
#                                child.getAttribute(HOP_ID) == hop_id:
#                            self.logger.debug("After replaceHopElem template_path has hop %s", child.toprettyxml(encoding="utf-8"))
                else:
                    self.logger.debug("Had EG AM in combineHops: %s", am)
                    link_id = hop._hop_link.urn
                    self.replaceHopLinkElement(template_path, self.getStitchingElement(am_manifest_dom), hop_id, path_id, link_id)
#            self.logger.debug("After swapping hops for %s, stitching extension is %s", am, stripBlankLines(template_stitching.toprettyxml(encoding="utf-8")))

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
                comment_text = comment_text + "\n\n"
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
        hops_info = []
        for hop in am._hops:
            if self.useReqs:
                tEntry = {'urn':hop._hop_link.urn, 'vlan_tag':str(hop._hop_link.vlan_suggested_request), 'vlan_range':str(hop._hop_link.vlan_range_request), 'path_id':hop.path.id, 'id':hop._id}
            else:
                tEntry = {'urn':hop._hop_link.urn, 'vlan_tag':str(hop._hop_link.vlan_suggested_manifest), 'path_id':hop.path.id, 'id':hop._id}
            if hop.globalId:
                tEntry['path_global_id'] = hop.globalId
            if hop._hop_link.ofAMUrl:
                tEntry['ofAMUrl'] = hop._hop_link.ofAMUrl
            if hop._hop_link.controllerUrl:
                tEntry['controllerUrl'] = hop._hop_link.controllerUrl
            hops_info.append(tEntry)
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
        if template_hop is None:
            self.logger.error("Cannot find hop %s in template manifest path %s", hop_id, path_id)
            return

        # Find the path for the given path_id (there may be more than one)
        am_path = self.findPathByID(am_stitching, path_id)

        am_hop = None
        if am_path is not None:
            for child in am_path.childNodes:
                if child.nodeType == Node.ELEMENT_NODE and \
                        child.localName == HOP and \
                        child.getAttribute(HOP_ID) == hop_id:
                    am_hop = child
                    break
        else:
            self.logger.error("Cannot find path %s in AM's stitching extension", path_id)
            return

        if am_hop is not None and template_hop is not None:
#            self.logger.debug("Replacing " + template_hop.toxml(encoding="utf-8") + " with " + am_hop.toxml(encoding="utf-8"))
            template_path.replaceChild(am_hop, template_hop)
        else:
            self.logger.error ("Can't replace hop %s from path %s in template: AM HOP %s TEMPLATE HOP %s" % (hop_id, path_id, am_hop, template_hop))
            return

    # Replace the hop link element in the template DOM with the hop link element 
    # from the aggregate DOM that has the given HOP LINK ID
    # For use with EG AMs
    def replaceHopLinkElement(self, template_path, am_stitching, template_hop_id, path_id, link_id):
        template_link = None
        template_hop = None

        for child in template_path.childNodes:
            if child.nodeType == Node.ELEMENT_NODE and \
                    child.localName == HOP and \
                    child.getAttribute(HOP_ID) == template_hop_id:
                template_hop = child
                for child2 in child.childNodes:
                    if child2.nodeType == Node.ELEMENT_NODE and \
                            child2.localName == LINK:
                        template_link = child2
                        break
                if template_link is None:
                    self.logger.warn("Did not find stitching hop %s's link in template manifest RSpec for path %s", template_hop_id, path_id)
                    return
                break
        if template_hop is None:
            self.logger.warn("Did not find stitching hop %s in template manifest RSpec for path %s", template_hop_id, path_id)
            return

        # Find the path for the given path_id (there may be more than one)
        am_path = self.findPathByID(am_stitching, path_id)

        am_link = None
        if am_path is not None:
            for child in am_path.childNodes:
                if child.nodeType == Node.ELEMENT_NODE and \
                        child.localName == HOP:
                    for child2 in child.childNodes:
                        if child2.nodeType == Node.ELEMENT_NODE and \
                                child2.localName == LINK and \
                                child2.getAttribute(LINK_ID) == link_id:
                            am_link = child2
                            break
            if am_link is None:
                self.logger.debug("Did not find HopLink %s in AM's Man RSpec, though found AM's path %s (usually harmless; happens 2+ times for ExoGENI aggregates)", link_id, path_id)
                return
        else:
            self.logger.warn("Did not find path %s in AM's Man RSpec to replace HopLink %s", path_id, link_id)

        if am_link is not None and template_link is not None and template_hop is not None:
#            self.logger.debug("Replacing " + template_link.toxml(encoding="utf-8") + " with " + am_link.toxml(encoding="utf-8"))
            template_hop.replaceChild(am_link, template_link)
        else:
            # This error happens at EG AMs and is harmless. See ticket #321
#            self.logger.debug("Can't replace hop link %s in path %s in template: AM HOP LINK %s; TEMPLATE HOP %s; TEMPLATE HOP LINK %s" % (link_id, path_id, am_link, template_hop, template_link))
            pass

    def findPathByID(self, stitching, path_id):
        path = None
        for child in stitching.childNodes:
            if child.nodeType == Node.ELEMENT_NODE and \
                    child.localName == defs.PATH_TAG and \
                    child.getAttribute(PATH_ID) == path_id:
                path = child
                break
        return path

    def getStitchingElement(self, manifest_dom):
        rspec_node = None
        for child in manifest_dom.childNodes:
            if child.nodeType == Node.ELEMENT_NODE and \
                    child.localName == defs.RSPEC_TAG:
                rspec_node = child
                break
        if rspec_node:
            for child in rspec_node.childNodes:
                if child.nodeType == Node.ELEMENT_NODE and \
                        child.localName == defs.STITCHING_TAG:
                    return child
        return None

def combineManifestRSpecs(ams_list, dom_template, useReqs=False):
    '''Combine the manifests from the given Aggregate objects into the given DOM template (a manifest). Return a DOM'''
    mrc = ManifestRSpecCombiner(useReqs)
    return mrc.combine(ams_list, dom_template)

