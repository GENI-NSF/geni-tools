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
from gcf.omnilib.util import OmniError, NoSliceCredError, RefusedError, AMAPIError, naiveUTC
import gcf.omnilib.util.json_encoding as json_encoding
import gcf.omnilib.util.credparsing as credparsing
from gcf.sfa.trust.credential import Credential

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

class Test(ut.OmniUnittest):
    """Acceptance tests for GENI AM API."""

    def setUp( self ):
        ut.OmniUnittest.setUp(self)
        # Set up RSpec type/version
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
        self.logger = omni.configure_logging(self.options_copy)

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
        omniargs = ['getversion', "-o", "--ForceUseGetVersionCache"]
        self.logger.info("\n=== doing checkRSpecVersion ===")
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
        """test_GetVersion: Passes if a 'GetVersion' returns an XMLRPC struct containing 
        'geni_api' and other parameters defined in Change Set A or APIv2 or APIv3, as appropriate.
        """
        # Do AM API call
        omniargs = ["getversion"]
        self.logger.info("\n=== Test.test_GetVersion ===")
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

            # Check v3+ AM optional geni_single_allocation and geni_allocate
            if self.options_copy.api_version >= 3:
                self.assertGeniSingleAllocationIfExists( "GetVersion", agg, value )
                self.assertGeniAllocateIfExists( "GetVersion", agg, value )

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
                # V3 changed these to be required but possibly empty
                if self.options_copy.api_version >= 3:
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
            # End loop over advertised request rspec versions

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
                # V3 changed these to be required but possibly empty
                if self.options_copy.api_version >= 3:
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
            # End of loop over advertised ad rspec versions

            self.assertTrue( ad,
                        "Return from 'GetVersion' at %s " \
                        "expected to have entry " \
                        "'geni_ad_rspec_versions' of " \
                        "'type'=%s and 'value'=%s" \
                        "but did not." 
                        % (agg, exp_type, exp_num) )

            # Check v3+ AM advertises geni_sfa credential support
            if self.options_copy.api_version >= 3:
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
                    if geni_type == Credential.SFA_CREDENTIAL_TYPE \
                            and (geni_version == '2' or geni_version == '3'):
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
        self.logger.info("\n=== Test.test_ListResources ===")
        if self.options_copy.api_version > 1:
            self.options_copy.arbitrary_option = True
        # omni sets 'geni_compress' = True
        self.subtest_ListResources()
        self.success = True

    def test_ListResources_geni_compressed(self):
        """test_ListResources_geni_compressed: Passes if 'ListResources' returns an advertisement RSpec.
        """
        # omni sets 'geni_compressed' = True, override
        self.logger.info("\n=== Test.test_ListResources_geni_compressed ===")
        self.options_copy.geni_compressed = False
        self.subtest_ListResources()
        self.success = True

    def test_ListResources_geni_available(self):
        """test_ListResources_geni_available: Passes if 'ListResources' returns an advertisement RSpec.
        """
        # omni sets 'geni_available' = False, override
        self.logger.info("\n=== Test.test_ListResources_geni_available ===")
        self.options_copy.geni_available = True
        self.subtest_ListResources()
        self.success = True

    def subtest_Describe_geni_compressed(self, slicename):
        """test_Describe_geni_compressed: Passes if 'Describe' returns an advertisement RSpec.
        """
        # omni sets 'geni_compressed' = True, override
        self.options_copy.geni_compressed = False
        self.subtest_Describe( slicename=slicename )
        self.success = True

    def test_ListResources_badCredential_malformedXML(self):
        """test_ListResources_badCredential_malformedXML: Run ListResources with 
        a User Credential that is missing it's first character (so that it is invalid XML). """
        self.logger.info("\n=== Test.test_ListResources_badCredential_malformedXML. Should FAIL ===")
        self.subtest_ListResources_badCredential(self.removeFirstChar)
        self.success = True

    def test_ListResources_badCredential_alteredObject(self):
        """test_ListResources_badCredential_alteredObject: Run ListResources with 
        a User Credential that has been altered (so the signature doesn't match). """
        self.logger.info("\n=== Test.test_ListResources_badCredential_alteredObject. Should FAIL ===")
        self.subtest_ListResources_badCredential(self.alterSignedObject)
        self.success = True

    # FIXME: Would love to test supplying a list of credentials, 1 good and 1 bad,
    # but Omni doesn't support it yet

    def test_ListResources_badCredential_badtype(self):
        """test_ListResources_badCredential_badtype: Run ListResources in API v3+ with 
        a User Credential that says it is of a nonexistent type only: should fail """
        if self.options_copy.api_version < 3:
            self.success = True
            return

        # (1) Get the usercredential
        omniargs = ["getusercred", "-o"]
        self.logger.info("\n=== Test.test_ListResources_badCredential_badtype -- Should FAIL ===")
        (text, usercredstruct) = self.call(omniargs, self.options_copy)

        geni_type, geni_version, usercred = self.assertUserCred(usercredstruct)
        brokencredstruct = dict()
        brokencredstruct['geni_type'] = geni_type + "BROKEN"
        brokencredstruct['geni_version'] = geni_version
        brokencredstruct['geni_value'] = usercred
        self.options_copy.devmode = True
        self.assertRaises((NotSuccessError, NotDictAssertionError), self.subtest_ListResources, 
                          usercred=json.dumps(brokencredstruct, cls=json_encoding.DateTimeAwareJSONEncoder))
        self.options_copy.devmode = False

    def subtest_ListResources_slice_with_usercred(self, slicename):
        """test_ListResources_slice_with_usercred: Run ListResources with 
        a User Credential pretending to be the slice cred: should fail """
        # (1) Get the usercredential
        omniargs = ["getusercred", "-o"]
        self.logger.info("\n=== Test.test_ListResources_slice_with_usercred ===")
        (text, usercredstruct) = self.call(omniargs, self.options_copy)
        self.options_copy.devmode = True
        user_cred=json.dumps(usercredstruct, cls=json_encoding.DateTimeAwareJSONEncoder)
        if self.options_copy.api_version == 1:
            self.assertRaises((NotSuccessError, NotDictAssertionError, AMAPIError, NotNoneAssertionError), self.subtest_generic_ListResources, 
                          slicename=slicename,
                          slicecred=user_cred)
        else:
            self.assertRaises((NotSuccessError, NotDictAssertionError, AMAPIError), self.subtest_generic_ListResources, 
                          slicename=slicename,
                          slicecred=user_cred)
            
        self.options_copy.devmode = False

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
        """test_ListResources_badCredential: Passes if 'ListResources' FAILS to return 
        an advertisement RSpec when using a bad credential.
        """

        # (1) Get the usercredential
        omniargs = ["getusercred", "-o"]
        self.logger.info("\n=== Test.test_ListResources_badCredential ===")
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
        self.options_copy.devmode = True           
        if self.options_copy.api_version == 1:
            self.assertRaises((AMAPIError, NotSuccessError, NotDictAssertionError, NotNoneAssertionError), self.subtest_ListResources, 
                          usercred=broken_usercred)
        else:
            self.assertRaises((AMAPIError, NotSuccessError, NotDictAssertionError), self.subtest_ListResources, 
                          usercred=broken_usercred)            
        self.options_copy.devmode = False

    def subtest_ListResources_wrongSlice(self, slicelist):
        num_slices = len(slicelist)
        for i in xrange(num_slices):
            slice = slicelist[i]
            # (1) Get the slicecredential
            omniargs = ["getslicecred", slice, "-o"]
            self.logger.info("\n=== Test.test_ListResources_wrongSlice ===")
            (text, slicecredstruct) = self.call(omniargs, self.options_copy)

            if self.options_copy.api_version >= 3:
                tmpRetVal = self.assertSliceCred(slicecredstruct)
                self.assertIsNotNone( tmpRetVal )
                geni_type, geni_version, slicecred = tmpRetVal
            else:
                slicecred = slicecredstruct
                self.assertStr( slicecred,
                            "Return from 'getslicered' " \
                            "expected to be string " \
                            "but instead returned: %r" 
                        % (slicecred))
                # Test if file is XML 
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
        self.options_copy.devmode = True   
        if self.options_copy.api_version == 1:
            self.assertRaises((AMAPIError, NotSuccessError, NotDictAssertionError, NotNoneAssertionError), self.subtest_generic_ListResources, 
                          slicename=slicelist[(i+1)%num_slices], slicecred=slicecred)
        else:
            self.assertRaises((AMAPIError, NotSuccessError, NotDictAssertionError), self.subtest_generic_ListResources, 
                          slicename=slicelist[(i+1)%num_slices], slicecred=slicecred)
        self.options_copy.devmode = False

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

    def test_ListResources_untrustedCredential(self):
        """test_ListResources_untrustedCredential: Passes if 'ListResources' FAILS to 
        return an advertisement RSpec when using a credential from an untrusted Clearinghouse.
        """
        # Call listresources with this credential
        # We expect this to fail
        # with slicename left to the default
        self.logger.info("\n=== Test.test_ListResources_untrustedCredential - should FAIL ===")
        if self.options_copy.api_version == 1:
            self.assertRaises((AMAPIError, NotSuccessError, NotDictAssertionError, NotNoneAssertionError), self.subtest_ListResources, 
                              usercredfile=self.options_copy.untrusted_usercredfile)
        else:
            self.assertRaises((AMAPIError, NotSuccessError, NotDictAssertionError), self.subtest_ListResources, 
                              usercredfile=self.options_copy.untrusted_usercredfile)            
        self.success = True

    def subtest_Describe( self,  slicename=None, slicecred=None, usercred=None, 
                          usercredfile=None, slicecredfile=None, typeOnly=False,
                          sliverurns=[], expectedExpiration=None):
        return self.subtest_query_rspec( AMAPI_call="Describe", slicename=slicename, 
                                         slicecred=slicecred, usercred=usercred, usercredfile=usercredfile, 
                                         slicecredfile=slicecredfile, typeOnly=typeOnly, sliverurns=sliverurns, expectedExpiration=expectedExpiration )

    def subtest_ListResources( self,  slicename=None, slicecred=None, usercred=None, usercredfile=None, 
                               slicecredfile=None, typeOnly=False, ):
        return self.subtest_query_rspec( AMAPI_call="ListResources", slicename=slicename, 
                                         slicecred=slicecred, usercred=usercred, usercredfile=usercredfile, 
                                         slicecredfile=slicecredfile, typeOnly=typeOnly )

    def subtest_query_rspec(self, AMAPI_call="ListResources", slicename=None, slicecred=None, 
                            usercred=None, usercredfile=None, slicecredfile=None, typeOnly=False, sliverurns=[], expectedExpiration=None):
        if not slicecred:
            self.assertTrue( self.checkAdRSpecVersion() )
        else:
            self.assertTrue(self.checkRequestRSpecVersion())

        # Check to see if 'rspeclint' can be found before doing the hard (and
        # slow) work of calling ListResources at the aggregate
        if self.options_copy.rspeclint:
            rspec_util.rspeclint_exists()

        if slicename:
            rspec_namespace = self.manifest_namespace
            rspec_schema = self.manifest_schema
        else:
            rspec_namespace = self.ad_namespace
            rspec_schema = self.ad_schema
        
        omniargs = ["-o"] 
        
        if slicename:
            omniargs = omniargs + [AMAPI_call, str(slicename)]
        else:
            omniargs = omniargs + [AMAPI_call]

        for urn in sliverurns:
            omniargs = omniargs + ['-u', urn]

        # Force actual omni output to a file? Then to debug things
        # we'd need to save those files, and they might step on each other...
#        omniargs = omniargs + ['-o']
        
        if usercred and slicecred:
            with tempfile.NamedTemporaryFile() as f:
                # make a temporary file containing the user credential
                f.write( usercred )
                f.seek(0)
                # Keeping f open...
                with tempfile.NamedTemporaryFile() as f2:
                    # make a temporary file containing the slice credential
                    f2.write( slicecred )
                    f2.seek(0)
                    # keeping both files open...
                    omniargs = omniargs + ["--usercredfile", f.name] + ["--slicecredfile", f2.name] 
                    # run command here while temporary file is open
                    (text, ret_dict) = self.call(omniargs, self.options_copy)
        elif slicecred and not(usercred):
            with tempfile.NamedTemporaryFile() as f2:
                # make a temporary file containing the slice credential
                f2.write( slicecred )
                f2.seek(0)
                # Keeping f2 open...
                omniargs = omniargs + ["--slicecredfile", f2.name] 
                (text, ret_dict) = self.call(omniargs, self.options_copy)
        elif usercred and not(slicecred):
            with tempfile.NamedTemporaryFile() as f:
                # make a temporary file containing the user credential
                f.write( usercred )
                f.seek(0)
                # Keeping f open...
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
            # AM API v3+ Describe( slicename )
            for agg, indAgg in ret_dict.items():
                err_code, msg = self.assertCodeValueOutput( AMAPI_call, agg, 
                                                            indAgg )    
                self.assertSuccess( err_code )
                # value only required if it is successful
                retVal = indAgg['value']
                slivers, rspec = self.assertDescribeReturn( agg, retVal)
                numslivers = len(slivers)
                self.assertRspec( AMAPI_call, rspec, 
                                  rspec_namespace, rspec_schema, 
                                  self.options_copy.rspeclint)
                self.assertRspecType( rspec, 'manifest', typeOnly=typeOnly)
                if sliverurns:
                    reported_urns = []
                    for sliver in slivers:
                        reported_urns.append( sliver['geni_sliver_urn'] )
                    self.assertTrue( set(reported_urns)==set(sliverurns),
                             "Return from '%s' at aggregate '%s' " \
                             "expected to only include requested sliver urns " \
                             "but did not. \nRequested slivers were: " \
                             "\n%s\n" \
                             "Returned slivers were: " \
                             "\n%s" 
                             % (AMAPI_call, agg, str(sliverurns), str(reported_urns)))
                # else it should be true that all slivers in the slice are reported

        else:
            # AM API v1-v3 ListResources() and 
            # AM API v1-v2 ListResources( slicename )
            # but not AM API v3 Describe() <-- which is covered above
            for (agg_url, rspec) in ret_dict.items():
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
        """test_CreateSliver: Passes if the sliver creation workflow succeeds.  
        Use --rspec-file to replace the default request RSpec."""
        self.logger.info("\n=== Test.test_CreateSliver ===")
        self.subtest_CreateSliverWorkflow()
        self.success = True

    def subtest_CreateSliverWorkflow(self, slicename=None, doProvision=True, doPOA=True):
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

        sliceExpiration = self.getSliceExpiration( slicename )
        numslivers, manifest, slivers = self.subtest_generic_CreateSliver( slicename, doProvision, doPOA, expectedExpiration=sliceExpiration )
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

            time.sleep(self.options_copy.sleep_time)
            self.subtest_generic_SliverStatus( slicename )        

            # in v1/v2 call ListResources(slicename)
            # in v3 call Describe(slicename)
            manifest2 = self.subtest_generic_ListResources( slicename=slicename )
            # in v3 ListResources(slicename) should FAIL
## Should this succeed by giving an advertisement? Or FAIL as shown?

            # Test passing a usercred as though it is a slice cred -- should fail
            self.subtest_ListResources_slice_with_usercred(slicename)

            if self.options_copy.api_version >= 3:
                self.options_copy.devmode = True   
                # Seems like we should be checking for something more
                # here?
                # NotSuccess would be if teh AM
                # refused. WrongRspecType would be if the AM ignored
                # the slice_urn option and treated this as an Ad request.
                self.assertRaises((NotSuccessError, WrongRspecType), 
                                  self.subtest_ListResources,
                                  slicename=slicename )
                self.assertRaises(NotSuccessError, 
                                  self.subtest_Describe,
                                  slicename=None )
                self.options_copy.devmode = False   

                self.subtest_Describe_geni_compressed( slicename )
                
                self.options_copy.devmode = True   
                # Call describe on an individual sliver
                # Then Call Describe() on a urn of type 'node' not 'sliver' - should fail
                if len(slivers)>0:
                    sliver = slivers[0]
                    sliver_urn = sliver['geni_sliver_urn']
                    allsliverurns = []
                    for sliveritem in slivers:
                        allsliverurns.append(sliveritem['geni_sliver_urn'])

                    # Make sure can call Status on an individual sliver
                    self.subtest_Status(slicename, sliverlist = [sliver_urn])

                    # If not geni_single_allocation, then Renew, Describe, Provision, POA on an 
                    # individual sliver should work. Else, should need all slivers
                    geni_single_allocation = False

                    # 1: Get GetVersion Result
                    omniargs = ["getversion", "-o", "--ForceUseGetVersionCache"]
                    (text, ret_dict) = self.call(omniargs, self.options_copy)
                    self.assertTrue(len(ret_dict.keys()) > 0,
                                    "GetVersion returned nothing")
                    aggName = ret_dict.keys()[0]

                    self.assertDict( ret_dict[aggName], "GetVersion return malformed" )
                    aggVersion = self.assertReturnKeyValueType( "GetVersion", aggName, 
                                                                ret_dict[aggName], 'value', dict )

                    # 2: Pull geni_single_allocation value
                    geni_single_allocation = self.assertGeniSingleAllocationIfExists( "GetVersion", aggName, aggVersion )
                    if geni_single_allocation:
#                        print "AM does geni_single_allocation: testing Renew/Describe with all sliver URNs at once"
                        sliverurns = allsliverurns
                    else:
#                        print "AM does NOT do geni_single_allocation: testing Renew/Describe with one sliver URN"
                        sliverurns = [sliver_urn]

                    now = ut.OmniUnittest.now_in_seconds()
                    fivemin = (now + datetime.timedelta(minutes=5)).isoformat()            
                    self.subtest_Renew(slicename, newtime=fivemin, sliverlist=sliverurns)

                    # FIXME: Try Provision or POA on an individual sliver?

                    sliver_urn2 = re.sub('\+sliver\+', '+node+', sliver_urn)
                    self.logger.info("\n===Describe on a node urn where sliver expected - should fail")
                    self.subtest_Describe(slicename=slicename, sliverurns=sliverurns )
                    badurnslist = sliverurns.append(sliver_urn2)
                    self.assertRaises(NotSuccessError, 
                                      self.subtest_Describe,
                                      slicename=slicename, 
                                      sliverurns=[sliver_urn2] )

                    # Call Describe() on a urn of type 'sliver' which isn't valid
                    sliver_urn3 = re.sub('\+sliver\+.*', '+sliver+INVALID', sliver_urn)
                    badurnslist = sliverurns.append(sliver_urn3)
                    self.assertRaises(NotSuccessError, 
                                      self.subtest_Describe,
                                      slicename=slicename, 
                                      sliverurns=[sliver_urn3] )
                self.options_copy.devmode = False

            self.assertRspecType( manifest2, 'manifest')
            self.assertRspec( "ListResources", manifest2, 
                              rspec_namespace, rspec_schema,
                              self.options_copy.rspeclint )
            # Make sure the Manifest returned the nodes identified in
            # the Request
            self.assertManifestMatchesRequest( request, manifest2, 
                                               self.RSpecVersion(),
                                               self.options_copy.bound,
                                               "ListResources/Described resources in slice")


            time.sleep(self.options_copy.sleep_time)
            # RenewSliver past slice expiration - should fail
            self.subtest_RenewPastSliceExpiration( slicename )

            time.sleep(self.options_copy.sleep_time)
            # RenewSliver for 5 mins, 2 days, and 5 days
            self.subtest_generic_RenewSliver_many( slicename )
        except:
            raise
        finally:
            time.sleep(self.options_copy.sleep_time)
            try:
                self.subtest_generic_DeleteSliver( slicename )
            except:
                pass

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
            self.subtest_generic_DeleteSliver( slicename )
        except:
            pass

#        # 2 False args mean in v3+ don't do Provision or poa
#        manifest = self.subtest_generic_CreateSliver( slicename, False, False )
        manifest = self.subtest_generic_CreateSliver( slicename )
#        with open(self.options_copy.rspec_file) as f:
#            req = f.readlines()
#            request = "".join(req)             
        try:
            self.subtest_generic_DeleteSliver( slicename )
        except:
            pass

        if not self.options_copy.reuse_slice_name:
            self.subtest_deleteslice( slicename )

    def test_CreateSliverWorkflow_fail_notexist( self ):
        """test_CreateSliverWorkflow_fail_notexist:  Passes if the sliver creation workflow 
        fails when the sliver has never existed."""
        self.logger.info("\n=== Test.test_CreateSliverWorkflow_fail_notexist -- should FAIL")
        slicename = self.create_slice_name_uniq(prefix='non')        

        # Create slice so that lack of existance of the slice doesn't
        # cause the AM test to fail
        self.subtest_createslice( slicename )
        # Test SliverStatus, ListResources and DeleteSliver on a
        # non-existant sliver
        self.subtest_CreateSliverWorkflow_failure( slicename )
        self.success = True

    def subtest_CreateSliverWorkflow_failure( self, slicename ):
        # Call Status, List, then Delete

        # v3 allows return with no slivers, so expect no errors.
        # Currently, PGv3 AM gives some other random error code (not
        # 0). But that isn't really right.
        # The GCF AM returns a SEARCHFAILED - a NotSuccessError.
        # PL returns an empty list
        # We should support all of those. See ticket #220
        self.logger.info("Get Status: should fail (error or 0 slivers)")
        gotRet = False
        if self.options_copy.api_version >= 3:
            # FIXME: Factor this out assertExceptionOrEmptyReturn
            # func, *args, **kwargs, funcname, assertions[]
            # return ret of function and whether that is defined (so
            # we can see None ret)
            try:
                ret = self.subtest_generic_SliverStatus( slicename, expectedNumSlivers=0 )
                gotRet = True
            except (AMAPIError, NotSuccessError,
                    NotDictAssertionError, NoSliceCredError), e:
                self.logger.debug("Status(non existent slice) got expected error %s %s", type(e), e)
            # Could drop this whole later except clause
            except Exception, e:
                self.logger.error("Got unexpected error from Status on non-existent slice: %s %s", type(e), e)
                raise

            if gotRet:
                self.assertEqual(ret, 0, "Expected Status() to show 0 slivers in slice %s, but got %s" % (slicename, ret))
        else:
            self.assertRaises((AMAPIError, NotSuccessError, NotDictAssertionError, NoSliceCredError), 
                          self.subtest_generic_SliverStatus, slicename, expectedNumSlivers=0 )
        
        self.logger.info("List slice contents: should fail (error or 0 slivers)")
        gotRet = False
        try:
            manifest = self.subtest_generic_ListResources(slicename )
            gotRet = True
        except (AMAPIError, NotSuccessError, NotDictAssertionError), e:
            if not self.options_copy.strict:
                self.logger.debug("ListResources(non existent slice) got expected error %s %s", type(e), e)
            else:
                self.logger.error("Got unexpected error from ListResources on non-existent slice: %s %s", type(e), e)
                raise
        except NotNoneAssertionError, e:
            if self.options_copy.api_version == 1 and not self.options_copy.strict:
                    self.logger.debug("ListResources(non existent slice) got expected error %s %s", type(e), e)
            else:
                self.logger.error("Got unexpected error from ListResources on non-existent slice: %s %s", type(e), e)
                raise
        except Exception, e:
            self.logger.error("Got unexpected error from ListResources on non-existent slice: %s %s", type(e), e)
            raise

        if gotRet:
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

        # Also calls to DeleteSliver should now fail
#        self.logger.info("Calling DeleteSliver")
        self.logger.info("Delete Sliver: should fail (error or 0 slivers)")
        gotRet = False
        ret = None
        try:
            ret = self.subtest_generic_DeleteSliver(slicename, expectedNumSlivers=0)
            gotRet = True
        except (AMAPIError, NotDictAssertionError, NotSuccessError), e:
            self.logger.debug("Delete(non existent slice) got expected error %s %s", type(e), e)
        except Exception, e:
            self.logger.error("Got unexpected error from Delete on non-existent slice: %s %s", type(e), e)
            raise

        if gotRet:
            self.assertEqual(ret, 0, "Expected Delete() to show 0 slivers in slice %s, but got %s" % (slicename, ret))

    def test_CreateSliverWorkflow_multiSlice(self): 
        """test_CreateSliverWorkflow_multiSlice: Do CreateSliver workflow with multiple slices 
        and ensure can not do ListResources on slices with the wrong credential."""

        self.logger.info("\n=== Test.test_CreateSliverWorkflow_multiSlice ===")
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
        num_slices = min( num_slices, len(self.options_copy.rspec_file_list) )

        if not self.options_copy.reuse_slice_list:
            for i in xrange(num_slices):
                # if reusing a slice name, don't create (or delete) the slice
                self.subtest_createslice( slicenames[i] )

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
                self.assertTrue( os.path.exists(self.options_copy.rspec_file_list[i]), 
                "Request RSpec file, '%s' for 'CreateSliver' call " \
                                     "expected to exist " \
                                     "but does not." 
                                 % self.options_copy.rspec_file_list[i] )
                with open(self.options_copy.rspec_file_list[i]) as f:
                    request.append("")
                    request[i] = "".join(f.readlines())
                numslivers.append(-1)
                manifest.append("")
                slivers.append("")
                self.options_copy.rspec_file = self.options_copy.rspec_file_list[i]
                time.sleep(self.options_copy.sleep_time)
#                # False args mean in v3+, don't do Provision or POA
#                createReturn = self.subtest_generic_CreateSliver( slicenames[i], False, False )
                sliceExpiration = self.getSliceExpiration( slicenames[i] )
                createReturn = self.subtest_generic_CreateSliver( slicenames[i], expectedExpiration=sliceExpiration )
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
            for i in xrange(num_slices):
                time.sleep(self.options_copy.sleep_time)
                self.subtest_generic_SliverStatus( slicenames[i] )        

            # Make sure you can't list resources on other slices
            # using the wrong slice cred
            self.subtest_ListResources_wrongSlice( slicenames )        

            time.sleep(self.options_copy.sleep_time)

            for i in xrange(num_slices):
                manifest2.append("")
                manifest2[i] = "".join(self.subtest_generic_ListResources( slicename=slicenames[i] ))
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
                self.subtest_generic_RenewSliver_many( slicenames[i] )
        except:
            raise
        finally:
            time.sleep(self.options_copy.sleep_time)
            for i in xrange(num_slices):
                try:
                    self.subtest_generic_DeleteSliver( slicenames[i] )
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


    def getSliceExpiration( self, slicename ):
        # (1) Get the slicecredential
        omniargs = ["getslicecred", slicename, "-o"]
        (text, slicecredstruct) = self.call(omniargs, self.options_copy)

        if self.options_copy.api_version >= 3:
            tmpRetVal = self.assertSliceCred(slicecredstruct)
            self.assertIsNotNone( tmpRetVal )
            geni_type, geni_version, slicecred = tmpRetVal
        else:
            slicecred = slicecredstruct
            self.assertStr( slicecred,
                            "Return from 'getslicecred' " \
                            "expected to be string " \
                            "but instead returned: %r" 
                            % (slicecred))
            # Test if file is XML 
            self.assertTrue(rspec_util.is_wellformed_xml( slicecred ),
                            "Return from 'getslicecred' " \
                                "expected to be XML " \
                                "but instead returned: \n" \
                                "%s\n" \
                                "... edited for length ..." 
                            % (slicecred[:100]))

        # Get slice expiration from slicecred
        slice_exp = credparsing.get_cred_exp(None, slicecred)
        return slice_exp

    def subtest_RenewPastSliceExpiration(self, slicename):
        if self.options_copy.skip_renew:
            print "Skipping renew tests"
            return

        self.logger.info("\n=== Test.subtest_RenewPastSliceExpiration ===")
        slice_exp = self.getSliceExpiration( slicename )

        # Try to renew to 2 days late
        twodayslate = (slice_exp + datetime.timedelta(days=2)).isoformat()
#        print "Will try to renew slice %s that expires at %s until %s" % (slicename, slice_exp, twodayslate)
        self.options_copy.devmode = True   
        if self.options_copy.api_version < 3:
            omniargs = ["renewsliver", slicename, twodayslate]
            try:
                self.logger.info("\n=== Should fail - renew 2 days past slice expiration ===")
                text, (succList, failList) = self.call(omniargs, self.options_copy)
                succNum, possNum = omni.countSuccess( succList, failList )
            except AMAPIError, err:
                text = str(err)
                succNum = 0
#            if text:
#                print "Got result: %s" % text
            # Assume single AM
            self.assertTrue( int(succNum) == 0,
                         "'RenewSliver' until %s " \
                         "expected to fail, " \
                         "but did not." % (str(twodayslate)))

        else:
            # FIXME: Need a call to Renew that expects failure
#            self.subtest_Renew( slicename, twodayslate)
            omniargs = ["renew", slicename, twodayslate] 
            self.logger.info("\n=== Should fail - renew 2 days past slice expiration ===")
            text, allAggs = self.call(omniargs, self.options_copy)
            for agg, indAgg in allAggs.items():
                err_code, msg = self.assertCodeValueOutput( "Renew", agg, indAgg )
#                print "... got result code %d" % err_code
                # err_code should be BADARGS (1) or REFUSED (7) or UNSUPPORTED (13) or FORBIDDEN (3) or EXPIRED (15)
                self.assertTrue((err_code != 0), 
                                "Renew to past slice expiration (to %s) expected to fail, but succeeded at %s" % (twodayslate, agg))
                # Could test that Status' geni_expires matches expectedExp
                # self.subtest_Status( slicename, expectedExpiration=slice_exp.isoformat() )
        self.options_copy.devmode = False



    def subtest_RenewSliver( self, slicename, newtime):
        if self.options_copy.skip_renew:
            print "Skipping renew tests"
            return

        omniargs = ["renewsliver", slicename, newtime] 
        self.logger.info("\n=== Test.subtest_RenewSliver ===")
        text, (succList, failList) = self.call(omniargs, self.options_copy)
        succNum, possNum = omni.countSuccess( succList, failList )
        # Assume single AM
        self.assertTrue( int(succNum) == 1,
                         "'RenewSliver' until %s " \
                         "expected to succeed, " \
                         "but did not." % (str(newtime)))

    def subtest_RenewSlice( self, slicename, newtime ):
        omniargs = ["renewslice", slicename, newtime] 
        self.logger.info("\n=== Test.subtest_RenewSlice ===")
        text, date = self.call(omniargs, self.options_copy)
        self.assertIsNotNone( date, 
                         "'RenewSlice' until %s " \
                         "expected to succeed " \
                         "but did not." % (str(newtime)))

    def subtest_RenewSliver_many( self, slicename ):
        if self.options_copy.skip_renew:
            print "Skipping renew tests"
            return

        now = ut.OmniUnittest.now_in_seconds() # utcnow()
        fivemin = (now + datetime.timedelta(minutes=5)).isoformat()            
        twodays = (now + datetime.timedelta(days=2)).isoformat()            
        fivedays = (now + datetime.timedelta(days=5)).isoformat()
        sixDaysRaw = now + datetime.timedelta(days=6)
        # If the slice already expires >= 6 days from now, do not try to renew the slice - it will fail and isn't needed
        sliceExpiration = self.getSliceExpiration( slicename ) # parser.parse with tzinfos=tzd
        if naiveUTC(sliceExpiration) < naiveUTC(sixDaysRaw):
            sixdays = sixDaysRaw.isoformat()
            self.subtest_RenewSlice( slicename, sixdays )
        time.sleep(self.options_copy.sleep_time)
#        self.subtest_RenewSliver( slicename, fivemin )
#        time.sleep(self.options_copy.sleep_time)
        self.subtest_RenewSliver( slicename, twodays )
        time.sleep(self.options_copy.sleep_time)
        self.subtest_RenewSliver( slicename, fivedays )

    def subtest_Renew_many( self, slicename ):
        if self.options_copy.skip_renew:
            print "Skipping renew tests"
            return

        now = ut.OmniUnittest.now_in_seconds()
        fivemin = (now + datetime.timedelta(minutes=5)).isoformat()            
        twodays = (now + datetime.timedelta(days=2)).isoformat()            
        fivedays = (now + datetime.timedelta(days=5)).isoformat()           
        sixDaysRaw = now + datetime.timedelta(days=6)
        # If the slice already expires >= 6 days from now, do not try to renew the slice - it will fail and isn't needed
        sliceExpiration = self.getSliceExpiration( slicename )
        if naiveUTC(sliceExpiration) < naiveUTC(sixDaysRaw):
            sixdays = sixDaysRaw.isoformat()
            self.subtest_RenewSlice( slicename, sixdays )
        time.sleep(self.options_copy.sleep_time)
#        self.subtest_RenewSliver( slicename, fivemin )
#        time.sleep(self.options_copy.sleep_time)
        self.subtest_Renew( slicename, twodays )
        self.subtest_Status( slicename, expectedExpiration=twodays )
        time.sleep(self.options_copy.sleep_time)
        self.subtest_Renew( slicename, fivedays )
        self.subtest_Status( slicename, expectedExpiration=fivedays )

    def subtest_Renew(self, slice_name, newtime, sliverlist = None):
        if self.options_copy.skip_renew:
            print "Skipping renew tests"
            return None

        return self.subtest_AMAPIv3CallNoRspec( slice_name, 
                                        omni_method='renew', 
                                        AMAPI_call="Renew", sliverlist=sliverlist,
                                        expectedExpiration=newtime)

    def subtest_Provision(self, slice_name, sliverlist = None, expectedExpiration=None):
        return self.subtest_AMAPIv3CallNoRspec( slice_name, 
                                        omni_method='provision', 
                                        AMAPI_call="Provision", 
                                        sliverlist=sliverlist,
                                        expectedExpiration=expectedExpiration)

    def subtest_Status(self, slice_name, sliverlist = None, expectedExpiration=None, expectedNumSlivers=None, status_value = None):
        return self.subtest_AMAPIv3CallNoRspec( slice_name, 
                                                omni_method='status', 
                                                AMAPI_call="Status", 
                                                sliverlist=sliverlist,
                                                expectedExpiration=expectedExpiration,
                                                expectedNumSlivers=expectedNumSlivers,
                                                status_value=status_value)


    def subtest_PerformOperationalAction(self, slice_name, command, sliverlist = None, expectedExpiration=None):
        return self.subtest_AMAPIv3CallNoRspec( slice_name, 
                                        omni_method='performoperationalaction', 
                                        AMAPI_call="PerformOperationalAction", sliverlist=sliverlist,
                                        command=command,
                                        expectedExpiration=expectedExpiration)
    def subtest_Delete(self, slice_name, sliverlist = None, expectedExpiration=None,expectedNumSlivers=None):
        return self.subtest_AMAPIv3CallNoRspec( slice_name, 
                                        omni_method='delete', 
                                        AMAPI_call="Delete", 
                                        sliverlist=sliverlist,
                                        expectedExpiration=expectedExpiration,
                                                expectedNumSlivers=expectedNumSlivers)

    def subtest_AMAPIv3CallNoRspec( self, slicename, 
                                    omni_method='provision', 
                                    AMAPI_call="Provision",
                                    sliverlist=None, 
                                    expectedExpiration=None, 
                                    command=None,                                     
                                    expectedNumSlivers=None,
                                    status_value=None):
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
            omniargs = [omni_method, slicename, expectedExpiration] 
        elif AMAPI_call is "PerformOperationalAction":
            omniargs = [omni_method, slicename, command] 
        else:
            omniargs = [omni_method, slicename]

        if sliverlist:
            for sliver in sliverlist:
                self.assertURNandType(sliver, 'sliver')
                omniargs.append('-u')
                omniargs.append(sliver)

        sliceExpiration = self.getSliceExpiration( slicename )

        self.logger.info("\n=== Test.subtest_AMAPIv3CallNoRspec ===")
        text, allAggs = self.call(omniargs, self.options_copy)
        for agg, indAgg in allAggs.items():
            err_code, msg = self.assertCodeValueOutput( AMAPI_call, agg, indAgg )
            retVal2 = None
            # For poa, err_code 13 (UNSUPPORTED) is valid
            if ((AMAPI_call is not "PerformOperationalAction") or
                (command not in ('geni_start', 'geni_stop', 'geni_restart'))):
                self.assertSuccess( err_code )
            else:
                ec = int(err_code)
                if not (ec in (0, 13)):
                    msg = "geni_code not 0 (SUCCESS) or 13 (UNSUPPORTED). "
                    if error_util.err_codes.has_key( err_code ):
                        label = error_util.err_codes[ err_code ]['label']
                        description = error_util.err_codes[ item ]['description']
                        msg = msg+"\nInstead reported geni_code %d (%s): '%s'" % (ec, label, description)
                    raise NotSuccessError, msg
            if err_code == SUCCESS:
                # value only required if it is successful
                slivers = None
                retVal = indAgg['value']
                if AMAPI_call is "Renew":
                    # if not --best-effort, also checks that the new
                    # sliver expiration matches the requested time
                    retVal2 = self.assertRenewReturn( agg, retVal, 
                                              expectedExpiration=expectedExpiration, sliceExpiration=sliceExpiration )
                    numSlivers = retVal2
                elif AMAPI_call is "Provision":
                    retVal2 = self.assertProvisionReturn( agg, retVal,
                                         expectedExpiration=expectedExpiration, sliceExpiration=sliceExpiration  )
                    slivers, manifest = retVal2
                    numSlivers = len(slivers)
                elif AMAPI_call is "Status":
                    retVal2 = self.assertStatusReturn( agg, retVal, 
                                      expectedExpiration=expectedExpiration,
                                      status_value=status_value, sliceExpiration=sliceExpiration  )
                    numSlivers = retVal2
                elif AMAPI_call is "PerformOperationalAction":
                    retVal2 = self.assertPerformOperationalActionReturn( agg, retVal, expectedExpiration=expectedExpiration, sliceExpiration=sliceExpiration  )
                    numSlivers = retVal2
                elif AMAPI_call is "Delete":
                    retVal2 = self.assertDeleteReturn( agg, retVal,
                                              expectedExpiration=expectedExpiration)
                    numSlivers = retVal2
                else:
                    print "Shouldn't get here"

                if expectedNumSlivers is None:
                    self.assertTrue( numSlivers > 0,
                                 "Return from '%s' " \
                                     "expected to list slivers " \
                                     "but did not"
                                 % (AMAPI_call))
                else:
                    self.assertTrue( numSlivers == expectedNumSlivers,
                                 "Return from '%s' " \
                                     "expected to list %d slivers " \
                                     "but listed %d instead"
                                 % (AMAPI_call, expectedNumSlivers, numSlivers))

                if sliverlist:
                    # Check that return slivers is same set as sliverlist!
                    if slivers:
                        retSliverURNs = []
                        for sliver in slivers:
                            retSliverURNs.append(sliver['geni_sliver_urn'])
                        self.assertTrue( set(retSliverURNs)==set(sliverlist),
                                 "Return from '%s' " \
                                     "expected to list all %d requested slivers " \
                                     "but listed %d"
                                 % (AMAPI_call, len(sliverlist), numSlivers))
                    else:
                        self.assertTrue( numSlivers == len(sliverlist),
                                 "Return from '%s' " \
                                     "expected to list all %d requested slivers " \
                                     "but listed %d"
                                 % (AMAPI_call, len(sliverlist), numSlivers))

                # FIXME: If not best_effort, then all slivers should have empty or no geni_error from Renew, Provision, POA, Delete

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
        self.logger.info("\n=== Test.subtest_CreateSliver ===")
        text, manifest = self.call(omniargs, self.options_copy)

        self.assertRspec( "CreateSliver", manifest, 
                          self.manifest_namespace,
                          self.manifest_schema,
                          self.options_copy.rspeclint)
        return 1, manifest

    def subtest_Allocate(self, slice_name, expectedExpiration=None):
        return self.subtest_CreateSliverPiece( slice_name, 
                                        omni_method='allocate', 
                                        AMAPI_call="Allocate", 
                                        expectedExpiration=expectedExpiration)

    def subtest_CreateSliverPiece(self, slice_name, 
                                  omni_method='createsliver', 
                                  AMAPI_call="CreateSliver", 
                                  expectedExpiration=None):
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
        self.logger.info("\n=== Test.subtest_CreateSliverPiece ===")
        text, allAggs = self.call(omniargs, self.options_copy)

        for agg, indAgg in allAggs.items():
            self.assertIsNotNone(indAgg,
                              "Return from '%s' " \
                              "expected to be or contain an XML file " \
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
                sliceExpiration = self.getSliceExpiration( slice_name )
                numSlivers, manifest, slivers = self.assertAllocateReturn( agg, 
                                                                           retVal,
                                                                           expectedExpiration=expectedExpiration,
                                                                           sliceExpiration=sliceExpiration)
                self.assertTrue( numSlivers > 0,
                                 "Return from '%s' " \
                                     "expected to list allocated slivers " \
                                     "but did not instead returned: \n" \
                                     "%s\n" \
                                     "... edited for length ..." 
                                 % (AMAPI_call, manifest[:100]))

                retVal2 = manifest, numSlivers, slivers

            self.assertTrue( rspec_util.has_child( manifest ),
                      "Manifest RSpec returned by '%s' on slice '%s' " \
                      "expected to be non-empty " \
                      "but was empty. Return was: " \
                      "\n%s\n" \
                      "... edited for length ..."
                      % (AMAPI_call, slice_name, manifest[:100]))


        return retVal2


    def subtest_SliverStatus(self, slice_name, status_value=None):
        # SliverStatus
        omniargs = ["sliverstatus", slice_name] 
        
        self.logger.info("\n=== Test.subtest_SliverStatus ===")
        text, agg = self.call(omniargs, self.options_copy)

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
        resourceCount = 0
        for aggName, status in agg.items():
            self.assertDict(status, 
                            "Return from 'SliverStatus' for Aggregate %s " \
                            "expected to be XMLRPC struct " \
                            "but instead returned: \n" \
                            "%s\n" \
                            "... edited for length ..." 
                            % (aggName, status))
            self.assertKeyValueType( 'SliverStatus', aggName, status, 'geni_urn', str )
            status_ret = self.assertReturnKeyValueType( 'SliverStatus', aggName, status, 'geni_status', str )
            if status_value :
                self.assertTrue( status_ret==status_value,
                            "Return from 'SliverStatus' for Aggregate %s " \
                            "expected to have 'geni_status'" \
                            "='%s', but it was '%s'."
                            % (aggName, status_value, status_ret))


            self.assertKeyValueType( 'SliverStatus', aggName, status, 'geni_resources', list )
            resources = status['geni_resources']
            self.assertTrue( len(resources) > 0,
                            "Return from 'SliverStatus' for Aggregate %s " \
                            "expected to have 'geni_resources' " \
                            "be a list of non-zero length, but it was not."
                            % (aggName))

            for resource in resources:
                self.assertKeyValueType( 'SliverStatus', aggName, resource, 'geni_urn', str )
                self.assertKeyValueType( 'SliverStatus', aggName, resource, 'geni_status', str )
                self.assertKeyValueType( 'SliverStatus', aggName, resource, 'geni_error', str )
            resourceCount += len(resources)
        return resourceCount

    def subtest_DeleteSliver(self, slice_name, expectedNumSlivers=None):
        omniargs = ["deletesliver", slice_name]
        self.logger.info("\n=== Test.subtest_DeleteSliver ===")
        text, (successList, failList) = self.call(omniargs, self.options_copy)
        _ = text # Appease eclipse
        succNum, possNum = omni.countSuccess( successList, failList )
        _ = possNum # Appease eclipse

        if expectedNumSlivers==0:
            # Either an Exception or Boolean is valid here, so don't test
            pass
        else:
            self.assertTrue( succNum == 1,
                         "Sliver deletion expected to work " \
                         "but instead sliver deletion failed for slice: %s"
                         % slice_name )
        return 0

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
        """test_CreateSliver_badrspec_emptyfile: Passes if the sliver creation workflow FAILs
        when the request RSpec is an empty file."""
        self.logger.info("\n=== Test.test_CreateSliver_badrspec_emptyfile == should FAIL")
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
        """test_CreateSliver_badrspec_malformed: Passes if the sliver creation workflow fails 
        when the request RSpec is not well-formed XML."""

        self.logger.info("\n=== Test.test_CreateSliver_badrspec_malformed --- should FAIL ===")

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

################################################################################
###
### This test is commented out because no aggregate actually passed it 
###    AND
### we don't care much.
###
################################################################################
    # def test_CreateSliver_badrspec_manifest(self):
    #     """test_CreateSliver_badrspec_manifest: Passes if the sliver creation workflow fails 
    #    when the request RSpec is a manifest RSpec.  --bad-rspec-file allows you to replace the 
    #    RSpec with an alternative."""
    #     slice_name = self.create_slice_name(prefix='bad3')
    #     self.options_copy.rspec_file = self.options_copy.bad_rspec_file
        
    #     # Check for the existance of the Request RSpec file
    #     self.assertTrue( os.path.exists(self.options_copy.rspec_file),
    #                      "Request RSpec file, '%s' for 'CreateSliver' call " \
    #                          "expected to exist " \
    #                          "but does not." 
    #                      % self.options_copy.rspec_file )

    #     self.assertRaises((AMAPIError, NotSuccessError, NotNoneAssertionError),
    #                           self.subtest_MinCreateSliverWorkflow, slice_name)
    #     self.success = True


    # Provide simple mapping for all v1, v2, and v3 calls
    def subtest_generic_ListResources( self, slicename, *args, **kwargs ):
        if self.options_copy.api_version <= 2:
            return self.subtest_ListResources( slicename, *args, **kwargs )
        elif self.options_copy.api_version >= 3:
            return self.subtest_Describe( slicename, *args, **kwargs )

    def subtest_generic_DeleteSliver( self, slicename, sliverlist =  None, expectedNumSlivers=None ):
        if self.options_copy.api_version <= 2:
            return self.subtest_DeleteSliver( slicename, expectedNumSlivers=expectedNumSlivers )
        elif self.options_copy.api_version >= 3:
            return self.subtest_Delete( slicename, sliverlist, expectedNumSlivers=expectedNumSlivers )

    def subtest_generic_CreateSliver( self, slicename, doProvision=True, doPOA=True, expectedExpiration=None ):
        """For v1 and v2, call CreateSliver().  For v3, call
        Allocate(), Provision(), and then
        PerformOperationalAction('geni_start').
        """
        if self.options_copy.api_version <= 2:
            numslivers, manifest = self.subtest_CreateSliver( slicename )
            slivers = None
        elif self.options_copy.api_version >= 3:
            manifest, numslivers, slivers = self.subtest_Allocate( slicename,
                                                                   expectedExpiration=expectedExpiration)
            if doProvision:
                slivers, manifest = self.subtest_Provision( slicename )
                numslivers = len(slivers)
                if doPOA:
                    # FIXME: Check operational state is ready for geni_start
                    # At least could wrap some of these in a try/catch
                    # that looks for geni_code UNSUPPORTED? or INPROGRESS (already starting)?
                    # At least look for the sliver(s) to NOT have operational state 'geni_pending_allocation'. AFter that, 
                    # actions are valid.
                    # Probably also check the sliver does not have operational state 'geni_ready' - in which case
                    # no 'start' is needed.
                    # FIXME: Is geni_start even a valid operation
                    self.subtest_PerformOperationalAction( slicename, 'geni_start')
                    # FIXME: Check operational state is ready for restart
                    # FIXME: Is geni_restart even a valid operation
                    self.subtest_PerformOperationalAction( slicename, 'geni_restart')
                    # FIXME: Check operational state is ready for stop
                    # At least check the state is not geni_notready - ie it has already been stopped
                    # FIXME: Is geni_stop even a valid operation
                    self.subtest_PerformOperationalAction( slicename, 'geni_stop')
                    self.options_copy.devmode = True   
                    self.assertRaises(NotSuccessError,
                                      self.subtest_PerformOperationalAction, 
                                      slicename, '' )
                    self.options_copy.devmode = False  
                    self.assertRaises(NotSuccessError, 
                                      self.subtest_PerformOperationalAction, 
                                      slicename, 'random_action' )
#                else:
#                    print 'not doing POA'
#            else:
#                print 'not doing Provision or POA'

        return numslivers, manifest, slivers

    def subtest_generic_SliverStatus( self, slicename, sliverlist = None, expectedNumSlivers=None, status=None ):
        if self.options_copy.api_version <= 2:
            return self.subtest_SliverStatus( slicename, status  )
        elif self.options_copy.api_version >= 3:
            return self.subtest_Status( slicename, sliverlist, status_value=status, expectedNumSlivers=expectedNumSlivers )

    def subtest_generic_RenewSliver_many( self, slicename ):
        if self.options_copy.skip_renew:
            print "Skipping renew tests"
            return

        if self.options_copy.api_version <= 2:
            self.subtest_RenewSliver_many( slicename )
        elif self.options_copy.api_version >= 3:
            self.subtest_Renew_many( slicename )

    @classmethod
    def getParser( cls, parser=omni.getParser(), usage=None):
        parser.add_option( "--reuse-slice", 
                           action="store", type='string', dest='reuse_slice_name', 
                           help="Use slice name provided instead of creating/deleting a new slice")
        parser.add_option( "--rspec-file", 
                           action="store", type='string', 
                           dest='rspec_file', default=REQ_RSPEC_FILE,
                           help="In CreateSliver tests, use _bound_ request RSpec file provided instead of default of '%s'" % REQ_RSPEC_FILE )

        # parser.add_option( "--bad-rspec-file", 
        #                    action="store", type='string', 
        #                    dest='bad_rspec_file', default=BAD_RSPEC_FILE,
        #                    help="In negative CreateSliver tests, use request RSpec file provided instead of default of '%s'" % BAD_RSPEC_FILE )

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
        parser.add_option( "--skip-renew", action="store_true", dest="skip_renew", default=False,
                           help="Skip all Renew or RenewSliver tests (default False)")


        parser.remove_option("-t")
        parser.set_defaults(logoutput='acceptance.log')

        return parser

    @classmethod
    def accept_parser( cls, parser=None, usage=None):
        if parser is None:
            parser = cls.getParser()
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


