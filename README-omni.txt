{{{
#!comment

N.B. This page is formatted for a Trac Wiki.
}}}

[[PageOutline]]

= The Omni GENI Client =

Omni is a GENI experimenter tool that communicates with GENI Aggregate
Managers (AMs) via the GENI AM API (the common API that GENI
aggregates support).  The Omni client also communicates with
clearinghouses and slice authorities (sometimes referred to as control
frameworks) in order to create slices, delete slices, and
enumerate available GENI Aggregate Managers (AMs). 
A Control Framework (CF) is a framework of resources that provides 
users with GENI accounts (credentials) that they can use to 
reserve resources in GENI AMs.

See INSTALL.txt or 
[http://trac.gpolab.bbn.com/gcf/wiki/OmniQuickStart Omni Quick Start] 
for details on installing Omni.

See README-omniconfigure.txt or
http://trac.gpolab.bbn.com/gcf/wiki/OmniConfigure for details about how to configure Omni.

The currently supported CFs are SFA (!PlanetLab),
ProtoGENI and GCF. Omni works with any GENI AM API compliant AM.
These include SFA, ProtoGENI, !OpenFlow and GCF.

Omni performs the following functions:
 * Talks to each CF in its native API
 * Contacts AMs via the GENI AM API

For the latest Omni documentation, examples, and trouble shooting
tips, see the Omni Wiki: http://trac.gpolab.bbn.com/gcf/wiki/Omni

== Release Notes ==
New in v2.1:
 - Fix ugly error on createslice error (ticket #192)
 - Fix ugly error on unexpected result format in sample myscript
 (ticket #193)
 - `CreateSliver` now accepts an RSpec in JSON format
 - Clean some output messages (`ListResources`, whether omni lists
 the getversion cache name option, a WARN on v2 getversion at a v1
 AM, etc)
 - Clean generated filenames from a protogeni AM (GCF #196)
 - Report PG error log URN on errors, if available (ticket #198)
 - On API version mismatch, report that error in the run summary
  (ticket #200)
 - Remove extra \n's in rspec output (ticket #202)
 - When we switch AM URLs, be sure result is hashed by correct URL
  (ticket #205)
 - Put overall sliver status in the result summary (ticket #197)
 - RSpec can now be a URL instead of a filename (ticket #189)

New in v2.0:

This is a major release. It includes:
 - AM API version 2 is the default. Include the -V option to use AM
 API v1 aggregates (like FOAM)
 - AM API version 3 is supported by all tools
 - Omnispecs are no longer supported in Omni.
 - Added a `--outputfile` option letting you specify the name of the
 file Omni saves results in.
 - Multiple aggregates can be specified on the Omni commandline using
 multiple `-a` options.
 - Lots of code cleanup and bug fixes.

Detailed changes:
 - Make AM API default to version 2, and RSpecs default to GENI 3 (in
 Omni, gcf-am, gcf-test). To talk to an AM API v1 aggregate
 (e.g. FOAM), you must supply an option: `-V1`. (ticket #173)
  AM API v2+ aggregates require that you specify the RSpec format you
 want, when using !ListResources. Omni now specifies the RSpec format
 GENI 3 by default: you can always request a different format, if the
 AM supports it. (ticket #90, #141)

 - Omni no longer supports the deprecated 'omnispecs' RSpec
   format. Use GENI v3 format RSpecs. (ticket #97)
 - Added AM API v3 support (ticket #174)
  - Each API method is a separate Omni command
  - `performoperationalaction` has a synonym: `poa`
  - Omni does not parse Ad RSpecs to reason about valid operational
    states or actions
  - !CreateSliver and other AM API v1&2 methods work only for AMs
    speaking those versions of the AM API.
  - Added new options `--best-effort`, `--sliver-urn` (`-u`) and `--end-time` to
    support passing `geni_best_effort`, individual sliver URNs to act on,
    and `geni_end_time` respectively
  - Support credential structs: Framework classes are responsible for
    tagging credentials with the appropriate type and version. Internally,
    Omni deals with credentials as opaque blobs, except for a few helper
    routines. Credential saving and loading method write to `.xml` or `.json`
    files appropriately, and infer and correct loaded credentials as
    needed.
  - v3 method returns, which are all structs, are saved to `.json`
    files. This means manifest RSpecs (as returned by Describe, Allocate,
    Provision) are one entry in a larger `.json` file. Note that Allocate
    can take a `.json` file as input, and it will extract the request RSpec
    if needed.
  - AM API v3+ Omni methods all return the full code/value/output struct for use
    by scripts. (ticket #183)
  - Omni checks v3 return structs, looking for missing slivers, slivers
    reporting errors, and checking sliver expirations.
 - Omni tries to correct the API version you specify: If you ask for V2
   but are talking to a V3 AM, it tries to reconnect to a V2 URL if the
   AM advertises it. (ticket #91, #141, #164)
 - Added a new option `--outputfile`: With `-o`, this means save command results to
   the given file name. Without this, Omni builds its own filename (as
   before). Include `%a` in specified filename and Omni interpolates an AM
   name. `%s` means insert the slice name. (ticket #175)
 - `getslicecred` and `getusercred` are more consistent in how the result
   is printed, logged, or saved. These methods now honor `-o`, `-p`, and `--stdout` options.
   `getusercred` honors the `--usercredfile` option. (ticket #176)
 - `getversion` output is saved to a `.json` file (ticket #150)
 - Allow specifying multiple aggregates on the command line (multiple
   `-a` options). All methods except `CreateSliver` support
   this. (ticket #177)
 - Added new option `--devmode` (default `False`). When true, only warn on bad
   inputs, but try to pass the bad inputs along anyhow. (ticket #78)
 - Added a new !GetVersion Cache: the results of !GetVersion are
   cached locally as serialed JSON. !ListResources an other calls that
   require information from !GetVersion may use this cache instead.
   !GetVersion does not use the cache by default. Cache entries
   have a max age, after which we always re-query the AM. (ticket #81)
 - libstitch example: Allow caller to specify the per-AM fake manifest RSpec to
   use when in fake mode, by using a comment in the request
   RSpec. (ticket #178)
 - omni-configure: Added new `-e` option to specify the experimenter's private
   SSH key. The public SSH key will be named `private_key.pub`
   (tickets #143, #144, #145)
 - readyToLogin: handle multiple users, multiple keys, the different
   ways different AMs return results, etc (ticket #117, #161, #171)
 - Omni code has been refactored for maintainability and
   extensability. Calls to clearinghouses are in chhandler.py, and to AM
   API functions are in amhandler.py. In the process, input checking and
   output formatting has been further standardized. (tickets #163, #168)
 - Log and return any AM API error return code and message (ticket #149).
 - Added a new option --raise-error-on-v2-amapi-error: When true, and
   using AM API v2, on an error return code, raise an AMAPIError that
   includes the full return struct: this allows scripts to reason about
   the return code. This replaces a special case check for code 7
   (Refused) (ticket #183)
 - `getversion` returns the full struct (code/value/output) to scripts
   (ticket #183)
 - A couple utility methods can take no slice name, just a slice
   credential filename, and read the slice name/urn from the
   credential. See print_slice_expiration
 - When reading a credential from a file, make sure it matches the
   expected slice.
 - Log clearly when a supplied credential filename was not used,
   and instead omni contacted the clearinghouse (ticket #165)
 - Use json.dumps to produce pretty dict output; this allows
   re-parsing that output in Omni, e.g. in Allocate to get the request
   RSpec
 - Replace old `doNonNative` scripting example (`myscript.py`) with a
   script that reads the AM URL and slice name from a comment in the
   supplied RSpec file. (tickets #97, #184)
 - Remove obsolete setup-*.py files. Follow INSTALL.txt to install
   GCF an Omni. (ticket #169)
 - Added a utility function that checks for valid URNs by type,
   including checking AM API v3 rules restricting characters in
   URNs. (ticket #113)
 - Updated to latest SFA (from around July 20th, 2012)
 - Clean up createsliver output (ticket #139)
 - Listresources notes if supplied slice credential is expired (ticket #162)

New in v1.6.2:
 * Added omni-configure.py script to autogenerate the omni_config (#127)
 * Log malformed sliverstatus (#128)
 * Better missing file error messages in delegateSliceCred (#129)
 * Update to SFA codebase as of 4/13/12
 * Bug fix: Handle AM down when !ListResources calls !GetVersion and
   gets a null (#131)
 * Implement list my slices for SFA/PlanetLab (#137)
 * Allow listing public keys installed by / known by the CH (#136)

New in v1.6:
 * Fix bug in printout of !CreateSliver error (ticket #95)
 * Make getversion AM API v2 implementation be consistent with other commands (#109)
 * Added --arbitrary-option to allow testing whether an AM supports an arbitrary option (#111) 
 * Moved omni_config template to be omni_config.sample and changed instructions to match (#83)
 * libstitch example scripts handle V2 AMs in some cases (#119)
 * Updated get_aggregates() call due to changes in SFA (#94)
 * Fix bug in _get_advertised_rspec() (#114)
 * Add --logoutput option and corresponding ability to use %(logfilename)s in log configuration file (#118)
 * readyToLogin.py example script now includes port info if ssh command is not port 22 (#115)
 * Fixed bug where if users attribute is empty in omni_config, then omni exited without a useful error (#116)

New in v1.5.2:
  * validate the API version argument (#92)

New in v1.5.1:
  * Incorporated latest SFA library changes (tag sfa-2.0-4)
  * Complete support of AM API v2 (ticket #69)
    - Default is AM API v1
    - Use -V 2 or --api-version 2 to cause omni to use AM APIv2 to speak to aggregates
   * Added --available to have listresources filter calls to only include available nodes (ticket #74)
   * Added --no-compress to allow the user to specify that AM API call returns should not be compressed (ticket #73)

New in v1.5:
  * Remove AM specific URL validation checks; they were confusing. (ticket #66)
  * Incorporated SFA library fixes
  * Updated readyToLogin script to filter out nodes that aren't ready
    and handle if !PlanetLab has no resources
  * Improved check of manifest RSpec returned by !CreateSliver
  * Added --usercredfile to allow the user to provide their user credential as a file
  * Implemented preliminary (but incomplete) support of AM API v2

New in v1.4:
 * Omni logging is configurable with a -l option, or from a
 script by calling applyLogConfig(). (ticket #61)
 * Omni aborts if it detects your slice has expired (ticket #51)
 * Omni config can define aggregate nicknames, to use instead
 of a URL in the -a argument. (ticket #62)
 * Solved a thread safety bug in omni - copy options list. (ticket #63)
 * SFA logger handles log file conflicts (ticket #48)
 * Handle expired user certs nicely in Omni (ticket #52)
 * Write output filename when !ListResources or !GetVersion saves
 results to a file. (ticket #53)
 * Warn on common AM URL typos. (ticket #54)
 * Pause 10sec and retry (max 3x) if server says it is busy, 
 as PG often does. (ticket #55)
 * SFA library updates (eg slices declare an XML namespace)
 * SFA library bug fixes
 * Added a "--no-tz" option for renewing slivers at older SFA-based
 aggregates. (ticket #65)

New in v1.3.2:
 * Fixed user-is-a-slice bug (ticket #49)

New in v1.3.1:
 * Correctly verify delegated slice credentials
 * Ensure the root error is reported to the user when there are
   problems.
 * Once the user has failed to enter their passphrase twice,
   exit - don't bury it in later errors. (ticket #43)
 * Clean up timezone handling, correctly handling credentials that
 specify a timezone. (ticket #47)
 * examples directory contains simple scripting examples
 * New delegateSliceCred script allowing off-line delegation of
   slice credentials.
   Run src/delegateSliceCred.py -h for usage. (ticket #44)

New in v1.3:
 * Omnispecs are deprecated, and native RSpecs are the default
 * Many commands take a '-o' option getting output saved to a
 file. Specifically, use that with 'listresources' and 'createsliver'
 to save advertisement and manifest RSpecs. See Handling Omni Output below.
 * Slice credentials can be saved to a file and re-used.
 * Added support for GENI AM API Draft Revisions.
 * You can specify a particular RSpec format, at aggregates that speak
 more than one format (eg both SFA and GENI V3).
 * New functions 'listmyslices' and 'print_slice_expiration'
 * All commands return a tuple: text result description and a
 command-specific object, suitable for use by calling scripts
 * Log and output messages are clearer.

Full changes are listed in the CHANGES file.

== Handling Omni Output ==
Omni supports the `-o` option to have Omni save the output of Omni to
one or more files. See the [#RunningOmni documentation] for individual
commands for details.

Omni output is done through the python logging package, and
prints to STDERR by default. Logging levels, format, and output
destinations are configurable by supplying a custom Python logging
configuration file, using the `-l` option. Note that these settings
will apply to the entire Python process. For help creating a logging
config file, see
http://docs.python.org/library/logging.config.html#configuration-file-format
and see the sample `omni_log_conf_sample.conf`. Note that if present
in your configuration file, Omni will use the special variable
'optlevel' to set logging to INFO by default, and DEBUG if you
specify the `--debug` option to Omni.

For further control of Omni output, use Omni as a library from your
own python script (see [#OmniasaLibrary below] for details). 
For example, your script can modify the `-l` logging config file
option between Omni calls. 
Alternatively, you can call the Omni function
`omni.applyLogConfig(<path to your log config file>)`. See the
documentation for `applyLogConfig` for details.

When using Omni as a [#OmniasaLibrary script] and you do `omni.call`
or `omni.applyLogConfig` to load a logging configuration from a file,
existing loggers are NOT disabled (which is the python logging
default). However, those existing loggers will not be modified with
the new logging settings, unless they are explicitly named in the
logging config file (they or their ancestor, where 'root' does not
count).

== Omni as a Library ==

The omni.py file can be imported as a library, enabling programmatic
access to Omni functions. To use Omni as a library, `import omni` and
use the `omni.call` function.

{{{
  text, returnStruct = omni.call( ['listmyslices', username], options )  
}}}

Omni scripting allows a script to:
 * Have its own private options
 * Programmatically set other omni options (like inferring the "-a")
 * Accept omni options (like "-f") in your script to pass along to Omni
 * Parse the returns from Omni commands and use those values in subsequent Omni calls
 * Control or suppress the logging in Omni

See `examples/expirationofmyslices.py` and `examples/myscript.py` in the gcf distribution.
Or [http://trac.gpolab.bbn.com/gcf/wiki/OmniScriptingExpiration Omni Scripting Expiration] 
and
[http://trac.gpolab.bbn.com/gcf/wiki/OmniScriptingWithOptions Omni Scripting with Options] 
on the gcf wiki.

== Extending Omni ==

Extending Omni to support additional frameworks with their own
clearinghouse APIs requires adding a new Framework extension
class. Adding other experiment management or utility functions can be
done using Omni scripting, or by adding functions to amhandler.py

== Omni workflow ==
For a fully worked simple example of using Omni, see 
http://groups.geni.net/geni/wiki/HowToUseOmni

 1. Get your user certificate and keys: Pick a Clearinghouse you want to
    use (that is the control framework you will use). Get a user
    certificate and key pair.
 2. Configure Omni: Be sure the appropriate section of omni_config for
    your framework (sfa/gcf/pg) has appropriate settings for
    contacting that CF, and user credentials that are valid for that
    CF. Make sure the `[omni]` section refers to your CF as the default.
    If you ran src/omni-configure.py this should automatically be
    configured.
 3. Find available resources: Run `omni.py -o listresources`
  a. When you do this, Omni will contact your designated
     Clearinghouse, using your framework-specific user credentials.
  b. The Clearinghouse will list the AMs it knows about. 
  c. Omni will then contact each of the AMs that the
     Clearinghouse told it about, and use the GENI AM API to ask each
     for its resources. 
  d. Omni will save the Advertisement RSpec from each aggregate into a separate
     file (the `-o` option requested that). Files will be named
     `rspec-<server>.xml` or `rspec-<server>.json` depending on the AM
    API version you are using.
 4. Describe the resources you want to request: Create a request Rspec
    to specify which resources you want to reserve. (See
    [http://groups.geni.net/geni/wiki/GENIExperimenter/RSpecs RSpec Documentation] 
    for more details.)
 5. Create a Slice: 
    Run: `omni.py createslice MySlice`
 6. Allocate your resources: 
    Given a slice, and your request rspec file, you are ready to
    allocate resources by creating slivers at each of the AMs.   Note
    you must specify the URL or nickname of the aggregate where you
    want to reserve resources using the `-a` option. Note also that
    here we show a local file for the rspec, but you can supply a URL.

 In AM API v1:
`omni.py -V 1 createsliver -a pg-utah1 MySlice request.rspec`

 In AM API v2 (default) do:
`omni.py createsliver -a pg-utah MySlice request.rspec`

 In AM API v3 this requires 3 steps:
  Step 1:
`omni.py -V 3 allocate -a myV3AM MySlice request.rspec` 
 Reserve the resources. Optionally you may delete the reservation if
 you didn't get what you wanted, or hold your reservation and try
 another reservation elsewhere to match. Be sure to `renew` your
 reservation if you want to hold it a while before you `provision` it.

  Step 2:
`omni.py -V 3 provision -a myV3AM MySlice` 
 Start Instantiating the resources.

 At this point, you likely want to call `status` (see below), to check
 when your slivers have been fully provisioned.

  Step 3:
`omni.py -V 3 performoperationalaction -a myV3AM MySlice geni_start`
 Boot or otherwise make available the resources. The specific actions
 available will be aggregate and sliver type specific. Consult the
 Advertisement RSpec from this aggregate for more information.

 At this point, you have resources and can do your experiment.

 7. Determine the status of your sliver: Use the `sliverstatus`
  command in AM API v1 and v2 (or `status` in AM API v3+) to
  determine the status of your resources.  Resources must typically
  be configured, and possibly booted, before they can be used.

 In AM API v1 & v2:
 When `geni_status` is `ready`, your resources are ready for your
 experiment to use.  Note: If `geni_status` is `unknown`, then
 your resources might be ready. 

 In AM API v1 run: 
`omni.py -V 1 sliverstatus -a pg-utah1 MySlice`

 In AM API v2 run: 
`omni.py sliverstatus -a pg-utah MySlice`

 In AM API v3+:
 After calling `provision`, use `status` to poll the aggregate manager
 and watch as the resources are configured and become ready for use.
 When calling `status`, look for a `geni_operational_state` other than
 `geni_pending_allocation`. The actual operational state that the
 sliver will change to depends on the sliver and aggregate
 type. Operational states are sliver type and aggregate specific, and
 defined in the aggregate's advertisement RSpec. In many cases, the
 aggregate indicates that the sliver is fully allocated with a
 `geni_operational_state` value of `geni_notready`. Once the resources
 are ready for use, you can typically call `performoperationalaction
 geni_start` to start the resources (e.g. boot a machine). You can
 then call `status` again to watch the action take effect. In many
 cases, the operational state will change from `geni_notready` to
 `geni_ready`.

 Run: 
`omni.py -V 3 status -a myV3AM MySlice`

 8. Renew your slice and slivers: Both slices and slivers have
    distinct expiration times.  After a while you may want to Renew
    your Sliver before it expires and is deleted.

 AM API v1: 
`omni.py -V 1 renewsliver -a pg-utah1 MySlice 20120531`

 AM API v2:
`omni.py renewsliver -a pg-utah MySlice 20120531`
 
 AM API V3:
`omni.py -V 3 renew -a myV3AM MySlice 20120531`
    
 9. Do your experiment! 

 Compute resources typically use SSH to let you log in to the
 machines. The SSH keys configured in your omni_config `users` section
 should be available for use.

10. Delete slivers when you are done, freeing the resources for others:

 AM API v1:
`omni.py -V 1 deletesliver -a pg-utah1 MySlice`

 AM API v2:
`omni.py deletesliver -a pg-utah MySlice`

 AM API v3:
`omni.py -V 3 delete -a myV3AM MySlice`

11. Optional: `listmyslices` and `print_slice_expiration`. 
Occasionally you may run `listmyslices` to remind yourself of your
outstanding slices. Then you can choose to delete or renew them as
needed. If you don't recall when your slice expires, use
`print_slice_expiration` to remind yourself. 

 To List your slices : `omni.py listmyslices <username>`

 To Print slice expiration : `omni.py print_slice_expiration MySlice`
    
== Running Omni ==

=== Supported options ===
Omni supports the following command-line options.

{{{

$ ~/gcf/src/omni.py -h                            
Usage:                                                                                        
GENI Omni Command Line Aggregate Manager Tool Version 2.0                                     
Copyright (c) 2012 Raytheon BBN Technologies                                                  

omni.py [options] <command and arguments> 

         Commands and their arguments are: 
                AM API functions:          
                         getversion        
                         listresources [In AM API V1 and V2 optional: slicename] 
                         describe slicename [AM API V3 only]                     
                         createsliver <slicename> <rspec filename or URL> [AM API V1&2 only]
                         allocate <slicename> <rspec filename or URL> [AM API V3 only]
                         provision <slicename> [AM API V3 only]                   
                         performoperationalaction <slicename> <action> [AM API V3 only] 
                         poa <slicename> <action>                                       
                                 [alias for 'performoperationalaction'; AM API V3 only] 
                         sliverstatus <slicename> [AMAPI V1&2 only]                     
                         status <slicename> [AMAPI V3 only]                             
                         renewsliver <slicename> <new expiration time in UTC> [AM API V1&2 only]                                                                                            
                         renew <slicename> <new expiration time in UTC> [AM API V3 only]      
                         deletesliver <slicename> [AM API V1&2 only]                          
                         delete <slicename> [AM API V3 only]                                  
                         shutdown <slicename>                                                 
                Clearinghouse / Slice Authority functions:                                    
                         listaggregates                                                       
                         createslice <slicename>                                              
                         getslicecred <slicename>                                             
                         renewslice <slicename> <new expiration time in UTC>                  
                         deleteslice <slicename>                                              
                         listmyslices <username>                                              
                         listmykeys                                                           
                         getusercred                                                          
                         print_slice_expiration <slicename>                                   

         See README-omni.txt for details.
         And see the Omni website at http://trac.gpolab.bbn.com/gcf

Options:
  --version             show program's version number and exit
  -h, --help            show this help message and exit       
  -c FILE, --configfile=FILE                                  
                        Config file name                      
  -f FRAMEWORK, --framework=FRAMEWORK                         
                        Control framework to use for creation/deletion of
                        slices                                           
  -V API_VERSION, --api-version=API_VERSION                              
                        Specify version of AM API to use (default 2)     
  -a AGGREGATE_URL, --aggregate=AGGREGATE_URL                            
                        Communicate with a specific
			aggregate. Multiple options allowed.
  -t AD-RSPEC-TYPE AD-RSPEC-VERSION, --rspectype=AD-RSPEC-TYPE AD-RSPEC-VERSION
                        Ad RSpec type and version to return, default 'GENI 3'  
  --debug               Enable debugging output                                
  -o, --output          Write output of many functions (getversion,            
                        listresources, allocate, status, getslicecred,...) ,   
                        to a file (Omni picks the name)                        
  --outputfile=OUTPUT_FILENAME                                                 
                        Name of file to write output to (instead of Omni       
                        picked name). '%a' will be replaced by servername,     
                        '%s' by slicename if any. Implies -o. Note that for    
                        multiple aggregates, without a '%a' in the name, only  
                        the last aggregate output will remain in the file.     
                        Will ignore -p.                                        
  -p FILENAME_PREFIX, --prefix=FILENAME_PREFIX                                 
                        Filename prefix when saving results (used with -o, not 
                        --usercredfile, --slicecredfile, or --outputfile)      
  --usercredfile=USER_CRED_FILENAME                                            
                        Name of user credential file to read from if it        
                        exists, or save to when running like '--usercredfile   
                        myUserCred.xml -o getusercred'
  --slicecredfile=SLICE_CRED_FILENAME
                        Name of slice credential file to read from if it
                        exists, or save to when running like '--slicecredfile
                        mySliceCred.xml -o getslicecred mySliceName'
  --tostdout            Print results like rspecs to STDOUT instead of to log
                        stream
  --no-compress         Do not compress returned values
  --available           Only return available resources
  --best-effort         Should AMs attempt to complete the operation on only
                        some slivers, if others fail
  -u SLIVERS, --sliver-urn=SLIVERS
                        Sliver URN (not name) on which to act. Supply this
                        option multiple times for multiple slivers, or not at
                        all to apply to the entire slice
  --end-time=GENI_END_TIME
                        Requested end time for any newly allocated or
                        provisioned slivers - may be ignored by the AM
  -v, --verbose         Turn on verbose command summary for omni commandline
                        tool
  --verbosessl          Turn on verbose SSL / XMLRPC logging
  -q, --quiet           Turn off verbose command summary for omni commandline
                        tool
  -l LOGCONFIG, --logconfig=LOGCONFIG
                        Python logging config file
  --logoutput=LOGOUTPUT
                        Python logging output file [use %(logfilename)s in
                        logging config file]
  --NoGetVersionCache   Disable using cached GetVersion results (forces
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
  --devmode             Run in developer mode: more verbose, less error
                        checking of inputs
  --arbitrary-option    Add an arbitrary option to ListResources (for testing
                        purposes)
  --raise-error-on-v2-amapi-error
                        In AM API v2, if an AM returns a non-0 (failure)
                        result code, raise an AMAPIError. Default False. For
                        use by scripts.
  --no-tz               Do not send timezone on RenewSliver
  --no-ssl              do not use ssl
  --orca-slice-id=ORCA_SLICE_ID
                        Use the given Orca slice id
  --abac                Use ABAC authorization
}}}

=== Supported commands ===
Omni supports the following commands.

==== listaggregates ====
List the URN and URL for all known aggregates.

Format: `omni.py [-a AM_URL_or_nickname] listaggregates`

Sample Usage:
 * List all aggregates from the omni_config 'aggregates' option if supplied, else all aggregates listed by the Clearinghouse
    `omni.py listaggregates`
 * List just the aggregate from the commandline.
    `omni.py -a http://localhost:8001 listaggregates`
 * List just the aggregate from the commandline, looking up the nickname in omni_config.
    `omni.py -a myLocalAM listaggregates`

Gets aggregates from:
 - command line (one per -a arg, no URN available), OR
 - command line nickname (one per -a arg, URN may be supplied), OR
 - omni_config `aggregates` entry (1+, no URNs available), OR
 - Specified control framework (via remote query). This is the
 aggregates that registered with the framework.

==== createslice ====
Creates the slice in your chosen control framework (cf) - that is, at
your selected slice authority.

Format:  `omni.py createslice <slice-name>`

Sample Usage: 
 * `omni.py createslice myslice`
 * Or to create the slice and save off the slice credential:
    `omni.py -o createslice myslice`
 * Or to create the slice and save off the slice credential to a
 specific file:
{{{
     omni.py -o --slicecredfile mySpecificfile-myslice-credfile.xml \
            createslice myslice
}}}

Slice name could be a full URN, but is usually just the slice name portion.
Note that PLC Web UI lists slices as <site name>_<slice name>
(e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

Note that Slice Authorities typically limit this call to
privileged users, e.g. PIs.

Note also that typical slice lifetimes are short. See `renewslice`.

==== getslicecred ====
For a given slice name, get the AM API compliant slice credential
(signed XML document) from the configured slice authority.

Format: `omni.py getslicecred <slicename>`

Sample Usage:
 * Get slice mytest's credential from slice authority, save to a file:
    `omni.py -o getslicecred mytest`
 * Get slice mytest's credential from slice authority, save to a file
 with filename prefix mystuff:
    `omni.py -o -p mystuff getslicecred mytest`
 * Get slice mytest's credential from slice authority,
 save to a file with name mycred.xml:
    `omni.py -o --slicecredfile mycred.xml getslicecred mytest`
 * Get slice mytest credential from saved file
 delegated-mytest-slicecred.xml (perhaps this is a delegated credential?):
    `omni.py --slicecredfile delegated-mytest-slicecred.xml getslicecred mytest`

If you specify the -o option, the credential is saved to a file.
The filename is `<slicename>-cred.xml`
But you can specify the filename using the `--slicecredfile` option.

Additionally, if you specify the `--slicecredfile` option and that
references a file that is not empty, then we do not query the Slice
Authority for this credential, but instead read it from this file.

Arg: slice name
Slice name could be a full URN, but is usually just the slice name portion.
Note that PLC Web UI lists slices as <site name>_<slice name>
(e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

==== renewslice ====
Renews the slice at your chosen control framework. If your slice
expires, you will be unable to reserve resources or delete
reservations at aggregates.

Format:  `omni.py renewslice <slice-name> <new expiration date-time>`

Sample Usage: `omni.py renewslice myslice 20100928T15:00:00Z`

Slice name could be a full URN, but is usually just the slice name portion.
Note that PLC Web UI lists slices as <site name>_<slice name>
(e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

The date-time argument takes a standard form such as
"YYYYMMDDTHH:MM:SSZ". The date and time are separated by 'T'. The
trailing 'Z' in this case represents time zone Zulu, which us UTC or
GMT. You may specify a different time zone, or none. Warning: slice
authorities are inconsistent in how they interpret times (with or
without timezones). The slice authority may interpret the time as a
local time in its own timezone.

==== deleteslice ====
Deletes the slice (at your chosen control framework); does not delete
any existing slivers or free any reserved resources.

Format:  `omni.py deleteslice <slice-name>`

Sample Usage: `omni.py deleteslice myslice`

Slice name could be a full URN, but is usually just the slice name portion.
Note that PLC Web UI lists slices as <site name>_<slice name>
(e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

Delete all your slivers first! Deleting your slice does not free up resources at
various aggregates.

Note that !DeleteSlice is not supported by all control frameworks: some just
let slices expire.

==== listmyslices ====
List slices registered under the given username.
Not supported by all frameworks.

Format: `omni.py listmyslices <username>`

Sample Usage: `omni.py listmyslices jdoe`

==== listmykeys ====
Provides a list of SSH public keys registered at the configured
control framework for the current user.
Not supported by all frameworks.

Sample Usage: `omni.py listmykeys`

==== getusercred ====
Get the AM API compliant user credential (signed XML document) from
the configured slice authority.

Format: `omni.py getusercred`

Sample Usage:
 * Print the user credential obtained from the slice authority:
    `omni.py getusercred`
 * Get the user credential from the slice authority and save it to a file:
    `omni.py -o getusercred`

This is primarily useful for debugging.

If you specify the `-o` option, the credential is saved to a file.
  If you specify `--usercredfile`:
    First, it tries to read the user credential from that file.
    Second, it saves the user credential to a file by that name (but
    with the appropriate extension).
  Otherwise, the filename is `<username>-<framework nickname from
  config file>-usercred.[xml or json, depending on AM API version]`.
  If you specify the `--prefix` option then that string starts the filename.

If instead of the `-o` option, you supply the `--tostdout` option, then
the usercred is printed to STDOUT.  
Otherwise the usercred is logged.

==== print_slice_expiration ====
Print the expiration time of the given slice, and a warning if it is
soon.  e.g. warn if the slice expires within 3 hours.

Format `omni.py print_slice_expiration <slice name>`

Sample Usage: `omni.py print_slice_expiration my_slice`

Arg: slice name
Slice name could be a full URN, but is usually just the slice name portion.
Note that PLC Web UI lists slices as <site name>_<slice name>
(e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

With the `--slicecredfile` option the slice's credential is read from
that file, if it exists. Otherwise the Slice Authority is queried.

==== getversion ====
Call the AM API !GetVersion function at each aggregate.
Get basic information about the aggregate and how to talk to it.

Format:  `omni.py [-a AM_URL_or_nickname] getversion`

Sample Usage:
 * `omni.py getversion`
 * !GetVersion for only this aggregate: 
    `omni.py -a http://localhost:12348 getversion`
 * Save !GetVersion information to per-aggregate files: 
    `omni.py -o getversion`

Aggregates queried:
 - Each URL given in an -a argument or URL listed under that given
 nickname in omni_config, if provided, ELSE
 - List of URLs given in omni_config aggregates option, if provided, ELSE
 - List of URNs and URLs provided by the selected clearinghouse

Output options:
 - `-o`: Save result (JSON format) in per-aggregate files
 - `-p <prefix>`: Prefix for resulting version information files (used with -o)
  - `--outputfile <filename>`: If supplied, use this output file name: substitute the AM for any %a
 - If not saving results to a file, they are logged.
 - If use `--tostdout` option, then instead of logging, print to STDOUT.

Omni caches getversion results for use elsewhere. This method skips the local cache.
 - `--ForceUseGetVersionCache` will force it to look at the cache if possible
 - `--GetVersionCacheAge <#>` specifies the # of days old a cache entry can be, before Omni re-queries the AM, default is 7
 - `--GetVersionCacheName <path>` is the path to the !GetVersion cache, default is ~/.gcf/get_version_cache.json

Options:
 - `--api-version #` or `-V #` or `-V#`: AM API Version # (default: 2)
 - `-l <configfile>` to specify a logging config file
 - `--logoutput <filename>` to specify a logging output filename

Options for development and testing:
 - `--devmode`: Continue on error if possible

==== listresources ====
Call the AM API !ListResources function at specified aggregates,
and print the rspec to stdout or to a file.
Optional argument for AM API v1 & v2 is a slice name which returns a manifest RSpec.
Note that the slice name argument is only supported in AM API v1 and v2.
For listing contents of a slice in AM API v3+, use `describe`.

Format: 
{{{
    omni.py [-a AM_URL_or_nickname] [-o [-p fileprefix] or
                    --outputfile filename] \
                    [-t <RSPEC_TYPE> <RSPEC_VERSION>] \
                    [--api-version <version #, 2 is default, or 1 or 3>] \
                    listresources [slice-name (APIv1 or 2 only)]
}}}

Sample usage:
 * List resources at all AMs on your CH using GENI v3 format advertisement RSpecs
    `omni.py listresources -t geni 3`
 * List resources in myslice from all AMs on your CH (AM API v1 or v2 only)
    `omni.py listresources myslice -t geni 3`
 * List resources in myslice at the localhost AM
    `omni.py -a http://localhost:12348 listresources myslice -t geni 3`
 * List resources at the AM with my nickname myLocalAM (in omni_config)
    `omni.py -a myLocalAM listresources -t geni 3`
 * List resources in myslice at the localhost AM, requesting that the
 AM send a GENI v3 format RSpec.
    `omni.py listresources -a http://localhost:12348 -t GENI 3 myslice`
 * List resources at a specific AM and save it to a file with prefix 'myprefix'.
{{{
    omni.py -a http://localhost:12348 -o -p myprefix listresources myslice \
            -t geni 3
}}}
 * List resources in myslice at the localhost AM, using AM API version
 2 and requesting GENI v3 format manifest RSpecs, saving results to a
 file with the slice and aggregate name inserted.
{{{
    omni.py -a http://localhost:12348 listresources myslice -t geni 3 \
            --api-version 2 -o --outputfile ManRSpec%sAt%a.xml
}}}

This command will list the RSpecs of all GENI aggregates available
through your chosen framework.
It can save the result to a file so you can use an edited version of the result to
create a reservation RSpec, suitable for use in a call to
`createsliver` or `allocate`.

If a slice name is supplied, then resources for that slice only 
will be displayed.  In this case, the slice credential is usually
retrieved from the Slice Authority. But
with the --slicecredfile option it is read from the specified file, if it
exists. Note that the slice name argument is only valid in AM API v1
or v2; for v3, see `describe`.

Aggregates queried:
 - Each URL given in an -a argument or URL listed under that given
 nickname in omni_config, if provided, ELSE
 - List of URLs given in omni_config aggregates option, if provided, ELSE
 - List of URNs and URLs provided by the selected clearinghouse

Output options:
 - `-o`: Save result in per-aggregate files
 - `-p <prefix>`: Prefix for resulting rspec files (used with -o)
 - `--outputfile <filename>`: If supplied, use this output file name: substitute the
 AM for any %a, the slice name for any %s.
 - If not saving results to a file, they are logged.
 - If `--tostdout` option, then instead of logging, print to STDOUT.
 - When using `-o` and not `--outputfile`, file names will indicate the
   slice name, file format, and which aggregate is represented.
   e.g.: `myprefix-myslice-rspec-localhost-8001.xml`

Other options:
 - `--api-version #` or `-V #` or `-V#`: AM API Version # (default: 2)
 - `-t <type version>` Requires the AM send RSpecs in the given type
 and version. If the AM does not speak that type and version, nothing
 is returned. Use `getversion` to see available types at that AM. Type
 and version are case-insensitive strings. This argument defaults to
 'GENI 3' if not supplied.
 - `--slicecredfile <filename>` says to use the given slicecredfile if it exists.
 - `--no-compress`: Request the returned RSpec not be compressed (default is to compress)
 - `--available`: Return Advertisement consisting of only available resources
 - `-l <config file>` to specify a logging config file
 - `--logoutput <filename>` to specify a logging output filename

Options for development and testing:
 - `--devmode`: Continue on error if possible
 - `--arbitrary-option`: supply arbitrary thing (for testing)

==== describe ====
GENI AM API v3 Describe()

Retrieve a manifest RSpec describing the resources contained by the
named entities (e.g. a single slice or a set of the slivers in a
slice). This listing and description should be sufficiently
descriptive to allow experimenters to use the resources. For listing
contents of a slice in APIv1 or 2, or to get the Advertisement of
available resources at an AM, use `listresources`.

Sample usage:
 * Run `describe` on a slice against one aggregate.  Requesting the
 returned Manifest RSpec be in the default GENI v3 RSpec format.
    `omni.py -a http://myaggregate/url -V 3 describe myslice`
 * Run `describe` on a slice against two aggregates. Save the results in a
 file, with the slice name and aggregate name (constructed from the URL) included in the filename.
 into the filename:
{{{
     omni.py -a http://myaggregate/url -a http://another/aggregate -V 3 \
        -o --outputfile RSpecOn%sAt%a.xml describe myslice
}}}
 * Run `describe` on two slivers against a particular aggregate.
{{{
     omni.py -a http://myaggregate/url -V 3 describe myslice \
    	    --sliver-urn urn:publicid:IDN:myam+sliver+sliver1 \
    	    --sliver-urn urn:publicid:IDN:myam+sliver+sliver2
}}}

Argument is a slice name, naming the slice whose contents will be described.
Lists contents and state on 1+ aggregates and prints the result to stdout or to a file.

 - `--sliver-urn` / `-u` option: each usage of this flag specifies a sliver URN to
   describe. If specified, only the listed slivers will be
   described. Otherwise, all slivers in the slice will be described.

Aggregates queried:
 - Each URL given in an `-a` argument or URL listed under that given
 nickname in omni_config, if provided, ELSE
 - List of URLs given in omni_config `aggregates` option, if provided, ELSE
 - List of URNs and URLs provided by the selected clearinghouse

Output directing options:
 - `-o` writes output to file instead of stdout; generates a single file per aggregate.
 - `-p <prefix>` gives a filename prefix for each output file
 - `--outputfile <filename>` If supplied, use this output file name: substitute
 the AM for any %a, and slicename for any %s
 - If not saving results to a file, they are logged.
 - If `--tostdout` option, then instead of logging, print to STDOUT.
 - When using `-o` and not `--outputfile`, file names will indicate the
   slice name, file format, and which aggregate is represented.
   e.g.: `myprefix-myslice-rspec-localhost-8001.json`

Other options:
 - `--api-version #` or `-V #` or `-V#`: AM API Version # (default: 2)
 - `-t <type version>`: Specify a required manifest RSpec type and
 version to return. It skips any AM that doesn't advertise (in
 !GetVersion) that it supports that format. Default is "GENI
 3". "ProtoGENI 2" is commonly supported as well. 
 - `--slicecredfile <path>` says to use the given slice credential file if it exists.
 - --no-compress: Request the returned RSpec not be compressed (default is to compress)
 - `-l <path>` to specify a logging configuration file
 - `--logoutput <filename>` to specify a logging output filename

Options for development and testing:
 - `--devmode`: Continue on error if possible
 - `--arbitrary-option`: supply arbitrary thing (for testing)

==== createsliver ====
The GENI AM API `CreateSliver()` call: reserve resources at GENI aggregates.

For use in AM API v1+2 only. 
For AM API v3+, use this sequence of three commands: `allocate`, `provision`, and `performoperationalaction`.

Format:  `omni.py [-a AM_URL_or_nickname] createsliver <slice-name> <rspec filename or URL>`

Sample Usage:
 * Reserve the resources defined in an RSpec file:
    `omni.py createsliver myslice resources.rspec`
 * Reserve the resources defined in an RSpec file at a particular
 aggregate (specifying aggregate with a nickname):
    `omni.py -a pg-gpo createsliver myslice resources.rspec`
 * Specify using GENI AM API v1 to reserve a sliver in `myslice`
 from a particular AM (specifying aggregate with a nickname), using
 the request rspec in `resources.rspec`:
{{{
     omni.py -a pg-gpo2 --api-version 1 createsliver \
              myslice resources.rspec
}}}
 * Use a saved (possibly delegated) slice credential: 
{{{
     omni.py --slicecredfile myslice-credfile.xml \
             -a pg-gpo createsliver myslice resources.rspec
}}}
 * Save manifest RSpec to a file with a particular prefix: 
{{{
     omni.py -a pg-gpo -o -p myPrefix \
             createsliver myslice resources.rspec
}}}

Note: 
The request RSpec file argument should have been created by using
availability information from a previous call to `listresources`
(e.g. `omni.py -o listresources`). The file can be local or a remote URL.
Warning: request RSpecs are often very different from advertisement
RSpecs.

For help creating GENI RSpecs, see
          http://www.protogeni.net/trac/protogeni/wiki/RSpec.
To validate the syntax of a generated request RSpec, run:
{{{
  xmllint --noout --schema http://www.geni.net/resources/rspec/3/request.xsd \
                      yourRequestRspec.xml
}}}

This `createsliver` command will allocate the requested resources at
the indicated aggregate.

Typically users save the resulting manifest RSpec to learn details
about what resources were actually granted to them. Use the `-o`
option to have that manifest saved to a file. Manifest files are
named something like:
   `myPrefix-mySlice-manifest-rspec-AggregateServerName.xml`

Slice name could be a full URN, but is usually just the slice name portion.
Note that PLC Web UI lists slices as <site name>_<slice name>
(e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

Options:
 - `--api-version #` or `-V #` or `-V#`: AM API Version # (default: 2)
 - `-a <nickname or URL>`: Contact only the aggregate at the given URL, or with the given nickname (that translates to a URL) in your omni_config
 - `--slicecredfile <path>`: Read slice credential from given file, if it exists
 - `-o` Save result (manifest rspec) in per-aggregate files
 - `-p <name>`: Prefix for resulting manifest RSpec files. (Use with `-o`)
 - `--outputfile <name>`: If supplied, use this output file name substituting the AM for any %a, and slicename for any %s.
 - If don't save results to a file, they are logged.
 - If --tostdout option, then instead of logging, print to STDOUT.
 - `-l <path>` to specify a logging config file
 - `--logoutput <filename>` to specify a logging output filename

Options for development and testing:
 - `--devmode`: Continue on error if possible

Slice credential is usually retrieved from the Slice Authority. But
with the `--slicecredfile` option it is read from that file, if it exists.

omni_config users section is used to get a set of SSH keys that
should be loaded onto the remote node to allow SSH login, if the
remote resource and aggregate support this.

Note you likely want to check `sliverstatus` to ensure your resource comes up.
And check the sliver expiration time; you may want to call `renewsliver` to extend the expiration time.

==== allocate ====
GENI AM API Allocate <slice name> <rspec filename or URL>

For use with AM API v3+ only. For AM API v1 and v2 use `createsliver`.

Allocate resources, as described in the request RSpec file name
argument, to a slice URN generated from the provided slice name (or
with the provided URN, if supplied instead of slice name). On success,
one or more slivers are allocated, containing resources satisfying the
request, and assigned to the given slice.

Sample usage:
 * Basic allocation of resources at one AM into myslice
    `omni.py -V 3 -a http://myaggregate/url allocate myslice my-request-rspec.xml`
 * Allocate resources on two AMs, requesting a specific sliver end
 time, saving results into specifically named files (that include an
 AM name calculated from the AM URL),and using the slice credential
 saved in the given file:
{{{
     omni.py -V 3 -a http://myaggregate/url -a http://myother/aggregate \
   	       --end-time 20120909 \
	       -o --outputfile myslice-manifest-%a.json \
	       --slicecredfile mysaved-myslice-slicecred.xml \
	       allocate myslice my-request-rspec.xml
}}}

Clients must `renew` or `provision` slivers before the expiration time
(given in the struct returned from `allocate`), or the aggregate will automatically delete them.

Slice name could be a full URN, but is usually just the slice name portion.
Note that the PLC Web UI lists slices as <site name>_<slice name>
(e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

Slice credential is usually retrieved from the Slice Authority. But
with the `--slicecredfile` option it is read from that file, if it exists.

Aggregates queried:
 - Each URL given in an `-a` argument or URL listed under the given
   nickname in omni_config, if provided, ELSE
 - List of URLs given in omni_config aggregates option, if provided, ELSE
 - List of URNs and URLs provided by the selected clearinghouse

Note that if multiple aggregates are supplied, the same RSpec will be submitted to each.
Aggregates should ignore parts of the Rspec requesting specific non-local resources (bound requests), but each
aggregate should attempt to satisfy all unbound requests. Note also that `allocate()` calls
are always all-or-nothing: if the aggregate cannot give everything requested, it gives nothing.

Output directing options:
 - `-o` Save result in per-Aggregate files
 - `-p <prefix>` (used with `-o`): Prefix for resulting files
 - `--outputfile <filename>` If supplied, use this output file name:
 substitute the AM for any `%a`, and slicename for any `%s`
 - If not saving results to a file, they are logged.
 - If `--tostdout` option, then instead of logging, print to STDOUT.
 - When using `-o` and not `--outputfile`, file names will indicate the
   slice name, file format, and which aggregate is represented.
   e.g.: `myprefix-myslice-allocate-AggregateServerName.json`

Other options:
 - `--api-version #` or `-V #` or `-V#`: AM API Version # (default: 2)
 - `--end-time <time>`: Request that new slivers expire at the given time.
   The aggregates may allocate the resources, but not be able to grant the requested expiration time.
   Note that per the AM API, expiration times will be timezone aware.
   Unqualified times are assumed to be in UTC.
   Note that the expiration time cannot be past your slice expiration
   time (see `renewslice`).
 - `-l <filename>` to specify a logging config file
 - `--logoutput <filename>` to specify a logging output filename

Options for development and testing:
 - `--devmode`: Continue on error if possible

==== provision ====
Calls GENI AM API Provision <slice name>.

For use with AM API v3+ only. For AM API v1 and v2, use `createsliver`.

Request that the named `geni_allocated` slivers be made `geni_provisioned`,
instantiating or otherwise realizing the resources, such that they have a
valid `geni_operational_status` and may possibly be made `geni_ready` for
experimenter use. This operation is synchronous, but may start a longer process,
such as creating and imaging a virtual machine.

Sample usage:
 * Basic `provision` of allocated resources at one AM into `myslice`:
    `omni.py -V 3 -a http://myaggregate/url provision myslice`
 * Provision resources in two AMs, requesting a specific sliver end
 time, save results into named files (that include an AM name
 calculated from the AM URL and slice name), using the slice
 credential saved in the given file. Provision in best effort mode
 to make sure as many resources as possible are provisioned.
{{{ 
     omni.py -V 3 -a http://myaggregate/url \
	   -a http://myother/aggregate \ 
	   --end-time 20120909 \
	   -o --outputfile %s-provision-%a.json \
	   --slicecredfile mysaved-myslice-slicecred.xml \
	   --best-effort provision myslice
}}}

 * Provision allocated resources in specific slivers:
{{{
     omni.py -V 3 -a http://myaggregate/url \
	         --sliver-urn urn:publicid:IDN+myam+sliver+1 \
        	 --sliver-urn urn:publicid:IDN+myam+sliver+2 \ 
		 provision myslice
}}}

Clients must `renew` or use slivers before the expiration time
(given in the return struct), or the aggregate will automatically delete them.

Slice name could be a full URN, but is usually just the slice name portion.
Note that PLC Web UI lists slices as <site name>_<slice name>
(e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

The slice credential is usually retrieved from the Slice Authority. But
with the `--slicecredfile` option it is read from that file, if it exists.

Aggregates queried:
 - Each URL given in an -a argument or URL listed under that given
   nickname in omni_config, if provided, ELSE
 - List of URLs given in omni_config aggregates option, if provided, ELSE
 - List of URNs and URLs provided by the selected clearinghouse

Options:
 - `--sliver-urn` or `-u` option: each specifies a sliver URN to provision. If specified,
   only the listed slivers will be provisioned. Otherwise, all slivers in the slice will be provisioned.
 - `--best-effort`: If supplied, slivers that can be provisioned, will be; some slivers
   may not be provisioned, in which case check the geni_error return for that sliver.
   If not supplied, then if any slivers cannot be provisioned, the whole call fails
   and sliver allocation states do not change.

Note that some aggregates may require provisioning all slivers in the same state at the same
time, per the `geni_single_allocation` !GetVersion return.

omni_config `users` section is used to get a set of SSH keys that
should be loaded onto the remote node to allow SSH login, if the
remote resource and aggregate support this.

Output directing options:
 - `-o`: Save result in per-aggregate files
 - `-p <prefix>` (used with `-o`): Prefix for resulting files
 - `--outputfile <filename>` If supplied, use this output file name: substitute the AM for any `%a`, and slicename for any `%s`
 - If not saving results to a file, they are logged.
 - If `--tostdout` option, then instead of logging, print to STDOUT.
 - When using `-o` and not `--outputfile`, file names will indicate the
   slice name, file format, and which aggregate is represented.
   e.g.: `myprefix-myslice-provision-localhost-8001.json`

Other options:
 - `--api-version #` or `-V #` or `-V#`: AM API Version # (default: 2)
 - `--end-time <time>`: Request that new slivers expire at the given time.
   The aggregates may provision the resources, but not be able to grant the requested
   expiration time.
   Note that per the AM API, expiration times will be timezone aware.
   Unqualified times are assumed to be in UTC.
   Note that the expiration time cannot be past your slice expiration
   time (see `renewslice`).
 - `-l <filename>` to specify a logging config file
 - `--logoutput <filename>` to specify a logging output filename

Options for development and testing:
 - `--devmode`: Continue on error if possible

==== performoperationalaction ====
Alias of "poa" which is an implementation of v3 `PerformOperationalAction`.

==== poa ====
GENI AM API `PerformOperationalAction` <slice name> <action name>.
For use with AM API v3+ only. For AM API v1 or v2 use `createsliver`.

Perform the named operational action on the named slivers or slice, possibly changing
the `geni_operational_status` of the named slivers. e.g. 'start' a VM. For valid
operations and expected states, consult the state diagram advertised in the
aggregate's advertisement RSpec.

Sample usage:
 * Do `geni_start` on all slivers in myslice:
    `omni.py -V 3 -a http://myaggregate poa myslice geni_start`
 * Do `geni_start` on two slivers in myslice, but continue if one fails, and save results to the named file:
{{{
    omni.py -V 3 -a http://myaggregate --best-effort \
   	   -o --outputfile %s-start-%a.json \
	   -u urn:publicid:IDN+myam+sliver+1 \
	   -u urn:publicid:IDN+myam+sliver+2 \
	   poa myslice geni_start
}}}

Clients must `renew` or use slivers before the expiration time
(given in the return struct), or the aggregate will automatically delete them.

Options:
 - `--sliver-urn` / `-u` option: each specifies a sliver URN on which to perform the given action. If specified,
   only the listed slivers will be acted on. Otherwise, all slivers in
   the slice will be acted on.
   Note though that actions are state and resource type specific, so the action may not apply everywhere.

Slice name could be a full URN, but is usually just the slice name
portion.
Note that PLC Web UI lists slices as <site name>_<slice name>
(e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

Aggregates queried:
 - Each URL given in an `-a` argument or URL listed under that given
   nickname in omni_config, if provided, ELSE
 - List of URLs given in omni_config aggregates option, if provided, ELSE
 - List of URNs and URLs provided by the selected clearinghouse

 - `--slicecredfile <path>`: Read slice credential from given file, if it exists.
   Slice credential is usually retrieved from the Slice Authority. But
   with the `--slicecredfile` option it is read from the specified file, if it exists.

 - `--best-effort`: If supplied, slivers that can be acted on, will be; some slivers
   may not be acted on successfully, in which case check the geni_error return for that sliver.
   If not supplied, then if any slivers cannot be changed, the whole call fails
   and sliver states do not change.

Output directing options:
 - `-o`: Save result in per-aggregate files
 - `-p <prefix>` (used with `-o`): Prefix for resulting files
 - `--outputfile <path>`: If supplied, use this output file name: substitute the AM for any `%a` and slicename for any `%s`
 - If not saving results to a file, they are logged.
 - If `--tostdout` option, then instead of logging, print to STDOUT.
 - When using `-o` and not `--outputfile`, file names will indicate the
   slice name, file format, and which aggregate is represented.
   e.g.: `myprefix-myslice-poa-geni_start-localhost-8001.json`

Other options:
 - `--api-version #` or `-V #` or `-V#`: AM API Version # (default: 2)
 - `-l <path>` to specify a logging config file
 - `--logoutput <filename>` to specify a logging output filename

Options for development and testing:
 - `--devmode`: Continue on error if possible

==== renewsliver ====
Calls the AM API v1 or v2 !RenewSliver function.  For AM API v3, see `renew` instead.

Format:  `omni.py [-a AM_URL_or_nickname] renewsliver <slice-name> "<time>"`

Sample Usage:
 * Renew all slivers in slice, myslice, at all aggregates 
    `omni.py renewsliver myslice "12/12/10 4:15pm"`
    `omni.py renewsliver myslice "12/12/10 16:15"`
 * Use AM API v1 to renew slivers in slice, myslice, at one aggregate
{{{
     omni.py -a http://localhost:12348 --api-version 1 \
             renewsliver myslice "12/12/10 16:15"
}}}
 * Renew slivers in slice, myslice, at one aggregate (specified by a nickname)
    `omni.py -a myLocalAM renewsliver myslice "12/12/10 16:15"`

This command will renew your resources at each aggregate up to the
specified time.  This time must be less than or equal to the time
available to the slice (see `print_slice_expiration` and
`renewslice`).  Times are in UTC or supply an explicit timezone.

Slice name could be a full URN, but is usually just the slice name portion.
Note that PLC Web UI lists slices as <site name>_<slice name>
(e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

Slice credential is usually retrieved from the Slice Authority. But
with the --slicecredfile option it is read from the specified file, if it exists.

Aggregates queried:
 - Each URL given in an -a argument or URL listed under that given
 nickname in omni_config, if provided, ELSE
 - List of URLs given in omni_config aggregates option, if provided, ELSE
 - List of URNs and URLs provided by the selected clearinghouse

Note that per the AM API expiration times will be timezone aware.
Unqualified times are assumed to be in UTC. See below for an exception.

Note that the expiration time cannot be past your slice expiration
time (see `print_slice_expiration` and `renewslice`). Some aggregates will
not allow you to _shorten_ your sliver expiration time.

Note that older SFA-based aggregates (like the MyPLC aggregates in the
GENI mesoscale deployment) fail to renew slivers when a timezone is
present in the call from omni. If you see an error from the aggregate
that says `Fault 111: "Internal API error: can't compare
offset-naive and offset-aware date times"` you should add the
"--no-tz" flag to the omni renewsliver command line.

==== renew ====
AM API Renew <slicename> <new expiration time in UTC
or with a timezone>
For use with AM API v3+. For AM API v1 & v2, see `renewsliver`.

Sample usage:
 * Renew slivers in slice myslice to the given time; fail the call if
 all slivers cannot be renewed to this time
    `omni.py -V 3 -a http://myaggregate/url renew myslice 20120909`
 * Renew slivers in slice myslice to the given time; any slivers that
 cannot be renewed to this time, stay as they were, while others are
 renewed
    `omni.py -V 3 -a http://myaggregate/url --best-effort renew myslice 20120909`
 * Renew the given sliver in myslice at this AM to the given time and
 write the result struct to the given file
{{{
     omni.py -V 3 -a http://myaggregate/url -o --outputfile \
             %s-renew-%a.json -u urn:publicid:IDN+myam+sliver+1 renew \
             myslice 20120909
}}}

Slice name could be a full URN, but is usually just the slice name portion.
Note that PLC Web UI lists slices as <site name>_<slice name>
(e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

Slice credential is usually retrieved from the Slice Authority. But
with the `--slicecredfile` option it is read from that file, if it exists.

Aggregates queried:
 - Each URL given in an -a argument or URL listed under that given
   nickname in omni_config, if provided, ELSE
 - List of URLs given in omni_config aggregates option, if provided, ELSE
 - List of URNs and URLs provided by the selected clearinghouse

Note that per the AM API, expiration times will be timezone aware.
Unqualified times are assumed to be in UTC.  Note that the expiration
time cannot be past your slice expiration time (see
`print_slice_expiration` and `renewslice`). Some aggregates will not
allow you to _shorten_ your sliver expiration time.

 - `--sliver-urn <urn>` / -u option: each specifies a sliver URN to renew. If specified,
   only the listed slivers will be renewed. Otherwise, all slivers in the slice will be renewed.
 - `--best-effort`: If supplied, slivers that can be renewed, will be; some slivers
   may not be renewed, in which case check the `geni_error` return for that sliver.
   If not supplied, then if any slivers cannot be renewed, the whole call fails
   and sliver expiration times do not change.

When renewing multiple slivers, note that slivers in the `geni_allocated` state are treated
differently than slivers in the `geni_provisioned` state, and typically are restricted
to shorter expiration times. Users are recommended to supply the `geni_best_effort` option,
and to consider operating on only slivers in the same state.

Note that some aggregates may require renewing all slivers in the same state at the same
time, per the `geni_single_allocation` field returned by `getversion`.

Output directing options:
 - `-o`: Save result in per-aggregate files
 - `-p <prefix>` (used with -o): Prefix for resulting files
 - `--outputfile <path>`: If supplied, use this output file name: substitute the AM for any `%a`, and slicename for any `%s`
 - If not saving results to a file, they are logged.
 - If `--tostdout` option, then instead of logging, print to STDOUT.
 - When using `-o and not `--outputfile`, file names will indicate the
   slice name, file format, and which aggregate is represented.
   e.g.: `myprefix-myslice-renew-localhost-8001.json`

Other options:
 - `--api-version #` or `-V #` or `-V#`: AM API Version # (default: 2)
 - `-l <path>` to specify a logging config file
 - `--logoutput <filename>` to specify a logging output filename

Options for development and testing:
 - `--devmode`: Continue on error if possible

==== sliverstatus ====
GENI AM API !SliverStatus function

Format: omni.py [-a AM_URL_or_nickname] sliverstatus <slice-name>`

Sample Usage:
 * Run `sliverstatus` on all slivers in slice, myslice, at all aggregates 
    `omni.py sliverstatus myslice`
 * Run `sliverstatus` on slivers in slice, myslice, at one aggregate
    `omni.py -a http://localhost:12348 sliverstatus myslice`
 * Use AM API v1 to run `sliverstatus` on slivers in slice, myslice, at one aggregate
    `omni.py -a http://localhost:12348 --api-version 1 sliverstatus myslice`
 * Run `sliverstatus` on slivers in slice, myslice, at one aggregate (specified by a nickname)
    `omni.py -a myLocalAM sliverstatus myslice`

This command will get information from each aggregate about the
status of the specified slice. This can include expiration time,
whether the resource is ready for use, and the SFA node login name.

Slice name could be a full URN, but is usually just the slice name portion.
Note that PLC Web UI lists slices as <site name>_<slice name>
(e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

Slice credential is usually retrieved from the Slice Authority. But
with the `--slicecredfile` option it is read from that file, if it exists.

Aggregates queried:
 - Each URL given in an -a argument or URL listed under that given
 nickname in omni_config, if provided, ELSE
 - List of URLs given in omni_config aggregates option, if provided, ELSE
 - List of URNs and URLs provided by the selected clearinghouse

Options:
 - `--api-version #` or `-V #` or `-V#`: AM API Version # (default: 2)
 - `-o` Save result in per-aggregate files
 - `-p <prefix>` Prefix for resulting files (used with -o)
 - If not saving results to a file, they are logged.
 - If `--tostdout` option, then instead of logging, print to STDOUT.

==== status ====
AM API Status <slice name>.  For use in AM API v3+. 

See `sliverstatus` for the AM API v1 and v2 equivalent.

Sample usage:
 * Get status on the slice at given aggregate
    `omni.py -V 3 -a http://aggregate/url status myslice`
 * Get status on specific slivers and save the result to a file
{{{
    omni.py -V 3 -a http://aggregate/url -o \
            --outputfile %s-status-%a.json -u urn:publicid:IDN+myam+sliver+1 \
            -u urn:publicid:IDN+myam+sliver+2 status myslice
}}}

Slice name could be a full URN, but is usually just the slice name portion.
Note that PLC Web UI lists slices as <site name>_<slice name>
(e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

Slice credential is usually retrieved from the Slice Authority. But
with the `--slicecredfile` option it is read from that file, if it exists.

 - `--sliver-urn` / `-u` option: each specifies a sliver URN to get status on. If specified,
   only the listed slivers will be queried. Otherwise, all slivers in the slice will be queried.

Aggregates queried:
 - Each URL given in an -a argument or URL listed under that given
   nickname in omni_config, if provided, ELSE
 - List of URLs given in omni_config aggregates option, if provided, ELSE
 - List of URNs and URLs provided by the selected clearinghouse

Output directing options:
 - `-o` Save result in per-Aggregate files
 - `-p <prefi>` (used with `-o`) Prefix for resulting files
 - `--outputfile <path>` If supplied, use this output file name: substitute the AM for any `%a`, and slicename for any `%s`
 - If not saving results to a file, they are logged.
 - If `--tostdout` option, then instead of logging, print to STDOUT.
 - When using `-o` and not `--outputfile`, file names will indicate the
   slice name, action, file format, and which aggregate is represented.
   e.g.: `myprefix-myslice-status-localhost-8001.json`

Other options:
 - `--api-version #` or `-V #` or `-V#`: AM API Version # (default: 2)
 - `-l <path>` to specify a logging config file
 - `--logoutput <filename>` to specify a logging output filename

Options for development and testing:
 - `--devmode`: Continue on error if possible

==== deletesliver ====
Calls the AM API v1 and v2 !DeleteSliver function. 
This command will free any resources associated with your slice at
the given aggregates.

For AM API v3, see `delete`.

Format: `omni.py [-a AM_URL_or_nickname] deletesliver <slice-name>`

Sample Usage:
 * Delete all slivers in slice, myslice, at all aggregates 
    `omni.py deletesliver myslice`
 * Delete slivers in slice, myslice, at one aggregate
    `omni.py -a http://localhost:12348 deletesliver myslice`
 * Use AM API v1 to delete slivers in slice, myslice, at one aggregate
    `omni.py -a http://localhost:12348 --api-version 1 deletesliver myslice`
 * Delete slivers in slice, myslice, at one aggregate (specified by a nickname)
    `omni.py -a myLocalAM deletesliver myslice`

Slice name could be a full URN, but is usually just the slice name portion.
Note that PLC Web UI lists slices as <site name>_<slice name>
(e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

Slice credential is usually retrieved from the Slice Authority. But
with the `--slicecredfile` option it is read from that file, if it exists.

Aggregates acted on:
 - Each URL given in an `-a` argument or URL listed under that given
 nickname in omni_config, if provided, ELSE
 - List of URLs given in omni_config aggregates option, if provided, ELSE
 - List of URNs and URLs provided by the selected clearinghouse

==== delete ====
AM API Delete <slicename>. For use in AM API v3+. 
For AM API v1 and v2, see `deletesliver`.

Delete the named slivers, making them `geni_unallocated`. Resources are stopped
if necessary, and both de-provisioned and de-allocated. No further AM API
operations may be performed on slivers that have been deleted.
See `deletesliver` for the AM API v1 and v2 equivalents.

Sample usage:
 * Delete all slivers in the slice at specific aggregates:
    `omni.py -V 3 -a http://aggregate/url -a http://another/url delete myslice`
 * Delete slivers in slice myslice; any slivers that cannot be deleted, stay as they were, while others are deleted
    `omni.py -V 3 -a http://myaggregate/url --best-effort delete myslice`
 * Delete the given sliver in myslice at this AM and write the result struct to the given file
{{{
     omni.py -V 3 -a http://myaggregate/url \
     	     -o --outputfile %s-delete-%a.json \
	     --sliver-urn urn:publicid:IDN+myam+sliver+1 delete myslice
}}}

Slice name could be a full URN, but is usually just the slice name portion.
Note that PLC Web UI lists slices as <site name>_<slice name>
(e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

Slice credential is usually retrieved from the Slice Authority. But
with the `--slicecredfile` option it is read from that file, if it exists.

 - `--sliver-urn` / `-u` option: each specifies a sliver URN to delete. If specified,
   only the listed slivers will be deleted. Otherwise, all slivers in the slice will be deleted.
 - `--best-effort`: If supplied, slivers that can be deleted, will be; some slivers
   may not be deleted, in which case check the geni_error return for that sliver.
   If not supplied, then if any slivers cannot be deleted, the whole call fails
   and slivers do not change.

Aggregates queried:
 - Each URL given in an -a argument or URL listed under that given
   nickname in omni_config, if provided, ELSE
 - List of URLs given in omni_config aggregates option, if provided, ELSE
 - List of URNs and URLs provided by the selected clearinghouse

Output directing options:
 - `-o`: Save result in per-aggregate files
 - `-p <prefix>` (used with `-o`): Prefix for resulting files
 - `--outputfile <path>`: If supplied, use this output file name: substitute the AM for any `%a`, and slicename for any `%s`
 - If not saving results to a file, they are logged.
 - If `--tostdout` option, then instead of logging, print to STDOUT.
 - When using `-o` and not `--outputfile`, file names will indicate the
   slice name, file format, and which aggregate is represented.
   e.g.: `myprefix-myslice-delete-localhost-8001.json`

Other options:
 - `--api-version #` or `-V #` or `-V#`: AM API Version # (default: 2)
 - `-l <path>` to specify a logging config file
 - `--logoutput <filename>` to specify a logging output filename

Options for development and testing:
 - `--devmode`: Continue on error if possible

==== shutdown ====
Calls the GENI AM API Shutdown function.

This command will stop the resources from running, but not delete
their state.  This command should NOT be needed by most users - it is
intended for use by operators when performing emergency stop and
supporting later forensics / debugging.

Format: `omni.py [-a AM_URL_or_nickname] shutdown <slice-name>`

Sample Usage:
 * Shutdown all slivers in slice, myslice, at all aggregates 
    `omni.py shutdown myslice`
 * Shutdown slivers in slice, myslice, at one aggregate
    `omni.py -a http://localhost:12348 shutdown myslice`
 * Use AM API v1 to shutdown slivers in slice, myslice, at one aggregate
    `omni.py -a http://localhost:12348 --api-version 1 shutdown myslice`
 * Shutdown slivers in slice, myslice, at one aggregate (specified by a nickname)
    `omni.py -a myLocalAM shutdown myslice`

Slice name could be a full URN, but is usually just the slice name portion.
Note that PLC Web UI lists slices as <site name>_<slice name>
(e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

Slice credential is usually retrieved from the Slice Authority. But
with the `--slicecredfile` option it is read from that file, if it exists.

Aggregates queried:
 - Single URL given in `-a` argument or URL listed under that given
 nickname in omni_config, if provided, ELSE
 - List of URLs given in omni_config aggregates option, if provided, ELSE
 - List of URNs and URLs provided by the selected clearinghouse
