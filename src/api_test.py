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
''' Use Omni as a library to unit test API compliance'''

# FIXME: Add usage instructions
# FIXME: Each test should describe expected results

import datetime
import inspect
import math
import os
import sys
import tempfile
import re
import unittest
import xml.etree.ElementTree as ET

import omni
from omnilib.xmlrpc.client import make_client

SLICE_NAME='mon'
TMP_DIR = '/tmp'

 #  292  ./omni.py getversion
 #  293  ./omni.py listresources 
 #  294  ./omni.py createslice    
 #  295  ./omni.py createslice foo 
 #  296  ./omni.py -h     
 #  297  ./omni.py listresources > bar.txt
 #  299  ./omni.py createsliver foo bar.txt 
 #  300  ./omni.py silverstatus foo     
 #  301  ./omni.py sliverstatus foo
 #  302  ./omni.py deletesliver foo      
 #  303  ./omni.py renewslice foo    
 #  304  ./omni.py renewslice foo "jan 1 2011"     
 #  305  ./omni.py deleteslice foo 

class GENISetup(unittest.TestCase):
   def __init__(self, methodName='runTest'):
      super(GENISetup, self).__init__(methodName)
      self.parser = omni.getParser()
      # Add this script's args
      self.options, self.args = self.parser.parse_args(sys.argv[1:])

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
      slice_name = SLICE_NAME
#      slice_name = datetime.datetime.strftime(datetime.datetime.now(), SLICE_NAME+"_%H%M%S")
      return slice_name

class Test(GENISetup):
   def test_getversion(self):
      self.sectionBreak()
      options = self.options
      # now modify options for this test as desired

      # now construct args
      omniargs = ["getversion"]
      print "doing omni.call %s %s" % (omniargs, options)
      (text, retDict) = omni.call(omniargs, options)
      msg = "No geni_api version listed in result: \n%s" % text
      successFail = False
      if type(retDict) == type({}):
         for key,verDict in retDict.items():
            if verDict.has_key('geni_api'):
               successFail = True
               break
      self.assertTrue(successFail, msg)
      self.printMonitoring( successFail )

   def test_listresources_succ_native(self):
      self.sectionBreak()
      options = self.options
      # now modify options for this test as desired

      # now construct args
      omniargs = ["-n", "-a", "http://myplc.gpolab.bbn.com:12346", "listresources"]

#CHECK THIS 
      print "doing omni.call %s %s" % (omniargs, options)
      (text, rspec) = omni.call(omniargs, options)
      # Make sure we got an XML file back
      msg = "Returned rspec is not XML: %s" % rspec
      successFail = True
      for key, value in rspec.items():
         successFail = successFail and (ET.fromstring(value) is not None)
      self.assertTrue(successFail, msg)
      self.printMonitoring( successFail )

   def test_listresources_succ_plain(self):
      self.sectionBreak()
      options = self.options
      # now modify options for this test as desired

      # now construct args
      omniargs = ["listresources"]
      print "doing omni.call %s %s" % (omniargs, options)
      (text, rspec) = omni.call(omniargs, options)
      msg = "No 'resources' found in rspec: %s" % rspec
      successFail = "resources" in text
      self.assertTrue(successFail, msg)
      self.printMonitoring( successFail )

   def test_slicecreation(self):
      self.sectionBreak()
      successFail = True
      slice_name = self.create_slice_name()
      try:
         successFail = successFail and self.subtest_createslice( slice_name )
         successFail = successFail and self.subtest_renewslice_fail( slice_name )
         successFail = successFail and self.subtest_renewslice_success(  slice_name )
      finally:
         successFail = successFail and self.subtest_deleteslice(  slice_name )
      self.printMonitoring( successFail )

   def test_slivercreation(self):
      self.sectionBreak()
      slice_name = self.create_slice_name()
      successFail = True
      try:
         successFail = successFail and self.subtest_createslice( slice_name )
         successFail = successFail and self.subtest_createsliver( slice_name )
         successFail = successFail and self.subtest_sliverstatus( slice_name )
         successFail = successFail and self.subtest_renewsliver_fail( slice_name )
         successFail = successFail and self.subtest_renewslice_success( slice_name )
         successFail = successFail and self.subtest_renewsliver_success( slice_name )
         successFail = successFail and self.subtest_deletesliver( slice_name )
      finally:
         successFail = successFail and self.subtest_deleteslice( slice_name )

      self.printMonitoring( successFail )

   def test_shutdown(self):
      self.sectionBreak()
      slice_name = self.create_slice_name()

      successFail = True
      try:
         successFail = successFail and self.subtest_createslice( slice_name )
         successFail = successFail and self.subtest_createsliver( slice_name )
         successFail = successFail and self.subtest_shutdown( slice_name )
         successFail = successFail and self.subtest_deletesliver( slice_name )
      finally:
         successFail = successFail and self.subtest_deleteslice( slice_name )
      self.printMonitoring( successFail )


   def subtest_createslice(self, slice_name ):
      options = self.options
      # now modify options for this test as desired

      # now construct args
      omniargs = ["createslice", slice_name]
      text, urn = omni.call(omniargs, options)
      msg = "Slice creation FAILED."
      if urn is None:
         successFail = False
      else:
         successFail = True
#      successFail = ("Created slice with Name %s" % SLICE_NAME) in text
      self.assertTrue( successFail, msg)
      return successFail

   def subtest_shutdown(self, slice_name):
      options = self.options
      # now modify options for this test as desired

      # now construct args
      omniargs = ["shutdown", slice_name]
      text = omni.call(omniargs, options)
      msg = "Shutdown FAILED."
      successFail = ("Shutdown Sliver") in text
#      self.assertTrue( successFail, msg)
#      return successFail
      return True

   def subtest_deleteslice(self, slice_name):
      options = self.options
      # now modify options for this test as desired

      # now construct args
      omniargs = ["deleteslice", slice_name]
      text, successFail = omni.call(omniargs, options)
      msg = "Delete slice FAILED."
      # successFail = ("Delete Slice %s result:" % SLICE_NAME) in text
#      self.assertTrue( successFail, msg)
#      return successFail

      # FIXMEFIXME?
      return True

   def subtest_renewslice_success(self, slice_name):
      options = self.options
      # now modify options for this test as desired

      # now construct args
      newtime = (datetime.datetime.now()+datetime.timedelta(hours=12)).isoformat()
      omniargs = ["renewslice", slice_name, newtime]
      text, retTime = omni.call(omniargs, options)
      msg = "Renew slice FAILED."
      if retTime is None:
         successFail = False
      else:
         successFail = True
#      successFail = ("now expires at") in text
      self.assertTrue( successFail, msg)
      return successFail

   def subtest_renewslice_fail(self, slice_name):
      options = self.options
      # now modify options for this test as desired

      # now construct args
      newtime = (datetime.datetime.now()+datetime.timedelta(days=-1)).isoformat()
      omniargs = ["renewslice", slice_name, newtime]
      text, retTime = omni.call(omniargs, options)
      msg = "Renew slice FAILED."
      if retTime is None:
         successFail = True
      else:
         successFail = False
#      successFail = ("now expires at") in text
      self.assertTrue( successFail, msg)
      return successFail

   def subtest_renewsliver_success(self, slice_name):
      options = self.options
      # now modify options for this test as desired

      # now construct args
      newtime = (datetime.datetime.now()+datetime.timedelta(hours=8)).isoformat()
      omniargs = ["renewsliver", slice_name, newtime]
      text, retTime = omni.call(omniargs, options)
      # if retTime is None:
      #    successFail = False
      # else:
      #    successFail = True
      m = re.search(r"Renewed slivers on (\w+) out of (\w+) aggregates", text)
      succNum = m.group(1)
      possNum = m.group(2)
      # we have reserved resources on exactly one aggregate
      successFail = (int(succNum) == 1)

      self.assertTrue( successFail )
      return successFail

   def subtest_renewsliver_fail(self, slice_name):
      options = self.options
      # now modify options for this test as desired

      # now construct args
      newtime = (datetime.datetime.now()+datetime.timedelta(days=-1)).isoformat()
      omniargs = ["renewsliver", slice_name, newtime]
      text, retTime = omni.call(omniargs, options)
      if retTime is None:
         successFail = True
      else:
         successFail = False
#      successFail = ("Renewed sliver") in text
      self.assertTrue( successFail )
      return successFail

   def subtest_sliverstatus(self, slice_name):
      options = self.options
      # now modify options for this test as desired

      # now construct args
      omniargs = ["sliverstatus", slice_name]
      text, status = omni.call(omniargs, options)
      m = re.search(r"Returned status of slivers on (\w+) of (\w+) possible aggregates.", text)
      succNum = m.group(1)
      possNum = m.group(2)
      # we have reserved resources on exactly one aggregate
      successFail = (int(succNum) == 1)
      self.assertTrue( successFail )
      return successFail

   def subtest_createsliver(self, slice_name):
      self.subtest_createslice( slice_name )

      options = self.options
      # now modify options for this test as desired

      # now construct args
      omniargs = ["-o", "listresources"]
      rspecfile = 'omnispec-1AMs.json'
      text, resourcesDict = omni.call(omniargs, options)

      with open(rspecfile) as file:
         rspectext = file.readlines()
         rspectext = "".join(rspectext)
         # allocate the first resource in the rspec
         resources = re.sub('"allocate": false','"allocate": true',rspectext, 1)
      # open a temporary named file for the rspec
      filename = os.path.join( TMP_DIR, datetime.datetime.strftime(datetime.datetime.now(), "apitest_%Y%m%d%H%M%S"))

      with open(filename, mode='w') as rspec_file:
         rspec_file.write( resources )
      omniargs = ["createsliver", slice_name, rspec_file.name]
      text, result = omni.call(omniargs, options)
      if result is None:
         successFail = False
      else:
         successFail = True

      # delete tmp file
      os.remove( filename )      

      self.assertTrue( successFail )
      return successFail
   def subtest_deletesliver(self, slice_name):
      options = self.options
      # now modify options for this test as desired

      # now construct args
      omniargs = ["deletesliver", slice_name]
      text, successFail = omni.call(omiargs, options)
      m = re.search(r"Deleted slivers on (\w+) out of a possible (\w+) aggregates", text)
      succNum = m.group(1)
      possNum = m.group(2)
      # we have reserved resources on exactly one aggregate
      successFail = (int(succNum) == 1)
      self.assertTrue( successFail )
      return successFail

   # def test_sliverstatusfail(self):
   #    self.sectionBreak()
#       options = self.options
#       # now modify options for this test as desired
#
#       # now construct args
#       omniargs = ["sliverstatus", "this_slice_does_not_exist"]
   #    text = omni.call(omniargs, options)
   #    print "*"*80
   #    print self.test_sliverstatusfail.__name__
   #    print "*"*80
   #    successFail = ("ERROR:omni:Call for Get Slice Cred ") in text
   #    self.assertTrue( successFail, "error message")
   #    self.printMonitoring( successFail )

if __name__ == '__main__':
   unittest.main()

