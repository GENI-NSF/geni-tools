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

#Requires unittest and python-nose
pgv2_sample_req="utah-request2.xml"
ion_sample_req="ion-request2.xml"
max_sample_req="max-request2.xml"
test_slicename="testslice"
test_username="testuser"
test_keyfile="fake"


#from src import rspec,stitchsession,util
from stitchsession import *
from util import *
from rspec import *
import unittest
import inspect
import logging


class TestReqRSpecFunctions(unittest.TestCase):
    
    def setUp(self):
        pass 


    #def test_toRSpec_success(self): #TODO

    #def test_calculateDeps_success(self): #TODO

    #def test_setRestriction_success(self): #TODO

    #def test_getRestriction_success(self): #TODO

    #def test_addDependee_success(self): #TODO

    #def test_hasDependencies_success(self): #TODO



class TestPGV2ReqRSpecFunctions(unittest.TestCase):

    def setUp(self):

        self.logger = logging.getLogger('test')
        self.session = StitchSession(test_slicename,test_username,test_keyfile,self.logger)

        ##Find the path of this module
        mod = inspect.getmodule(self)
        path = os.path.dirname(mod.__file__)
        testFilesDir = path+"/../samples"  

        fh = open(testFilesDir+"/"+pgv2_sample_req)
        tmpStr = fh.read()
        fh.close()
        self.rs = ReqRSpec(tmpStr,self.session,self.logger)


    def test_selectedType(self):
        self.assertTrue(isinstance(self.rs,PGV2ReqRSpec))


    #def test_fromRSpec_success(self): #TODO

    def test_calculateRestrictions_success(self): 
        self.rs.calculateRestrictions()
        self.assertTrue(self.rs.getRestriction('vlanTranslation')==True)

    #def test_insertVlanData_success(self): #TODO

    #def test_insertExpiry_success(self): #TODO

    #def test_insertSliceName_success(self): #TODO

    #def test_doRequest_success(self): #TODO

    #def test_doFakeRequest_success(self): #TODO



class TestIonReqRSpecFunctions(unittest.TestCase):

    def setUp(self):
        self.logger = logging.getLogger('test')
        self.session = StitchSession(test_slicename,test_username,test_keyfile,self.logger)

        ##Find the path of this module
        mod = inspect.getmodule(self)
        path = os.path.dirname(mod.__file__)
        testFilesDir = path+"/../samples"  

        fh = open(testFilesDir+"/"+ion_sample_req)
        tmpStr = fh.read()
        fh.close()
        self.rs = ReqRSpec(tmpStr,self.session,self.logger)
        

    def test_selectedType(self):
        self.assertTrue(isinstance(self.rs,IonReqRSpec))


    #def test_fromRSpec_success(self): #TODO

    def test_calculateRestrictions_success(self): 
        self.rs.calculateRestrictions()
        self.assertTrue(self.rs.getRestriction('vlanTranslation')==False)

    #def test_insertVlanData_success(self): #TODO
        
    #def test_insertExpiry_success(self): #TODO

    #def test_insertSliceName_success(self): #TODO

    #def test_doRequest_success(self): #TODO

    #def test_doFakeRequest_success(self): #TODO



class TestMaxReqRSpecFunctions(unittest.TestCase):

    def setUp(self):
        self.logger = logging.getLogger('test')
        self.session = StitchSession(test_slicename,test_username,test_keyfile,self.logger)

        ##Find the path of this module
        mod = inspect.getmodule(self)
        path = os.path.dirname(mod.__file__)
        testFilesDir = path+"/../samples"  

        fh = open(testFilesDir+"/"+max_sample_req)
        tmpStr = fh.read()
        fh.close()
        self.rs = ReqRSpec(tmpStr,self.session,self.logger)
        

    def test_selectedType(self):
        self.assertTrue(isinstance(self.rs,MaxReqRSpec))


    #def test_fromRSpec_success(self): #TODO

    def test_calculateRestrictions_success(self): 
        self.rs.calculateRestrictions()
        self.assertTrue(self.rs.getRestriction('vlanTranslation')==True)

    #def test_insertVlanData_success(self): #TODO
        
    #def test_insertExpiry_success(self): #TODO

    #def test_insertSliceName_success(self): #TODO

    #def test_doRequest_success(self): #TODO

    #def test_doFakeRequest_success(self): #TODO



if __name__ == '__main__':
    unittest.main()

