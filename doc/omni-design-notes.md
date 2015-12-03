# Contents
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
      util/:
        credparsing.py: Utilities to parse credentials and distinguish
          between XML credentials and JSON wrapped credentials (wrapped
          as a struct giving type, version, and value)
	dates.py: Define naiveUTC for ensuring all dates internally
          are naive (no timezone) and are in UTC.
	dossl.py: Wrapper for SSL calls to handle common errors,
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
      stitchhandler.py: Handle stitching calls
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

geni-tools code is structured to make it easier to import it in other
tools. Set PYTHONPATH to the `src` directory. To ease this, files use
relative imports. See for example speaksfor_util.py which uses a
try/except to use relative imports by preference, but allow for
running this file's main directly with absolute imports. For similar
reasons, Omni has all its main code in `src/gcf/oscript.py`
rather than directly in omni.py. Stitcher should be refactored
similarly, but has not been.

Omni calls are handled by a special "handler"; handler.py dispatches
to chhandler or amhandler (and Stitcher uses a parallel stitchhandler
for future smoother integration). The handler allows invoking any
method in the handler classes (excluding private methods, indicated by
a name that starts with `_`). Handlers do two kinds of operations:
Call a clearinghouse using a 'framework' (to create a slice or get a credential for
example), and calls to an aggregate. Omni supports multiple
clearinghouse APIs, whose differences are abstracted away with a
'framework' whose API is defined in framework_base.py. The framework
handles getting the user and slice credentials. Additionally, in AM
APIv3 credentials are a struct that indicates the type and version of
the actual credential. The framework handles wrapping and unwrapping
the actual credential as needed. The specific framework to use is inferred dynamically based on the
`omni_config` file. frameworks are named `framework_<framework'type'>.py`, using the `type` from the selected framework section of
the `omni_config`. `framework_chapi` supports the Uniform Federation
API v1 and v2. Currently it hard codes some assumptions that should be
done dynamically using information from `GetVersion` (like whether the
CH supports projects).

`chhandler` supports calls to the clearinghouse: get a user or slice
credential, create or renew a slice, list aggregates, list a user's
slices or projects, etc. Each call parses the commandline arguments
(not options) itself. Calls to the proper framework to do the
clearinghouse call are typically wrapped in _do_ssl to support
automatic retry.

`amhandler` supports calls to aggregates, including all AM APIv2, v2,
v3, and adopted v4 calls. In addition, a number of aggregate specific
calls are supported. Each call parses the arguments itself (e.g. to
get out the slice name), and calls to the aggregate itself are wrapped
in _do_ssl. The amhandler tries to auto-correct the AM API version in
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
versa. Soem of this is available at the clearinghouse, but Omni
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

Many common functions are handled by methods in
handler_utils. handler_utils contains methods for loading and saving
credentials, for saving command output to a file or printing it as
specified by the options, for getting the list of aggregates, and for
looking up aggregates or nicknames in the aggregate nickname
cache.

Omni keeps a cache of aggregate nicknames, by default in
`~/.gcf/agg_nick_cache`. This INI format file maps nicknames to
aggregate URL and URN. Note that the same URN may have multiple URLs
(different AM API versions typically), and the same URL could have
multiple nicknames. The cache is maintained in git and posted on the
Omni wiki. Omni downloads the cache once daily. Nicknames in the cache
are ordered by convention with AM API agnostic nicknames before those
specific to a version, and then by API version number. Nicknames are
typically `<site>-<type>[version#]`, e.g. "moxi-of1". For some purposes,
Omni takes a nickname and looks up the aggregate URN and URL. For
other purposes, Omni starts with a URL or URN and looks up the
nickname for prettier log messages. When doing so, Omni uses some
heuristics for choosing among nicknames that share the same URN or
URL. For example, Omni ignores http vs https in the URL, and Omni prefers
a shorter nickname and one that lists the AM type after the site. Note
that these heuristics are brittle, and hard code the possible strings
to name an AM type. The only risk however is picking an uglier
nickname. Note also that the agg_nick_cache must be kept
up-to-date. In particular, when omni users use the
`--useSliceAggregates` option, it uses the sliver_info records at the
clearinghouse to get AM URNs that are registered as having resources
on this slice. Then Omni must look up a URL for that URN, and uses the
agg_nick_cache to do so. Therefore, any AM that is not listed in the
agg_nick_cache will not be included in Omni operations that use `--useSliceAggregates`.

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
Given the slice name, `_listaggregates` gets the AM URNs from teh
sliver_info records at the clearinghouse, if possible (only at CHAPI
compatible clearinghouses). Omni then retrieves the AM URL and
nickname if possible, avoiding duplicate entries.
If the options do not require using the sliver_info records, then Omni
considers the `-a` options, again looking up the url and urn for the
aggregate nickname (or urn or url). Failing that, Omni uses the
`aggregates` section of the omni_config file. If that fails, Omni asks
the clearinghouse for _all_ aggregates. Except for the explicit CH
call to list all aggregates, this is usually the wrong thing.

handler_utils also provides functions for manipulating
credentials. Omni can save a slice or user credential, or a speaks for
credential, and then load it for use in AM or CH calls. `_load_cred`
handles reading JSON (APIv3) or XML (APIv2 or v1)
credentials. `_get_slice_cred` tries to read any saved credential in
the file specified by `--slicecredfile`, otherwise it asks the
clearinghouse for the slice credential, wrapping or unwrapping the
credential in JSON as needed. `_save_cred` writes the proper JSON or
XML file.

handler_utils also provides helpers for printing or saving call
results, to STDOUT, the logger, a JSON file, or an XML file, as
appropriate, based on the data type and the options. The main method for this is `_printResults`.

amhandler includes a large number of helper functions to support it's
operations and simplify the individual methods. 
BadClientException
GetVersionCache
self.clients
self._extractSliceArg
self._correctAPIVersion
self._api_call
self._getclients()
self._retrieve_value
self._args_to_slicecred
self._build_options
v2 vs v3 functions
self._build_urns

sliver_info stuff
amhandler sliver result parsing functions
opts.devmode

* handlers (reference the AM API and CH specs)
* omni as library (oscript, imports, ...)
* logging (options, config, tricks to edit the handlers, ...)
* frameworks (for CH, baseclass, use of handler_utils)
* get version cache (why, how used, optinos to control use, known
issues)
* AM nick cache (why, how used, options, downloading new one, operator
must upload new one, who decides what goes in here, ordering entries,
key methods in handler_utils, finding URNs for URLs or nicknames,
finding shortest nickname, use with sliver_info, uglinesses
* sliver info: with GENI CH, where used, use of AM nick cache,
* saved user and slice creds
* m2crypto vs pyopenssl vs ?, managing ssl versions and ciphers,
passing chained certs issues, the secure server/client classes
* do_ssl (errors it wraps, retries, errors it suppresses)
* AM method return struct (keeping it common)
* output control options and their interaction
* todo items (summarize tix, code cleanup, pure API call versions, ?)
* show create sliver pseudo code to walk much of the sub systems
* ?

# stitcher
* SCS
 * where to find docs and code, who runs it (contact), who maintains
 it (contact)
 * running scs.py
 * avail commands and their returns
 * what is in the SCS and who controls
 * error modes
 * how stitcher uses it
 * options/inputs that control when/how it is used

* AL2S
 * What it is and how it is used
 * who runs/maintains (contact)
 * where to find code
 * OESS

* stitchhandler, launcher, objects.py
* pseudo code control flow
* logging
* use of omni via omni.call
 * alternatives with more direct calls
 * funniness messing with loggers to suppress some calls
* workflow parsing and how workflow is calculated/used
* developer options
* to do items
 * factor so can use as library
 * factor so can add other things to workflow, other dependencies
 * extract out AM specifics more
 * refactoring for managability / maintainability
 

# tools

# gcf
* What it is
* m2crypto vs pyopenssl
* following the AM API (shortcomings)
 * gram
* doesn't follow the federation API but should
* gcf-test
* using with omni
* cred_utils and speaks for
 * how it is used, what it does, what it doesn't do

authorization engine
* point to readme
* docs on why

scheduling support
* point to readme

acceptance
* what it is, where it is, pointers to using it
* incomplete
* doesn't do v3

# SFA
- we use some of their files. See src/gcf/sfa.
Thierry Parmentelat <thierry.parmentelat@inria.fr>
Tony Mack <tmack@CS.Princeton.EDU>
- Start at merging latest is here: https://github.com/ahelsing/geni-tools/tree/tkt854-newsfa
- credential.xsd really should be posted by geni.net, but
isn't. Unclear what the trust/verification effect would be of a
change. Note that it would require changing the namespace.
http://git.planet-lab.org/?p=sfa.git
