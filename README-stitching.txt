{{{
#!comment

N.B. This page is formatted for a Trac Wiki.
}}}

[[PageOutline]]

= Stitcher: The Omni GENI Experimenter-Defined Cross-Aggregate Topologies Client =

'''stitcher''' is an Omni based script for instantiating multi
aggregate topologies, including in particular experimenter
defined topologies that cross multiple aggregates, aka 'network
stitching' or just 'stitching'. Experimenters specify their desired
network topology, and this client expands that request using the
"Stitching Computation Service", and then attempts to reserve the
necessary resources at each aggregate involved in the topology.

'''Note''': This is complex functionality, relying on multiple services;
expect problems. If issues arise, report them on the
[https://groups.google.com/forum/#!forum/geni-users GENI Users mailing list].
See below for known limitations.

Currently, GENI stitching creates point to point (not multipoint or
broadcast) layer 2 circuits between particular interfaces on
particular compute nodes. Over time, multipoint circuits may be
possible at certain locations in the GENI network.

GENI stitching uses VLANs to create these circuits. Depending on where
you are connecting resources, there may be very few VLANs
available. In this case, your circuit may fail because other 
experimenters are using the VLANs. Over time, more VLANs will become
available to GENI.

GENI stitching is enabled at only select aggregates (based on software
capability of the aggregates, or based on provisioning of VLANs). Over
time, this restriction will be lifted.

== Usage ==
stitcher is a simple extension of Omni. Use stitcher just as you would
use Omni. If you try to allocate (using `CreateSliver` or `Allocate`)
resources at multiple aggregates, and specifically if you request a
link that requires stitching, then the new 
code will be exercised (otherwise you are running Omni as usual).

To use stitcher:

 1. Be sure you can run Omni.

 2. Design a topology. Write a standard GENI v3 RSpec or build one
 with a graphical tool like Flack, jFed, or Jacks. For a stitched
 topology, include 1 or more `<link>`s
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
    $ python ./src/stitcher.py createsliver <valid slice name> <path to RSpec>
}}}
(assuming a valid `omni_config` in one of the usual spots)

 5. Stitcher will make allocations at ALL aggregates required for your
 topology. (It ignores the `-a` option.) This may take a while.

 6. Examine the resulting manifest RSpec. Stitcher returns a single
 combined manifest RSpec, covering all the resources just
 reserved. XML comments at the top of the RSpec summarize the
 aggregates at which reservations were made and the circuits reserved.
 Also be sure to notice in the stitcher output when your resources
 expire - particularly if they expire at different times.

 7. Use your resources.

 8. Delete your resources when done. Be sure to delete resources from
 all aggregates - including any reservations at transit networks you
 did not specify in your original request RSpec. If you use
 `stitcher.py` to delete your resources and supply no `-a` argument,
 `stitcher` will delete from all aggregates at which it reserved
 resources. If you use `omni`, you must specify which aggregates to
 invoke (or use `--useSliceAggregates`).

For example, to fully delete your reservation:
{{{
    $ python ./src/stitcher.py deletesliver <valid slice name>
}}}

To delete from only 1 aggregate:
{{{
    $ python ./src/stitcher.py -a <URL> deletesliver <valid slice name>
}}}

=== Notes ===

`createsliver` or `allocate` commands with an RSpec that is bound to
multiple aggregates (one that requires allocations at multiple aggregates),
including those with stitched links and GRE links, will be processed
by the stitcher code. All other calls will be passed directly to Omni.

The same request RSpec will be submitted to every aggregate required
for your topology. Stitcher will create reservations at each of these
aggregates for you. ''Note'' however that stitcher only knows how to
contact aggregates that are either listed in the aggregate nickname
cache (as most production aggregates are), or are in involved in the
circuits you request - nodes at new or non GENI aggregates that you
are trying to reserve in the RSpec that are not linked with 
a stitching link may not be reserved, because stitcher may not know
the URL to contact that aggregate. 

All calls use AM APIv2 by default currently, due to aggregate
limitations. If an aggregate does not speak at least AM API v2, `stitcher`
exits.

AM API v3 is supported where possible. If you invoke stitcher
with `-V3`, the stitcher uses APIv3 at aggregates that support
APIv3. Stitcher will in this case only `allocate` the resources at
those aggregates. Therefore, you will need to use omni later to call
`omni -a <AM> -V3 provision <slice>` and `omni -a <AM> -V3 poa <slice> geni_start`
to complete your reservation. You will then also want to
use stitcher to renew your resources, as in `stitcher renewsliver <slice> <new time>`

Your input request RSpec does ''not'' need a stitching extension, but
should be a single RSpec for all resources that you want in your slice.
To create a request that needs stitching, include at least 1 `<link>` elements with 
more than 1 different `<component_manager>` elements (and no
`<shared_vlan>` element and no `<link_type>` element of other than
`VLAN`). Also note that since the same request RSpec goes to all
aggregates, that all nodes must be bound to specific aggregates.

The result of stitcher is a single combined GENI v3 manifest RSpec, showing
all resources reserved as a result of this request.

Resource expiration is determined by local aggregates. Some aggregates
expires resources in 5 days unless renewed. stitcher attempts to
minimize the number of different times at which your resources expire,
which sometims means your initial expiration at a particular
aggregate will be sooner that it might otherwise have been. Always pay
attention to the reported resource expiration when stitcher completes,
and renew your resources (using `stitcher renewsliver`) when necessary.

stitcher output is controlled using the same options as Omni,
including `-o` to send RSpecs to files, and `--WARN` to turn down most
logging. However, stitcher always saves your combined result manifest
RSpec to a file (named
'`<slicename>-manifest-rspec-multiam-combined.xml`'), unless you
specify the `--tostdout` option. 
Currently, stitcher will (at least temporarily) write several files to the current
working directory (results from `GetVersion` and `SliverStatus`, plus
several manifest RSpecs) (change this directory using the option `--fileDir`).

stitcher output can be all placed in a single directory by using the
`--fileDir` option. This is particularly useful when running multiple
stitcher instances in parallel.

By default, stitcher logs basic information to the console, and
detailed debug information to a file named `stitcher.log`, using the
logging config file `gcf\sticher_logging.conf`. Log format
and content can be controlled with the omni options `--logoutput`,
`--logconfig`, and `--debug`. If you run into problems with stitcher,
you may be asked to submit the debug logs found in
`stitcher.log`. (Logs from your last few runs of stitcher are saved in
backup files. Control the number of backups using the `--logFileCount`
option.)

When complete, `stitcher` writes a file to `~/.gcf` (or the directory
specified by `--fileDir`), listing the
aggregates at which it made reservations. This file is used by
`stitcher` later to drive calls, e.g. to `sliverstatus` or 
`renewsliver` or `deletesliver`. This file is named something like
`slice.hrn-amlist.txt`.

To recreate the combined manifest RSpec for your entire slice as one
file, you can call stitcher with the `listresource` or `describe`
command.
 - Specify `--useSliceAggregates` to ignore the local stitcher file of
 aggregates in your slice, and instead query the clearinghouse.
 - The combined RSpec will be saved to a file as usual.
 - The return signature for the stitcher call (when used as a tool)
 matches that for Omni, with the combined manifest stored under
 `combined`.

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
  URN. For example: 
`--excludehop urn:publicid:IDN+instageni.gpolab.bbn.com+interface+procurve2:5.24=3747-3748`
 - `--includehop <hop URN>`: When supplied, the Stitching Computation
 Service will insist on including the specified switch/port on ANY computed
 stitching paths. You can supply this argument many times. Use this
 with caution, particularly if your request has multiple
 `<link>`s. For many cases, see the following option instead.
 - `--includehoponpath <hop URN> <path id or link client_id>`: When supplied, the Stitching Computation
 Service will insist on including the specified switch/port on only
 the named computed stitching path. You can supply this argument many times. Use this
 with caution. Note that this only includes the hop on the named link,
 in contrast to `--includehop`. Note also that a hop cannot both be
 excluded (via `--excludehop`) and included (via `--includehop` or `--includehoponpath`).

Together, the above options should allow you some control over the
paths used for your circuits, without requiring that you construct the
full RSpec stitching extension yourself.

Additionally, these options are used for some topologies:
 - `--defaultCapacity`: If not specified, set all stitched links to
 request the specified capacity (in Kbps). Default is '20000' meaning ~20Mbps.
 - `--fixedEndpoint`: Use this if you want a dynamic circuit that ends
 not at a node, but at a switch (E.G. because you have a static VLAN to a
 fixed non-AM controlled host from there.). This option adds a fake
 `node` and `interface_ref` to the link. Note that your request RSpec will
 still need >= 2 `component_manager`s on the `<link>`, and you will need a
 skeletal stitching extension with 1 hop being the switch/VLAN where
 you want to end, and a 2nd being the AM where you want to end up.
 - `--noExoSM`: Avoid using the ExoGENI ExoSM. If an aggregate is an
 ExoGENI aggregate and the URL we get is the ExoSM URL, then try to
 instead use the local rack URL, and therefore only local rack
 allocated VMs and VLANs. This is inconsistent with `--useExoSM` and
 implies `--noEGStitching` (use GENI stitching where possible).
 For this to work, your `omni_config` or the
 base aggregate nicknames must have an entry for the local ExoGENI
 rack that specifies both the aggregate URN as well as the URL, EG:
{{{
eg-bbn=urn:publicid:IDN+exogeni.net:bbnvmsite+authority+am,https://bbn-hn.exogeni.net:11443/orca/xmlrpc
eg-renci=urn:publicid:IDN+exogeni.net:rcivmsite+authority+am,https://rci-hn.exogeni.net:11443/orca/xmlrpc
eg-fiu=urn:publicid:IDN+exogeni.net:fiuvmsite+authority+am,https://fiu-hn.exogeni.net:11443/orca/xmlrpc
}}}
 - `--useExoSM`: Try to use the ExoGENI ExoSM for ExoGENI
 reservations. If we get an individual ExoGENI rack URL for an
 aggregate, then try to use the ExoSM URL. This is inconsistent with
 `--noExoSM` or `--noEGStitching` or `--noEGStitchingOnLink`; ExoGENI stitching wil be used where
 applicable. For this to work, your
 `omni_config`  or the base aggregate nicknames must have an entry for
 the ExoGENI rack that specifies the URN and URL, as well as an entry
 for the ExoSM.
 - `--noEGStitching`: Force use of GENI stitching (send the request to
 the SCS) on all links, and not ExoGENI stitching between EG aggregates. This is
 inconsistent with `--useExoSM`.
 - `--noEGStitchingOnLink <link clien_id>`: Force use of GENI stitching (send the request to
 the SCS) only on the named Link, and do not use ExoGENI stitching on
 this link. This is inconsistent with `--useExoSM`. You can supply
 this argument many times for multiple links between ExoGENI resources.

Other options you should not need to use:
 - `--fileDir`: Save _all_ files to this directory, and not the usual
 directory used by stitcher (`/tmp`, CWD or `~`).
 This allows multiple stitcher instances to be run in parallel.
 - `--logoutput` to change the name of the stitcher logging file
 (default is `stitcher.log`).
 - `--logFileCount` to change the number of backup stitcher log files
 to keep (default is 5).
 - `--ionRetryIntervalSecs <# seconds>`: # of seconds to sleep between
 reservation attempts at a DCN based aggregate (e.g. MAX). Default
 is 600 (10 minutes), to allow routers to reset.
 - `--ionStatusIntervalSecs <# seconds>`: # of seconds to sleep between
 sliverstatus calls at a DCN based aggregate (e.g. MAX). Default
 is 30 (seconds).
 - `--scsURL <url>`: URL at which the Stitching Computation Service
 runs. Use the default.
  - The default may be updated over time via a new `omni_defaults`
  entry in the `agg_nick_cache`.
 - `--noReservation`: Do not try to reserve at aggregates; instead,
   just save the expanded request RSpec.
 - `--logconfig` to use a non standard logging configuration. Stitcher
 expects one `StreamHandler` for the console. Default configuration is
 in `gcf\stitcher_logging.conf`.
 - `--timeout`: Maximum number of minutes to allow stitcher to run,
 before timing out. Default is no timeout (`0` minutes). Note that
 by far most runs complete within 45 minutes, and usually much less. Some
 successful stitching runs take 90 minutes or more. On timeout,
 existing reservations are deleted.
 - `--noAvailCheck`: Disable checking for currently available VLAN
 tags at aggregates that support doing such checks.
 - `--genRequest`: Generate the fully expanded request (including SCS
 inputs and checking current availability), but do not do the
 reservation. Instead, save that request to a file.
 - `--fakeModeDir <directory>`: When supplied, does not make any
 actual reservations at aggregates. For testing only.
 - `--savedSCSResults`: Use the specified JSON file of saved results
   from calling the SCS, instead of actually calling the SCS.
 - `--useSCSugg`: Always use the VLAN tag suggested by the
 SCS. Usually stitcher asks the aggregate to pick, despite what the
 SCS suggested.
 - `--noDeleteAtEnd`: When specified, do not delete any successful reservations when the overall
   request has failed, or when the user has interrupted stitcher with Ctrl-C.
 - `--noTransitAMs`: When specified, stop when the only aggregates ready to reserve are those
   added by the SCS (which we assume are transit or intermediate aggregates).
  - In both these cases, finish by printing out how many reservations you have, and saving a
    combined manifest RSpec for your reservations, and a combined request RSpec for the reservations
    that you still need to make. The experimenter must manually edit this request to fill in the proper
    `suggestedVLANRange` and `vlanRangeAvailability` in the proper hops in the request's stitching extension.
    See the comments at the top of the RSpec: `get_vlantag_from` indicates what other `hop` the given `hop`
    should take its VLAN tag from. `Have Reservation?` indicates if you have a reservation here. And
    `AM Depends on` indicates which other AMs must be reserved first before you make a reservation here.
 - `--noSCS`: Do not call the SCS even on stitched topologies. This
    might be useful to reserve a topology previously expanded using
    `--noReservation`, or a topology which has a stitching extension
    already and which for some reason the SCS gives an error on.

== Tips and Details ==

In running stitcher, follow these various tips:
 - Create a single GENI v3 request RSpec for all resources at all
 aggregates you want linked. 
 Stitcher sends the same request RSpec to all aggregates involved in
 your request.
 - Be sure all nodes in the request are bound to specific aggregates.
 - This script can take a while - it must make reservations at all the
 aggregates, and keeps retrying at aggregates that can't provide
 matching VLAN tags. Stitcher must pause 45 seconds or more between
 retries. Be patient.
 - Stitcher will retry when something goes wrong, up to a point. If
 the failure is isolated to a single aggregate failing to find a VLAN,
 stitcher retries at just that aggregate (currently up to 50
 times). If the problem is larger, stitcher will go back to the
 Stitching Computation Service for a new path recommendation (possibly
 excluding a failed hop or a set of failed VLAN tags). Stitcher will
 retry that up to 5 times. After that or on other kinds of errors,
 stitcher will delete any existing reservations and exit.
 - When the script completes, you will have reservations at each of the
 aggregates where you requested nodes in your request RSpec, plus any
 intermediate aggregates required to complete your circuit (e.g. AL2S)
  - or none, if your request failed.
 - Stitcher makes reservations at ''all'' aggregates involved in your
 stitching circuits. Note however that stitcher only knows how to
 contact aggregates that are either listed in the aggregate nickname
 cache (as most production aggregates are), or are in involved in the
 circuits you request - nodes at new or non GENI aggregates that you
 are trying to reserve in the RSpec that are not linked with 
 a stitching link may not be reserved, because stitcher may not know
 the URL to contact that aggregate. 
 - The script return is a single GENI v3 manifest RSpec for all the aggregates
 where you have reservations for this request, saved to a file named
 '<slicename>-manifest-rspec-multiam-combined.xml'
 - Stitcher remembers the aggregates where it made reservations. If
 you use `stitcher.py` for later `renewsliver` or `sliverstatus` or
 `deletesliver` or other calls, stitcher will invoke the command at
 all the right aggregates.
 - If you want to check what aggregates are stitchable, you should view
 the [http://groups.geni.net/geni/wiki/GeniNetworkStitchingSites GENI stitching sites list online].
 You should only try to stitch among aggregates listed here - all
 other requests will fail.
 To check programmatically for a list of sites, including those still
 in testing:
{{{
cd <omni install directory>
export PYTHONPATH=$PYTHONPATH:./src
python src/gcf/omnilib/stitch/scs.py --listaggregates --key <path-to-key> --cert <path-to-cert>
}}}
 - Stitching to fixed endpoints:
  - A fixed endpoint is any switch/port that happens to connect to
  other things but not an explicit node. Use the `--fixedEndpoint`
  option to be sure aggregates can handle this.
  - Typically when using this option, you supply a partial stitching
    extension in your request RSpec, indicating as hop1 a GENI
    aggregate with compute resources, and the other end your switch or
    other fixed endpoint. This should correspond to a main body link
    which has an interface at the GENI aggregate but no interface on a
    2nd aggregate.
 - Stitching to ExoGENI aggregates
  - ExoGENI reservations can come from the specific rack, or from the
  ExoSM's allocation of resources at that rack. You can control in
  stitcher whether you use the local racks or the ExoSM, by using the
  `--useExoSM` or `--noExoSM` options.
  - By default, stitcher uses ExoGENI stitching between ExoGENI
  aggregates, by submitting such requests to the ExoSM. Supplying
  `--noEGStitching` forces stitcher to try to use GENI stitching
  between all such aggregates. Use `--noEGStitchingOnLink` to force
  using GENI stitching only on the named link between ExoGENI racks.
 - Be sure to see the list of Known Issues below.

=== Stitching Computation Service ===

For stitching, the request RSpec must specify the exact switches and
ports to use to connect each aggregate, specifying a full path between
the aggregates. However, experimenters do not
need to do this themselves. Instead, there is a Stitching Computation
Service (SCS) which will fill in these details, including any transit
networks at which you need a reservation (like AL2S). For details on
this service, see the
[https://wiki.maxgigapop.net/twiki/bin/view/GENI/NetworkStitchingAPI MAX SCS wiki page].

Experimenters can of course specify this information themselves, using
[http://hpn.east.isi.edu/rspec/ext/stitch/0.1/stitch-schema.xsd the stitching extension]. 

The Stitching Computation Service (SCS), also provides hints to the
stitcher script on the order in which to make reservations at the
various aggregates.

The SCS URL is set by code, may be updated via a new value in the
aggregate nickname cache, and may be over-ridden by developers or
testers using the `--scsURL` option.

This service was developed by engineers at MAX, and the default
instance is operated by Internet2.

Known issues with this service can be found on the
[http://groups.geni.net/geni/query?status=new&status=assigned&status=reopened&component=MAXSCS GENI Trac]

=== AL2S Aggregate ===

Many connections will cross Internet2's AL2S network. To
support this, Internet2 has developed an AL2S / OESS aggregate. This
aggregate accepts calls using the GENI Aggregate Manager API, and
translates those into calls to the Internet2 OESS system.

This aggregate has no compute resources - it exists only to provision
circuits between other aggregates. When you request a stitched link
between 2 aggregates, often stitcher and the SCS will automatically
add AL2S to your request to provide connectivity.

Known issues with this aggregate can be found on the
[http://groups.geni.net/geni/query?status=new&status=assigned&status=reopened&component=STITCHING GENI Trac]

=== ION Aggregate ===

Previously Internet2 ran an aggregate for their ION network. This
aggregate, as with the ION service, has been decommissioned. The ION AM
translated GENI calls into OSCARS calls, and allocated dynamic
circuits to complete stitched links. This service and aggregate have
been replaced by AL2S.

== Troubleshooting ==

Stitching uses several complex services (this
client, the Stitching Computation Service, the AL2S aggregate, as well
as stitching implementations at aggregates). Therefore, bugs and rough
edges are expected. Please note failure conditions, expect occasional
failures, and report any apparent bugs on the
[https://groups.google.com/forum/#!forum/geni-users GENI Users mailing list].

As with Omni errors, when reporting problems please include as much
detail as possible:
 - Attach the stitcher debug logs found by default in `stitcher.log`
  - If you cannot send us this file, please send:
   - `python src/omni.py --version`
   - The exact commandline you used to invoke stitcher
   - At least the last few lines of your call to stitcher, and all the logs if
   possible
 - The request RSpec you used with stitcher
 - The resulting manifest RSpec if the script succeeded
 - Listing of any new rspec or other files created in `/tmp` and your current
 working directory (or your custom directory from `--fileDir`)

See the list of Known Issues below.

== Common Error Messages ==

=== Fatal errors – something is wrong with your request ===

{{{
StitchingServiceFailedError: Error from Stitching Service: code 3: 
MxTCE ComputeWorker return error message
'Action_ProcessRequestTopology_MP2P::Finish() 
Cannot find the set of paths for the RequestTopology. '.
}}}
  - Errors like this mean there is no GENI layer 2 path possible
  between your specified endpoints. Did you specify an `excludehop` or
  `includehop` you shouldn't have? Or include an aggregate that does
  not support stitching? Alternatively, it may mean that `stitcher`
  tried all available VLAN tags for one of your aggregates, and got a
  stitching failure on each - probably because all tags were not
  available.

`Reservation request impossible at <Aggregate ...>`
 - Something about your request cannot be satisfied. The rest of the message may say more.

`Node ... is unbound in request`
 - One of the nodes in your request did not specify an
 aggregate at which to reserve the resources. All nodes must be bound
 to a specific aggregates (include a `component_manager_id` attribute).

`Inconsistent ifacemap`
 - Your request is impossible. Try the `-–fixedEndpoint` option if that is relevant.

`Not enough bandwidth to connect some nodes`:
 - You requested a link with more bandwidth than is available. Edit
 the `capacity` attribute in your RSpec, or try specifying
 `--defaultCapacity` with a smaller number, or pick a different
 aggregate, or try again later.

`Too many VMs requested on physical host` OR
`Not enough nodes with fast enough interfaces`
 - You have asked for more nodes than are available. Use fewer nodes or
 a different aggregate, or try again later.

`*** ERROR: mapper` OR 
`Could not verify topo` OR 
`Could not map to resources`
 - You may have asked for more nodes or bandwidth than are
 available. Or your request may be malformed. The error message may
 say more, or you can ask on geni-users@googlegroups.com

`Hostname > 63 char`
 - Try a shorter client_id (node name) or slice name

`no edge hop`
 - Your request RSpec likely lists a `component_manager` naming an
 aggregate which has no interface on the given link. Perhaps a
 copy-and-paste error?

`Duplicate link`
 - Do you have 2 links with the same client_id? Edit your request.

`Must delete existing slice/sliver` OR 
`CreateSliver: Existing record` OR
`Rspec error: VM with name ... already exists`
 - You already have a reservation in this slice at this aggregate. Delete it first.

`Malformed keys`
 - Your SSH keys (from your omni_config usually) are malformed.

`Edge domain does not exist`
 - Your ExoGENI request is malformed in some way

`check_image_size error` OR 
`Incorrect image URL in ImageProxy`
 - Check your ExoGENI disk image specification

`Insufficient numCPUCores`
 - The ExoGENI AM has no room for your VM. Stitcher will try the ExoSM / the local rack to see if it has room.

`Need node id for links`
 - You likely have a typo in an interface `client_id` in your link.

`....: Edge iface mismatch when stitching`
 - You have listed 2 nodes at the same AM on the same stitched
 link. Each stitched link should be between 2 interfaces on 2
 different nodes/AMs.

`RSpec requires AM ... which is not in workflow and URL is unknown!`
 - Check your RSpec does not have a typo in the
 `component_manager`. You asked for resources at an unknown aggregate.

`Malformed arguments: *** verifygenicred`
 - There was a problem with your credentials. Try renewing your slice?

`Malformed rspec`
 - There was a problem with your request RSpec. Do you have a typo?

`Duplicate node`
 - 2 of your nodes have the same client_id. Change one.

`No stitching path to ` or `Malformed request? Wrong link type?`
 - There is a problem with your request RSpec. Did you specify the
 wrong link type?

`such a short life for a sliver` or `Renew your slice`
 - Try renewing your slice. Your resources would expire too soon as requested.

`Error encountered converting RSpec to NDL`
 - ExoGENI did not understand something in your request RSpec.

`Embedding workflow ERROR: 1:Insufficient resources or Unknown domain`
 - This ExoGENI error may mean the aggregate ran out of VLAN tags or
 some other resource. Alternately, it may mean you sent your request
 to the wrong ExoGENI aggregate (included an incorrect URN in your
 request RSpec or used the `--noExoSM` option mistakenly.

`Embedding workflow ERROR`
 - ExoGENI aggregates cannot handle requests that mention other
   ExoGENI aggregates. Typically, stitcher sends such requests
   to the ExoSM. Did you supply `--noExoSM` by mistake?
   Alternatively, there may be an error in your request RSpec.

`Exception`
 - A generic aggregate error. Perhaps try again?

`this user is not on the controller's whitelist`
 - The ExoGENI aggregate is in maintenance. Try a different aggregate
 or try again later. Monitor the mailing list: https://groups.google.com/forum/#!forum/geni-orca-users

`Invalid slice urn`
 - This is a fatal error from ExoGENI. Did you request more than 1
   GENI stitching link at a single ExoGENI site?

=== Errors in the tool – you may need to report this as a bug ===

` … has request tag XXX that is already in use by …`
 - Stitcher made an error and picked a tag that is in use. Report this bug.

`SCS gave error: …`
 - The Stitching Computation Service had an error. You may need to report it.

=== Transient errors – stitcher can handle these ===

`Circuit reservation failed at … (…..). Try again from the SCS`
 - An aggregate reported an error. Stitcher will try a new path from
 the SCS to see if that solves your problem (it may not).

`Could not reserve vlan tags` OR 
`Error reserving vlan tag for …` OR 
`vlan tag … not available` OR
`Could not find a free vlan tag` OR
`Could not reserve a vlan tag for` OR
`Exception: requested VLAN unavailable` OR
`Error in building the dependency tree, probably not available vlan path`
 - Some VLAN tag you requested is not available. Stitcher will try to
 find another and try again.

`AddPersonToSite: Invalid argument: No such site`
 - This is the first time this aggregate has seen your
 project. Stitcher will retry and the error should go away. If not,
 try again.

`Topology too complex`
 - Stitcher cannot find a new VLAN tag to try itself, but will retry
 your request at the SCS if possible.

=== After too many transient errors, stitcher gives up ===

`Stitching reservation failed X times. Last error: …`
 - Stitcher goes to the Stitching Service for a path a limited number
 of times. After that, it gives up with this error. Typically this
 means there are not enough VLANs or bandwidth to get to your
 aggregates.

== Known Issues and Limitations ==
 - Aggregate support is limited. See http://groups.geni.net/geni/wiki/GeniNetworkStitchingSites
 - Links are point to point only - each link connects an interface on
 a compute node to another interface on a node.
 - Links between aggregates use VLANs. QinQ is not supported at any
 current aggregates, and VLAN translation support is limited. VLAN
 tags available at each aggregate are limited, and may run out.
 - Stitching to ExoGENI is limited:
  - Reservations at ExoGENI AMs work.
   - Previously if you requested resources at
  multiple ExoGENI AMs, Stitcher would use the ExoSM for all ExoGENI
  reservations. Currently, stitcher allows you to continue using the
  individual ExoGENI racks, unless you specify --useExoSM.
  - Stitching within ExoGENI, by submitting a request to the ExoSM
  with only ExoGENI resources, works fine.
  - Stitching between ExoGENI and non ExoGENI resources only works at
  a very few ExoGENI sites currently.
  - Due to limitations in the `stitcher` tool, you cannot reserve some
  ExoGENI resources from the ExoSM, and some from an individual
  ExoGENI rack. You must either use all ExoSM resources, or all
  resources at an individual rack. See options `--useExoSM` and `--noExoSM`
 - Some aggregates require an explicit capacity to be requested on links. 
   For this reason, stitcher ensures that all requests for stitched links include 
   an explicit capacity (whose value defaults to the `--defaultCapacity` option).
  - Works around issues http://groups.geni.net/geni/ticket/1039 and 
    http://groups.geni.net/geni/ticket/1101
 - AM API v3 support is limited. Users must manually provision, and
   VLAN tag negotiation is not supported.
 - AM API v1 only aggregates are not supported
 - Aggregates do not support `Update`, so you cannot add a link to
 an existing reservation.
 - Some fatal errors at aggregates are not recognized, so the script keeps trying longer
 than it should.
 - [https://github.com/GENI-NSF/geni-tools/issues?q=is%3Aopen+is%3Aissue+label%3Astitcher Known stitcher defects]
   are listed on the project Github repository.
 - Python2.6 has a 60 second delay talking to the SSL protected SCS
   run by Internet2. If you are running python2.6, use `--scsURL http://geni-scs.net.internet2.edu:8081/geni/xmlrpc`

== To Do items ==
 - With ExoGENI AMs: After reservation, loop checking sliverstatus for
 success or failure, then get the manifest after that
 - Thread all calls to omni
 - Summarize errors at the end of the run.
 - Support stitch-to-aggregate at ProtoGENI based aggregates if supported
 - Clean up hard-coded aggregate-specific sliver expiration policy handling
 - Fully support AM API v3; specifically, `provision` reservations on success
 - Consolidate constants
 - Fully handle negotiating among AMs for a VLAN tag to use
  - As in when the returned `suggestedVLANRange` is not what was requested
 - `fakeMode` is incomplete
 - Tune counters, sleep durations, etc
 - Return a struct with detailed results (not just comments in manifest)
 - Return a struct on errors
 - `opts.warn` is used to suppress omni output. Clean that up. A `scriptMode` option?
 - Implement `confirmSafeRequest()` to ensure no dangerous requests are made
 - Expand to additional aggregates
 - Support multipoint circuits

== Related Reading ==
 - [http://groups.geni.net/geni/wiki/GENIExperimenter/Tutorials/StitchingTutorial Stitching Tutorial]
 - [http://groups.geni.net/geni/wiki/GeniNetworkStitchingSites GENI Stitching Sites]
 - [http://groups.geni.net/geni/browser/trunk/stitch-examples Sample Stitching RSpecs]
 - [http://groups.geni.net/geni/wiki/GENIExperimenter/ExperimentExample-stitching A sample use of stitching]
 - [https://wiki.maxgigapop.net/twiki/bin/view/GENI/NetworkStitchingOverview MAX Stitching Architecture and Stitching Service pages]
 - [http://groups.geni.net/geni/wiki/GeniNetworkStitching GENI Network Stitching Design Page]
