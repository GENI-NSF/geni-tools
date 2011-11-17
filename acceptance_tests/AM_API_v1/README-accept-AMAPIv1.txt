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
 * acceptance_tests/omni_accept.conf 
   - logging configuration file for am_api_v1_accept.py
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
	 NOTE: The above script does the steps in INSTALL.txt.
     (b) Close both of the xterm windows that were opened.
     (c) Configure Omni (based on the provided omni_config)
         XXXX

 (2) Positive testing: Run acceptance tests with a GENI credential
 accepted by the AM
     (a) Set PYTHONPATH so the acceptance tests can locate omni.py:
     	 PYTHONPATH=$PYTHONPATH:path/to/omni.py

	 Or add the following to your ~/.bashrc:
	 export PYTHONPATH=${PYTHONPATH}:path/to/omni.py
     (b) Run all of the tests:
          $ cd gcf/acceptance_tests/AM_API_v1
          $ ./am_api_v1_accept.py -l ../omni_accept.conf -c path/to/omni_config -a AM_url_or_nickname_to_test
         Optional: To run individual tests:
          $ ./am_api_v1_accept.py -l ../omni_accept.conf -c path/to/omni_config -a AM_url_or_nickname_to_test Test.test_getversion
     (c) Correct errors and run step (3b) again, as needed.

 (3) Negative testing: Run acceptance tests with a credential at a gcf
 clearinghouse not accepted by the AM.
     (a) Make sure the gcf-ch and gcf-am are running:
          $ ../../install/run_gcf.sh
     (b) Run getversion test:
          $ ./am_api_v1_accept.py -f my_gcf -l ../omni_accept.conf -c path/to/omni_config -a AM_url_or_nickname_to_test Test.test_getversion
         This should fail with the following error:
     (c) Correct errors and run step (3b) again, as needed.

 (4) Congratulations! You are done.	 
  
Sample Output
=============

Message explaining all of the command line options;
      $ ./am_api_v1_accept.py -h 


A successful run looks like this:

An unsuccessful run looks like this:

Further Reading
===============
 * AM API v1 documentation: http://groups.geni.net/geni/wiki/GAPI_AM_API
 * gcf and Omni documentation: http://trac.gpolab.bbn.com/gcf/wiki

