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
'''Parse an RSpec that might have a stitching extension, 
for use in driving stitchign reservations and selecting VLANs'''

import logging
import sys
from xml.dom.minidom import parseString, getDOMImplementation

from objects import *
from utils import StitchingError

# XML tag constants
RSPEC_TAG = 'rspec'
LINK_TAG = 'link'
NODE_TAG = 'node'
STITCHING_TAG = 'stitching'
PATH_TAG = 'path'
STITCH_SCHEMA_V1 = 'http://hpn.east.isi.edu/rspec/ext/stitch/0.1/'
GENI_SCHEMA_V3 = 'http://www.geni.net/resources/rspec/3'

# This should go away, its value is no longer used
LAST_UPDATE_TIME_TAG = "lastUpdateTime"

class RSpecParser:

    def __init__(self, logger=None):
        self.logger = logger if logger else logging.getLogger('stitch')

    def parse(self, data):
        try:
            dom = parseString(data)
        except Exception, e:
            self.logger.error("Failed to parse rspec: %s", e)
            raise StitchingError("Failed to parse rspec: %s" % e)
        rspecs = dom.getElementsByTagName(RSPEC_TAG)
        if len(rspecs) != 1:
            raise StitchingError("Expected 1 rspec tag, got %d" % (len(rspecs)))
        rspec = self.parseRSpec(rspecs[0])
        rspec.dom = dom
        return rspec

    def parseRSpec(self, rspec_element):
        # FIXME: Here we use localName, ignoring the namespace. What's the right thing?
        if rspec_element.localName != RSPEC_TAG:
            msg = "parseRSpec got unexpected tag %s" % (rspec_element.tagName)
            raise StitchingError(msg)
        links = []
        nodes = []
        stitching = None
        for child in rspec_element.childNodes:
            if child.localName == LINK_TAG:
                self.logger.debug("Parsing Link")
                link = Link.fromDOM(child)
                links.append(link)
            elif child.localName == NODE_TAG:
                self.logger.debug("Parsing Node")
                nodes.append(Node.fromDOM(child))
            elif child.localName == STITCHING_TAG:
                self.logger.debug("Parsing Stitching")
                stitching = self.parseStitching(child)
            else:
                self.logger.debug("Skipping '%s' node", child.nodeName)
        rspec = RSpec(stitching)
        rspec.links = links
        rspec.nodes = nodes

        # Fill in a list of distinct AM URNs in this RSpec
        for node in nodes:
            rspec.amURNs.add(node.amURN)
        for link in links:
            for am in link.aggregates:
                rspec.amURNs.add(am.urn)
        # Workflow parser ensures Aggs implied by the stitching extension are included

        return rspec

    def parseStitching(self, stitching_element):
        '''Parse the stitching element of an RSpec'''
        # FIXME: Do we need getAttributeNS?
        last_update_time = stitching_element.getAttribute(LAST_UPDATE_TIME_TAG)
        paths = []
        for child in stitching_element.childNodes:
            if child.localName == PATH_TAG:
                path = Path.fromDOM(child)
                paths.append(path)
        stitching = Stitching(last_update_time, paths)
        return stitching

if __name__ == "__main__":
    if len(sys.argv) <= 1:
        print "Usage RspecParser <file.xml> [<out.xml>]"
        sys.exit()

    filename = sys.argv[1]
    print "FN = " + filename
    file = open(filename, 'r')
    data = file.read()
    file.close()
    parser = RSpecParser(verbose=True)
    rspec = parser.parse(data)
    print "== RSPEC =="
    print "\t== NODES =="
    print rspec.nodes
    print "\t== LINKS =="
    print rspec.links
    cnt = 1
    for node in rspec.nodes:
        print "\t\t== NODE %s ==" % (str(cnt))
        cnt +=1
        print node
        cnt2 = 1
        for interface in node.interfaces:
            print "\t\t\t== INTERFACE %s ==" % (str(cnt2))
            cnt2 +=1
            print interface
    cnt = 1
    for link in rspec.links:
        print "\t\t== LINK %s ==" % (str(cnt))
        cnt +=1
        print link
    print "\t== STITCHING == " 
    print rspec.stitching
    cnt = 1
    for hop in rspec.stitching.path.hops:
        print "\t\t== HOP %s ==" % (str(cnt))
        cnt +=1
        print hop

# Now convert back to XML and print out
    impl = getDOMImplementation()
    doc = impl.createDocument(None, 'rspec', None)
    root = doc.documentElement
    rspec.toXML(doc, root)
    if len(sys.argv) > 2:
        outf = open(sys.argv[2], "w")
        doc.writexml(outf)
        outf.close()
    else:
        print doc.toprettyxml()
