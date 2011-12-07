AM API v1 Acceptance Tests
==========================

Description
===========

Acceptance tests verify compliance to the GENI Aggregate Manager (AM)
API v1 specification [1] plus change set A of the AM API v2
specification [2]. This is an early version of the acceptance test to
get feedback on the test mechanism.

Acceptance tests are intended to be run with credentials from the GPO
ProtoGENI, but they work with any credentials that are trusted at the
AM under test.

Test verifies: 
     - Sliver creation workflow 
     - GetVersion returns GENI AM API version 1 
     - ListResources returns an advertisement RSpec (that is
       optionally validated with rspeclint)
     - ListResources FAILS when using a bad user credential.

Installation & Getting Started
==============================
Software Dependencies
=====================
Requires:
 * Omni 1.5 and the acceptance tests [3] which are distributed as part
   of the GCF1.5 package
 * (optional) rspeclint (Code [4] and documentation [5] is available from ProtoGENI.)
   (1) Install LibXML (which rspeclint relies on) from CPAN.
     -- On Ubuntu Linux this is the libxml-libxml-perl package 
     	$ sudo apt-get install libxml-libxml-perl
     -- On Fedora Linux this is the perl-XML-LibXML package 
     	$ sudo yum install perl-XML-LibXML
   (2) Download rspeclint from ProtoGENI and save the file as "rspeclint".  
       'rspeclint' perl file is found here: 
       		 http://www.protogeni.net/trac/protogeni/wiki/RSpecDebugging
   (3) Add rspeclint to your path.

Credentials
===========
By policy, requires:
 * GENI credentials from the GPO ProtoGENI Slice Authority (SA) which
   is located at:
   https://boss.pgeni.gpolab.bbn.com:443/protogeni/xmlrpc/sa

Software
==================
 * gcf-1.5/acceptance_tests/AM_API_v1/am_api_v1_accept.py 
   - the AM API v1 acceptance tests
 * gcf-1.5/acceptance_tests/AM_API_v1/omni_config
   - omni_config file 
 * gcf-1.5/acceptance_tests/AM_API_v1/omni_accept.conf 
   - logging configuration file for am_api_v1_accept.py
   - used by default unless you override it with -l
 * gcf-1.5/src/omni_unittest.py 
   - facilitates using Omni and unittest together

Pre-work
========
These instructions assume you have already done the following items:

 (1) Allow your Aggregate Manager (AM) to use credentials from the GPO
 ProtoGENI AM.
     This step varies by AM type.
     For example, instructions for doing this with a MyPLC are here:
     http://groups.geni.net/geni/wiki/GpoLab/MyplcReferenceImplementation#TrustaRemoteSliceAuthority

 (2) Request GPO ProtoGENI credentials.  If you don't have any, e-mail:
     help@geni.net

 (3) [optional] Move gcf/acceptance_tests/AM_API_v1/omni_config to
     ~/.gcf/omni_config to ease running of acceptance tests from any
     location.  But be careful to not overwrite any omni_config that
     may already be at that location.


Usage Instructions
==================

 (1) Install GCF1.5 (which includes Omni and the acceptance tests)
     (a) Install and test it per the instructions in INSTALL.txt.
	 All of the tests should return "passed".
     (b) Configure omni_config as necessary.
         * Omni configuration is described in README-omni.txt
         * Verify the ProtoGENI .pem files are found in the location
           specified in the omni_config
     (c) Set PYTHONPATH so the acceptance tests can locate omni.py:
     	 PYTHONPATH=$PYTHONPATH:path/to/gcf-1.5/src

	 Or add the following to your ~/.bashrc:
	 export PYTHONPATH=${PYTHONPATH}:path/to/gcf-1.5/src
     (d) Change into the directory where you will run the acceptance test:
          $ cd gcf/acceptance_tests/AM_API_v1
     (e) Run 'rspeclint' to make sure rspeclint is in your path so that
     am_api_v1_accept.py can find it.
     	  $ rspeclint
	  Usage: rspeclint [<namespace> <schema>]+ <document>

	  Schema and document locations are either paths or URLs.
 (2) (optional) Run acceptance test with default AM to ensure everything works.
     (a) Run all of the tests:
          $ am_api_v1_accept.py -a am-undertest
         Optional: To run individual tests:
          $ am_api_v1_accept.py -a am-undertest Test.test_GetVersion
     (b) The above tests should all pass.

 (3) Configure to point to AM under test. 
     (a) Configure omni_config as necessary.
         * Edit 'aggregates' to point to the url of the AM under test.
         * Edit 'am-undertest' to point to the url of the AM under test.
     (b) Write a request RSpec for AM under test.
     	 (i) Move default rspec used in (2) out of the way.
             $ mv gcf-1.5/acceptance_tests/AM_API_v1/request.xml  gcf-1.5/acceptance_tests/AM_API_v1/request.xml.default
         (ii) Write a request RSpec for the AM under test and save as: 
     	     gcf-1.5/acceptance_tests/AM_API_v1/request.xml

 (4) Run acceptance tests with a GENI credential accepted by the AM
     (a) Run all of the tests:
          $ am_api_v1_accept.py -a am-undertest
         Optional: To run individual tests:
          $ am_api_v1_accept.py -a am-undertest Test.test_GetVersion
     (b) Correct errors and run step (4a) again, as needed.

 (5) Congratulations! You are done.	 

Variations
==========

 * To validate your RSpecs with rspeclint add the --rspeclint option:
    $ am_api_v1_accept.py -a am-undertest --rspeclint
Note this will cause the following text to print (which should be ignored):
Usage: rspeclint [<namespace> <schema>]+ <document>

Schema and document locations are either paths or URLs.

 * To run with ProtoGENI v2 RSpecs instead of GENI v3 run:
    $ am_api_v1_accept.py -a am-undertest --ProtoGENIv2

 * With the default AM configuration, instead run:
    $ am_api_v1_accept.py -a am-undertest --ProtoGENIv2 --rspec-file request_pgv2.xml  
  
Sample Output
=============

A successful run looks like this:
$ am_api_v1_accept.py  -a am-undertest
....
----------------------------------------------------------------------
Ran 4 tests in 120.270s

OK


An unsuccessful run looks like this:

$ am_api_v1_accept.py  -f my_gcf -a am-undertest                                                                                 
FFFF                                                                                    
======================================================================                  
FAIL: Passes if the sliver creation workflow succeeds:                                  
----------------------------------------------------------------------                  
Traceback (most recent call last):                                                      
  File "./am_api_v1_accept.py", line 362, in test_CreateSliver                          
    self.subtest_CreateSliver( slice_name )                                             
  File "./am_api_v1_accept.py", line 371, in subtest_CreateSliver                       
    self.assertTrue( self.checkRequestRSpecVersion() )                                  
  File "./am_api_v1_accept.py", line 105, in checkRequestRSpecVersion                   
    return self.checkRSpecVersion(type='request')                                       
  File "./am_api_v1_accept.py", line 123, in checkRSpecVersion                          
    "AM %s didn't respond to GetVersion" % (agg) )                                      
AssertionError: AM https://www.emulab.net/protogeni/xmlrpc/am didn't respond to GetVersion

======================================================================
FAIL: Passes if a 'GetVersion' returns an XMLRPC struct containing 'geni_api = 1'.
----------------------------------------------------------------------
Traceback (most recent call last):
  File "./am_api_v1_accept.py", line 173, in test_GetVersion
    % (agg))
AssertionError: Return from 'GetVersion' at aggregate 'https://www.emulab.net/protogeni/xmlrpc/am' expected to be XML-RPC struct but instead returned None.

======================================================================
FAIL: Passes if 'ListResources' returns an advertisement RSpec (an XML document which passes rspeclint).
----------------------------------------------------------------------
Traceback (most recent call last):
  File "./am_api_v1_accept.py", line 205, in test_ListResources
    self.subtest_ListResources()
  File "./am_api_v1_accept.py", line 255, in subtest_ListResources
    self.assertTrue( self.checkAdRSpecVersion() )
  File "./am_api_v1_accept.py", line 103, in checkAdRSpecVersion
    return self.checkRSpecVersion(type='ad')
  File "./am_api_v1_accept.py", line 123, in checkRSpecVersion
    "AM %s didn't respond to GetVersion" % (agg) )
AssertionError: AM https://www.emulab.net/protogeni/xmlrpc/am didn't respond to GetVersion

======================================================================
FAIL: Passes if 'ListResources' FAILS to return an advertisement RSpec when using a bad credential.
----------------------------------------------------------------------
Traceback (most recent call last):
  File "./am_api_v1_accept.py", line 251, in test_ListResources_badCredential
    self.assertRaises(NotDictAssertionError, self.subtest_ListResources, usercred=broken_usercred)
AssertionError: AM https://www.emulab.net/protogeni/xmlrpc/am didn't respond to GetVersion

----------------------------------------------------------------------
Ran 4 tests in 4.837s

FAILED (failures=4)

Output of help message:

$ am_api_v1_accept.py  -h
Usage:                                                                  
      ./am_api_v1_accept.py -a am-undertest                             
      Also try --vv                                                     

Options:
  --version             show program's version number and exit
  -h, --help            show this help message and exit       
  -c FILE, --configfile=FILE                                  
                        Config file name                      
  -f FRAMEWORK, --framework=FRAMEWORK                         
                        Control framework to use for creation/deletion of
                        slices                                           
  -n, --native          Use native RSpecs (default)                      
  --omnispec            Use Omnispecs (deprecated)                       
  -a AGGREGATE_URL, --aggregate=AGGREGATE_URL
                        Communicate with a specific aggregate
  --debug               Enable debugging output
  --no-ssl              do not use ssl
  --orca-slice-id=ORCA_SLICE_ID
                        Use the given Orca slice id
  -o, --output          Write output of getversion, listresources,
                        createsliver, sliverstatus, getslicecred to a file
                        (Omni picks the name)
  -p FILENAME_PREFIX, --prefix=FILENAME_PREFIX
                        Filename prefix when saving results (used with -o)
  --usercredfile=USER_CRED_FILENAME
                        Name of user credential file to read from if it
                        exists, or save to when running like '--usercredfile
                        myUserCred.xml -o getusercred'
  --slicecredfile=SLICE_CRED_FILENAME
                        Name of slice credential file to read from if it
                        exists, or save to when running like '--slicecredfile
                        mySliceCred.xml -o getslicecred mySliceName'
  -t AD-RSPEC-TYPE AD-RSPEC-VERSION, --rspectype=AD-RSPEC-TYPE AD-RSPEC-VERSION
                        Ad RSpec type and version to return, e.g. 'GENI 3'
  -v, --verbose         Turn on verbose command summary for omni commandline
                        tool
  -q, --quiet           Turn off verbose command summary for omni commandline
                        tool
  --tostdout            Print results like rspecs to STDOUT instead of to log
                        stream
  --abac                Use ABAC authorization
  -l LOGCONFIG, --logconfig=LOGCONFIG
                        Python logging config file
  --no-tz               Do not send timezone on RenewSliver
  -V API_VERSION, --api-version=API_VERSION
                        Specify version of AM API to use (1, 2, etc.)
  --reuse-slice=REUSE_SLICE_NAME
                        Use slice name provided instead of creating/deleting a
                        new slice
  --rspec-file=RSPEC_FILE
                        In CreateSliver tests, use request RSpec file provided
                        instead of default of 'request.xml'
  --rspeclint           Validate RSpecs using 'rspeclint'
  --ProtoGENIv2         Use ProtoGENI v2 RSpecs instead of GENI 3
  --vv                  Give -v to unittest
  --qq                  Give -q to unittest


Bibliography
===============
 [1] AM API v1 documentation: http://groups.geni.net/geni/wiki/GAPI_AM_API
 [2] AM API v2 change set A documentation: 
     http://groups.geni.net/geni/wiki/GAPI_AM_API_DRAFT#ChangeSetA
 [3] gcf and Omni documentation: http://trac.gpolab.bbn.com/gcf/wiki
 [4] rspeclint code: http://www.protogeni.net/resources/rspeclint
 [5] rspeclint documentation: http://www.protogeni.net/trac/protogeni/wiki/RSpecDebugging

 
