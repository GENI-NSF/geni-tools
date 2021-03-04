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
[https://github.com/GENI-NSF/geni-tools/wiki/QuickStart the Installation instructions] 
for details on installing Omni.

See README-omniconfigure.txt or
https://github.com/GENI-NSF/geni-tools/wiki/Omni-Configuration-Automatically for details about how to configure Omni.

For 'stitching' (experimenter defined custom topologies) or
multi-aggregate topologies, see README-stitching.txt.

The currently supported CFs (clearinghouses) are the GENI Portal,
ProtoGENI,  SFA (!PlanetLab), and GCF. Omni works with any GENI AM API compliant AM.
These include InstaGENI and ExoGENI racks, ProtoGENI, !OpenFlow, SFA, AL2S, FOAM and GCF.

Omni performs the following functions:
 * Talks to each CF in its native API
 * Contacts AMs via the GENI AM API

For the latest Omni documentation, examples, and trouble shooting
tips, see the Omni Wiki: https://github.com/GENI-NSF/geni-tools/wiki/Omni

== Release Notes ==
New in v2.11
 * Due to the changes in the underlying OpenSSL versions some minor changes to SSL protocol versions were implemented.
   These changes were needed to make omni run on newer Operating Systems using the updated OpenSSL version

New in v2.10:
 * Continue anyway if no aggregate nickname cache can be loaded. (#822)
  * Sliver info reporting and operations on AMs by nickname will likely fail.
 * For connections to servers, use TLSv1 if possible (falling back to SSLv3
   in the usual OpenSSL way), plus a restricted set of ciphers
   (`HIGH:MEDIUM:!ADH:!SSLv2:!MD5:!RC4:@STRENGTH`) when using python2.7.
   This avoids some security issues, and allows Omni on older clients
   to connect to some updated servers. (#745)
 * Use `False` instead of `'f'` for `SLICE_EXPIRED` and `PROJECT_EXPIRED` when 
   using Common Federation API clearinghouses. (#856)
  * Thanks to Umar Toseef for the bug report.
 * Do not assume `PROJECT_MEMBER_UID` is returned when listing project members,
   but allow it. (#857)
  * Thanks to Umar Toseef for the bug report.
 * Calling `getslicecred` while specifying a `slicecredfile` that exists
   no longer means just return that file. Instead, that file will be
   ignored and, if you specify `-o`, replaced. (#868, #869)
 * Moved canonical `agg_nick_cache` location to Github. (#814, #882)
 * Use `urllib2.urlopen` instead of `urllib.urlretrieve` to avoid bad
   interaction with M2Crypto. (#881)

New in v2.9:
 * If `sliverstatus` fails in a way that indicates there are no local resources,
   and the caller specified `--raise-error-on-v2-amapi-error`, still delete any
   sliver info records at the clearinghouse (as necessary). (#778)
 * If `deletesliver` or `delete` fail indicating there are no local resources,
   delete any sliver info records at teh clearinghouse (as necessary). (#782)
 * Add 11 aggregates to the nickname cache. (#783)
 * Trim fractional seconds from user input datetimes before passing to servers. (#795)
  * Avoids errors in ProtoGENI based code.
 * Allow getting Ad RSpecs (calling `ListResources` not in slice context)
   without a user credential. (#793)
  * Implements AM API Change Proposal AD.
 * If the return from `POA` is a `geni_credential`, or per sliver has a
   `geni_credential`, then save that cred in a separate file. (#803)
  * Also when saving output, JSON that has XML content shouldn't get
    the header inserted within the XML content.

New in v2.8:
 * Allow configuring how many times Omni retries on a busy error from
   an AM or CH. Use `--maxBusyRetries`. Default remains 4. (#749)
 * Support `Update()` and `Cancel()` from AM APIv4 in any v3+ implementation. Support
   is only known at ProtoGENI, and is limited. (#589)
 * New option `--noCacheFiles` completely disables reading or writing the !GetVersion and
   Aggregate nickname cache files. (#772)
 * New config that sets the current release number and a release message,
   so Omni can alert you if a new release is available. (#698)
 * Better control of Omni logging configuration. (#458)
  * Allow a Python logging configuration dictionary, and configure
    logging from that if possible.
  * New option `--noLoggingConfiguration` completely disables
    configuring Python loggers from Omni. A script might use this to
    allow it to configure logging later in its own way.
 * Fix error message on expired user cert. (#756)
 * Remove ticket #722 workaround (bug fixed at ION AM). (#724)
 * Mac installer: remove old aliases before adding new ones. (#556)
 * Clean up `listresources` summary string and include sliver expiration if known. (#704)
 * Add support for `--start-time` option to specify a `geni_start_time` option
   for any aggregates that support such a value. (#660)
 * Update copyrights to 2015 (#764)
 * Add nicknames for !CloudLab and Apt. (#767)
 * Avoid exception on empty aggregate in `-a` argument. (#771)
 * Support python 2.7.9+ where we must request not verifying server certificates
   for the SSL connection. Thanks to Ezra Kissel. (#776)

New in v2.7:
 * Calls to `status` and `sliverstatus` will also call the CH
   to try to sync up the CH records of slivers with truth
   as reported by the AM. (#634)
 * Make `useSliceMembers` True by default and deprecate the option. (#667)
  * By default, Omni will create accounts and install SSH keys for members of your slice, 
    if you are using a CHAPI style framework / Clearinghouse 
    which allows defining slice members (as the GENI Clearinghouse does). 
  * This is not a change for Omni users who configured Omni using the `omni-configure` script,
    which already forced that setting to true.
  * The old `--useSliceMembers` option is deprecated and will be
    removed in a future release.
  * Added new option `--noSliceMembers` to over-ride that default and tell Omni
    to ignore any slice members defined at the Clearinghouse.
  * You may also set `useslicemembers=False` in the `omni` section of
    your `omni_config` to over-ride the `useSliceMembers` default of True.
 * Honor the `useslicemembers` and `ignoreconfigusers` options in the `omni_config` (#671)
 * Fix `get_member_email` e.g. from `listprojectmembers` for speaks-for. (#676)
 * Fix nickname cache updating when temp and home directories are on 
   different disks - use `shutil.move`. (#646)
 * Look for fallback `agg_nick_cache` in correct location (#662)
 * Use relative imports in `speaksfor_util` if possible. (#657)
 * Fix URL to URN lookups to better handle names that differ by a prefix. (#683)
 * Increase the sleep between busy SSL call retries from 15 to 20 seconds. (#697)
 * Rename `addAliases.sh` to `addAliases.command` for Mac install. (#647)
 * Add new section `omni_defaults` to the Omni config file. (#713)
  * This should set system defaults. Where these overlap in meaning with other 
    omni_config or commandline options, let those take precedence.
  * Allow these `omni_defaults` to be specified in the `agg_nick_cache`. These
    are read before those in the per-user omni config. If a default is set
    in the `agg_nick_cache`, that takes precedence over any value in 
    the user's `omni_config`: if a user should be able to over-ride the 
    default, use a different omni config setting (not in `omni_defaults`), or
    use a command line option.
  * Stitcher uses this for the SCS URL. 
 * Allow FOAM/AL2S AMs to submit sliver URNs that are the slice URN with an ID 
   appended. 
  * This works around known bug http://groups.geni.net/geni/ticket/1294. (#719)
 * Work around malformed ION sliver URNs: (#722)
  * Allow submitting URNs that use the slice authority as the sliver authority.
  * If the sliver urn reported by sliverstatus is malformed, replace it
    with the proper URN as the manifest returns, so sliver_info reporting
    works without even deleting the existing entry.
  * See http://groups.geni.net/geni/ticket/1292
 * Quiet down some debug logs when printing SSH keys and when talking to CHAPI. (#727)

New in v2.6:
 * New function `removeslicemember <slice> <username>`: 
   Remove the user with the given username from the named slice. (#515)
 * Add functions `listprojects` to list your projects, and `listprojectmembers`
   to list the members of a project and their role in the project and
   email address. (#495)
 * Include `addMemberToSliceAndSlivers` in Windows and Mac binaries (#585)
 * Include `remote-execute` in Mac binaries (#601)
 * Record FOAM reservations at the clearinghouse when using the
   `chapi` framework, by using fake sliver URNs. (#574)
 * `listslicemembers` honors the `-o` option to save results to a
   file, and `--tostdout` to instead go to STDOUT. (#489)
 * `listslivers` honors the `-o` option to save results to a file,
   and `--tostdout` to instead go to STDOUT. (#488)
 * `get_ch_version`, `listaggregates`, `listslices`, `listmyslices`,
   `listkeys`, `listmykeys`, `listimages`, and `nicknames`
   honor the `-o` option to save results to a file,
   and `--tostdout` to instead to to STDOUT. (#371)
 * `listkeys` return is a list of structs of ('`public_key`',
   '`private_key`'), where `private_key` is omitted for most
   frameworks and most cases where not available. (#600)
 * Added `print_sliver_expirations` to print the expirations of your
   slivers at requested aggregates. Also print sliver expirations from
   `sliverstatus`, `listresources` and `createsliver` calls. (#465, #564, #571)
  * Added new utilities in `handler_utils` to extract sliver
    expiration from the manifest and sliverstatus.
 * Clean up console log messages. (#623)
 * Retry on AM busy message two more times, sleeping 15 seconds instead
   of 10. (#624,#635)
 * Restore printing of non-standard options used in command summary. (#625)
 * Help specifies defaults for more options. (#626)
 * Mac install clears old `omni.py` and similar aliases (#556)
 * Fix `get_cert_keyid` to get the key id from the certificate (#573)
 * `renewslice` properly warns if your new expiration is not what you
   requested (#575)
 * rspec_util utility takes optional logger (#612)
 * Add support for talking to SA/MA that speak Federation API v2.
   To use the v2 APIs, add to your `omni_config`: `speakv2=true`. (#613)
 * Ensure manifest from `createsliver` is printed prettily.
   `getPrettyRSpec` takes a flag on whether it does pretty
   printing, default True. Do not do pretty printing on most
   Ads, and some manifests. Uses less memory. (#610)
 * Clean up error getting slice credential for unknown slice from
  `chapi` clearinghouses. (#538)
 * Clarify error messages in `delegateSliceCred`. (#619)
 * Harden update of `agg_nick_cache` to avoid replacing a good cache
   with one that was empty or incomplete on download. (#631)
 * Document creating an alias for `addMemberToSliceAndSlivers`
   in `INSTALL.txt`. (#632)
 * Avoid error doing `listprojects` when user has none. (#637)
 * More use of `os.path.join`, `os.sep`, `os.normpath` for Windows support (#639)
 * Ensure SFA libraries look for the temp dir in `TMP` as well as `TEMPDIR`, and try to create
   the directory if it doesn't exist. (#560)

New in v2.5.3:
 * Can now parse omni-configure sections of omni_config. (#436)

New in v2.5.2:
 * Update the OpenSSL version used in the Windows package to 1.0.1g,
   avoiding the heartbleed vulnerability. (#594)
 * Update various packages in Windows and Mac binaries to be
   consistent versions. (#595)

New in v2.5:

Highlights:
 * Released Windows and Mac OS X packages of the Omni experimenter
   utilities. (Developer gcf components are not included.)
 * Omni adds the ability to contact clearinghouses that speak the
   Uniform Federation API using framework type `chapi`
 * When using the new `chapi` framework allow a `--useSliceAggregates`
   option to specify that the aggregate action should be taken at all
   aggregates at which you have resources in this slice. (#507)
 * Added new options to allow installing SSH keys of all slice members
   when using the new `chapi` framework. (#491, #278)
 * Refactored the source code to make it easier to import Omni in
   other tools. Look in `src/gcf` for directories that were
   previously directly under `src`. (#388)
 * Added utilities for creating and processing 'Speaks For'
   credentials (which Omni can pass along to aggregates and to Uniform
   Federation API clearinghouses).
 * Timeout Omni calls to servers after 6 minutes (controlled by `--ssltimeout`)


Details:
 - Add a new framework type `chapi` for talking the Uniform Federation API 
   (http://groups.geni.net/geni/wiki/UniformClearinghouseAPI)
   to compliant clearinghouses (e.g. GENI Clearinghouse). (#345, #440)
  - See `omni_config.sample` for config options required
  - To upgrade a `pgch` config for `ch.geni.net` to a `chapi` config:
   - Change `type = pgch` to `type = chapi`
   - Change `ch = https://ch.geni.net...` to:
{{{
ch=https://ch.geni.net:8444/CH
ma=https://ch.geni.net/MA
sa=https://ch.geni.net/SA
}}}
  Included in this change:
  - When creating or renewing or deleting slivers, tell the Slice Authority.
    This allows the SA to know (non-authoritatively) where your slice
    has resources. (#439)
  - New function `listslivers <slice>`: lists the slivers reported to 
    the slice authority in the given slice, by aggregate (with
    the sliver expirations). Note that this information is not
    authoritative - contact the aggregates if you want to be sure
    not to miss any reservations.
  - New function `listslicemembers <slice>`: lists the members of
    the given slice, with their email and registered SSH public
    keys (if any) and role in the slice. (#421, #431, #278)
  - New function `addslicemember <slice> <username> [optional: role]`:
    Adds the user with the given username to the named slice,
    with the given role (or `MEMBER` by default). Note this
    does not change what SSH keys are installed on any existing
    slivers. (#422,#513)
 - Support `geni_extend_alap` with new `--alap` option, allowing you to
   request that slivers be renewed as long as possible, if your
   requested time is not permitted by local AM policy. (#415)
 - When using the new `chapi` framework allow a `--useSliceAggregates`
   option to specify that the aggregate action should be taken at all
   aggregates at which you have resources in this slice. (#507)
  - Any `-a` aggregates are extra. 
  - At other frameworks, this is ignored.
  - This option is ignored for commands like `createsliver`,
  `allocate`, `provision`, and `getversion`.
 - Added new option `--noExtraCHCalls` to disable calls to the
   clearinghouse to report slivers, query for slivers, or query
   a list of aggregates; explicit CH calls and retrieving credentials
   is not effected. (#514)
 - Added new options controlling what SSH keys are installed on
   compute resources. Default behavior is unchanged. These options
   control what users are created and SSH keys installed in new
   slivers from `createsliver` or `provision`, or when you update
   the installed users and keys using 
   `performoperationalaction <slice> geni_update_users`.
   If you supply the new option `--useSliceMembers` and your
   clearinghouse supports listing slice members (i.e. the new `chapi`
   type), then Omni will fetch the members of your slice from the
   clearinghouse and their public SSH keys, and send those to the
   aggregate to install on new compute resources. (#278, #441)
   By default, Omni will ''also'' read the users and SSH keys
   configured in your `omni_config` as usual, ''adding'' those users
   and keys to the set downloaded from the clearinghouse, if any.
   You can skip reading the `omni_config` keys by supplying the new option
   `--ignoreConfigUsers`.
   As before, `performoperationalaction` allows you to specify a file
   containing options with the `--optionsfile` option. If that file
   specifies the `geni_users` option, then that is the only set of
   users and keys that is supplied with `performoperationalaction`.
   However, if you do not supply the `geni_users` option from a file,
   Omni uses the same logic as for `createsliver`, optionally
   querying your clearinghouse for slice members, and by default 
   reading users and keys configured in your `omni_config`. (#491)
 - If set, `GENI_FRAMEWORK` environment variable is the default for
   the `--framework` option (#315)
 - If set, `GENI_USERCRED` and `GENI_SLICECRED` environment variables
   set the default path to your saved user and slice credentials (#434)
 - Handle `~` in `usercredfile` and `slicecredfile` (#455)
 - Support querying for other users' SSH keys where the CH supports it (#472)
 - Allow nicknames or URLs in the aggregates list in `omni_config` (#476)
 - Allow `PerformOperationalAction` on v2 AMs (#412)
 - Renew Slice returns actual new expiration (checks the SA, not just
   assuming success means you got what you asked for) (#428)
 - Add a 360 second timeout on AM and CH calls. Option `--ssltimeout`
   allows changing this. (#407)
  - If Omni hangs talking to a server you believe is up, try
    specifying `--ssltimeout 0` to disable the timeout. Some servers
    cannot handle the timeout request. (See ticket #506)
  - Note this timeout does not work on old versions of python2.6 due
    to a known python bug: http://bugs.python.org/issue5103
 - Speed up `listaggregates` in `pgch` framework (don't test AM API
   compliance) (#482)
 - Refactored the source code to make it easier to import Omni in
   other tools. Look in `src/gcf` for directories that were
   previously directly under `src`. (#388)
  - Your Omni based tool no longer needs to include any of the top
    level scripts that Omni/GCF includes, nor to provide the existing
    Omni `main`.
  - Most of the code in `omni.py` has now been moved to
    `gcf/oscript.py`
  - To update your script that uses omni as a library:
   - Change `import omni` to `import gcf.oscript as omni`
 - Avoid sending options to `getversion` if there are none, to support querying v1 AMs (#375)
 - Fix passing speaksfor and other options to `createsliver`, `renewsliver` (#377)
 - `renewslice` when given a slice credential replaces the saved 
   slice credential in place, rather than in a new filename. (#386)
 - Create any directories needed in the path to the agg_nick_cache (#383)
 - If using `--AggNickCacheName` and can't read/write to the specified
   file, omni should fall back to reading `agg_nick_cache.base` (#384)
 - Look up AM URN by URL in the defined aggregate nicknames (#404)
 - Support named timezones when renewing, etc (#503)
 - Eliminated a repetitive log message (#384, #385)
 - Fix bug in APIv3 calling status with slivers with different expiration times (#408)
 - Fit Omni result summaries in 80 character wide terminals (#409)
 - `ForceUseAggNickCache` avoids fetching new cache even if the agg
   nick cache is old (#391)
 - SFA slice and user records changed: keys and slices moved (#429)
 - Fix bug in handling errors in `listimages` and `deleteimage` (#437)
 - Support unicode urns (#448)
 - Return any error message from a CH on `getusercred` (#452)
 - Return error on SA error in `listslices` (#456)
 - Omni `cred_util.py` uses an omni logger (#460)
 - URN testing requires 4 `+` separated pieces (#483)
 - Log at debug when downloading the aggregate nickname cache fails (#485)
 - `chapi` framework looks up the MA and SA at the clearinghouse,
   though you can configure where they run. (#490)
 - Warn when acting at all AMs in the clearinghouse - slow (#461)
 - Speaks for option that Omni passes to aggregates has been renamed
   `geni_speaking_for` (#466)
 - Show the AM nickname instead of URL in output (#424, #504)
 - Properly parse the verbose config option and let the commandline
   `--verbosessl` over-ride it talking to clearinghouses. (#509)
 - Ensure `geni_version` on credential structs is a string.
   Fix bug in `get_cred_type` and correct for a chapi bug. (#516)
 - Notice invalid slice and member names earlier and suppress ugly
   tracebacks on most `chapi` framework errors. (#517)
 - Support AM API draft proposal O1 and allow '.' and '_' in sliver
   names, and do not complain or stop needlessly on illegal sliver
   names. (#518)
 - Catch parse errors when determining credential type (#521)
 - Using `chapi` framework, expired slice expirations are printed (#523)
 - When doing `renewsliver --alap`, if the real expiration is not in
   the `output` slot, call `sliverstatus` to get it. (#527)
 - Bail early from `createsliver` or `createimage` if the user
   didn't specify exactly one aggregate. (#395)
 - Update copyrights to 2014 (#463, #426)
 - Handle non string rspec when printing RSpec (#445)
 - Allow `--optionsfile` with `createimage`, `deleteimage`, and
   `listimages`. (#532)
 - Allow underscore in generated clean filenames (#533)
 - Handle `createslice` errors at the GENI Clearinghouse that might
   be due to having the wrong case, now the project and slice names 
   are case sensitive. (#535)
 - Trim trailing newlines before installing SSH keys (#537)
 - Explicitly import framework files in `oscript.py` to support
   Windows and Mac binaries. (#542)
 - Fix wording and licenses for Windows and Mac binaries (#541)


Older changes are listed in the CHANGES file.

== Handling Omni Output ==
Omni supports the `-o` option to have Omni save the output of Omni to
one or more files. See the [#RunningOmni documentation] for individual
commands for details.

Omni output is done through the python logging package, and
prints to STDERR by default. Logging levels, format, and output
destinations are configurable by either supplying a Pythong logging
configuration dictionary (to `oscript.call` or `oscript.initialize`),
or by supplying a custom Python logging
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

You may also completely disable Omni output, by specifying the option
`--noLoggingConfiguration`. Unless you use Omni as a library and your
tool configures Python logging, Omni will not write any output to
Python logging streams. For example, a tool might include
`--noLoggingConfiguration` when initializing the Omni library, and
then programmatically configure Python logging itself. Note that you
should generally configure some logging; many errors will cause Python
to stop Omni immediately if a log message is called for and no logging
configuration has been done. (You will see an error like:
'`No handlers could be found for logger "omni"`'.)

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

Omni is really a thin wrapper around `src/gcf/oscript.py`, which can
be imported as a library, enabling programmatic
access to Omni functions. To use Omni as a library, 
`import gcf.oscript as omni` and use the `omni.call` function.

Note that prior to v2.5, the import statement was `import omni` - be
sure you have updated your scripts when you upgrade.

{{{
  text, returnStruct = omni.call( ['listmyslices', username], options )  
}}}

The return from `omni.call` is a list of 2 items: a human readable string summarizing the result 
(possibly an error message), and the result object (may be `None` on error). The result 
object type varies by the underlying command called. See the docs in
the source code for individual methods.

Omni scripting allows a script to:
 * Have its own private options
 * Programmatically set other omni options (like inferring the "-a")
 * Accept omni options (like "-f") in your script to pass along to Omni
 * Parse the returns from Omni commands and use those values in subsequent Omni calls
 * Control or suppress the logging in Omni (see the above section for details)

For examples, see `src/stitcher.py` or `examples/expirationofmyslices.py` and `examples/myscript.py` in the gcf distribution.
Or [https://github.com/GENI-NSF/geni-tools/wiki/Omni-Scripting-Example-Showing-Expiration Omni Scripting Expiration] 
and
[https://github.com/GENI-NSF/geni-tools/wiki/Omni-Scripting-Example-With-Options Omni Scripting with Options] 
on the gcf wiki.

'''NOTE''': Omni uses multiple command line options, and creates its
own option names internally. Be sure not to pick the same option names. See `gcf/oscript.py` and the
`getParser()` function, around line 781 for all the option names.

== Extending Omni ==

Extending Omni to support additional frameworks with their own
clearinghouse APIs requires adding a new Framework extension
class. Adding other experiment management or utility functions can be
done using Omni scripting, or by adding functions to
`src/gcf/omnilib/amhandler.py`. 

== Omni workflow ==
For a fully worked simple example of using Omni, see 
http://groups.geni.net/geni/wiki/HowToUseOmni

 1. Get your user certificate and keys: Pick a Clearinghouse you want to
    use (that is the control framework you will use). Get a user
    certificate and key pair. 
 2. Configure Omni: Be sure the appropriate section of omni_config for
    your framework (sfa/gcf/pg/chapi/pgch) has appropriate settings for
    contacting that CF, and user credentials that are valid for that
    CF. Make sure the `[omni]` section refers to your CF as the default.
    If you ran `src/omni-configure.py` this should automatically be
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
 plus those for all members of your slice (when using select `chapi`
 style clearinghouses like the GENI Clearinghouse)
 should be available for use. See the options `--noSliceMembers` and
 `--ignoreConfigUsers` to change this behavior.

10. Delete slivers when you are done, freeing the resources for others:

 AM API v1:
`omni.py -V 1 deletesliver -a pg-utah1 MySlice`

 AM API v2:
`omni.py deletesliver -a pg-utah MySlice`

 AM API v3:
`omni.py -V 3 delete -a myV3AM MySlice`

11. Optional commands:
Occasionally you may run `listmyslices` to remind yourself of your
outstanding slices. Then you can choose to delete or renew them as
needed. If you don't recall when your slice expires, use
`print_slice_expiration` to remind yourself. If you use a `chapi`
framework (clearinghouse), you can additionally query the
clearinghouse to be reminded of where you may have reservations, using `listslivers`

 To List your slices : `omni.py listmyslices`

 To Print slice expiration : `omni.py print_slice_expiration MySlice`

 To list slivers where you made reservations using Omni: `omni.py listslivers MySlice`

== Running Omni ==

=== Supported options ===
Omni supports the following command-line options.

{{{
$ ~/gcf/src/omni.py -h                            
Usage: 
GENI Omni Command Line Aggregate Manager Tool Version 2.10
Copyright (c) 2011-2015 Raytheon BBN Technologies

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
 			 update <slicename> <rspec URL, filename, or nickname> [Some AM API V3 AMs only] 
 			 cancel <slicename> [Some AM API V3 AMs only] 
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
 			 listprojects [optional: username] [Alias for listmyprojects]
 			 listmyprojects [optional: username] 
 			 listmykeys [optional: username] [Alias for listkeys]
 			 listkeys [optional: username]
 			 getusercred 
 			 print_slice_expiration <slicename> 
 			 listslivers <slicename> 
 			 listprojectmembers <projectname> 
 			 listslicemembers <slicename> 
 			 addslicemember <slicename> <username> [optional: role] 
 			 removeslicemember <slicename> <username>  
 		Other functions: 
 			 nicknames 
 			 print_sliver_expirations <slicename> 

	 See README-omni.txt for details.
	 And see the Omni website at https://github.com/GENI-NSF/geni-tools/wiki

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
                        RSpec type and version to return, default: '['GENI',
                        '3']'
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
                        Requested start time for any allocated slivers
                        - NOW if not provided, could be for future reservations
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
                        logging config file]. Default: 'omni.log'
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
}}}

==== Notes on Options ====
Most options are documented more fully with the commands where they
are relevant. Some notes on select options are provided here.

Commonly used options:
Omni provides many options. However, most users will only use a very
few of them. 
 - `-a`: specify the aggregate at which to operate
 - `-r`: over-ride your default project setting
 - `--alap`: ask aggregates to renew your reservations as long as possible
 - `-o`: to save manifest RSpecs to a file
 - `--useSliceAggregates`: renew or delete at all aggregates where you
 used Omni to reserve resources
 - `--optionsfile`: Specify custom options for commands
 - `-u`: Specify a particular sliver to act on when using APIv3
 - `--debug`: Turn on debug logging when resolving an Omni problem
 - `--usercredfile`: Use a saved user credential (to save time
 calling the clearinghouse re-retrieving it later)
 - `--slicecredfile`: Use a saved slice credential (to save time
 calling the clearinghouse re-retrieving it later)

Basic Options:
 - The `-a` option may be an aggregate nickname or URL. Nicknames are
 defined in your `omni_config` plus some standard nicknames are
 defined globally and updated automatically by Omni. Run the command
 `nicknames` for a list.
 - `--available` is for use with `listresources` and `describe`
 - `-f` specifies the name of the framework in your `omni_config`,
 such as "my_genich". It is not required if you want to use the
 framework specified by `default_cf` in your `omni_config`.
 - If set, the `GENI_FRAMEWORK` environment variable will be the
 default for the `--framework` option, over-riding any default from
 your Omni config file.
 - `-r` / `--project` is used by framework types `pgch` and `chapi` which
 use a 'project' to group slices. It is only required if you want to
 use project other than your configured `default_project` from your `omni_config`.
 - `--alap` is supported only at select aggregates with `renew` and
 `renewsliver`
 - `-t` is typically not required. See `createsliver`
 - `-V` is typically not required as AM API v2 is the default. Specify
 `-V3` if you are calling an AM API V3 command
 - `--useSliceAggregates` is supported only when using framework type
 `chapi`, and then only with commands after your resources have been
 reserved, such as `renewsliver`, `sliverstatus`, and
 `deletesliver`. It relies on the clearinghouse's advisory list of aggregates where
 you have used Omni to reserve resources - reservations made using
 other tools may not be reflected.

AM API v3 Options:
 - `--best-effort`: In AM API v3 operations are on multiple
 slivers. This option, when supported by the aggregate, allows the AM
 to let the operation succeed on slivers where possible and only fail
 the operation on select slivers, rather than having to fail the whole
 request. For example, you might use this with `renew` to renew your
 reservation for 3 nodes, and allow the aggregate to fail to extend
 your reservation on a 4th node.
 - `--cred` allows you to specify an extra credential to any call that
 takes a list of credentials.
 - `--optionsfile` allows you to specify arbitrary options to be
 passed to aggregate calls. For example, use this to specify options
 for `performoperationalaction`.

File Output Options:
 - `-o` specifies that many commands write their output to a
 file. This includes RSpecs, sliver status, and slice and user
 credentials. Not all commands support this. `-p` and `--outputfile`
 work with `-o`.
 - `--usercredfile` and `--slicecredfile`: Most aggregate operations
 require a credential to prove your authorization. This credential
 comes from your framework / clearinghouse. This credential typically
 does not change frequently, so many users choose to save this
 credential to a file using the commands `omni -o getusercred` and
 `omni -o getslicecred`. Then by supplying the `--usercredfile` and
 `--slicecredfile` options, Omni can uses the saved credential and
 save the time required to re-fetch the credential from the
 clearinghouse.

Advanced / Developer Options:
 - `--ssltimeout`: Omni times out calls to servers, by default after
 360 seconds (6 minutes). Use this option to change that timeout. If
 commands to a server that you believe is up are failing, try
 specifying a timeout of `0` to disable the timeout.
 - `--noExtraCHCalls`: Omni makes multiple calls to the
 clearinghouse, particularly when using framework type `chapi`. These
 include reporting creation / renewal of slivers, querying for lists
 of aggregates, etc. These functions are necessary to support some
 Omni operations (such as provided by `--useSliceMembers` and
 `--useSliceAggregates`). However, you can disable these calls with
 this option.
 - `--noSliceMembers`: Disable `useSliceMembers`, which is True by default.
 By default, Omni tries to contact your clearinghouse to retrieve
 any slice members, to install their SSH keys on any reserved
 resources. This is only supported at some CHAPI-based
 clearinghouses, specifically the GENI Clearinghouse. Note also that
 `useslicemembers` in the `omni` section of your `omni_config` file
 can be set to `false` to disable `useSliceMembers`.
 - `--ignoreConfigUsers`: By default, `createsliver` and `provision`
 tell the aggregate to create accounts including for users listed in the users
 section of your `omni_config`, and install the listed SSH keys. With
 this option, Omni will not use those keys. See also `--noSliceMembers`.
 - `--noCacheFiles`: Completely disable reading, writing or
 downloading the aggregate nickname and !GetVersion cache files. This
 may be useful for tools using Omni as a library when multiple
 instances may run in parallel.
 - `--noLoggingConfiguration`: Omni will not configure the Python
 loggers. Without such a configuration, output only goes to STDOUT if
 you supply `--tostdout`, or to files if you specify `-o`.

=== Supported commands ===
Omni supports the following commands.

==== get_ch_version ====
Get the version information advertised by the configured framework /
clearinghouse, if supported. Return is a dictionary.

Format: `omni.py get_ch_version`

Output directing options:
 * `-o` Save result in a file
 * `-p` (used with `-o`) Prefix for resulting filename
 * `--outputfile`: If supplied, use this output file name
 * If not saving results to a file, they are logged.
 * If intead of `-o` you specify the `--tostdout` option, then instead of logging, print to STDOUT.
 * File names will indicate the CH name from the omni config 
  * e.g.: myprefix-portal-chversion.txt

==== listaggregates ====
List the URN and URL for all known aggregates.

Note that this lists all known aggregates, not just those used by a
particular slice.

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

Output directing options:
 * `-o` Save result in a file
 * `-p` (used with `-o`): Prefix for resulting filename
 * `--outputfile`: If supplied, use this output file name
 * If not saving results to a file, they are logged.
 * If intead of `-o` you specify the `--tostdout` option, then instead of logging, print to STDOUT.
 * File names will indicate the CH name from the omni config
  * e.g.: `myprefix-portal-aggregates.txt`

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

NOTE: If you specify the `--slicecredfile` option or define the
`GENI_SLICECRED` environment variable, and that
references a file that is not empty, then that file will be ignored,
and replaced if you specify `-o`.

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

Output directing options:
 * `-o` Save result in a file
 * `-p` (used with `-o`): Prefix for resulting filename
 * `--outputfile`: If supplied, use this output file name
 * If not saving results to a file, they are logged.
 * If intead of `-o` you specify the `--tostdout` option, then instead of logging, print to STDOUT.
 * File names will indicate the username whose slices are listed and the configuration
   file name of the framework
  * e.g.: `myprefix-jsmith-slices-portal.txt`

==== listprojects ====
List projects registered under the given username at the configured
slice authority.
Alias for `listmyprojects`.

==== listmyprojects ====
List projects registered under the given username at the configured
slice authority.
Not supported by all frameworks.

Format: `omni.py listmyprojects [optional: username]`

Sample Usage: `omni.py listmyprojects jdoe`

With no `username` supplied, it will look up projects registered to you
(the user whose certificate is supplied).

Printed output shows the names of your projects and your role in the
project. Supply `--debug` or `--devmode` to see a listing of your
expired projects as well.

Return object is a list of structs, containing
`PROJECT_URN`, `PROJECT_UID`, `EXPIRED`, and `PROJECT_ROLE`. `EXPIRED` is a boolean.

Output directing options:
 * `-o` Save result in a file
 * `-p` (used with `-o`): Prefix for resulting filename
 * `--outputfile`: If supplied, use this output file name
 * If not saving results to a file, they are logged.
 * If intead of `-o` you specify the `--tostdout` option, then instead of logging, print to STDOUT.
 * File names will indicate the username whose projects are listed and the configuration
   file name of the framework
  * e.g.: `myprefix-jsmith-projects-portal.txt`

==== listmykeys ====
Provides a list of SSH public keys registered at the configured
control framework for the specified user, or current user if not defined.
Not supported by all frameworks. Some frameworks only support querying
the current user.
At some frameworks will return the caller's private SSH key if known.
Really just an alias for `listkeys`.

Sample Usage: `omni.py listmykeys`

Output directing options:
 * `-o` Save result in a file
 * `-p` (used with `-o`): Prefix for resulting filename
 * `--outputfile`: If supplied, use this output file name
 * If not saving results to a file, they are logged.
 * If intead of `-o` you specify the `--tostdout` option, then instead of logging, print to STDOUT.
 * File names will indicate the username whose keys are listed
  * e.g.: `myprefix-jsmith-keys.txt`

==== listkeys ====
Provides a list of SSH public keys registered at the configured
control framework for the specified user, or current user if not defined.
Not supported by all frameworks. Some frameworks only support querying
the current user.
At some frameworks will return the caller's private SSH key if known.

Sample Usage: `omni.py listkeys` or `omni.py listkeys jsmith`

Output directing options:
 * `-o` Save result in a file
 * `-p` (used with `-o`): Prefix for resulting filename
 * `--outputfile`: If supplied, use this output file name
 * If not saving results to a file, they are logged.
 * If intead of `-o` you specify the `--tostdout` option, then instead of logging, print to STDOUT.
 * File names will indicate the username whose keys are listed and the configuration
   file name of the framework
  * e.g.: `myprefix-jsmith-keys-portal.txt`

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

==== listslivers ====
List all slivers of the given slice by aggregate, as recorded at the
clearinghouse. Note that this is non-authoritative information.

Notes:
 - This is a function of the clearinghouse, and relies on information
 reported by Omni and other tools.
 - This is non-authoritative information: your slice may have other
 reservations and some of these reservations may have since been
 renewed or deleted.
 - This command does not list all known aggregates, only those used by a
 particular slice. For a list of all known aggregates, see `listaggregates`.

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

Output directing options:
 - `-o` Save result in a file
 - `-p` (used with `-o`) Prefix for resulting filename
 - `--outputfile` If supplied, use this output file name: substitute slicename for any `%s`.
 - If not saving results to a file, they are logged.
 * If intead of `-o` you specify the `--tostdout` option, then instead of logging, print to STDOUT.
 - File names will indicate the slice name
  - e.g.: `myprefix-myslice-slivers.txt`

This is purely advisory information, that is voluntarily reported by
some tools and some aggregates to the clearinghouse. As such, it is
not authoritative. You may use it to look for reservations, but if you
require accurate information you must query the aggregates. Note in
particular that slivers reserved through Flack are currently not reported here.

This function is only supported at some `chapi` style clearinghouses,
including the GENI Clearinghouse.

==== listprojectmembers ====
List all the members of the given project.

Format: `omni.py listprojectmembers <projectname>`

Sample usage: `omni.py listprojectmembers myproject>`

Output prints out the project members and their project role, and
email.

Return is a list of the members of the project as registered at the
clearinghouse. For each such user, the return includes:
 - `PROJECT_MEMBER`: URN identifier of the user
 - `EMAIL` address of the user
 - `PROJECT_ROLE` of the user in the project.
 - `PROJECT_MEMBER_UID`: Internal UID identifier of the member, if
 returned by the clearingnouse and the user supplied `--debug`

Output directing options:
 * `-o` Save result in a file
 * `-p` (used with `-o`) Prefix for resulting filename
 * `--outputfile` If supplied, use this output file name: substitute projectname for any '`%s`'.
 * If not saving results to a file, they are logged.
 * If intead of `-o` you specify the `--tostdout` option, then instead of logging, print to STDOUT.
 * File names will indicate the project name
  * e.g.: `myprefix-myproject-projectmembers.txt`

Note that project membership is only supported at some `chapi` type
clearinghouses, including the GENI Clearinghouse. Project membership
determines who has rights to create a slice in the
named project. 

==== listslicemembers ====
List all the members of the given slice, including their registered
public SSH keys.

Format: `omni.py listslicemembers <slicename>`

Sample usage: `omni.py listslicemembers myslice>`

Output prints out the slice members and their SSH keys, URN, and
email.

Return is a list of the members of the slice as registered at the
clearinghouse. For each such user, the return includes:
 - `KEYS`: a list of all public SSH keys registered at the clearinghouse
 - `URN` identifier of the user
 - `EMAIL` address of the user
 - `ROLE` of the user in the slice.

Output directing options:
 * `-o` Save result in a file
 * `-p` (used with `-o`) Prefix for resulting filename
 * `--outputfile` If supplied, use this output file name: substitute slicename for any '`%s`'.
 * If not saving results to a file, they are logged.
 * If intead of `-o` you specify the `--tostdout` option, then instead of logging, print to STDOUT.
 * File names will indicate the slice name
  * e.g.: `myprefix-myslice-slicemembers.txt`

Note that slice membership is only supported at some `chapi` type
clearinghouses, including the GENI Clearinghouse. Slice membership
determines who has rights to get a slice credential and can act on the
named slice. Additionally, all members of a slice ''may'' have their
public SSH keys installed on reserved resources.

Note also that just because a slice member has SSH keys registered does not
mean that those SSH keys have been installed on all reserved compute resources.

==== addslicemember ====
Add the named user to the named slice. The user's role in the
slice will be `MEMBER` if not specified.

Format: `omni.py addslicemember <slice name> <user username> [role]`

Sample Usage: `omni.py addslicemember myslice jsmith`

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

Note also that adding a user to a slice does not automatically add
their public SSH keys to resources that have already been reserved.

==== removeslicemember ====
Remove the named user from the named slice. 

Format: `omni.py removeslicemember <slice name> <user username>`

Sample Usage: `omni.py removeslicemember myslice jsmith`

Return is a boolean indicating success or failure.

Note that slice membership is only supported at some `chapi` type
clearinghouses, including the GENI Clearinghouse. Slice membership
determines who has rights to get a slice credential and can act on the
named slice. Additionally, all members of a slice ''may'' have their
public SSH keys installed on reserved resources.

This function is typically a privileged operation at the
clearinghouse, limited to slice members with the role `LEAD` or
`ADMIN`.

Note also that removing a user from a slice does not automatically remove
their public SSH keys from resources that have already been reserved.

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
 - Each URL given in an `-a` argument or URL listed under that given
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
 - If `--useSliceAggregates`, each aggregate recorded at the clearinghouse as having resources for the given slice,
   '''and''' any aggregates specified with the `-a` option.
  - Only supported at some clearinghouses, and the list of aggregates is only advisory
 - Each URL given in an `-a` argument or URL listed under that given
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
 - If `--useSliceAggregates`, each aggregate recorded at the clearinghouse as having resources for the given slice,
   '''and''' any aggregates specified with the `-a` option.
  - Only supported at some clearinghouses, and the list of aggregates is only advisory
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
 - `--cancelled`: For use with `Update()`: Show only slivers that are
 `geni_provisioned`, not slivers that are only `geni_allocated` or `geni_updating`.

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
    `omni.py -a gpo-ig createsliver myslice resources.rspec`
 * Specify using GENI AM API v1 to reserve a sliver in `myslice`
 from a particular AM (specifying aggregate with a nickname), using
 the request rspec in `resources.rspec`:
{{{
     omni.py -a gpo-ig2 --api-version 1 createsliver \
              myslice resources.rspec
}}}
 * Use a saved (possibly delegated) slice credential: 
{{{
     omni.py --slicecredfile myslice-credfile.xml \
             -a gpo-ig createsliver myslice resources.rspec
}}}
 * Save manifest RSpec to a file with a particular prefix: 
{{{
     omni.py -a gpo-ig -o -p myPrefix \
             createsliver myslice resources.rspec
}}}
 * Reserve resources, installing all slice members' keys on the new
 nodes, but not any users listed in `omni_config`.
{{{
     omni.py -a gpo-ig --ignoreConfigUsers \
             createsliver myslices resources.rspec
}}}
 * Reserve resources, installing only SSH keys for users listed in `omni_config`.
{{{
     omni.py -a gpo-ig --noSliceMembers \
             createsliver myslices resources.rspec
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

Users and SSH Keys:
By default, Omni passes to the aggregate a list of users and SSH keys
that combines those listed as members of your slice at the
Clearinghouse, plus those listed in your `omni_config` file `users`
section. Thus any member of your slice _plus_ anyone using the
specific SSH keys you specify will be able to log in via SSH into reserved
compute resources.
2 command-line options control this:
 - `--ignoreConfiguUsers': When supplied, ignore the omni_config
 `users` and do not install any keys listed there.
 - `--noSliceMembers`: When supplied, over-ride the default 
 and do NOT contact the clearinghouse to retrieve slice members.
The old (pre v2.7) option `--useSliceMembers` is deprecated, and has
no effect - the behavior it enables is the default.
You can also control this behavior using 2 settings in your
`omni_config` file in the `omni` section. 
 * Add the setting `useslicemembers=True` or `useslicemembers=False` to toggle retrieving
   slice members' SSH keys. 
 * Additionally, setting `ignoreconfigusers=True` has the same effect as
   including `--ignoreConfigUsers` as a commandline option.

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
 - Note that `--useSliceAggregates` is not honored, as the desired
   aggregate usually has no resources in this slice yet.

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
 - Note that `--useSliceAggregates` is not honored, as the desired
   aggregate usually has no resources in this slice yet.

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

Users and SSH Keys:
By default, Omni passes to the aggregate a list of users and SSH keys
that combines those listed as members of your slice at the
Clearinghouse, plus those listed in your `omni_config` file `users`
section. Thus any member of your slice _plus_ anyone using the
specific SSH keys you specify will be able to log in via SSH into reserved
compute resources.
2 command-line options control this:
 - `--ignoreConfiguUsers': When supplied, ignore the omni_config
 `users` and do not install any keys listed there.
 - `--noSliceMembers`: When supplied, over-ride the default 
 and do NOT contact the clearinghouse to retrieve slice members.
The old (pre v2.7) option `--useSliceMembers` is deprecated, and has
no effect - the behavior it enables is the default.
You can also control this behavior using 2 settings in your
`omni_config` file in the `omni` section. 
 * Add the setting `useslicemembers=True` or `useslicemembers=False` to toggle retrieving
   slice members' SSH keys. 
 * Additionally, setting `ignoreconfigusers=True` has the same effect as
   including `--ignoreConfigUsers` as a commandline option.

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
aggregate's advertisement RSpec. Commonly available actions are listed below.

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

Common `poa` Actions:
Some actions are well known and supported at many aggregates and
resource types. Always check the Ad RSpec for an aggregate to verify
what is supported.
 - `geni_start`: Make the resources ready for use (like booting
 machines). No options needed
 - `geni_restart`: For example, reboot a machine. No options required.
 - `geni_stop`: Stop a resource (e.g. shut it down). No options
 needed.
 - `geni_update_users`: Refresh the set of user accounts and installed
 SSH keys on the resource. Takes the option `geni_users`. This action
 creates any users specified that do not already exist, and sets the
 SSH keys for all users per the list of keys specified - including
 removing keys not explicitly listed. The `geni_users` option can be
 supplied using the `--optionsfile` argument. If not supplied that
 way, then users are read from the omni_config or clearinghouse slice
 members, as documented under `createsliver`.

Note:
Clients must `renew` or use slivers before the expiration time
(given in the return struct), or the aggregate will automatically delete them.

Options:
 - `--sliver-urn` / `-u` option: each specifies a sliver URN on which to perform the given action. If specified,
   only the listed slivers will be acted on. Otherwise, all slivers in
   the slice will be acted on.
   Note though that actions are state and resource type specific, so the action may not apply everywhere.
 - `--optionsfile`: Path to a JSON format file defining options to be passed to
 the aggregate. The specific required options depend on the action
 specified.

Slice name could be a full URN, but is usually just the slice name
portion.
Note that PLC Web UI lists slices as <site name>_<slice name>
(e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

Aggregates queried:
 - If `--useSliceAggregates`, each aggregate recorded at the clearinghouse as having resources for the given slice,
   '''and''' any aggregates specified with the `-a` option.
  - Only supported at some clearinghouses, and the list of aggregates is only advisory
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
 - If `--useSliceAggregates`, each aggregate recorded at the clearinghouse as having resources for the given slice,
   '''and''' any aggregates specified with the `-a` option.
  - Only supported at some clearinghouses, and the list of aggregates is only advisory
 - Each URL given in an `-a` argument or URL listed under that given
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
 - If `--useSliceAggregates`, each aggregate recorded at the clearinghouse as having resources for the given slice,
   '''and''' any aggregates specified with the `-a` option.
  - Only supported at some clearinghouses, and the list of aggregates is only advisory
 - Each URL given in an `-a` argument or URL listed under that given
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
 - If `--useSliceAggregates`, each aggregate recorded at the clearinghouse as having resources for the given slice,
   '''and''' any aggregates specified with the `-a` option.
  - Only supported at some clearinghouses, and the list of aggregates is only advisory
 - Each URL given in an `-a` argument or URL listed under that given
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
 - If `--useSliceAggregates`, each aggregate recorded at the clearinghouse as having resources for the given slice,
   '''and''' any aggregates specified with the `-a` option.
  - Only supported at some clearinghouses, and the list of aggregates is only advisory
 - Each URL given in an `-a` argument or URL listed under that given
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
 - If `--useSliceAggregates`, each aggregate recorded at the clearinghouse as having resources for the given slice,
   '''and''' any aggregates specified with the `-a` option.
  - Only supported at some clearinghouses, and the list of aggregates is only advisory
 - Each URL given in an `-a` argument or URL listed under that given
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
 - If `--useSliceAggregates`, each aggregate recorded at the clearinghouse as having resources for the given slice,
   '''and''' any aggregates specified with the `-a` option.
  - Only supported at some clearinghouses, and the list of aggregates is only advisory
 - Single URL given in `-a` argument or URL listed under that given
 nickname in omni_config, if provided, ELSE
 - List of URLs given in omni_config aggregates option, if provided, ELSE
 - List of URNs and URLs provided by the selected clearinghouse

==== update ====
Call GENI AM API Update <slice name> <rspec file name>

For use with AM API v3+ only, and only at some AMs. 
Technically adopted for AM API v4, but may be implemented by v3 AMs. 
See http://groups.geni.net/geni/wiki/GAPI_AM_API_DRAFT/Adopted#ChangeSetC:Update

Update resources as described in a request RSpec argument in a slice with 
the named URN. Update the named slivers if specified, or all slivers in the slice at the aggregate.
On success, new resources in the RSpec will be allocated in new slivers, existing resources in the RSpec will
be updated, and slivers requested but missing in the RSpec will be deleted.

Return a string summarizing results, and a dictionary by AM URL of the return value from the AM.

Format: `omni.py -V3 [-a AM_url_or_nickname] [-u sliver_urn] update <slicename> <rspec file or nickname>`

Sample usage:
 - Basic update of resources at 1 AM into myslice
   `omni.py -V3 -a http://myaggregate/url update myslice my-request-rspec.xml`
 - Update resources in 2 AMs, requesting a specific sliver end time, save results into specificly named files that include an AM name calculated from the AM URL,
   using the slice credential saved in the given file
   `omni.py -V3 -a http://myaggregate/url -a http://myother/aggregate --end-time 20120909 -o --outputfile myslice-manifest-%a.json --slicecredfile mysaved-myslice-slicecred.xml update myslice my-update-rspec.xml`

After update, slivers that were `geni_allocated` remain `geni_allocated` (unless they were left
out of the RSpec, indicating they should be deleted, which is then immediate). Slivers that were 
`geni_provisioned` or `geni_updating` will be `geni_updating`.
Clients must `Renew` or `Provision` any new (`geni_updating`) slivers before the expiration time
(given in the return struct), or the aggregate will automatically revert the changes 
(delete new slivers or revert changed slivers to their original state). 
Slivers that were `geni_provisioned` that you do not include in the RSpec will be deleted, 
but only after calling `Provision`.
Slivers that were `geni_allocated` or `geni_updating` are immediately changed.

Slice name could be a full URN, but is usually just the slice name portion.
Note that PLC Web UI lists slices as <site name>_<slice name>
(e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

Slice credential is usually retrieved from the Slice Authority. But
with the `--slicecredfile` option it is read from that file, if it exists.

Aggregates queried:
 - If `--useSliceAggregates`, each aggregate recorded at the clearinghouse as having resources for the given slice,
   '''and''' any aggregates specified with the `-a` option.
  - Only supported at some clearinghouses, and the list of aggregates is only advisory
 - Each URL given in an `-a` argument or URL listed under that given
 nickname in omni_config, if provided, ELSE
 - List of URLs given in omni_config `aggregates` option, if provided, ELSE
 - List of URNs and URLs provided by the selected clearinghouse
Note that if multiple aggregates are supplied, the same RSpec will be submitted to each.
Aggregates should ignore parts of the Rspec requesting specific non-local resources (bound requests), but each 
aggregate should attempt to satisfy all unbound requests. 

Options:
 - `--sliver-urn` or `-u` option: each specifies a sliver URN to update. If specified,
   only the listed slivers will be updated. Otherwise, all slivers in the slice will be updated.
 - `--best-effort`: If supplied, slivers that can be updated, will be; some slivers
   may not be updated, in which case check the geni_error return for that sliver.
   If not supplied, then if any slivers cannot be updated, the whole call fails
   and sliver allocation states do not change.
   Note that some aggregates may require updating all slivers in the same state at the same 
   time, per the `geni_single_allocation` !GetVersion return.
 - `--end-time <time>`: Request that new slivers expire at the given time.
   The aggregates may provision the resources, but not be able to grant the requested
   expiration time.
   Note that per the AM API, expiration times will be timezone aware.
   Unqualified times are assumed to be in UTC.
   Note that the expiration time cannot be past your slice expiration
   time (see `renewslice`).

Output directing options:
 - `-o`: Save result in per-aggregate files
 - `-p <prefix>` (used with `-o`): Prefix for resulting files
 - `--outputfile <path>`: If supplied, use this output file name: substitute the AM for any `%a`, and slicename for any `%s`
 - If not saving results to a file, they are logged.
 - If `--tostdout` option, then instead of logging, print to STDOUT.
 - When using `-o` and not `--outputfile`, file names will indicate the
   slice name, file format, and which aggregate is represented.
   e.g.: `myprefix-myslice-update-localhost-8001.json`

Other options:
 - `--api-version #` or `-V #` or `-V#`: AM API Version # (default: 2)
 - `-l <path>` to specify a logging config file
 - `--logoutput <filename>` to specify a logging output filename

Options for development and testing:
 - `--devmode`: Continue on error if possible

==== cancel ====
Call GENI AM API Cancel <slice name>

For use with AM API v3+ only, and only at some AMs. 
Technically adopted for AM API v4, but may be implemented by v3 AMs. 
See http://groups.geni.net/geni/wiki/GAPI_AM_API_DRAFT/Adopted#ChangeSetC:Update

Cancel pending changes in a slice with 
the named URN. Cancel the changes to the named slivers if specified, or all slivers in the slice at the aggregate.
On success, any slivers that were being allocated will be deleted
(geni_unallocated), and any slivers that were being updated
('geni_updating'), will revert to their previous state
('geni_provisioned' with all state and properties as before).

Return a string summarizing results, and a dictionary by AM URL of the return value from the AM.

Format: `omni.py -V3 [-a AM_url_or_nickname] [-u sliver_urn] cancel <slicename>`

Sample usage:
 - Basic cancel of changes at 1 AM into myslice
   `omni.py -V3 -a http://myaggregate/url cancel myslice`
 - Cancel changes in 2 AMs, save results into specificly named files that include an AM name calculated from the AM URL,
   using the slice credential saved in the given file
   `omni.py -V3 -a http://myaggregate/url -a http://myother/aggregate -o --outputfile myslice-manifest-%a.json --slicecredfile mysaved-myslice-slicecred.xml cancel myslice`

Slice name could be a full URN, but is usually just the slice name portion.
Note that PLC Web UI lists slices as <site name>_<slice name>
(e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

Slice credential is usually retrieved from the Slice Authority. But
with the `--slicecredfile` option it is read from that file, if it exists.

Aggregates queried:
 - If `--useSliceAggregates`, each aggregate recorded at the clearinghouse as having resources for the given slice,
   '''and''' any aggregates specified with the `-a` option.
  - Only supported at some clearinghouses, and the list of aggregates is only advisory
 - Each URL given in an `-a` argument or URL listed under that given
 nickname in omni_config, if provided, ELSE
 - List of URLs given in omni_config `aggregates` option, if provided, ELSE
 - List of URNs and URLs provided by the selected clearinghouse

Options:
 - `--sliver-urn` or `-u` option: each specifies a sliver URN to revert. If specified,
   only the changes to the listed slivers will be canceled. Otherwise, all changes in the slice will be canceled.
 - `--best-effort`: If supplied, slivers that can be canceled, will be; some slivers
   may not be canceled, in which case check the geni_error return for that sliver.
   If not supplied, then if any slivers cannot be canceled, the whole call fails
   and sliver allocation states do not change.
   Note that some aggregates may require canceling all changes in the same state at the same 
   time, per the `geni_single_allocation` !GetVersion return.

Output directing options:
 - `-o`: Save result in per-aggregate files
 - `-p <prefix>` (used with `-o`): Prefix for resulting files
 - `--outputfile <path>`: If supplied, use this output file name: substitute the AM for any `%a`, and slicename for any `%s`
 - If not saving results to a file, they are logged.
 - If `--tostdout` option, then instead of logging, print to STDOUT.
 - When using `-o` and not `--outputfile`, file names will indicate the
   slice name, file format, and which aggregate is represented.
   e.g.: `myprefix-myslice-cancel-localhost-8001.json`

Other options:
 - `--api-version #` or `-V #` or `-V#`: AM API Version # (default: 2)
 - `-l <path>` to specify a logging config file
 - `--logoutput <filename>` to specify a logging output filename

Options for development and testing:
 - `--devmode`: Continue on error if possible

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
Alias for `createimage`

==== deleteimage ====
Call the ProtoGENI / InstaGENI !DeleteImage method, to delete a disk
snapshot (image) previously created at a given aggregate.

This command is not supported at older ProtoGENI AMs or at non
ProtoGENI AMs.

See http://www.protogeni.net/trac/protogeni/wiki/ImageHowTo

Format: `omni.py deleteimage IMAGEURN [CREATORURN]`

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

Output directing options:
 - `-o`: Save result in per-Aggregate files
 - `-`p (used with `-o`): Prefix for resulting files
 - `--outputfile`: If supplied, use this output file name: substitute the AM for any `%a`
 - If not saving results to a file, they are logged.
 - If `--tostdout` option is supplied (and not `-o`), then instead of logging, print to STDOUT.
 - File names will indicate the user and which aggregate is represented.
  - e.g.: `myprefix-imageowner-listimages-localhost-8001.json`

==== nicknames ====
Print / return the known Aggregate and RSpec nicknames, as defined in
the Omni config file(s). 

If you specify nicknames in `-a` arguments, it will look up that
nickname and print any matching aggregate URN/URL.

Output directing options:
 * `-o`: Save result in a file
 * `-p` (used with `-o`): Prefix for resulting filename
 * `--outputfile`: If supplied, use this output file name
 * If not saving results to a file, they are logged.
 * If intead of `-o` you specify the `--tostdout` option, then instead of logging, print to STDOUT.
 * File name will be `nicknames.txt` (plus any requested prefix)

Sample Output:
{{{
....
  Result Summary: Omni knows the following Aggregate Nicknames:

        Nickname | URL                                                                    | URN
=============================================================================================================
          gpo-ig | https://boss.instageni.gpolab.bbn.com:12369/protogeni/xmlrpc/am/2.0    | urn:publicid:IDN+instageni.gpolab.bbn.com+authority+cm
....
Omni knows the following RSpec Nicknames:

  Nickname | Location
====================================================================================
 hellogeni | http://www.gpolab.bbn.com/experiment-support/HelloGENI/hellogeni.rspec

(Default RSpec location: http://www.gpolab.bbn.com/experiment-support )

(Default RSpec extension: rspec )
}}}

==== print_sliver_expirations ====
Print the expiration of any slivers in the given slice.
Return is a string, and a struct by AM URL of the list of sliver expirations.

Format: 
`omni.py [-a amURNOrNick] [--useSliceAggregates] [-u sliverurn] print_sliver_expirations mySlice`

Sample output:
{{{
  Result Summary: Slice urn:publicid:IDN+ch.geni.net:ahscaletest+slice+ahtest expires on 2014-05-21 18:37:12 UTC
Resources in slice ahtest at AM utahddc-ig expire at 2014-05-21T00:00:00 UTC.
 First resources expire at 2014-05-21 00:00:00 (UTC) at AM utahddc-ig.
}}}

Slice name could be a full URN, but is usually just the slice name portion.
Note that PLC Web UI lists slices as <site name>_<slice name>
(e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

Slice credential is usually retrieved from the Slice Authority. But
with the `--slicecredfile` option it is read from that file, if it exists.

 - `--sliver-urn` / `-u` option: each specifies a sliver URN to get status on. If specified, 
   only the listed slivers will be queried. Otherwise, all slivers in the slice will be queried.

Aggregates queried:
 - If `--useSliceAggregates`, each aggregate recorded at the clearinghouse as having resources for the given slice,
   '''and''' any aggregates specified with the `-a` option.
  - Only supported at some clearinghouses, and the list of aggregates is only advisory
 - Each URL given in an `-a` argument or URL listed under that given
   nickname in omni_config, if provided, ELSE
 - List of URLs given in omni_config aggregates option, if provided, ELSE
 - List of URNs and URLs provided by the selected clearinghouse

 - `-V#` API Version #
 - `--devmode`: Continue on error if possible
 - `-l` to specify a logging config file
 - `--logoutput <filename>` to specify a logging output filename
