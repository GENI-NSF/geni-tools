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
""" Acceptance tests for AM API v1, v2, and v3."""

import datetime
import dateutil.parser
from geni.util import rspec_util 
from geni.util import urn_util
import unittest
import omni_unittest as ut
from omni_unittest import NotSuccessError, NotDictAssertionError, NotNoneAssertionError
from omni_unittest import NotXMLAssertionError, NoResourcesAssertionError
from omnilib.util import OmniError, NoSliceCredError, RefusedError, AMAPIError
import omni
import os
import pprint
import re
import sys
import time
import tempfile
import xml.etree.ElementTree as etree 
from geni.util.rspec_schema import *

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
SLEEP_TIME=20

SUCCESS = 0
################################################################################
#
# Test AM API v1 calls for accurate and complete functionality.
#
# This script relies on the unittest module.
#
# To run all tests:
# ./am_api_accept.py -a <AM to test>
#
# To run a single test:
# ./am_api_accept.py -a <AM to test> Test.test_GetVersion
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

    def setUp( self ):
        ut.OmniUnittest.setUp(self)
        if self.options_copy.protogeniv2:
            self.options_copy.rspectype = (PGV2_RSPEC_NAME, PGV2_RSPEC_NUM)  
            self.manifest_namespace = PG_2_NAMESPACE
            self.manifest_schema = PG_2_MAN_SCHEMA
            self.request_namespace = PG_2_NAMESPACE
            self.request_schema = PG_2_REQ_SCHEMA
            self.ad_namespace = PG_2_NAMESPACE
            self.ad_schema = PG_2_AD_SCHEMA
        else:
            self.options_copy.rspectype = (RSPEC_NAME, RSPEC_NUM)
            self.manifest_namespace = GENI_3_NAMESPACE
            self.manifest_schema = GENI_3_MAN_SCHEMA
            self.request_namespace = GENI_3_NAMESPACE
            self.request_schema = GENI_3_REQ_SCHEMA
            self.ad_namespace = GENI_3_NAMESPACE
            self.ad_schema = GENI_3_AD_SCHEMA
        self.success = False
    def tearDown( self ):
        ut.OmniUnittest.tearDown(self)
        if self.options_copy.monitoring:
            # MONITORING test_TestName 1
            print "\nMONITORING %s %d" % (self.id().split('.',2)[-1],int(not self.success))
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

            if self.options_copy.api_version >= 2: 
                value = thisVersion['value']
                rspec_version = self.assertReturnKeyValueType( 
                    'GetVersion', agg, value, 
                    'geni_'+rspec_type, 
                    list )
            else:
                value = thisVersion               
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
        self.assertDict(ret_dict,
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
            value = self.assertReturnKeyValueType( 'GetVersion', agg, ver_dict, 
                                                   'geni_api', int )
            self.assertEqual(value, self.options_copy.api_version,
                          "Return from 'GetVersion' at aggregate '%s' " \
                          "expected to have 'geni_api=%d' " \
                          "but instead 'geni_api=%d.'"  
                           % (agg, self.options_copy.api_version, value))

            # If we only want to test Pure AM API v1 stop here
            if self.options_copy.api_version == 1 and self.options_copy.pure_v1:
                self.success = True
                return

            if self.options_copy.api_version >= 2:
                err_code, msg = self.assertCodeValueOutput( 'GetVersion', 
                                                            agg, ver_dict )    
                self.assertSuccess( err_code )
                value = ver_dict['value']
                api_vers = self.assertReturnKeyValueType( 
                    'GetVersion', agg, value, 
                    'geni_api_versions', 
                    dict )
                
                self.assertKeyValueType( 'GetVersion', agg, api_vers, 
                                         str(self.options_copy.api_version), 
                                         str )

            if self.options_copy.api_version >= 2:
                request_rspec_versions = self.assertReturnKeyValueType( 
                    'GetVersion', agg, value, 
                    'geni_request_rspec_versions', 
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
                self.assertKeyValueType( 'GetVersion', agg, vers, 'type', str)
                self.assertKeyValueType( 'GetVersion', agg, vers, 'version', str, )
                if self.options_copy.api_version == 3:
                    self.assertKeyValueType( 'GetVersion', agg, vers, 'schema', str )
                    self.assertKeyValueType( 'GetVersion', agg, vers, 'namespace', str )
                    self.assertKeyValueType( 'GetVersion', agg, vers, 'extensions', list )

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



            if self.options_copy.api_version >= 2:
                ad_rspec_versions = self.assertReturnKeyValueType( 
                    'GetVersion', agg, value, 
                    'geni_ad_rspec_versions', 
                    list )
            else:
                ad_rspec_versions = self.assertReturnPairKeyValue( 
                    'GetVersion', agg, ver_dict, 
                    'ad_rspec_versions',
                    'geni_ad_rspec_versions', 
                    list )
            ad = False
            for vers in ad_rspec_versions:
                self.assertKeyValueType( 'GetVersion', agg, vers, 'type', str)
                self.assertKeyValueType( 'GetVersion', agg, vers, 'version', str, )
                if self.options_copy.api_version == 3:
                    self.assertKeyValueType( 'GetVersion', agg, vers, 
                                             'schema', str )
                    self.assertKeyValueType( 'GetVersion', agg, vers, 
                                             'namespace', str )
                    self.assertKeyValueType( 'GetVersion', agg, vers, 
                                             'extensions', list )

                try:
                    self.assertKeyValueLower( 'GetVersion', agg, vers, 
                                         'type', exp_type )
                    self.assertKeyValueLower( 'GetVersion', agg, vers, 
                                         'version', exp_num )
                    ad = True
                except:
                    pass
                self.assertKeyValueType( 'GetVersion', agg, vers, 
                                         'extensions', list )
            self.assertTrue( ad,
                        "Return from 'GetVersion' at %s " \
                        "expected to have entry " \
                        "'geni_ad_rspec_versions' of " \
                        "'type'=%s and 'value'=%s" \
                        "but did not." 
                        % (agg, exp_type, exp_num) )


            if self.options_copy.api_version == 3:
                cred_types = self.assertReturnKeyValueType( 
                    'GetVersion', agg, value, 
                    'geni_credential_types', 
                    list )
                hasSfa = False
                for creds in cred_types:
                    geni_type = self.assertReturnKeyValueType( 
                        'GetVersion', agg, creds, 
                        'geni_type', str)
                    geni_version = self.assertReturnKeyValueType( 
                        'GetVersion', agg, creds, 
                        'geni_version', str )
                    if geni_type == 'geni_sfa' and (geni_version == '2' or geni_version == '3'):
                        hasSfa = True
                        continue
                self.assertTrue( hasSfa,
                        "Return from 'GetVersion' at %s " \
                        "expected to have at least one entry " \
                        "'geni_credential_types' of " \
                        "'geni_type'='sfa' and 'geni_version'= 3 (or 2) " \
                        "but did not." 
                        % (agg) )

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
        (text, usercredstruct) = self.call(omniargs, self.options_copy)

        if self.options_copy.api_version >= 3:
            geni_type, geni_version, usercred = self.assertUserCred(usercredstruct)
        else:
            usercred = usercredstruct
            self.assertStr( usercred,
                        "Return from 'getusercred' " \
                            "expected to be string " \
                            "but instead returned: %r" 
                        % (usercred))
            # Test if file is XML 
            self.assertTrue(rspec_util.is_wellformed_xml( usercred ),
                        "Return from 'getusercred' " \
                        "expected to be XML " \
                        "but instead returned: \n" \
                        "%s\n" \
                        "... edited for length ..." 
                        % (usercred[:100]))

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
        self.assertRaises(NotDictAssertionError, self.subtest_generic_ListResources, slicename=slicelist[(i+1)%num_slices], slicecred=slicecred)


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
    # def test_ListResources_delegatedSliceCred(self):
    #     """test_ListResources_delegatedSliceCred: Passes if 'ListResources' succeeds with a delegated slice credential. Override the default slice credential using --delegated-slicecredfile"""
    #     # Check if slice credential is delegated.
    #     xml = self.file_to_string( self.options_copy.delegated_slicecredfile )
    #     self.assertTrue( self.is_delegated_cred(xml), 
    #                    "Slice credential is not delegated " \
    #                    "but expected to be. " )
    #     slice_name = self.get_slice_name_from_cred( xml )                
    #     self.assertTrue( slice_name,
    #                    "Credential is not a slice credential " \
    #                    "but expected to be: \n%s\n\n<snip> " % xml[:100] )
    #     # Run slice credential
    #     self.subtest_ListResources(
    #        slicename=slice_name,
    #        slicecredfile=self.options_copy.delegated_slicecredfile,
    #        typeOnly=True)
    #     self.success = True

    def test_ListResources_untrustedCredential(self):
        """test_ListResources_untrustedCredential: Passes if 'ListResources' FAILS to return an advertisement RSpec when using a credential from an untrusted Clearinghouse.
        """
        # Call listresources with this credential
        # We expect this to fail
        # self.subtest_ListResources(usercred=invalid_usercred) 
        # with slicename left to the default
        self.assertRaises(NotDictAssertionError, self.subtest_ListResources, usercredfile=self.options_copy.untrusted_usercredfile)
        self.success = True

    def subtest_Describe( self,  slicename=None, slicecred=None, usercred=None, usercredfile=None, slicecredfile=None, typeOnly=False, ):
        return self.subtest_query_rspec( AMAPI_call="Describe", slicename=slicename, slicecred=slicecred, usercred=usercred, usercredfile=usercredfile, slicecredfile=slicecredfile, typeOnly=typeOnly )

    def subtest_ListResources( self,  slicename=None, slicecred=None, usercred=None, usercredfile=None, slicecredfile=None, typeOnly=False, ):
        return self.subtest_query_rspec( AMAPI_call="ListResources", slicename=slicename, slicecred=slicecred, usercred=usercred, usercredfile=usercredfile, slicecredfile=slicecredfile, typeOnly=typeOnly )

    def subtest_query_rspec(self, AMAPI_call="ListResources", slicename=None, slicecred=None, usercred=None, usercredfile=None, slicecredfile=None, typeOnly=False, ):
        if not slicecred:
            self.assertTrue( self.checkAdRSpecVersion() )

        # Check to see if 'rspeclint' can be found before doing the hard (and
        # slow) work of calling ListResources at the aggregate
        if self.options_copy.rspeclint:
            rspec_util.rspeclint_exists()

        self.options_copy.omnispec = False # omni will complain if both true
        if slicename:
            rspec_namespace = self.manifest_namespace
            rspec_schema = self.manifest_schema
        else:
            rspec_namespace = self.ad_namespace
            rspec_schema = self.ad_schema
        
        omniargs = [] 
        
        # AMAPI_call = "ListResources"
        # if slicename and (self.options_copy.api_version >= 3):
        #     # AM API v3 Describe(slicename)
        #     AMAPI_call = "Describe"            
        #     omniargs = omniargs + ["describe", str(slicename)]
        # if slicename and (self.options_copy.api_version < 3):
        #     # AM API v1 and v2 ListResources(slicename)
        #     omniargs = omniargs + ["listresources", str(slicename)]
        # else:
        #     # AM API v1-v3 ListResources()
        #     omniargs = omniargs + ["listresources"]

        if slicename:
            omniargs = omniargs + [AMAPI_call, str(slicename)]
        else:
            omniargs = omniargs + [AMAPI_call]


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
            (text, ret_dict) = self.call(omniargs, self.options_copy)
        elif slicecredfile:
            omniargs = omniargs + ["--slicecredfile", slicecredfile] 
            (text, ret_dict) = self.call(omniargs, self.options_copy)
        else:
            (text, ret_dict) = self.call(omniargs, self.options_copy)

        pprinter = pprint.PrettyPrinter(indent=4)

        self.assertDict(ret_dict,
                       "Call to '%s' failed or not possible " \
                        "but expected to succeed. " \
                        "Error returned:\n %s"
                        % (AMAPI_call, text))

        # An empty dict indicates a misconfiguration!
        self.assertTrue(ret_dict,
                        "Return from '%s' " \
                        "expected to contain dictionary keyed by aggregates " \
                        "but instead returned empty dictionary. " \
                        "This indicates there were no aggregates checked. " \
                        "Look for misconfiguration." % (AMAPI_call) )

        if AMAPI_call == "Describe":            
            # AM API v3 Describe( slicename )
            for agg, indAgg in ret_dict.items():
                err_code, msg = self.assertCodeValueOutput( AMAPI_call, agg, 
                                                            indAgg )    
                self.assertSuccess( err_code )
                if err_code == SUCCESS:
                    # value only required if it is successful
                    retVal = indAgg['value']
                    numslivers, rspec = self.assertDescribeReturn( agg, retVal )
                    self.assertRspec( AMAPI_call, rspec, 
                                      rspec_namespace, rspec_schema, 
                                      self.options_copy.rspeclint)
                    self.assertRspecType( rspec, 'manifest', typeOnly=typeOnly)
        else:
            # AM API v1-v3 ListResources() and 
            # AM API v1-v2 ListResources( slicename )
            # but not AM API v3 Describe() <-- which is covered above
            for ((agg_name, agg_url), rspec) in ret_dict.items():
                if self.options_copy.api_version >= 2:
                    err_code, msg = self.assertCodeValueOutput( AMAPI_call, 
                                                                agg_url, rspec )
                    self.assertSuccess( err_code )
                    rspec = rspec['value']
                self.assertRspec( AMAPI_call, rspec, 
                                  rspec_namespace, rspec_schema, 
                                  self.options_copy.rspeclint)

                if slicename:
                    self.assertRspecType( rspec, 'manifest', typeOnly=typeOnly)
                else:
                    self.assertRspecType( rspec, 'advertisement', typeOnly=typeOnly)

                if self.options_copy.geni_available:
                    self.assertTrue(rspec_util.rspec_available_only( rspec, 
                                                         namespace=rspec_namespace, 
                                                         schema=rspec_schema, 
                                                         version=self.RSpecVersion() ),
                                "Return from '%s' at aggregate '%s' " \
                                "expected to only include available nodes " \
                                "but did not. Return was: " \
                                "\n%s\n" \
                                "... edited for length ..."
                                % (AMAPI_call, agg_url, rspec[:100]))
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

        numslivers, manifest = self.subtest_generic_CreateSliver( slicename )
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
                                               self.options_copy.bound )

            time.sleep(self.options_copy.sleep_time)
            self.subtest_generic_SliverStatus( slicename )        

            # in v1/v2 call ListResources(slicename)
            # in v3 call Describe(slicename)
            manifest2 = self.subtest_generic_ListResources( slicename=slicename )
            # in v3 ListResources(slicename) should FAIL
## Should this succeed by giving an advertisement? Or FAIL as shown?
            if self.options_copy.api_version >= 3:
                self.options_copy.devmode = True   
                # Seems like we should be checking for something more here?
                self.assertRaises(NotSuccessError, 
                                  self.subtest_ListResources,
                                  slicename=slicename )
                self.assertRaises(NotSuccessError, 
                                  self.subtest_Describe,
                                  slicename=None )

                self.options_copy.devmode = False   
            self.assertRspecType( manifest2, 'manifest')
            self.assertRspec( "ListResources", manifest2, 
                              rspec_namespace, rspec_schema,
                              self.options_copy.rspeclint )
            # Make sure the Manifest returned the nodes identified in
            # the Request
            self.assertManifestMatchesRequest( request, manifest2, 
                                               self.RSpecVersion(),
                                               self.options_copy.bound )

            # Attempting to CreateSliver again should fail or return a
            # manifest
            if not self.options_copy.strict:
                # if --less-strict, then accept a returned error
                if self.options_copy.api_version == 3:
                    self.assertRaises(NotSuccessError, 
                                      self.subtest_generic_CreateSliver, 
                                      slicename )
                elif self.options_copy.api_version == 2:
                    # Be more specific when we can
                    self.assertRaises(AMAPIError, 
                                      self.subtest_generic_CreateSliver, 
                                      slicename )
                else:
                    # This is a little generous, as this error is
                    # raised for many reasons
                    self.assertRaises(NotNoneAssertionError, 
                                      self.subtest_generic_CreateSliver, 
                                      slicename )
            else:
                # if --more-strict
                # CreateSliver should return an RSpec containing no
                # resources
                numslivers, manifest = self.subtest_generic_CreateSliver( 
                    slicename )
                self.assertTrue( rspec_util.is_wellformed_xml( manifest ),
                  "Manifest RSpec returned by 'CreateSliver' on slice '%s' " \
                  "expected to be wellformed XML file " \
                  "but was not. Return was: " \
                  "\n%s\n" \
                  "... edited for length ..."
                  % (slicename, manifest[:100]))                         
                self.assertTrue( rspec_util.has_child( manifest ),
                  "Manifest RSpec returned by 'CreateSliver' on slice '%s' " \
                  "expected to be non-empty " \
                  "but was empty. Return was: " \
                  "\n%s\n" \
                  "... edited for length ..."
                  % (slicename, manifest[:100]))

            time.sleep(self.options_copy.sleep_time)
            # RenewSliver for 5 mins, 2 days, and 5 days
#            self.subtest_generic_RenewSliver_many( slicename )
        except:
            raise
        finally:
            time.sleep(self.options_copy.sleep_time)
            self.subtest_generic_DeleteSliver( slicename )

        # Test SliverStatus, ListResources and DeleteSliver on a deleted sliver
        self.subtest_CreateSliverWorkflow_failure( slicename )

        if not self.options_copy.reuse_slice_name:
            self.subtest_deleteslice( slicename )
            
    def test_AllocateWorkflow( self, slicename='foobar'):
        # THIS IS TEMPORARY TEST
        try:
            # Start fresh; Delete existing slivers if they already exist
            self.subtest_Delete( slicename )
        except:
            pass
#        self.subtest_createslice( slicename )
        try:
            self.subtest_Allocate( slicename )
            self.subtest_Provision( slicename )
            
            self.subtest_Renew_many( slicename )
            self.subtest_PerformOperationalAction( slicename, 'geni_start' )
            self.subtest_Renew_many( slicename )
        except:
            raise
        finally:
            self.subtest_Delete( slicename )

    def test_ProvisionWorkflow( self, slicename='foobar'):
        self.subtest_Allocate( slicename )
#        self.subtest_Provision( slicename )
#        self.subtest_Renew( slicename )
#        self.subtest_Delete( slicename )
    def test_PerformOperationalActionWorkflow( self, slicename='foobar'):
        self.subtest_Allocate( slicename )
#        self.subtest_Provision( slicename )
#        self.subtest_PerformOperationalAction( slicename, 'geni_start' )
#        self.subtest_PerformOperationalAction( slicename, 'geni_restart' )
#        self.subtest_PerformOperationalAction( slicename, 'geni_stop' )
#        self.subtest_Delete( slicename )


    def subtest_MinCreateSliverWorkflow(self, slicename=None):
        if slicename==None:
            slicename = self.create_slice_name()

        # if reusing a slice name, don't create (or delete) the slice
        if not self.options_copy.reuse_slice_name:
            self.subtest_createslice( slicename )
            time.sleep(self.options_copy.sleep_time)

        # cleanup up any previous failed runs
        try:
            self.subtest_generic_DeleteSliver( slicename )
        except:
            pass

        manifest = self.subtest_generic_CreateSliver( slicename )
        with open(self.options_copy.rspec_file) as f:
            req = f.readlines()
            request = "".join(req)             
        try:
            self.subtest_generic_DeleteSliver( slicename )
        except:
            pass

        if not self.options_copy.reuse_slice_name:
            self.subtest_deleteslice( slicename )


    def test_CreateSliverWorkflow_fail_notexist( self ):
        """test_CreateSliverWorkflow_fail_notexist:  Passes if the sliver creation workflow fails when the sliver has never existed."""
        slicename = self.create_slice_name_uniq(prefix='non')        

        # Create slice so that lack of existance of the slice doesn't
        # cause the AM test to fail
        self.subtest_createslice( slicename )
        # Test SliverStatus, ListResources and DeleteSliver on a
        # non-existant sliver
        self.subtest_CreateSliverWorkflow_failure( slicename )
        self.success = True

    def subtest_CreateSliverWorkflow_failure( self, slicename ):
        self.assertRaises((AMAPIError, NotSuccessError, NotDictAssertionError, NoSliceCredError), 
                          self.subtest_generic_SliverStatus, slicename )
        
        if not self.options_copy.strict:
            # if --less-strict, then accept a returned error
            self.assertRaises((AMAPIError, NotSuccessError, NotDictAssertionError), self.subtest_generic_ListResources, slicename )
        else:
            # if --more-strict
            # ListResources should return an RSpec containing no resources
            manifest = self.subtest_generic_ListResources( slicename )
            self.assertTrue( rspec_util.is_wellformed_xml( manifest ),
                  "Manifest RSpec returned by 'ListResources' on slice '%s' " \
                             "expected to be wellformed XML file " \
                             "but was not. Return was: " \
                             "\n%s\n" \
                             "... edited for length ..."
                         % (slicename, manifest[:1000]))                         
            self.assertFalse( rspec_util.has_child( manifest ),
                  "Manifest RSpec returned by 'ListResources' on slice '%s' " \
                              "expected to be empty " \
                              "but was not. Return was: " \
                              "\n%s\n" \
                              "... edited for length ..."
                          % (slicename, manifest[:1000]))
        
        # Also repeated calls to DeleteSliver should now fail
        try:
            self.assertRaises((AMAPIError, AssertionError, NoSliceCredError), 
                              self.subtest_generic_DeleteSliver, slicename )
        # Or succeed by returning True
        except AssertionError:
            self.subtest_generic_DeleteSliver( slicename )


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
                time.sleep(self.options_copy.sleep_time)
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
                time.sleep(self.options_copy.sleep_time)
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
            
            for i in xrange(num_slices):
                time.sleep(self.options_copy.sleep_time)
                self.subtest_SliverStatus( slicenames[i] )        

            # Make sure you can't list resources on other slices
            # using the wrong slice cred
            self.subtest_ListResources_wrongSlice( slicenames )        

            time.sleep(self.options_copy.sleep_time)

            for i in xrange(num_slices):
                manifest2.append("")
                manifest2[i] = "".join(self.subtest_generic_ListResources( slicename=slicenames[i] ))
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



                # Make sure the Manifest returned the nodes identified
                # in the Request
                if rspec_util.has_child_node( manifest2[i], self.RSpecVersion()):
                    if self.options_copy.bound:
                        self.assertCompIDsEqual( request[i], 
                                             manifest2[i], 
                                             self.RSpecVersion(), 
                                 "Request RSpec and Manifest RSpec " \
                                 "returned by 'ListResources' on slice '%s' " \
                                 "expected to have same component_ids " \
                                 "but did not." % slicenames[i] )
                    self.assertClientIDsEqual( request[i], 
                                             manifest2[i], 
                                             self.RSpecVersion(), 
                                 "Request RSpec and Manifest RSpec " \
                                 "returned by 'ListResources' on slice '%s' " \
                                 "expected to have same client_ids " \
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

    def subtest_Renew_many( self, slicename ):
        now = datetime.datetime.utcnow()
        fivemin = (now + datetime.timedelta(minutes=5)).isoformat()            
        twodays = (now + datetime.timedelta(days=2)).isoformat()            
        fivedays = (now + datetime.timedelta(days=5)).isoformat()           
        sixdays = (now + datetime.timedelta(days=6)).isoformat()            
        self.subtest_RenewSlice( slicename, sixdays )
        time.sleep(self.options_copy.sleep_time)
#        self.subtest_RenewSliver( slicename, fivemin )
#        time.sleep(self.options_copy.sleep_time)
        self.subtest_Renew( slicename, twodays )
        time.sleep(self.options_copy.sleep_time)
        self.subtest_Renew( slicename, fivedays )


    def subtest_Renew(self, slice_name, newtime):
        retVal = self.subtest_AMAPIv3CallNoRspec( slice_name, 
                                        omni_method='renew', 
                                        AMAPI_call="Renew",
                                        newtime=newtime)
        return retVal

    def subtest_Provision(self, slice_name):
        return self.subtest_AMAPIv3CallNoRspec( slice_name, 
                                        omni_method='provision', 
                                        AMAPI_call="Provision")
    def subtest_Status(self, slice_name):
        return self.subtest_AMAPIv3CallNoRspec( slice_name, 
                                        omni_method='status', 
                                        AMAPI_call="Status")

    def subtest_PerformOperationalAction(self, slice_name, command):
        return self.subtest_AMAPIv3CallNoRspec( slice_name, 
                                        omni_method='performoperationalaction', 
                                        AMAPI_call="PerformOperationalAction",
                                                command=command)
    def subtest_Delete(self, slice_name):
        return self.subtest_AMAPIv3CallNoRspec( slice_name, 
                                        omni_method='delete', 
                                        AMAPI_call="Delete")

    def subtest_AMAPIv3CallNoRspec( self, slicename, 
                                    omni_method='provision', 
                                    AMAPI_call="Provision",
                                    sliverlist=None, newtime=None, 
                                    command=None):
        self.assertTrue(omni_method in ['renew', 'provision', 'status',
                                        'performoperationalaction', 'delete'],
                        "omni_method is %s and not one of " \
                        "'renew', 'provision', 'status', " \
                        "'performoperationalaction', or 'delete'." % omni_method)
            
        self.assertTrue( AMAPI_call in ['Renew', 'Provision', 'Status', 'PerformOperationalAction','Delete'],
                        "AMAPI_call is %s and not one of " \
                        "'Renew', 'Provision', 'Status', " \
                        "'PerformOperationalAction', or 'Delete'." % AMAPI_call)

        if AMAPI_call is "Renew":
            omniargs = [omni_method, slicename, newtime] 
        elif AMAPI_call is "PerformOperationalAction":
            omniargs = [omni_method, slicename, command] 
        else:
            omniargs = [omni_method, slicename]

        if sliverlist:
            print "Not handling lists of slivers yet"
#            omniargs = [omni_method, slicename]
        text, allAggs = self.call(omniargs, self.options_copy)
        for agg, indAgg in allAggs.items():
            err_code, msg = self.assertCodeValueOutput( AMAPI_call, agg, indAgg )
            retVal2 = None
            self.assertSuccess( err_code )
            if err_code == SUCCESS:
                # value only required if it is successful
                retVal = indAgg['value']
                if AMAPI_call is "Renew":
                    retVal2 = self.assertRenewReturn( agg, retVal )
                    numSlivers = retVal2
                elif AMAPI_call is "Provision":
                    retVal2 = self.assertProvisionReturn( agg, retVal )
                    numSlivers, manifest = retVal2
                elif AMAPI_call is "Status":
                    retVal2 = self.assertStatusReturn( agg, retVal )
                    numSlivers = retVal2
                elif AMAPI_call is "PerformOperationalAction":
                    retVal2 = self.assertPerformOperationalActionReturn( agg, retVal )
                    numSlivers = retVal2
                elif AMAPI_call is "Delete":
                    retVal2 = self.assertDeleteReturn( agg, retVal )
                    numSlivers = retVal2
                else:
                    print "Shouldn't get here"

                self.assertTrue( numSlivers > 0,
                                 "Return from '%s' " \
                                     "expected to list slivers " \
                                     "but did not"
                                 % (AMAPI_call))
        return retVal2


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
        self.assertRspec( "CreateSliver", manifest, 
                          self.manifest_namespace,
                          self.manifest_schema,
                          self.options_copy.rspeclint)
        return 1, manifest

    def subtest_Allocate(self, slice_name):
        return self.subtest_CreateSliverPiece( slice_name, 
                                        omni_method='allocate', 
                                        AMAPI_call="Allocate")

    def subtest_CreateSliverPiece(self, slice_name, 
                                  omni_method='createsliver', 
                                  AMAPI_call="CreateSliver"):
        """Handle CreateSliver and Allocate both of which take in a request RSpec and return a manifest RSpec.
        """
        self.assertTrue(omni_method in ['createsliver', 'allocate'],
                        "omni_method is %s and not one of " \
                            " 'createsliver' or 'allocate'." % omni_method)
            
        self.assertTrue( AMAPI_call in ['CreateSliver', 'Allocate'],
                        "AMAPI_call is %s and not one of " \
                            " 'CreateSliver' or 'Allocate'." % AMAPI_call)

                                       
        self.assertTrue( self.checkRequestRSpecVersion() )

        # Check for the existance of the Request RSpec file
        self.assertTrue( os.path.exists(self.options_copy.rspec_file),
                         "Request RSpec file, '%s' for '%s' call " \
                             "expected to exist " \
                             "but does not." 
                         % (self.options_copy.rspec_file, AMAPI_call) )
        
        # CreateSliver() or Allocate()
        omniargs = [omni_method, slice_name, str(self.options_copy.rspec_file)] 
        text, allAggs = self.call(omniargs, self.options_copy)

        for agg, indAgg in allAggs.items():
            self.assertIsNotNone(indAgg,
                              "Return from '%s' " \
                              "expected to be XML file " \
                              "but instead nothing returned. AM returned:\n %s"
                                 % (AMAPI_call, text))
            # Check that each aggregate returned standard: 
            #    code, value, and output
            err_code, msg = self.assertCodeValueOutput( AMAPI_call, agg, 
                                                        indAgg )
            self.assertSuccess( err_code )

            if AMAPI_call is "CreateSliver":
                manifest = indAgg
                self.assertRspec( manifest )
                retVal2 = manifest 
            elif AMAPI_call is "Allocate":
                retVal = indAgg['value']
                # FIX aggregate reference
                numSlivers, manifest = self.assertAllocateReturn( "FOOBAR", 
                                                                  retVal )
                self.assertTrue( numSlivers > 0,
                                 "Return from '%s' " \
                                     "expected to list allocated slivers " \
                                     "but did not instead returned: \n" \
                                     "%s\n" \
                                     "... edited for length ..." 
                                 % (AMAPI_call, manifest[:100]))

                retVal2 = manifest, numSlivers 

            self.assertTrue( rspec_util.has_child( manifest ),
                      "Manifest RSpec returned by '%s' on slice '%s' " \
                      "expected to be non-empty " \
                      "but was empty. Return was: " \
                      "\n%s\n" \
                      "... edited for length ..."
                      % (AMAPI_call, slice_name, manifest[:100]))


        return retVal2


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
                            "Return from 'SliverStatus' for Aggregate %s " \
                            "expected to be XMLRPC struct " \
                            "but instead returned: \n" \
                            "%s\n" \
                            "... edited for length ..." 
                            % (aggName, status))
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
            self.assertRaises((AMAPIError, NotSuccessError, NotNoneAssertionError),
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
            self.assertRaises((AMAPIError, NotSuccessError, NotNoneAssertionError),
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

        self.assertRaises((AMAPIError, NotSuccessError, NotNoneAssertionError),
                              self.subtest_MinCreateSliverWorkflow, slice_name)
        self.success = True


    # Provide simple mapping for all v1, v2, and v3 calls
    def subtest_generic_ListResources( self, slicename ):
        if self.options_copy.api_version <= 2:
            return self.subtest_ListResources( slicename )
        elif self.options_copy.api_version >= 3:
            return self.subtest_Describe( slicename )

    def subtest_generic_DeleteSliver( self, slicename ):
        if self.options_copy.api_version <= 2:
            self.subtest_DeleteSliver( slicename )
        elif self.options_copy.api_version >= 3:
            self.subtest_Delete( slicename )
    def subtest_generic_CreateSliver( self, slicename ):
        """For v1 and v2, call CreateSliver().  For v3, call
        Allocate(), Provision(), and then
        PerformOperationalAction('geni_start').
        """
        if self.options_copy.api_version <= 2:
            numslivers, manifest = self.subtest_CreateSliver( slicename )
        elif self.options_copy.api_version == 3:
            self.subtest_Allocate( slicename )
            numslivers, manifest = self.subtest_Provision( slicename )
            self.subtest_PerformOperationalAction( slicename, 'geni_start' )
            self.options_copy.devmode = True   
            self.assertRaises(NotSuccessError,
                              self.subtest_PerformOperationalAction, 
                              slicename, '' )
            self.options_copy.devmode = False  
            self.assertRaises(NotSuccessError, 
                              self.subtest_PerformOperationalAction, 
                              slicename, 'random_action' )

        return numslivers, manifest
    def subtest_generic_SliverStatus( self, slicename ):
        if self.options_copy.api_version <= 2:
            self.subtest_SliverStatus( slicename )
        elif self.options_copy.api_version == 3:
            self.subtest_Status( slicename )

    def subtest_generic_RenewSliver_many( self, slicename ):
        if self.options_copy.api_version <= 2:
            self.subtest_RenewSliver_many( slicename )
        elif self.options_copy.api_version == 3:
            self.subtest_Renew_many( slicename )

    @classmethod
    def accept_parser( cls, parser=omni.getParser(), usage=None):
        parser.add_option( "--reuse-slice", 
                           action="store", type='string', dest='reuse_slice_name', 
                           help="Use slice name provided instead of creating/deleting a new slice")
        parser.add_option( "--rspec-file", 
                           action="store", type='string', 
                           dest='rspec_file', default=REQ_RSPEC_FILE,
                           help="In CreateSliver tests, use _bound_ request RSpec file provided instead of default of '%s'" % REQ_RSPEC_FILE )

        parser.add_option( "--bad-rspec-file", 
                           action="store", type='string', 
                           dest='bad_rspec_file', default=BAD_RSPEC_FILE,
                           help="In negative CreateSliver tests, use request RSpec file provided instead of default of '%s'" % BAD_RSPEC_FILE )

        parser.add_option("--untrusted-usercredfile", default='untrusted-usercred.xml', metavar="UNTRUSTED_USER_CRED_FILENAME",
                      help="Name of an untrusted user credential file to use in test: test_ListResources_untrustedCredential")


        parser.add_option( "--rspec-file-list", 
                           action="store", type='string', nargs=3, 
                           dest='rspec_file_list', default=(REQ_RSPEC_FILE_1,REQ_RSPEC_FILE_2,REQ_RSPEC_FILE_3),
                           help="In multi-slice CreateSliver tests, use _bound_ request RSpec files provided instead of default of '(%s,%s,%s)'" % (REQ_RSPEC_FILE_1,REQ_RSPEC_FILE_2,REQ_RSPEC_FILE_3) )

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
        parser.add_option( "--pure-v1", 
                           action="store_true",
                           default=False,
                           help="Allows some tests to check for AM API v1 compliance without Change Set A.  -V must be set to '1'." )
        parser.add_option("--delegated-slicecredfile", default='delegated.xml', metavar="DELEGATED_SLICE_CRED_FILENAME",
                          help="Name of a delegated slice credential file to use in test: test_ListResources_delegatedSliceCred")
        parser.add_option( "--un-bound", 
                           action="store_false",
                           dest='bound',
                           default=True,
                           help="RSpecs are unbound (requesting some resources, not a particular resource)" )


        parser.remove_option("-t")
        parser.set_defaults(logoutput='acceptance.log')

        argv = Test.unittest_parser(parser=parser, usage=usage)

        return argv



if __name__ == '__main__':
    usage = "\n      %s -a am-undertest " \
            "\n      Also try --vv" \
            "\n\n     Run an individual test using the following form..." \
            "\n     %s -a am-undertest Test.test_GetVersion" % (sys.argv[0], sys.argv[0])
    # Include default Omni_unittest command line options
    argv = Test.accept_parser(usage=usage)

    # Invoke unit tests as usual
    unittest.main()


