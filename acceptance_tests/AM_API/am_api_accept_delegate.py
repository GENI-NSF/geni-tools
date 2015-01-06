#!/usr/bin/python

#----------------------------------------------------------------------
# Copyright (c) 2011-2015 Raytheon BBN Technologies
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

from gcf.geni.util import rspec_util 
import omni_unittest as ut
from omni_unittest import NotDictAssertionError, NotNoneAssertionError
from omni_unittest import NotXMLAssertionError, NoResourcesAssertionError
from gcf.omnilib.util import OmniError, NoSliceCredError
import gcf.oscript as omni

import am_api_accept as accept

import datetime
import os
import pprint
import re
import sys
import time
import tempfile
import unittest


# Works at PLC
PGV2_RSPEC_NAME = "ProtoGENI"
PGV2_RSPEC_NUM = 2
RSPEC_NAME = "GENI"
RSPEC_NUM = 3

TMP_DIR="."
REQ_RSPEC_FILE="request.xml"
BAD_RSPEC_FILE="bad.xml"
SLEEP_TIME=3
################################################################################
#
# Test AM API v1 calls for accurate and complete functionality.
#
# This script relies on the unittest module.
#
# To run test:
# ./am_api_accept.py -a <AM to test> 
#
# To add a new test:
# Create a new method with a name starting with 'test_".  It will
# automatically be run when am_api_accept.py is called.
#
################################################################################

# This is the acceptance test for AM API version 1
API_VERSION = 1


class DelegateTest(accept.Test):
    """Delegation acceptance test for GENI AM API v1."""

    def setUp( self ):
        accept.Test.setUp( self )
    def test_ListResources_delegatedSliceCred(self):
        """test_ListResources_delegatedSliceCred: Passes if 'ListResources' succeeds with a delegated slice credential. Override the default slice credential using --delegated-slicecredfile"""
        # Check if slice credential is delegated.
        xml = self.file_to_string( self.options_copy.delegated_slicecredfile )
        self.assertTrue( self.is_delegated_cred(xml), 
                       "Slice credential is not delegated " \
                       "but expected to be. " )
        slice_name = self.get_slice_name_from_cred( xml )                
        self.assertTrue( slice_name,
                       "Credential is not a slice credential " \
                       "but expected to be: \n%s\n\n<snip> " % xml[:100] )
        # Run slice credential
        self.subtest_generic_ListResources(
           slicename=slice_name,
           slicecredfile=self.options_copy.delegated_slicecredfile,
           typeOnly=True)
        self.success = True

if __name__ == '__main__':
    usage = "\n      %s -a am-undertest" \
            "\n      Also try --vv" % sys.argv[0]
    DelegateTest.accept_parser(usage=usage)

    suite = unittest.TestLoader().loadTestsFromName("am_api_accept_delegate.DelegateTest.test_ListResources_delegatedSliceCred")
    unittest.TextTestRunner().run(suite)



