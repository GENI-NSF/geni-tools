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
import inspect
import sys
import unittest

import omni

SLICE_NAME = 'mon'


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

    def create_slice_name( self ):
        """slice name to be used to create a test slice"""
#        slice_name = SLICE_NAME
        if self.options.reuse_slice_name is None:
            slice_name = datetime.datetime.strftime(datetime.datetime.utcnow(),
                                                    SLICE_NAME+"-%H%M%S")
        else:
            slice_name = self.options.reuse_slice_name
            
        return slice_name

    def call( self, cmd, options ):
        """Make the Omni call"""
        ret_val = omni.call( cmd, options=options, verbose=True )
        return ret_val


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


