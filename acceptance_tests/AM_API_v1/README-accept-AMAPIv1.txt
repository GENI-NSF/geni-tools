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
 * Omni 1.4 [1]
 * rspeclint (Code [2] and documentation [3] is available from ProtoGENI.)
   (1) Install LibXML (which rspeclint relies on) from CPAN.
     -- On Ubuntu Linux this is the libxml-libxml-perl package 
     	$ sudo apt-get install libxml-libxml-perl
     -- On Fedora Linux this is the perl-XML-LibXML package 
     	$ sudo yum install perl-XML-LibXML
     -- On CentOS this is the XXX package 
        $
   (2) Download rspeclint from ProtoGENI and save the file as "rspeclint".  
       rspeclint perl file is here: 
       		 http://www.protogeni.net/trac/protogeni/wiki/RSpecDebugging
   (3) Add rspeclint to your path.

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
     (a) Install Omni 1.4 and test it per the instructions in INSTALL.txt.
	 All of the tests should return "passed".
     (b) Configure omni_config as necessary.
         * Edit 'aggregates' to point to the url of the AM under test.
         * Edit 'am-undertest' to point to the url of the AM under test.
         * Double check the location of the ProtoGENI .pem files
         listed in the omni_config
	 
 (2) Positive testing: Run acceptance tests with a GENI credential
 accepted by the AM
     (a) Set PYTHONPATH so the acceptance tests can locate omni.py:
     	 PYTHONPATH=$PYTHONPATH:path/to/gcf/src

	 Or add the following to your ~/.bashrc:
	 export PYTHONPATH=${PYTHONPATH}:path/to/gcf/src
     (b) Change into the directory where you will run the acceptance test:
          $ cd gcf/acceptance_tests/AM_API_v1
     (c) Run 'rspeclint' to make sure rspeclint is in your path so that
     am_api_v1_accept.py can find it.
     	  $ rspeclint
	  Usage: rspeclint [<namespace> <schema>]+ <document>

	  Schema and document locations are either paths or URLs.
     (d) Run all of the tests:
          $ am_api_v1_accept.py -a am-undertest
         Optional: To run individual tests:
          $ am_api_v1_accept.py -a am-undertest Test.test_getversion
     (e) Correct errors and run step (3d) again, as needed.

# THIS SECTION DEFERED UNTIL WE HAVE MORE TESTS WRITTEN
# (3) Negative testing: Run acceptance tests with a credential at a gcf
# clearinghouse not accepted by the AM.
#     (a) Make sure the gcf-ch and gcf-am are running:
#          $ ../../install/run_gcf.sh
#     (b) Run getversion test:
#          $ ./am_api_v1_accept.py -a am-undertest -f my_gcf Test.test_getversion
#         This should fail with the error shown in the Sample Output below.
#     (c) Correct errors and run step (3b) again, as needed.
# END DEFER

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
$ ./am_api_v1_accept.py -f my_gcf -a am-undertest
F
======================================================================
FAIL: Passes if a 'GetVersion' returns an XMLRPC struct containing 'geni_api = 1'.
----------------------------------------------------------------------
Traceback (most recent call last):
  File "./am_api_v1_accept.py", line 88, in test_GetVersion
    % (agg))
AssertionError: Return from 'GetVersion' at aggregate 'https://pgeni.gpolab.bbn.com/protogeni/xmlrpc/am' expected to be XML-RPC struct but instead returned None.

----------------------------------------------------------------------
Ran 1 test in 0.063s

FAILED (failures=1)

Output of help message:
$ ./am_api_v1_accept.py -h
Usage:
      ./am_api_v1_accept.py 
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


Further Reading
===============
 [1] gcf and Omni documentation: http://trac.gpolab.bbn.com/gcf/wiki
 [2] rspeclint code: http://www.protogeni.net/resources/rspeclint
 [3] rspeclint documentation: http://www.protogeni.net/trac/protogeni/wiki/RSpecDebugging

 * AM API v1 documentation: http://groups.geni.net/geni/wiki/GAPI_AM_API
