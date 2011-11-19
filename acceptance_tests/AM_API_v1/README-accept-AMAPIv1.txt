AM API v1 Acceptance Tests
==========================

Description
===========
Acceptance tests to show that the AM API v1 is implemented completely at
the aggregate under test.

Installation & Getting Started
==============================
Software Dependencies
=====================
Requires:
 * GENI credentials from the GPO ProtoGENI SA
   * NOTE: The acceptance tests work fine with other credentials that
     are trusted at the AM under test
 * Omni 1.4

Software
==================
 * acceptance_tests/AM_API_v1/am_api_v1_accept.py 
   - the AM API v1 acceptance tests
 * acceptance_tests/AM_API_v1/omni_config
   - omni_config file 
   - NOTE: Move to ~/.gcf/omni_config to ease running of acceptance tests
     from any location.  But be careful to not overwrite any
     omni_config that you may already have at that location.
 * acceptance_tests/AM_API_v1/omni_accept.conf 
   - logging configuration file for am_api_v1_accept.py
   - used by default unless you override it with -l
 * src/omni_unittest.py 
   - facilitates using Omni and unittest together

Pre-work
========
These instructions assume you have already done the following items:

 (1) Allow your Aggregate Manager (AM) to use credentials from the GPO
 ProtoGENI AM.
     For example, instructions for doing this with a MyPLC are here:
     http://groups.geni.net/geni/wii/GpoLab/MyplcReferenceImplementation#TrustaRemoteSliceAuthority
     NOTE: The acceptance tests work fine with other credentials that
     are trusted at the AM under test.

 (2) Request GPO ProtoGENI credentials.  If you don't have any, e-mail:
     help@geni.net

Usage Instructions
==================

 (1) Install Omni 
     (a) Install Omni 1.4 and test
         $ ./gcf/install/install.sh
	 All of the tests should return "passed".

	 NOTE: The above script does the steps in INSTALL.txt for
	 Ubuntu, but can be easily edited for RedHat/Fedora.
	 Others should follow the steps in INSTALL.txt
     (b) Close the xterm windows that were opened.
     (c) Configure omni_config as necessary.
         * Edit the AM nickname "am-undertest" to point to the AM under test.
         * Double check the location of the ProtoGENI .pem files
         listed in the omni_config
	 
 (2) Positive testing: Run acceptance tests with a GENI credential
 accepted by the AM
     (a) Set PYTHONPATH so the acceptance tests can locate omni.py:
     	 PYTHONPATH=$PYTHONPATH:path/to/omni.py

	 Or add the following to your ~/.bashrc:
	 export PYTHONPATH=${PYTHONPATH}:path/to/omni.py
     (b) Run all of the tests:
          $ cd gcf/acceptance_tests/AM_API_v1
          $ ./am_api_v1_accept.py -a am-undertest
         Optional: To run individual tests:
          $ ./am_api_v1_accept.py -a am-undertest Test.test_getversion
     (c) Correct errors and run step (3b) again, as needed.

 (3) Negative testing: Run acceptance tests with a credential at a gcf
 clearinghouse not accepted by the AM.
     (a) Make sure the gcf-ch and gcf-am are running:
          $ ../../install/run_gcf.sh
     (b) Run getversion test:
          $ ./am_api_v1_accept.py -a am-undertest -f my_gcf Test.test_getversion
         This should fail with the error shown in the Sample Output below.
     (c) Correct errors and run step (3b) again, as needed.

 (4) Congratulations! You are done.	 
  
Sample Output
=============

A successful run looks like this:
$ ./am_api_v1_accept.py -a am-undertest
.
----------------------------------------------------------------------
Ran 1 test in 5.590s

OK

An unsuccessful run looks like this:
$ ./am_api_v1_accept.py -a am-undertest -f my_gcf
F
======================================================================
FAIL: Passes if a 'GetVersion' returns an XMLRPC struct containing 'geni_api = 1'.
----------------------------------------------------------------------
Traceback (most recent call last):
  File "./am_api_v1_accept.py", line 79, in test_getversion
    (agg, pprinter.pformat(ver_dict)))
AssertionError: "getversion" fails to return expected XML-RPC struct from aggregate "https://pgeni.gpolab.bbn.com/protogeni/xmlrpc/am". Returned: None

----------------------------------------------------------------------
Ran 1 test in 0.062s

FAILED (failures=1)

Output of help message:

$ ./am_api_v1_accept.py -h
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
  --vv                  Give -v to unittest
  --qq                  Give -q to unittest


Message explaining all of the command line options;
Further Reading
===============
 * AM API v1 documentation: http://groups.geni.net/geni/wiki/GAPI_AM_API
 * gcf and Omni documentation: http://trac.gpolab.bbn.com/gcf/wiki

