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
import unittest
import omni_unittest as ut
import pprint

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
    def test_getversion(self):
        """Passes if a 'GetVersion' returns an XMLRPC struct containing 'geni_api = 1'.
        """
        # Do AM API call
        options = docopy.deepcopy(self.options)
        omniargs = ["getversion"]
        (text, ret_dict) = self.call(omniargs, options)

        pprinter = pprint.PrettyPrinter(indent=4)
        # If this isn't a dictionary, something has gone wrong in Omni.  
        ## In python 2.7: assertIs
        self.assertTrue(type(ret_dict) is dict,
                      '"getversion" returned: \n%s' % (pprinter.pformat(ret_dict)))
        # An empty dict indicates a misconfiguration!
        self.assertTrue(len(ret_dict.keys()) > 0,
                      '"getversion" returned empty dictionary which indicates ' \
                      'there were no aggregates checked.  ' \
                      'Look for misconfiguration.')

        # Checks each aggregate
        for (agg, ver_dict) in ret_dict.items():
            self.assertTrue(type(ver_dict) is dict,
                          '"getversion" fails to return expected XML-RPC struct ' \
                          'from aggregate "%s". Returned: %s' % 
                          (agg, pprinter.pformat(ver_dict)))
            self.assertTrue(len(ver_dict.keys()) > 0,
                            '"getversion" returned an empty XML-RPC struct ' \
                            'from aggregate "%s".' % (agg))
            ## In python 2.7: assertIn
            self.assertTrue('geni_api' in ver_dict,
                            "No geni_api included in 'getversion' returned " \
                            "from aggregate '%s': \n%s" % 
                            (agg, pprinter.pformat(ver_dict)))
            value = ver_dict['geni_api']
            self.assertTrue(type(value) is int,
                            'Received %r but expected "geni_api" to be int ' \
                            'in "getversion" returned from aggregate "%s"' % 
                            (type(value), agg))
            self.assertEqual(value, API_VERSION,
                           'Received "geni_api=%d" but expected "geni_api=%d" ' \
                            'in "getversion" returned from aggregate %s' % (
                            API_VERSION, value, agg))

if __name__ == '__main__':
    # Include default Omni command line options
    # Support unittest option by replacing -v and -q with --vv a --qq
    Test.unittest_parser()

    # Invoke unit tests as usual
    unittest.main()


