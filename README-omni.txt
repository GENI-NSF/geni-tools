= The Omni GENI Client =

Omni is an end-user GENI client that communicates with GENI Aggregate
Managers via the GENI AM API.  The Omni client can also communicate with
control frameworks in order to create slices, delete slices, and
enumerate available GENI Aggregate Managers.  Note that Omni 
supports using control framework native RSpecs, or a (deprecated)
common unified 'omnispec'.

To configure Omni, please copy omni_config to your ~/.gcf
directory and fill in the parameters for at least one control
framework.  The "omni" section should be filled in with the
certificate and key that you use in your control framework.  Note that
keys for the GCF framework are by default stored in ~/.gcf. Embedded
comments describe the meaning of each field.

The currently supported control frameworks are SFA (PlanetLab),
ProtoGENI and GCF. Any AM API compliant aggregate should work. These include SFA,
ProtoGENI, OpenFlow and GCF.

Omni performs the following functions:
 * Talks to each control framework in its native API
 * Contacts Aggregate Managers via the GENI API
 * Uses either native RSpecs or a common RSpec format called an
   omnispec (deprecated).


== Omnispecs ==

NOTE: Omnispecs are deprecated. Use native Aggregate RSpecs.

Each resource in an omnispec is referred to as an OmniResource. Each
OmniResource has a name, a description, a type, booleans indicating
whether the resource is allocated and whether the request wants to
allocate it, and then hashes for options and misc fields.


== Omni as a Library ==

The omni.py file can be imported as a library, allowing Omni to front
for other user tools. To do so, import omni and use the omni.call
function.
EG:
     User does:    myscript.py -f my_sfa --myScriptPrivateOption doNativeList slicename

     Your myscript.py code does:
      import omni
      # Get a parser from omni that understands omni options
      parser = omni.getParser()
      # Add additional optparse.OptionParser style options for your script as needed
      # Be sure not to re-use options already in use by omni for different meanings
      # otherwise you'll raise an OptionConflictError
      parser.add_option("--myScriptPrivateOption", action="store_true", default=False)
      # options is an optparse.Values object, and args is a list
      options, args = parser.parse_args(sys.argv[1:])
      if options.myScriptPrivateOption:
          # do something special for your private script's options
	  print "Got myScriptOption"
      # figure out doNativeList means to do listresources with the -n argument and parse out slicename arg
      omniargs = ["-n", 'listresources', slicename]
      # And now call omni, and omni sees your parsed options and arguments
      text, dict = omni.call(omniargs, options)
      print text

    This is equivalent to: 
    	    	       ./omni.py -n listresources slicename
    However, this allows your calling script to:
    	     Have its own private options
    	     Programmatically set other omni options (like inferring the "-n")
	     Accept omni options (like "-f") in your script to pass
    	    	       along to omni

In the omni.call method:
    argv is a list ala sys.argv
    options is an optional optparse.Values structure like you get from parser.parse_args
      Use this to pre-set certain values, or allow your caller to get omni options from its commandline

    The verbose option allows printing the command and summary, or suppressing it.
    Callers can control omni logs (suppressing console printing for example) using python logging.

== Extending Omni ==

Extending Omni to support additional types of Aggregate Managers with
different RSpec formats requires adding a new omnispec/rspec
conversion file.

Extending Omni to support additional frameworks with their own
clearinghouse APIs requires adding a new Framework extension class.


== Omni workflow ==

 1. Pick a Clearinghouse you want to use. That is the control framework you
    will use.
 2. Be sure the appropriate section of omni config for your framework
    (sfa/gcf/pg) has appropriate settings for contacting that
    Clearinghouse, and user credentials that are valid for that
    Clearinghouse.
 3. Run omni -n -o listresources
  a. When you do this, Omni will contact your designated
     Clearinghouse, using your framework-specific user credentials.
  b. The clearinghouse will list the Aggregates it knows about. EG for
     GCF, the am_* entries in gcf_config. For SFA, it will return the
     contents of /etc/sfa/geni_aggregates.xml.
  c. Omni will then contact each of the Aggregates that the
     Clearinghouse told it about, and use the GENI AM API to ask each
     for its resources. Again, it will use your user credentials. So
     each Aggregate Manager must trust the signer of your user
     credentials, in order for you to talk to it. This is why you add
     the CH certificate to /etc/sfa/trusted_roots or to the -r
     argument of your GCF gcf-am.py.  
  d. Omni will then save the RSpec from each aggregate into a separate
     XML File (the -o option requested that). Files will be named
     'rspec-<server>.xml'
     (Without the -n argument, Omni would convert the
     proprietary RSPecs all into a single 'omnispec'.)
 4. Edit this file (or create a new file, per the control framework
    documentation) to specify which resources you want to reserve.
    If you used an omnispec, do this by changing 'allocate: false' to 'allocate: true'
    wherever the resource is not already allocated ('allocated: true').
 5. Create a Slice. Slices are created at your Clearinghouse. Slices
    are named based on the Clearinghouse authority that signs for
    them. Using the shorthand (just the name of your slice within PG,
    for example) allows Omni to ensure your Slice is named
    correctly. 
    So run: omni.py createslice MyGreatTestSlice
 6. Allocate your Resources. Given a slice, and your edited rspec
    file, you are ready to allocate resources by creating slivers at
    each of the Aggregate Managers.  Omni will contact your
    Clearinghouse again, to get the credentials for your slice. 
    If you used an omnispec, omni will parse your omnispec file,
    converting it back into framework specific RSpec format as
    necessary.
    If you used a native RSpec, you specify the URL of the aggregate
    where you want to reserve resources. Otherwise with an omnispec,
    omni will then contact each Aggregate Manager in your omnispec
    where you are reserving resources.
    Then omni will call the GENI AM API CreateSliver call on the
    Aggregate Manager. It will supply your Slice Credentials (from the
    Clearinghouse) plus your own user certificate, and the RSpec. At
    this point, you have resources and can do your experiment.
 7. Renew or Delete.  After a while you may want to Renew your Sliver
    that is expiring, or Delete it. Omni will contact the
    Clearinghouse, get a list of all Aggregates, and invoke
    RenewSliver or DeleteSliver on each, for your slice name.

== Running Omni ==

=== The following options are supported: ===

-c FILE   Location of your config file (default ~/.gcf/omni_config)

-f FRAMEWORK   Control framework to use (e.g. my_sfa), overriding
default in config file.  The framework is a section named in the config file.

-n, --native   Use native RSpecs (preferred)
--omnispec     Use OmniSpec RSpecs (default, will be deprecated soon)
-a AGGREGATE_URL, --aggregate=AGGREGATE_URL
                Communicate with a specific aggregate
--debug   Enable debugging output
--no-ssl   Do not use ssl
--orca-slice-id=ORCA_SLICE_ID
                Use the given Orca slice id
-o, --output   Write output of listresources to a file
-p FILENAME_PREFIX, --prefix=FILENAME_PREFIX
                  RSpec filename prefix
-t AD-RSPEC-TYPE AD-RSPEC-VERSION, --rspectype=AD-RSPEC-TYPE AD-RSPEC-VERSION
                  Ad RSpec type and version to return, EG 'ProtoGENI 2'

=== The following commands are supported: ===

=== listaggregates ===
 * format: omni.py listaggregates [-a AM_URL]
 * examples:
   omni.py listaggregates
   	   To list all aggregates from the omni_config 'aggregates'
	   option if supplied, else all aggregates listed by the
	   Clearinghouse
   omni.py listaggregates -a http://localhost:8001
   	   To list just the aggregate from the commandline
 
   Print the known aggregates' URN and URL.
   Get the aggregates list from the commandline, or from the
   omni_config 'aggregates' option, or from the Clearinghouse.

==== createslice ====
 * format:  omni.py createslice <slice-name>
 * example: omni.py createslice myslice

  Creates the slice in your chosen control framework.

  Slice name could be a full URN, but is usually just the slice name portion.
  Note that PLC Web UI lists slices as <site name>_<slice name> (EG bbn_myslice), and we want
  only the slice name part here.

  Note that Slice Authorities typically limit this call to privileged users. EG PIs.

  Note also that typical slice lifetimes are short. See RenewSlice.

==== renewslice ====
 * format:  omni.py renewslice <slice-name> <date-time>
 * example: omni.py renewslice myslice 20100928T15:00:00Z

  Renews the slice at your chosen control framework. If your slice
  expires, you will be unable to reserve resources or delete
  reservations at aggregates.

  Slice name could be a full URN, but is usually just the slice name portion.
  Note that PLC Web UI lists slices as <site name>_<slice name> (EG bbn_myslice), and we want
  only the slice name part here.

  The date-time argument takes a standard form
  "YYYYMMDDTHH:MM:SSZ". The date and time are separated by 'T'. The
  trailing 'Z' represents time zone Zulu, which us UTC or GMT. If you
  would like the time to be in local time at the control framework you
  can leave off the trailing 'Z'.


==== deleteslice ====
 * format:  omni.py deleteslice <slice-name> 
 * example: omni.py deleteslice myslice

  Deletes the slice in your chosen control framework.

  Slice name could be a full URN, but is usually just the slice name portion.
  Note that PLC Web UI lists slices as <site name>_<slice name> (EG bbn_myslice), and we want
  only the slice name part here.

  Delete all your slivers first! This does not free up resources at
  various aggregates.

  Note that this is not supported by all control frameworks: some just
  let slices expire.

=== listmyslices ===
 * format: omni.py listmyslices <username>
 * example: omni.py listmyslices jdoe

  List slices registered under the given username. Not supported by all frameworks.

==== getversion ====
 * format:  omni.py getversion [-a AM-URL]
 * examples:
  * omni.py getversion
  * omni.py getversion -a http://localhost:12348

  Call the AM API GetVersion function at each aggregate.

  Aggregates queried:
  - Single URL given in -a argument, if provided, ELSE
  - List of URLs given in omni_config aggregates option, if provided, ELSE
  - List of URNs and URLs provided by the selected clearinghouse

==== listresources ====
 * format:  omni.py listresources [-a AM-URL] [-n] [slice-name] \
   	    	    		      	     [-o  [-p fileprefix]]
 * examples:
  * omni.py listresources
    	    List resources at all AMs on your CH
  * omni.py listresources myslice
    	    List resources in myslices from all AMs on your CH
  * omni.py listresources -a http://localhost:12348 myslice
    	    List resources in myslice at the localhost AM
  * omni.py listresources -a http://localhost:12348 -t ProtoGENI 2 myslice
    	    List resources in myslice at the localhost AM requesting
	    the AM send ProtoGENI V2 format.
  * omni.py listresources -a http://localhost:12348 -n myslice
    	    List resources in myslice at the localhost AM, leaving
	    them in native format
  * omni.py listresources -a http://localhost:12348 -n myslice \
    	    		  -o -p myprefix
  		   
  Call the AM API ListResources function at specified aggregates.

  This command will list the rspecs of all GENI aggregates available
  through your chosen framework, and present them optionally in omnispec form.
  It can save the result to a file so you can edit the result to
  create a reservation RSpec, suitable for use in a call to
  createsliver. EG for omnispecs, set 'allocate' to 'true' to reserve
  the given resource.

  If a slice name is supplied, then resources for that slice only 
  will be displayed.

  If an Aggregate Manager URL is supplied, only resources
  from that AM will be listed.

  If the "-n" flag is used then the native RSpec is returned instead of an
  omnispec. 

  -n gives native format; otherwise print omnispec in json format
     Note: omnispecs are deprecated. Native format is preferred.
  --omnispec request OmniSpec translation. Deprecated
  -o writes to file instead of stdout; omnispec written to 1 file,
     native format written to single file per aggregate.
  -p gives filename prefix for each output file
  -t Requires the AM send RSpecs in the given type and version. If the
     AM does not speak that type and version, nothing is returned. Use
     GetVersion to see available types at that AM.
     Type and version are case-sensitive strings.

  File names will indicate the slice name, file format, and either
  the number of Aggregates represented (omnispecs), or
  which aggregate is represented (native format).
  EG: myprefix-myslice-rspec-localhost-8001.xml

==== createsliver ====
 * format:  omni.py createsliver [-a AM-URL [-n]] <slice-name> <spec file>
 * examples:
  * omni.py createsliver myslice resources.ospec
  * omni.py createsliver -a http://localhost:12348 -n myslice resources.rspec

 The GENI AM API CreateSliver call

 * argument: the spec file should have been created by a call to 
            listresources (e.g. omni.py -o listresources)
            Then, edit the file, eg for an omnispec set "allocate": true, for each
			resource that you want to allocate.

  This command will allocate the requested resources (those marked
  with allocate: true in an omnispec).  It will send an rspec to each
  aggregate manager that a resource is requested for.
  This command can also operate in native mode "-n" by sending a
  native rspec to a single aggregate specified by the "-a" command.
  Omnispecs are deprecated and native format RSpecs are preferred.

  Slice name could be a full URN, but is usually just the slice name portion.
  Note that PLC Web UI lists slices as <site name>_<slice name> (EG bbn_myslice), and we want
  only the slice name part here.

  omni_config users section is used to get a set of SSH keys that should be loaded onto the
  remote node to allow SSH login, if the remote resource and aggregate support this

  Note you likely want to check SliverStatus to ensure your resource comes up.
  And check the sliver expiration time: you may want to call RenewSliver


==== renewsliver ====
 * format:  omni.py renewsliver [-a AM-URL] <slice-name> "<time>"
 * examples:
  * omni.py renewsliver myslice "12/12/10 4:15pm"
  * omni.py renewsliver myslice "12/12/10 16:15"
  * omni.py renewsliver -a http://localhost:12348 myslice "12/12/10 16:15"

  AM API RenewSliver function

  This command will renew your resources at each aggregate up to the
  specified time.  This time must be less than or equal to the time
  available to the slice.  Times are in UTC.

  Slice name could be a full URN, but is usually just the slice name portion.
  Note that PLC Web UI lists slices as <site name>_<slice name> (EG bbn_myslice), and we want
  only the slice name part here.

  Aggregates queried:
  - Single URL given in -a argument, if provided, ELSE
  - List of URLs given in omni_config aggregates option, if provided, ELSE
  - List of URNs and URLs provided by the selected clearinghouse

  Note that the expiration time cannot be past your slice expiration time (see renewslice). Some aggregates will
  not allow you to _shorten_ your sliver expiration time.

==== sliverstatus ====
 * format: omni.py sliverstatus [-a AM-URL] <slice-name>
 * examples:
  * omni.py sliverstatus myslice
  * omni.py sliverstatus -a http://localhost:12348 myslice

  GENI AM API SliverStatus function

  This command will get information from each aggregate about the
  status of the specified slice. This can include expiration time,
  whether the resource is ready for use, and the SFA node login name.

  Slice name could be a full URN, but is usually just the slice name portion.
  Note that PLC Web UI lists slices as <site name>_<slice name> (EG bbn_myslice), and we want
  only the slice name part here.

  Aggregates queried:
  - Single URL given in -a argument, if provided, ELSE
  - List of URLs given in omni_config aggregates option, if provided, ELSE
  - List of URNs and URLs provided by the selected clearinghouse


==== deletesliver ====
 * format:  omni.py deletesliver [-a AM-URL] <slice-name>
 * examples:
  * omni.py deletesliver myslice
  * omni.py deletesliver -a http://localhost:12348 myslice

  GENI AM API DeleteSliver function
  This command will free any resources associated with your slice at
  the given aggregates.

  Slice name could be a full URN, but is usually just the slice name portion.
  Note that PLC Web UI lists slices as <site name>_<slice name> (EG bbn_myslice), and we want
  only the slice name part here.

  Aggregates queried:
  - Single URL given in -a argument, if provided, ELSE
  - List of URLs given in omni_config aggregates option, if provided, ELSE
  - List of URNs and URLs provided by the selected clearinghouse

==== shutdown ====
 * format:  omni.py shutdown [-a AM-URL] <slice-name>
 * examples:
  * omni.py shutdown myslice
  * omni.py shutdown -a http://localhost:12348 myslice

  GENI AM API Shutdown function
  This command will stop the resources from running, but not delete
  their state.  This command should not be needed by most users - it
  is intended for emergency stop and supporitng later forensics /
  debugging. 

  Slice name could be a full URN, but is usually just the slice name portion.
  Note that PLC Web UI lists slices as <site name>_<slice name> (EG bbn_myslice), and we want
  only the slice name part here.

  Aggregates queried:
  - Single URL given in -a argument, if provided, ELSE
  - List of URLs given in omni_config aggregates option, if provided, ELSE
  - List of URNs and URLs provided by the selected clearinghouse

