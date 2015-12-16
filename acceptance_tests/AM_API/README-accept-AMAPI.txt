{{{
#!comment

N.B. This page is formatted for a Trac Wiki.
}}}

[[PageOutline]]

= AM API Acceptance Tests =

== Description ==

Acceptance tests verify compliance to 
[http://groups.geni.net/geni/wiki/GAPI_AM_API_V2 GENI AM API v2].

Alternatively the tests can be run against:
 - [http://groups.geni.net/geni/wiki/GAPI_AM_API_V1 GENI Aggregate Manager (AM) API v1 specification], plus
 - [http://groups.geni.net/geni/wiki/GAPI_AM_API_V2_DELTAS#ChangeSetA Change set A of the AM API v2 specification], or
 - [http://groups.geni.net/geni/wiki/GAPI_AM_API_V3 GENI AM API v3].

Acceptance tests are intended to be run with credentials from the GENI
Clearinghouse, but they work with any credentials that are trusted at the AM under test.

Test verifies: 
     - Sliver creation workflow
        * !CreateSliver : checks that request and manifest match
	* !SliverStatus
	* !ListResources <slice name> : checks that request and manifest match
	* !DeleteSliver
     - Sliver creation workflow works with multiple simultaneous slices
        * checks that you can't use a slice credential from one slice to do
          !ListResources <slicename> on another slice
     - Sliver creation workflow fails when:
        * request RSpec is malformed (ie a tag is not closed)
        * request RSpec is an empty file
     - Sliver creation workflow fails or returns a manifest when:
        * sliver already exists
     - !SliverStatus, !ListResources <slice name>, and !DeleteSliver fail when:
        * slice has been deleted
	* slice never existed
     - !GetVersion return contains either:
        * GENI AM API version 1 
        * 'geni_ad_rspec_versions' (or 'ad_rspec_versions') which in turn
          contains a 'type' and 'version'
        * 'geni_request_rspec_versions' (or 'request_rspec_versions')
          which in turn contains a 'type' and 'version'
	* or alternatively contains expected return from AM API v2 or AM API v3
     - !ListResources returns an advertisement RSpec (that is
       optionally validated with rspeclint)
     - !ListResources works properly with a delegated credential
     - !ListResources FAILS when using a bad user credential
     - !ListResources FAILS when using a valid but untrusted user
       credential 
     - !ListResources supports 'geni_compressed' and 'geni_available' options
     - !RenewSliver for 2 days and 5 days succeeds
     - Shutdown: WARNING, running this test (which is in a separate
       file) likely requires administrator assistance to recover from)
     - Optional AM API v2 support
     - Optional AM API v3 support
        * Testing with AM API v3, runs the same tests as v1/v2, but
	replaces the v1/v2 AM API command with the equivalent v3
	command: 
	  - `Describe()` for `ListResources(slicename)`
	  - `Status()` for `SliverStatus()`
	  - `Allocate()`, `Provision()`, and `PerformOperationalAction()` instead of `CreateSliver()`
	  - `Delete()` instead of `DeleteSliver()`

= Installation & Getting Started =

== Software Dependencies ==

Requires:
 * Omni and the acceptance tests which are distributed as part of the
   [https://github.com/GENI-NSF/geni-tools/wiki gcf] package
 * (optional)
   [http://www.protogeni.net/trac/protogeni/wiki/RSpecDebugging rspeclint]

   (1) Install LibXML (which rspeclint relies on) from CPAN.
    -- On Ubuntu Linux this is the libxml-libxml-perl package
{{{
     	$ sudo apt-get install libxml-libxml-perl
}}}
    -- On Fedora Linux this is the perl-XML-LibXML package
{{{
     	$ sudo yum install perl-XML-LibXML
}}}
   (2) Download rspeclint from ProtoGENI and save the file as `rspeclint` from:
        http://www.protogeni.net/trac/protogeni/wiki/RSpecDebugging

   (3) Add rspeclint to your path.

== Credentials ==

By policy, requires:
 * GENI credentials from the GENI Portal/Clearinghouse Slice Authority (SA) which
   is located at

   {{{https://ch.geni.net/SA}}}

 * A colleague with GENI credentials willing to delegate you a slice.

== Software ==

The GENI AM API Acceptance Tests:
 * $GCF/acceptance_tests/AM_API/am_api_accept.py
 * $GCF/acceptance_tests/AM_API/am_api_accept_shutdown.py
 * $GCF/acceptance_tests/AM_API/am_api_accept_delegate.py
 * $GCF/acceptance_tests/AM_API/am_api_accept_scaling.py
 * $GCF/acceptance_tests/AM_API/am_api_accept_nagios.py

Default omni_config file:
 * `$GCF/acceptance_tests/AM_API/omni_config.sample`

Logging configuration file:
 * `$GCF/acceptance_tests/AM_API/logging.conf`

Script to facilitate using Omni and unittest together:
 * $GCF/src/omni_unittest.py


== Pre-work ==

These instructions assume you have already done the following items:

(1) Allow your Aggregate Manager (AM) to use credentials from the GENI
Clearinghouse.

This step varies by AM type. For example, instructions for doing this with a MyPLC
are here:

   http://groups.geni.net/geni/wiki/GpoLab/MyplcReferenceImplementation#TrustaRemoteSliceAuthority

(2) Request GENI Clearinghouse credentials.  If you don't have any, e-mail:
help@geni.net or see http://groups.geni.net/geni/wiki/SignMeUp

== Usage Instructions ==

(1) Install gcf (which includes Omni and the acceptance tests)

  (a) Install and test gcf per the instructions in INSTALL.txt.
   All of the tests should return "passed".

  (b) Change into the directory where you will run the acceptance
  test:
{{{
      $ cd $GCF/acceptance_tests/AM_API
}}}

  (c) Configure `omni_config`.

     (i) Omni configuration is described in README-omni.txt.

     (ii) Verify the Portal .pem files are found in the location
     specified in the omni_config
{{{
      $ cp omni_config.sample omni_config
}}}

     (iii) Set the `default_project` to the Portal project where you
     will create your testing slices.

  (d) Set PYTHONPATH so the acceptance tests can locate `omni.py`:
{{{
      $ export PYTHONPATH=$PYTHONPATH:$GCF/src
}}}

      Or add the following to your `~/.bashrc`:
{{{
      export PYTHONPATH=${PYTHONPATH}:$GCF/src
}}}
  (e) Verify rspeclint is in your path so that am_api_accept.py can find it.
{{{
      $ rspeclint

      Usage: rspeclint [<namespace> <schema>]+ <document>
}}}
      Schema and document locations are either paths or URLs.

(2) (optional) Run acceptance test with default AM to ensure everything works.
  (a) Move sample RSpecs into place:
 {{{
       $ cp request.xml.sample request.xml
       $ cp request1.xml.sample request1.xml
       $ cp request2.xml.sample request2.xml
       $ cp request3.xml.sample request3.xml
 }}}
  (b) Clear any old acceptance log file:
{{{
      $ \rm acceptance.log
}}}
  (c) Run all of the acceptance tests:
{{{
      $ am_api_accept.py -a am-undertest
}}}
      Optional: To run individual tests:
{{{
      $ am_api_accept.py -a am-undertest Test.test_GetVersion
}}}

(3) Configure to point to AM under test.

  (a) Configure omni_config
    (i) Edit `aggregates` to point to the url of the AM under test.

    (ii) Edit `am-undertest` to point to the url of the AM under test.

  (b) Write three request RSpecs for AM under test.
    (i) Remove the sample RSpecs if you executed (2).
{{{
          $ rm request.xml request1.xml request2.xml request3.xml
}}}
    (ii) Write three [#BoundRSpecs bound request RSpecs] for the AM under test and save as:
 {{{
          $GCF/acceptance_tests/AM_API/request.xml
          $GCF/acceptance_tests/AM_API/request1.xml
          $GCF/acceptance_tests/AM_API/request2.xml
          $GCF/acceptance_tests/AM_API/request3.xml
 }}}
	If you need to run with unbound RSpecs, use the `--un-bound` option.

  (c) To test slice delegation, you will need to:
   send your certificate to a co-worker with a GENI Portal account and have
   them create a slice, reserve resources on that slice, and
   delegate their slice credential to you.

    (i) Have a colleague create a slice. (Keep the slice name under 12
    characters. Here we are using "delegSlice".) Your colleague should do:
{{{
         $ $GCF/src/omni.py -o createslice delegSlice
}}}
    (ii) Have your colleague reserve resources at the AM under
    test. Your colleague should do:
{{{
         $ $GCF/src/omni.py -a am-undertest -o createsliver delegSlice req.xml
}}}
    (iii) Have your colleague download their slice credential:
{{{
         $ $GCF/src/omni.py getslicecred delegSlice -o
}}}
    (iv) Have your colleague delegate their slice to you.
     See $GCF/src/delegateSliceCred.py -h for more information.
     Note that this is the command that your colleague runs, to
    delegate their slice credential to you. In this case, you are the
    delegee, and the `delegeegid` is your certificate that you sent to them.
{{{
         $ $GCF/src/delegateSliceCred.py --cert path/to/their/cert.pem \
              --key path/to/their/key.pem --delegeegid path/to/your/gid_file.pem \
              --slicecred delegSlice-cred.xml
}}}
     Note: This command generates a delegation file named something like
     `ch-geni-net-lnevers-delegated-delegSlice-cred.xml`.

    (v) Place the output delegation file in your acceptance test path as:
{{{
     $GCF/acceptance_tests/AM_API/delegated.xml
}}}

(4) Run "GENI AM API" acceptance tests with a GENI credential accepted by the AM
under test (double check). Make sure you are still in the directory where you will
run the acceptance tests.
{{{
    $ cd $GCF/acceptance_tests/AM_API
}}}
  (a) Clear any old acceptance log file:
{{{
      $ \rm acceptance.log
}}}
  (b) Run all of the tests:
{{{
    $ am_api_accept.py -a am-undertest
}}}
    Optional: To run individual tests replace test_GetVersion with the name of
    the appropriate test:
{{{
    $ am_api_accept.py -a am-undertest Test.test_GetVersion
}}}
    Optional: To run with AM API v3:
{{{ 
    $ am_api_accept.py -a am-undertest -V 3 --NoGetVersionCache
}}}
  (c) Correct errors and run steps (4a and b) again, as needed.

    (i) See "Common Errors and What to Do About It" below.

    (ii) You may find `--more-strict` helpful if your AM returns an empty RSpec
     from !ListResources when a slice does not exist.

(5) Run "Credential Delegation" acceptance tests:
{{{
        $ am_api_accept_delegate.py -a am-undertest
}}}
(6) Run "Shutdown" acceptance tests.  Beware that this test likely requires an
admin to recover from as it runs the AM API command "Shutdown" on a slice.
{{{
        $ am_api_accept_shutdown.py -a am-undertest
}}}
(7) Optional: Test the AM handles multiple calls reasonably (scaling):
{{{
        $ am_api_accept_scaling.py -a am-undertest
}}}

(8) Congratulations! You are done.

== Variations ==

 * To run the tests with AM API v1 plus Change Set A use `-V 1`.  To run
   with AM API v3 use `-V 3`.  But be sure to update the `am-undertest`
   definition to the url of the new AM in `omni_config`.

 * Use `--vv` to have the underlying unittest be more verbose (including
   printing names of tests and descriptions of tests).

 * To validate your RSpecs with rspeclint add the `--rspeclint`
   option:
{{{
        $ am_api_accept.py -a am-undertest --rspeclint
}}}

 * To run with ProtoGENI v2 RSpecs instead of GENI v3 use:
   `--ProtoGENIv2` and `--rspec-file`.(Also replace `request.xml`,
   `request1.xml`, `request2.xml`, and `request3.xml` with appropriate
   files.)

   For example, with the default AM configuration, run:
{{{
     $ am_api_accept.py -a am-undertest --ProtoGENIv2 --rspec-file request_pgv2.xml
}}}
   This provides an appropriate ProtoGENI v2 request RSpec for the test.

 * To run the test with unbound RSpecs add the `--un-bound` flag.

 * It is possible to edit the omni_config to support use of other
   frameworks. 

   - Use `--rspec-file` to override the default RSpec.
   (Also replace `request.xml`, `request1.xml`, `request2.xml`, and
   `request3.xml` with appropriate files.)

   - If you use !PlanetLab, make sure to run the following which will
   cause your !PlanetLab credential to be downloaded:
{{{
        $ omni.py -f plc listresources
}}}
   - If you use gcf, make sure to use the `--more-strict` option.

 * `--untrusted-usercred` allows you to pass in a user credential that
     is not trusted by the framework defined in the `omni_config` for
     use in `Test.test_ListResources_untrustedCredential`

 * Future versions of this test will provide options
   `--rspec-file-list` and `--reuse-slice-list` which take lists of
   RSpec file and lists of existing slicenames for use in
   `Test.test_CreateSliverWorkflow_multiSlice`

 * Some of the tests may be run to monitor AM operations, e.g. via
   nagios. See `am_api_accept_nagios.py`.

== Common Errors and What to Do About It ==

 * When running with ProtoGENI as the AM, you may occasionally get
   intermittent errors caused by making the AM API calls to quickly.
   If you see these errors, either rerun the test or use the
   `--sleep-time` option to increase the time between calls.

 * If you see:
{{{
   NotNoneAssertionError: Return from 'CreateSliver'expected to be XML file but instead returned None.
}}}

Then:
   It's possible that a previous run of the test failed to delete the sliver.
   Manually delete the sliver and try again:
{{{
        $ $GCF/src/omni.py -a am-undertest deleteSliver acc<username>
}}}
where <username> is your Unix account username.

 * If a test fails, look at
   the contents of the `acceptance.log` file for an indication of the
   source of the problem. Consider running the single test alone, using syntax like the following:
{{{
        $ am_api_accept.py -a am-undertest Test.test_GetVersion
}}}
== Sample Output ==

A successful run looks something like this:
{{{
$ ./am_api_accept.py --NoGetVersionCache --sleep-time 0 -a https://localhost:8001 \
                     -V 2 --rspec-file ../../src/gcf/geni/am/amapi2-request.xml
.............
----------------------------------------------------------------------
Ran 13 tests in 18.542s

OK
}}}

Acceptance Tests output of help message:
{{{
$ ./am_api_accept.py -h
Usage: 
      ./am_api_accept.py -a am-undertest 
      Also try --vv

     Run an individual test using the following form...
     ./am_api_accept.py -a am-undertest Test.test_GetVersion

Options:
  --version             show program's version number and exit
  -h, --help            show this help message and exit
  --reuse-slice=REUSE_SLICE_NAME
                        Use slice name provided instead of creating/deleting a
                        new slice
  --rspec-file=RSPEC_FILE
                        In CreateSliver tests, use _bound_ request RSpec file
                        provided instead of default of 'request.xml'
  --untrusted-usercredfile=UNTRUSTED_USER_CRED_FILENAME
                        Name of an untrusted user credential file to use in
                        test: test_ListResources_untrustedCredential
  --rspec-file-list=RSPEC_FILE_LIST
                        In multi-slice CreateSliver tests, use _bound_ request
                        RSpec files provided instead of default of
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
                        (Default: 30 seconds)
  --monitoring          Print output to allow tests to be used in monitoring.
                        Output is of the form: 'MONITORING test_TestName 1'
                        The third field is 1 if the test is successful and 0
                        is the test is unsuccessful.
  --pure-v1             Allows some tests to check for AM API v1 compliance
                        without Change Set A.  -V must be set to '1'.
  --delegated-slicecredfile=DELEGATED_SLICE_CRED_FILENAME
                        Name of a delegated slice credential file to use in
                        test: test_ListResources_delegatedSliceCred
  --un-bound            RSpecs are unbound (requesting some resources, not a
                        particular resource)
  --skip-renew          Skip all Renew or RenewSliver tests (default False)
  --vv                  Give -v to unittest
  --qq                  Give -q to unittest

  Basic and Most Used Options:
    -a AGGREGATE_URL, --aggregate=AGGREGATE_URL
                        Communicate with a specific aggregate
    --available         Only return available resources
    -c FILE, --configfile=FILE
                        Config file name (aka `omni_config`)
    -f FRAMEWORK, --framework=FRAMEWORK
                        Control framework to use for creation/deletion of
                        slices
    -r PROJECT, --project=PROJECT
                        Name of project. (For use with pgch framework.)
    --alap              Request slivers be renewed as close to the requested
                        time as possible, instead of failing if the requested
                        time is not possible. Default is False.
    -V API_VERSION, --api-version=API_VERSION
                        Specify version of AM API to use (default v2)
    --useSliceAggregates
                        Perform the slice action at all aggregates the given
                        slice is known to use according to clearinghouse
                        records. Default is False.

  AM API v3+:
    Options used in AM API v3 or later

    --best-effort       Should AMs attempt to complete the operation on only
                        some slivers, if others fail
    --cred=CRED_FILENAME
                        Send credential in given filename with any call that
                        takes a list of credentials
    --end-time=GENI_END_TIME
                        Requested end time for any newly allocated or
                        provisioned slivers - may be ignored by the AM
    --start-time=GENI_START_TIME
                        Requested start time for any allocated slivers - NOW
                        if not provided, could be for future reservations
    --optionsfile=JSON_OPTIONS_FILENAME
                        Send all options defined in named JSON format file to
                        methods that take options
    --speaksfor=USER_URN
                        Supply given URN as user we are speaking for in Speaks
                        For option
    -u SLIVERS, --sliver-urn=SLIVERS
                        Sliver URN (not name) on which to act. Supply this
                        option multiple times for multiple slivers, or not at
                        all to apply to the entire slice
    --cancelled         Should Describe show sliver state of only
                        geni_provisioned slivers, ignoring any geni_updating
                        and geni_allocated slivers (default False)

  Logging and Verboseness:
    Control the amount of output to the screen and/or to a log

    -q, --quiet         Turn off verbose command summary for omni commandline
                        tool
    -v, --verbose       Turn on verbose command summary for omni commandline
                        tool
    --debug             Enable debugging output. If multiple loglevel are set
                        from commandline (e.g. --debug, --info) the more
                        verbose one will be preferred.
    --info              Set logging to INFO.If multiple loglevel are set from
                        commandline (e.g. --debug, --info) the more verbose
                        one will be preferred.
    --warn              Set log level to WARN. This won't print the command
                        outputs, e.g. manifest rspec, so use the -o or the
                        --outputfile options to save it to a file. If multiple
                        loglevel are set from commandline (e.g. --debug,
                        --info) the more verbose one will be preferred.
    --error             Set log level to ERROR. This won't print the command
                        outputs, e.g. manifest rspec, so use the -o or the
                        --outputfile options to save it to a file.If multiple
                        loglevel are set from commandline (e.g. --debug,
                        --info) the more verbose one will be preferred.
    --verbosessl        Turn on verbose SSL / XMLRPC logging
    -l LOGCONFIG, --logconfig=LOGCONFIG
                        Python logging config file. Default: 'none'
    --logoutput=LOGOUTPUT
                        Python logging output file [use %(logfilename)s in
                        logging config file]. Default: 'acceptance.log'
    --tostdout          Print results like rspecs to STDOUT instead of to log
                        stream
    --noLoggingConfiguration
                        Do not configure python logging; for use by other
                        tools.

  File Output:
    Control name of output file and whether to output to a file

    -o, --output        Write output of many functions (getversion,
                        listresources, allocate, status, getslicecred,...) ,
                        to a file (Omni picks the name)
    -p FILENAME_PREFIX, --prefix=FILENAME_PREFIX
                        Filename prefix when saving results (used with -o, not
                        --usercredfile, --slicecredfile, or --outputfile)
    --outputfile=OUTPUT_FILENAME
                        Name of file to write output to (instead of Omni
                        picked name). '%a' will be replaced by servername,
                        '%s' by slicename if any. Implies -o. Note that for
                        multiple aggregates, without a '%a' in the name, only
                        the last aggregate output will remain in the file.
                        Will ignore -p.
    --usercredfile=USER_CRED_FILENAME
                        Name of user credential file to read from if it
                        exists, or save to when running like '--usercredfile
                        myUserCred.xml -o getusercred'. Defaults to value of
                        'GENI_USERCRED' environment variable if defined.
    --slicecredfile=SLICE_CRED_FILENAME
                        Name of slice credential file to read from if it
                        exists, or save to when running like '--slicecredfile
                        mySliceCred.xml -o getslicecred mySliceName'. Defaults
                        to value of 'GENI_SLICECRED' environment variable if
                        defined.

  GetVersion Cache:
    Control GetVersion Cache

    --NoGetVersionCache
                        Disable using cached GetVersion results (forces
                        refresh of cache)
    --ForceUseGetVersionCache
                        Require using the GetVersion cache if possible
                        (default false)
    --GetVersionCacheAge=GETVERSIONCACHEAGE
                        Age in days of GetVersion cache info before refreshing
                        (default is 7)
    --GetVersionCacheName=GETVERSIONCACHENAME
                        File where GetVersion info will be cached, default is
                        ~/.gcf/get_version_cache.json
    --noCacheFiles      Disable both GetVersion and Aggregate Nickname cache
                        functionality completely; no files are downloaded,
                        saved, or loaded.

  Aggregate Nickname Cache:
    Control Aggregate Nickname Cache

    --NoAggNickCache    Disable using cached AggNick results and force refresh
                        of cache (default is False)
    --ForceUseAggNickCache
                        Require using the AggNick cache if possible (default
                        False)
    --AggNickCacheAge=AGGNICKCACHEAGE
                        Age in days of AggNick cache info before refreshing
                        (default is 1)
    --AggNickCacheName=AGGNICKCACHENAME
                        File where AggNick info will be cached, default is
                        ~/.gcf/agg_nick_cache
    --AggNickDefinitiveLocation=AGGNICKDEFINITIVELOCATION
                        Website with latest agg_nick_cache, default is
                        https://raw.githubusercontent.com/GENI-NSF/geni-
                        tools/master/agg_nick_cache.base. To force Omni to
                        read this cache, delete your local AggNickCache or use
                        --NoAggNickCache.

  For Developers / Advanced Users:
    Features only needed by developers or advanced users

    --useSliceMembers   DEPRECATED - this option no longer has any effect. The
                        option is always true, unless you specify
                        --noSliceMembers.
    --noSliceMembers    Reverse of --useSliceMembers. Do NOT create accounts
                        or install slice members' SSH keys on reserved
                        resources in createsliver, provision or
                        performoperationalaction. Default is False. When
                        specified, only users from your omni_config are used
                        (unless --ignoreConfigUsers).
    --ignoreConfigUsers
                        Ignore users and SSH keys listed in your omni_config
                        when installing SSH keys on resources in createsliver
                        or provision or performoperationalaction. Default is
                        false - your omni_config users are read and used.
    --ssltimeout=SSLTIMEOUT
                        Seconds to wait before timing out AM and CH calls.
                        Default is 360 seconds.
    --noExtraCHCalls    Disable extra Clearinghouse calls like reporting
                        slivers. Default is False.
    --devmode           Run in developer mode: more verbose, less error
                        checking of inputs
    --raise-error-on-v2-amapi-error
                        In AM API v2, if an AM returns a non-0 (failure)
                        result code, raise an AMAPIError. Default is False.
                        For use by scripts.
    --maxBusyRetries=MAXBUSYRETRIES
                        Max times to retry AM or CH calls on getting a 'busy'
                        error. Default: 4
    --no-compress       Do not compress returned values
    --abac              Use ABAC authorization
    --arbitrary-option  Add an arbitrary option to ListResources (for testing
                        purposes)
    --no-ssl            do not use ssl
    --no-tz             Do not send timezone on RenewSliver
    --orca-slice-id=ORCA_SLICE_ID
                        Use the given Orca slice id

$ ./am_api_accept_delegate.py -h      
Usage:                                                                    
      ./am_api_accept_delegate.py -a am-undertest                         
      Also try --vv                                                       

<snip>


$ ./am_api_accept_shutdown.py -h   
Usage:                                                                 
      ./am_api_accept_shutdown.py -a am-undertest                      
      Also try --vv                                                    
  WARNING: Be very careful running this test. Administator support is
  likely to be needed to recover from running this test. 

<snip>

$ ./am_api_accept_scaling.py -h
Usage: 
      ./am_api_accept_scaling.py -a am-undertest
      Also try --vv

Options:
<snip>
  --max-createsliver-time=MAX_TIME
                        Max number of seconds will attempt to check status of
                        a sliver before failing  [default: 180]
  --num-slices=NUM_SLICES
                        Number of slices to create [default: 3]
  --slice-name=SLICE_NAME
                        Use slice name as base of slice name [default: scale]
<snip>
}}}

= Manual Tests =
Not all AM API features and requirements can be readily tested with
automated tests. For example, a test that says 'now wait 3 days' is
impractical. Here we outline tests that aggregate developers should
manually run to confirm AM API compliance.

== Log in to Nodes ==
This set of tests verifies that reserved compute resources are
accessible as expected.

 1. Can you log in to all reserved nodes?
In AM API v1 or 2, use AM and sliver specific mechanisms to determine
how to 'log in' to reserved nodes. Use that and log in. See
gcf/src/readyToLogin.py for help determining how to log in. In AM API
v3, see the 'ssh-users' elements in the manifest RSpec.

 2. Are all keys configured in `omni_config` usable for logging in?
All public SSH keys listed under users who are part of the `users` section of the
`omni_config` should be installed on nodes that use such
keys. Depending on the sliver type, the keys may be installed on a
single user or multiple users. As above, see `readyToLogin.py` for
hints. 
  a. Configure `omni_config` with 2+ users, each with 2+ keys
  b. Reserve 2+ nodes
  c. Run `readyToLogin` for tips on how to access nodes
  d. Try to log in using each SSH key listed in the
  `omni_config`. Test fails if any configured key cannot access a node.

== Node Configuration ==
This set of tests verifies that reserved compute resources have the
configuration specified in the manifest RSpec.

 1. Do reserved nodes have the hostname, IP, and disk image specifie
 in the manifest RSpec?
 2. Are data plane interfaces live as described in the manifest: on
 the expected LAN, with the expected IP address, able to reach
 expected other nodes? And no other nodes are reachable from those
 interfaces?
 3. Have any `install` and `execute` tags been run as promised?

== !RenewSliver ==
This test verifies that in AM API v2, the aggregate returns the
correct sliver expiration time, in its own aggregate-specific way. In
AM API v3, there is a standard way to get this value.

 1. Reserve some resources
 2. Check for an aggregate specific statement of sliver
 expiration. This is often in the return from `SliverStatus`. Field
 names include `orca_expires', `pg_expires`.
  a. Value should be > now
  b. Value should be <= slice expiration
 3. Call `RenewSliver` to renew sliver until
 current-expiration-plus-1-minute. Assuming success:
  a. Check aggregate specific sliver expiration (as above)
  b. Value should be == the requested expiration time
 
== Sliver Expiration ==
This test verifies that aggregates do not expire slivers early, change
sliver expiration after a Renew call, and actually expire slivers when
they are supposed to expire - including freeing resources.

 1. Do renewed slivers stay active past old expiration time, until new
 time?
  a. Reserve resources (!CreateSliver or Allocate)
  b. Get current sliver expiration (in AM or API specific way:
  `geni_expires` in AM API v3, or from !SliverStatus as described above)
  c. Renew sliver to oldTime+1 minute
  d. Confirm (in AM specific or API specific way) that AM reports new
  expiration time for the sliver
  e. Wait until old expiration time
   i. Confirm resources still reachable (nodes can be pinged, even can
   log in)
   ii. Confirm in AM/API specific way that AM still reports new
   expiration time
 2. After sliver expiration time is reached
  a. Confirm AM API calls reflect that the sliver has expired.
   - Not in manifest
   - API calls querying the sliver give errors
  b. Confirm the resources no longer accessible. (Ping, try logging in)
  c. Confirm the resources listed as available in the Ad RSpec.

= Bibliography =

 1. AM API v1 documentation: http://groups.geni.net/geni/wiki/GAPI_AM_API_V1
 2. AM API v2 change set A documentation: http://groups.geni.net/geni/wiki/GAPI_AM_API_V2_DELTAS#ChangeSetA
 3. AM API v2 documentation: http://groups.geni.net/geni/wiki/GAPI_AM_API_V2
 3. AM API v3 documentation: http://groups.geni.net/geni/wiki/GAPI_AM_API_V3
 4. gcf and Omni documentation: https://github.com/GENI-NSF/geni-tools/wiki
 5. rspeclint code: http://www.protogeni.net/resources/rspeclint
 6. rspeclint documentation: http://www.protogeni.net/trac/protogeni/wiki/RSpecDebugging

= Notes =

== Bound RSpecs ==
A ''bound'' request RSpec explicitly lists all resources in the
RSpec. (This is as opposed to requesting some resource without
specifying which instance is being requested.) This is important
because the acceptance tests compare the component IDs of the
resources in the request RSpec with those in the manifest RSpecs to
make sure that !CreateSliver and !ListResources are working properly.

To run the test with unbound RSpecs, add the `--un-bound` flag.
