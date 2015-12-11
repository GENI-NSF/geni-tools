This file contains some notes on the design and implementation of Omni. Many details are in the issues or the source code. This document may serve as a pointer, or explanation for the code you are reading.

**NOTE**: This is a work in progress.
This document has many holes and needs polishing.

# Directory Contents
## Source code & scripts:
```
acceptance_tests/AM_API: scripts for developers to test an aggregate's
			 compliance with the GENI AM API
src/: Put this directory on your PYTHONPATH
 gcf-*.py: Run GCF reference aggregate, clearinghouse, etc.
 omni.py
 stitcher.py
 omni-configure.py
 delegateSliceCred.py
 omni_log_conf_sample.conf
 gcf/
    geni/: Utilities particularly for the GCF tree
      am/: AM API samples
        am2.py: APIv2 reference aggregate
	am3.py: APIv3 reference aggregate
	am_method_context.py: authorization wrapper around method
	  calls
	aggregate.py, fakevm.py, resource.py: Model key pieces in a
  	  simple way
      auth/: Authorization module (see README-authorization.txt)
      util/: Utilities
        cert_util: Define create_cert
	cred_util: Methods to create and validate credentials, doing
	  authorization
	secure_xmlrpc_client.py: A client that IDs with a cert over
	  SSL using PyOpenSSL
	speaksfor_util.py: Utilities to generate and validate a speaks
	  for (ABAC) credential. Has a main for commandline
	  operations.
	urn_util: Utilities for manipulating URNs, transforming
	  to/from public ID, validating
      SecureXMLRPCServer.py: A python XML-RPC server that requires a
        client certificate. Used by the reference AM and CH
      SecureThreadedXMLRPCServer.py: This threaded variant has
        issues. See Github.
      ch.py: Sample Clearinghouse. Not Uniform Federation API
        compliant.
      am1.py: AM APIv1 reference AM
      ca.py: Test CA for generating user and aggregate certs.

    omnilib/: Omni
      frameworks/: Code for talking to different kinds of
        clearinghouses. Used by chhandler.py
	framework_base.py: Base class
        framework_chapi.py: Talking to Uniform Federation API (GENI Clearinghouse)
	framework_gcf.py: Talk to reference GCF CH
	framework_pg.py: Talk natively to ProtoGENI
	framework_sfa.py: Talk to SFA Slice Authority
      stitch/: Support code for Stitcher
        objects.py: Define the Aggregate class which has the key allocate method,
	           plus classes representing parts of the RSpec. Much of stitcher is here.
	ManifestRspecCombiner.py: Combine multiple manifests in a single rspec
	RSpecParser.py: For parsing the request from the SCS
	VLANRange.py: Utilities for parsing & printing ranges of VLANs (a set)
	launcher.py: A loop over aggregates whose dependencies are satisfied, to call them in
	            turn to be allocated
	scs.py: Utilities to call functions at the SCS
	workflow.py: Parse the workflow from the SCS and calculated dependencies among aggregates
	            and path hops
	GENIObject.py and gmoc.py: Some aborted work to use GMOC code for modeling
      util/:
        credparsing.py: Utilities to parse credentials and distinguish
          between XML credentials and JSON wrapped credentials (wrapped
          as a struct giving type, version, and value)
	dates.py: Define naiveUTC for ensuring all dates internally
          are naive (no timezone) and are in UTC.
	dossl.py: Provide the _do_ssl wrapper for SSL calls to handle common errors,
          retrying if reasonable. Retry on an error code meaning the
          server is busy up to 4 times. Allow retrying when user mistypes
          their SSL passphrase. Detect and prettify some common SSL
          error codes.
      json_encoding: Ensure datetimes are properly encoded in JSON
      omnierror.py: Define OmniError and AMAPIError
      handler_utils.py: Handle aggregate nicknames and URN/URL
        lookups, RSpec nickname lookups, getting the list of aggregates
        to operate on, loading/saving/retreiving credentials,
        constructing filenames, formatting results for saving and
        printing/saving results, and getting sliver/reservation expiration
        from manifest RSpecs and sliverstatus
      xmlrpc/client.py: PyOpenSSL XMLRPC client that authenticates
        with a certificate. See geni/util/secure_xmlrpc_client.py for
        duplicate code.
      handler.py: Depending on the call, Omni calls are dispatched to
        a handler. This is the base class.
      amhandler.py: Handle all AM API calls (like createsliver)
      chhandler.py: Handle calls to a clearinghouse (like createslice)
      stitchhandler.py: Handle stitching calls, calling launcher and
           the objects.py Aggregate classes as needed.
    sfa/: Code imported from SFA. Defines Certificates and Credentials
      and how to validate them.
    gcf_version.py: Define the current Omni version
    oscript.py: Main for Omni. See `call()` and `main()`.
    stitcher_logging.conf: Python Logging config file for Stitcher
    stitcher_logging_deft.py: Alternate stitcher configuration if the
      .conf file is not found (can happen on Windows)
examples/: Some examples and useful scripts
  readyToLogin.py
  addMemberToSliceAndSlivers.py
  renewSliceAndSlivers.py
```
## Various READMEs, some in GitHub markdown format, some in Trac wiki format:
```
doc/
CHANGES
CONTRIBUTING.md
CONTRIBUTORS.md
INSTALL*.*
LICENSE.txt
README-*.txt
README.md
README.txt
```

## Sample configuration files:
```
gcf_config.sample
omni_config.sample
```

## Files for building RPMs. See README-packaging.md:
```
Makefile.am
autogen.sh
configure.ac
geni-tools.spec
debian/
```

## Test and config files for older modules:
```
stitcherTestFiles/
gib-config-files/
gib-rspec-examples/
```

## Files for building binaries:
```
mac_install/
windows_install/
doc/CreatingBinaries.md
```
## Mapping of Aggregate nicknames to URN and URL. 
Latest version is posted to the Omni wiki for automatic download by Omni, but version
controlled here.
`agg_nick_cache.base`

# Omni
Omni is the command line tool for reserving resources from GENI
Aggregate Manager API compliant resource providers. It also supports
managing projects and slices from Uniform Federation API compliant
clearinghouses.
It is used for talking to aggregates by the GENI Portal and GENI
Desktop. Key functions are used by geni-lib. It underlies the Sticher
tool for creating stitched topologies, which is used by CloudLab to
reserve topologies that span multiple CloudLab sites.
For a user's guide to Omni, see README-omni.txt

Multiple sample and useful scripts that use Omni are in the
`examples/` directory. Otherwise all main code is under `src/`.

## Use as Library
geni-tools code is structured to make it easier to import it in other
tools. Set PYTHONPATH to the `src` directory. To ease this, files use
relative imports. See for example `speaksfor_util.py` which uses a
try/except to use relative imports by preference, but allow for
running this file's main directly with absolute imports. For similar
reasons, Omni has all its main code in `src/gcf/oscript.py`
rather than directly in omni.py. Stitcher should be refactored
similarly, but has not been.
See `README-omni`.

## Overall Code Structure
Omni calls are handled by a special "handler"; handler.py dispatches
to chhandler or amhandler (and Stitcher uses a parallel stitchhandler
for future smoother integration). The handler allows invoking any
method in the handler classes (excluding private methods, indicated by
a name that starts with `_`). Handlers do two kinds of operations:
Call a clearinghouse using a 'framework' (to create a slice or get a credential for
example), and calls to an aggregate.

## Frameworks and contacting clearinghouses
Omni supports multiple
clearinghouse APIs, whose differences are abstracted away with a
'framework' whose API is defined in framework_base.py. The framework
handles getting the user and slice credentials. Additionally, in AM
APIv3 credentials are a struct that indicates the type and version of
the actual credential. The framework handles wrapping and unwrapping
the actual credential as needed. The specific framework to use is inferred dynamically based on the
`omni_config` file. frameworks are named `framework_<framework'type'>.py`, using the `type` from the selected framework section of
the `omni_config`. `framework_chapi` supports the Uniform Federation
API v1 and v2 (http://groups.geni.net/geni/wiki/CommonFederationAPIv2). Currently it hard codes some assumptions that should be
done dynamically using information from `GetVersion` (like whether the
CH supports projects).
Note that each 'framework' represents a different clearinghouse API. These differences are hidden by Omni behind `chhandler`. It would be nice if there were a way to directly call the individual framework APIs.

## `chhandler`
`chhandler` supports calls to the clearinghouse: get a user or slice
credential, create or renew a slice, list aggregates, list a user's
slices or projects, etc. The supported calls are necessarily a subset of the functionality that any given framework / clearinghouse API supports. Each call parses the commandline arguments
(not options) itself. Calls to the proper framework to do the
clearinghouse call are typically wrapped in `_do_ssl` to support
automatic retry. 

## `amhandler`
`amhandler` supports calls to aggregates, including all AM APIv2, v2,
v3, and adopted v4 calls (http://groups.geni.net/geni/wiki/GAPI_AM_API). In addition, a number of aggregate specific
calls are supported. Each call parses the arguments itself (e.g. to
get out the slice name), and calls to the aggregate itself are wrapped
in `_do_ssl`. The amhandler tries to auto-correct the AM API version in
use, taking into account the requested AM API version and what version
of the AM API is supported at the aggregate(s) being contacted. It may
adjust the API version, or adjust the URL at which it contacts the
aggregate, to use a different AM API version. To do this, it uses the
information from the GetVersion call, which it caches. In order to
determine which aggregates to call, it uses a combination of the `-a`
argument(s), the aggregates listed as used by the given slice at the
clearinghouse (in the sliver_info structure), and aggregates specified
in the omni_config file. To allow this to work, Omni must have a
record of the mapping of aggregate URNs and nicknames to URLs and vice
versa. Some of this is available at the clearinghouse, but Omni
primarily uses the Aggregate nickname cache, which it updates daily
from a central server.

Handlers share a few common elements. Omni errors extend the OmniError
class. Handlers log the error and re-raise the error, including the AM
API error return triple if available. All public methods return a list
of 2 elements: a pretty string to describe the result, and an object
that is the return value. The type of the return value depends on the
specific method call. Within Omni, all timestamps are assumed to be in
UTC but do not have an explicit timezone (naive
timestamps). Timestamps are converted to assure this remains
true.

## `handler_utils`
Many common functions are handled by methods in
handler_utils. handler_utils contains methods for loading and saving
credentials, for saving command output to a file or printing it as
specified by the options, for getting the list of aggregates, and for
looking up aggregates or nicknames in the aggregate nickname
cache.

## Aggregate nicknames
Omni keeps a cache of aggregate nicknames, by default in
`~/.gcf/agg_nick_cache`. This INI format file maps nicknames to
aggregate URL and URN. Note that the same URN may have multiple URLs
(different AM API versions typically), and the same URL could have
multiple nicknames. The cache is maintained in git and available at https://raw.githubusercontent.com/GENI-NSF/geni-tools/master/agg_nick_cache.base. Omni downloads the cache once daily (configurable). Nicknames in the cache
are ordered by convention with AM API agnostic nicknames before those
specific to a version, and then by API version number. Nicknames are
typically `<site>-<type>[version#]`, e.g. "moxi-of1".

For some purposes,
Omni takes a nickname and looks up the aggregate URN and URL. For
other purposes, Omni starts with a URL or URN and looks up the
nickname for prettier log messages. When doing so, Omni uses some
heuristics for choosing among nicknames that share the same URN or
URL. For example, Omni ignores `http` vs `https` in the URL, and Omni prefers
a shorter nickname and one that lists the AM type after the site. Note
that these heuristics are brittle, and hard code the possible strings
to name an AM type. The only risk however is picking an uglier
nickname. Note also that the `agg_nick_cache` must be kept
up-to-date. In particular, when omni users use the
`--useSliceAggregates` option, it uses the sliver_info records at the
clearinghouse to get AM URNs that are registered as having resources
on this slice. Then Omni must look up a URL for that URN, and uses the
agg_nick_cache to do so. Therefore, any AM that is not listed in the
agg_nick_cache will not be included in Omni operations that use `--useSliceAggregates`.

GENI operations must keep the `agg_nick_cache` up to date with the proper AM URLs and list the proper aggregates, to ensure sliver info reporting, availability of reasonable nicknames, and reasonable Omni printouts. Generally, any aggregate that conforms to the AM API and provides reservable resources could be listed in the cache, but GENI policy may require additional testing (reliability for example).
Note that there are options for controlling where the cache is saved, and options to force not attempting to download a new cache at all.
Also note that much of the information in the `agg_nick_cache` is duplicated in the GENI Clearinghouse' service registry. It might be nice if this data could be retrieved from that registry or some similar database, reducing the number of sources of such information.

## `_listaggregates`
handler_utils also provides the `_listaggregates` function for getting
a list of aggregates to operate on. First, it handles the
`--useSliceAggregates` option. HOWEVER, this only makes sense if there
is a slice to operate on and which will have existing sliver_info
records. Therefore, in amhandler, the `_handle` function calls
`_extractSliceArg(args)`, which extracts the slice name argument from
the given commandline arguments. However, this function carefully
excludes method calls that do not provides a slice name, or for which
there would not yet be sliver info records or the records would not be
useful; when calling createsliver, you do not want to reserve
resources at the AMs where there is already a reservation, as that
will fail.

Given the slice name, `_listaggregates` gets the AM URNs from the
sliver_info records at the clearinghouse, if possible (only at CHAPI
compatible clearinghouses). Omni then retrieves the AM URL and
nickname if possible, avoiding duplicate entries.

If the options do not require using the sliver_info records, then Omni
considers the `-a` options, again looking up the url and urn for the
aggregate nickname (or urn or url). Failing that, Omni uses the
`aggregates` section of the omni_config file. If that fails, Omni asks
the clearinghouse for _all_ aggregates. Except for the explicit CH
call to list all aggregates, this is usually the wrong thing.

## Credential Manipulation
handler_utils also provides functions for manipulating
credentials. Omni can save a slice or user credential, or a speaks for
credential, and then load it for use in AM or CH calls. `_load_cred`
handles reading JSON (APIv3) or XML (APIv2 or v1)
credentials. `_get_slice_cred` tries to read any saved credential in
the file specified by `--slicecredfile`, otherwise it asks the
clearinghouse for the slice credential, wrapping or unwrapping the
credential in JSON as needed. `_save_cred` writes the proper JSON or
XML file.

## Saving results
handler_utils also provides helpers for printing or saving call
results, to STDOUT, the logger, a JSON file, or an XML file, as
appropriate, based on the data type and the options. The main method for this is `_printResults`. That function
tries hard to add a "header" to the file in a way that makes the file still valid xml or json.  It is often used in
conjunction with `_writeRSpec`, which gets the RSpec in proper format and gets a header string, constructs
a filename for saving the rspec using `_construct_output_filename`, and then calls `_printResults`.
`_construct_output_filename` uses several helpers to pull a server name out of AM URN or URL,
extract out the meaningful bits, remove bad characters, and then create a filename
based on that name.

## `amhandler` helpers and details
amhandler includes a large number of helper functions to support its
operations and simplify the individual methods. 

### `BadClientException`
This helper exception is used to signal that Omni called an AM that spoke the wrong version of the AM API, or
is otherwise not callable (see `self._api_call`). Then the calling methods (e.g. `Describe`) can note
the failure in the return message, bail if that's the only AM, or continue to the next aggregate.

### GetVersion Cache
In order to call each AM with the proper API version (or call the right URL for an AM), Omni uses the return from GetVersion.
Rather than call GetVersion on nearly every call, Omni caches the result of GetVersion for use between Omni invocations.
There are multiple options for controlling how long the cache is good for, where it is, or whether to use it at all. `amhandler`
has many helper functions for retrieving `GetVersion` values, using the cache if available, or otherwise actually
calling GetVersion, and caching the result (including any error return). Note that Omni calls GetVersion twice when the user invokes GetVersion explicitly.

### `self.clients`
A list of XMLRPC client objects, one per aggregate that the call should be run at. The entries are corrected to point to the right URL by `self._correctAPIVersion`. The variable is filled in by `self._getclients()`. That method first calls `handler_utils._listaggregates`
to get the right list of aggregates. Then an XMLRPC client is created for each. The client object is marked up with a
nickname (using `handler_utils._lookupAggNick`) and a pretty string for printing out the contact.
`self._getclients()` is called by each method.

### `self._extractSliceArg`
Get the slice name for use by `handler_utils._listaggregates` in finding the aggregates on which to operate.
Called by the `_handle` function, get the the slice name out of the commandline arguments.
This function knows which methods take a slice name (or URN), but also which are called on a slice that could conceivably
have `sliver_info` records at the clearinghouse, and such could give a list of aggregates at the clearinghouse to operate on.
The fact that this knows about the individual method calls is ugly / fragile.

### `self._correctAPIVersion`
Omni users will often invoke Omni with a generic nickname (`gpo-ig`) or URL, disregarding which version of the AM API they are
invoking. They may also easily forget to supply the `-V3` argument when that was intended. This function
attempts to correct for these mistakes. This function first ensures that all clients are reachable, dropping
those that are not. Then it figures out which AM API version most AMs talk. It then auto corrects which version of the AM API
it uses. Later, Omni will change individual clients to use a different URL to match the desired AM API version as needed (see `_checkValidClient` and how it is called from `_api_call`).

### `self._api_call`
This function wraps calls to the XMLRPC AM clients. First it ensures that the client exists and speaks the correct AM API version (raising a `BadClientException` if not). Then it makes the call (wrapped in `_do_ssl`).

### `self._checkValidClient`
Check the `GetVersion` cache for this client, and ensure this client speaks the proper AM API version. Bail if there is a problem with the client. Try changing to a client at a different URL to match the desired AM API version if necessary.

### `opts.devmode`
It's worth noting here the `devmode` option. This option allows developers to over-ride many of the argument/option error checks
that Omni provides, forcing Omni to do something that looks wrong; perhaps to test the response of an aggregate to that
input. For example, use `devmode` to foce Omni to speak AM API v3 to a v2 client.

### `self._args_to_slicecred`
This function parses the commandline arguments and then loads/retrieves the proper slice credential. You specify the number of expected arguments for error checking. It gets a slice URN (using the framework translation function), uses `handler_utils._get_slice_cred` to load or retrieve the slice credential, unwraps the credential from JSON if needed, prints the slice expiration, and then
returns the slice name, urn, credential, etc.

### `self._build_options`
Build the AM API `options` argument for this method call and the specified commandline Omni options.
This includes `geni_end_time`, `geni_start_time`, `geni_best_effort`, `geni_speaking_For`, `geni_extend_alap`, and any arbitrary options specified in the `--optionsfile` JSON file of options. For an example of those options, see http://groups.geni.net/geni/wiki/HowTo/ShareALan or http://groups.geni.net/geni/wiki/GAPI_AM_API_DRAFT/Adopted#ChangeSetQ:Supportchangingusersandkeysonexistingcomputeslivers
This method knows what options are relevant in what AM API methods. As such, it is brittle. `devmode` can be used to force passing options to additional method calls.

### AM API v2 vs v3 functions
Omni tries to stop you from calling an AM API v2 method at an AM API v3 AM. `devmode` allows you to do so anyhow. Note however the interaction with `_correctAPIVersion` which could cause unexpected results; in practice, this does this right thing.

### `self._build_urns`
For use with AM API v3+, this function builds the urns argument to AM API calls. It includes the slice urn or the specified sliver URNs as needed.

### `self._retrieve_value`
AM API methods return a triple (`code`, `output`, `value`), and Omni helps extract the real result from this, or a reasonable error message. This method considers also the SSL call return message, if any. This function also attempts to extract any PG based AMs log URL (a URL where full logs of teh call at the AM are available). Omni provides an option to raise an error (an `AMAPIError` with the the return triple) if there is an AM API error return code when using AM API v2: `--raise-error-on-v2-amapi-error`. Otherwise, this method returns an error string or the return value.

### `sliver_info` records
The Uniform Federation API specifies a 'sliver info' mechanism, by which tools or aggregates can voluntarily provide sliver records to the clearinghouse. These records record which aggregates have resources reserved for what slices, and when they expire. This information is useful for inferring what aggregates to talk to when acting on a slice. Omni uses this information when you use the `--useSliceAggregates` option and the `framework_chapi` clearinghouse interface.

When using the `framework_chapi`, Omni tries to report this information to the clearinghouse: new slivers reserved (`createsliver` or `provision`), slivers renewed (`renewsliver` or `renew`) or slivers deleted (`deletesliver`, `delete`). Additionally, Omni ensures the records are correct when you call `sliverstatus` or `status`. Since this is also used by the GENI Portal and GENI Desktop, most GENI reservations are properly reported to the GENI clearinghouse. (Reservations made using other clearinghouses will of course not be recorded.) Note that allocated slivers are not reported. Also note that Omni attempts to continue if there is an error with reporting, which could result in mis-matches.

Omni tries to get the proper sliver expiration times. This logic may have errors (where sliver expiration is not reported correctly, or is missing as in some returns from `createsliver`). In such cases, Omni may correct this in a later call, or the expiration may be that of the slice, and therefore the resource may expire sooner than listed; generally this is not harmful.

Additionally, Omni needs a good sliver URN to report. At some AMs, this has been problematic in the past. Omni includes heuristics to determine or generate a sliver URN, and to try to match such generated URNs with later reported URNs. This too could cause problems.
Users may disable sliver info reporting using `--noExtraCHCalls`.

As noted elsewhere, to use these sliver info records, Omni must determine the URN of the aggregate. Omni tries to look up the aggregate URN if it is not available (using the aggregate nickname cache or the clearinghouse or the GetVersion cache), or to guess it from the sliver URN. None of these mechanisms is foolproof, and as such, some resource reservations may not be reported. In general, all aggregates should be listed in the `agg_nick_cache` to ensure the sliver info mechanism works.

### amhandler sliver result parsing functions
Starting with AM API v3, many functions return a struct or list of structs for teh slivers in the reservation at this AM. `amhandler` provides multiple helper methods for parsing and interpreting these. `_getSliverStatuses` summarizes the allocation/operational status of the slivers. `_didSliversFail` indicates what slivers if any had per sliver failures (as in when the user supplied `--bestEffort`). `_findMissingSlivers` reports on slivers which were in the list of slivers requested to act on but for which there is no result. `_getSliverExpirations` helps summarize when your slivers expire. `_getSliverAllocStates` gets a mapping of sliver to allocation state, optionally filtered to only slivers whose state is not as expected.

## `do_ssl`
As noted above, `dossl.py` provides the `_do_ssl` wrapper around SSL calls. This allows catching common SSL errors and retrying; for example, mis-typing your SSL key passphrase, or a server reporting an AM API error code indicating it is busy. The number of times to retry and time to pause between attempts is hard coded (4 times, 20 seconds). Other common SSL errors are interpreted to provide a more user friendly error message (such as your user certificate is expired or not trusted). This function also allows suppressing certain error codes - allowing this to look like an empty return with an error message, instead of logging a noisy error.

The tuning of time to wait between busy retries and number of times to retry has been tuned to support the current slowest AMs (like ProtoGENI Utah). But this is brittle and could need future tuning.

## Logging
Omni uses python logging. Omni provides multiple options to tune and configure logging, attempting to be friendly to the use of Omni as a library in another application. Some user level documentation is available in `README-omni`.

Some times, configuring logging as desired requires manually modifying the python handlers in the calling code. For example, stitcher does things like this:
```python
        ot = self.opts.output
        if not self.opts.tostdout:
            self.opts.output = True

        if not self.opts.debug:
            # Suppress all but WARN on console here
            lvl = self.logger.getEffectiveLevel()
            handlers = self.logger.handlers
            if len(handlers) == 0:
                handlers = logging.getLogger().handlers
            for handler in handlers:
                if isinstance(handler, logging.StreamHandler):
                    lvl = handler.level
                    handler.setLevel(logging.WARN)
                    break
# Write the RSpec to a file, not to the log stream....
        retVal, filename = handler_utils._writeRSpec(self.opts, self.logger, reqString, None, '%s-expanded-request'%self.slicename, '', None)
# Then undo the edits to the handler
        if not self.opts.debug:
            handlers = self.logger.handlers
            if len(handlers) == 0:
                handlers = logging.getLogger().handlers
            for handler in handlers:
                if isinstance(handler, logging.StreamHandler):
                    handler.setLevel(lvl)
                    break
        self.opts.output = ot
```

Similar things suppress all but warnings on the console:
```python
            if not self.opts.debug:
                # Suppress all but WARN on console here
                lvl = self.logger.getEffectiveLevel()
                handlers = self.logger.handlers
                if len(handlers) == 0:
                    handlers = logging.getLogger().handlers
                for handler in handlers:
                    if isinstance(handler, logging.StreamHandler):
                        lvl = handler.level
                        handler.setLevel(logging.WARN)
                        break

# Then do something that would log at INFO that you don't want to see

            if not self.opts.debug:
                handlers = self.logger.handlers
                if len(handlers) == 0:
                    handlers = logging.getLogger().handlers
                for handler in handlers:
                    if isinstance(handler, logging.StreamHandler):
                        handler.setLevel(lvl)
                        break
            self.opts.output = ot
```

A sample omni logging configuration file is at `src/omni_log_conf_sample.conf`.
Another good example is how Stitcher configures logging. `src/stitcher.py` finds a python logging config file (in its case, `src/gcf/stitcher_logging.conf`). Then stitcher has omni configure logging: `omni.configure_logging(options)`.

## Saved user and slice creds
Many CH operations require a user credential. Most AM API methods require a user credential or usually a slice credential. These credentials change very infrequently. So Omni can save these, letting you do many things faster.
A future enhancement would automatically cache these.

When you use the `-o` option with `getusercred` or `getslicecred`, you can save the credential. Then through use of `--slicecredfile` or `--usercredfile` you can have Omni load the credential from the saved file. `framework_base.init_user_cred` tries to read a saved user credential from a file. `handler_utils._maybe_save_slicecred` is used to save the slice credential to a file. `handler_utils._get_slice_cred` will call `_load_cred` to load the slice credential from a file if possible. Stitcher uses the saved slice credential so that the numerous individual Omni calls required for a single stich all use the same saved slice credential.
`chhandler` has to be a little careful, particularly in calling `renewslice` and `getslicecred` when there is a saved slice credential.

## Making SSL connections
There are multiple ways of making SSL connections from python. geni-tools uses some M2Crypto and some PyOpenSSL.
`secure_xmlrpc_client.py` and `xmlrpc/client.py` use PyOpenSSL. There was an attempt to use M2Crypto, particularly to support a callback for entering the SSL passphrase only once, but this had trouble. Unused code remains for future potential use.

Note that managing the SSL version and the ciphers used in creating the SSL connection has been an issue in the past. There are notes on github issues. In particular, remember that Omni should work on Windows and Mac as well as Linux, and there are a wide variety of servers it must talk to.
Also note that Omni wants to authenticate with a client certificate over SSL, which is unusual among python libraries. In addition, it must pass a full chain of certificates in general (an MA and a user cert). And do this with an XMLRPC connection. Ensuring the cert chain is passed, and that SSL timeouts are honored, has been an issue in the past.
Additionally, Omni attempts to work with Python 2.6 and 2.7, including more recent 2.7.9. These various versions introduce differences that Omni must work around.

Currently, by default Omni specified that it wants TLSv1. By default, Python would do SSLv23 (which secretly also allows SSLv3). This enures TLS is supported and that servers that have disabled both SSLV2 and v3 (as generally recommended) will work.
Additionally, Omni by default uses a cipher list that tries to avoid most weak ciphers (though python2.6 ignores our requested cipher list).
See `xmlrpc/client.make_client`.

On the server side, the relevant file is `gcf.geni.SecureXMLRPCServer`. This is an XMLRPCServer where on each connection we get the peer (client) certificate, and we wrap the socket in an SSL connection. We specify that we accept SSLv23. Ideally we'd specify the ciphers too, but that doesn't (easily) work, and specifying SSL versions of TLSv1 risks locking out some clients.

## AM method return struct
All public methods return a list
of 2 elements: a pretty string to describe the result, and an object
that is the return value. The type of the return value depends on the
specific method call.
This common return simplifies tools that use Omni.
The pretty string should be reasonably short for printing.
Note that it might be nice to add the raw return tuple that the aggregate returns (code, value, output), perhaps as a 3rd item in the triple that the methods return. But this would cause multiple changes, so be careful.


## Output control
Omni provides multiple options for controlling its output. The primary output is the python logger, which logs to STDERR (console) by default. With the `-o` option (and related options), primary output (like rspecs and credentials) can be sent to a file. With the `--tostdout` option that output goes to STDOUT instead. Supply your own python logging config file to further control Omni output (use `--logconfig`) or tell Omni not to configure logging at all (because the caller tool has already done so - use `--noLoggingConfiguration`).
For some purposes, it might be nice if Omni sent everything to STDOUT instead of STDERR (e.g. to pipe the output to `grep`). The output control functions are in `handler_utils`; see above.

## To Do items
The open issues in Github cover many of the outstanding tasks and wishlist items for Omni. To highlight a few:
- #854: SFA code has been updated. There is a branch on a fork to update to the latest SFA, to make future integration easier
- #814: There remain some references to GPO lab servers, which will go away or change names before too long
- #427: Provide a way to get the full return triple from AM calls
- #829: There is code duplication between the omni `client.py` and the GCF `secure_xmlrrpc_client.py`
- #820: What should the dependency of GCF on Omni or Omni on GCF be? Could they be independent? Currently GCF `am3.py` depends on `omnilib` (see related #819)
- #773: It would help tools using Omni if exceptions were more specific
- #592: Add library functions that are raw AM API calls, for use by tools
- #525: The code for looking up nicknames / URNs is ugly. Refactor it
- #524: The code for handling `--useSliceAggregates` includes some ugly hacks. Refactor it.
- #766: `rspec_util` uses XML parsers but does very little with that, and the parsers don't handle everything an XML document could have smoothly
- #752: Does Omni properly return a non 0 exit code when there is an AM API error?
- #656: Omni could infer the AMs to reserve resources at from your (bound) RSpec, similar to how stitcher does
- #655: Many stitcher utilities could be part of Omni
- #652: Calling `poa geni_update_keys` when using a PG clearinghouse causes existing SSH keys on nodes to be removed
- #520: When searching for a URL or nickname, consider the desired AM API version
- #494: The CHAPI clearinghouse framework should use the `get_version` return to decide which functions to call, which services are supported
- #457: Find a way to ask for the SSL passphrase only once
- #430: Omni does not handle an HTTP redirect

Overall, it has been a couple years since Omni was refactored. It is time. When doing so, consider ways to split up Omni to better support the multiple audiences:
- Omni for newbie experimenters
- Omni for expert experimenters
- Omni for developers
- Omni as a library for other tools

Other possible improvements are noted inline above.

FIXME: show create sliver pseudo code to walk much of the sub systems?

# Stitcher
Stitcher is a tool that uses Omni to coordinate reservations among multiple aggregates. For usage information, see README-stitching.txt.
Stitcher uses the Omni option parser and logging configuration, and then does multiple instances of `omni.call()` to invoke numerous AM API calls.

## Stitching Overview
GENI stitching breaks up the reservation of coordinated slices into individual reservations at multiple aggregates. Each aggregate simply reserves what is requested of it. It is the responsibility of the tool to coordinate those reservations as necessary. For example, the tool may reserve a link at Aggregate A, and Aggregate A will provide that link. It is up to the tool to reserve the other end of that link at Aggregate B. If the tool does not do so, nothing useful will happen on that link, but Aggregate A does not care. However, a good tool would look at the specific link allocated by Aggregate A, and ensure it reserves the matching link at Aggregate B; for example, using the same VLAN tag number.

In general, there could be multiple reasons why the reservation at a second aggregate depends on what is reserved at the first aggregate. The Stitcher tool handles the case of using the same VLAN tag at multiple aggregates.
GENI provides multiple mechanisms for creating links between resources at multiple aggregates: GRE and EGRE links, specialized aggregates like VTS, and VLAN circuits. Stitcher focuses primarily on VLAN circuits, and that is what we refer to when we speak of GENI Stitched links.

GENI provides experimenters a private custom topology by using VLAN tags across the GENI network. Experimenters can then modify anything within their layer 2 network. Stitching works because GENI operators pre-negotiate a range of VLANs across campus, regionals, and backbone providers to be dedicated to GENI and the ports connecting GENI resources. These pools of VLANs are then managed by GENI aggregates. GENI stitching then involves the coordinated reservation of those VLAN tags across a circuit of aggregates/resources.
One variation on GENI stitching, is the creation of Openflow controlled stitcher circuits. In this variation, the aggregates give the slice a VLAN on the switch, but also connect a designated Openflow controller to that VLAN circuit, allowing the experimenter to control traffic on their VLAN using their Openflow controller. Experimenters can do this using the normal stitching mechanism, but specifying an Openflow controller within the main body `<link>`. More properly, experimenters would use version 2 of the stitching RSpec extension which allows specifying the Openflow controller as part of the stitching request.

## Stitcher workflow
Fundamentally, stitcher does a series of reservations at aggregates using Omni. Stitcher figures out the dependency among aggregates, and then makes a sequence of reservations. Stitcher reserves a VLAN at the first aggregate, reads out the VLAN tag that was assigned, and then requests the same VLAN tag at the next aggregate in the circuit. In the end, the slice has reservations at multiple aggregates with consistent VLAN tags. Stitcher then collects and integrates the manifest RSpecs from the multiple aggregates, and reports the result to the experimenter as a single manifest RSpec.

This process is made more complex by error handling. Any given reservation may fail, due perhaps to a problem in the request, unavailability of compute resources, or unavailability of the requested VLAN tag. Stitcher works hard to determine whether the request is fatally flawed, or whether some part of the reservation can be productively deleted and retried automatically. A number of other factors complicate stitching:
* Some aggregates can translate VLAN tags (using 1 VLAN tag on the way in, and another on the way out), and some cannot
* Some aggregates prefer to select the VLAN tag (producers), and some want to be told what VLAN tag to use (consumers)
* Stitched links request a given bandwidth (typically just a best effort bookkeeping reservation) that must be satisfied
* A given slice may use multiple stitched links, and may use multiple inter aggregate link types
* No GENI aggregates currently support multi point circuits, so slices must be made of multiple circuits

Stitcher is written so that it handles any Omni calls that it can, and redirects to Omni for anything it cannot handle.

## Stitching Links
Some links for learning more about stitching in general and GENI stitching:
* GENI Stitching and links to SCS code and the stitching extension: https://wiki.maxgigapop.net/twiki/bin/view/GENI/NetworkStitchingOverview
* SCS code on Github: https://github.com/xi-yang/MXTCE-GENI-SCS
* Some sample stitching RSpecs: http://groups.geni.net/geni/browser/trunk/stitch-examples
* A stitching tutorial: http://groups.geni.net/geni/wiki/GENIExperimenter/Tutorials/StitchingTutorial
* Stitching RSpec extension v2 (mostly unused): https://www.geni.net/resources/rspec/ext/stitch/2/stitch-schema.xsd
* Tested stitching sites: http://groups.geni.net/geni/wiki/GeniNetworkStitchingSites
* Slides describing stitching to experimenters: http://groups.geni.net/geni/attachment/wiki/GEC20Agenda/InterAggExpts/GEC20-InterAggregate.pdf
* Most recent developer stitching slides: http://groups.geni.net/geni/attachment/wiki/GEC16Agenda/DevelopersGrabBag/geni-gec16-stitching.pdf
* Old out of date page on GENI stitching: http://groups.geni.net/geni/wiki/GeniNetworkStitching
* PG stitching: http://www.protogeni.net/ProtoGeni/wiki/Stitching
* Orca stitching: https://geni-orca.renci.org/trac/wiki/Stitching

## Stitcher todo items
Stitcher has never been refactored, and the code needs to be cleaned up.
Arguably stitcher could be refactored to support considering and using arbitrary dependencies among aggregates.
Stitcher hard codes a lot of knowledge of how aggregates work, making it brittle. Some pieces of this could be at least factored into config / data files.
* Error codes and messages from aggregates and what they mean
* Default sliver expiration times
* Whether an aggregate produces a good manifest immediately, or only after the sliver becomes ready (like EG, DCN)
* Whether an aggregate's manifest is cumulated (an edited request), or is new / limited (like EG).
* Whether an aggregate supports changing the suggested VLAN tag to `any`

Stitching schema v2 is not used by aggregates. While stitcher claims to support this, there are likely lurking issues.

The open issues cover most things that could/should be done. Some highlights:
* Allow specifying a VLAN to use on a link (#872)
* Fix up handling of stitching to a fixed endpoint (#840)
* Support resuming a partial reservation (#810)
* Check available bandwidth first (#809)
* Allow 2 hops with the same interface on a single hop (like a loop) (#784)
* Put more AM specifices in `omni_defaults` (#762)
* Reconcile the use of `any` and the SCS selected VLANs (#650)
* Refactor `stitcher.call` into `stitchhandler` for better library use (#649)
* Move some stitcher utilities and options into base Omni (#627, #655)
* Support full VLAN negotiation (#567)
* Clean up overlapping use of stitcher `amlist` and `--useSliceAggregates` (#585)
* Check status of Orca reservations (#318)
* Multithread where reasonable (#260)

## SCS
The Stitching Computation Service (SCS) is documented in README-stitching, and is an optional service to find paths across GENI. It was written by Tom Lehman and Xi Yang of MAX and U Maryland. It is operated by Internet2. See links above for design documents and source code. For issues with the running instance, contact the GMOC / Internet2. Interactions with the SCS are mediated by `scs.py`. That file contains a `main`, allowing direct testing of the SCS (be sure the set your `PYTHONPATH=<geni-tools-dir>/src`). Functions at the SCS include `ComputePath` (the main function stitcher uses) and `ListAggregates` (list the aggregate known to the SCS). `GetVersion` is a simple check if the server is up and what code version it is. Comments in the `main` list URLs for different SCS instances, and running `scs.py -h` will show usage of its `main()`.

The aggregates loaded in a given instance of the SCS will vary. It should include aggregates known to work with GENI stitching. As such, the list will be constrained by GENI Operations testing for the official Internet2 SCS instance; testing SCS instances may include additional aggregates.
The SCS operates by parsing aggregate advertisements and constructing topologies from that information. As such, it must be kept up to date with the latest ad RSpec, and errors in those RSpecs will cause problems.

Note also that the SCS, by design, does not consider current VLAN tag availability - only advertised ranges. Therefore it will report a possible VLAN range and suggested tag that may not currently work. Stitcher considers availability (where known) to filter or change that suggested information itself.

At runtime, stitcher calls the SCS when it determines that 1 or more links require using GENI stitching. The SCS then adds a stitching extension to the request RSpec, specifying the hops (switch and port) in sequence that define the circuit, along with suggested VLAN tags to request. In addition, the SCS calculates which aggregate should be asked to pick the VLAN tag, and which aggregates should be told the VLAN tag selected by the previous aggregate. This workflow information is used to drive stitcher.
When stitcher requests a path from SCS for which there is no configuration, or there is no overlap in VLAN tags configured, then the SCS returns a path not found error.

The SCS is optional, in that a tool could use some other mechanism for finding a path and possible VLAN tags, but the SCS is the mechanism stitcher uses.

Several stitcher options control the use of the SCS.
* `--excludehop` allows the experimenter to request that a given interface (switch-port), by URN, not be used on any path/circuit. By appending `=<VLANTAGRANGE>` you can exclude a specific VLAN tag or range of VLAN tags. Use this to avoid some hop or VLAN that you know has problems, or to effectively force the use of some other tag.
* `--includehop`: Include this hop on EVERY path
* `--includehoponpath`: Include the specified hop on the specified path (link `client_id`)
* `--scsURL`: URL of the SCS. Used to specify a non default (say, testing) SCS
* `--noSCS`: Do not call the SCS. Use this if supplying a request that already has a stitching extension and the SCS would fail the request
* `--useSCSSugg`: Use the SCS suggested VLAN tag, and do not change the request to `any` at supported aggregates

## AL2S
The GENI network uses the AL2S (OESS) backbone from Internet2 to connect most GENI aggregates. This network supports dynamic circuits, uses Openflow under the covers, and gives GENI dedicated VLANs for each experimenter request. Contact Internet2 / GMOC with any operational problems with AL2S. Internet2 operates a GENI aggregate manager for reserving circuits across AL2S.
The AL2S aggregate is based on FOAM (https://bitbucket.org/barnstorm/foam). The base code is roughly that at: 
https://bitbucket.org/ahelsing/foam-0.12-with-speaks-for
It was written by Luke Fowler of Indiana University / Internet2.

## Workflow
1. Configure logging and set up options
* Find `stitcher_logging.conf`, which is more complicated due to windows binaries
* Create needed directories and set up logging output
* Rotate `stitcher.log` so we keep up to 5 old log files
* Configure logging using Omni
* Suppress anything but WARN messages on the console while we load the omni config file, by editing the level on the console log handler. Note this is sensitive to the setup of the logging configuration file.
* Merge use of the omni `-p` option the the stitcher `--fileDir` option
* Call stitchhandler
2. Set up Stitch Handler
* Initilize the Omni framework. Suppress all but WARN console messages when doing so
* Set the `timeoutTime` to track when Stitcher should give up
3. Parse arguments
* Select functions by name that stitcher can handler that aren't allocations, like `describe` and `delete`
 * Construct the aggregates to act on for those methods
  * Use the stitcher saved AM list first
  * If that gives none, use `--useSliceAggregates`
  * If there is just one aggregate, pass this to Omni
 * If this is `describe`, do `rebuildManifest` (see below)
 * Otherse, `doDelete()` (see below)
* If this is not `allocate` or `createsliver`, then pass this to Omni (adding aggregates from the amlist file)
4. Parse the RSpec (see `RSpecParser`)
5. Check the kind of request this is
* `mustCallSCS`
 * Make sure all links explicitly list the aggregates implied, by searching through the nodes for the interfaces on the link
 * If the link has more than 1 aggregate, is the `vlan` type, and doesn't use a shared VLAN, it is stitching. Note that this heuristic is brittle.
 * Check by aggregate URN if the aggregates on this link are all ExoGENI. If so, we could just use ExoGENI stitching (no SCS needed). But if the users said `--noEGStitching` in some form or `--noExoSM`, then we choose to use the SCS anyhow
* `hasGRELink`
 * If there is a link of type `gre` or `egre` with 2 aggregates / 2 interfaces, then it is a GRE link
* Check for any unbound nodes and ensure the list of aggregates to process includes all aggregates hosting nodes
* If this is not a fully bound multi aggregate request, pass the call to Omni
6. Set up other singletons
* Get the slice credential: We get it once for re-use later
* Create the SCS interface
7. Call the main stitching loop (see below) to reserve the resources - see `mainStitchingLoop`
8. Create and save the combined manifest: `getAndSaveCombinedManifest`
9. Get pretty messages about when resources expire: `getExpirationMessage`
10. Save the list of aggregates used in this slice in a file for later use by stitcher
11. Clean up temporary files
12. Construct a return message and return

FIXME FIXME.....

## Sections to add
* stitchhandler, launcher, objects.py
* Pseudo code control flow
* Logging
Stitcher uses a complicated Pythong logging config file to force all log messages (including debug) to a file (`stitcher.log`) while the console has a much more limited set of log messages. Doing this requires to messy handler manipulation and clever use of Omni logging configuration. Stitcher also does its own per-invocation log file rotation. Stitcher has an option to push all output files into a named directory (supporting multiple invocations on the same server). FIXME.
* Calling Omni
Stitcher makes multiple omni method calls. It does so by constructing strings or lists of strings for Omni to parse, and invoking `omni.call`. That's inefficient, and refactoring some things in Omni would make this cleaner.
 * alternatives with more direct calls
 * funniness messing with loggers to suppress some calls
* workflow parsing and how workflow is calculated/used
* Stitcher decides if the request is a stitching request based on some heuristics about link types and number of aggregates on a link. That determines if it calls the SCS.
* Developer options
* AM error codes
To add a new error code / message that stitcher should handle, see objects.py around line 2067. The key questions are whether you mark it `isFatal` (don't bother retrying locally) or `isVlanAvailableIssue` (try to look for another VLAN) or nothing, and what error message is printed.

## `objects.py`
This file defines a number of basic objects. The primary one is the `Aggregate` class that represents an aggregate. This has the key method `allocate`. An Aggregate instance stores things like the type of AM, the AM API version to speak, the URN and URL, the paths it is on, the hops it provides, its dependencies, whether there is a reservation, the request and manifest DOM instances, etc.

* See `Aggregate.supportsAny` which hard codes which AM types can take a suggested vlan tag of `any`
* `Aggregate.getExpiresForRequest` knows about the different AM types that have different expirations and uses the `defs.py` which in turn checks `omni_defaults` in the `omni_config` to find out when slivers will initially expire.
* `Aggregate.editEGRequest` edits ExoGENI URNs so that EG AMs don't have errors trying to process parts of the request for them that are really for another EG AM.
* `Aggregate.doAvail` knows which AM types provide valid VLAN tag availability information from `listresources` when called with the `--available` option
* `Aggregate.urn_syns_helper` knows about the multiple URN forms that can refer to the same AM (like `+cm` vs `+am` or `vmsite` vs `net`).
* `Aggregate` has multiple constants, like the number of times to retry
* This file is in serious need of refactoring.

FIXME: Say more about the key methods and data structures

# Tools
There are multiple support script included with geni-tools under `src` and `examples`.

## readyToLogin
Use `sliverstatus` and the manifest to determine when compute resources are ready for use, and report the proper SSH commandline. See github for open issues.

## omni-configure
Run this on the Omni configuration bundle downloaded from the GENI portal to set up SSH and SSL keys and the omni.config file needed to run Omni.

## clear-passpharses
Remove the passphrase from an SSL key

## deleteSliceCred
Slice credentials can be delegated. A delegated slice credential may be a subset of the permissions in theory, though in practice all credentials allow doing anything. When using a delegated credential, the actor appears to be the owner of the resources and is responsible, as opposed to speaks for, where the original user retains responsibility. This script allows generating a delegated slice credential.

## addMemberToSliceAndSlivers
Update slice membership at the CH (not supported by all CHs) and then use the slice membership to install SSH keys (as listed by the CH) on the slivers, using the `poa` command. Note supported at all aggregates.

## experiationofmyslices
Essentially `print_sliver_expiration` on all slices listed at the CH

## remote-execute
Essentially using SSH to execute a command on multiple nodes

## renewSliceAndSlivers
Use this for instance in a cron job to auto renew a long lived slice. This script does not do a good job at checking error returns or reporting on script results.

# GCF
GCF refers to the gcf sample aggregate and clearinghouse. The sample clearinghouse (run using `gcf-ch`) is extremely trivial, providing no persistence and only basic functionality. It does not run the Uniform Federation API - this would be a good improvement.
The sample aggregate (run using `gcf-am`) implements the GENI AM API. There are versions for each AM API version. This aggregate has no persistence and no real resources. However, there are multiple efforts to use this as the basis of real aggregates. The primary benefit of this foundation is the definition of the AM API functions and the authorization support. For one example based on the GCM AM, see https://github.com/GENI-NSF/gram
Note that there are limits to the AM API support of this GCF AM, such as some of the newer APIv4 changes.

You can do basic tests that the GCF AM/CH are working using `gcf-test`. Omni can talk to the GCF CH, and of course to the AM as it is just another aggregate; use `type=gcf` in your `omni_config`.

`gen-certs.py` can be used to generate some testing certificates for the GCF CH and AM, and a test user or 2.

The GCF code sits under `src/gcf/geni`.

## Credential utilities
`src/gcf/geni/util/cred_util.py` contains utilities for validating credentials and determining if a credential provides the needed rights for the caller to invoke a method. The `CredentialVerifier` reads the list of trust roots, and provides the `verify_from_strings` method that the gcf-am uses. This function also handles speaks for. This same file also provides a utility for creating a credential.

## Speaks For
Also included within the GCF code directory is support for Speaks For. For more information on Speaks For, see
* http://groups.geni.net/geni/wiki/GAPI_AM_API_DRAFT/Adopted#ChangeSetP:SupportproxyclientsthatSpeakForanexperimenter
* http://groups.geni.net/geni/wiki/TIEDABACCredential
* http://abac.deterlab.net/

Speaks for allows a tools to act on behalf of an experimenter, while the experimenter retains responsibility for the actions. It is conferred using a special credential that contains an ABAC statement.
geni-tools provides utilities for creating and validating speaks for credentials in `src/gcf/geni/utils/speaksfor_util.py`. That file provides a `main()` (be sure to set `PYTHONPATH=geni-tools-dir/src`) whose `-h` message provides more usage information. Runtime callers use `determine_speaks_for` which returns a certificate: either that of caller of the XMLRPC method if this was not a valid speaks-for call, or the certificate of the real user instead of the caller/tool, if this was a valid speaks-for invocation.

## Authorization engine
See README-authorization.txt


## Scheduling support
See README-scheduling.txt


# Acceptance tests
geni-tools comes with some basic tests for checking that an aggregate complies with the GENI AM API. See `acceptance_tests/AM_API/README-accept-AMAPI.txt`.
These tests are not complete and have not been updated for recent additions / modifications to the AM API.
They are however a good start for aggregate developers.

# SFA
For validating and generating certificates and credentials, geni-tools uses code from the PlanetLab Slice Federation Architecture (SFA). See http://git.planet-lab.org/?p=sfa.git
For details on what is used, the license, and how it is used, see `src/gcf/sfa`.
Our contacts at SFA are:
* Thierry Parmentelat <thierry.parmentelat@inria.fr>
* Tony Mack <tmack@CS.Princeton.EDU>

The latest SFA code has not been integrated. See ticket #854, and a start at this integration at : https://github.com/ahelsing/geni-tools/tree/tkt854-newsfa

Credentials follow a schema. GENI uses a schema that is at http://www.planet-lab.org/resources/sfa/credential.xsd
Note that ProtoGENI has a version of this (same content, different namespace.
Ideally, GENI would use a version that is hosted at geni.net, but it is unclear what issues with verification / trust this would cause. Note that the namespace in such a schema would need to be changed.

GENI also uses the SFA mechanism for assigning rights. In practice, all useful rights are included in any credential, but a possible future enhancement would be to change to more reasonable rights - ones that better map to actual operations, allowing giving different rights in different credentials.

SFA makes use of M2Crypto, PyOpenSSL, and xmlsec. As a result, Omni depends on all these. xmlsec is used to sign and validate XML digital signatures.
* https://www.aleksey.com/xmlsec/
* https://gitlab.com/m2crypto/m2crypto

M2Crypto is old and has issues, and the use of both M2Crypto and PyOpenSSL is unfortunate. It would be nice to eliminate some of this.

