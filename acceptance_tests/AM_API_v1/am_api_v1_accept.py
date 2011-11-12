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
""" Acceptance tests for AM API."""

import copy as docopy
import unittest
import omni_unittest as ut
import pprint

################################################################################
#
# Test scripts which test AM API calls on a CH where the running user
# has permission to create slices.  This script is built on the unittest module.
#
# Purpose of the tests is to determine that AM API is functioning properly.
#
# To run all tests:
# ./am_api_accept.py
#
# To run a single test:
# ./am_api_accept.py Test.test_getversion
#
# To add a new test:
# Create a new method with a name starting with 'test_".  It will
# automatically be run when am_api_accept.py is called.
#
################################################################################

# This is the acceptance test for AM API version 1
API_VERSION = 1

class Test(ut.OmniUnittest):
    """Acceptance tests for GENI AM API v1."""
    def test_getversion(self):
        """Passes if a 'getversion' call at each aggregate returns an XMLRPC struct with 'geni_api' field set to API_VERSION.""" 

        self.section_break()
        options = docopy.deepcopy(self.options)
        # now modify options for this test as desired

        # now construct args
        omniargs = ["getversion"]
        (text, ret_dict) = self.call(omniargs, options)

        success_fail = True
        msg = "All aggregates returned a geni_api version of %s" % (str(API_VERSION))
        if type(ret_dict) == type({}):
            # loop through each aggregate
            for (agg, ver_dict) in ret_dict.items():
                if ver_dict is not None: 
                    if ver_dict.has_key('geni_api'):
                        # Fails if any aggs return geni_api != API_VERSION
                        if str(ver_dict['geni_api']) != str(API_VERSION):
                            msg = 'geni_api version returned "%s" not "%s" as expected from aggregate "%s"' % ( str(ver_dict['geni_api']), str(API_VERSION), agg)
                            success_fail = False
                            break
                    else:
                        pprinter = pprint.PrettyPrinter(indent=4)
                        msg = "No geni_api version listed in 'getversion' return from aggregate '%s': \n%s" % (agg, pprinter.pformat(ver_dict))
                        success_fail = False
                        break
                else:
                    pprinter = pprint.PrettyPrinter(indent=4)
                    msg = '"getversion" fails to return an XMLRPC struct from aggregate "%s": \n%s' % (agg, pprinter.pformat(ver_dict))
                    success_fail = False
                    break
        else:
            # To end up here, means something went wrong in Omni
            pprinter = pprint.PrettyPrinter(indent=4)
            msg = 'Failure. Returned: \n%s' % (pprinter.pformat(ret_dict))
            success_fail = False

#        self.print_monitoring( success_fail )
        self.assertTrue(success_fail, msg)



if __name__ == '__main__':
    # Include default Omni command line options
    # Support unittest option by replacing -v and -q with --vv a --qq
    Test.unittest_parser()

    # Invoke unit tests as usual
    unittest.main()


