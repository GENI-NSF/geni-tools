= The Omni GENI Client =

Omni is a GENI experimenter tool that communicates with GENI Aggregate
Managers(AMs) via the GENI AM API (GENI AM API is a common API that 
many AMs support).  The Omni client also communicates with
control frameworks in order to create slices, delete slices, and
enumerate available GENI Aggregate Managers (AMs). 
A Control Framework (CF) is a framework of resources that provides 
users with GENI accounts (credentials) that they can use to 
reserve resources in GENI AMs.

See README-omniconfigure.txt for details about how to configure omni.  

The currently supported CFs are SFA (!PlanetLab),
ProtoGENI and GCF. Omni works with any GENI AM API compliant AM.
These include SFA, ProtoGENI, !OpenFlow and GCF.

Omni performs the following functions:
 * Talks to each CF in its native API
 * Contacts AMs via the GENI API

For the latest Omni documentation, examples, and trouble shooting
tips, see the Omni Wiki: http://trac.gpolab.bbn.com/gcf/wiki/Omni

== Release Notes ==
New in v2.0:

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
  * Improved check of manifest RSpec returned by CreateSliver
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
 more than one format (eg both SFA and GENI V3).
 * New functions 'listmyslices' and 'print_slice_expiration'
 * All commands return a tuple: text result description and a
 command-specific object, suitable for use by calling scripts
 * Log and output messages are clearer.

Full changes are listed in the CHANGES file.

== Handling Omni Output ==
In Omni versions prior to v1.3, some output went to STDOUT. Callers could
redirect STDOUT ('>') to a file.
In all cases where users would do that, Omni supports the
'-o' option to have Omni save the output to one or more files for
you. See the [#RunningOmni documentation] for individual commands for details.

Omni output is done through the python logging package, and
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

For further control of Omni output, use Omni as a library from your
own python script (see [#OmniasaLibrary below] for details). 
For example, your script can modify the '-l' logging config file 
option between Omni calls. 
Alternatively, you can call the Omni function
'omni.applyLogConfig(<path to your log config file>)'. See the
documentation for 'applyLogConfig' for details.

When using Omni as a [#OmniasaLibrary script] and you do 'omni.call'
or 'omni.applyLogConfig' to load a logging configuration from a file,
existing loggers are NOT disabled (which is the python logging
default). However, those existing loggers will not be modified with
the new logging settings, unless they are explicitly named in the
logging config file (they or their ancestor, where 'root' does not
count).

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

== Omni workflow ==
For a fully worked simple example of using Omni, see 
http://groups.geni.net/geni/wiki/HowToUseOmni

 1. Pick a Clearinghouse you want to use. That is the control framework you
    will use.
 2. Be sure the appropriate section of omni_config for your framework
    (sfa/gcf/pg) has appropriate settings for contacting that
    CF, and user credentials that are valid for that
    CF. Make sure the [omni] section refers to your
    CF as the default.  If you ran src/omni-configure.py this
    should automatically be configured.
 3. Run `omni.py -o listresources`
  a. When you do this, Omni will contact your designated
     Clearinghouse, using your framework-specific user credentials.
  b. The Clearinghouse will list the AMs it knows about. 
  c. Omni will then contact each of the AMs that the
     Clearinghouse told it about, and use the GENI AM API to ask each
     for its resources. 
  d. Omni will save the Advertisement RSpec from each aggregate into a separate
     XML File (the `-o` option requested that). Files will be named
     `rspec-<server>.xml`
 4. Create a request Rspec to specify which resources you want to
    reserve. (See [http://groups.geni.net/geni/wiki/GENIExperimenter/RSpecs RSpec Documentation] for more details.)
 5. Create a Slice. 
    Run: `omni.py createslice MySlice`
 6. Allocate your Resources. Given a slice, and your request rspec
    file, you are ready to allocate resources by creating slivers at
    each of the AMs.   Note you must specify the URL or nickname of the aggregate
    where you want to reserve resources using the `-a` option. 
    Run: `omni.py createsliver -a pg-utah MySlice request.rspec`
    At this point, you have resources and can do your experiment.
 7. Sliver Status.  Use the `sliverstatus` command to determine the
    status of your resources.  When `geni_status` is `ready`, your
    resources are ready to use for your experiment.

    Run: `omni.py sliverstatus -a pg-utah MySlice`

    Note: If you `geni_status` is `unknown`, then your resources might be ready.
 
 7. Renew or Delete.  Both slices and slivers have distinct expiration times. 
    After a while you may want to Renew your Sliver
    that is expiring, or Delete it. 

    To Renew: `omni.py renewsliver -a pg-utah MySlice 20120531`
    
    To Delete: `omni.py deletesliver -a pg-utah MySlice`

 8. Optional: `listmyslices` and `print_slice_expiration`. Occasionally you
    may run `listmyslices` to remind yourself of your outstanding
    slices. Then you can choose to delete or renew them as needed. If
    you don't recall when your slice expires, use
    `print_slice_expiration` to remind yourself.

    To List your slices : `omni.py listmyslices <username>`

    To Print slice expiration : `omni.py print_slice_expiration MySlice`
    
== Running Omni ==

=== Supported options ===
Omni supports the following command-line options.

{{{
$ ./omni.py -h                                
Usage:                                                                         
GENI Omni Command Line Aggregate Manager Tool Version 1.6.2                    
Copyright (c) 2011 Raytheon BBN Technologies                                   

omni.py [options] <command and arguments> 

         Commands and their arguments are: 
                AM API functions:          
                         getversion        
                         listresources [optional: slicename] 
                         createsliver <slicename> <rspec file> 
                         sliverstatus <slicename>              
                         renewsliver <slicename> <new expiration time in UTC> 
                         deletesliver <slicename>                             
                         shutdown <slicename>                                 
                Clearinghouse / Slice Authority functions:                    
                         listaggregates                                       
                         createslice <slicename>                              
                         getslicecred <slicename>                             
                         renewslice <slicename> <new expiration time in UTC>  
                         deleteslice <slicename>                              
                         listmyslices <username>                              
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
  --usercredfile=USER_CRED_FILENAME
                        Name of user credential file to read from if it
                        exists, or save to when running like '--usercredfile
                        myUserCred.xml -o getusercred'
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
  --logoutput=LOGOUTPUT
                        Python logging output file [use %(logfilename)s in
                        logging config file]
  --no-tz               Do not send timezone on RenewSliver
  -V API_VERSION, --api-version=API_VERSION
                        Specify version of AM API to use (1, 2, etc.)
  --no-compress         Do not compress returned values
  --available           Only return available resources
  --arbitrary-option    Add an arbitrary option to ListResources (for testing
                        purposes)
}}}

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

==== getusercred ====
Get the AM API compliant user credential (signed XML document) from
the configured slice authority.

 * format: omni.py getusercred

 * examples:
  * Print the user credential obtained from the slice authority:
      omni.py getusercred

  * Get the user credential from the slice authority and save it to a file:
      omni.py -o getusercred

If you specify the -o option, the credential is saved to a file.
The filename is <framework>-usercred.xml.

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
                    [-t <RSPEC_TYPE> <RSPEC_VERSION>] \
                    [--api-version <version #, 1 is default, or 2>] \
                    listresources [slice-name] 
 * examples:
  * omni.py listresources -t geni 3
            List resources at all AMs on your CH using GENI v3 format ad RSpecs
  * omni.py listresources myslice -t geni 3
            List resources in myslice from all AMs on your CH
  * omni.py -a http://localhost:12348 listresources myslice -t geni 3
            List resources in myslice at the localhost AM
  * omni.py -a myLocalAM listresources -t geni 3
            List resources at the AM with my nickname myLocalAM in omni_config
  * omni.py listresources -a http://localhost:12348 -t GENI 3 myslice
            List resources in myslice at the localhost AM, requesting that
            the AM send a GENI v3 format RSpec.
  * omni.py -a http://localhost:12348 -o -p myprefix listresources myslice \
            -t geni 3
            List resources at a specific AM and save it to a file
            with prefix 'myprefix'.
  * omni.py -a http://localhost:12348 listresources myslice -t geni 3 \
            --api-version 2
            List resources in myslice at the localhost AM, using AM API
            version 2 and requesting GENI v3 format manifest RSpecs.

This command will list the RSpecs of all GENI aggregates available
through your chosen framework.
It can save the result to a file so you can use the result to
create a reservation RSpec, suitable for use in a call to
createsliver.

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
    This argument is REQUIRED when using AM API version 2 or later.
 - --slicecredfile says to use the given slicecredfile if it exists.
 - --api-version specifies the version of the AM API to speak.
    AM API version 1 is the default.

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
  * omni.py -a http://localhost:12348 --api-version 2 createsliver \
            myslice resources.rspec
        Specify using GENI AM API v2 to reserve a sliver in myslice from \
        an AM running at localhost, using the request rspec in resources.rspec.
  * Use a saved (delegated?) slice credential: 
        omni.py --slicecredfile myslice-credfile.xml \
            -a http://localhost:12348 createsliver myslice resources.rspec
  * Save manifest RSpec to a file with a particular prefix: 
        omni.py -a http://localhost:12348 -o -p myPrefix \
             createsliver myslice resources.rspec 

 * argument: the RSpec file should have been created by using
            availability information from a previous call to
            listresources (e.g. omni.py -o listresources). 
	    Warning: request RSpecs are often very different from
            advertisement RSpecs.
For help creating GENI RSpecs, see
              http://www.protogeni.net/trac/protogeni/wiki/RSpec.
To validate the syntax of a generated request RSpec, run:
{{{
  xmllint --noout --schema http://www.geni.net/resources/rspec/3/request.xsd \
                      yourRequestRspec.xml
}}}

This createsliver command will allocate the requested resources at
the indicated aggregate.
Note: This command operates by default in native mode "-n" by sending a
native rspec to a single aggregate specified by the "-a" command.

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
 - --api-version specifies the version of the AM API to speak.
    AM API version 1 is the default.

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
  * omni.py -a http://localhost:12348 --api-version 2 \
            renewsliver myslice "12/12/10 16:15"
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
  * omni.py -a http://localhost:12348 --api-version 2 sliverstatus myslice
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
 - --api-version specifies the version of the AM API to speak.
    AM API version 1 is the default.

==== deletesliver ====
Calls the GENI AM API DeleteSliver function. 
This command will free any resources associated with your slice at
the given aggregates.

 * format:  omni.py [-a AM_URL_or_nickname] deletesliver <slice-name>
 * examples:
  * omni.py deletesliver myslice
  * omni.py -a http://localhost:12348 deletesliver myslice
  * omni.py -a http://localhost:12348 --api-version 2 deletesliver myslice
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
  * omni.py -a http://localhost:12348 --api-version 2 shutdown myslice
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
