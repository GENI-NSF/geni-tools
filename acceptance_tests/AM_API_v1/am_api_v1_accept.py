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
# OR IMPLIED, IsNCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
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
from omnilib.util import OmniError, NoSliceCredError, RefusedError
import omni
import os
import pprint
import re
import sys
import time
import tempfile
import xml.etree.ElementTree as etree 

# TODO: TEMPORARILY USING PGv2 because test doesn't work with any of the others
# Works at PLC
PGV2_RSPEC_NAME = "ProtoGENI"
PGV2_RSPEC_NUM = '2'
RSPEC_NAME = "GENI"
RSPEC_NUM = '3'

# TODO: TEMPORARILY USING PGv2 because test doesn't work with any of the others
AD_NAMESPACE = "http://www.protogeni.net/resources/rspec/2"
AD_SCHEMA = "http://www.protogeni.net/resources/rspec/2/ad.xsd"
GENI_AD_NAMESPACE = "http://www.geni.net/resources/rspec/3"
GENI_AD_SCHEMA = "http://www.geni.net/resources/rspec/3/ad.xsd"
REQ_NAMESPACE = "http://www.protogeni.net/resources/rspec/2"
REQ_SCHEMA = "http://www.protogeni.net/resources/rspec/2/request.xsd"
GENI_REQ_NAMESPACE = "http://www.geni.net/resources/rspec/3"
GENI_REQ_SCHEMA = "http://www.geni.net/resources/rspec/3/request.xsd"
MANIFEST_NAMESPACE = "http://www.protogeni.net/resources/rspec/2"
MANIFEST_SCHEMA = "http://www.protogeni.net/resources/rspec/2/manifest.xsd"
GENI_MANIFEST_NAMESPACE = "http://www.geni.net/resources/rspec/3"
GENI_MANIFEST_SCHEMA = "http://www.geni.net/resources/rspec/3/manifest.xsd"

PG_CRED_NAMESPACE = "http://www.protogeni.net/resources/credential/ext/policy/1"
PG_CRED_SCHEMA = "http://www.protogeni.net/resources/credential/ext/policy/1/policy.xsd"


TMP_DIR="."
REQ_RSPEC_FILE="request.xml"
REQ_RSPEC_FILE_2="request2.xml"
REQ_RSPEC_FILE_3="request3.xml"
BAD_RSPEC_FILE="bad.xml"
SLEEP_TIME=3
################################################################################
#
# Test AM API v1 calls for accurate and complete functionality.
#
# This script relies on the unittest module.
#
# To run all tests:
# ./am_api_v1_accept.py -a <AM to test>
#
# To run a single test:
# ./am_api_v1_accept.py -a <AM to test> Test.test_GetVersion
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

    def setUp( self ):
        ut.OmniUnittest.setUp(self)

        if self.options_copy.protogeniv2:
            self.options_copy.rspectype = (PGV2_RSPEC_NAME, PGV2_RSPEC_NUM)  
            self.manifest_namespace = MANIFEST_NAMESPACE
            self.manifest_schema = MANIFEST_SCHEMA
            self.request_namespace = REQ_NAMESPACE
            self.request_schema = REQ_SCHEMA
            self.ad_namespace = AD_NAMESPACE
            self.ad_schema = AD_SCHEMA
        else:
            self.options_copy.rspectype = (RSPEC_NAME, RSPEC_NUM)
            self.manifest_namespace = GENI_MANIFEST_NAMESPACE
            self.manifest_schema = GENI_MANIFEST_SCHEMA
            self.request_namespace = GENI_REQ_NAMESPACE
            self.request_schema = GENI_REQ_SCHEMA
            self.ad_namespace = GENI_AD_NAMESPACE
            self.ad_schema = GENI_AD_SCHEMA
        self.success = False
    def tearDown( self ):
        ut.OmniUnittest.tearDown(self)
        if self.options_copy.monitoring:
            # MONITORING test_TestName 1
            print "\nMONITORING %s %d" % (self.id().split('.',2)[-1],int(self.success))
    def checkAdRSpecVersion(self):
        return self.checkRSpecVersion(type='ad')
    def checkRequestRSpecVersion(self):
        return self.checkRSpecVersion(type='request')
    def checkRSpecVersion(self, type='ad'):
        """type is either 'ad' or 'request' """
        if type not in ('ad', 'request'):
            print "type must be either 'ad' or 'request', received '%s' instead" % type
            return False

        rspec_type = type+"_rspec_versions"
        rtype = self.options_copy.rspectype[0]
        rver = self.options_copy.rspectype[1]

        # call GetVersion
        omniargs = ['getversion']
        (text, version) = self.call(omniargs, self.options_copy)

        mymessage = ""

        for agg, thisVersion in version.items():

            self.assertTrue( thisVersion, 
                             "AM %s didn't respond to GetVersion" % (agg) )
            value = thisVersion               
            if self.options_copy.api_version == 2: 
#                value = thisVersion['value']
                rspec_version = self.assertReturnPairKeyValue( 
                    'GetVersion', agg, value, 
                    'geni_'+rspec_type, 
                    None,
                    list )
            else:
                rspec_version = self.assertReturnPairKeyValue( 
                    'GetVersion', agg, value, 
                    rspec_type, 
                    'geni_'+rspec_type, 
                    list )

            # foreach item in the list that is the val
            match = False
            for availversion in rspec_version:
                if not(str(availversion['type']).lower().strip() == rtype.lower().strip()):
                    continue
                if not(str(availversion['version']).lower().strip() == str(rver).lower().strip()):
                    continue

                match = True
                rtype=availversion['type']
                rver=availversion['version']
                break
            self.assertTrue(match, 
                        "Agg doesn't support requested version: %s %s" % (rtype, rver))
            return match

    def test_GetVersion(self):
        """test_GetVersion: Passes if a 'GetVersion' returns an XMLRPC struct containing 'geni_api' and other parameters defined in Change Set A.
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

            self.assertEqual(value, self.options_copy.api_version,
                          "Return from 'GetVersion' at aggregate '%s' " \
                          "expected to have 'geni_api=%d' " \
                          "but instead 'geni_api=%d.'"  
                           % (agg, self.options_copy.api_version, value))

            if self.options_copy.api_version == 2:
                request_rspec_versions = self.assertReturnPairKeyValue( 
                    'GetVersion', agg, ver_dict, 
                    'geni_request_rspec_versions', 
                    None,
                    list )
            else:
                request_rspec_versions = self.assertReturnPairKeyValue( 
                    'GetVersion', agg, ver_dict, 
                    'request_rspec_versions', 
                    'geni_request_rspec_versions', 
                    list )
            if self.options_copy.protogeniv2:
                exp_type = PGV2_RSPEC_NAME
                exp_num = PGV2_RSPEC_NUM
            else:
                exp_type = RSPEC_NAME
                exp_num = RSPEC_NUM
            request = False
            for vers in request_rspec_versions:
#                self.assertKeyValueType( 'GetVersion', agg, vers, 'schema', str )
#                self.assertKeyValueType( 'GetVersion', agg, vers, 'namespace', str )
                self.assertKeyValueType( 'GetVersion', agg, vers, 'type', str)
                self.assertKeyValueType( 'GetVersion', agg, vers, 'version', str, )
                try:
                    self.assertKeyValueLower( 'GetVersion', agg, vers, 
                                         'type', exp_type )
                    self.assertKeyValueLower( 'GetVersion', agg, vers, 
                                         'version', exp_num )
                    request = True
                except:
                    pass

                self.assertKeyValueType( 'GetVersion', agg, vers, 'extensions', type([]) )


            self.assertTrue( request,
                        "Return from 'GetVersion' at %s " \
                        "expected to have entry " \
                        "'geni_request_rspec_versions' of " \
                        "type='%s' and value='%s' " \
                        "but did not." 
                        % (agg, exp_type, exp_num) )



            if self.options_copy.api_version == 2:
                ad_rspec_versions = self.assertReturnPairKeyValue( 
                    'GetVersion', agg, ver_dict, 
                    'geni_ad_rspec_versions', 
                    None,
                    list )
            else:
                ad_rspec_versions = self.assertReturnPairKeyValue( 
                    'GetVersion', agg, ver_dict, 
                    'ad_rspec_versions',
                    'geni_ad_rspec_versions', 
                    list )
            ad = False
            for vers in ad_rspec_versions:
#                self.assertKeyValueType( 'GetVersion', agg, vers, 'schema', str )
#                self.assertKeyValueType( 'GetVersion', agg, vers, 'namespace', str )
                self.assertKeyValueType( 'GetVersion', agg, vers, 'type', str)
                self.assertKeyValueType( 'GetVersion', agg, vers, 'version', str, )
                try:
                    self.assertKeyValueLower( 'GetVersion', agg, vers, 
                                         'type', exp_type )
                    self.assertKeyValueLower( 'GetVersion', agg, vers, 
                                         'version', exp_num )
                    ad = True
                except:
                    pass
                self.assertKeyValueType( 'GetVersion', agg, vers, 'extensions', type([]) )
            self.assertTrue( ad,
                        "Return from 'GetVersion' at %s " \
                        "expected to have entry " \
                        "'geni_ad_rspec_versions' of " \
                        "'type'=%s and 'value'=%s" \
                        "but did not." 
                        % (agg, exp_type, exp_num) )



        self.success = True
    def test_ListResources(self):
        """test_ListResources: Passes if 'ListResources' returns an advertisement RSpec.
        """
        if self.options_copy.api_version > 1:
            self.options_copy.arbitrary_option = True
        # omni sets 'geni_compress' = True
        self.subtest_ListResources()
        self.success = True
    def test_ListResources_geni_compressed(self):
        """test_ListResources_geni_compressed: Passes if 'ListResources' returns an advertisement RSpec.
        """
        # omni sets 'geni_compressed' = True, override
        self.options_copy.geni_compressed = False
        self.subtest_ListResources()
        self.success = True
    def test_ListResources_geni_available(self):
        """test_ListResources_geni_available: Passes if 'ListResources' returns an advertisement RSpec.
        """
        # omni sets 'geni_available' = False, override
        self.options_copy.geni_available = True
        self.subtest_ListResources()
        self.success = True

    def test_ListResources_badCredential_malformedXML(self):
        """test_ListResources_badCredential_malformedXML: Run ListResources with a User Credential that is missing it's first character (so that it is invalid XML). """
        self.subtest_ListResources_badCredential(self.removeFirstChar)
        self.success = True
    def test_ListResources_badCredential_alteredObject(self):
        """test_ListResources_badCredential_alteredObject: Run ListResources with a User Credential that has been altered (so the signature doesn't match). """
        self.subtest_ListResources_badCredential(self.alterSignedObject)
        self.success = True
    def removeFirstChar( self, usercred ):
        return usercred[1:]

    def alterSignedObject( self, usercred ):
        try:
            root = etree.fromstring(usercred)
        except:
            raise ValueError, "'usercred' is not an XML document."
        newElement = etree.Element("foo")
        root.insert(0, newElement)
        newcred = etree.tostring(root)
        return newcred

    def subtest_ListResources_badCredential(self, mundgeFcn):
        """test_ListResources_badCredential: Passes if 'ListResources' FAILS to return an advertisement RSpec when using a bad credential.
        """

        # (1) Get the usercredential
        omniargs = ["getusercred"]
        (text, usercred) = self.call(omniargs, self.options_copy)
        self.assertTrue( type(usercred) is str,
                        "Return from 'getusercred' " \
                            "expected to be string " \
                            "but instead returned: %r" 
                        % (usercred))

        # Test if file is XML and contains "<rspec" or "<resv_rspec"
        self.assertTrue(rspec_util.is_wellformed_xml( usercred ),
                        "Return from 'getusercred' " \
                        "expected to be XML " \
                        "but instead returned: \n" \
                        "%s\n" \
                        "... edited for length ..." 
                        % (usercred[:100]))

        # TO DO Validate usercred xml file
        # # Test if XML file passes rspeclint
        # if self.options_copy.rspeclint:
        #     self.assertTrue(rspec_util.validate_rspec( rspec, 
        #                                                namespace=rspec_namespace, 
        #                                                schema=rspec_schema ),
        #                     "Return from 'ListResources' at aggregate '%s' " \
        #                     "expected to pass rspeclint " \
        #                     "but did not. Return was: " \
        #                     "\n%s\n" \
        #                     "... edited for length ..."
        #                     % (agg_name, rspec[:100]))



        # (2) Create a broken usercred
        broken_usercred = mundgeFcn(usercred)

        # (3) Call listresources with this broken credential
        # We expect this to fail
        # self.subtest_ListResources(usercred=broken_usercred) 
        # with slicename left to the default
        self.assertRaises(NotDictAssertionError, self.subtest_ListResources, usercred=broken_usercred)

    def subtest_ListResources_wrongSlice(self, slicelist):
        num_slices = len(slicelist)
        for i in xrange(num_slices):
            slice = slicelist[i]
            # (1) Get the usercredential
            omniargs = ["getslicecred", slice]
            (text, slicecred) = self.call(omniargs, self.options_copy)
            self.assertTrue( type(slicecred) is str,
                             "Return from 'getslicecred' " \
                                 "expected to be string " \
                                 "but instead returned: %r" 
                             % (slicecred))

        # Test if file is XML and contains "<rspec" or "<resv_rspec"
        self.assertTrue(rspec_util.is_wellformed_xml( slicecred ),
                        "Return from 'getslicecred' " \
                        "expected to be XML " \
                        "but instead returned: \n" \
                        "%s\n" \
                        "... edited for length ..." 
                        % (slicecred[:100]))

        # (2) Call listresources on the next slice
        # We expect this to fail
        # self.subtest_ListResources(slice) 
        self.assertRaises(NotDictAssertionError, self.subtest_ListResources, slicename=slicelist[(i+1)%num_slices], slicecred=slicecred)


    def file_to_string( self, filename ):
        with open(filename) as f:
            contents = f.readlines()
            output = "".join(contents)        
        return output

    def get_cred_schema_info( self, version ):
        if version.lower() in ("protogeni", "pg"):
            return (PG_CRED_NAMESPACE, 
                    PG_CRED_SCHEMA)

    def is_delegated_cred( cls, xml):
        try:
            root = etree.fromstring(xml)
        except:
            return False

#        ns, schema = cls.get_cred_schema_info( version=version )
#        prefix = "{%s}"%ns
        parent = root.findall( 'credential/parent' )
        if len(parent) > 0:
            return True
        else:
            return False

    def get_slice_name_from_cred( cls, xml):
        """Get the slice_name from the credential (retrieve the first if there is more than one)"""
        try:
            root = etree.fromstring(xml)
        except:
            return False

#        ns, schema = cls.get_cred_schema_info( version=version )
#        prefix = "{%s}"%ns
        target = root.findall( 'credential/parent/credential/target_urn' )
        urn = target[0].text

        # urn is of form: ...+slice+name
        # (1) check that second to last part of URN is 'slice'
        # (1) return the last part of the URN
        urn_type = urn.rsplit("+")[-2]
        if urn_type == 'slice':
            slice_name = urn.rsplit("+")[-1]
            return slice_name
        else:
            return None
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
        self.subtest_ListResources(
           slicename=slice_name,
           slicecredfile=self.options_copy.delegated_slicecredfile)
        self.success = True
    def test_ListResources_untrustedCredential(self):
        """test_ListResources_untrustedCredential: Passes if 'ListResources' FAILS to return an advertisement RSpec when using a credential from an untrusted Clearinghouse.
        """
        # Call listresources with this credential
        # We expect this to fail
        # self.subtest_ListResources(usercred=invalid_usercred) 
        # with slicename left to the default
        self.assertRaises(NotDictAssertionError, self.subtest_ListResources, usercredfile=self.options_copy.untrusted_usercredfile)
        self.success = True


    def subtest_ListResources(self, slicename=None, slicecred=None, usercred=None, usercredfile=None, slicecredfile=None):
        if not slicecred:
            self.assertTrue( self.checkAdRSpecVersion() )

        # Check to see if 'rspeclint' can be found before doing the hard (and
        # slow) work of calling ListResources at the aggregate
        if self.options_copy.rspeclint:
            rspec_util.rspeclint_exists()

        self.options_copy.omnispec = False # omni will complaining if both true
        if slicename:
            rspec_namespace = self.manifest_namespace
            rspec_schema = self.manifest_schema
        else:
            rspec_namespace = self.ad_namespace
            rspec_schema = self.ad_schema
        
        omniargs = [] 

        if slicename:
            omniargs = omniargs + ["listresources", str(slicename)]
        else:
            omniargs = omniargs + ["listresources"]

        if usercred and slicecred:
            with tempfile.NamedTemporaryFile() as f:
                # make a temporary file containing the user credential
                f.write( usercred )
                f.seek(0)
                with tempfile.NamedTemporaryFile() as f2:
                    # make a temporary file containing the slice credential
                    f2.write( slicecred )
                    f2.seek(0)
                    omniargs = omniargs + ["--usercredfile", f.name] + ["--slicecredfile", f2.name] 
                    # run command here while temporary file is open
                    (text, ret_dict) = self.call(omniargs, self.options_copy)
        elif slicecred and not(usercred):
            with tempfile.NamedTemporaryFile() as f2:
                    # make a temporary file containing the slice credential
                    f2.write( slicecred )
                    f2.seek(0)
                    omniargs = omniargs + ["--slicecredfile", f2.name] 
                    (text, ret_dict) = self.call(omniargs, self.options_copy)
        elif usercred and not(slicecred):
            with tempfile.NamedTemporaryFile() as f:
                # make a temporary file containing the user credential
                f.write( usercred )
                f.seek(0)
                omniargs = omniargs + ["--usercredfile", f.name] 
                # run command here while temporary file is open
                (text, ret_dict) = self.call(omniargs, self.options_copy)
        elif usercredfile:
            omniargs = omniargs + ["--usercredfile", usercredfile] 
            # run command here while temporary file is open
            (text, ret_dict) = self.call(omniargs, self.options_copy)
        elif slicecredfile:
            omniargs = omniargs + ["--slicecredfile", slicecredfile] 
            # run command here while temporary file is open
            (text, ret_dict) = self.call(omniargs, self.options_copy)
        else:
            (text, ret_dict) = self.call(omniargs, self.options_copy)

        pprinter = pprint.PrettyPrinter(indent=4)

        ## In python 2.7: assertIs
        self.assertDict(ret_dict,
                       "Call to 'ListResources' failed or not possible " \
                        "but expected to succeed. " \
                        "Error returned:\n %s"
                        % (text))

        # An empty dict indicates a misconfiguration!
        self.assertTrue(ret_dict,
                        "Return from 'ListResources' " \
                        "expected to contain dictionary keyed by aggregates " \
                        "but instead returned empty dictionary. " \
                        "This indicates there were no aggregates checked. " \
                        "Look for misconfiguration.")

        # Checks each aggregate
        for ((agg_name, agg_url), rspec) in ret_dict.items():
#            print "+++++++++++++"
#            print agg_name, agg_url, rspec
#            print "+++++++++++++"
#            if self.options_copy.api_version == 2: 
#                self.assertV2ReturnStruct( 'ListResources', agg_name, rspec)
#                rspec = rspec['value']


            ## In python 2.7: assertIsNotNone
            self.assertTrue(rspec,
                          "Return from 'ListResources' at aggregate '%s' " \
                          "expected to be XML file " \
                          "but instead nothing returned." 
                           % (agg_name))
            # TODO: more elegant truncation
            self.assertTrue(type(rspec) is str,
                          "Return from 'ListResources' at aggregate '%s' " \
                          "expected to be string " \
                          "but instead returned: \n" \
                          "%s\n" \
                          "... edited for length ..." 
                          % (agg_name, rspec[:100]))

            # Test if file is XML and contains "<rspec" or "<resv_rspec"
            # TODO is_rspec_string() might not be exactly the right thing here
            self.assertTrue(rspec_util.is_rspec_string( rspec ),
                          "Return from 'ListResources' at aggregate '%s' " \
                          "expected to be XML " \
                          "but instead returned: \n" \
                          "%s\n" \
                          "... edited for length ..." 
                           % (agg_name, rspec[:100]))

            if slicename:
                self.assertRspecType( rspec, 'manifest')
            else:
                self.assertRspecType( rspec, 'advertisement')

            # Test if XML file passes rspeclint
            if self.options_copy.rspeclint:
                self.assertTrue(rspec_util.validate_rspec( rspec, 
                                                       namespace=rspec_namespace, 
                                                       schema=rspec_schema ),
                            "Return from 'ListResources' at aggregate '%s' " \
                            "expected to pass rspeclint " \
                            "but did not. Return was: " \
                            "\n%s\n" \
                            "... edited for length ..."
                            % (agg_name, rspec[:100]))

        return rspec

    def test_CreateSliver(self):
        """test_CreateSliver: Passes if the sliver creation workflow succeeds.  Use --rspec-file to replace the default request RSpec."""
        self.subtest_CreateSliverWorkflow()
        self.success = True

    def subtest_CreateSliverWorkflow(self, slicename=None):
        # Check to see if 'rspeclint' can be found before doing the hard (and
        # slow) work of calling ListResources at the aggregate
        if self.options_copy.rspeclint:
            rspec_util.rspeclint_exists()
            rspec_namespace = self.manifest_namespace
            rspec_schema = self.manifest_schema


        if slicename==None:
            slicename = self.create_slice_name()

        # if reusing a slice name, don't create (or delete) the slice
        if not self.options_copy.reuse_slice_name:
            self.subtest_createslice( slicename )
            time.sleep(self.options_copy.sleep_time)

        # cleanup up any previous failed runs
        try:
            self.subtest_DeleteSliver( slicename )
        except:
            pass

        manifest = self.subtest_CreateSliver( slicename )
        with open(self.options_copy.rspec_file) as f:
            req = f.readlines()
            request = "".join(req)

        try:

            self.assertRspecType( request, 'request')
            self.assertRspecType( manifest, 'manifest')

            # manifest should be valid XML 
            self.assertIsXML(  manifest,
                         "Manifest RSpec returned by 'CreateSliver' on slice '%s' " \
                             "expected to be wellformed XML file " \
                             "but was not. Return was: " \
                             "\n%s\n" \
                             "... edited for length ..."
                         % (slicename, manifest[:100]))                         


            # Test if manifest passes rspeclint
            if self.options_copy.rspeclint:
                self.assertTrue(rspec_util.validate_rspec( manifest, 
                                                       namespace=rspec_namespace, 
                                                       schema=rspec_schema ),
                            "Manifest RSpec returned from 'CreateSliver' " \
                            "expected to pass rspeclint " \
                            "but did not. Return was: " \
                            "\n%s\n" \
                            "... edited for length ..."
                            % (manifest[:100]))

            # Make sure the Manifest returned the nodes identified in the Request
            if rspec_util.has_child_node( manifest, self.RSpecVersion()):
                self.assertCompIDsEqual( request, manifest, self.RSpecVersion(), 
                                     "Request RSpec and Manifest RSpec " \
                                         "returned by 'ListResources' on slice '%s' " \
                                         "expected to have same component_ids " \
                                         "but did not." % slicename)
            else:
                # the top level node should have a child
                self.assertResourcesExist( manifest,
                          "Manifest RSpec returned by 'CreateSliver' on slice '%s' " \
                              "expected to NOT be empty " \
                              "but was. Return was: " \
                              "\n%s\n" 
                          % (slicename, manifest))

            
            time.sleep(self.options_copy.sleep_time)

            self.subtest_SliverStatus( slicename )        
            manifest2 = self.subtest_ListResources( slicename=slicename )

            self.assertRspecType( manifest2, 'manifest')

            # manifest should be valid XML 
            self.assertIsXML(  manifest2,
                         "Manifest RSpec returned by 'ListResources' on slice '%s' " \
                             "expected to be wellformed XML file " \
                             "but was not. Return was: " \
                             "\n%s\n" \
                             "... edited for length ..."
                         % (slicename, manifest2[:100]))                         

            # Test if manifest passes rspeclint
            if self.options_copy.rspeclint:
                self.assertTrue(rspec_util.validate_rspec( manifest2, 
                                                       namespace=rspec_namespace, 
                                                       schema=rspec_schema ),
                            "Manifest RSpec returned from 'ListResources' " \
                            "on a slice " \
                            "expected to pass rspeclint " \
                            "but did not. Return was: " \
                            "\n%s\n" \
                            "... edited for length ..."
                            % (manifest2[:100]))


            # Make sure the Manifest returned the nodes identified in the Request
            if rspec_util.has_child_node( manifest2, self.RSpecVersion()):
                self.assertCompIDsEqual( request, manifest2, self.RSpecVersion(),
                                     "Request RSpec and Manifest RSpec " \
                                         "returned by 'ListResources' on slice '%s' " \
                                         "expected to have same component_ids " \
                                         "but did not." % slicename )
            else:
                # the top level node should have a child
                self.assertResourcesExist( manifest2,
                          "Manifest RSpec returned by 'ListResources' on slice '%s' " \
                              "expected to NOT be empty " \
                              "but was. Return was: " \
                              "\n%s\n" 
                          % (slicename, manifest2))


            # Attempting to CreateSliver again should fail or return a manifest

            if not self.options_copy.strict:
                # if --less-strict, then accept a returned error
                if self.options_copy.api_version == 2:
                    # Be more specific when we can
                    self.assertRaises(RefusedError, 
                                      self.subtest_CreateSliver, slicename )
                else:
                    # This is a little generous, as this error is
                    # raised for many reasons
                    self.assertRaises(NotNoneAssertionError, 
                                      self.subtest_CreateSliver, slicename )                    
            else:
                # if --more-strict
                # ListResources should return an RSpec containing no resources
                manifest = self.subtest_ListResources( slicename )
                self.assertTrue( rspec_util.is_wellformed_xml( manifest ),
                             "Manifest RSpec returned by 'ListResources' on slice '%s' " \
                             "expected to be wellformed XML file " \
                             "but was not. Return was: " \
                             "\n%s\n" \
                             "... edited for length ..."
                         % (slicename, manifest[:100]))                         
                self.assertTrue( rspec_util.has_child( manifest ),
                          "Manifest RSpec returned by 'ListResources' on slice '%s' " \
                              "expected to be non-empty " \
                              "but was empty. Return was: " \
                              "\n%s\n" \
                              "... edited for length ..."
                          % (slicename, manifest[:100]))



            time.sleep(self.options_copy.sleep_time)
            # RenewSliver for 5 mins, 2 days, and 5 days
            self.subtest_RenewSliver_many( slicename )
        except:
            raise
        finally:
            time.sleep(self.options_copy.sleep_time)
            self.subtest_DeleteSliver( slicename )

        # Test SliverStatus, ListResources and DeleteSliver on a deleted sliver
        self.subtest_CreateSliverWorkflow_failure( slicename )

        if not self.options_copy.reuse_slice_name:
            self.subtest_deleteslice( slicename )
            
    def subtest_MinCreateSliverWorkflow(self, slicename=None):
        if slicename==None:
            slicename = self.create_slice_name()

        # if reusing a slice name, don't create (or delete) the slice
        if not self.options_copy.reuse_slice_name:
            self.subtest_createslice( slicename )
            time.sleep(self.options_copy.sleep_time)

        # cleanup up any previous failed runs
        try:
            self.subtest_DeleteSliver( slicename )
        except:
            pass

        manifest = self.subtest_CreateSliver( slicename )
        with open(self.options_copy.rspec_file) as f:
            req = f.readlines()
            request = "".join(req)             
        try:
            self.subtest_DeleteSliver( slicename )
        except:
            pass

        if not self.options_copy.reuse_slice_name:
            self.subtest_deleteslice( slicename )


    def test_CreateSliverWorkflow_fail_notexist( self ):
        """test_CreateSliverWorkflow_fail_notexist:  Passes if the sliver creation workflow fails when the slice has never existed."""
        slicename = self.create_slice_name_uniq(prefix='non')        
        # Test SliverStatus, ListResources and DeleteSliver on a non-existant sliver
        self.subtest_CreateSliverWorkflow_failure( slicename )
        self.success = True
    def subtest_CreateSliverWorkflow_failure( self, slicename ):
        self.assertRaises((NotDictAssertionError, NoSliceCredError), 
                          self.subtest_SliverStatus, slicename )
        
        if not self.options_copy.strict:
            # if --less-strict, then accept a returned error
            self.assertRaises(NotDictAssertionError, self.subtest_ListResources, slicename )
        else:
            # if --more-strict
            # ListResources should return an RSpec containing no resources
            manifest = self.subtest_ListResources( slicename )
            self.assertTrue( rspec_util.is_wellformed_xml( manifest ),
                             "Manifest RSpec returned by 'ListResources' on slice '%s' " \
                             "expected to be wellformed XML file " \
                             "but was not. Return was: " \
                             "\n%s\n" \
                             "... edited for length ..."
                         % (slicename, manifest[:100]))                         
            self.assertFalse( rspec_util.has_child( manifest ),
                          "Manifest RSpec returned by 'ListResources' on slice '%s' " \
                              "expected to be empty " \
                              "but was not. Return was: " \
                              "\n%s\n" \
                              "... edited for length ..."
                          % (slicename, manifest[:100]))
        
        # Also repeated calls to DeleteSliver should now fail
        self.assertRaises((AssertionError, NoSliceCredError), 
                          self.subtest_DeleteSliver, slicename )


    def test_CreateSliverWorkflow_multiSlice(self): 
        """test_CreateSliverWorkflow_multiSlice: Do CreateSliver workflow with multiple slices and ensure can not do ListResources on slices with the wrong credential."""

        if self.options_copy.rspeclint:
            rspec_util.rspeclint_exists()
            rspec_namespace = self.manifest_namespace
            rspec_schema = self.manifest_schema

        request = []
        manifest = []
        manifest2 = []
        slicenames = []

        NUM_SLICES = 3

        if self.options_copy.reuse_slice_list:
            slicenames = self.options_copy.reuse_slice_list
            num_slices = len(slicenames)
        else:
            num_slices = NUM_SLICES
            for i in xrange(num_slices):
                slicenames.append("")
                slicenames[i] = self.create_slice_name()+str(i)

        # Handle if rspec_file_list and reuse_slice_list are different lengths
        num_slices = min( num_slices, self.options_copy.rspec_file_list )

        for i in xrange(num_slices):
            # if reusing a slice name, don't create (or delete) the slice
            if not self.options_copy.reuse_slice_list:
                self.subtest_createslice( slicenames[i] )

        if not self.options_copy.reuse_slice_list:
            time.sleep(self.options_copy.sleep_time)

        # in case some slivers were left laying around from last
        # time, try to delete them now
        for i in xrange(num_slices):
            try:
                self.subtest_DeleteSliver( slicenames[i] )
            except:
                pass

        try:
            for i in xrange(num_slices):
                # Check for the existance of the Request RSpec file
                self.assertTrue( os.path.exists(self.options_copy.rspec_file_list[i]), 
                "Request RSpec file, '%s' for 'CreateSliver' call " \
                                     "expected to exist " \
                                     "but does not." 
                                 % self.options_copy.rspec_file_list[i] )
                with open(self.options_copy.rspec_file_list[i]) as f:
                    request.append("")
                    request[i] = "".join(f.readlines())
                manifest.append("")
                self.options_copy.rspec_file = self.options_copy.rspec_file_list[i]
                
                manifest[i] = "".join(self.subtest_CreateSliver( slicenames[i] ))


            for i in xrange(num_slices):
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


                # Make sure the Manifest returned the nodes identified in the Request
                if rspec_util.has_child_node( manifest[i], self.RSpecVersion()):
                    self.assertCompIDsEqual( "".join(request[i]), "".join(manifest[i]), self.RSpecVersion(), 
                                         "Request RSpec and Manifest RSpec " \
                                             "returned by 'ListResources' on slice '%s' " \
                                             "expected to have same component_ids " \
                                             "but did not." % slicenames[i])
                                         
                else:
                    # the top level node should have a child
                    self.assertResourcesExist( "".join(manifest[i]),
                    "Manifest RSpec returned by 'CreateSliver' on slice '%s' " \
                    "expected to NOT be empty " \
                    "but was. Return was: " \
                    "\n%s\n" 
                    % (slicenames[i], "".join(manifest[i])))
            
            time.sleep(self.options_copy.sleep_time)

            for i in xrange(num_slices):
                self.subtest_SliverStatus( slicenames[i] )        

            # Make sure you can't list resources on other slices
            # using the wrong slice cred
            self.subtest_ListResources_wrongSlice( slicenames )        

            time.sleep(self.options_copy.sleep_time)

            for i in xrange(num_slices):
                manifest2.append("")
                manifest2[i] = "".join(self.subtest_ListResources( slicename=slicenames[i] ))
            for i in xrange(num_slices):
                self.assertRspecType( "".join(manifest2[i]), 'manifest')

                # manifest should be valid XML 
                self.assertIsXML(  manifest2[i],
                         "Manifest RSpec returned by 'ListResources' on slice '%s' " \
                             "expected to be wellformed XML file " \
                             "but was not. Return was: " \
                             "\n%s\n" \
                             "... edited for length ..."
                         % (slicenames[i], manifest[i][:100]))                         

                if self.options_copy.rspeclint:
                    self.assertTrue(rspec_util.validate_rspec( manifest2[i], 
                                                    namespace=rspec_namespace, 
                                                    schema=rspec_schema ),
                            "Return from 'CreateSliver' " \
                            "expected to pass rspeclint " \
                            "but did not. Return was: " \
                            "\n%s\n" \
                            "... edited for length ..."
                            % (manifest2[i][:100]))



                # Make sure the Manifest returned the nodes identified in the Request
                if rspec_util.has_child_node( manifest2[i], self.RSpecVersion()):
                    self.assertCompIDsEqual( request[i], manifest2[i], self.RSpecVersion(), 
                                     "Request RSpec and Manifest RSpec " \
                                         "returned by 'ListResources' on slice '%s' " \
                                         "expected to have same component_ids " \
                                         "but did not." % slicenames[i] )
                else:
                    # the top level node should have a child
                    self.assertResourcesExist( "".join(manifest2[i]),
                    "Manifest RSpec returned by 'ListResources' on slice '%s' " \
                    "expected to NOT be empty " \
                    "but was. Return was: " \
                    "\n%s\n" 
                    % (slicenames[i], "".join(manifest2[i])))

            time.sleep(self.options_copy.sleep_time)
            # RenewSliver for 5 mins, 2 days, and 5 days
            for i in xrange(num_slices):
                time.sleep(self.options_copy.sleep_time)
                self.subtest_RenewSliver_many( slicenames[i] )
        except:
            raise
        finally:
            time.sleep(self.options_copy.sleep_time)
            for i in xrange(num_slices):
                try:
                    self.subtest_DeleteSliver( slicenames[i] )
                except:
                    pass

        # Test SliverStatus, ListResources and DeleteSliver on a deleted sliver
        for i in xrange(num_slices):       
            self.subtest_CreateSliverWorkflow_failure( slicenames[i] )


        if not self.options_copy.reuse_slice_list:
            for i in xrange(num_slices):
                try:
                    self.subtest_deleteslice( slicenames[i] )
                except:
                    pass
        self.success = True
    def subtest_RenewSliver( self, slicename, newtime ):
        omniargs = ["renewsliver", slicename, newtime] 
        text, (succList, failList) = self.call(omniargs, self.options_copy)
        succNum, possNum = omni.countSuccess( succList, failList )
        pprinter = pprint.PrettyPrinter(indent=4)
        self.assertTrue( int(succNum) == 1,
                         "'RenewSliver' until %s " \
                         "expected to succeed " \
                         "but did not." % (str(newtime)))

    def subtest_RenewSlice( self, slicename, newtime ):
        omniargs = ["renewslice", slicename, newtime] 
        text, date = self.call(omniargs, self.options_copy)
        pprinter = pprint.PrettyPrinter(indent=4)
        self.assertIsNotNone( date, 
                         "'RenewSlice' until %s " \
                         "expected to succeed " \
                         "but did not." % (str(newtime)))

    def subtest_RenewSliver_many( self, slicename ):
        now = datetime.datetime.utcnow()
        fivemin = (now + datetime.timedelta(minutes=5)).isoformat()            
        twodays = (now + datetime.timedelta(days=2)).isoformat()            
        fivedays = (now + datetime.timedelta(days=5)).isoformat()           
        sixdays = (now + datetime.timedelta(days=6)).isoformat()            
        self.subtest_RenewSlice( slicename, sixdays )
        time.sleep(self.options_copy.sleep_time)
#        self.subtest_RenewSliver( slicename, fivemin )
#        time.sleep(self.options_copy.sleep_time)
        self.subtest_RenewSliver( slicename, twodays )
        time.sleep(self.options_copy.sleep_time)
        self.subtest_RenewSliver( slicename, fivedays )

    def subtest_CreateSliver(self, slice_name):
        self.assertTrue( self.checkRequestRSpecVersion() )

        # Check for the existance of the Request RSpec file
        self.assertTrue( os.path.exists(self.options_copy.rspec_file),
                         "Request RSpec file, '%s' for 'CreateSliver' call " \
                             "expected to exist " \
                             "but does not." 
                         % self.options_copy.rspec_file )
        
        # CreateSliver
        omniargs = ["createsliver", slice_name, str(self.options_copy.rspec_file)] 
        text, manifest = self.call(omniargs, self.options_copy)

        pprinter = pprint.PrettyPrinter(indent=4)
        ## In python 2.7: assertIsNotNone
        self.assertIsNotNone(manifest,
                          "Return from 'CreateSliver'" \
                          "expected to be XML file " \
                          "but instead nothing returned. AM returned:\n %s"%text)
        # TODO: more elegant truncation
        self.assertTrue(type(manifest) is str,
                        "Return from 'CreateSliver' " \
                            "expected to be string " \
                            "but instead returned: \n" \
                            "%s\n" \
                            "... edited for length ..." 
                        % (manifest[:100]))

        # Test if file is XML and contains "<rspec" or "<resv_rspec"
        # TODO is_rspec_string() might not be exactly the right thing here
        self.assertTrue(rspec_util.is_rspec_string( manifest ),
                        "Return from 'CreateSliver' " \
                            "expected to be XML " \
                            "but instead returned: \n" \
                            "%s\n" \
                            "... edited for length ..." 
                        % (manifest[:100]))

        return manifest

    def subtest_SliverStatus(self, slice_name):
        # SliverStatus
        omniargs = ["sliverstatus", slice_name] 
        
        text, agg = self.call(omniargs, self.options_copy)

        pprinter = pprint.PrettyPrinter(indent=4)

        self.assertIsNotNone(agg,
                          "Return from 'SliverStatus'" \
                          "expected to be XMLRPC struct " \
                          "but instead returned None.")
        self.assertTrue(type(agg) is dict,
                        "Return from 'SliverStatus' " \
                            "expected to be XMLRPC struct " \
                            "but instead returned: \n" \
                            "%s\n" \
                            "... edited for length ..." 
                        % (agg))
        for aggName, status in agg.items():
            self.assertDict(status, 
                            "Return from 'SliverStatus' for Aggregate %s" \
                            "expected to be XMLRPC struct " \
                            "but instead returned: \n" \
                            "%s\n" \
                            "... edited for length ..." 
                            % (agg, status))
            self.assertKeyValueType( 'SliverStatus', aggName, status, 'geni_urn', str )
            self.assertKeyValueType( 'SliverStatus', aggName, status, 'geni_status', str )
            self.assertKeyValueType( 'SliverStatus', aggName, status, 'geni_resources', list )
            resources = status['geni_resources']
            for resource in resources:
                self.assertKeyValueType( 'SliverStatus', aggName, resource, 'geni_urn', str )
                self.assertKeyValueType( 'SliverStatus', aggName, resource, 'geni_status', str )
                self.assertKeyValueType( 'SliverStatus', aggName, resource, 'geni_error', str )


        




    def subtest_DeleteSliver(self, slice_name):
        omniargs = ["deletesliver", slice_name]
        text, (successList, failList) = self.call(omniargs, self.options_copy)
        _ = text # Appease eclipse
        succNum, possNum = omni.countSuccess( successList, failList )
        _ = possNum # Appease eclipse
        # ASSUMES we have reserved resources on exactly one aggregate
        self.assertTrue( int(succNum) == 1, 
                         "Sliver deletion expected to work " \
                         "but instead sliver deletion failed for slice: %s"
                         % slice_name )


    def subtest_createslice(self, slice_name ):
        """Create a slice. Not an AM API call."""
        omniargs = ["createslice", slice_name]
        text, urn = self.call(omniargs, self.options_copy)
        _ = text # Appease eclipse
        self.assertTrue( urn, 
                         "Slice creation expected to work " \
                         "but instead slice creation failed for slice: %s"
                         % slice_name )

    def subtest_deleteslice(self, slice_name):
        """Delete a slice. Not an AM API call."""
        omniargs = ["deleteslice", slice_name]
        text, successFail = self.call(omniargs, self.options_copy)
        _ = text # Appease eclipse
        self.assertTrue( successFail, 
                         "Slice deletion expected to work " \
                             "but instead slice deletion failed for slice: %s"
                         % slice_name )

    def test_CreateSliver_badrspec_emptyfile(self):
        """test_CreateSliver_badrspec_emptyfile: Passes if the sliver creation workflow fails when the request RSpec is an empty file."""
        slice_name = self.create_slice_name(prefix='bad1')
        with tempfile.NamedTemporaryFile() as f:
            # write to a new temporary file
            f.write( "" )
            f.seek(0)        
            self.options_copy.rspec_file = f.name
            self.assertRaises(NotNoneAssertionError,
                              self.subtest_MinCreateSliverWorkflow, slice_name )
        self.success = True
    def test_CreateSliver_badrspec_malformed(self):
        """test_CreateSliver_badrspec_malformed: Passes if the sliver creation workflow fails when the request RSpec is not well-formed XML."""

        # Check for the existance of the Request RSpec file
        self.assertTrue( os.path.exists(self.options_copy.rspec_file),
                         "Request RSpec file, '%s' for 'CreateSliver' call " \
                             "expected to exist " \
                             "but does not." 
                         % self.options_copy.rspec_file )

        slice_name = self.create_slice_name(prefix='bad2')

        # open self.options_copy.rspec_file
        with open(self.options_copy.rspec_file) as good:
            good_rspec = good.readlines()

        good_rspec = "".join(good_rspec)
        # replace </rspec> with <rspec>
        bad_rspec = good_rspec.replace("</rspec>", "<rspec>")

        with tempfile.NamedTemporaryFile() as f:
            # write to a new temporary file
            f.write( bad_rspec )
            f.seek(0)        
            self.options_copy.rspec_file = f.name
            self.assertRaises(NotNoneAssertionError,
                              self.subtest_MinCreateSliverWorkflow, slice_name )
        self.success = True

    def test_CreateSliver_badrspec_manifest(self):
        """test_CreateSliver_badrspec_manifest: Passes if the sliver creation workflow fails when the request RSpec is a manifest RSpec.  --bad-rspec-file allows you to replace the RSpec with an alternative."""
        slice_name = self.create_slice_name(prefix='bad3')
        self.options_copy.rspec_file = self.options_copy.bad_rspec_file
        
        # Check for the existance of the Request RSpec file
        self.assertTrue( os.path.exists(self.options_copy.rspec_file),
                         "Request RSpec file, '%s' for 'CreateSliver' call " \
                             "expected to exist " \
                             "but does not." 
                         % self.options_copy.rspec_file )

        self.assertRaises(NotNoneAssertionError,
                              self.subtest_MinCreateSliverWorkflow, slice_name)
        self.success = True
    @classmethod
    def accept_parser( cls, parser=omni.getParser(), usage=None):
        parser.add_option( "--reuse-slice", 
                           action="store", type='string', dest='reuse_slice_name', 
                           help="Use slice name provided instead of creating/deleting a new slice")
        parser.add_option( "--rspec-file", 
                           action="store", type='string', 
                           dest='rspec_file', default=REQ_RSPEC_FILE,
                           help="In CreateSliver tests, use _bounded_ request RSpec file provided instead of default of '%s'" % REQ_RSPEC_FILE )

        parser.add_option( "--bad-rspec-file", 
                           action="store", type='string', 
                           dest='bad_rspec_file', default=BAD_RSPEC_FILE,
                           help="In negative CreateSliver tests, use request RSpec file provided instead of default of '%s'" % BAD_RSPEC_FILE )

        parser.add_option("--untrusted-usercredfile", default='untrusted-usercred.xml', metavar="UNTRUSTED_USER_CRED_FILENAME",
                      help="Name of an untrusted user credential file to use in test: test_ListResources_untrustedCredential")


        parser.add_option("--delegated-slicecredfile", default='delegated.xml', metavar="DELEGATED_SLICE_CRED_FILENAME",
                      help="Name of a delegated slice credential file to use in test: test_ListResources_delegatedSliceCred")

        parser.add_option( "--rspec-file-list", 
                           action="store", type='string', nargs=3, 
                           dest='rspec_file_list', default=(REQ_RSPEC_FILE,REQ_RSPEC_FILE_2,REQ_RSPEC_FILE_3),
                           help="In multi-slice CreateSliver tests, use _bounded_ request RSpec files provided instead of default of '(%s,%s,%s)'" % (REQ_RSPEC_FILE,REQ_RSPEC_FILE_2,REQ_RSPEC_FILE_3) )

        parser.add_option( "--reuse-slice-list", 
                           action="store", type='string', nargs=3, dest='reuse_slice_list', 
                           help="In multi-slice CreateSliver tests, use slice names provided instead of creating/deleting a new slice")

        parser.add_option( "--rspeclint", 
                           action="store_true", 
                           dest='rspeclint', default=False,
                           help="Validate RSpecs using 'rspeclint'" )
        parser.add_option( "--less-strict", 
                           action="store_false", 
                           dest='strict', default=False,
                           help="Be less rigorous. (Default)" )
        parser.add_option( "--more-strict", 
                           action="store_true", 
                           dest='strict', default=False,
                           help="Be more rigorous." )
        parser.add_option( "--ProtoGENIv2", 
                           action="store_true", 
                           dest='protogeniv2', default=False,
                           help="Use ProtoGENI v2 RSpecs instead of %s %s"%(RSPEC_NAME, RSPEC_NUM) )
        parser.add_option( "--sleep-time", 
                           action="store", type='float', 
                           default=SLEEP_TIME,
                           help="Time to pause between some AM API calls in seconds (Default: %s seconds)"%(SLEEP_TIME) )
        parser.add_option( "--monitoring", 
                           action="store_true",
                           default=False,
                           help="Print output to allow tests to be used in monitoring. Output is of the form: 'MONITORING test_TestName 1' The third field is 1 if the test is successful and 0 is the test is unsuccessful." )

        argv = Test.unittest_parser(parser=parser, usage=usage)

        return argv

if __name__ == '__main__':
    usage = "\n      %s -a am-undertest " \
            "\n      Also try --vv" \
            "\n\n     Run an individual test using the following form..." \
            "\n     %s -a am-undertest Test.test_GetVersion" % (sys.argv[0], sys.argv[0])
    # Include default Omni_unittest command line options
    Test.accept_parser(usage=usage)

    # Invoke unit tests as usual
    unittest.main()


