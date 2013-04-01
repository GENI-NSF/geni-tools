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
expect problems. If issues arise, email [mailto:omni-help@geni.net
omni-help@geni.net]. See below for known limitations.

Currently, GENI stitching creates point to point (not multipoint or
broadcast) layer 2 circuits between particular interfaces on
particular compute nodes. Over time, multipoint circuits may be
possible at certain locations in the GENI network.

GENI stitching uses VLANs to create these
circuits. Depending on where you are connecting resources, there may
be very few VLANs available - as few as 1. In this case, your circuit
may fail because other experimenters are using the VLANs. Over time,
more VLANs will become available to GENI.

GENI stitching is enabled at only select aggregates (based on software
capability of the aggregates, or based on provisioning of VLANs). Over
time, this restriction will be lifted.

== Usage ==
stitcher is a simple extension of Omni. Use stitcher just as you would
use Omni. If you try to allocate (using `CreateSliver` or `Allocate`)
resources that include a link that requires stitching, then the new
code will we exercised (otherwise you are just running Omni).

To use stitcher:

 0. Be sure you can run Omni.

 1. Design a topology. Write a standard RSpec. Include 1 more more `<link>`s
 between interfaces on 2 compute nodes. E.G.
{{{
  <link client_id="link-pg-utah1-ig-gpo1">
    <component_manager name="urn:publicid:IDN+emulab.net+authority+cm"/>
    <interface_ref client_id="pg-utah1:if0" />
    <component_manager name="urn:publicid:IDN+instageni.gpolab.bbn.com+authority+cm"/>
    <interface_ref client_id="ig-gpo1:if0" />
  </link>
}}}

 2. Create and renew a slice.

 3. Call stitcher just like Omni, but using `stitcher.py`:
{{{
    $ python ./src/stitcher.py -o createsliver <valid slice name> <path to RSpec>
}}}
(assuming a valid `omni_config` in the usual spots)

 4. Examine the resulting manifest RSpec. Stitcher returns a single
 combined manifest RSpec, covering all the resources just
 reserved. XML comments at the top of the RSpec summarize the
 aggregates at which reservations were made and the circuits reserved.

 5. Use your resources.

 6. Delete your resources when done. Be sure to delete resources from
 all aggregates - including any reservations at transit networks you
 did not specify in your original request RSpec.

=== Notes ===

`createsliver` or `allocate` commands with an RSpec that requires
stitching will be processed by the stitcher code. All other calls will
be passed directly to Omni.

All calls use AM APIv2 (hard-coded) currently, due to aggregate limitations.
Your input request RSpec does ''not'' need a stitching extension, but
should be a single RSpec for all resources that you want in your slice.
To create a request that needs stitching, include at least 1 `<link>` elements with 
more than 1 different `<component_manager>` elements.

The result of stitcher is a single combined manifest RSpec, showing
all resources reserved as a result of this request.

stitcher output is controlled using the same options as Omni,
including `-o` to send RSpecs to files, and `--WARN` to turn down most
logging. Currently, stitcher will write several files to the current
working directory (results from `GetVersion` and `SliverStatus`, plus
several manifest RSpecs).

`./stitcherTestFiles` contains a selection of sample request RSpecs
for use with stitching. Note this is not exhaustive; multiple links
between the same aggregate pairs are possible for example.

=== Options ===
stitcher is a simple extension of Omni. As such, it uses all the same
options as Omni. stitcher however adds several options:
 - `--excludehop <hop URN>`: When supplied, the Stitching Computation
 Service will exclude the specified switch/port from ANY computed
 stitching paths. You can supply this argument many times.
 - `--includehop <hop URN>`: When supplied, the Stitching Computation
 Service will insist on including the specified switch/port on ANY computed
 stitching paths. You can supply this argument many times. Use this
 with caution, particularly if your request has multiple `<link>`s.

Together, the above options should allow you some control over the
paths used for your circuits, without requiring that you construct the
full RSpec stitching extension yourself.

Other options you should not need to use:
 - `--fakeModeDir <directory>`: When supplied, does not make any
 actual reservations at aggregates. For testing only.
 - `--scsURL <url>`: URL at which the Stitching Computation Service
 runs. Use the default.

== Tips and Details ==
 - Create a single request RSpec for all aggregates you want linked
 - Include the necessary 2 `<component_manager>` elements for the 2 different AMs in the `<link>`
 - Stitching currently only works at Utah InstaGENI, GPO InstaGENI,
 Kentucky ProtoGENI, and Utah ProtoGENI
  - And currently, Utah InstaGENI can only stitch to Utah ProtoGENI 
 - Use "src/stitcher.py" instead of "src/omni.py"
 - This script can take a while - it must make reservations at all the
 aggregates, and keep retrying at aggregates that can't provide
 matching VLAN tags. Be patient.
 - When the script completes, you will have reservations at each of the
 aggregates mentioned in your request RSpec, plus any intermediate
 aggregates required to complete your circuit (e.g. ION) - or none, if
 your request failed.
 - The script return is a single manifest RSpec for all the aggregates where you
 have reservations for this request.
 - Stitcher will retry when something goes wrong, up to a point. If
 the failure is isolated to a single aggregate failing to find a VLAN,
 stitcher retries at just that aggregate (currently up to 50
 times). If the problem is larger, stitcher will go back to the
 Stitching Computation Service for a new path recommendation (possibly
 excluding a failed hop or a set of failed VLAN tags). Stitcher will
 retry that up to 5 times. After that or on other kinds of errors,
 stitcher will delete any existing reservations and exit.

=== Stitching Computation Service ===

For stitching, the request RSpec must specify the exact switches and
ports to use to connect each aggregate. However, experimenters do not
need to do this themselves. Instead, there is a Stitching Computation
Service (SCS) which will fill in these details, including any transit
networks at which you need a reservation (like ION). For details in
this service, see
http://geni.maxgigapop.net/twiki/bin/view/GENI/NetworkStitchingAPI

Experimenters can of course specify this information themselves, using
the stitching extension
(http://hpn.east.isi.edu/rspec/ext/stitch/0.1/stitch-schema.xsd). 

The Stitching Computation Service (SCS), also provides hints to the
stitcher script on the order in which to make reservations at the
various aggregates.

=== ION Aggregate ===

Many connections will cross Internet2's ION network. To support this,
Internet2 currently operates a ''prototype'' GENI aggregate over
ION. This aggregate accepts calls using the GENI Aggregate Manager
API, and translates those into calls to OSCARS (ION).

== Troubleshooting ==

Stitching is new to GENI, and uses several prototype services (this
client, the Stitching Computation Service, the ION aggregate, as well
as stitching implementations at aggregates). Therefore, bugs and rough
edges are expected. Please note failure conditions, expect occasional
failures, and report any apparent bugs to omni-help@geni.net

Expected failure conditions include:
 - No path exists between specified endpoints
 - No VLAN tags available at one of the aggregates

As with Omni errors, when reporting problems please include as much
detail as possible:
 - `python src/omni.py --version`
 - The exact commandline you used to invoke stitcher
 - The request RSpec you used with stitcher
 - The last few lines of your call to stitcher - all the logs if
 possible
 - The resulting manifest RSpec if the script succeeded

== Known Issues and Limitations ==
 - Aggregate support is limited. Available aggregates as of 3/2013:
  - Utah InstaGENI
  - GPO InstaGENI
  - Kentucky ProtoGENI
  - Utah ProtoGENI
 - Links are point to point only - each link connects an interface on
 a compute node to another interface on a node.
 - Links between aggregates use VLANs. QinQ is not supported at any
 current aggregates, and VLAN translation support is limited. VLAN
 tags available at each aggregate are limited, and may run out.
 - AM API v3 is not supported - VLAN tag selection is not optimal
 - Aggregates do not support `Update`, so you cannot add a link to
 an existing reservation.
 - Fatal errors are not recognized, so the script keeps trying longer
 than it should.
 - The ION aggregate (across Internet2) does not support
 `RenewSliver`, but instead allocates resources until the slice
 expiration. Be sure to renew your slice to the desired expiration
 time before allocating resources.

== To Do items ==
 - Thread all calls to omni
 - Support AM API v3
 - Consolidate constants
 - Fully handle a VLAN_UNAVAILABLE error from an AM
 - Fully handle negotiating among AMs for a VLAN tag to use
    As in when the returned suggestedVLANRange is not what was requested
 - fakeMode is incomplete
 - Tune counters, sleep durations, etc
 - Return a struct with detailed results (not just comments in manifest)
 - Return a struct on errors
 - Get AM URLs from the Clearinghouse
 - Use Authentication with the SCS
 - Support Stitching schema v2
 - Time out omni calls in case an AM hangs
 - opts.warn is used to suppress omni output. Clean that up. A scriptMode option?
 - Implement confirmSafeRequest to ensure no dangerous requests are made
 - Expand to additional aggregates
 - Support multipoint circuits
 - Support GRE tunnels

== Related Reading ==
 - [http://geni.maxgigapop.net/twiki/bin/view/GENI/NetworkStitchingOverview MAX Stitching Architecture and Stitching Service pages]
- [http://groups.geni.net/geni/wiki/GeniNetworkStitching GENI Network Stitching Design Page]

