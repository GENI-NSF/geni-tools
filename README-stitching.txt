{{{
#!comment

N.B. This page is formatted for a Trac Wiki.
}}}

[[PageOutline]]

= The Omni GENI Experimenter-Defined Cross-Aggregate Topologies Client =

'''stitcher''' is an Omni based script for instantiating experimenter
defined topologies that cross multiple aggregates, aka 'network
stitching' or just 'stitching'. Experimenters specify their desired
network topology, and this client expands that request using the
"Stitching Computation Service", and then attempts to reserve the
necessary resources at each aggregate involved in the topology.

'''Note''': This is new functionality, relying on several prototype services;
expect problems. If issues arise, email [mailto:omni-help@geni.net omni-help@geni.net]. 
See below for known limitations.

Currently, GENI stitching creates point to point (not multipoint or
broadcast) layer 2 circuits between particular interfaces on
particular compute nodes. Over time, multipoint circuits may be
possible at certain locations in the GENI network.

GENI stitching uses VLANs to create these circuits. Depending on where
you are connecting resources, there may be very few VLANs available -
as few as 1. In this case, your circuit may fail because other
experimenters are using the VLANs. Over time, more VLANs will become
available to GENI.

GENI stitching is enabled at only select aggregates (based on software
capability of the aggregates, or based on provisioning of VLANs). Over
time, this restriction will be lifted.

== Usage ==
stitcher is a simple extension of Omni. Use stitcher just as you would
use Omni. If you try to allocate (using `CreateSliver` or `Allocate`)
resources that include a link that requires stitching, then the new
code will be exercised (otherwise you are just running Omni).

To use stitcher:

 1. Be sure you can run Omni.

 2. Design a topology. Write a standard GENI v3 RSpec. Include 1 or more `<link>`s
 between interfaces on 2 compute nodes. E.G.
{{{
#!xml
  <link client_id="link-pg-utah1-ig-gpo1">
    <component_manager name="urn:publicid:IDN+emulab.net+authority+cm"/>
    <interface_ref client_id="pg-utah1:if0" />
    <component_manager name="urn:publicid:IDN+instageni.gpolab.bbn.com+authority+cm"/>
    <interface_ref client_id="ig-gpo1:if0" />
  </link>
}}}

 3. Create and renew a slice.

 4. Call stitcher just like Omni, but using `stitcher.py`:
{{{
    $ python ./src/stitcher.py -o createsliver <valid slice name> <path to RSpec>
}}}
(assuming a valid `omni_config` in one of the usual spots)

 5. Stitcher will make allocations at ALL aggregates required for your
 topology. (It ignores the `-a` option.) This may take a while.

 6. Examine the resulting manifest RSpec. Stitcher returns a single
 combined manifest RSpec, covering all the resources just
 reserved. XML comments at the top of the RSpec summarize the
 aggregates at which reservations were made and the circuits reserved.

 7. Use your resources.

 8. Delete your resources when done. Be sure to delete resources from
 all aggregates - including any reservations at transit networks you
 did not specify in your original request RSpec. If you use
 `stitcher.py` to delete your resources and supply no `-a` argument,
 `stitcher` will delete from all aggregates at which it reserved
 resources. If you use `omni`, you must specify which aggregates to invoke. 
For example, to fully delete your reservation:
{{{
    $ python ./src/stitcher.py deletesliver <valid slice name>
}}}
To delete from only 1 aggregate:
{{{
    $ python ./src/stitcher.py -a <URL> deletesliver <valid slice name>
}}}


=== Notes ===

`createsliver` or `allocate` commands with an RSpec that requires
stitching will be processed by the stitcher code. All other calls will
be passed directly to Omni.

The same request RSpec will be submitted to every aggregate required
for your topology. Stitcher will create reservations at each of these
aggregates for you. NOTE however that in general stitcher only knows how to
contact aggregates that are involved in the circuits you request -
nodes you are trying to reserve in the RSpec that are not linked with
a stitching link may not be reserved, because stitcher may not know
the URL to contact that aggregate. If there is an aggregate nickname
for the component manager URN in your RSpec with a matching URL,
stitcher should find it.

All calls use AM APIv2 (hard-coded) currently, due to aggregate
limitations. If an aggregate does not speak AM API v2, `stitcher`
exits.

Your input request RSpec does ''not'' need a stitching extension, but
should be a single RSpec for all resources that you want in your slice.
To create a request that needs stitching, include at least 1 `<link>` elements with 
more than 1 different `<component_manager>` elements (and no
`<shared_vlan>` element and no `<link_type>` element of other than `VLAN`).

The result of stitcher is a single combined GENI v3 manifest RSpec, showing
all resources reserved as a result of this request.

stitcher output is controlled using the same options as Omni,
including `-o` to send RSpecs to files, and `--WARN` to turn down most
logging. However, stitcher always saves your combined result manifest
RSpec to a file (named
'<slicename>-manifest-rspec-stitching-combined.xml'), unless you specify the `--tostdout` option.
Currently, stitcher will write several files to the current
working directory (results from `GetVersion` and `SliverStatus`, plus
several manifest RSpecs).

`./stitcherTestFiles` contains a selection of sample request RSpecs
for use with stitching. Note this is not exhaustive; multiple links
between the same aggregate pairs are possible for example.

When complete, `stitcher` writes a file to your current working
directory, listing the aggregates at which it made reservations. This
file is used by `stitcher` later to drive calls, e.g. to `sliverstatus` or
`renewsliver` or `deletesliver`. This file is named something like
`slice.hrn-amlist.txt`.

When done, be sure to delete your reservations, at ''all''
aggregates involved in your reservation. `stitcher` remembers the
aggregates at which it made reservations (see above), so this is easy
to do using:
{{{
    $ python ./src/stitcher.py deletesliver <valid slice name>
}}}
Note that stitcher will not delete reservations at other aggregates
not involved in stitching. To partially delete your reservation or
delete at these other aggregates, supply the necessary `-a` options.

Be sure to see the Known Issues section below.

=== Options ===
stitcher is a simple extension of Omni. As such, it uses all the same
options as Omni. `stitcher` however adds several options:
 - `--excludehop <hop URN>`: When supplied, the Stitching Computation
 Service will exclude the specified switch/port from ANY computed
 stitching paths. You can supply this argument many times.
  - Alternately, you can exclude only certain VLAN tags from being
  used at a particular hop, by appending `=<VLAN range>` to the hop
  URN. For example `--excludehop urn:publicid:IDN+instageni.gpolab.bbn.com+interface+procurve2:5.24=3747-3748`
 - `--includehop <hop URN>`: When supplied, the Stitching Computation
 Service will insist on including the specified switch/port on ANY computed
 stitching paths. You can supply this argument many times. Use this
 with caution, particularly if your request has multiple `<link>`s.

Together, the above options should allow you some control over the
paths used for your circuits, without requiring that you construct the
full RSpec stitching extension yourself.

Additionally, these options are used for some topologies:
 - `--fixedEndpoint`: Use this if you want a dynamic circuit that ends
 not at a node, but at a switch (E.G. because you have a static VLAN to a
 fixed non-AM controlled host from there.). This option adds a fake
 node and interface_ref to the link. Note that your request RSpec will
 still need >= 2 `component_manager`s on the `<link>`, and you will need a
 skeletal stitching extension with 1 hop being the switch/VLAN where
 you want to end, and a 2nd being the AM where you want to end up.
 - `--noExoSM`: Avoid using the ExoGENI ExoSM. If an aggregate is an
 ExoGENI aggregate and the URL we get is the ExoSM URL, then try to
 instead use the local rack URL, and therefore only local rack
 allocated VMs and VLANs. For this to work, your `omni_config` or the
 base aggregate nicknames must have an entry for the local ExoGENI
 rack that specifies both the aggregate URN as well as the URL, EG:
{{{
eg-bbn=urn:publicid:IDN+exogeni.net:bbnvmsite+authority+am,https://bbn-hn.exogeni.net:11443/orca/xmlrpc
eg-renci=urn:publicid:IDN+exogeni.net:rencivmsite+authority+am,https://rci-hn.exogeni.net:11443/orca/xmlrpc
eg-fiu=urn:publicid:IDN+exogeni.net:fiuvmsite+authority+am,https://fiu-hn.exogeni.net:11443/orca/xmlrpc
}}}
 - `--useExoSM`: Try to use the ExoGENI ExoSM for ExoGENI
 reservations. If we get an individual ExoGENI rack URL for an
 aggregate, then try to use the ExoSM URL. For this to work, your
 `omni_config`  or the base aggregate nicknames must have an entry for
 the ExoGENI rack that specifies the URN and URL, as well as an entry
 for the ExoSM.

Other options you should not need to use:
 - `--fakeModeDir <directory>`: When supplied, does not make any
 actual reservations at aggregates. For testing only.
 - `--scsURL <url>`: URL at which the Stitching Computation Service
 runs. Use the default.
 - `--ionRetryIntervalSecs <# seconds>`: # of seconds to sleep between
 reservation attempts at ION or another DCN based aggregate. Default
 is 600 (10 minutes), to allow routers to reset.
 - `--ionStatusIntervalSecs <# seconds>`: # of seconds to sleep between
 sliverstatus calls at ION or another DCN based aggregate. Default
 is 30 (seconds).

== Tips and Details ==
 - Create a single GENI v3 request RSpec for all aggregates you want linked
 - Include the necessary 2 `<component_manager>` elements for the 2 different AMs in each `<link>`
 - Stitching currently only works at a few aggregates, with more being
 added regularly. Contact help@geni.net for a current list.
 - Use "src/stitcher.py" instead of "src/omni.py"
 - This script can take a while - it must make reservations at all the
 aggregates, and keeps retrying at aggregates that can't provide
 matching VLAN tags. Be patient.
 - When the script completes, you will have reservations at each of the
 aggregates involved in stitched links in your request RSpec, plus any intermediate
 aggregates required to complete your circuit (e.g. ION) - or none, if
 your request failed.
 - Stitcher sends the same request RSpec to all aggregates involved in
 your request.
 - Stitcher makes reservations at ''all'' aggregates involved in your
 stitching circuits. Note however that stitcher generally only knows how to
 contact aggregates that are involved in the circuits you request -
 nodes you are trying to reserve in the RSpec that are not linked with
 a stitching link may not be reserved, because stitcher may not know
 the URL to contact that aggregate. If there is an aggregate nickname
 for the component manager URN in your RSpec with a matching URL,
 stitcher should find it.
 - The script return is a single GENI v3 manifest RSpec for all the aggregates
 where you have reservations for this request, saved to a file named
 '<slicename>-manifest-rspec-stitching-combined.xml'
 - Stitcher will retry when something goes wrong, up to a point. If
 the failure is isolated to a single aggregate failing to find a VLAN,
 stitcher retries at just that aggregate (currently up to 50
 times). If the problem is larger, stitcher will go back to the
 Stitching Computation Service for a new path recommendation (possibly
 excluding a failed hop or a set of failed VLAN tags). Stitcher will
 retry that up to 5 times. After that or on other kinds of errors,
 stitcher will delete any existing reservations and exit.
 - Stitcher remembers the aggregates where it made reservations. If
 you use `stitcher.py` for later `renewsliver` or `sliverstatus` or
 `deletesliver` or other calls, stitcher will invoke the command at
 all the right aggregates.
 - If you want to check what aggregates are stitchable, you can view
 the [http://groups.geni.net/geni/wiki/GeniNetworkStitchingSites GENI stitching sites list online], or programmatically.
 You should only try to stitch among aggregates listed here - all
 other requests will fail.
 To check programmatically:
{{{
cd <omni install directory>
export PYTHONPATH=$PYTHONPATH:.
python src/omnilib/stitch/scs.py --listaggregates
}}}
 - Be sure to see the list of Known Issues below.

=== Stitching Computation Service ===

For stitching, the request RSpec must specify the exact switches and
ports to use to connect each aggregate. However, experimenters do not
need to do this themselves. Instead, there is a Stitching Computation
Service (SCS) which will fill in these details, including any transit
networks at which you need a reservation (like ION). For details on
this service, see the
[https://wiki.maxgigapop.net/twiki/bin/view/GENI/NetworkStitchingAPI MAX SCS wiki page].

Experimenters can of course specify this information themselves, using
[http://hpn.east.isi.edu/rspec/ext/stitch/0.1/stitch-schema.xsd the stitching extension]. 

The Stitching Computation Service (SCS), also provides hints to the
stitcher script on the order in which to make reservations at the
various aggregates.

Known issues with this service can be found on the
[http://groups.geni.net/geni/query?status=new&status=assigned&status=reopened&component=MAXSCS GENI Trac]

=== ION Aggregate ===

Many connections will cross Internet2's ION network. To support this,
Internet2 currently operates a ''prototype'' GENI aggregate over
ION. This aggregate accepts calls using the GENI Aggregate Manager
API, and translates those into calls to OSCARS (ION).

This same software runs other aggregates for OSCARS networks,
specifically the MAX aggregate.

Known issues with this aggregate can be found on the
[http://groups.geni.net/geni/query?status=new&status=assigned&status=reopened&component=I2AM GENI Trac]

== Troubleshooting ==

Stitching is relatively new to GENI, and uses several prototype services (this
client, the Stitching Computation Service, the ION aggregate, as well
as stitching implementations at aggregates). Therefore, bugs and rough
edges are expected. Please note failure conditions, expect occasional
failures, and report any apparent bugs to [mailto:omni-help@geni.net omni-help@geni.net].

As with Omni errors, when reporting problems please include as much
detail as possible:
 - `python src/omni.py --version`
 - The exact commandline you used to invoke stitcher
 - The request RSpec you used with stitcher
 - At least the last few lines of your call to stitcher, and all the logs if
 possible
 - The resulting manifest RSpec if the script succeeded
 - Listing of new rspec files created in `/tmp` and your current
 working directory

Some sample error messages and their meaning:
 - `StitchingServiceFailedError: Error from Stitching Service: code 3: MxTCE ComputeWorker return error message ' Action_ProcessRequestTopology_MP2P::Finish() Cannot find the set of paths for the RequestTopology. '.`
  - Errors like this mean there is no GENI layer 2 path possible
    between your specified endpoints. Did you specify an `excludehop`
    or `includehop` you shouldn't have? Follow the set of supported
    aggregates (below)? Alternatively, it may mean that `stitcher`
    tried all available VLAN tags for one of your aggregates, and got
    a stitching failure on each - probably because that tag was not available.

See the list of Known Issues below.

== Known Issues and Limitations ==
 - Aggregate support is limited. See http://groups.geni.net/geni/wiki/GeniNetworkStitchingSites
 - Links are point to point only - each link connects an interface on
 a compute node to another interface on a node.
 - Links between aggregates use VLANs. QinQ is not supported at any
 current aggregates, and VLAN translation support is limited. VLAN
 tags available at each aggregate are limited, and may run out.
 - If your circuit goes across ProtoGENI Utah (nickname `pg-utah`) to
 `ig-utah` or `utah-ddc`, then you will need to explicitly set the
 MTU on your link in order to exchange TCP traffic. Otherwise, while
 `ping` will work, most other traffic will not pass. 
  - Workaround: After reserving your circuit, log in to each of your nodes and
  change the MTU to 1496 on your data plane interface.
   - For example, `sudo /sbin/ifconfig eth1 mtu 1496`
  - This is a known issue: http://groups.geni.net/geni/ticket/1086
 - Stitching to ExoGENI is limited:
  - Stitching within ExoGENI, by submitting a request to the ExoSM
  with only ExoGENI resources, works fine.
  - Stitching between ExoGENI and non ExoGENI resources only works at
  a very few ExoGENI sites currently.
  - You can have only 1 stitched link per ExoGENI node (though you can
  have multiple nodes).
   - See http://groups.geni.net/exogeni/ticket/193
  - You cannot stitch to ExoGENI 'bare metal' nodes; stitching only
  works at ExoGENI VMs.
   - See http://groups.geni.net/exogeni/ticket/195
  - Due to limitations in the `stitcher` tool, you cannot reserve some
  ExoGENI resources from the ExoSM, and some from an individual
  ExoGENI rack. You must either use all ExoSM resources, or all
  resources at an individual rack. See options `--useExoSM` and `--noExoSM`
 - AM API v3 is not supported - VLAN tag selection is not optimal
 - AM API v1 only aggregates are not supported
 - Aggregates do not support `Update`, so you cannot add a link to
 an existing reservation.
 - Some fatal errors at aggregates are not recognized, so the script keeps trying longer
 than it should.

== To Do items ==
 - Handle known ExoGENI error messages - particularly those that are fatal, and
 those that mean the VLAN failed and we should retry with a different tag
 - With ExoGENI AMs: After reservation, loop checking sliverstatus for
 success or failure, then get the manifest after that
 - Thread all calls to omni
 - Add Aggregate specific top level RSpec elements in combined manifest
 - Support AM API v3
 - Consolidate constants
 - Fully handle a `VLAN_UNAVAILABLE` error from an AM
 - Fully handle negotiating among AMs for a VLAN tag to use
  - As in when the returned `suggestedVLANRange` is not what was requested
 - `fakeMode` is incomplete
 - Tune counters, sleep durations, etc
 - Return a struct with detailed results (not just comments in manifest)
 - Return a struct on errors
 - Use authentication with the SCS
 - Support stitching schema v2
 - `opts.warn` is used to suppress omni output. Clean that up. A `scriptMode` option?
 - Implement `confirmSafeRequest()` to ensure no dangerous requests are made
 - Expand to additional aggregates
 - Support multipoint circuits
 - Support GRE tunnels or other stitching technologies

== Related Reading ==
 - [http://groups.geni.net/geni/wiki/GeniNetworkStitchingSites GENI Stitching Sites]
 - [https://wiki.maxgigapop.net/twiki/bin/view/GENI/NetworkStitchingOverview MAX Stitching Architecture and Stitching Service pages]
 - [http://groups.geni.net/geni/wiki/GeniNetworkStitching GENI Network Stitching Design Page]

