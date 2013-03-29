{{{
#!comment

N.B. This page is formatted for a Trac Wiki.
}}}

[[PageOutline]]

= The Omni GENI Experimenter Defined Cross Aggregate Topologies (aka 'stitching') Client =
'''stitcher''' is an Omni based script for instantiating experimenter
defined topologies that cross multiple aggregates, aka 'network
stitching' or just 'stitching'. This script extends Omni.
This is new functionality, relying on several prototype services;
expect problems. If issues arise, email omni-help@geni.net.

Currently, GENI stitching creates point to point (not multipoint or
broadcast) layer 2 circuits between particular interfaces on
particular compute nodes. Over time, multipoint circuits may be
possible at certain locations in the GENI network.

GENI stitching uses VLANs to create these
circuits. Depending on where you are connecting resources, there may
be very few VLANs available - as few as 1. In this case, your circuit
may fail because another experimenter is using the VLAN. Over time,
more VLANs will become available.

GENI stitching is enabled at only select aggregates (based on software
capability of the aggregates, or based on provisioning of VLANs). Over
time, this restriction will be lifted.

== Usage ==
Call stitcher just like omni:
{{{
    $ python ./src/stitcher.py -o createsliver <valid slice name> <path to RSpec file>
}}}
(assuming a valid `omni_config` in the usual spots)
`createsliver` or `allocate` commands with an RSpec that requires stitching will be processed 
by the stitcher code. All other calls will be passed directly to Omni.
All calls use AM APIv2 (hard-coded) currently, due to aggregate limitations.
Your input request RSpec does ''not'' need a stitching extension, but
should be a single RSpec for all resources that you want in your slice.
To create a request that needs stitching, include at least 1 <link> elements with 
more than 1 different <component_manager> elements.

== Key points ==
 - Create a single request RSpec for all aggregates you want linked
 - Include the necessary 2 component_manager elements for the 2 different AMs in the <link>
 - Stitching currently only works at Utah InstaGENI, GPO InstaGENI,
 Kentucky ProtoGENI, and Utah ProtoGENI
  - And currently, Utah InstaGENI can only stitch to Utah ProtoGENI 
 - Use "src/stitcher.py" instead of "src/omni.py"
 - It can take a while
 - When the script completes, you will have reservations at each of the
 aggregates mentioned in your request RSpec, plus any intermediate
 aggregates rqeuired to complete your circuit (e.g. ION) - or none, if
 your request failed.
 - Return is a single manifest RSpec for all the aggregates where you
 have reservations for this request.

== Known Issues ==
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
