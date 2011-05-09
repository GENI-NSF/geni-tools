#!/usr/bin/python
import os
import unittest
import omni
import sys
import re
import datetime
import inspect
import math
import tempfile
import xml.etree.ElementTree as ET
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

   def call( self, cmd, opts ):
      # create argv containing cmds and options
      argv = [str(cmd)]
      argv.extend(opts) 

#      print argv
      # do initial setup 
      framework, config, args, opts = omni.initialize(argv)
      # process the user's call
      result = omni.API_call( framework, config, args, opts )
      if len(result)==2:
         retVal, retItem = result
      else:
         retVal = result
         retItem = None
      
      # Print the output
      s = "Command 'omni.py "+" ".join(args) + "' Returned"
      headerLen = (80 - (len(s) + 2)) / 4
      header = "- "*headerLen+" "+s+" "+"- "*headerLen
      print "-"*80
      print header
      print retVal
      print "="*80

      return retVal, retItem

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
      slice_name = datetime.datetime.strftime(datetime.datetime.now(), SLICE_NAME+"_%H%M%S")
      return slice_name

class Test(GENISetup):
   def test_getversion(self):
      self.sectionBreak()
      (text, verDict) = self.call('getversion', list(''))
      msg = "No geni_api version listed in result: \n%s" % text
      successFail = False
      if type(verDict) == type({}):
         if verDict.has_key('geni_api'):
            successFail = True
#      successFail = "'geni_api':" in text
      self.assertTrue(successFail, msg)
      self.printMonitoring( successFail )

   def test_listresources_succ_native(self):
      self.sectionBreak()
#CHECK THIS 
      (text, rspec) = self.call('ListResources', ['-n', '-a http://myplc.gpolab.bbn.com:12346'])
      # Make sure we got an XML file back
      msg = "Returned rspec is not XML: %s" % rspec
      successFail = ET.fromstring(text) is not None
      self.assertTrue(successFail, msg)
      self.printMonitoring( successFail )

   def test_listresources_succ_plain(self):
      self.sectionBreak()
      (text, rspec) = self.call('ListResources', [''])
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
      text, urn = self.call('createslice', [slice_name])
      msg = "Slice creation FAILED."
      if urn is None:
         successFail = False
      else:
         successFail = True
#      successFail = ("Created slice with Name %s" % SLICE_NAME) in text
      self.assertTrue( successFail, msg)
      return successFail

   def subtest_shutdown(self, slice_name):
      text = self.call('shutdown', [slice_name])
      msg = "Shutdown FAILED."
      successFail = ("Shutdown Sliver") in text
#      self.assertTrue( successFail, msg)
#      return successFail
      return True

   def subtest_deleteslice(self, slice_name):
      text, successFail = self.call('deleteslice', [slice_name])
      msg = "Delete slice FAILED."
      # successFail = ("Delete Slice %s result:" % SLICE_NAME) in text
#      self.assertTrue( successFail, msg)
#      return successFail
      return True

   def subtest_renewslice_success(self, slice_name):
      newtime = (datetime.datetime.now()+datetime.timedelta(hours=12)).isoformat()
      text, retTime = self.call('renewslice', [slice_name, newtime])
      msg = "Renew slice FAILED."
      if retTime is None:
         successFail = False
      else:
         successFail = True
#      successFail = ("now expires at") in text
      self.assertTrue( successFail, msg)
      return successFail

   def subtest_renewslice_fail(self, slice_name):
      newtime = (datetime.datetime.now()+datetime.timedelta(days=-1)).isoformat()
      text, retTime = self.call('renewslice', [slice_name, newtime])
      msg = "Renew slice FAILED."
      if retTime is None:
         successFail = True
      else:
         successFail = False
#      successFail = ("now expires at") in text
      self.assertTrue( successFail, msg)
      return successFail

   def subtest_renewsliver_success(self, slice_name):
      newtime = (datetime.datetime.now()+datetime.timedelta(hours=8)).isoformat()
      text, retTime = self.call('renewsliver', [slice_name, newtime])
      if retTime is None:
         successFail = False
      else:
         successFail = True
      self.assertTrue( successFail )
      return successFail

   def subtest_renewsliver_fail(self, slice_name):
      newtime = (datetime.datetime.now()+datetime.timedelta(days=-1)).isoformat()
      text, retTime = self.call('renewsliver', [slice_name, newtime])
      if retTime is None:
         successFail = True
      else:
         successFail = False
#      successFail = ("Renewed sliver") in text
      self.assertTrue( successFail )
      return successFail

   def subtest_sliverstatus(self, slice_name):
      text, status = self.call('sliverstatus', [slice_name])
      successFail = ("Status of Slice ") in text
      self.assertTrue( successFail )
      return successFail

   def subtest_createsliver(self, slice_name):
      self.subtest_createslice( slice_name )
      text, resourcesDict = self.call('listresources',[''])

      # allocate the first resource in the rspec
      resources = re.sub('"allocate": false','"allocate": true',text, 1)

      # open a temporary named file for the rspec
      filename = os.path.join( TMP_DIR, datetime.datetime.strftime(datetime.datetime.now(), "apitest_%Y%m%d%H%M%S"))
      with open(filename, mode='w') as rspec_file:
         rspec_file.write( resources )
      text, result = self.call('createsliver', [slice_name, rspec_file.name] )
      if result is None:
         successFail = False
      else:
         successFail = True

      # delete tmp file
      os.remove( filename )      

      self.assertTrue( successFail )
      return successFail
   def subtest_deletesliver(self, slice_name):
      text, successFail = self.call('deletesliver', [slice_name])
      # ("Deleted sliver") in text
      self.assertTrue( successFail )
      return successFail

   # def test_sliverstatusfail(self):
   #    self.sectionBreak()
   #    text = self.call('sliverstatus', ['this_slice_does_not_exist'])
   #    print "*"*80
   #    print self.test_sliverstatusfail.__name__
   #    print "*"*80
   #    successFail = ("ERROR:omni:Call for Get Slice Cred ") in text
   #    self.assertTrue( successFail, "error message")
   #    self.printMonitoring( successFail )

if __name__ == '__main__':
   unittest.main()

