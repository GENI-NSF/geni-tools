#!/usr/bin/env python

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
""" Acceptance tests for AM API v1, v2, and v3."""

import copy
import datetime
import dateutil.parser
import json
import os
import pprint
import re
import sys
import time
import tempfile
import unittest
import xml.etree.ElementTree as etree 

from gcf.geni.util import rspec_util 
from gcf.geni.util.rspec_schema import *
from gcf.geni.util import urn_util
from gcf.geni.util import error_util

import gcf.oscript as omni
import omni_unittest as ut
from omni_unittest import NotSuccessError, NotDictAssertionError, NotNoneAssertionError
from omni_unittest import NotXMLAssertionError, NoResourcesAssertionError, WrongRspecType
from gcf.omnilib.util import OmniError, NoSliceCredError, RefusedError, AMAPIError
import gcf.omnilib.util.json_encoding as json_encoding
import gcf.omnilib.util.credparsing as credparsing

import am_api_accept as accept

# Works at PLC
PGV2_RSPEC_NAME = "ProtoGENI"
PGV2_RSPEC_NUM = '2'
RSPEC_NAME = "GENI"
RSPEC_NUM = '3'

TMP_DIR="."
REQ_RSPEC_FILE="request.xml"
REQ_RSPEC_FILE_1="request1.xml"
REQ_RSPEC_FILE_2="request2.xml"
REQ_RSPEC_FILE_3="request3.xml"
BAD_RSPEC_FILE="bad.xml"
SLEEP_TIME=30 # Pause between AM API calls in seconds

SUCCESS = 0
################################################################################
#
# Test AM API calls for accurate and complete functionality.
#
# This script relies on the unittest module.
#
# To run:
# am_api_accept_scaling.py -a eg-bbn -V 2 --rspec-file twoegvmsoneline.rspec --un-bound ScalingTest.test_CreateSliverWorkflow_scalingTest 
#
# To add a new test:
# Create a new method with a name starting with 'test_".  It will
# automatically be run when am_api_accept.py is called.
#
################################################################################
NUM_SLEEP = 12
MAX_TIME_TO_CREATESLIVER = 3*60 # 3 minutes
NUM_SLICES = 3 # number of slices to create
DEFAULT_SLICE_NAME = "scale" # eg scale01, scale02, etc

class ScalingTest(accept.Test):
    def test_CreateSliverWorkflow_scalingTest(self): 
        """test_CreateSliverWorkflow_ScalingTest: Do CreateSliver workflow with multiple slices"""

        self.logger.info("\n=== Test.test_CreateSliverWorkflow_scalingTest ===")
        if self.options_copy.rspeclint:
            rspec_util.rspeclint_exists()
            rspec_namespace = self.manifest_namespace
            rspec_schema = self.manifest_schema

        request = []
        numslivers = []
        manifest = []
        slivers = []
        manifest2 = []
        slicenames = []

        num_slices = self.options_copy.num_slices

        # make always --un-bound (since this test assumes that you can
        # offer the same rspec to an aggregate multiple times)
        self.options_copy.bound = False

        for i in xrange(num_slices):
            slicenames.append("")
#                slicenames[i] = self.create_slice_name()+str(i)
            slicenames[i] = self.options_copy.slice_name+str(i)

        for i in xrange(num_slices):
            # if reusing a slice name, don't create (or delete) the slice
            self.subtest_createslice( slicenames[i] )
            print "%d: CreateSlice [%s] completed..."%(i, slicenames[i])
        time.sleep(self.options_copy.sleep_time)

        # in case some slivers were left laying around from last
        # time, try to delete them now
        for i in xrange(num_slices):
            try:
                self.subtest_generic_DeleteSliver( slicenames[i] )
                time.sleep(self.options_copy.sleep_time)
            except:
                pass

        try:
            for i in xrange(num_slices):
                # Check for the existance of the Request RSpec file
#                self.assertTrue( os.path.exists(self.options_copy.rspec_file_list[i]), 
                self.assertTrue( os.path.exists(self.options_copy.rspec_file), 
                "Request RSpec file, '%s' for 'CreateSliver' call " \
                                     "expected to exist " \
                                     "but does not." 
#                                 % self.options_copy.rspec_file_list[i] )
                                 % self.options_copy.rspec_file )
#                with open(self.options_copy.rspec_file_list[i]) as f:
                with open(self.options_copy.rspec_file) as f:
                    request.append("")
                    request[i] = "".join(f.readlines())
                numslivers.append(-1)
                manifest.append("")
                slivers.append("")
#                self.options_copy.rspec_file = self.options_copy.rspec_file_list[i]
                time.sleep(self.options_copy.sleep_time)
#                # False args mean in v3+, don't do Provision or POA
#                createReturn = self.subtest_generic_CreateSliver( slicenames[i], False, False )
                sliceExpiration = self.getSliceExpiration( slicenames[i] )
                createReturn = self.subtest_generic_CreateSliver( slicenames[i], expectedExpiration=sliceExpiration )
                print "%d: CreateSliver on slice [%s] completed..."%(i, slicenames[i])
                numslivers[i], tmpManifest, slivers[i] = createReturn
                manifest[i] = "".join(tmpManifest)

                self.assertRspecType( "".join(request[i]), 'request')
                self.assertRspecType( "".join(manifest[i]), 'manifest')

                # manifest should be valid XML 
                self.assertIsXML(  manifest[i],
                   "Manifest RSpec returned by 'CreateSliver' on slice '%s' " \
                             "expected to be wellformed XML file " \
                             "but was not. Return was: " \
                             "\n%s\n" \
                             "... edited for length ..."
                         % (slicenames[i], manifest[i][:100]))

                if self.options_copy.rspeclint:
                    self.assertTrue(rspec_util.validate_rspec( manifest[i], 
                                                    namespace=rspec_namespace, 
                                                    schema=rspec_schema ),
                            "Return from 'CreateSliver' " \
                            "expected to pass rspeclint " \
                            "but did not. Return was: " \
                            "\n%s\n" \
                            "... edited for length ..."
                            % (manifest[i][:100]))


                # Make sure the Manifest returned the nodes identified
                # in the Request
                if rspec_util.has_child_node( manifest[i], self.RSpecVersion()):
                    if self.options_copy.bound:
                        self.assertCompIDsEqual( "".join(request[i]), 
                                             "".join(manifest[i]), 
                                             self.RSpecVersion(), 
                                  "Request RSpec and Manifest RSpec " \
                                  "returned by 'ListResources' on slice '%s' " \
                                  "expected to have same component_ids " \
                                  "but did not." % slicenames[i])
                    self.assertClientIDsEqual( "".join(request[i]), 
                                             "".join(manifest[i]), 
                                             self.RSpecVersion(), 
                                  "Request RSpec and Manifest RSpec " \
                                  "returned by 'ListResources' on slice '%s' " \
                                  "expected to have same client_ids " \
                                  "but did not." % slicenames[i])
                                         
                else:
                    # the top level node should have a child
                    self.assertResourcesExist( "".join(manifest[i]),
                    "Manifest RSpec returned by 'CreateSliver' on slice '%s' " \
                    "expected to NOT be empty " \
                    "but was. Return was: " \
                    "\n%s\n" 
                    % (slicenames[i], "".join(manifest[i])))

            # Separate for loop here guarantees time has passed on each AM since createsliver call
            self.subtest_SliverStatus_scaling(slicenames)

        except:
            raise
        finally:
            time.sleep(self.options_copy.sleep_time)
            for i in xrange(num_slices):
                try:
                    self.subtest_generic_DeleteSliver( slicenames[i] )
                    print "%d: DeleteSliver on slice [%s] completed..."%(i, slicenames[i])
                except:
                    pass
        self.success = True


    def subtest_SliverStatus_scaling(self, slicenames):
        num_slices = len(slicenames)
        have_slept = 0
        long_sleep = max( 5, self.options_copy.max_time / NUM_SLEEP )
        short_sleep = 30
        # before starting check if this is going to fail for unrecoverable reasons having nothing to do with being ready
        # maybe get the slice credential
        # self.subtest_generic_SliverStatus( slicename )        
        slices_to_test = set(range(num_slices))
        status_ready = {}
        while have_slept <= self.options_copy.max_time:
            tmp_slices_to_test = copy.deepcopy(slices_to_test)
            for i in tmp_slices_to_test:
                status_ready[i] = False
                try:
                    # checks geni_operational_status to see if ready
                    if self.options_copy.api_version >= 3:
                        geni_status = "geni_ready"
                    else:
                        geni_status = "ready"

                        self.subtest_generic_SliverStatus( slicenames[i], status=geni_status )
                    status_ready[i]=True 
                    slices_to_test.remove( i )
                except Exception, e:
                    self.logger.info("Waiting for SliverStatus to succeed and return status of '%s'" % geni_status)
                    self.logger.info("Exception raised: %s" % e)
                    self.logger.debug("===> Starting to sleep")
                    self.logger.debug("=== sleep %s seconds ==="%str(long_sleep))
                    time.sleep( short_sleep )
                    have_slept += short_sleep
            time.sleep( long_sleep )
            have_slept += long_sleep
            self.logger.debug("<=== Finished sleeping")
        for i in set(range(num_slices)):
            if status_ready[i]:
                print "%d: SliverStatus on slice [%s] completed with status READY"%(i, slicenames[i])
            else:
                print "%d: SliverStatus on slice [%s] completed WITHOUT status ready."%(i, slicenames[i])
                print "%d: Consider setting --max-createsliver-time value to be greater than %s seconds."%(i, self.options_copy.max_time)
        for i in set(range(num_slices)):
            self.assertTrue( status_ready[i], 
                             "SliverStatus on slice '%s' expected to be '%s' but was not" % (slicenames[i], geni_status))

    @classmethod
    def getParser( cls, parser=accept.Test.getParser(), usage=None):
        parser.add_option( "--max-createsliver-time", 
                           action="store", type='int', 
                           default = MAX_TIME_TO_CREATESLIVER,
                           dest='max_time', 
                           help="Max number of seconds will attempt to check status of a sliver before failing  [default: %default]")

        parser.add_option( "--num-slices", 
                           action="store", type='int', 
                           default=NUM_SLICES, 
                           dest='num_slices', 
                           help="Number of slices to create [default: %default]")
        parser.add_option( "--slice-name", 
                           action="store", type='string', 
                           default=DEFAULT_SLICE_NAME,
                           dest='slice_name', 
                           help="Use slice name as base of slice name [default: %default]")
        return parser

    @classmethod
    def scaling_parser( cls, parser=None, usage=None):
        if parser is None:
            parser = cls.getParser()
        argv = ScalingTest.unittest_parser(parser=parser, usage=usage)
        return argv

if __name__ == '__main__':
    usage = "\n      %s -a am-undertest" \
            "\n      Also try --vv" % sys.argv[0]
    argv = ScalingTest.scaling_parser(usage=usage)
    unittest.main()
