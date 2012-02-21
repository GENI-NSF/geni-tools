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

import datetime
from geni.util import rspec_util 
import unittest
import omni_unittest as ut
from omni_unittest import NotDictAssertionError, NotNoneAssertionError
from omni_unittest import NotXMLAssertionError, NoResourcesAssertionError
from omnilib.util import OmniError, NoSliceCredError
import os
import pprint
import re
import sys
import time
import tempfile

import am_api_accept as accept

# TODO: TEMPORARILY USING PGv2 because test doesn't work with any of the others
# Works at PLC
PGV2_RSPEC_NAME = "ProtoGENI"
PGV2_RSPEC_NUM = 2
RSPEC_NAME = "GENI"
RSPEC_NUM = 3

# TODO: TEMPORARILY USING PGv2 because test doesn't work with any of the others
AD_NAMESPACE = "http://www.protogeni.net/resources/rspec/2"
AD_SCHEMA = "http://www.protogeni.net/resources/rspec/2/ad.xsd"
#GENI_AD_NAMESPACE = "http://www.geni.net/resources/rspec/3"
#GENI_AD_SCHEMA = "http://www.geni.net/resources/rspec/3/ad.xsd"
REQ_NAMESPACE = "http://www.protogeni.net/resources/rspec/2"
REQ_SCHEMA = "http://www.protogeni.net/resources/rspec/2/request.xsd"
#GENI_REQ_NAMESPACE = "http://www.geni.net/resources/rspec/3"
#GENI_REQ_SCHEMA = "http://www.geni.net/resources/rspec/3/request.xsd"
MANIFEST_NAMESPACE = "http://www.protogeni.net/resources/rspec/2"
MANIFEST_SCHEMA = "http://www.protogeni.net/resources/rspec/2/manifest.xsd"
#GENI_MANIFEST_NAMESPACE = "http://www.geni.net/resources/rspec/3"
#GENI_MANIFEST_SCHEMA = "http://www.geni.net/resources/rspec/3/manifest.xsd"

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


class ShutdownTest(accept.Test):
    """Shutdown acceptance test for GENI AM API v1."""

    def setUp( self ):
        accept.Test.setUp( self )
    def subtest_Shutdown(self, slicename=None):
        omniargs = ["shutdown", slicename, str(self.options_copy.rspec_file)] 
        text, (succList, failList) = self.call(omniargs, self.options_copy)
        self.assertTrue( (len(succList) >=1) and (len(failList)==0),
                        "Return from 'Shutdown' " \
                        "expected to succeed " \
                        "but did not for: %s" % ", ".join(failList) )

    def test_CreateSliverWorkflow_with_Shutdown(self, slicename=None):
        if slicename==None:
            slicename = self.create_slice_name(prefix='down')

        # if reusing a slice name, don't create (or delete) the slice
        if not self.options_copy.reuse_slice_name:
            self.subtest_createslice( slicename )
            time.sleep(self.options_copy.sleep_time)

        manifest = self.subtest_CreateSliver( slicename )
        self.assertResourcesExist( manifest, 
                       "Manifest RSpec returned by CreateSliver " \
                       "expected to contain resources but does not.")
        try:
            self.subtest_Shutdown( slicename )
        except:
            # If Shutdown fails, then DeleteSliver to clean up for next run
            self.subtest_DeleteSliver( slicename )

        if not self.options_copy.reuse_slice_name:
            self.subtest_deleteslice( slicename )

if __name__ == '__main__':
    usage = "\n      %s -a am-undertest" \
            "\n      Also try --vv" \
            "\n  WARNING: Be very careful running this test. " \
            "Administator support is likely to be needed to recover " \
                "from running this test." % sys.argv[0]
    # Include default Omni command line options
    # Support unittest option by replacing -v and -q with --vv a --qq
    # Also include acceptance test options
    argv = ShutdownTest.accept_parser(usage=usage)

    suite = unittest.TestLoader().loadTestsFromName("am_api_accept_shutdown.ShutdownTest.test_CreateSliverWorkflow_with_Shutdown")
#    suite = unittest.TestLoader().loadTestsFromName("am_api_accept_shutdown.ShutdownTest.test_GetVersion")
    unittest.TextTestRunner().run(suite)
