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
"""
RSpec validation utilities.
"""
import lxml.objectify
import lxml.etree as etree
import subprocess
import tempfile
import xml.parsers.expat

PG_2_NAMESPACE = "http://www.protogeni.net/resources/rspec/2"
PG_2_AD_SCHEMA = "http://www.protogeni.net/resources/rspec/2/ad.xsd"
PG_2_REQ_SCHEMA = "http://www.protogeni.net/resources/rspec/2/req.xsd"

GENI_3_NAMESPACE = "http://www.geni.net/resources/rspec/3"
GENI_3_AD_SCHEMA = "http://www.geni.net/resources/rspec/3/ad.xsd"
GENI_3_REQ_SCHEMA = "http://www.geni.net/resources/rspec/3/request.xsd"

RSPECLINT = "rspeclint" 

def is_wellformed_xml( string ):
    # Try to parse the XML code.
    # If it fails to parse, then it is not well-formed
    # 
    # Definition of well-formed is here:
    # http://www.w3.org/TR/2008/REC-xml-20081126/#sec-well-formed
    parser = xml.parsers.expat.ParserCreate()
    retVal = True
    try: 
        parser.Parse( string, 1 )
    except Exception:
        # Parsing failed
        print Exception
        retVal= False
    return retVal

# def compare_request_manifest( request, manifest ):
#     """Compare the nodes in the request and manifest to make sure they match."""
#     req = lxml.objectify.fromstring(request)    
#     print help(req)
#     man = lxml.objectify.fromstring(manifest)
    
def has_child( xml ):
    try:
        root = etree.fromstring(xml)
    except:
        return False
    # see if there are any children
    if len(list(root)) > 0:
        return True
    else:
        return False

# def has_nodes( xml, node_name="node" ):
#     print xml
#     try:
#         root = etree.fromstring(xml)
#     except:
#         return False
#     firstnode = root.find("node")
#     print firstnode
#     if firstnode is None:
#         return False
#     else:
#         return True
def xml_equal( xml1, xml2 ):
    """Compare two xml documents and determine if they are the same (return: True)."""
    # Is this guaranteed to always work?
    obj1 = lxml.objectify.fromstring(xml1.strip())
    newxml1 = etree.tostring(obj1)
    obj2 = lxml.objectify.fromstring(xml2.strip())
    newxml2 = etree.tostring(obj2)
    return newxml1 == newxml2

def rspeclint_exists():
    """Try to run 'rspeclint' to see if we can find it."""
    # TODO: Hum....better way (or place) to do this? (wrapper? rspec_util?)
    # TODO: silence this call
    try:
        cmd = [RSPECLINT]
        output = subprocess.call( cmd )
    except:
        # TODO: WHAT EXCEPTION TO RAISE HERE?
        raise Exception, "Failed to locate or run '%s'" % RSPECLINT


# add some utility functions for testing various namespaces and schemas
def validate_rspec( ad, namespace=GENI_3_NAMESPACE, schema=GENI_3_REQ_SCHEMA ):
    """Run 'rspeclint' on a file.
    ad - a string containing an RSpec
    """
    # rspeclint must be run on a file
    with tempfile.NamedTemporaryFile() as f:
        f.write( ad )
        # TODO silence rspeclint
        # Run rspeclint "../rspec/3" "../rspec/3/ad.xsd" <rspecfile>
        cmd = [RSPECLINT, namespace, schema, f.name]
        f.seek(0)
        output = subprocess.call( cmd )
        # log something?
        # "Return from 'ListResources' at aggregate '%s' " \
        #     "expected to pass rspeclint " \
        #     "but did not. "
        # % (agg_name, ad[:100]))

        # if rspeclint returns 0 then it was successful
        if output == 0:
            return True
        else: 
            return False
    
#def is_valid_rspec(): 
# Call is_rspec_string()
# Call validate_rspec()
def is_rspec_string( rspec ):
    '''Could this string be part of an XML-based rspec?
    Returns: True/False'''

    if rspec is None or not(isinstance(rspec, str)):
        return False

    # do all comparisons as lowercase
    rspec = rspec.lower()

    # (1) Check if rspec is a well-formed XML document
    if not is_wellformed_xml( rspec ):
        return False
    
    # (2) Check if rspec is a valid XML document
    #   (a) a snippet of XML starting with <rspec>, or
    #   (b) a snippet of XML starting with <resv_rspec>
    if (('<rspec' in rspec) or
        ('<resv_rspec' in rspec)): 
        return True

    # (3) TBD: Validate rspec against schema
    return False

if __name__ == "__main__":
    xml_str = """<?xml version='1.0'?>
<!--Comment-->
<rspec><node></node></rspec>"""

    rspec_comment_str = """
<!--Comment-->
<rspec></rspec>"""

    rspec_str = """
<rspec></rspec>"""

    resvrspec_comment_str = """
<!--Comment-->
<resv_rspec></resv_rspec>"""
    resvrspec_str = """
<resv_rspec></resv_rspec>"""

    none_str = None
    number = 12345
    xml_notrspec_str = """<?xml version='1.0'?>
<!--Comment-->
<foo></foo>"""
    malformed_str = """<?xml version='1.0'?>
<!--Comment-->
<rspec></rspecasdf>"""
    earlycomment_str = """<!--Comment-->
<?xml version='1.0'?>
<rspec></rspec>"""
    def test( test_str ):
        print test_str
        if is_rspec_string( test_str ):
            print "is_rspec_str() is TRUE"
        else:
            print "is_rspec_str() is FALSE"                

#        print is_wellformed_xml( test_str )

    print "===== For the following strings is_rspec_str() should be TRUE ====="
    test( xml_str )
    test( rspec_comment_str)
    test( rspec_str)
    test( resvrspec_comment_str )
    test( resvrspec_str )


    print "===== For the following strings is_rspec_str() should be FALSE ====="
    test( none_str )
    test( number )
    test( xml_notrspec_str )
    test( malformed_str )
    test( earlycomment_str )

    print "===== XML Equality test ======"
    print xml_equal(xml_str, xml_notrspec_str)
    print xml_equal(xml_str, xml_str)

    # print "===== XML Comparison test ======"
    # print compare_request_manifest(xml_str, xml_notrspec_str)
    # print compare_request_manifest(xml_str, xml_str)

    # print "===== RSpec has nodes? ======"
    # print has_nodes(xml_str)
    # print has_nodes(rspec_str)
    # print has_nodes(xml_notrspec_str)
    # print has_nodes(malformed_str)

    print "===== RSpec has child? ======"
    print has_child(xml_str)
    print has_child(rspec_str)
    print has_child(xml_notrspec_str)
    print has_child(malformed_str)
