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

import xml.parsers.expat

def is_wellformed_xml( string ):
    # Try to parse the XML code.
    # If it fails to parse, then it is not well-formed
    # 
    # Definition of well-formed is here:
    # http://www.w3.org/TR/2008/REC-xml-20081126/#sec-well-formed
    parser = xml.parsers.expat.ParserCreate()
    retVal = True
    try: 
        parser.Parse( string )
    except Exception:
        # Parsing failed
        print Exception
        retVal= False
    return retVal

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
<rspec></rspec>"""

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

        print is_wellformed_xml( test_str )

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
