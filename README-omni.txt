The Omni GENI Client -

Omni is an end-user GENI client that communicates with GENI Aggregate
Managers and presents their resources with a uniform specification,
known as the omnispec.  The Omni client can also communicate with
control frameworks in order to create slices, delete slices, and
enumerate available GENI Aggregate Managers.

To configure Omni, please copy the src/omni_config file to your ~/.omni
directory and fill in the parameters for at least one control
framework.  The "omni" section should be filled in with the
certificate and key that you use in your control framework.

See src/documented_omni_config_dont_use for commentary explaining how to
customize your omni_config file.

The currently supported control frameworks are SFA, PG and GCF.

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


Running Omni -

== The following options are supported: ==

-c FILE -- location of your config file (default ~/.omni/omni_config)

-f FRAMEWORK -- control framework to use (e.g. sfa), overiding default
 in config file

--debug -- Enable debug output

== The following commands are supported: ==

** createslice
- format:  omni.py createslice <slice urn>
- example: omni.py createslice <plc:gpo:site+slice+foobar>

  Creates the slice in your chosen control framework.

  Default GCF certs require a slice named geni.net:gpo:gcf+slice+<name>
  based on the GCF_CERT_PREFIX constant in init-ca.py


** deleteslice
- format:  omni.py deleteslice <slice urn>
- example: omni.py deleteslice <plc:gpo:site+slice+foobar>

  Deletes the slice in your chosen control framework


** listresources
- format:  omni.py listresources <optional slice urn>
- example: omni.py listresources <plc:gpo:site+slice+foobar>

  This command will list the rspecs of all geni aggregates available
  through your chosen framework, and present them in omnispec form.
  If a slice urn is supplied, then resources for that slice will be
  displayed.


** createsliver
- format:  omni.py createsliver <slice urn> <omnispec file>
- example: omni.py createsliver plc:gpo:site+slice+foobar ospec
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

	This command will free any resources associated with your slice.  



** renewsliver
- format:  omni.py renewsliver <slice urn> "<time>"
- example: omni.py renewsliver plc:gpo:site+slice+foobar "12/12/10 4:15pm"
- example: omni.py renewsliver plc:gpo:site+slice+foobar "12/12/10 16:15"

	This command will renew your resources at each aggregate up to the
	specified time.  This time must be less than or equal to the time
	available to the slice.



** sliverstatus
- format: omni.py sliverstatus <slice urn>
- example: omni.py sliverstatus plc:gpo:site+slice+foobar

	This command will get information from each aggregate about the
	status of the specified slice



** shutdown
- format:  omni.py shutdown <slice urn> 
- example: omni.py shutdown plc:gpo:site+slice+foobar

  This command will stop the resources from running, but not delete
	their state.  This command should not be needed by most users.
