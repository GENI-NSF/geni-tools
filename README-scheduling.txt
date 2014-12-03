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
