= The Omni GENI Client =

Omni is a GENI experimenter tool that communicates with GENI Aggregate
Managers via the GENI AM API.  The Omni client can also communicate with
control frameworks in order to create slices, delete slices, and
enumerate available GENI Aggregate Managers.  Note that Omni 
supports using control framework native RSpecs, or a (deprecated)
common subset called an 'omnispec'.

To configure Omni, please copy omni_config to your ~/.gcf
directory and fill in the parameters for at least one control
framework - particularly the location of your certificate and key, in
its appropriate section.  Edit the [omni] section to specify that
framework as your default. Embedded comments describe the meaning of
each field. (Note that keys for the GCF framework are stored in ~/.gcf
by default.)

The currently supported control frameworks are SFA (PlanetLab),
ProtoGENI and GCF. Any AM API compliant aggregate should work.
These include SFA, ProtoGENI, OpenFlow and GCF.

Omni performs the following functions:
 * Talks to each control framework in its native API
 * Contacts Aggregate Managers via the GENI API
 * Uses either native RSpecs or a common RSpec format called an
   omnispec (deprecated).

For the latest Omni documentation, examples, and trouble shooting
tips, see the Omni Wiki: http://trac.gpolab.bbn.com/gcf/wiki/Omni

== Release Notes ==
New in v1.5:

New in v1.4:
 * Omni logging is configurable with a -l option, or from a
 script by calling applyLogConfig(). (ticket #61)
 * Omni aborts if it detects your slice has expired (ticket #51)
 * Omni config can define aggregate nicknames, to use instead
 of a URL in the -a argument. (ticket #62)
 * Solved a thread safety bug in omni - copy options list. (ticket #63)
 * SFA logger handles log file conflicts (ticket #48)
 * Handle expired user certs nicely in Omni (ticket #52)
 * Write output filename when ListResources or GetVersion saves
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
 more than one format (eg both SFA and ProtoGENI V2).
 * New functions 'listmyslices' and 'print_slice_expiration'
 * All commands return a tuple: text result description and a
 command-specific object, suitable for use by calling scripts
 * Log and output messages are clearer.

Full changes are listed in the CHANGES file.

== Handling Omni Output ==
In Omni versions prior to v1.3, some output went to STDOUT. Callers could
redirect STDOUT ('>') to a file.
In all cases where users would do that, Omni now supports the
'-o' option to have Omni save the output to one or more files for
you. See the documentation for individual commands for details.

Remaining output is done through the python logging package, and
prints to STDERR by default. Logging levels, format, and output
destinations are configurable by supplying a custom Python logging
configuration file, using the '-l' option. Note that these settings
will apply to the entire Python process. For help creating a logging
config file, see
http://docs.python.org/library/logging.config.html#configuration-file-format
and see the sample 'omni_log_conf_sample.conf'. Note that if present
in your configuration file, Omni will use the special variable
'optlevel' to set logging to INFO by default, and DEBUG if you
specify the '--debug' option to Omni.

Note also that when you do 'omni.call' or 'omni.applyLogConfig' to load a
logging configuration from a file, existing loggers are NOT disabled
(which is the python logging default). However, those existing logers
will not be modified with the new logging settings, unless they are
explicitly named in the logging config file (they or their ancestor,
where 'root' does not count).

For further control of Omni output, use Omni as a library from your
own python script (see below for details). For example, your script
can modify the '-l' logging config file option between Omni
calls. Alternatively, you can call the Omni function
'omni.applyLogConfig(<path to your log config file>)'. See the
documentation for 'applyLogConfig' for details.

== Omnispecs ==

'''Omnispecs are now deprecated. Use native Aggregate RSpecs.'''

Each resource in an omnispec is referred to as an Omni Resource. Each
Omni Resource has a name, a description, a type, booleans indicating
whether the resource is allocated and whether the request wants to
allocate it, and then dictionaries for options and misc fields.

== Omni as a Library ==

The omni.py file can be imported as a library, enabling programmatic
access to Omni functions. To use omni as a library, import omni and
use the omni.call function.

For example:
  User does:
{{{
    myscript.py -f my_sfa --myScriptPrivateOption doNonNativeList <slicename>
}}}

  Your myscript.py code does:
{{{
#!/usr/bin/python
import sys
import omni

################################################################################
# Requires that you have omni installed or the path to gcf/src in your
# PYTHONPATH.
#
# For example put the following in your bashrc:
#     export PYTHONPATH=${PYTHONPATH}:path/to/gcf/src
#
################################################################################

def main(argv=None):
  ##############################################################################
  # Get a parser from omni that understands omni options
  ##############################################################################
  parser = omni.getParser()
  # update usage for help message
  omni_usage = parser.get_usage()
  parser.set_usage(omni_usage+"\nmyscript.py supports additional commands.\n\n\tCommands and their arguments are:\n\t\t\tdoNonNativeList [optional: slicename]")

  ##############################################################################
  # Add additional optparse.OptionParser style options for your
  # script as needed.
  # Be sure not to re-use options already in use by omni for
  # different meanings, otherwise you'll raise an OptionConflictError
  ##############################################################################
  parser.add_option("--myScriptPrivateOption",
                    help="A non-omni option added by %s"%sys.argv[0],
                    action="store_true", default=False)
  # options is an optparse.Values object, and args is a list
  options, args = parser.parse_args(sys.argv[1:])
  if options.myScriptPrivateOption:
    # do something special for your private script's options
    print "Got myScriptOption"



  ##############################################################################
  # figure out that doNonNativeList means to do listresources with the
  # --omnispec argument and parse out slicename arg
  ##############################################################################
  omniargs = []
  if args and len(args)>0:
    if args[0] == "doNonNativeList":
      print "Doing omnispec listing"
      omniargs.append("--omnispec")
      omniargs.append("listresources")
      if len(args)>1:
        print "Got slice name %s" % args[1]
        slicename=args[1]
        omniargs.append(slicename)
    else:
      omniargs = args
  else:
    print "Got no command. Run '%s -h' for more information."%sys.argv[0]
    return

  ##############################################################################
  # And now call omni, and omni sees your parsed options and arguments
  ##############################################################################
  text, retItem = omni.call(omniargs, options)

  # Give the text back to the user
  print text

  # Process the dictionary returned in some way
  if type(retItem) == type({}):
    numItems = len(retItem.keys())
  elif type(retItem) == type([]):
    numItems = len(retItem)
  if numItems:
    print "\nThere were %d items returned." % numItems

if __name__ == "__main__":
  sys.exit(main())
}}}

  This is equivalent to:
{{{
    ./omni.py --omnispec listresources <slicename>
}}}

This allows your calling script to:
 * Have its own private options
 * Programmatically set other omni options (like inferring the "--omnispec")
 * Accept omni options (like "-f") in your script to pass along to omni

In the omni.call method:
 * argv is a list just like sys.argv
 * options is an optional optparse.Values structure,
   like you get from parser.parse_args.  
   Use this to pre-set certain values, or allow your caller to get
   omni options from its commandline.

 * The verbose option allows printing the command and summary,
   or suppressing it.
 * Callers can control omni logs (suppressing console printing for
   example) using python logging.

== Extending Omni ==

Extending Omni to support additional frameworks with their own
clearinghouse APIs requires adding a new Framework extension class.

We recommend not trying to support omnispecs for different RSpec formats.

== Omni workflow ==
For a fully worked simple example of using Omni, see 
http://groups.geni.net/geni/wiki/GENIExperimenter

 1. Pick a Clearinghouse you want to use. That is the control framework you
    will use.
 2. Be sure the appropriate section of omni_config for your framework
    (sfa/gcf/pg) has appropriate settings for contacting that
    Clearinghouse, and user credentials that are valid for that
    Clearinghouse. And be sure the [omni] section refers to your
    framework as the default.
 3. Run omni -o listresources
  a. When you do this, Omni will contact your designated
     Clearinghouse, using your framework-specific user credentials.
  b. The clearinghouse will list the Aggregates it knows about. For
     example for GCF, the am_* entries in gcf_config. For SFA, it will
     return the contents of /etc/sfa/geni_aggregates.xml.
  c. Omni will then contact each of the Aggregates that the
     Clearinghouse told it about, and use the GENI AM API to ask each
     for its resources. Again, it will use your user credentials. So
     each Aggregate Manager must trust the signer of your user
     credentials, in order for you to talk to it. [This is why you add
     the CH certificate to /etc/sfa/trusted_roots or to the -r
     argument of your GCF gcf-am.py.]
  d. Omni will then save the RSpec from each aggregate into a separate
     XML File (the -o option requested that). Files will be named
     'rspec-<server>.xml'
     (With the --omnispec argument, Omni would convert the
     proprietary RSPecs all into a single 'omnispec'.)
 4. Create a request Rspec, per the control framework
    documentation, to specify which resources you want to reserve.
    [If you used an omnispec, do this by changing 'allocate: false'
    to 'allocate: true' wherever the resource is not already allocated
    ('allocated: true').]
 5. Create a Slice. Slices are created at your Clearinghouse. Slices
    are named based on the Clearinghouse authority that signs for
    them. Using the shorthand (just the name of your slice within PG,
    for example) allows Omni to ensure your Slice is named
    correctly. 
    So run: omni.py createslice MyGreatTestSlice
 6. Allocate your Resources. Given a slice, and your edited request rspec
    file, you are ready to allocate resources by creating slivers at
    each of the Aggregate Managers.  Omni will contact your
    Clearinghouse again, to get the credentials for your slice. 
    (If you used an omnispec, omni will parse your omnispec file,
    converting it back into the framework specific RSpec format.)
    Note you must specify the URL of the aggregate
    where you want to reserve resources. (Otherwise with an omnispec,
    omni will then contact each Aggregate Manager in your omnispec
    where you are reserving resources.)
    Then omni will call the GENI AM API CreateSliver call on the
    Aggregate Manager. It will supply your Slice Credentials (from the
    Clearinghouse) plus your own user certificate, and the RSpec. 

    At this point, you have resources and can do your experiment.

 7. Renew or Delete.  After a while you may want to Renew your Sliver
    that is expiring, or Delete it. Omni will contact the
    Clearinghouse, get a list of all Aggregates, and invoke
    RenewSliver or DeleteSliver on each, for your slice name.

 8. Optional: listmyslices and print_slice_expiration. Occasionally you
    may run listmyslices to remind yourself of your outstanding
    slices. Then you can choose to delete or renew them as needed. If
    you don't recall when your slice expires, use
    print_slice_expiration to remind yourself.

== Running Omni ==

=== Supported options ===
Omni supports the following command-line options.

-c FILE   Location of your config file (default ~/.gcf/omni_config)

-f FRAMEWORK   Control framework to use (e.g. my_sfa), overriding
        default in config file.  The framework is a section named in the config file.

-n, --native   Use native RSpecs (default)

--omnispec     Use Omnispecs (deprecated)

-a AGGREGATE_URL, --aggregate=AGGREGATE_URL or nickname defined in omni_config
                Communicate with a specific aggregate

--debug   Enable debugging output

--no-ssl   Do not use ssl

--orca-slice-id=ORCA_SLICE_ID
        Use the given Orca slice id

-o, --output   Write output of getversion, listresources,
        createsliver, sliverstatus, or getslicecred to a file (Omni
        picks the name)

-p FILENAME_PREFIX, --prefix=FILENAME_PREFIX
        Filename prefix (used with -o)

--slicecredfile SLICE_CRED_FILENAME
        Name of slice credential file to read from if it exists, or
	save to when running like 
	'--slicecredfile mySliceCred.xml -o getslicecred mySliceName'

-t AD-RSPEC-TYPE AD-RSPEC-VERSION, --rspectype=AD-RSPEC-TYPE AD-RSPEC-VERSION
        Ad RSpec type and version to return, e.g. 'ProtoGENI 2'

-v, --verbose  (default True)
        Turn on verbose command summary for omni commandline tool

-q, --quiet    (default False)
        Turn off verbose command summary for omni commandline tool

--tostdout (default True)
        Print results like RSpecs to STDOUT instead of logging.
	Only relevant when not saving results to a file with the -o option.

=== Supported commands ===
Omni supports the following commands.

==== listaggregates ====
Print the known aggregates' URN and URL.

 * format: omni.py [-a AM_URL_or_nickname] listaggregates
 * examples:
  * omni.py listaggregates
           List all aggregates from the omni_config 'aggregates'
	   option if supplied, else all aggregates listed by the
	   Clearinghouse
  * omni.py -a http://localhost:8001 listaggregates
           List just the aggregate from the commandline
  * omni.py -a myLocalAM listaggregates
           List just the aggregate from the commandline, looking up
           the nickname in omni_config
 
 Gets the aggregates list from the commandline, or from the
 omni_config 'aggregates' option, or from the Clearinghouse.

==== createslice ====
Creates the slice in your chosen control framework.

 * format:  omni.py createslice <slice-name>
 * examples: 
  * omni.py createslice myslice
  * Or to create the slice and save off the slice credential:
     	   omni.py -o createslice myslice
  *  Or to create the slice and save off the slice credential to a
           specific file:
           omni.py -o --slicecredfile mySpecificfile-myslice-credfile.xml 
                   createslice myslice

 Slice name could be a full URN, but is usually just the slice name portion.
 Note that PLC Web UI lists slices as <site name>_<slice name>
 (e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

 Note that Slice Authorities typically limit this call to
 privileged users, e.g. PIs.

 Note also that typical slice lifetimes are short. See RenewSlice.

==== renewslice ====
Renews the slice at your chosen control framework. If your slice
expires, you will be unable to reserve resources or delete
reservations at aggregates.

 * format:  omni.py renewslice <slice-name> <date-time>
 * example: omni.py renewslice myslice 20100928T15:00:00Z

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
Deletes the slice in your chosen control framework.

 * format:  omni.py deleteslice <slice-name> 
 * example: omni.py deleteslice myslice

Slice name could be a full URN, but is usually just the slice name portion.
Note that PLC Web UI lists slices as <site name>_<slice name>
(e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

Delete all your slivers first! Deleting your slice does not free up resources at
various aggregates.

Note that DeleteSlice is not supported by all control frameworks: some just
let slices expire.

==== listmyslices ====
List slices registered under the given username.
Not supported by all frameworks.

 * format: omni.py listmyslices <username>
 * example: omni.py listmyslices jdoe

==== getslicecred ====
Get the AM API compliant slice credential (signed XML document)
for the given slice name

 * format: omni.py getslicecred <slicename>

 * examples:
  * Get slice mytest credential from slice authority, save to a file:
      omni.py -o getslicecred mytest

  * Get slice mytest credential from slice authority,
    save to a file with prefix mystuff:
      omni.py -o -p mystuff getslicecred mytest

  * Get slice mytest credential from slice authority,
    save to a file with name mycred.xml:
      omni.py -o --slicecredfile mycred.xml getslicecred mytest

  * Get slice mytest credential from saved file 
    delegated-mytest-slicecred.xml (perhaps this is a delegated credential?): 
      omni.py --slicecredfile delegated-mytest-slicecred.xml getslicecred mytest

If you specify the -o option, the credential is saved to a file.
The filename is <slicename>-cred.xml
But if you specify the --slicecredfile option then that is the filename used.

Additionally, if you specify the --slicecredfile option and that
references a file that is not empty, then we do not query the Slice
Authority for this credential, but instead read it from this file.

Arg: slice name
Slice name could be a full URN, but is usually just the slice name portion.
Note that PLC Web UI lists slices as <site name>_<slice name>
(e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

==== print_slice_expiration ====
Print the expiration time of the given slice, and a warning if it is
soon.
e.g. warn if the slice expires within 3 hours.

 * format omni.py print_slice_expiration <slice name>
 * example: omni.py print_slice_expiration my_slice

Arg: slice name
Slice name could be a full URN, but is usually just the slice name portion.
Note that PLC Web UI lists slices as <site name>_<slice name>
(e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

With the --slicecredfile option the slice's credential is read from
that file, if it exists. Otherwise the Slice Authority is queried.

==== getversion ====
Call the AM API GetVersion function at each aggregate.

 * format:  omni.py [-a AM_URL_or_nickname] getversion
 * examples:
  * omni.py getversion
  * GetVersion for only this aggregate: 
        omni.py -a http://localhost:12348 getversion
  * Save GetVersion information to per-aggregate files: 
        omni.py -o getversion

Aggregates queried:
 - Single URL given in -a argument or URL listed under that given
 nickname in omni_config, if provided, ELSE
 - List of URLs given in omni_config aggregates option, if provided, ELSE
 - List of URNs and URLs provided by the selected clearinghouse

Options:
 - -o Save result (JSON format) in per-Aggregate files
 - -p Prefix for resulting version information files (used with -o) 
 - If not saving results to a file, they are logged.
 - If --tostdout option, then instead of logging, print to STDOUT.

==== listresources ====
Call the AM API ListResources function at specified aggregates.

 * format:  omni.py [-a AM_URL_or_nickname] [-n] [-o [-p fileprefix]] \
                    listresources [slice-name] 
 * examples:
  * omni.py listresources
    	    List resources at all AMs on your CH
  * omni.py listresources myslice
    	    List resources in myslice from all AMs on your CH
  * omni.py -a http://localhost:12348 listresources myslice
    	    List resources in myslice at the localhost AM
  * omni.py -a myLocalAM listresources
            List resources at the AM with my nickname myLocalAM in omni_config
  * omni.py listresources -a http://localhost:12348 -t ProtoGENI 2 myslice
            List resources in myslice at the localhost AM, requesting that
	    the AM send a ProtoGENI V2 format RSpec.
  * omni.py -a http://localhost:12348 --omnispec listresources myslice
            List resources in myslice at the localhost AM, converting
	    them to the deprecated omnispec format.
  * omni.py -a http://localhost:12348 -o -p myprefix listresources myslice 
            List resources at a specific AM and save it to a file
	    with prefix 'myprefix'.

This command will list the rspecs of all GENI aggregates available
through your chosen framework.
It can save the result to a file so you can use the result to
create a reservation RSpec, suitable for use in a call to
createsliver.
Omnispecs can be optionally generated with --omnispec.

If a slice name is supplied, then resources for that slice only 
will be displayed.  In this case, the slice credential is usually
retrieved from the Slice Authority. But
with the --slicecredfile option it is read from that file, if it exists.


If an Aggregate Manager URL is supplied, only resources
from that AM will be listed.

If the "--omnispec" flag is used then the native RSpec is converted
to the deprecated omnispec format.

Options:
 - -n gives native format (default)
    Note: omnispecs are deprecated. Native format is preferred.
 - --omnispec request Omnispec (json format) translation. Deprecated
 - -o writes to file instead of stdout; omnispec written to 1 file,
    native format written to single file per aggregate.
 - -p gives filename prefix for each output file
 - If not saving results to a file, they are logged.
 - If --tostdout option, then instead of logging, print to STDOUT.
 - -t Requires the AM send RSpecs in the given type and version. If the
    AM does not speak that type and version, nothing is returned. Use
    GetVersion to see available types at that AM.
    Type and version are case-sensitive strings.
 - --slicecredfile says to use the given slicecredfile if it exists.

File names will indicate the slice name, file format, and either
the number of Aggregates represented (omnispecs), or
which aggregate is represented (native format).
e.g.: myprefix-myslice-rspec-localhost-8001.xml

==== createsliver ====
The GENI AM API CreateSliver call: reserve resources at GENI aggregates.

 * format:  omni.py [-a AM_URL_or_nickname [-n]] createsliver <slice-name> <spec file>
 * examples:
  * omni.py createsliver myslice resources.rspec
  * omni.py -a http://localhost:12348 createsliver myslice resources.rspec
  * Use a saved (delegated?) slice credential: 
        omni.py --slicecredfile myslice-credfile.xml \
            -a http://localhost:12348 createsliver myslice resources.rspec
  * Save manifest RSpec to a file with a particular prefix: 
        omni.py -a http://localhost:12348 -o -p myPrefix \
             createsliver myslice resources.rspec 
  * Use an omnispec to create sliver(s): 
        omni.py --omnispec createsliver myslice resources.ospec

 * argument: the RSpec file should have been created by using
            availability information from a previous call to
            listresources (e.g. omni.py -o listresources). 
	    Warning: request RSpecs are often very different from
            advertisement RSpecs.
For help creating ProtoGENI RSpecs, see
              http://www.protogeni.net/trac/protogeni/wiki/RSpec.
To validate the syntax of a generated request RSpec, run:
{{{
  xmllint --noout --schema http://www.protogeni.net/resources/rspec/2/ad.xsd \
                      yourRequestRspec.xml
}}}

This createsliver command will allocate the requested resources at
the indicated aggregate (or in omnispecs those marked
with allocate: true).
Note: This command operates by default in native mode "-n" by sending a
native rspec to a single aggregate specified by the "-a" command.
Omnispecs are deprecated and native format RSpecs are the default.

Typically users save the resulting manifest RSpec, to learn details
about what resources were actually granted to them. Use the -o
option to have that manifest saved to a file. Manifest files are
named something like:
   myPrefix-mySlice-manifest-rspec-AggregateServername.xml

Slice name could be a full URN, but is usually just the slice name portion.
Note that PLC Web UI lists slices as <site name>_<slice name>
(e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

Options:
 - -n Use native format RSpec. Requires -a.
    Native RSpecs are default, and omnispecs are deprecated.
 - --omnispec Use Omnispec formats. Deprecated.
 - -a Contact only the aggregate at the given URL, or with the given
 nickname that translates to a URL in your omni_config
 - --slicecredfile Read slice credential from given file, if it exists
 - -o Save result (manifest rspec) in per-Aggregate files
 - -p Prefix for resulting manifest RSpec files. (used with -o)
 - If not saving results to a file, they are logged.
 - If --tostdout option, then instead of logging, print to STDOUT.

Slice credential is usually retrieved from the Slice Authority. But
with the --slicecredfile option it is read from that file, if it exists.

omni_config users section is used to get a set of SSH keys that
should be loaded onto the remote node to allow SSH login, if the
remote resource and aggregate support this.

Note you likely want to check SliverStatus to ensure your resource comes up.
And check the sliver expiration time: you may want to call RenewSliver.

==== renewsliver ====
Calls the AM API RenewSliver function

 * format:  omni.py renewsliver [-a AM_URL_or_nickname] <slice-name> "<time>"
 * examples:
  * omni.py renewsliver myslice "12/12/10 4:15pm"
  * omni.py renewsliver myslice "12/12/10 16:15"
  * omni.py -a http://localhost:12348 renewsliver myslice "12/12/10 16:15"
  * omni.py -a myLocalAM renewsliver myslice "12/12/10 16:15"

This command will renew your resources at each aggregate up to the
specified time.  This time must be less than or equal to the time
available to the slice.  Times are in UTC or supply an explicit timezone.

Slice name could be a full URN, but is usually just the slice name portion.
Note that PLC Web UI lists slices as <site name>_<slice name>
(e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

Slice credential is usually retrieved from the Slice Authority. But
with the --slicecredfile option it is read from that file, if it exists.

Aggregates queried:
 - Single URL given in -a argument or URL listed under that given
 nickname in omni_config, if provided, ELSE
 - List of URLs given in omni_config aggregates option, if provided, ELSE
 - List of URNs and URLs provided by the selected clearinghouse

Note that per the AM API expiration times will be timezone aware.
Unqualified times are assumed to be in UTC. See below for an exception.

Note that the expiration time cannot be past your slice expiration
time (see renewslice). Some aggregates will
not allow you to _shorten_ your sliver expiration time.

Note that older SFA-based aggregates (like the MyPLC aggregates in the
GENI mesoscale deployment) fail to renew slivers when a timezone is
present in the call from omni. If you see an error from the aggregate
that says {{{Fault 111: "Internal API error: can't compare
offset-naive and offset-aware date times"}}} you should add the
"--no-tz" flag to the omni renewsliver command line.

==== sliverstatus ====
GENI AM API SliverStatus function

 * format: omni.py [-a AM_URL_or_nickname] sliverstatus <slice-name>
 * examples:
  * omni.py sliverstatus myslice
  * omni.py -a http://localhost:12348 sliverstatus myslice
  * omni.py -a myLocalAM sliverstatus myslice

This command will get information from each aggregate about the
status of the specified slice. This can include expiration time,
whether the resource is ready for use, and the SFA node login name.

Slice name could be a full URN, but is usually just the slice name portion.
Note that PLC Web UI lists slices as <site name>_<slice name>
(e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

Slice credential is usually retrieved from the Slice Authority. But
with the --slicecredfile option it is read from that file, if it exists.

Aggregates queried:
 - Single URL given in -a argument or URL listed under that given
 nickname in omni_config, if provided, ELSE
 - List of URLs given in omni_config aggregates option, if provided, ELSE
 - List of URNs and URLs provided by the selected clearinghouse

Options:
 - -o Save result in per-aggregate files
 - -p Prefix for resulting files (used with -o) 
 - If not saving results to a file, they are logged.
 - If --tostdout option, then instead of logging, print to STDOUT.

==== deletesliver ====
Calls the GENI AM API DeleteSliver function. 
This command will free any resources associated with your slice at
the given aggregates.

 * format:  omni.py [-a AM_URL_or_nickname] deletesliver <slice-name>
 * examples:
  * omni.py deletesliver myslice
  * omni.py -a http://localhost:12348 deletesliver myslice
  * omni.py -a myLocalAM deletesliver myslice

Slice name could be a full URN, but is usually just the slice name portion.
Note that PLC Web UI lists slices as <site name>_<slice name>
(e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

Slice credential is usually retrieved from the Slice Authority. But
with the --slicecredfile option it is read from that file, if it exists.

Aggregates queried:
 - Single URL given in -a argument or URL listed under that given
 nickname in omni_config, if provided, ELSE
 - List of URLs given in omni_config aggregates option, if provided, ELSE
 - List of URNs and URLs provided by the selected clearinghouse

==== shutdown ====
Calls the GENI AM API Shutdown function
This command will stop the resources from running, but not delete
their state.  This command should NOT be needed by most users - it
is intended for emergency stop and supporting later forensics /
debugging. 

 * format:  omni.py [-a AM_URL_or_nickname] shutdown <slice-name>
 * examples:
  * omni.py shutdown myslice
  * omni.py -a http://localhost:12348 shutdown myslice
  * omni.py -a myLocalAM shutdown myslice

Slice name could be a full URN, but is usually just the slice name portion.
Note that PLC Web UI lists slices as <site name>_<slice name>
(e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

Slice credential is usually retrieved from the Slice Authority. But
with the --slicecredfile option it is read from that file, if it exists.

Aggregates queried:
 - Single URL given in -a argument or URL listed under that given
 nickname in omni_config, if provided, ELSE
 - List of URLs given in omni_config aggregates option, if provided, ELSE
 - List of URNs and URLs provided by the selected clearinghouse

