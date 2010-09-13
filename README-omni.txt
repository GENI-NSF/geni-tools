= The Omni GENI Client =

Omni is an end-user GENI client that communicates with GENI Aggregate
Managers and presents their resources with a uniform specification,
known as the omnispec.  The Omni client can also communicate with
control frameworks in order to create slices, delete slices, and
enumerate available GENI Aggregate Managers.
Note that Omni also supports using control framework native RSpecs.

To configure Omni, please copy src/omni_config or /etc/omni/templates/omni_config 
to your ~/.gcf directory and fill in the parameters for at least one control
framework.  The "omni" section should be filled in with the
certificate and key that you use in your control framework.  Note that keys
for the GCF framework are by default stored in ~/.gcf-servers. Embedded
comments describe the meaning of each field.

The currently supported control frameworks are SFA, PG and GCF. OpenFlow
Aggregate Managers are also supported.

Omni performs the following functions:
 * Talks to each clearinghouse in its native API
 * Contacts Aggregate Managers via the GENI API
 * Converts RSpects into (and from) native RSpec form to  a common 'omnispec'.

== Omnispecs ==
Each OmniResource has a name, a description, a type, booleans
indicating whether the resource is allocated and whether the request
wants to allocate it, and then hashes for options and misc fields.

== Extending Omni ==
Extending Omni to support additional types of Aggregate Managers with
different RSpec formats requires adding a new omnispec/rspec conversion file.

Extending Omni to support additional frameworks with their own
clearinghouse APIs requires adding a new Framework extension class.

== Omni workflow ==
 1. Pick a Clearinghouse you want to use. That is the control framework you
  will use.

 2. Be sure the appropriate section of omni config for your framework 
  (sfa/gcf/pg) has appropriate settings for contacting that Clearinghouse, 
  and user credentials that are valid for that Clearinghouse.

 3. Run omni listresources > avail-resources.omnispec
  a. When you do this, Omni will contact your designated Clearinghouse, using
   your framework-specific user credentials.
  b. The clearinghouse will list the Aggregates it knows about. EG for GCF,
   the am_* entries in gcf_config. For SFA, it will
   return the contents of /etc/sfa/geni_aggregates.xml.
  c. Omni will then contact each of the Aggregates that the Clearinghouse
   told it about, and use the GENI AM API to ask each for its resources. Again, 
   it will use your user credentials. So each Aggregate Manager must  trust the 
   signer of your user credentials, in order for you to talk to it. This is why
   you add the CH certificate to /etc/sfa/trusted_roots or to the -r argument of 
   your GCF gcf-am.py.
  d. Omni will then convert the proprietary RSPecs into a single 'omnispec'.

 4. Save this to a file. You can then edit this file to reserve resources, by changing 
  'allocate: false' to 'allocate: true' wherever the resource is not already allocated 
  ('allocated: true').

 5. Create a Slice.
  Slices are created at your Clearinghouse. Slices are named based on the 
  Clearinghouse authority that signs for them. Using the shorthand (just 
  the name of your slice within PG, for example) allows Omni to ensure 
  your Slice is named correctly. So run: omni.py createslice MyGreatTestSlice

 6. Allocate your Resources
  Given a slice, and your edited omnispec file, you are ready to allocate
  resources by creating slivers at each of the Aggregate Managers.
  Omni will contact your Clearinghouse again, to get the credentials
  for your slice. It will parse your omnispec file, converting it back
  into framework specific RSpec format as necessary.
  It will then contact each Aggregate Manager in your
  omnispec where you are reserving resources, calling the GENI AM API
  CreateSliver call on each. It will supply your Slice Credentials 
  (from the Clearinghouse) plus your own user certificate, and the RSpec.

  At this point, you have resources and can do your experiment.

 7. Renew or Delete
  After a while you may want to Renew your Sliver that is expiring, or 
  Delete it. Omni will contact the Clearinghouse, get a list of all
  Aggregates, and invoke RenewSliver or DeleteSliver on each, for 
  your slice name.

== Running Omni ==

=== The following options are supported: ===

-c FILE -- location of your config file (default ~/.gcf/omni_config)

-f FRAMEWORK -- control framework to use (e.g. my_sfa), overriding default
 in config file.  The framework is a section named in the config file.

--debug -- Enable debug output

=== The following commands are supported: ===

==== createslice ====
 * format:  omni.py createslice <slice-name>
 * example: omni.py createslice myslice

  Creates the slice in your chosen control framework.

  Default GCF certs require a slice named geni.net:gpo:gcf+slice+<name>
  based on the base_name section of gcf_config.  The shorthand notation
  is available for SFA and PG.  Shorthand works if your control framework is GCF
  only if you have configured the 'authority' line in the gcf section of 
  omni_config.

==== deleteslice ====
 * format:  omni.py deleteslice <slice-name> 
 * example: omni.py deleteslice myslice

  Deletes the slice in your chosen control framework

==== getversion ====
 * format:  omni.py getversion [-a AM-URL]
 * examples:
  * omni.py getversion
  * omni.py getversion -a http://localhost:12348

==== listresources ====
 * format:  omni.py listresources [-a AM-URL [-n]] [slice-name]
 * examples:
  * omni.py listresources
  * omni.py listresources myslice
  * omni.py listresources -a http://localhost:12348 myslice
  * omni.py listresources -a http://localhost:12348 -n myslice
  		   
  This command will list the rspecs of all geni aggregates available
  through your chosen framework, and present them in omnispec form.
  Save the result to a file and edit the allocate value to true
  to set up a reservation RSpec, suitable for use in a call to
  createsliver.

  If a slice name is supplied, then resources for that slice only 
  will be displayed.

  If an Aggregate Manager URL is supplied, only resources
  from that AM will be listed.

  If the "-n" flag s used the native RSpec is returned instead of an
  omnispec. The "-n" flag requires the "-a" flag also be used to
  specify an aggregate manager.


==== createsliver ====
 * format:  omni.py createsliver [-a AM-URL [-n]] <slice-name> <spec file>
 * examples:
  * omni.py createsliver myslice resources.ospec
  * omni.py createsliver -a http://localhost:12348 -n myslice resources.rspec

 * argument: the spec file should have been created by a call to 
            listresources (e.g. omni.py listresources > resources.ospec)
            Then, edit the file and set "allocate": true, for each
			resource that you want to allocate.

  This command will allocate the requested resources (those marked
  with allocate: true in the rspec).  It will send an rspec to each
  aggregate manager that a resource is requested for.
  This command can also operate in native mode "-n" by sending a
  native rspec to a single aggregate specified by the "-a" command.

==== deletesliver ====
 * format:  omni.py deletesliver [-a AM-URL] <slice-name>
 * examples:
  * omni.py deletesliver myslice
  * omni.py deletesliver -a http://localhost:12348 myslice

	This command will free any resources associated with your slice.  


==== renewsliver ====
 * format:  omni.py renewsliver [-a AM-URL] <slice-name> "<time>"
 * examples:
  * omni.py renewsliver myslice "12/12/10 4:15pm"
  * omni.py renewsliver myslice "12/12/10 16:15"
  * omni.py renewsliver -a http://localhost:12348 myslice "12/12/10 16:15"

	This command will renew your resources at each aggregate up to the
	specified time.  This time must be less than or equal to the time
	available to the slice.
	Times are in UTC.


==== sliverstatus ====
 * format: omni.py sliverstatus [-a AM-URL] <slice-name>
 * examples:
  * omni.py sliverstatus myslice
  * omni.py sliverstatus -a http://localhost:12348 myslice

	This command will get information from each aggregate about the
	status of the specified slice


==== shutdown ====
 * format:  omni.py shutdown [-a AM-URL] <slice-name>
 * examples:
  * omni.py shutdown myslice
  * omni.py shutdown -a http://localhost:12348 myslice

  This command will stop the resources from running, but not delete
	their state.  This command should not be needed by most users.
