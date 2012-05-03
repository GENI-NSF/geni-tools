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
import inspect
import sys
import unittest
import omni
import os.path
import pwd

SLICE_NAME = 'acc'
LOG_CONFIG_FILE = "logging.conf"


class NotDictAssertionError( AssertionError ):
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

    def assertDict(self, item, msg):
        if not type(item) == dict:
            raise NotDictAssertionError, msg

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
        self.assertDict(dictionary, 
                        "Return from '%s' at %s " \
                            "expected to be a dictionary " \
                            "but instead returned: \n" \
                            "%s\n" \
                            "... edited for length ..." 
                        % (method, aggName, str(dictionary)))

        self.assertTrue(dictionary.has_key(key),
                        "Return from '%s' at %s " \
                            "expected to have entry '%s' " \
                            "but instead returned: \n" \
                            "%s\n" \
                            "... edited for length ..." 
                        % (method, aggName, key, str(dictionary)))

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
class Test(OmniUnittest):
    """ Only here for testing omni_unittest.py code"""
    def test_getversion(self):
        """Passes if a call to 'getversion' on each aggregate returns
        a structure with a 'geni_api' field.
        """

        self.section_break()
        options = docopy.deepcopy(self.options)
        # now modify options for this test as desired

        # now construct args
        omniargs = ["getversion"]
#      print "Doing self.call %s %s" % (omniargs, options)
        (text, ret_dict) = self.call(omniargs, options)
        msg = "No geni_api version listed in result: \n%s" % text
        success_fail = False
        if type(ret_dict) == type({}):
            for ver_dict in ret_dict.values():
                if ver_dict is not None and ver_dict.has_key('geni_api'):
                    success_fail = True
                    break
        self.assertTrue(success_fail, msg)
        self.print_monitoring( success_fail )

if __name__ == '__main__':
    usage = "\n\tTHIS IS REPLACED USAGE"
    sys.argv = OmniUnittest.unittest_parser(usage=usage)
    # Invoke unit tests as usual
    unittest.main()


