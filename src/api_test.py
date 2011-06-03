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
""" Use Omni as a library to unit test API compliance"""

# FIXME: Add usage instructions
# FIXME: Each test should describe expected results

import copy as docopy
import inspect
import math
import re
import time
import traceback
import unittest
import xml.etree.ElementTree as ET

import omni
from omni import *

SLICE_NAME='mon'
TMP_DIR = '/tmp'

################################################################################
#
# Test scripts which test AM API calls on a CH where the running user
# has permission to create slices.  This script is built on the unittest module.
#
# Purpose of the tests is to determine that AM API is functioning properly.
#
# To run all tests:
# ./api_test.py
#
# To run a single test:
# ./api_test.py Test.test_getversion
#
# To add a new test:
# Create a new method with a name starting with 'test_".  It will
# automatically be run when api_test.py is called.
# If you want the test to be part of monitoring, include a call to the
# printMonitoring method().
#
################################################################################


TEST_OPTS = None
TEST_ARGS = ()

class GENISetup(unittest.TestCase):
    def __init__(self, methodName='runTest'):
        super(GENISetup, self).__init__(methodName)
        # Add this script's args
        self.options, self.args = (TEST_OPTS, TEST_ARGS)

    def sectionBreak( self ):
        print "\n"
        print "="*80
        testname = inspect.stack()[1][3]
        preName = "NEW TEST: %s" % testname
        lenName = len(preName)
        numSpaces = int(math.floor((80-lenName)/2))
        spaceStr = " "*numSpaces
        secHeader = spaceStr+preName+spaceStr
        print secHeader
        print "-"*80

    def printMonitoring( self, result ):
        """prints a line of text like:
              MONITORING test_getversion 1"""

        if result is True:
            resultStr = 1
        else:
            resultStr = 0

        # inspect.stack()[0][3] returns the name of the method being called
        # inspect.stack()[1][3] returns the name of the parent of the method being called
        print "MONITORING %s %s" % (inspect.stack()[1][3], resultStr)      

    def create_slice_name( self ):
#        slice_name = SLICE_NAME
        slice_name = datetime.datetime.strftime(datetime.datetime.utcnow(), SLICE_NAME+"_%H%M%S")
        return slice_name

    def call( self, cmd, options ):
        retVal= omni.call( cmd, options=options, verbose=True )
        return retVal

class Test(GENISetup):
    def test_getversion(self):
        """Passes if a call to 'getversion' on each aggregate returns
        a structure with a 'geni_api' field.
        """

        self.sectionBreak()
        options = docopy.deepcopy(self.options)
        # now modify options for this test as desired

        # now construct args
        omniargs = ["getversion"]
#      print "Doing self.call %s %s" % (omniargs, options)
        (text, retDict) = self.call(omniargs, options)
        msg = "No geni_api version listed in result: \n%s" % text
        successFail = False
        if type(retDict) == type({}):
            for key,verDict in retDict.items():
                if verDict is not None and verDict.has_key('geni_api'):
                    successFail = True
                    break
        self.assertTrue(successFail, msg)
        self.printMonitoring( successFail )

    def test_listresources_succ_native(self):
        """Passes if a call to 'listresources -n' on the listed
        aggregate succeeds.
        """
        self.sectionBreak()
        options = docopy.deepcopy(self.options)
        # now modify options for this test as desired

        # now construct args
        omniargs = ["-n", "listresources"]
        # Explicitly set this false so omni doesn't complain if both are true
        options.omnispec=False

        (text, rspec) = self.call(omniargs, options)

        # Make sure we got an XML file back
        msg = "Returned rspec is not XML: %s" % rspec
        successFail = True
        if rspec is not None:
            for key, value in rspec.items():
                successFail = successFail and (ET.fromstring(value) is not None)
        self.assertTrue(successFail, msg)
        self.printMonitoring( successFail )

    def test_listresources_succ_plain(self):
        """Passes if a call to 'listresources' succeeds."""
        self.sectionBreak()
        options = docopy.deepcopy(self.options)
        # now modify options for this test as desired

        if options.native:
            print "Forcing use of omnispecs..."
            options.native = False

        # now construct args
        omniargs = ["listresources"]
#      print "Doing self.call %s %s" % (omniargs, options)
        (text, rspec) = self.call(omniargs, options)
        msg = "No 'resources' found in rspec: %s" % rspec
        successFail = "resources" in text
        self.assertTrue(successFail, msg)
        self.printMonitoring( successFail )

    def test_slicecreation(self):
        """Passes if the entire slice creation workflow succeeds:
        (1) createslice
        (2) renewslice (in a manner that should fail)
        (3) renewslice (in a manner that should succeed)
        (4) deleteslice
        """
        self.sectionBreak()
        successFail = True
        slice_name = self.create_slice_name()
        try:
            successFail = successFail and self.subtest_createslice( slice_name )
            successFail = successFail and self.subtest_renewslice_fail( slice_name )
            successFail = successFail and self.subtest_renewslice_success(  slice_name )
        except Exception, exp:
            print 'test_slicecreation had an error: %s' % exp
            successFail = False
            traceback.print_exc()
        finally:
            successFail = successFail and self.subtest_deleteslice(  slice_name )
        self.printMonitoring( successFail )

    def test_slivercreation(self):
        """Passes if the sliver creation workflow succeeds:
        (1) createslice
        (2) createsliver
        (3) sliverstatus
        (4) renewsliver (in a manner that should fail)
        (5) renewslice (to make sure the slice does not expire before the sliver expiration we are setting in the next step)
        (6) renewsliver (in a manner that should succeed)
        (7) deletesliver
        (8) deleteslice
        """
        self.sectionBreak()
        slice_name = self.create_slice_name()
        successFail = True
        try:
            successFail = successFail and self.subtest_createslice( slice_name )
            time.sleep(5)
            successFail = successFail and self.subtest_createsliver( slice_name )
            successFail = successFail and self.subtest_sliverstatus( slice_name )
            successFail = successFail and self.subtest_renewsliver_fail( slice_name )
            successFail = successFail and self.subtest_renewslice_success( slice_name )
            successFail = successFail and self.subtest_renewsliver_success( slice_name )
        except Exception, exp:
            print 'test_slivercreation had an error: %s' % str(exp)
            successFail = False
            traceback.print_exc()
        finally:
            try:
                successFail = successFail and self.subtest_deletesliver( slice_name )
            except:
                pass
            successFail = successFail and self.subtest_deleteslice( slice_name )

        self.printMonitoring( successFail )

    # def test_shutdown(self):
    #     self.sectionBreak()
    #     slice_name = self.create_slice_name()
        
    #     successFail = True
    #     try:
    #         successFail = successFail and self.subtest_createslice( slice_name )
    #         successFail = successFail and self.subtest_createsliver( slice_name )
    #         successFail = successFail and self.subtest_shutdown( slice_name )
    #         successFail = successFail and self.subtest_deletesliver( slice_name )
    #     finally:
    #         successFail = successFail and self.subtest_deleteslice( slice_name )
    #         self.printMonitoring( successFail )


    def subtest_createslice(self, slice_name ):
        options = docopy.deepcopy(self.options)
        # now modify options for this test as desired

        # now construct args
        omniargs = ["createslice", slice_name]
        text, urn = self.call(omniargs, options)
        msg = "Slice creation FAILED."
        if urn is None:
            successFail = False
        else:
            successFail = True
        self.assertTrue( successFail, msg)
        return successFail

    def subtest_shutdown(self, slice_name):
        options = docopy.deepcopy(self.options)
        # now modify options for this test as desired

        # now construct args
        omniargs = ["shutdown", slice_name]
        text, (successList, failList) = self.call(omniargs, options)
        succNum, failNum = omni.countSuccess( successList, failList )
        if succNum == 1:
            successFail = True
        else:
            successFail = False
        return successFail

    def subtest_deleteslice(self, slice_name):
        options = docopy.deepcopy(self.options)
        # now modify options for this test as desired

        # now construct args
        omniargs = ["deleteslice", slice_name]
        text, successFail = self.call(omniargs, options)
        msg = "Delete slice FAILED."
        self.assertTrue( successFail, msg)
        return successFail

    def subtest_renewslice_success(self, slice_name):
        options = docopy.deepcopy(self.options)
        # now modify options for this test as desired

        # now construct args
        newtime = (datetime.datetime.utcnow()+datetime.timedelta(hours=12)).isoformat()
        omniargs = ["renewslice", slice_name, newtime]
        text, retTime = self.call(omniargs, options)
        msg = "Renew slice FAILED."
        if retTime is None:
            successFail = False
        else:
            successFail = True
        self.assertTrue( successFail, msg)
        return successFail

    def subtest_renewslice_fail(self, slice_name):
        options = docopy.deepcopy(self.options)
        # now modify options for this test as desired

        # now construct args
        newtime = (datetime.datetime.utcnow()+datetime.timedelta(days=-1)).isoformat()
        omniargs = ["renewslice", slice_name, newtime]
        print "Will try to renew slice to past: should fail..."
        text, retTime = self.call(omniargs, options)
        msg = "Renew slice FAILED."
        if retTime is None:
            print "Renew to a day ago failed as expected"
            successFail = True
        else:
            successFail = False
        self.assertTrue( successFail, msg)
        return successFail

    def subtest_renewsliver_success(self, slice_name):
        options = docopy.deepcopy(self.options)
        # now modify options for this test as desired

        # now construct args
        newtime = (datetime.datetime.utcnow()+datetime.timedelta(hours=8)).isoformat()

        omniargs = ["renewsliver", slice_name, newtime]
        text, (succList, failList) = self.call(omniargs, options)
        succNum, possNum = omni.countSuccess( succList, failList )
        # # retTime is only None if so renewslivers happened
        # if retTime is None:
        #    succNum = 0
        # else:
        #    try:
        #       # this string only prints if there > 1 successes
        #       m = re.search(r"Renewed slivers on (\w+) out of (\w+) aggregates", text)
        #       succNum = m.group(1)
        #       possNum = m.group(2)
        #    except:
        #       succNum = 1
        #       possNum = 1

        # we have reserved resources on exactly one aggregate
        successFail = (int(succNum) == 1)

        self.assertTrue( successFail )
        return successFail

    def subtest_renewsliver_fail(self, slice_name):
        options = docopy.deepcopy(self.options)
        # now modify options for this test as desired

        # now construct args
        (foo, slicecred) = omni.call(["getslicecred", slice_name], options)
        sliceexp = credutils.get_cred_exp(None, slicecred)
        # try to renew the sliver for a time after the slice would expire
        # this should fail
        newtime = (sliceexp+datetime.timedelta(days=1)).isoformat()
        print "Will renew past slice expiration %s to %s (should fail)" % (sliceexp, newtime)
        time.sleep(2)
        omniargs = ["renewsliver", slice_name, newtime]
        retTime = None
        try:
            text, retTime = self.call(omniargs, options)
        except:
            print "Renewsliver threw exception as expected"

        msg = "Renew sliver FAILED."
        if retTime is None:
            successFail = True
        else:
            print "Renew succeeded when it should have failed? text: %s, retTime: %s" % (text, retTime)
            successFail = False
        self.assertTrue( successFail, msg )
        return successFail

    def subtest_sliverstatus(self, slice_name):
        options = docopy.deepcopy(self.options)
        # now modify options for this test as desired

        # now construct args
        omniargs = ["sliverstatus", slice_name]
        text, status = self.call(omniargs, options)
        m = re.search(r"Returned status of slivers on (\w+) of (\w+) possible aggregates.", text)
        succNum = m.group(1)
        possNum = m.group(2)
        # we have reserved resources on exactly one aggregate
        successFail = (int(succNum) == 1)
        self.assertTrue( successFail )
        return successFail

    def _filename_part_from_am_url(self, url):
        """Strip uninteresting parts from an AM URL 
        to help construct part of a filename.
        """
        # see listresources and createsliver

        if url is None or url.strip() == "":
            return url

        # remove all punctuation and use url
        server = url
        # strip leading protocol bit
        if url.find('://') > -1:
            server = url[(url.find('://') + 3):]

        # strip standard url endings that dont tell us anything
        if server.endswith("/xmlrpc/am"):
            server = server[:(server.index("/xmlrpc/am"))]
        elif server.endswith("/xmlrpc"):
            server = server[:(server.index("/xmlrpc"))]
        elif server.endswith("/openflow/gapi/"):
            server = server[:(server.index("/openflow/gapi/"))]
        elif server.endswith("/gapi"):
            server = server[:(server.index("/gapi"))]
        elif server.endswith(":12346"):
            server = server[:(server.index(":12346"))]

        # remove punctuation. Handle both unicode and ascii gracefully
        bad = u'!"#%\'()*+,-./:;<=>?@[\]^_`{|}~'
        if isinstance(server, unicode):
            table = dict((ord(char), unicode('-')) for char in bad)
        else:
            assert isinstance(server, str)
            table = string.maketrans(bad, '-' * len(bad))
        server = server.translate(table)
        return server

    def subtest_createsliver(self, slice_name):
        options = docopy.deepcopy(self.options)
        # now modify options for this test as desired

        # now construct args
        omniargs = ["-o", "listresources"]
        text, resourcesDict = self.call(omniargs, options)

        self.assertTrue((resourcesDict is not None and len(resourcesDict.keys()) > 0), "Cannot create sliver: no resources listed")

        numAggs = len(resourcesDict.keys())
        server = str(numAggs) + "AMs"
        if (numAggs == 1) and (options.aggregate is not None):
            server = self._filename_part_from_am_url(options.aggregate)
        filename = "omnispec-" + server + ".json"
        if options.prefix and options.prefix.strip() != "":
            filename  = options.prefix.strip() + "-" + filename

        rspecfile = filename
        
        with open(rspecfile) as file:
            rspectext = file.readlines()
            rspectext = "".join(rspectext)
            # allocate the first resource in the rspec
            resources = re.sub('"allocate": false','"allocate": true',rspectext, 1)
        # open a temporary named file for the rspec
        filename = os.path.join( TMP_DIR, datetime.datetime.strftime(datetime.datetime.utcnow(), "apitest_%Y%m%d%H%M%S"))
        with open(filename, mode='w') as rspec_file:
            rspec_file.write( resources )
        omniargs = ["createsliver", slice_name, rspec_file.name]
        text, result = self.call(omniargs, options)
        if result is None:
            successFail = False
        else:
            successFail = True
        # delete tmp file
        os.remove( filename )      
        self.assertTrue( successFail )
        return successFail

    def subtest_deletesliver(self, slice_name):
        options = docopy.deepcopy(self.options)
        # now modify options for this test as desired

        # now construct args
        omniargs = ["deletesliver", slice_name]
        text, (successList, failList) = self.call(omniargs, options)
        succNum, possNum = omni.countSuccess( successList, failList )
#        m = re.search(r"Deleted slivers on (\w+) out of a possible (\w+) aggregates", text)
#        succNum = m.group(1)
#        possNum = m.group(2)

        # we have reserved resources on exactly one aggregate
        successFail = (int(succNum) == 1)
        self.assertTrue( successFail )
        return successFail
# def test_sliverstatusfail(self):
#    self.sectionBreak()
#       options = docopy.deepcopy(self.options)
#       # now modify options for this test as desired
#
#       # now construct args
#       omniargs = ["sliverstatus", "this_slice_does_not_exist"]
#    text = self.call(omniargs, options)
#    print "*"*80
#    print self.test_sliverstatusfail.__name__
#    print "*"*80
#    successFail = ("ERROR:omni:Call for Get Slice Cred ") in text
#    self.assertTrue( successFail, "error message")
#    self.printMonitoring( successFail )

if __name__ == '__main__':
    # This code uses the Omni option parser to parse the options here,
    # allowing the unit tests to take options.
    # Then we carefully edit sys.argv removing the omni options,
    # but leave the remaining options (or none) in place so that
    # the unittest optionparser doesnt throw an exception on omni
    # options, and still can get its -v or -q arguments

    # Get the omni optiosn and arguments
    parser = omni.getParser()
    parser.add_option("--vv", action="store_true", help="Give -v to unittest", default=False)
    parser.add_option("--qq", action="store_true", help="Give -q to unittest", default=False)
    TEST_OPTS, TEST_ARGS = parser.parse_args(sys.argv[1:])
    
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
    haveV = False
    haveQ = False
    haveVV = False
    haveQQ = False
    for i,option in enumerate(sys.argv):
        if option in omni_options_with_arg:
            del_lst.append(i)
            del_lst.append(i+1)
        elif option in omni_options_no_arg:
            if option == "-v":
                haveV = True
                if haveVV:
                    continue
            elif option == "-q":
                haveQ = True
                if haveQQ:
                    continue
            elif option == "--vv":
                haveVV = True
                if haveV:
                    # Want to not remove -v but we already did!
                    # So just replace the --vv with -v
                    sys.argv[i] = "-v"
                    continue
            elif option == "--qq":
                haveQQ = True
                if haveQ:
                    # Want to not remove -q but we alredy did!
                    # So just replace the --qq with -q
                    sys.argv[i] = "-q"
                    continue
            del_lst.append(i)

    del_lst.reverse()
    for i in del_lst:
        del sys.argv[i]

    # Add -v or -q if only had --vv or --qq
    if haveVV and not haveV:
        sys.argv.insert(1,'-v')
    if haveQQ and not haveQ:
        sys.argv.insert(1,'-q')

    # Invoke unit tests as usual
    unittest.main()

