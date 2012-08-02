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
""" Code for using Omni and unittest together"""

import copy as docopy
import datetime
from geni.util import rspec_util 
from geni.util import urn_util
import inspect
import sys
import unittest
import omni
import os.path
import pwd
import dateutil.parser

SLICE_NAME = 'acc'
LOG_CONFIG_FILE = "logging.conf"


class NotDictAssertionError( AssertionError ):
    pass
class NotListAssertionError( AssertionError ):
    pass
class NotNoneAssertionError( AssertionError ):
    pass
class NoResourcesAssertionError( AssertionError ):
    pass
class NotXMLAssertionError( AssertionError ):
    pass
class NotEqualComponentIDsError( AssertionError ):
    pass
class NotEqualClientIDsError( AssertionError ):
    pass
class WrongRspecType( AssertionError ):
    pass

class OmniUnittest(unittest.TestCase):
    """Methods for using unittest module with Omni. """
    def __init__(self, method_name='runTest'):
        super(OmniUnittest, self).__init__(method_name)
        # Add this script's args
        #        self.options, self.args = (TEST_OPTS, TEST_ARGS)
#        self.options = None
#        self.args = ()

    def section_break( self ):
        """Text to separate individual tests"""
        testname = inspect.stack()[1][3]
        pre_name = "NEW TEST: %s" % testname
        print pre_name


    def print_monitoring( self, result ):
        """prints a line of text like:
              MONITORING test_getversion 1"""

        if result is True:
            result_str = 1
        else:
            result_str = 0

        # inspect.stack()[0][3] returns the name of the method being called
        # inspect.stack()[1][3] returns the name of the parent of the
        #    method being called
        print "MONITORING %s %s" % (inspect.stack()[1][3], result_str)      

    def create_slice_name( self, prefix=SLICE_NAME ):
        """slice name to be used to create a test slice"""
        if self.options.reuse_slice_name:
            return self.options.reuse_slice_name
        else:
            user = pwd.getpwuid(os.getuid())[0]
            pre = prefix+user[:3]
            return datetime.datetime.strftime(datetime.datetime.utcnow(), pre+"-%H%M%S")
#            return prefix+pwd.getpwuid(os.getuid())[0]

    def create_slice_name_uniq( self, prefix=SLICE_NAME ):
        """Unique slice name to be used to create a test slice"""
        if self.options.reuse_slice_name:
            return self.options.reuse_slice_name
        else:
#            return prefix+os.getlogin()
            return datetime.datetime.strftime(datetime.datetime.utcnow(),
                                                    prefix+"-%H%M%S")

    def setUp( self ):
        self.options_copy = docopy.deepcopy(self.options)

    def call( self, cmd, options ):
        """Make the Omni call"""
        ret_val = omni.call( cmd, options=options, verbose=True )
        return ret_val
    def assertIsNotNone(self, item, msg):
        if item is None:
            raise NotNoneAssertionError, msg

    def assertDict(self, item, msg=None):
        if msg is None:
            msg = "Type of '%s' is not 'dict'." % item
        if not type(item) == dict:
            raise NotDictAssertionError, msg

    def assertList(self, item, msg=None):
        if msg is None:
            msg = "Type of '%s' is not 'list'." % item
        if not type(item) == list:
            raise NotListAssertionError, msg

    def assertIsXML(self, rspec, msg=None):
        if not rspec_util.is_wellformed_xml( rspec ):
            if msg is None:
                msg = "RSpec expected to be wellformed XML file " \
                    "but was not. Return was: " \
                    "\n%s\n" \
                    "... edited for length ..." % (rspec[:100])
            raise NotXMLAssertionError, msg

    def assertResourcesExist(self, rspec, msg=None):                
        if not rspec_util.has_child( rspec ):
            if msg is None:
                msg =  "RSpec expected to NOT be empty " \
                    "but was. Return was: " \
                    "\n%s\n" % (rspec[:100])
            raise NoResourcesAssertionError, msg
    def assertChildNodeExists(self, rspec, version="GENI 3", msg=None):        
        if not rspec_util.has_child_node( rspec ):
            if msg is None:
                msg =  "RSpec expected to contain <node> " \
                    "but did not. Return was: " \
                    "\n%s\n" % (rspec[:100])
            raise NoResourcesAssertionError, msg

    def RSpecVersion( self ):
        if self.options_copy.protogeniv2:
            return "ProtoGENI 2"
        else:
            return "GENI 3"
    def assertCompIDsEqual(self, rspec1, rspec2, version="GENI 3", msg=None):
        if not rspec_util.compare_comp_ids( rspec1, rspec2, version=version ):
            if msg is None:
                msg =  "Two RSpecs expected to have same component_ids " \
                    "but did not."
            raise NotEqualComponentIDsError, msg

    def assertClientIDsEqual(self, rspec1, rspec2, version="GENI 3", msg=None):
        if not rspec_util.compare_client_ids( rspec1, rspec2, version=version ):
            if msg is None:
                msg =  "Two RSpecs expected to have same client_ids " \
                    "but did not."
            raise NotEqualClientIDsError, msg

    def assertRspec( self, AMAPI_call, rspec ):
        self.assertTrue(type(rspec) is str,
                        "Return from '%s' " \
                            "expected to be string " \
                            "but instead returned: \n" \
                            "%s\n" \
                            "... edited for length ..." 
                        % (AMAPI_call, rspec[:100]))

        # Test if file is XML and contains "<rspec" or "<resv_rspec"
        self.assertTrue(rspec_util.is_rspec_string( rspec ),
                        "Return from '%s' " \
                            "expected to be XML " \
                            "but instead returned: \n" \
                            "%s\n" \
                            "... edited for length ..." 
                        % (AMAPI_call, rspec[:100]))



    def assertRspecType(self, rspec, type='request', version=None, typeOnly=False, msg=None):
        if version == None:
            rspec_type = self.options_copy.rspectype
            if len(rspec_type) == 2:
                version = "%s %s" % (rspec_type[0], str(rspec_type[1]))
            else:
                version = "GENI 3"
        if not rspec_util.is_rspec_of_type( rspec, type=type, version=version, typeOnly=typeOnly ):
            if msg is None:
                msg =  "RSpec expected to have type '%s' " \
                    "but schema was not correct." % (type)
            raise WrongRspecType, msg        
    # def assertRaisesOnly( self, err, msg, method, *args, **kwargs ):
    #     try:
    #         self.assertRaises( err, method, *args, **kwargs )
    #     except AssertionError, e:
    #         print "foo"
    #         raise
    #     except Exception, e:
    #         output_msg = "%s not raised.  %s raised instead:\n%s" % (err.__name__, type(e).__name__, str("\n".join(e.args)))
    #         if msg != "":
    #            output_msg = "%s: %s" % (output_msg, msg)
    #         raise AssertionError, output_msg
        
    def assertV2ReturnStruct( self, method, aggName, dictionary):
        self.assertKeyValueType( 'GetVersion', aggName,  dictionary, 'code', dict )
        self.assertKeyValueType( 'GetVersion', aggName,  dictionary, 'value', dict )
        self.assertKeyValueType( 'GetVersion', aggName,  dictionary, 'output', str )


    def assertKeyValueLower( self, method, aggName, dictionary, key, value):
#        self.assertKeyValueType( method, aggName, dictionary, key, type(value))
        self.assertTrue( dictionary[key].lower()==value.lower(),
                        "Return from '%s' at %s " \
                            "expected to have entry '%s' of value '%s' " \
                            "but instead returned: %s" 
                        % (method, aggName, key, str(value), str(dictionary[key])))                         
                                 
    def assertKeyValueType( self, method, aggName, dictionary, key, valueType=str):
        """Check whether dictionary returned by method at aggName has_key( key ) of type valueType"""
        self.assertKeyValue( method, aggName, dictionary, key)
        self.assertTrue(type(dictionary[key])==valueType,
                        "Return from '%s' %s " \
                            "expected to have entry '%s' of type '%s' " \
                            "but instead returned: %s" 
                        % (method, aggName, key, str(valueType), str(dictionary[key])))
    def assertKeyValue( self, method, aggName, dictionary, key):
        """Check whether dictionary returned by method at aggName has_key( key )"""
        if aggName is None:
            agg = ""
        else:
            agg = "at %s "%aggName

        self.assertDict(dictionary, 
                        "Return from '%s' %s " \
                            "expected to be a dictionary " \
                            "but instead returned: \n" \
                            "%s\n" \
                            "... edited for length ..." 
                        % (method, agg, str(dictionary)))

        self.assertTrue(dictionary.has_key(key),
                        "Return from '%s' %s" \
                            "expected to have entry '%s' " \
                            "but instead returned: \n" \
                            "%s\n" \
                            "... edited for length ..." 
                        % (method, agg, key, str(dictionary)))

    def assertReturnKeyValueType( self, method, aggName, dictionary, key, valueType=str):
        self.assertKeyValueType( method, aggName, dictionary, key, valueType=valueType)
        return dictionary[key]
    

    def assertKeyValueTypeIfExists( self, method, aggName, dictionary, key, valueType ):
        """Check that if dictionary has key that it is of type valueType.
        """
        self.assertDict( dictionary )
        if dictionary.has_key(key):
            self.assertTrue(type(dictionary[key])==valueType,
                            "Return from '%s' at %s " \
                                "expected to have entry '%s' of type '%s' " \
                                "but instead returned: %s" 
                            % (method, aggName, key, str(valueType), str(dictionary[key])))

    def assertPairKeyValue( self, method, aggName, dictionary, keyA, keyB, valueType=str):
        """Check whether dictionary returned by method at aggName has at least one of keyA or keyB of type valueType.  If both keyA and keyB exist, the type of keyA will be tested."""
        self.assertDict( dictionary,
                        "Return from '%s' at %s " \
                            "expected to be dictionary " \
                            "but instead returned: \n" \
                            "%s\n" \
                            "... edited for length ..." 
                        % (method, aggName, str(dictionary)))      

        self.assertTrue( dictionary.has_key(keyA) or
                         dictionary.has_key(keyB), 
                        "Return from '%s' at %s " \
                            "expected to have entry '%s' or '%s' " \
                            "but instead returned: \n" \
                            "%s\n" \
                            "... edited for length ..." 
                        % (method, aggName, keyA, keyB,  str(dictionary)[:100]))

        # Test the first of these which exists
        if dictionary.has_key(keyA):
            keyTest = keyA
        else:
            keyTest = keyB

        self.assertTrue(type(dictionary[keyTest])==valueType,
                        "Return from '%s' at %s " \
                            "expected to have entry '%s' of type '%s' " \
                            "but did not." 
                        % (method, aggName, keyTest, str(valueType)))
    
    def assertReturnPairKeyValue( self, method, aggName, dictionary, keyA, keyB, valueType=str):
        """Check whether dictionary returned by method at aggName has one of keyA or keyB of type valueType and return whichever one exists.
        If both exist, return dictionary[keyA]."""
        self.assertPairKeyValue( method, aggName, dictionary, keyA, keyB, valueType=valueType)
        if dictionary.has_key(keyA):
            return dictionary[keyA]
        else:
            return dictionary[keyB]            

    def assertCodeValueOutput( self, AMAPI_call, agg, retVal ):
        """Checks retVal fits form:
{
code:   {
          geni_code: integer
          am_type: [optional] string
          am_code: [optional] int
        }
value:  [optional on error] integer
output: [required on failure; optional on success] XML-RPC string with 
        a human readable message explaining the result
}
"""
        # FIX ME: Pull from a standard file
        SUCCESS = 0

        err_code = self.assertCode( AMAPI_call, agg, retVal )
        if err_code == SUCCESS:
            # required
            value = self.assertValue( AMAPI_call, agg, retVal )            
            # optional
#            self.assertKeyValueTypeIfExists( AMAPI_call, agg, code,
#                                             'am_type', str )
            msg = ""
#            msg = self.assertOutput( AMAPI_call, agg, retVal )
        else:
            # required
            msg = self.assertOutput( AMAPI_call, agg, retVal )
            # optional
#            value = self.assertValue( AMAPI_call, agg, retVal )            
        
        return err_code, msg

    def assertCode( self, AMAPI_call, agg, retVal ):
        """Check that the dictionary retVal has key: 
              'code'
Check that the value of 'code' is as follows:
{
    geni_code: integer
    am_type: [optional] string
    am_code: [optional] int
}
        """
        self.assertDict( retVal )
        code = self.assertReturnKeyValueType( AMAPI_call, agg, retVal, 
                                              'code', dict )
        geni_code = self.assertReturnKeyValueType( AMAPI_call, agg, code, 
                                              'geni_code', int )

        # Check type of optional am_type and am_code
        self.assertKeyValueTypeIfExists( AMAPI_call, agg, code,
                                         'am_type', str )
        self.assertKeyValueTypeIfExists( AMAPI_call, agg, code,
                                         'am_code', int )
        return geni_code

    def assertValue( self, AMAPI_call, agg, retVal ):
        """Check that the dictionary retVal has key: 
              'value'
        """
        self.assertDict( retVal )
        self.assertKeyValue( AMAPI_call, agg, retVal, 
                                 'value' )

    def assertOutput( self, AMAPI_call, agg, retVal ):
        """Check that the dictionary retVal has key: 
              'value'
        """
        self.assertDict( retVal )
        output = self.assertReturnKeyValueType( AMAPI_call, agg, retVal, 
                                 'output', str )
        return output
        
       
    def assertDescribeReturn( self, agg, retVal ):
        """Checks retVal fits form:
{
   geni_rspec: <geni.rspec, a Manifest RSpec>
   geni_urn: <string slice urn of the containing slice>
   geni_slivers: [
               {
                  geni_sliver_urn: <string sliver urn>
                  geni_expires: <dateTime.rfc3339 allocation expiration string, as in geni_expires from SliversStatus>,
                  geni_allocation_status: <string sliver state - e.g. geni_allocated or geni_provisioned >,
                  geni_operational_status: <string sliver operational state>,
                  geni_error: <optional string, may be omitted entirely, explaining any failure for a sliver>
               },
               ...
         ]
}
        """
        AMAPI_call = "Describe"
        self.assertDict( retVal )
        manifest = self.assertGeniRspec( AMAPI_call, agg, 
                                         retVal, type='manifest')        
        self.assertGeniUrn(AMAPI_call, agg, retVal)        
        slivers = self.assertGeniSlivers(AMAPI_call, agg, retVal)        
        for sliver in slivers:
            self.assertGeniSliverUrn(AMAPI_call, agg, sliver)        
            self.assertGeniExpires(AMAPI_call, agg, sliver)        
            self.assertGeniAllocationStatus(AMAPI_call, agg, sliver)        
            self.assertGeniOperationalStatus(AMAPI_call, agg, sliver)        
            self.assertGeniErrorIfExists(AMAPI_call, agg, sliver)        
        return len(slivers)


    def assertStatusReturn( self, agg, retVal ):
        """Checks retVal fits form:
{
  geni_urn: <slice URN>
  geni_slivers: [ 
                    { geni_sliver_urn: <sliver URN>
                      geni_allocation_status: <string, eg provisioned>
                      geni_operational_status: <string, eg ready>
                      geni_expires: <dateTime.rfc3339 of individual sliver expiration>
                      geni_error: <string, eg ''>,
                     },
                    { geni_sliver_urn: <sliver URN>
                      geni_allocation_status: <string, eg provisioned>
                      geni_operational_status: <string, eg ready>
                      geni_expires: <dateTime.rfc3339 of individual sliver expiration>
                      geni_error: <string, eg ''>,
                      }
                  ]
}
        """
        AMAPI_call = "Status"
        self.assertDict( retVal )
        self.assertGeniUrn(AMAPI_call, agg, retVal)        
        slivers = self.assertGeniSlivers(AMAPI_call, agg, retVal)        
        for sliver in slivers:
            self.assertGeniSliverUrn(AMAPI_call, agg, sliver)        
            self.assertGeniExpires(AMAPI_call, agg, sliver)        
            self.assertGeniAllocationStatus(AMAPI_call, agg, sliver)        
            self.assertGeniOperationalStatus(AMAPI_call, agg, sliver)        
            self.assertGeniError(AMAPI_call, agg, sliver)        
        return len(slivers)



    def assertDeleteReturn( self, agg, retVal ):
        """Checks retVal fits form:
[
  {
   geni_sliver_urn: <string>,
   geni_allocation_status: <string>,
   geni_expires: <dateTime.rfc3339 when the sliver expires from its current state>,
   [optional: 'geni_error': string indicating any AM failure deleting the sliver.]
  },
  ...
]
        """
        AMAPI_call = "Delete"
        self.assertTrue( type(retVal) is list )
        for sliver in retVal:
            self.assertGeniSliverUrn(AMAPI_call, agg, sliver)        
            self.assertGeniExpires(AMAPI_call, agg, sliver)        
            self.assertGeniAllocationStatus(AMAPI_call, agg, sliver)        
            self.assertGeniErrorIfExists(AMAPI_call, agg, sliver)        
        return len(retVal)

    def assertRenewReturn( self, agg, retVal ):
        """Returns:
        [
  {
   geni_sliver_urn: <string>,
   geni_allocation_status: <string>,
   geni_operational_status: <string>,
   geni_expires: <dateTime.rfc3339 when the sliver expires from its current state>,
   geni_error: <optional string, may be omitted entirely, explaining any renewal failure for this sliver>
  },
  ...
]
        """
        AMAPI_call = "Renew"
        
        self.assertList( retVal )
        for sliver in retVal:
            self.assertGeniSliverUrn(AMAPI_call, agg, sliver)        
            self.assertGeniExpires(AMAPI_call, agg, sliver)        
            self.assertGeniAllocationStatus(AMAPI_call, agg, sliver)        
            self.assertGeniOperationalStatus(AMAPI_call, agg, sliver)    
            self.assertGeniErrorIfExists(AMAPI_call, agg, sliver)            
        return len(retVal)



    def assertProvisionReturn( self, agg, retVal ):
        """Returns:
geni_rspec: <geni.rspec, RSpec manifest>,
  geni_slivers: 
  [
    {
     geni_sliver_urn: <string>,
     geni_allocation_status: <string>,
     geni_operational_status: <string>,
     geni_expires <dateTime.rfc3339 when the sliver expires from its current state>,
     geni_error: <optional string, may be omitted entirely, explaining any failure to Provision this sliver>
    },
    ...
  ]
        """
        AMAPI_call = "Provision"
        self.assertDict( retVal )
        manifest = self.assertGeniRspec( AMAPI_call, agg, 
                                         retVal, type='manifest')        
        slivers = self.assertGeniSlivers( AMAPI_call, agg, retVal)  
        for sliver in slivers:
            self.assertGeniSliverUrn(AMAPI_call, agg, sliver)        
            self.assertGeniExpires(AMAPI_call, agg, sliver)        
            self.assertGeniAllocationStatus(AMAPI_call, agg, sliver)        
            self.assertGeniOperationalStatus(AMAPI_call, agg, sliver)    
            self.assertGeniErrorIfExists(AMAPI_call, agg, sliver)            
        return len(slivers)

    def assertAllocateReturn( self, agg, retVal ):
        """Returns:
{
 geni_rspec: <geni.rspec manifest of newly allocated slivers>,
 geni_slivers: [
        {
                  geni_sliver_urn: <string sliver urn>
                  geni_expires: <dateTime.rfc3339 allocation expiration string, as in geni_expires from Status>,
                  geni_allocation_status: <string sliver state - e.g. geni_allocated>
        },
        ...
    ]
}
        """
        AMAPI_call = "Allocate"
        self.assertDict( retVal )
        manifest = self.assertGeniRspec( AMAPI_call, agg, 
                                         retVal, type='manifest')        
        slivers = self.assertGeniSlivers( AMAPI_call, agg, retVal)        
        for sliver in slivers:
            self.assertGeniSliverUrn(AMAPI_call, agg, sliver)        
            self.assertGeniExpires(AMAPI_call, agg, sliver)        
            self.assertGeniAllocationStatus(AMAPI_call, agg, sliver)     
            self.assertGeniErrorIfExists(AMAPI_call, agg, sliver)           
        return len(slivers), manifest

    def assertPerformOperationalActionReturn( self, agg, retVal ):
        """Returns:
[ {
        geni_sliver_urn : <string>,
        geni_allocation_status: <string, eg provisioned>,
        geni_operational_status : <string>,
        geni_expires: <dateTime.rfc3339 of individual sliver expiration>,
        [optional: 'geni_resource_status' : string],
        [optional: 'geni_error': string explanation of operation failure for this sliver]
        }, 
        ... 
]        """
        AMAPI_call = "PerformOperationalAction"
        self.assertTrue( type(retVal) is list )
        for sliver in retVal:
            self.assertGeniSliverUrn(AMAPI_call, agg, sliver)        
            self.assertGeniExpires(AMAPI_call, agg, sliver)        
            self.assertGeniAllocationStatus(AMAPI_call, agg, sliver)        
            self.assertGeniOperationalStatus(AMAPI_call, agg, sliver)    
            self.assertGeniResourceStatusIfExists(AMAPI_call, agg, sliver)
            self.assertGeniErrorIfExists(AMAPI_call, agg, sliver)            
        return len(retVal)


    def assertGeniUrn( self, AMAPI_call, agg, retVal ):
        """Check that the dictionary retVal has keys: 
              geni_urn
        """
        slice_urn = self.assertReturnKeyValueType( AMAPI_call, agg, retVal, 
                                 'geni_urn', str )        
        self.assertURNandType( slice_urn, 'slice' )

    def assertGeniRspec( self, AMAPI_call, agg, retVal, type='manifest' ):
        self.assertDict( retVal )
        manifest = self.assertReturnKeyValueType( AMAPI_call, agg, retVal, 
                                 'geni_rspec', str )        

        self.assertRspec( AMAPI_call, manifest )
# ADD IN
#        rspec_version = self.RSpecVersion()
#        self.assertRspecType( manifest, type=type, 
#                              version=rspec_version, typeOnly=False)

        return manifest
    def assertGeniSlivers( self, AMAPI_call, agg, retVal ):
        """Check that the dictionary retVal has keys: 
              geni_slivers
        """
        slivers = self.assertReturnKeyValueType( AMAPI_call, agg, retVal, 
                                 'geni_slivers', list )        
        return slivers
    def assertGeniError( self, AMAPI_call, agg, retVal ):
        """Check that the dictionary retVal has keys: 
              geni_error
        """
        self.assertDict( retVal )
        self.assertKeyValueType( AMAPI_call, agg, retVal, 
                                 'geni_error', str )        


    def assertGeniErrorIfExists( self, AMAPI_call, agg, retVal ):
        """Check that if the dictionary retVal has key geni_error that
        it is of type 'str'.
        """
        key='geni_error'
        valueType=str
        self.assertKeyValueTypeIfExists(AMAPI_call, agg, retVal, key, valueType)

    def assertGeniResourceStatusIfExists( self, AMAPI_call, agg, retVal ):
        """Check that if the dictionary retVal has key geni_resource_status that
        it is of type 'str'.
        """
        key='geni_resource_status'
        valueType=str
        self.assertKeyValueTypeIfExists(AMAPI_call, agg, retVal, key, valueType)

    def assertGeniOperationalStatus( self, AMAPI_call, agg, retVal ):
        """Check that the dictionary retVal has keys: 
              geni_operational_status
        """
        self.assertDict( retVal )
        self.assertKeyValueType( AMAPI_call, agg, retVal, 
                                 'geni_operational_status', str )

    def assertGeniSliverUrn( self, AMAPI_call, agg, retVal ):
        """Check that the dictionary retVal has keys: 
              geni_sliver_urn
        """
        self.assertDict( retVal )
        sliver_urn = self.assertReturnKeyValueType( AMAPI_call, agg, retVal, 
                                 'geni_sliver_urn', str )
        self.assertURNandType( sliver_urn, 'sliver' )


    def assertGeniExpires( self, AMAPI_call, agg, retVal ):
        """Check that the dictionary retVal has keys: 
              geni_expires
        """
        self.assertDict( retVal )
        expires = self.assertReturnKeyValueType( AMAPI_call, agg, retVal, 
                                 'geni_expires', str ) # RFC3339 dateTime
#ADD IN        self.assertTimestamp( expires )

    def assertGeniAllocationStatus( self, AMAPI_call, agg, retVal ):
        """Check that the dictionary retVal has keys: 
              geni_allocation_status
        """
        self.assertDict( retVal )
        alloc_status = self.assertReturnKeyValueType( AMAPI_call, agg, retVal, 
                                 'geni_allocation_status', str )
        self.assertTrue( alloc_status in ['geni_unallocated', 'geni_allocated', 'geni_provisioned'],
                         "Return from '%s' " \
                             "expected to have 'geni_allocation_status' " \
                             "of one of 'geni_unallocated', " \
                             " 'geni_allocated', or 'geni_provisioned' " \
                             "but instead returned: \n" \
                             "%s\n" 
                         % (AMAPI_call, alloc_status))



    def assertTimestamp( self, timestamp ):
        self.assertTrue( self.validate_timestamp(timestamp),
                         "Return expected to have 'geni_expires' " \
                         "in form of a timestamp " \
                         "but instead returned: \n" \
                         "%s\n" 
                         % (timestamp))

    def assertURN( self, urn ):
        self.assertTrue( self.validate_URN(urn),
                         "Return expected to " \
                         "be a URN but instead returned: \n" \
                         "%s\n"
                         % (urn))

    def assertURNandType( self, urn, type ):
        self.assertTrue( self.validate_URN_and_type(urn, type),
                         "Return expected to " \
                         "be a URN of type '%s' but instead returned: \n" \
                         "%s\n"
                         % (type, urn))

    def validate_timestamp( self, timestamp ):
        """
        Returns true if timestamp is parseable by dateutil.parser.parse
        Otherwise returns false
        """
        retVal = False
        try:
            datetimeStruct = dateutil.parser.parse( timestamp )
            if type(datetimeStruct) is datetime.datetime:
                retVal = True
        except:
            retVal = False
        return retVal

    def validate_URN( self, urn ):
        return urn_util.is_valid_urn( urn )
    def validate_URN_and_type( self, urn, type ):
        return urn_util.is_valid_urn_bytype( urn, type )

    @classmethod
    def unittest_parser( cls, parser = omni.getParser(), usage=None):
        # This code uses the Omni option parser to parse the options here,
        # allowing the unit tests to take options.
        # Then we carefully edit sys.argv removing the omni options,
        # but leave the remaining options (or none) in place so that
        # the unittest optionparser doesnt throw an exception on omni
        # options, and still can get its -v or -q arguments

        if usage is not None:
            parser.set_usage(usage)

        # Get the omni options and arguments

        parser.add_option("--vv", action="store_true", 
                          help="Give -v to unittest", default=False)
        parser.add_option("--qq", action="store_true", 
                          help="Give -q to unittest", default=False)
        cls.options, cls.args = parser.parse_args(sys.argv[1:])

        # Use the default log configuration file provided with the
        # test unless the -l option is used
        if not cls.options.logconfig:
            cls.options.logconfig = LOG_CONFIG_FILE

        # Create a list of all omni options as they appear on commandline
        omni_options_with_arg = []
        omni_options_no_arg = []
        for opt in parser._get_all_options():
            #print "Found attr %s = %s" % (attr, getattr(TEST_OPTS, attr))
            if opt.takes_value():
                for cmdline in opt._long_opts:
                    omni_options_with_arg.append(cmdline)
                for cmdline in opt._short_opts:
                    omni_options_with_arg.append(cmdline)
            else:
                for cmdline in opt._long_opts:
                    omni_options_no_arg.append(cmdline)
                for cmdline in opt._short_opts:
                    omni_options_no_arg.append(cmdline)

        parser.remove_option("--vv")
        parser.remove_option("--qq")

        # Delete the omni options and values from the commandline
        del_lst = []
        have_v = False
        have_q = False
        have_vv = False
        have_qq = False
        for i, option in enumerate(sys.argv):
            if option in omni_options_with_arg:
                del_lst.append(i)
                del_lst.append(i+1)
            elif option in omni_options_no_arg:
                if option == "-v":
                    have_v = True
                    if have_vv:
                        continue
                elif option == "-q":
                    have_q = True
                    if have_qq:
                        continue
                elif option == "--vv":
                    have_vv = True
                    if have_v:
                        # Want to not remove -v but we already did!
                        # So just replace the --vv with -v
                        sys.argv[i] = "-v"
                        continue
                elif option == "--qq":
                    have_qq = True
                    if have_q:
                        # Want to not remove -q but we alredy did!
                        # So just replace the --qq with -q
                        sys.argv[i] = "-q"
                        continue
                del_lst.append(i)

        del_lst.reverse()
        for i in del_lst:
            del sys.argv[i]

        # Add -v or -q if only had --vv or --qq
        if have_vv and not have_v:
            sys.argv.insert(1,'-v')
        if have_qq and not have_q:
            sys.argv.insert(1,'-q')
        return sys.argv

##  REMAINING CODE IS ONLY FOR TESTING THE CODE IN THIS FILE
rspec = """<?xml version='1.0'?>
<!--Comment-->
<rspec xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.geni.net/resources/rspec/3 http://www.geni.net/resources/rspec/3/manifest.xsd"><node component_id='b'><sliver_type/></node></rspec>"""

sliver = dict(
                  geni_sliver_urn="urn:publicid:IDN+foobar+sliver+sliverbar",
                  geni_expires="2012-07-27T12:12:12Z", 
                  geni_allocation_status= 'geni_allocated',
                  geni_operational_status= 'geni_started',
                  geni_error= "an error message",
#                  geni_resource_status="testing"
                  )
 


class Test(OmniUnittest):
    """ Only here for testing omni_unittest.py code"""
    def test_Describe( self ):
        describe = dict(
            geni_rspec=rspec,
            geni_urn="urn:publicid:IDN+foobar+slice+slicefoo",
            geni_slivers=[sliver, sliver]
            )
        self.assertDescribeReturn( "foobar", describe )
    def test_Allocate( self ):
        allocate = dict(
            geni_rspec=rspec,
            geni_slivers= [sliver, sliver]
            )
        self.assertAllocateReturn( "foobar", allocate )
    def test_Renew( self ):
        renew = [sliver, sliver]
        self.assertRenewReturn( "foobar", renew )

    def test_Provision( self ):
        provision = dict(
            geni_rspec=rspec,
            geni_slivers= [sliver, sliver]
            )
        self.assertProvisionReturn( "foobar", provision )

    def test_Status( self ):
        status = dict(
            geni_urn="urn:publicid:IDN+foobar+slice+slicefoo",
            geni_slivers= [sliver, sliver]
            )
        self.assertStatusReturn( "foobar", status )


    def test_PerformOperationalAction( self ):
        opaction = [sliver, sliver]
        self.assertPerformOperationalActionReturn( "foobar", opaction )

    def test_Delete( self ):
        delete = [sliver, sliver]
        self.assertPerformOperationalActionReturn( "foobar", delete )



#     def test_getversion(self):
#         """Passes if a call to 'getversion' on each aggregate returns
#         a structure with a 'geni_api' field.
#         """

#         self.section_break()
#         options = docopy.deepcopy(self.options)
#         # now modify options for this test as desired

#         # now construct args
#         omniargs = ["getversion"]
# #      print "Doing self.call %s %s" % (omniargs, options)
#         (text, ret_dict) = self.call(omniargs, options)
#         msg = "No geni_api version listed in result: \n%s" % text
#         success_fail = False
#         if type(ret_dict) == type({}):
#             for ver_dict in ret_dict.values():
#                 if ver_dict is not None and ver_dict.has_key('geni_api'):
#                     success_fail = True
#                     break
#         self.assertTrue(success_fail, msg)
#         self.print_monitoring( success_fail )

if __name__ == '__main__':
    usage = "\n\tTHIS IS REPLACED USAGE"
    sys.argv = OmniUnittest.unittest_parser(usage=usage)
    # Invoke unit tests as usual
    unittest.main()


