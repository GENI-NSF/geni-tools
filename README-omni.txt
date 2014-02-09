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
[http://trac.gpolab.bbn.com/gcf/wiki/QuickStart the Installation instructions] 
for details on installing Omni.

See README-omniconfigure.txt or 
http://trac.gpolab.bbn.com/gcf/wiki/OmniConfigure/Automatic for details about how to configure Omni.

For 'stitching' support (experimenter defined custom topologies), see
README-stitching.txt.

The currently supported CFs are the GENI Portal,
ProtoGENI,  SFA (!PlanetLab), and GCF. Omni works with any GENI AM API compliant AM.
These include InstaGENI and ExoGENI racks, ProtoGENI, !OpenFlow, SFA and GCF.

Omni performs the following functions:
 * Talks to each CF in its native API
 * Contacts AMs via the GENI AM API

For the latest Omni documentation, examples, and trouble shooting
tips, see the Omni Wiki: http://trac.gpolab.bbn.com/gcf/wiki/Omni

== Release Notes ==

New in v2.5:
 - Avoid sending options to getversion if there are none, to support querying v1 AMs (#375)
 - Fix passing speaksfor and other options to createsliver, renewsliver (#377)
 - Add a 360 second timeout on AM and CH calls. Option `--ssltimeout`
   allows changing this. (#407)
 - Create any directories need in the path to the agg_nick_cache (#383)
 - If using `--AggNickCacheName` and can't read/write to the specified
   file, omni should fall back to reading `agg_nick_cach.base` (#384)
 - Look up AM URN by URL in the defined aggregate nicknames (#404)
 - Eliminated a repetitive log message (#384)
 - Fix bug in APIv3 calling status with slivers with different expiration times (#408)
 - Fit Omni result summaries in 80 character wide terminals (#409)
 - `ForceUseAggNickCache` avoids fetching new cache even if the agg
   nick cache is old (#391)
 - Support `geni_extend_alap` with new `--alap` option, allowing you to
   request that slivers be renewed as long as possible, if your
   requested time is not permitted by local AM policy. (#415)
 - Renew Slice returns actual new expiration (checks the SA, not just
   assuming success means you got what you asked for) (#428)
 - SFA slice and user records changed: keys and slices moved (#429)
 - Fix bug in handling errors in `listimages` and `deleteimage` (#437)
 - Support unicode urns (#448)
 - Return any error message from a CH on `getusercred` (#452)
 - If set, `GENI_FRAMEWORK` environment variable is the default for
   the `--framework` option (#315)
 - If set, `GENI_USERCRED` and `GENI_SLICECRED` environment variables
   set the default path to your saved user and slice credentials (#434)
 - Handle `~` in `usercredfile` and `slicecredfile` (#455)
 - Return error on SA error in `listslices` (#456)
 - Allow `PerformOperationalAction` on v2 AMs (#412)
 - Omni cred_util uses an omni logger (#460)
 - Support querying for other users' SSH keys where the CH supports it (#472)
 - Allow nicknames or URLs in the aggregates list in `omni_config` (#476)
 - Speed up listaggregates in `pgch` framework (don't test AM API
   compliance) (#482)
 - URN testing requires 4 `+` separated pieces (#483)
 - Log at debug when downloading the aggregate nickname cache fails (#485)
 - Add a new framework type `chapi` for talking the uniform federation API 
   (http://groups.geni.net/geni/wiki/UniformClearinghouseAPI)
   to compliant clearinghouses (e.g. GENI Clearinghouse). (#345)
  - See `omni_config.sample` for config options required
   Included in this change:
  - When creating or renewing or deleting slivers, tell the Slice Authority.
    This allows the SA to know (non-authoritatively) where your slice
    has resources. (#439)
  - New function `listslivers <slice>` lists the slivers reported to 
    the slice authority in the given slice, by aggregate (with
    the sliver expirations). Note that this information is not
    authoritative - contact the aggregates if you want to be sure
    not to miss any reservations.
  - New function `listslicemembers <slice>` lists the members of
    the given slice, with their email and registered SSH public
    keys (if any). (#421, #431)
  - New function `addmembertoslice <slice> <member> [optional: role]`
    Adds the member with the given username to the named slice,
    with the given role (or `MEMBER` by default). Note this
    does not change what SSH keys are installed on any existing
    slivers. (#422)
 - `chapi` framework looks up the MA and SA at the clearinghouse,
   though you can configure where they run. (#490)
 - Warn when acting at all AMs in the clearinghouse - slow (#461)
 - Speaks for option has been renamed `geni_speaking_for` (#466)


New in v2.4:
 - Add nicknames for RSpecs; includes ability to specify a default
 location. See the sample omni_config for details. (#265,#360,#361)
 - Make `allocate` accept rspecs loaded from a url (#287)
 - New command `nicknames` lists the known aggregate and rspec nicknames (#146)
 - Split aggregate nicknames into a separate file from `omni_config`. (#352)
   Omni periodically downloads a config file of standard aggregate
   nicknames so you don't have to define these, and can get such
   nicknames as soon as new aggregates are available.
 - New option `--speaksfor` to specify a user urn for the speaks for option. (#339) 
   See http://groups.geni.net/geni/wiki/GAPI_AM_API_DRAFT#ChangeSetP:SupportproxyclientsthatSpeakForanexperimenter
 - New option `--cred` to specify a file containing a credential to
   send to any call that takes a list of credentials. Supply this
   argument as many times as desired. (#46)
 - New option `--optionsfile` takes the name of a JSON format file
   listing additional named options to supply to calls that take
   options. (#327)
   Sample options file content:
{{{
{
 "option_name_1": "value",
 "option_name_2": {"complicated_dict" : 37},
 "option_name_3": 67
}
}}}
 - Log messages: include timestamp, make clearer (#296)
 - Renew to now or past raises an exception (#337)
 - Re-organize Omni help message for readability (#350)
 - When renewing a slice using a saved slice credential, save the new
   slice credential and avoid printing the old slice expiration (#314)
 - Clean up logs and error messages when an aggregate is unreachable. Clients are cached 
   for a given Omni invocation. `CreateSliver` now gets its aggregate similar to other methods. (#275,#311)
 - Add Utah DDC rack (#347)
 - Refactor chhandler credential saving methods into `handler_utils.py` (#309)
 - Explicitly import framework files to support packaging (#322)
 - Ignore unicode vs string in comparing AM URNs (#333)
 - Document omni command line options (#329)
 - Fix parsing of cache ages (#362)
 - Check for 0 sliver expirations in parsing `Provision` results (#364)
 - Allow scripts to use the omni `parse_args` with a supplied parser 
   (one that the script modified from the omni base). (#368)

New in v2.3.2:
 - Make framework_pgch not require a project if slice URN is given (#293)
 - Stop common errors in framework_pgch.py from throwing a stacktrace (#306)
 - `clear-passphrases.py`: fix bug when omni_config is in certain directories (#304) 

New in v2.3.1:
 - Added a new script to do GENI VLAN stitching: stitcher.py
 See README-stitching.txt  (Ticket #250)
 - Ticket #240: don't print ProtoGENI log URL in result summary on success
 - Ticket #242: Be robust to malformed geni_api_versions
 - Refactor file saving utilities out of amhandler and into handler_utils (ticket #248)
 - getversion not caching from PG because the log url looks like an
 error (ticket #249)
 - Busy results from XMLRPC calls missed: is_busy_result looking for
 geni_code in wrong spot (ticket #247)
 - Ensure RSpec test code can call rspeclint (ticket #246)
 - Ticket #245: Return slice URNs from listmyslices in all cases
 - Ticket #226: Look for python in environment in scripts in a more
 friendly way
 - Update sample omni_config (ticket #258)
 - Added `listslices` alias for `listmyslices`, and made username
 argument optional (defaults to your username). (ticket #256)
 - Log ProtoGENI log URL on clearinghouse errors (ticket #251)
 - Added new `get_ch_version` method for querying the the configured
 clearinghouse for its version, if supported. And add support to the
 GENI Clearinghouse interface. (ticket #270)
 - Various minor code cleanup changes
 - Add 3 more known InstaGENI racks to the `omni_config` nicknames
 (ticket #258)
 - Fix pgch handling of new `authority` field for GENI Portal
 accounts, for both slices and users (ticket #279)
 - Make the GENI Clearinghouse framework say 'GENI Clearinghouse', and
 not 'PG' (ticket #281)
 - Add `authority` field to `pgch` framework. Omni users with a 'GENI
 Clearinghouse' account should re download an Omni bundle from the
 Portal and re-run omni-configure, or manually add a line setting
 `authority = panther` (or `ch.geni.net` after June 5). (#268)

New in v2.2.1:
 - omni-configure: Added support for automatic configuration of omni
   for portal credentials. (ticket #252)

New in v2.2:
 - If an aggregate does not speak the requested Ad RSpec version and
 the user is just using the default and the aggregate either speaks
 only 1 RSpec format or specified a default Ad format, then use that
 (ticket #212)
 - If all requested aggregates (or most) speak a different AM API
 version than requested, switch to that. Note that API version
 changes are for the entire Omni invocation, not per
 aggregate. Do not change in dev mode, or if the user explicitly
 specified this API version. (ticket #213)
 - Add new options to set log level: `--error`, `--warn`,
 `--info`. This allows scripts using Omni to suppress output. Note
 that at WARN and ERROR levels, command results (like the manifest
 RSpec) are not printed: use `-o`. If multiple log levels are
 specified, the more verbose log level is used. (tickets #209, #223)
 - If an aggregate does not speak the requested Ad RSpec version,
 print a more helpful message. (ticket #211)
 - Add support for the ProtoGENI / InstaGENI 'createimage' method to
 snapshot your disk. This is only minimally supported by ProtoGENI.
 On success, you should see the URN and URL for the new
 image, and later an email will tell you the image is ready, and the image file will be
 available under `/proj/<project>/images/<imagename>.ndz` on the node
 which was associated with the sliver urn used with the Omni command. See
 http://www.protogeni.net/trac/protogeni/wiki/ImageHowTo (ticket #186)
 - Ticket #232: Implemented ProtoGENI/InstaGENI !DeleteImage: supply
 the URN of your image to delete it.
 - Support ProtoGENI/InstaGENI `ListImages`: list the disk images
 created by the given user, or by you if no name given. (ticket #239)
 - Ticket #237: Print PG error log URL if available
 - Ticket #238: Print the PG log URL in INFO logs on success, in
 result summary on error
 - Support GCF CH `list_my_slices` in the Omni `listmyslices` command (ticket #214)
 - Add a 'gib' framework for geni-in-a-box to talk to the 'pgch' clearinghouse
 - Provision now supplies the `geni_rspec_version` option, to specify
 the manifest format to use.
 - All keys in omni_config are stored lowercase - including aggregate
 nicknames. This means nicknames are case insensitive, and must be
 looked up that way. (ticket # 218)
 - Print error if certificate or key file is empty (ticket #210)
 - Avoid exception if no live AMs are found (ticket #221)
 - Change ProtoGENI Utah, GPO and Kentucky URLs to use port 12369 (ticket #227)

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
 - Strip more useless info from generated filenames
 - Bug fixes, log message cleanup

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
   credential. See `print_slice_expiration`
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

Older changes are listed in the CHANGES file.

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
'optlevel' to set logging to INFO by default, DEBUG if you
specify the `--debug` option to Omni, INFO if you specify `--info`,
etc. If multiple log level options are supplied, Omni uses the most
verbose setting specified. Note that at WARN and ERROR levels, command
outputs are not printed: use the `-o` option to save command results
to files, or --tostdout to print results to STDOUT.

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

The return from `omni.call` is a list of 2 items: a human readable string summarizing the result 
(possibly an error message), and the result object (may be `None` on error). The result 
object type varies by the underlying command called.

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

'''NOTE''': Omni uses multiple command line options, and creates its
own option names internally. Be sure not to pick the same option names. See omni.py and the
getParser() function, around line 781 for all the option names.

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

 To List your slices : `omni.py listmyslices`

 To Print slice expiration : `omni.py print_slice_expiration MySlice`
    
== Running Omni ==

=== Supported options ===
Omni supports the following command-line options.

{{{

$ ~/gcf/src/omni.py -h                            
Usage: 
GENI Omni Command Line Aggregate Manager Tool Version 2.5
Copyright (c) 2014 Raytheon BBN Technologies

omni.py [options] [--project <proj_name>] <command and arguments> 

 	 Commands and their arguments are: 
 		AM API functions: 
 			 getversion 
 			 listresources [In AM API V1 and V2 optional: slicename] 
 			 describe slicename [AM API V3 only] 
 			 createsliver <slicename> <rspec URL, filename, or nickname> [AM API V1&2 only] 
 			 allocate <slicename> <rspec URL, filename, or nickname> [AM API V3 only] 
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
 		Non AM API aggregate functions (supported by some aggregates): 
 			 createimage <slicename> <imagename> [optional: false (keep image private)] -u <sliver urn> [ProtoGENI/InstaGENI only] 
 			 snapshotimage <slicename> <imagename> [optional: false (keep image private)] -u <sliver urn> [ProtoGENI/InstaGENI only] 
 				 [alias for 'createimage'] 
 			 deleteimage <imageurn> [optional: creatorurn] [ProtoGENI/InstaGENI only] 
 			 listimages [optional: creatorurn] [ProtoGENI/InstaGENI only] 
 		Clearinghouse / Slice Authority functions: 
 			 get_ch_version 
 			 listaggregates 
 			 createslice <slicename> 
 			 getslicecred <slicename> 
 			 renewslice <slicename> <new expiration time in UTC> 
 			 deleteslice <slicename> 
 			 listslices [optional: username] [Alias for listmyslices]
 			 listmyslices [optional: username] 
 			 listmykeys
 			 listkeys [optional: username]
 			 getusercred 
 			 print_slice_expiration <slicename> 
			 listslivers <slicename>
			 listslicemembers <slicename>
			 addslicemember <slicename> <membername> [optional: role]
 		Other functions: 
 			 nicknames 

	 See README-omni.txt for details.
	 And see the Omni website at http://trac.gpolab.bbn.com/gcf

Options:
  --version             show program's version number and exit
  -h, --help            show this help message and exit

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
    -t RSPEC-TYPE RSPEC-VERSION, --rspectype=RSPEC-TYPE RSPEC-VERSION
                        RSpec type and version to return, default 'GENI 3'
    -V API_VERSION, --api-version=API_VERSION
                        Specify version of AM API to use (default 2)

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
                        Python logging config file
    --logoutput=LOGOUTPUT
                        Python logging output file [use %(logfilename)s in
                        logging config file]
    --tostdout          Print results like rspecs to STDOUT instead of to log
                        stream

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
                        http://trac.gpolab.bbn.com/gcf/raw-
                        attachment/wiki/Omni/agg_nick_cache. To force Omni to
                        read this cache, delete your local AggNickCache or use
                        --NoAggNickCache.

  For Developers:
    Features only needed by developers

    --abac              Use ABAC authorization
    --arbitrary-option  Add an arbitrary option to ListResources (for testing
                        purposes)
    --devmode           Run in developer mode: more verbose, less error
                        checking of inputs
    --no-compress       Do not compress returned values
    --no-ssl            do not use ssl
    --no-tz             Do not send timezone on RenewSliver
    --orca-slice-id=ORCA_SLICE_ID
                        Use the given Orca slice id
    --raise-error-on-v2-amapi-error
                        In AM API v2, if an AM returns a non-0 (failure)
                        result code, raise an AMAPIError. Default False. For
                        use by scripts.
    --ssltimeout=SSLTIMEOUT
                        Seconds to wait before timing out AM and CH calls.
                        Default is 360 seconds.
}}}

Notes:
 - If set, the `GENI_FRAMEWORK` environment variable will be the
 default for the `--framework` option, over-riding any default from
 your Omni config file.

=== Supported commands ===
Omni supports the following commands.

==== get_ch_version ====
Get the version information advertised by the configured framework /
clearinghouse, if supported. Return is a dictionary.

Format: `omni.py get_ch_version`

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
But you can specify the filename using the `--slicecredfile` option or
by defining the `GENI_SLICECRED` environment variable to the desired path.

Additionally, if you specify the `--slicecredfile` option or define the
`GENI_SLICECRED` environment variable, and that
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

The date-time argument takes a standard form such as "MM/DD/YYYY
HH:MM" (quotes important) or "YYYYMMDDTHH:MM:SSZ". The date and time are separated by 'T'. The
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

==== listslices ====
List slices registered under the given username at the configured
slice authority.
Alias for `listmyslices`.

==== listmyslices ====
List slices registered under the given username at the configured
slice authority.
Not supported by all frameworks.

Format: `omni.py listmyslices [optional: username]`

Sample Usage: `omni.py listmyslices jdoe`

With no `username` supplied, it will look up slices registered to you
(the user whose certificate is supplied).

==== listmykeys ====
Provides a list of the SSH public keys registered at the confiigured
clearinghouse for the current user. 
Not supported by all frameworks.

Sample Usage: `omni.py listmykeys`

==== listkeys ====
Provides a list of SSH public keys registered at the configured
control framework for the specified user, or current user if not defined.
Not supported by all frameworks. Some frameworks only support querying
the current user.

Sample Usage: `omni.py listkeys` or `omni.py listkeys jsmith`

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
  If you specify `--usercredfile` or define the `GENI_USERCRED`
  environment variable:
    First, it tries to read the user credential from that file.
    Second, it saves the user credential to a file by that name (but
    with the appropriate extension).
  Otherwise, the filename is `<username>-<framework nickname from
  config file>-usercred.[xml or json, depending on AM API version]`.
  If you specify the `--prefix` option then that string starts the filename.

If instead of the `-o` option, you supply the `--tostdout` option, then
the user credential is printed to STDOUT.  
Otherwise the user credential is logged.

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

=== listslivers ===
List all slivers of the given slice by aggregate, as recorded at the
clearinghouse. Note that this is non-authoritative information.

Format: `omni.py listslivers <slice name>`

Sample usage: `omni.py listslivers myslices`

Return: String printout of slivers by aggregate, with the sliver expiration if known, AND
a dictionary by aggregate URN of a dictionary by sliver URN of the sliver info records, 
each of which is a dictionary possibly containing:
 - `SLIVER_INFO_URN`: URN of the sliver
 - `SLIVER_INFO_SLICE_URN`: Slice URN
 - `SLIVER_INFO_AGGREGATE_URN`: Aggregate URN
 - `SLIVER_INFO_CREATOR_URN`: URN of the user who reserved the sliver,
 or who first reported the sliver if not known
 - `SLIVER_INFO_EXPIRATION`: When the sliver expires, if known
 - `SLIVER_INFO_CREATION`: When the sliver was created if known (or
 sometimes when it was first reported to the clearinghouse)

This is purely advisory information, that is voluntarily reported by
some tools and some aggregates to the clearinghouse. As such, it is
not authoritative. You may use it to look for reservations, but if you
require accurate information you must query the aggregates. Note in
particular that slivers reserved through Flack are not reported here.

This function is only supported at some `chapi` style clearinghouses,
including the GENI Clearinghouse.

=== listslicemembers ===
List all the members of the given slice, including their registered
public SSH keys.

Format: `omni.py listslicemembers <slicename>`

Sample usage: `omni.py listslicemembers myslice>`

Output prints out the slice members and their SSH keys, URN, and
email.

Return is a list of the members of the slice as registered at the
clearinghouse. For each member, the return includes:
 - `KEYS`: a list of all public SSH keys registered at the clearinghouse
 - `URN` identifier of the member
 - `EMAIL` address of the member

Note that slice membership is only supported at some `chapi` type
clearinghouses, including the GENI Clearinghouse. Slice membership
determines who has rights to get a slice credential and can act on the
named slice. Additionally, all members of a slice ''may'' have their
public SSH keys installed on reserved resources.

Note also that just because a slice member has SSH keys registered does not
mean that those SSH keys have been installed on all reserved compute resources.

=== addmembertoslice ===
Add the named member to the named slice. The member's role in the
slice will be `MEMBER` if not specified.

Format: `omni.py addmembertoslice <slice name> <member username> [role]`

Sample Usage: `omni.py addmembertoslice myslice jsmith`

Return is a boolean indicating success or failure.

Note that slice membership is only supported at some `chapi` type
clearinghouses, including the GENI Clearinghouse. Slice membership
determines who has rights to get a slice credential and can act on the
named slice. Additionally, all members of a slice ''may'' have their
public SSH keys installed on reserved resources.

Note also that `role` may be limited to certain values, typically
`ADMIN`, `MEMBER`, or `AUDITOR`. Typically `AUDITOR` members may not
get a slice credential and so may not act on slices, but may only see them.

This function is typically a privileged operation at the
clearinghouse, limited to slice members with the role `LEAD` or
`ADMIN`.

Note also that adding a member to a slice does not automatically add
their public SSH keys to resources that have already been reserved.

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
with the `--slicecredfile` option it is read from the specified file, if it
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
 - `--slicecredfile <filename>` says to use the given slice credential
 file if it exists.
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

Format:  `omni.py [-a AM_URL_or_nickname] createsliver <slice-name> <rspec filename or URL or nickname>`

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

When you call
     `omni.py createsliver myslice myrspec`
omni will try to read 'myrspec' by interpreting it in the following order:
1. a URL or a file on the local filesystem
2. an RSpec nickname specified in the omni_config
3. a file in a location (file or url) defined as: 
   `<default_rspec_server>/<rspec_nickname>.<default_rspec_extension>` 
where <default_rspec_server> and <default_rspec_extension> are defined in the omni_config.

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

The omni_config `users` section is used to get a set of SSH keys that
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
 - `-t <type version>`: Specify a required manifest RSpec type and
 version to return. It skips any AM that doesn't advertise (in
 !GetVersion) that it supports that format. Default is "GENI
 3". "ProtoGENI 2" is commonly supported as well. 

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
`renewslice`).  Times are in UTC or supply an explicit timezone, and
should be quoted if they contain spaces or forward slashes.

Slice name could be a full URN, but is usually just the slice name portion.
Note that PLC Web UI lists slices as <site name>_<slice name>
(e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

Slice credential is usually retrieved from the Slice Authority. But
with the `--slicecredfile` option it is read from the specified file, if it exists.

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

Aggregates may have local policy that limits how long reservations may
be renewed, possibly per resource type or even per user. By default,
if your reservation cannot be extended to your requested time, the
whole operation fails. To request that your reservation be extended as
long as possible, supply the `--alap` option. Default is `False`. This
option is not supported at all aggregates.

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
    `omni.py -V 3 -a http://myaggregate/url --best-effort renew myslice "2012/09/09 12:00"`
 * Renew the given sliver in myslice at this AM to the given time and
 write the result struct to the given file
{{{
     omni.py -V 3 -a http://myaggregate/url -o --outputfile \
             %s-renew-%a.json -u urn:publicid:IDN+myam+sliver+1 renew \
             myslice 20120909
}}}

This command will renew your resources at each aggregate up to the
specified time.  This time must be less than or equal to the time
available to the slice (see `print_slice_expiration` and
`renewslice`).  Times are in UTC or supply an explicit timezone, and
should be quoted if they contain spaces or forward slashes.

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

Aggregates may have local policy that limits how long reservations may
be renewed, possibly per resource type or even per user. By default,
if your reservation cannot be extended to your requested time, the
whole operation fails. To request that your reservation be extended as
long as possible, supply the `--alap` option. Default is `False`. This
option is not supported at all aggregates.

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

==== createimage ====
Call the ProtoGENI / InstaGENI !CreateImage method, to snapshot the
disk for a single node.

This command is not supported at older ProtoGENI AMs or at non
ProtoGENI AMs.

See http://www.protogeni.net/trac/protogeni/wiki/ImageHowTo

Format: omni.py createimage SLICENAME IMAGENAME [false] -u <SLIVER URN>

By default, images are public. To make the image private, supply the
optional 3rd argument 'false'.

Be sure to supply the URN for the sliver that contains the node whose
disk you want to create an image from.

Image names are alphanumeric.

Note that this method returns quickly; the experimenter gets an email
later when it is done. In the interval, don't change anything.
Note that if you re-use the image name, you replace earlier content.

Slice name could be a full URN, but is usually just the slice name portion.
Note that PLC Web UI lists slices as <site name>_<slice name>
(e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

Slice credential is usually retrieved from the Slice Authority. But
with the `--slicecredfile` option it is read from that file, if it exists.

 - `--sliver-urn` / `-u` option: Use exactly one. Specifies the sliver URN to snapshot.

Aggregates queried:
Only one aggregate should be queried.
 - Single URL given in `-a` argument or URL listed under that given
 nickname in omni_config, if provided, ELSE
 - Single URL given in omni_config aggregates option, if provided
 - You will likely get an error

==== snapshotimage ====
Alias for createimage

==== deleteimage ====
Call the ProtoGENI / InstaGENI !DeleteImage method, to delete a disk
snapshot (image) previously created at a given aggregate.

This command is not supported at older ProtoGENI AMs or at non
ProtoGENI AMs.

See http://www.protogeni.net/trac/protogeni/wiki/ImageHowTo

Format: omni.py deleteimage IMAGEURN [CREATORURN]

Deletes the image with the given URN. Use the image URN from the
return of createimage, or the email ProtoGENI sends when the image
creation is done. If you did not create the image, then you must
supply the URN of the user who did create the image as a 2nd
(optional) argument.

Note that you cannot delete an image that is in use. Note also that
only 1 aggregate will have your image; queries to other aggregates
will return a `SEARCHFAILED` error.

Aggregates queried:
 - Each URL given in an `-a` argument or URL listed under that given
   nickname in `omni_config`, if provided, ELSE
 - List of URLs given in `omni_config` aggregates option, if provided, ELSE
 - List of URNs and URLs provided by the selected clearinghouse

==== listimages ====
Call the ProtoGENI / InstaGENI !ListImages method, to list all disk
snapshots (images) previously created at a given aggregate by a
particular user.

This command is not supported at older ProtoGENI AMs or at non
ProtoGENI AMs.

See http://www.protogeni.net/trac/protogeni/wiki/ImageHowTo

Format: `omni.py listimages [CREATORURN]`

List the disk images created by the given user. 
Takes a user urn or name. If no user is supplied, uses the caller's urn. 
Returns a list of all images created by that user, including the URN 
for deleting the image. Return is a list of structs containing the `url` and `urn` of the iamge.
Note that you should invoke this at the AM where the images were created.

Aggregates queried:
 - Each URL given in an `-a` argument or URL listed under that given
   nickname in `omni_config`, if provided, ELSE
 - List of URLs given in `omni_config` aggregates option, if provided, ELSE
 - List of URNs and URLs provided by the selected clearinghouse

=== nicknames ===
Print / return the known Aggregate and RSpec nicknames, as defined in
the Omni config file(s). 

Sample Output:
{{{
....
  Result Summary: Omni knows the following Aggregate Nicknames:

        Nickname | URL                                                                    | URN
=============================================================================================================
          pg-bbn | https://pgeni.gpolab.bbn.com:12369/protogeni/xmlrpc/am/2.0             | urn:publicid:IDN+pgeni.gpolab.bbn.com+authority+cm
....
Omni knows the following RSpec Nicknames:

  Nickname | Location
====================================================================================
 hellogeni | http://www.gpolab.bbn.com/experiment-support/HelloGENI/hellogeni.rspec

(Default RSpec location: http://www.gpolab.bbn.com/experiment-support )

(Default RSpec extension: rspec )
}}}
