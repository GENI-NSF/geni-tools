AM API Acceptance Tests
==========================

Description
===========

Acceptance tests verify compliance to the GENI Aggregate Manager (AM)
API v1 specification [1] plus change set A of the AM API v2
specification [2a] (alternatively the tests can be run against AM API v2 [2b]). 

Acceptance tests are intended to be run with credentials from the GPO
ProtoGENI, but they work with any credentials that are trusted at the
AM under test.

Test verifies: 
     - Sliver creation workflow
 	* CreateSliver : checks that request and manifest match
	* SliverStatus
	* ListResources <slice name> : checks that request and manifest match
	* DeleteSliver
     - Sliver creation workflow works with multiple simultaneous slices
        * checks that you can't use a slice credential from one slice to do
          ListResources <slicename> on another slice
     - Sliver creation workflow fails when:
        * request RSpec is really a manifest RSpec
	* request RSpec is malformed (ie a tag is not closed)
 	* request RSpec is an empty file
     - Sliver creation workflow fails or returns a manifest when:
        * sliver already exists
     - SliverStatus, ListResources <slice name>, and DeleteSliver fail when:
        * slice has been deleted
	* slice never existed
     - GetVersion return contains either:
        * GENI AM API version 1 
        * 'geni_ad_rspec_versions' (or 'ad_rspec_versions') which in turn
          contains a 'type' and 'version'
        * 'geni_request_rspec_versions' (or 'request_rspec_versions')
          which in turn contains a 'type' and 'version'
	* or alternatively contains expected return from AM API v2
     - ListResources returns an advertisement RSpec (that is
       optionally validated with rspeclint)
     - ListResources works properly with a delegated credential
     - ListResources FAILS when using a bad user credential
     - ListResources FAILS when using a valid but untrusted user
       credential 
     - ListResources supports 'geni_compressed' and 'geni_available' options
     - SliverRenewal for 2 days and 5 days succeeds
     - Shutdown : WARNING, running this test (which is in a separate
       file) likely requires administrator assistance to recover from)
     - Optional AM API v2 support

Installation & Getting Started
==============================
Software Dependencies
=====================
Requires:
 * Omni 1.6 and the acceptance tests [3] which are distributed as part
   of the gcf-1.6 package
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
 * A colleague with a set of GENI credentials willing to delegate you a slice.

Software
==================
 * gcf-1.6/acceptance_tests/AM_API/am_api_accept.py 
 * gcf-1.6/acceptance_tests/AM_API/am_api_accept_shutdown.py 
 * gcf-1.6/acceptance_tests/AM_API/am_api_accept_delegate.py 
   - the AM API acceptance tests
 * gcf-1.6/acceptance_tests/AM_API/omni_config.sample
   - default omni_config file 
 * gcf-1.6/acceptance_tests/AM_API/logging.conf 
   - logging configuration file for am_api_accept.py
   - used by default unless you override it with -l
 * gcf-1.6/src/omni_unittest.py 
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

Usage Instructions
==================

 (1) Install gcf-1.6 (which includes Omni and the acceptance tests)
     (a) Install and test it per the instructions in INSTALL.txt.
	 All of the tests should return "passed".
     (b) Change into the directory where you will run the acceptance test:
          $ cd gcf-1.6/acceptance_tests/AM_API
     (c) Configure omni_config.
         * Omni configuration is described in README-omni.txt
         * Verify the ProtoGENI .pem files are found in the location
           specified in the omni_config

     	 $ cp omni_config.sample omni_config

     (d) Set PYTHONPATH so the acceptance tests can locate omni.py:
     	 export PYTHONPATH=$PYTHONPATH:path/to/gcf-1.6/src

	 Or add the following to your ~/.bashrc:
	 export PYTHONPATH=${PYTHONPATH}:path/to/gcf-1.6/src
     (e) Run 'rspeclint' to make sure rspeclint is in your path so that
     am_api_accept.py can find it.
     	  $ rspeclint
	  Usage: rspeclint [<namespace> <schema>]+ <document>

	  Schema and document locations are either paths or URLs.
 (2) (optional) Run acceptance test with default AM to ensure everything works.
     (a) Move default RSpecs used into place:
             $ cp gcf-1.6/acceptance_tests/AM_API/request.xml.sample  gcf-1.6/acceptance_tests/AM_API/request.xml
             $ cp gcf-1.6/acceptance_tests/AM_API/request1.xml.sample  gcf-1.6/acceptance_tests/AM_API/request1.xml
             $ cp gcf-1.6/acceptance_tests/AM_API/request2.xml.sample  gcf-1.6/acceptance_tests/AM_API/request2.xml
             $ cp gcf-1.6/acceptance_tests/AM_API/request3.xml.sample  gcf-1.6/acceptance_tests/AM_API/request3.xml
             $ cp gcf-1.6/acceptance_tests/AM_API/bad.xml.sample  gcf-1.6/acceptance_tests/AM_API/bad.xml
     (b) Run all of the tests:
          $ am_api_accept.py -a am-undertest
         Optional: To run individual tests:
          $ am_api_accept.py -a am-undertest Test.test_GetVersion
     (c) The above tests should all pass except for one 
     	  * Test.test_CreateSliver_badrspec_manifest fails as shown in
                 the sample output.

 (3) Configure to point to AM under test. 
     (a) Configure omni_config
         * Edit 'aggregates' to point to the url of the AM under test.
         * Edit 'am-undertest' to point to the url of the AM under test.
     (b) Write three request RSpecs for AM under test.
     	 (i) Move default RSpecs used in (2) out of the way.
             $ rm gcf-1.6/acceptance_tests/AM_API/request.xml
             $ rm gcf-1.6/acceptance_tests/AM_API/request1.xml
             $ rm gcf-1.6/acceptance_tests/AM_API/request2.xml
             $ rm gcf-1.6/acceptance_tests/AM_API/request3.xml
         (ii) Write three bounded [6] request RSpec for the AM under test and save as: 
     	     gcf-1.6/acceptance_tests/AM_API/request.xml
     	     gcf-1.6/acceptance_tests/AM_API/request1.xml
     	     gcf-1.6/acceptance_tests/AM_API/request2.xml
     	     gcf-1.6/acceptance_tests/AM_API/request3.xml
     (c) Write a manifest RSpec for AM under test.
     	 (i) Move default rspec used in (2) out of the way.
             $ rm gcf-1.6/acceptance_tests/AM_API/bad.xml
         (ii) Write a manifest RSpec for the AM under test and save as: 
     	     gcf-1.6/acceptance_tests/AM_API/bad.xml

     (d) Send your cert to a co-worker with a PG GPO account and have
     them create a slice, reserve resources on that slice, and
     delegate the slice credential to you.
     	 (i) Have your colleague create a slice. (Remember to keep the
     	 slice name under 12 characters. Here using "delegSlice".)
	     $ gcf-1.6/src/omni.py -o createslice delegSlice
     	 (ii) Have your colleague reserve resources at the AM under test.
	     $ gcf-1.6/src/omni.py -a am-undertest -o createsliver delegSlice req.xml
	 (iii) Have your colleague download their slice credential.
	     $ gcf-1.6/src/omni.py getslicecred delegSlice -o
	 (iv) Have your colleague delegate their slice to you. (See
	 gcf-1.6/src/delegateSliceCred.py -h for more information.)
	     $ gcf-1.6/src/delegateSliceCred.py --cert path/to/their/cert.pem --key path/to/their/key.pem --delegeegid path/to/your/gid_file.pem --slicecred delegSlice-cred.xml
	 (v) Put the file generated by the above command here on your
	 computer (e.g. the original file should be named something
	 like this
	 pgeni--gpolab-bbn--com-lnevers-delegated-delegSlice-cred.xml):
	     gcf-1.6/acceptance_tests/AM_API/delegated.xml

 (4) Run acceptance tests with a GENI credential accepted by the AM
     (double check) Make sure you are still in the directory where you
     will run the acceptance tests.
          $ cd gcf-1.6/acceptance_tests/AM_API
     (a) Run all of the tests:
          $ am_api_accept.py -a am-undertest
         Optional: To run individual tests (replacing test_GetVersion
         with the name of the appropriate test):
          $ am_api_accept.py -a am-undertest Test.test_GetVersion
     (b) Correct errors and run step (4a) again, as needed.
     	 * See "Common Errors and What to Do About It" below for how
                to deal with common errors.  
	 * In particular, you may find --more-strict helpful if your
                AM returns an empty RSpec from ListResources when a
                slice does not exist.

 (5) Run "Credential Delegation" acceptance tests.  
         $ am_api_accept_delegate.py -a am-undertest 

 (6) Run "Shutdown" acceptance tests.  Beware that this test likely
 requires an admin to recover from as it runs the AM API command
 "Shutdown" on a slice.
         $ am_api_accept_shutdown.py -a am-undertest 

 (7) Congratulations! You are done.	 

Variations
==========

 * Use --vv to have the underlying unittest be more verbose (including
   printing names of tests and descriptions of tests).

 * To validate your RSpecs with rspeclint add the --rspeclint option:
    $ am_api_accept.py -a am-undertest --rspeclint

 * To run the tests with AM API v2 use -V 2.  But be sure to update
   the 'am-undertest' definition to the url of the new AM in omni_config.

 * To run with ProtoGENI v2 RSpecs instead of GENI v3 use:
   --ProtoGENIv2, --rspec-file, and --bad-rspec-file.
   (Also replace request.xml, request1.xml, request2.xml, and
   request3.xml with appropriate files.)

   For example, with the default AM configuration, run:
   $ am_api_accept.py -a am-undertest --ProtoGENIv2 --rspec-file request_pgv2.xml  
    
   This provides an appropriate ProtoGENI v2 request RSpec for the test.

   Use --bad-rspec-file to provide an alternative manifest RSpec or
   other inappropriate file to verify CreateSliver fails when passed
   a bad request RSpec.

 * It is possible to edit the omni_config to support use of other
   frameworks. 
   - Use --rspec-file and --bad-rspec-file to override the default RSpecs.
   (Also replace request.xml, request1.xml, request2.xml, and
   request3.xml with appropriate files.)
   - If you use PlanetLab, make sure to run the following which will
   cause your PlanetLab credential to be downloaded:
     $ omni.py -f plc listresources  
   - If you use gcf, make sure to use the --more-strict option.

 * --untrusted-usercred allows you to pass in a user credential that
     is not trusted by the framework defined in the omni_config for
     use in test_ListResources_untrustedCredential 

 * Future versions of this test will provide options --rspec-file-list
     and --reuse-slice-list which take lists of RSpec file and lists
     of existing slicenames for use in
     test_CreateSliverWorkflow_multiSlice

Common Errors and What to Do About It
=====================================

 * When running with ProtoGENI as the AM, you may occasionally get
   intermittent errors caused by making the AM API calls to quickly.
   If you see these errors, either rerun the test or use the
   --sleep-time option to increase the time between calls.

 * If you see:
   NotNoneAssertionError: Return from 'CreateSliver'expected to be XML file but instead returned None.

Then:
   It's possible that a previous run of the test failed to delete the sliver.  Manually delete the sliver and try again:
   $ path/to/omni.py -a am-undertest deleteSliver acc<username>
where <username> is your Unix account username.

 * If a test fails, rerun the individual test by itself and look at
the contents of the acceptance.log file for an indication of the
source of the problem using syntax like the following:
          $ am_api_accept.py -a am-undertest Test.test_GetVersion

Sample Output
=============

A successful run looks something like this:
$ am_api_accept.py  -a am-undertest
....
----------------------------------------------------------------------
Ran 14 tests in 444.270s

OK



A partially unsuccessful run looks like this (run against ProtoGENI):
(NOTE that this may improve as PG modifies some minor issues with the RSpec format.)
$ am_api_accept.py -a pg-utah2 -V 2 --rspeclint --sleep-time 10  --vv                                           
test_CreateSliver: Passes if the sliver creation workflow succeeds.  Use --rspec-file to replace the default request RSpec. ...                                                 
ok                                                                                      
test_CreateSliverWorkflow_fail_notexist:  Passes if the sliver creation workflow fails when the slice has never existed. ...                                                    
ok                                                                                      
test_CreateSliverWorkflow_multiSlice: Do CreateSliver workflow with multiple slices and ensure can not do ListResources on slices with the wrong credential. ...                
ok                                                                                      
test_CreateSliver_badrspec_emptyfile: Passes if the sliver creation workflow fails when the request RSpec is an empty file. ...                                                 
ok                                                                                      
test_CreateSliver_badrspec_malformed: Passes if the sliver creation workflow fails when the request RSpec is not well-formed XML. ...                                           
ok                                                                                      
test_CreateSliver_badrspec_manifest: Passes if the sliver creation workflow fails when the request RSpec is a manifest RSpec.  --bad-rspec-file allows you to replace the RSpec with an alternative. ... FAIL                                                           

test_GetVersion: Passes if a 'GetVersion' returns an XMLRPC struct containing 'geni_api' and other parameters defined in Change Set A. ...                                      
ok                                                                                      
test_ListResources: Passes if 'ListResources' returns an advertisement RSpec. ... FAIL  

test_ListResources_badCredential_alteredObject: Run ListResources with a User Credential that has been altered (so the signature doesn't match). ...                            
ok                                                                                      
test_ListResources_badCredential_malformedXML: Run ListResources with a User Credential that is missing it's first character (so that it is invalid XML). ...                   
ok                                                                                      
test_ListResources_delegatedSliceCred: Passes if 'ListResources' succeeds with a delegated slice credential. Override the default slice credential using --delegated-slicecredfile ... FAIL                                                                             

test_ListResources_geni_available: Passes if 'ListResources' returns an advertisement RSpec. ... FAIL                                                                           

test_ListResources_geni_compressed: Passes if 'ListResources' returns an advertisement RSpec. ... FAIL                                                                          

test_ListResources_untrustedCredential: Passes if 'ListResources' FAILS to return an advertisement RSpec when using a credential from an untrusted Clearinghouse. ...           
ok                                                                                      

======================================================================
FAIL: test_CreateSliver_badrspec_manifest: Passes if the sliver creation workflow fails when the request RSpec is a manifest RSpec.  --bad-rspec-file allows you to replace the RSpec with an alternative.                                                              
----------------------------------------------------------------------                  
Traceback (most recent call last):                                                      
  File "./am_api_accept.py", line 1248, in test_CreateSliver_badrspec_manifest       
    self.subtest_MinCreateSliverWorkflow, slice_name)                                   
AssertionError: NotNoneAssertionError not raised                                        

======================================================================
FAIL: test_ListResources: Passes if 'ListResources' returns an advertisement RSpec.
----------------------------------------------------------------------             
Traceback (most recent call last):                                                 
  File "./am_api_accept.py", line 329, in test_ListResources                    
    self.subtest_ListResources()                                                   
  File "./am_api_accept.py", line 621, in subtest_ListResources                 
    % (agg_name, rspec[:100]))                                                     
AssertionError: Return from 'ListResources' at aggregate 'unspecified_AM_URN' expected to pass rspeclint but did not. Return was:                                               
<?xml version="1.0" encoding="UTF-8"?>                                                  
<rspec xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"                            
... edited for length ...                                                               

======================================================================
FAIL: test_ListResources_delegatedSliceCred: Passes if 'ListResources' succeeds with a delegated slice credential. Override the default slice credential using --delegated-slicecredfile                                                                                
----------------------------------------------------------------------                  
Traceback (most recent call last):                                                      
  File "./am_api_accept.py", line 486, in test_ListResources_delegatedSliceCred      
    slicecredfile=self.options_copy.delegated_slicecredfile)                            
  File "./am_api_accept.py", line 569, in subtest_ListResources
    % (text))
  File "/home/sedwards/gcf-1.6/src/omni_unittest.py", line 120, in assertDict
    raise NotDictAssertionError, msg
NotDictAssertionError: Call to 'ListResources' failed or not possible but expected to succeed. Error returned:
 Got no resources on slice ahtestbbn. No resources from AM https://www.emulab.net/protogeni/xmlrpc/am/2.0: Nothing here by that name

======================================================================
FAIL: test_ListResources_geni_available: Passes if 'ListResources' returns an advertisement RSpec.
----------------------------------------------------------------------
Traceback (most recent call last):
  File "./am_api_accept.py", line 343, in test_ListResources_geni_available
    self.subtest_ListResources()
  File "./am_api_accept.py", line 621, in subtest_ListResources
    % (agg_name, rspec[:100]))
AssertionError: Return from 'ListResources' at aggregate 'unspecified_AM_URN' expected to pass rspeclint but did not. Return was:
<?xml version="1.0" encoding="UTF-8"?>
<rspec xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
... edited for length ...

======================================================================
FAIL: test_ListResources_geni_compressed: Passes if 'ListResources' returns an advertisement RSpec.
----------------------------------------------------------------------
Traceback (most recent call last):
  File "./am_api_accept.py", line 336, in test_ListResources_geni_compressed
    self.subtest_ListResources()
  File "./am_api_accept.py", line 621, in subtest_ListResources
    % (agg_name, rspec[:100]))
AssertionError: Return from 'ListResources' at aggregate 'unspecified_AM_URN' expected to pass rspeclint but did not. Return was:
<?xml version="1.0" encoding="UTF-8"?>
<rspec xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
... edited for length ...

----------------------------------------------------------------------
Ran 14 tests in 1041.449s

FAILED (failures=5)

Output of help message:
$ am_api_accept.py -h
Usage:                                                                 
      ./am_api_accept.py -a am-undertest                            
      Also try --vv                                                    

     Run an individual test using the following form...
     ./am_api_accept.py -a am-undertest Test.test_GetVersion

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
  --no-compress         Do not compress returned values
  --available           Only return available resources
  --arbitrary-option    Add an arbitrary option to ListResources (for testing
                        purposes)
  --reuse-slice=REUSE_SLICE_NAME
                        Use slice name provided instead of creating/deleting a
                        new slice
  --rspec-file=RSPEC_FILE
                        In CreateSliver tests, use _bounded_ request RSpec
                        file provided instead of default of 'request.xml'
  --bad-rspec-file=BAD_RSPEC_FILE
                        In negative CreateSliver tests, use request RSpec file
                        provided instead of default of 'bad.xml'
  --untrusted-usercredfile=UNTRUSTED_USER_CRED_FILENAME
                        Name of an untrusted user credential file to use in
                        test: test_ListResources_untrustedCredential
  --delegated-slicecredfile=DELEGATED_SLICE_CRED_FILENAME
                        Name of a delegated slice credential file to use in
                        test: test_ListResources_delegatedSliceCred
  --rspec-file-list=RSPEC_FILE_LIST
                        In multi-slice CreateSliver tests, use _bounded_
                        request RSpec files provided instead of default of
                        '(request1.xml,request2.xml,request3.xml)'
  --reuse-slice-list=REUSE_SLICE_LIST
                        In multi-slice CreateSliver tests, use slice names
                        provided instead of creating/deleting a new slice
  --rspeclint           Validate RSpecs using 'rspeclint'
  --less-strict         Be less rigorous. (Default)
  --more-strict         Be more rigorous.
  --ProtoGENIv2         Use ProtoGENI v2 RSpecs instead of GENI 3
  --sleep-time=SLEEP_TIME
                        Time to pause between some AM API calls in seconds
                        (Default: 3 seconds)
  --monitoring          Print output to allow tests to be used in monitoring.
                        Output is of the form: 'MONITORING test_TestName 1'
                        The third field is 1 if the test is successful and 0
                        is the test is unsuccessful.
  --vv                  Give -v to unittest
  --qq                  Give -q to unittest



$ am_api_accept_shutdown.py -h     

Usage:                                                                               
      ./am_api_accept_shutdown.py -a am-undertest Test.test_CreateSliverWorkflow_with_Shutdown                                                                               
      Also try --vv                                                                     
  WARNING: Be very careful running this test. Administator support is likely to be needed to recover from running this test.              

<snip>

Bibliography
===============
 [1] AM API v1 documentation: http://groups.geni.net/geni/wiki/GAPI_AM_API_V1
 [2a] AM API v2 change set A documentation: 
     http://groups.geni.net/geni/wiki/GAPI_AM_API_V2_DELTAS#ChangeSetA
 [2b] AM API v2 documentation: 
     http://groups.geni.net/geni/wiki/GAPI_AM_API_V2
 [3] gcf and Omni documentation: http://trac.gpolab.bbn.com/gcf/wiki
 [4] rspeclint code: http://www.protogeni.net/resources/rspeclint
 [5] rspeclint documentation: http://www.protogeni.net/trac/protogeni/wiki/RSpecDebugging
 [6] A _bounded_ advertisement RSpec explicitly lists all resources in
 the RSpec.  (This is as oppossed to requesting some resource without
 specifying which instance is being requested.)  This is important
 because the acceptance tests compare the component IDs of the
 resources in the request RSpec with those in the manifest RSpecs to
 make sure that CreateSliver and ListResources are working properly.

 
