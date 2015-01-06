#!/usr/bin/env python

#----------------------------------------------------------------------
# Copyright (c) 2012-2015 Raytheon BBN Technologies
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

from gcf.geni.util import rspec_util 
import omni_unittest as ut
from omni_unittest import NotDictAssertionError, NotNoneAssertionError
from omni_unittest import NotXMLAssertionError, NoResourcesAssertionError
from gcf.omnilib.util import OmniError, NoSliceCredError, RefusedError, AMAPIError
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
# Tests for use with nagios.
#
# This script relies on the code in am_api_accept.py.
#
# To run test:
# ./am_api_accept_nagios.py -a TEST_AM -V 2 --reuse-slice SLICE_NAME NagiosTest.test_CreateSliver_nagios
# ./am_api_accept_nagios.py -a TEST_AM -V 2 --reuse-slice SLICE_NAME NagiosTest.test_SliverStatus_nagios
# 
# The above also works with -V 3.
#
# Run using:
#
# ./am_api_accept_nagios.py NagiosTest.test_getusercred_nagios
# Outputs file to default location used by getusercred.
#
#./am_api_accept_nagios.py NagiosTest.test_getusercred_nagios --usercredfile myusercred
#
# Outputs file as myusercred.xml.
#
#./am_api_accept_nagios.py NagiosTest.test_getusercred_nagios --usercredfile myusercred -V 3
# Outputs file as myusercred.json
#
#
################################################################################

# This is the acceptance test for AM API version 1
API_VERSION = 2

NUM_SLEEP = 12
MAX_TIME_TO_CREATESLIVER = 3*60 # 3 minutes

class NagiosTest(accept.Test):
    """Test to be used by nagios."""

    def setUp( self ):
        accept.Test.setUp( self )
        self.slicename = self.create_slice_name( prefix="nag-" )


    def test_getusercred_nagios(self):
        """test_getusercred_nagios: Passes if getting a user credential succeed.  
        Use omni option --outputfile to specify the location of where to write the user credential file."""
        self.logger.info("\n=== NagioTest.test_getusercred_nagios ===")
        self.subtest_getusercred_nagios()
        self.success = True

    def subtest_getusercred_nagios(self):
        # (1) Get the usercredential
        omniargs = ["getusercred", "-o"]
        (text, usercredstruct) = self.call(omniargs, self.options_copy)
        if self.options_copy.api_version <= 2:
            self.assertStr( usercredstruct,
                        "Return from 'getusercred' " \
                            "expected to be string " \
                            "but instead returned: %r" 
                        % (usercredstruct))
            # Test if file is XML 
            self.assertTrue(rspec_util.is_wellformed_xml( usercredstruct ),
                        "Return from 'getusercred' " \
                            "expected to be XML " \
                            "but instead returned: \n" \
                            "%s\n" \
                            "... edited for length ..." 
                        % (usercredstruct[:100]))
        else:
            geni_type, geni_version, usercred = self.assertUserCred(usercredstruct)

    def test_CreateSliver_nagios(self):
        """test_CreateSliver: Passes if the sliver creation workflow succeeds.  
        Use --rspec-file to replace the default request RSpec."""
        self.logger.info("\n=== Test.test_CreateSliver_nagios ===")
        self.subtest_CreateSliver_nagios( self.slicename )
        self.success = True

    def subtest_CreateSliver_nagios(self, slicename=None, doProvision=True, doPOA=False):
        # Check to see if 'rspeclint' can be found before doing the hard (and
        # slow) work of calling ListResources at the aggregate
        if self.options_copy.rspeclint:
            rspec_util.rspeclint_exists()
            rspec_namespace = self.manifest_namespace
            rspec_schema = self.manifest_schema
        else:
            rspec_namespace = None
            rspec_schema = None

        if slicename==None:
            slicename = self.create_slice_name()

        # if reusing a slice name, don't create (or delete) the slice
        if not self.options_copy.reuse_slice_name:
            self.subtest_createslice( slicename )
            time.sleep(self.options_copy.sleep_time)

        # cleanup up any previous failed runs
        try:
            self.subtest_generic_Delete( slicename )
            time.sleep(self.options_copy.sleep_time)
        except:
            pass

        numslivers, manifest, slivers = self.subtest_generic_CreateSliver( slicename, doProvision, doPOA )
        with open(self.options_copy.rspec_file) as f:
            req = f.readlines()
            request = "".join(req)

        try:
            self.assertRspec( "CreateSliver", manifest, 
                              rspec_namespace, rspec_schema,
                              self.options_copy.rspeclint )
            self.assertRspecType( request, 'request')
            self.assertRspecType( manifest, 'manifest')
            # Make sure the Manifest returned the nodes identified in
            # the Request
            self.assertManifestMatchesRequest( request, manifest, 
                                               self.RSpecVersion(),
                                               self.options_copy.bound,
                                               "Created sliver")
            if self.options_copy.api_version >= 3:
                self.subtest_PerformOperationalAction( slicename, 'geni_start')
        except:
            raise
        finally:
            time.sleep(self.options_copy.sleep_time)

    def test_SliverStatus_nagios(self):
        self.logger.info("\n=== Test.test_SliverStatus_nagios ===")
        self.assertTrue( hasattr(self.options_copy, 'reuse_slice_name'),
                         "No slice name passed in via (--reuse-slice) to use on this test.")
        self.subtest_SliverStatus_nagios(self.slicename)
        self.success = True

    def subtest_SliverStatus_nagios(self, slicename):
        have_slept = 0
        status_ready = False
        long_sleep = max( 5, self.options_copy.max_time / NUM_SLEEP )
        if slicename==None:
            slicename = self.create_slice_name()
        # before starting check if this is going to fail for unrecoverable reasons having nothing to do with being ready
        # maybe get the slice credential
        # self.subtest_generic_SliverStatus( slicename )        
        while have_slept <= self.options_copy.max_time:
            try:
                # checks geni_operational_status to see if ready
                if self.options_copy.api_version >= 3:
                    geni_status = "geni_ready"
                else:
                    geni_status = "ready"
                self.subtest_generic_SliverStatus( slicename, status=geni_status )
                status_ready=True 
                break
            except Exception, e:
                self.logger.info("Waiting for SliverStatus to succeed and return status of '%s'" % geni_status)
                self.logger.info("Exception raised: %s" % e)
                self.logger.debug("===> Starting to sleep")
                self.logger.debug("=== sleep %s seconds ==="%str(long_sleep))
                time.sleep( long_sleep )
                have_slept += long_sleep
                self.logger.debug("<=== Finished sleeping")
        self.assertTrue( status_ready, 
                         "SliverStatus on slice '%s' expected to be '%s' but was not" % (slicename, geni_status))


    def test_get_ch_version(self):
        """test_get_ch_version: Passes if a 'get_ch_version' returns an XMLRPC struct
        """
        # Do AM API call
        omniargs = ["get_ch_version"]
        self.logger.info("\n=== Test.test_get_ch_version ===")
        (text, ret_dict) = self.call(omniargs, self.options_copy)

        pprinter = pprint.PrettyPrinter(indent=4)
        # If this isn't a dictionary, something has gone wrong in Omni.  
        self.assertDict(ret_dict,
                        "Return from 'get_ch_version' " \
                        "expected to contain dictionary" \
                        "but instead returned:\n %s"
                        % (pprinter.pformat(ret_dict)))
        # An empty dict indicates a misconfiguration!
        self.assertTrue(ret_dict,
                        "Return from 'get_ch_version' " \
                        "expected to contain dictionary " \
                       "but instead returned empty dictionary. ")

        value = self.assertReturnKeyValueType( 'get_ch_version', None, ret_dict, 
                                                   'api', int )
        # Note that old gcf-pgch return a float here, new one is int,
        # and the PG spec uses int

        self.success = True


    @classmethod
    def getParser( cls, parser=accept.Test.getParser(), usage=None):

        parser.add_option( "--max-createsliver-time", 
                           action="store", type='int', 
                           default = MAX_TIME_TO_CREATESLIVER,
                           dest='max_time', 
                           help="Max number of seconds will attempt to check status of a sliver before failing  [default: %default]")
        return parser

    def nagios_parser( cls, parser=None, usage=None):
        if parser is None:
            parser = cls.getParser()
        argv = NagiosTest.unittest_parser(parser=parser, usage=usage)
        return argv

if __name__ == '__main__':
    usage = "\n      %s -a am-undertest" \
            "\n      Also try --vv" % sys.argv[0]
    NagiosTest.accept_parser(usage=usage)
    unittest.main()



