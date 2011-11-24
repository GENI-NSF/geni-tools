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
""" Acceptance tests for AM API v1."""

import copy as docopy
from geni.util import rspec_util 
import unittest
import omni
import omni_unittest as ut
import tempfile
import pprint
import subprocess

RSPECLINT = "rspeclint" 

# TODO: TEMPORARILY USING PGv2 because test doesn't work with any of the others
# Works at PLC
RSPEC_NAME = "ProtoGENI"
RSPEC_NUM = 2
#RSPEC_NAME = "GENI"
#RSPEC_NUM = 3

# TODO: TEMPORARILY USING PGv2 because test doesn't work with any of the others
AD_NAMESPACE = "http://www.protogeni.net/resources/rspec/2"
AD_SCHEMA = "http://www.protogeni.net/resources/rspec/2/ad.xsd"
#GENI_AD_NAMESPACE = "http://www.geni.net/resources/rspec/3"
#GENI_AD_SCHEMA = "http://www.geni.net/resources/rspec/3/ad.xsd"



################################################################################
#
# Test AM API v1 calls for accurate and complete functionality.
#
# This script relies on the unittest module.
#
# To run all tests:
# ./am_api_v1_accept.py -l ../omni_accept.conf -c <omni_config> -a <AM to test>
#
# To run a single test:
# ./am_api_v1_accept.py -l ../omni_accept.conf -c <omni_config> -a <AM to test> Test.test_getversion
#
# To add a new test:
# Create a new method with a name starting with 'test_".  It will
# automatically be run when am_api_v1_accept.py is called.
#
################################################################################

# This is the acceptance test for AM API version 1
API_VERSION = 1

class Test(ut.OmniUnittest):
    """Acceptance tests for GENI AM API v1."""



    def test_GetVersion(self):
        """Passes if a 'GetVersion' returns an XMLRPC struct containing 'geni_api = 1'.
        """
        # Do AM API call
        omniargs = ["getversion"]
        (text, ret_dict) = self.call(omniargs, self.options_copy)

        pprinter = pprint.PrettyPrinter(indent=4)
        # If this isn't a dictionary, something has gone wrong in Omni.  
        ## In python 2.7: assertIs
        self.assertTrue(type(ret_dict) is dict,
                        "Return from 'GetVersion' " \
                        "expected to contain dictionary" \
                        "but instead returned:\n %s"
                        % (pprinter.pformat(ret_dict)))
        # An empty dict indicates a misconfiguration!
        self.assertTrue(ret_dict,
                        "Return from 'GetVersion' " \
                        "expected to contain dictionary keyed by aggregates " \
                        "but instead returned empty dictionary. " \
                        "This indicates there were no aggregates checked. " \
                        "Look for misconfiguration.")
        # Checks each aggregate
        for (agg, ver_dict) in ret_dict.items():
            ## In python 2.7: assertIsNotNone
            self.assertTrue(ver_dict is not None,
                          "Return from 'GetVersion' at aggregate '%s' " \
                          "expected to be XML-RPC struct " \
                          "but instead returned None." 
                           % (agg))
            self.assertTrue(type(ver_dict) is dict,
                          "Return from 'GetVersion' at aggregate '%s' " \
                          "expected to be XML-RPC struct " \
                          "but instead returned:\n %s" 
                          % (agg, pprinter.pformat(ver_dict)))
            self.assertTrue(ver_dict,
                          "Return from 'GetVersion' at aggregate '%s' " \
                          "expected to be non-empty XML-RPC struct " \
                          "but instead returned empty XML-RPC struct." 
                           % (agg))
            ## In python 2.7: assertIn
            self.assertTrue('geni_api' in ver_dict,
                          "Return from 'GetVersion' at aggregate '%s' " \
                          "expected to include 'geni_api' " \
                          "but did not. Returned:\n %s:"  
                           % (agg, pprinter.pformat(ver_dict)))
            value = ver_dict['geni_api']
            self.assertTrue(type(value) is int,
                          "Return from 'GetVersion' at aggregate '%s' " \
                          "expected to have 'geni_api' be an integer " \
                          "but instead 'geni_api' was of type %r." 
                           % (agg, type(value)))
            self.assertEqual(value, API_VERSION,
                          "Return from 'GetVersion' at aggregate '%s' " \
                          "expected to have 'geni_api=%d' " \
                          "but instead 'geni_api=%d.'"  
                           % (agg, API_VERSION, value))

    def test_ListResources(self):
        """Passes if 'ListResources' returns an advertisement RSpec (an XML document which passes rspeclint).
        """

        # Check to see if rspeclint exists before doing the hard (and
        # slow) work of calling ListResources at the aggregate
        # TODO: Hum....better way (or place) to do this? (wrapper? rspec_util?)
        # TODO: silence this call
        try:
            cmd = [RSPECLINT]
            output = subprocess.call( cmd )
        except:
            # TODO: WHAT EXCEPTION TO RAISE HERE?
            raise Exception, "Failed to locate or run '%s'" % RSPECLINT
        
        # Do AM API call
        omniargs = ["listresources", "-t", str(RSPEC_NAME), str(RSPEC_NUM)]
        self.options_copy.omnispec = False # omni will complaining if both true
        (text, ret_dict) = self.call(omniargs, self.options_copy)

# FOR TESTING WITHOUT WAITING FOR LIST RESOURCES TO RETURN
#        print ret_dict
#        text = "This is a test"
#        ret_dict = {}
#        ret_dict[('amurn', 'http://amurl')] = "".join(open('rspec-www-emulab-net-protogeni.xml').readlines())

        pprinter = pprint.PrettyPrinter(indent=4)

        # If this isn't a dictionary, something has gone wrong in Omni.  
        ## In python 2.7: assertIs
        self.assertTrue(type(ret_dict) is dict,
                        "Return from 'ListResources' " \
                        "expected to contain dictionary " \
                        "but instead returned:\n %s"
                        % (pprinter.pformat(ret_dict)))
        # An empty dict indicates a misconfiguration!
        self.assertTrue(ret_dict,
                        "Return from 'ListResources' " \
                        "expected to contain dictionary keyed by aggregates " \
                        "but instead returned empty dictionary. " \
                        "This indicates there were no aggregates checked. " \
                        "Look for misconfiguration.")

        # Checks each aggregate
        for ((agg_name, agg_url), ad) in ret_dict.items():
            ## In python 2.7: assertIsNotNone
            self.assertTrue(ad is not None,
                          "Return from 'ListResources' at aggregate '%s' " \
                          "expected to be XML file " \
                          "but instead returned None." 
                           % (agg_name))
            self.assertTrue(type(ad) is str,
                          "Return from 'ListResources' at aggregate '%s' " \
                          "expected to be string " \
                          "but instead returned: \n" \
                          "%s\n" \
                          "... edited for length ..." 
                          % (agg_name, ad[:100]))

            # Test if file is XML and contains "<rspec" or "<resv_rspec"
            self.assertTrue(rspec_util.is_rspec_string( ad ),
                          "Return from 'ListResources' at aggregate '%s' " \
                          "expected to be XML " \
                          "but instead returned: \n" \
                          "%s\n" \
                          "... edited for length ..." 
                           % (agg_name, ad[:100]))

            
            # TO DO this should be moved to rspec_util.py
            # rspeclint must be run on a file
            with tempfile.NamedTemporaryFile() as f:
                f.write( ad )
                # TODO silence rspeclint
                # Run rspeclint "../rspec/2" "../rspec/2/ad.xsd" <rspecfile>
                cmd = [RSPECLINT, AD_NAMESPACE, AD_SCHEMA, f.name]
                f.seek(0)
                output = subprocess.call( cmd )
                self.assertEqual(output, 0, 
                                "Return from 'ListResources' at aggregate '%s' " \
                                "expected to pass rspeclint " \
                                "but did not. Return was: " \
                                "\n%s\n" \
                                "... edited for length ..."
                                % (agg_name, ad[:100]))



if __name__ == '__main__':
    import sys
    # Include default Omni command line options
    # Support unittest option by replacing -v and -q with --vv a --qq
    usage = "\n      %s -a am-undertest " \
            "\n      Also try --vv" % sys.argv[0]
    Test.unittest_parser(usage=usage)
    # Invoke unit tests as usual
    unittest.main()


