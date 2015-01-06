Asset Scheduling in GCF
=======================

As of gcf 2.8, the GCF AM provides the ability to allocate resources
at some time in the future. Some details:
   - The GCF AM now accepts a 'geni_start_time' option to 'Allocate',
   specifying when the reservation window should begin.
   - The start_time of the allocation (when it is allowed to be provisioned)
   is indicated by the 'geni_start_time' option.
   - The start_time must not be before the current time nor later than
   the geni_end_time or geni_expires times.
    - geni_end_time remains the requested sliver expiration, where
    geni_expires is the actual sliver expiration time.
    - If unspecified, the default geni_start_time is 'now' (current
    time). This is the current standard AM API behavior.
    - Provisioning resources can only take place when the current time
    is between geni_start_time and geni_end_time.

In the context of scheduled assets, the essentials of the AM API calls and
returns are unchanged:
    - One has a list of slivers that can be queried (Status, Details)
or acted upon (Delete, etc.).
   - Status and Details indicate the geni_start_time for resources in
their return.
   - One can Delete or Renew (extend the expiration of) future 
reservations, but not perform POA on such slivers.
 
Asset scheduling only makes sense in an AM API V3 context in which
resource allocation and provisioning are operational states.

One benefit of such an approach is to allow for the writing and
enforcing of policies that take into consideration all allocations, not
merely current allocations/provisions. For example, one may want
to limit the total number of VM-hours allocatable to a given user (or
slice, project or authority) to some limit.

Any AM that is built as a delegate on the GCF AM framework will inherit this
capability transparently.

One feature that remains to be implemented and standardized is the
advertisement in GetVersion that a given AM handles asset scheduling. This
advertisement, once standardized in the AM API (or informally among aggregate
developers) will enable tools to know which aggregates may or may not
be tasked with future allocations.


Details on AM API time parameters
===================================

The scheduling of GENI resources are usually characterized by three times, 
namely the start_time, end_time and expiration time. This section describes
how these times operate and interact in different contexts and provisioning
states.

1. Present Allocation.

The default case is to allocate resources for the current time ('now'). In this
case the geni_start_time is not provided and is assumed to be the current time.
GENI allows resources to be in allocated (but not yet provisioned) state for
a short period of time. During that window, the resource must be provisioned 
or it expires. There is no difference between the 'geni_end_time' and
'geni_expires' in this case.

When the resource is allocated, 
     - geni_start_time = Now
     - geni_end_time = geni_expires = Now + some small time delta
     (e.g. 5 min), when the allocated sliver will expire if not
     renewed or provisioned. The experimenter may request a specific
     geni_end_time, though it is not honored everywhere.

When the resource is provisioned, 
     - geni_start_time = Time of allocation
     - geni_end_time = geni_expires = time of provisioned sliver expiration
     		   which will be typically many hours or days in the future
		   depending on the aggregate policy (max_lease) and
		   the expiration of slice credentials. The
		   experimenter may supply a desired geni_end_time as
		   part of the call to Provision.

When the resource is renewed, 
     the geni_end_time and geni_expires are to be moved in tandem to the time 
     requested by the user, bounded by aggregate policy
     and the expiration of slice credentials. 

2. Future Allocation

In the case of future (scheduled) allocation, the start_time is the
requested start of the scheduled allocation (when the experimenter
wants the resources) and the end_time is the
requested end of the scheduled allocation (when the experimenter wants
the actual reservation to end; in the case of a call to Allocate or
allocated slivers, this is a change from APIv3 and the Present
Allocation case).  As above, there is a small window
during which an allocated resource may be provisioned, indicated by the
geni_expires time. If the resource is not provisioned by the end of that 
window (the expiration time), the resource expires and may not be 
subsequently provisioned.

When the resource is allocated,
     - geni_start_time is provided to specify a time in future when
     the actual reservation should start
     - geni_end_time is provided to specify a time in future (the time that the
     		   resource WILL expire once provisioned) bound by
		   aggregate policy and slice credential
		   expiraiton. Note that this is different from the
		   Present Allocation case, when this time specifies
		   when the allocated slivers will expire.
     - geni_expires is the time the allocated sliver will expire if not
     		  provisioned, typically several minutes after
		  geni_start_time and well before geni_end_time.

When resource is provisioned,
     - geni_start_time is the time the resource is provisioned; this
     is when the resources actually began belonging to the experimenter
     - geni_end_time is the time indicated in the allocation call when 
     		   the resource will expire, or as modified by the
		   experimenter with a new geni_end_time argument to Provision
     - geni_expires is the same as geni_end_time

Resource renewal is different in the allocated and provisioned states:
    - When renewing a resource in the allocated state, the expires time is moved 
    as requested (bound by slice credential expiration and aggregate policy) 
    and end_time is unchanged. 
    - When renewing a resource in the provisioned state, the end_time and expires
    time are changed together (bound by slice credential expiration and 
    aggregate policy).

Summarizing key differences from the Present Allocation case (and
standard AM API v3):
 - geni_start_time is supplied to Allocate for when the reservation
 should start (when they will be Provisioned)
 - geni_end_time as an argument always modifies when Provisioned
 resources will expire, and there is no way to request when Allocated
 slivers will expire before they are allocated; use Renew
 - geni_expires and geni_end_time as return values are different for geni_allocated
 slivers; geni_expires is when the slivers expire, and geni_end_time
 is when the future reservation window closes

Returns from Allocate, Provision and Details return all three times 
(geni_start_time, geni_end_time, geni_expires) for all specified slivers.

Recommended Future Work
=======================

This GCF implementation of resource scheduling is somewhat inconsistent with 
the AM API as currently documented. In the AM API, providing a geni_end_time 
argument modifies the expiration time of slivers in their current state: there is no distinction
between the end_time and expiration_time of a resource.

We suggest one of two solutions:
   1. Modify the AM API to indicate that geni_expires be the flag provided
to allocate, renew, provision to modify the expiration time.
or 2. Modify the scheduling code to take an additional time argument (e.g.
"geni_requested_end_time") to explicitly handle the time for which
the resource is requessted to expire WHEN PROVISIONED (leaving
   geni_end_time's meaning unchanged).

In the current implementation, one cannot change the start time of a future 
reservation: one must call delete and then re-allocate. Perhaps in the future
we can augment the AM API to move the scheduled time of an unprovisioned 
resource.

In the current implementation, it is assumed that an Allocated
resource will be used as provided, and the resource is held for the
experimenter. An experimenter that does not intend to use an
allocation as provided must explicitly call Delete to avoid tying up
future resources. An explicit 'Commit' call to be used between
Allocate and Provision (with associated time windows and states) would
allow AMs to require an explicit commitment from experimenters of
their intent to use a future reservation.

