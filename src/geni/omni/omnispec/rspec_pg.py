#----------------------------------------------------------------------
# Copyright (c) 2010 Raytheon BBN Technologies
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

import code
import logging
import xml.etree.ElementTree as ET
from .omnispec import OmniSpec, OmniResource

def can_translate(urn, rspec):
    """Determine if I can translate the given rspec from the aggregate
    manager with the given URN.
     
    Returns True if it can be translated, False otherwise.
    
    """
    logger = logging.getLogger('omni.omnispec.rspec.pg')
    logger.debug('urn = %r', urn)
    # The URN is not sufficiently distinguished so we have to look at
    # the rspec itself. We should really parse it and pull some
    # information out of the 'rspec' tag. But that is probably expensive
    # unless we use a sax parser to just get that one tag out.
    #
    # For now, do a simple string match.
    return 'http://www.protogeni.net/resources' in rspec

def pg_tag(tag):
    # The elementtree parser throws away namespace declarations.
    # Hardcoded for now, but...
    # TODO: use a different xml parser or some other way of preserving xmlns
    return '{http://www.protogeni.net/resources/rspec/0.1}' + tag

def add_nodes(ospec, root):
    for res in root.findall(pg_tag('node')):
        name = res.attrib['component_name']
        description = 'ProtoGENI Node'
        type = 'node'
        omni_res = OmniResource(name, description, type)
        
        available = res.find(pg_tag('available')).text.lower() == 'true'
        omni_res.set_allocated(not(available))
        omni_res['orig_xml'] = ET.tostring(res)
        id = res.attrib['component_uuid']
        ospec.add_resource(id, omni_res)
        
def add_links(ospec, root):
    for res in root.findall(pg_tag('link')):
        name = res.attrib['component_name']
        description = 'ProtoGENI Link'
        type = 'link'
        omni_res = OmniResource(name, description, type)
        
        # Links appear to be always available
        available = True
        omni_res.set_allocated(not(available))
        omni_res['orig_xml'] = ET.tostring(res)
        id = res.attrib['component_uuid']
        ospec.add_resource(id, omni_res)

def rspec_to_omnispec(urn, rspec):
    ospec = OmniSpec("rspec_pg", urn)
    doc = ET.fromstring(rspec)
    add_nodes(ospec, doc)
    add_links(ospec, doc)
    return ospec

def add_node(root, onode):
    root.append(ET.fromstring(onode['orig_xml']))

def add_link(root, olink):
    root.append(ET.fromstring(olink['orig_xml']))

def omnispec_to_rspec(omnispec, filter_allocated):
    # Convert it to XML
    root = ET.Element('rspec')
    for id, r in omnispec.get_resources().items():
        if filter_allocated and not r.get_allocate():
            continue
        res_type = r.get_type()
        if res_type == 'node':
            add_node(root, r)
        elif res_type == 'link':
            add_link(root, r)
        else:
            raise(Exception('Unknown resource type ' + res_type))

    return ET.tostring(root)
    