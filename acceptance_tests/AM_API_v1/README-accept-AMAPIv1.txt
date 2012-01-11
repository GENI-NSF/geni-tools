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
 	* CreateSliver
	* SliverStatus
	* ListResources <slice name>
	* DeleteSliver	
     - Sliver creation workflow fails when:
        * request RSpec is really a manifest RSpec
	* request RSpec is malformed (ie a tag is not closed)
 	* request RSpec is an empty file
     - SliverStatus, ListResources <slice name>, and DeleteSliver fail when:
        * slice has been deleted
	* slice never existed
     - GetVersion return contains:
        * GENI AM API version 1 
        * 'geni_ad_rspec_versions' (or 'ad_rspec_versions') which in turn
          contains a 'type' and 'version'
        * 'geni_request_rspec_versions' (or 'request_rspec_versions') which in turn
          contains a 'type' and 'version'
     - ListResources returns an advertisement RSpec (that is
       optionally validated with rspeclint)
     - ListResources FAILS when using a bad user credential.
     - ListResources supports 'geni_compressed' and 'geni_available' options
     - SliverRenewal for 2 days and 5 days succeeds
     

Installation & Getting Started
==============================
Software Dependencies
=====================
Requires:
 * Omni 1.5.2 and the acceptance tests [3] which are distributed as part
   of the gcf1.5.2 package
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
 * gcf-1.5.2/acceptance_tests/AM_API_v1/am_api_v1_accept.py 
   - the AM API v1 acceptance tests
 * gcf-1.5.2/acceptance_tests/AM_API_v1/omni_config
   - omni_config file 
 * gcf-1.5.2/acceptance_tests/AM_API_v1/omni_accept.conf 
   - logging configuration file for am_api_v1_accept.py
   - used by default unless you override it with -l
 * gcf-1.5.2/src/omni_unittest.py 
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

 (1) Install gcf1.5.2 (which includes Omni and the acceptance tests)
     (a) Install and test it per the instructions in INSTALL.txt.
	 All of the tests should return "passed".
     (b) Configure omni_config.
         * Omni configuration is described in README-omni.txt
         * Verify the ProtoGENI .pem files are found in the location
           specified in the omni_config
     (c) Set PYTHONPATH so the acceptance tests can locate omni.py:
     	 PYTHONPATH=$PYTHONPATH:path/to/gcf-1.5.2/src

	 Or add the following to your ~/.bashrc:
	 export PYTHONPATH=${PYTHONPATH}:path/to/gcf-1.5.2/src
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
     (b) The above tests should all pass except for one 
     	  * Test.test_CreateSliver_badrspec_manifest fails as shown in
                 the sample output.

 (3) Configure to point to AM under test. 
     (a) Configure omni_config
         * Edit 'aggregates' to point to the url of the AM under test.
         * Edit 'am-undertest' to point to the url of the AM under test.
     (b) Write a request RSpec for AM under test.
     	 (i) Move default RSpecs used in (2) out of the way.
             $ mv gcf-1.5.2/acceptance_tests/AM_API_v1/request.xml  gcf-1.5.2/acceptance_tests/AM_API_v1/request.xml.default
             $ mv gcf-1.5.2/acceptance_tests/AM_API_v1/request2.xml  gcf-1.5.2/acceptance_tests/AM_API_v1/request2.xml.default
             $ mv gcf-1.5.2/acceptance_tests/AM_API_v1/request3.xml  gcf-1.5.2/acceptance_tests/AM_API_v1/request3.xml.default
         (ii) Write three bounded [6] request RSpec for the AM under test and save as: 
     	     gcf-1.5.2/acceptance_tests/AM_API_v1/request.xml
     	     gcf-1.5.2/acceptance_tests/AM_API_v1/request2.xml
     	     gcf-1.5.2/acceptance_tests/AM_API_v1/request3.xml
     (c) Write a manifest RSpec for AM under test.
     	 (i) Move default rspec used in (2) out of the way.
             $ mv gcf-1.5.2/acceptance_tests/AM_API_v1/bad.xml  gcf-1.5.2/acceptance_tests/AM_API_v1/bad.xml.default
         (ii) Write a manifest RSpec for the AM under test and save as: 
     	     gcf-1.5.2/acceptance_tests/AM_API_v1/bad.xml

 (4) Run acceptance tests with a GENI credential accepted by the AM
     (a) Run all of the tests:
          $ am_api_v1_accept.py -a am-undertest
         Optional: To run individual tests (replacing test_GetVersion
         with the name of the appropriate test):
          $ am_api_v1_accept.py -a am-undertest Test.test_GetVersion
     (b) Correct errors and run step (4a) again, as needed.
     	 * See "Common Errors and What to Do About It" below for how
                to deal with common errors.  
	 * In particular, you may find --more-strict helpful if your
                AM returns an empty RSpec from ListResources when a
                slice does not exist.

 (5) Run "Shutdown" acceptance tests.  Beware that this test likely
 requires an admin to recover from as it runs the AM API command
 "Shutdown" on a slice.
         $ am_api_v1_accept.py -a am-undertest Test.test_CreateSliverWorkflow_with_Shutdown

 (6) Congratulations! You are done.	 

Variations
==========

 * Use --vv to have the underlying unittest be more verbose (including
   printing names and descriptions of tests).

 * To validate your RSpecs with rspeclint add the --rspeclint option:
    $ am_api_v1_accept.py -a am-undertest --rspeclint
Note this will cause the following text to print (which should be ignored):
Usage: rspeclint [<namespace> <schema>]+ <document>

Schema and document locations are either paths or URLs.

 * To run with ProtoGENI v2 RSpecs instead of GENI v3 use:
   --ProtoGENIv2, --rspec-file, and --bad-rspec-file.

    For example, with the default AM configuration, run:
    $ am_api_v1_accept.py -a am-undertest --ProtoGENIv2 --rspec-file request_pgv2.xml  
    
    This provides an appropriate ProtoGENI v2 request RSpec for the test.

    Use --bad-rspec-file to provide an alternative manifest RSpec or
    other inappropriate file to verify CreateSliver fails when passed
    a bad request RSpec.

 * It is possible to edit the omni_config to support use of other
   frameworks. 
   - Use --rspec-file and --bad-rspec-file to override the default RSpecs.
   - If you use PlanetLab, make sure to run the following which will
   cause your PlanetLab credential to be downloaded:
     $ omni.py -f plc listresources  
   - If you use GCF, make sure to use the --more-strict option.

 * --untrusted-usercred allows you to pass in a user credential that
     is not trusted by the framework defined in the omni_config for
     use into test_ListResources_untrustedCredential 

 * Future versions of this test will provide options --rspec-file-list
     and --reuse-slice-list which take lists of RSpec file and lists
     of existing slicenames for use in
     test_CreateSliverWorkflow_multiSlice

Common Errors and What to Do About It
=====================================

 * When running with ProtoGENI, you may occasionally get intermittent errors caused by making the AM API calls to quickly.  If you see these errors, either rerun the test or use the --sleep-time option to increase the time between calls.

 * If you see:
   NotNoneAssertionError: Return from 'CreateSliver'expected to be XML file but instead returned None.

Then:
   It's possible that a previous run of the test failed to delete the sliver.  Manually delete the sliver and try again:
   $ path/to/omni.py -a am-undertest deleteSliver acc<username>
where <username> is your Unix account username.

 * If a test fails, rerun the individual test by itself and look at the
contents of the acceptance.log file for an indication of the source of
the problem.

Sample Output
=============

A successful run looks like this:
$ am_api_v1_accept.py  -a am-undertest
....
----------------------------------------------------------------------
Ran 4 tests in 120.270s

OK



A partially unsuccessful run looks like this (run against ProtoGENI):
$ am_api_v1_accept.py -a am-undertest
....F.....
======================================================================
FAIL: Passes if the sliver creation workflow fails when the request RSpec is a manifest RSpec.  --bad-rspec-file allows you to replace the RSpec with an alternative.
----------------------------------------------------------------------
Traceback (most recent call last):
  File "./am_api_v1_accept.py", line 724, in test_CreateSliver_badrspec_manifest
    slice_name )
AssertionError: NotNoneAssertionError not raised

----------------------------------------------------------------------
Ran 10 tests in 320.791s

FAILED (failures=1)


Output of help message:
$am_api_v1_accept.py -h
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
  --no-compress         Do not compress returned values
  --available           Only return available resources
  --reuse-slice=REUSE_SLICE_NAME
                        Use slice name provided instead of creating/deleting a
                        new slice
  --rspec-file=RSPEC_FILE
                        In CreateSliver tests, use _bounded_ request RSpec
                        file provided instead of default of 'request.xml'
  --bad-rspec-file=BAD_RSPEC_FILE
                        In negative CreateSliver tests, use request RSpec file
                        provided instead of default of 'bad.xml'
  --rspeclint           Validate RSpecs using 'rspeclint'
  --less-strict         Be less rigorous. (Default)
  --more-strict         Be more rigorous.
  --ProtoGENIv2         Use ProtoGENI v2 RSpecs instead of GENI 3
  --sleep-time=SLEEP_TIME
                        Time to pause between some AM API calls in seconds
                        (Default: 3 seconds)
  --vv                  Give -v to unittest
  --qq                  Give -q to unittest

Bibliography
===============
 [1] AM API v1 documentation: http://groups.geni.net/geni/wiki/GAPI_AM_API_V1
 [2] AM API v2 change set A documentation: 
     http://groups.geni.net/geni/wiki/GAPI_AM_API_V2_DELTAS#ChangeSetA
 [3] gcf and Omni documentation: http://trac.gpolab.bbn.com/gcf/wiki
 [4] rspeclint code: http://www.protogeni.net/resources/rspeclint
 [5] rspeclint documentation: http://www.protogeni.net/trac/protogeni/wiki/RSpecDebugging
 [6] A _bounded_ advertisement RSpec explicitly lists all resources in
 the RSpec.  (This is as oppossed to requesting some resource without
 specifying which instance is being requested.)  This is important
 because the acceptance tests compare the component IDs of the
 resources in the request RSpec with those in the manifest RSpecs to
 make sure that CreateSliver and ListResources are working properly.

 
