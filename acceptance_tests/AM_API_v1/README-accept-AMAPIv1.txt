AM API v1 Acceptance Tests
==========================

Description
===========
Acceptance tests to show that AM API v1 is implemented completely at
an aggregate.

Installation & Getting Started
==============================
Software Dependencies
=====================
Requires:
 * GENI credentials 
 * omni 1.4

Included Software
==================
 * acceptance_tests/AM_API_v1/am_api_v1_accept.py 
   - the AM API v1 acceptance tests
 * acceptance_tests/omni_accept.conf 
   - configuration file for the am_api_accept.py
 * src/omni_unittest.py 
   - facilitates using Omni and unittest

Usage Instructions
==================
 (1) Request GENI credentials if you don't have them
 (2) Install Omni 1.4
 (3) Set PYTHONPATH
 (4) Configure Omni (based on some provided omni_config)
 (5) To run all of the tests:
      $ cd gcf/acceptance_tests/AM_API_v1
      $ ./am_api_v1_accept.py -l ../omni_accept.conf -c path/to/omni_config -a AM_url_or_nickname_to_test
     To run individual tests:
      $ ./am_api_v1_accept.py -l ../omni_accept.conf -c path/to/omni_config -a AM_url_or_nickname_to_test Test.test_getversion
 (6) Correct errors and run step (5) again, as needed.
 (7) 
  
A successful run looks like this:
$ ./am_api_v1_accept.py -l ../omni_accept.conf -c ~/.gcf/omni_config.keep -f pgeni_utah  -a pg-utah
NEW TEST: test_getversion
.
----------------------------------------------------------------------
Ran 1 test in 3.496s

OK


An unsuccessful run looks like this:
$ ./am_api_v1_accept.py -l ../omni_accept.conf -c ~/.gcf/omni_config.keep -f pgeni_utah  -a pg-utah2
NEW TEST: test_getversion
F
======================================================================
FAIL: Passes if a 'getversion' call at each aggregate returns an XMLRPC struct with 'geni_api' field set to API_VERSION.
----------------------------------------------------------------------
Traceback (most recent call last):
  File "./am_api_v1_accept.py", line 96, in test_getversion
    self.assertTrue(success_fail, msg)
AssertionError: geni_api version returned "2" not "1" as expected from aggregate "https://www.emulab.net:12369/protogeni/xmlrpc/am/2.0"

----------------------------------------------------------------------
Ran 1 test in 3.751s

FAILED (failures=1)
	   

Further Reading
===============

 * AM API v1 documentation:

