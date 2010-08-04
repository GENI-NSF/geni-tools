The Omni GENI Client -

Omni is an end-user GENI client that communicates with GENI Aggregate
Managers and presents their resources with a uniform specification,
known as the omnispec.  The Omni client can also communicate with
control frameworks in order to create slices, delete slices, and
enumerate available GENI Aggregate Managers.

To configure Omni, please copy the src/omni_config file to your ~/.omni
directory and fill in the parameters for at least one control
framework.  The "omni" section should be filled in with the
certificate and key that you use in your control framework. Embedded
comments describe the meaning of each field.

The currently supported control frameworks are SFA, PG and GCF. OpenFlow
Aggregate Managers are also supported.

Omni works by 
- The Framework classes know the API for each clearinghouse
- Aggregate Managers are contacted via the GENI API
- RSpecs are converted to a very simple common 'omnispec'
format. Users (hand) edit these and supply these to createsliver calls.

Each OmniResource has a name, a description, a type, booleans
indicating whether the resource is allocated and whether the request
wants to allocate it, and then hashes for options and misc fields.

Extending Omni to support additional types of Aggregate Managers with
different RSpec formats requires adding a new omnispec/rspec conversion file.

Extending Omni to support additional frameworks with their own
clearinghouse APIs requires adding a new Framework extension class.

Omni workflow
=============
- Pick a Clearinghouse you want to use. That is the control framework you
 will use.

- Be sure the appropriate section of omni config for your framework 
(sfa/gcf/pg) has appropriate settings for contacting that Clearinghouse, 
and user credentials that are valid for that Clearinghouse.

- Run omni listresources > avail-resources.omnispec
a) When you do this, Omni will contact your designated Clearinghouse, using 
your framework-specific user credentials.
b) The clearinghouse will list the Aggregates it knows about.
EG for GCF, the contents of geni_aggregates. For SFA, it will return the
contents of /etc/sfa/geni_aggregates.xml.
c) Omni will then contact each of the Aggregates that the Clearinghouse told
it about, and use the GENI AM API to ask each for its resources.
Again, it will use your user credentials. So each Aggregate Manager must 
trust the signer of your user credentials, in order for you to talk
to it. This is why you add the CH certificate to /etc/sfa/trusted_roots or to
the -r argument of your GCF gam.py.
d) Omni will then convert the proprietary RSPecs into a single 'omnispec'.

- Save this to a file. You can then edit this file to reserve resources, 
by changing 'allocate: false' to 'allocate: true' wherever the resource
is not already allocated ('allocated: true').

- Create a Slice.
Slices are created at your Clearinghouse. Slices are named based on
the Clearinghouse authority that signs for them. Using the shorthand
(just the name of your slice within PG, for example) allows Omni to
ensure your Slice is named correctly. So run:
omni.py createslice MyGreatTestSlice

- Allocate your Resources
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

- Renew or Delete
After a while you may want to Renew your Sliver that is expiring, or 
Delete it. Omni will contact the Clearinghouse, get a list of all
Aggregates, and invoke RenewSliver or DeleteSliver on each, for 
your slice name.

Running Omni -

== The following options are supported: ==

-c FILE -- location of your config file (default ~/.omni/omni_config)

-f FRAMEWORK -- control framework to use (e.g. my_sfa), overiding default
 in config file.  The framework is a section named in the config file.

--debug -- Enable debug output

== The following commands are supported: ==

** createslice
- format:  omni.py createslice <slice name>
- example: omni.py createslice <plc:gpo:site+slice+foobar> 
           Shorthand notation is also available (e.g., 'foobar')

  Creates the slice in your chosen control framework.

  Default GCF certs require a slice named geni.net:gpo:gcf+slice+<name>
  based on the CERT_AUTHORITY constant in gen-certs.py.  The shorthand notation
  is available for SFA and PG.  Shorthand works if your control framework is GCF
  only if you have configured the 'authority' line in the gcf section of 
  omni_config. (also see ch.py SLICEPUBID_PREFIX)


** deleteslice
- format:  omni.py deleteslice <slice urn> 
- example: omni.py deleteslice <plc:gpo:site+slice+foobar>
           Shorthand notation is also available (e.g., 'foobar')

  Deletes the slice in your chosen control framework


** listresources
- format:  omni.py listresources <optional slice urn> <optional AM URL 1> <AM URL 2> ... <AM URL n>
- example: omni.py listresources
		   omni.py listresources plc:gpo:site+slice+foobar
  		   omni.py listresources foobar http://localhost:12348
  		   omni.py listresources http://localhost:12348 http://myplc4.gpolab.bbn.com:12348
  		   
  This command will list the rspecs of all geni aggregates available
  through your chosen framework, and present them in omnispec form.
  Save the result to a file and edit the allocate value to true
  to set up a reservation RSpec, suitable for use in a call to
  createsliver.
  If a slice urn is supplied, then resources for that slice only 
  will be displayed.



** createsliver
- format:  omni.py createsliver <slice urn> <omnispec file>
- example: omni.py createsliver plc:gpo:site+slice+foobar ospec
           Shorthand notation is also available (e.g., 'foobar')

- argument: the omnispec file should have been created by a call to 
            listresources (e.g. omni.py listresources > ospec)
            Then, edit the file and set "allocate": true, for each
			resource that you want to allocate.

  This command will allocate the requested resources (those marked
  with allocate: true in the rspec).  It will send an rspec to each
  aggregate manager that a resource is requested for.



** deletesliver
- format:  omni.py deletesliver <slice urn>
- example: omni.py deletesliver plc:gpo:site+slice+foobar
           Shorthand notation is also available (e.g., 'foobar')

	This command will free any resources associated with your slice.  



** renewsliver
- format:  omni.py renewsliver <slice urn> "<time>"
- example: omni.py renewsliver plc:gpo:site+slice+foobar "12/12/10 4:15pm"
- example: omni.py renewsliver plc:gpo:site+slice+foobar "12/12/10 16:15"
           Shorthand notation is also available (e.g., 'foobar')

	This command will renew your resources at each aggregate up to the
	specified time.  This time must be less than or equal to the time
	available to the slice.



** sliverstatus
- format: omni.py sliverstatus <slice urn>
- example: omni.py sliverstatus plc:gpo:site+slice+foobar
           Shorthand notation is also available (e.g., 'foobar')


	This command will get information from each aggregate about the
	status of the specified slice



** shutdown
- format:  omni.py shutdown <slice urn> 
- example: omni.py shutdown plc:gpo:site+slice+foobar
           Shorthand notation is also available (e.g., 'foobar')

  This command will stop the resources from running, but not delete
	their state.  This command should not be needed by most users.
