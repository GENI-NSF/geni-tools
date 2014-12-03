GCF Policy-based Authorization
==============================

Overview
--------

As of GCF version 2.8, the GCF AM's support a policy-based authorization 
capability by which aggregates may use external policy files to add additional
and specific restrictions on which invocations may or may not be allowed
by the aggregate manager. The GCF AM (v2 and v3) look for an authorizer class
(if configured: see below) and if provided, will call the authorizer to 
see if the given request is allowed.

This authorization call is interposed between the
authentication and argument validation portion of the AM and the call
to the delegate. Thus, any aggregate manager that uses the GCF AM framework
and provides its own delegate will inherit this capability.

The intent of this authorization capability is to provide support 
for policies that are sufficiently expressive for a given aggregate's needs.
There is no required policy language or implementation: these can be
provided by aggregate-provided python classes. However, we provide two
default authorizer classes:
   * SFAAuthorizer: Use standard SFA-based authorization by validating
provided credentials against the requested AM API method. [Note, if
a given AM uses this authorizer or one derived from it, there is no need
for the delegates to do their own SFA-based authorization. They will, however,
probably need to extract expiration times from SFA credentials.]
   * ABACAuthorizer: Parse policy files that set up authorization
based on succeeding/failing to provide ABAC statements indicated in
a policy file. The details on this file and its semantics are described below.

Configuration
-------------

Configuring the policy-based authorization feature consists of
adding the following keyword entries (values for which are examples only)
into the gcf_config file (typically in ~/.gcf):

# Name of python authorizer class to be used to make authorization
# decisions. This class is called by the AM class before invoking
# the delegate methods. If none is provided, no authorization is provided.
# The authorizer must derive from gcf.geni.auth.base_authorizer and
# provide the method:
#
#
# Arguments:
#   method : name of AM API method
#   caller : GID (cert) of caller
#   creds : List of credential/type pairs
#   args : Dictionary of name/value pairs of AM call arguments
#   opts : Dictionary of user provided options
#   requested_allocation_state: The state of the allocated resources
#     if the given request WERE to be authorized. This consists of 
#     a list of all allocation measurements.
# def authorize(self, method, caller, creds, args, opts,
#                      requested_allocation_state):
authorizer=gcf.geni.auth.abac_authorizer.ABAC_Authorizer 

# Name of the policy map file containing the ABAC policies appropriate for 
# given authorities. A given authority may have multiple ABAC policy files
# that apply to requests from users from that authority. An
# example policy_map file might look like:
# {
#        "default" : ["/Users/mbrinn/.gcf/default_policies.json"],
#
#        "ch1.gpolab.bbn.com" : ["/Users/mbrinn/.gcf/default_policies.json",
#                               "/Users/mbrinn/.gcf/ch1_policies.json"]
#  }
authorizer_policy_map_file=/Users/mbrinn/.gcf/am_policy_map.json

# Name of the resource manager python class to be invoked in 
# the authorization process.
# If none is provided, no authorization is performed.
# The resource manager must derive from 
# gcf.geni.auth.abac_resource_manager.BaseResourceManager and provide a method:
#
#
# Return a list of proposed allocated slivers
# with sliver_urn, slice_urn, user_urn, start_time, end_time plus a list 
# of all measurements about the sliver.
# {meas : value}
# e.g.
# [
#   {'sliver_urn' : sliver1, 'slice_urn' : slice1, 'user_urn' : user1,
#    'start_time' : t0, 'end_time' : t1',
#     'measurements' : {'M1' : 3, 'M2' : 4}}
#   ...
# ]
# def get_requested_allocation_state(self, aggregate_manager, method_name,
#                                            arguments, options,  creds):
authorizer_resource_manager=gcf.geni.auth.abac_resource_manager.GCFAM_Resource_\
Manager

# The authorization process supports interposing an argument guard
# to add additional requirements, validation checks or transformations
# on provided arguments.
# The argument guard must derive from the python class
# gcf.geni.auth.argument_guard.Base_Argument_Guard and provide this method:
#
#
# Check the arguments and options presented to the given call.
# Either return an exception or 
# return the (same or modified) arguments and options.
# def validate_arguments(self, method_name, arguments, options):
#     return arguments, options
argument_guard=gcf.geni.auth.argument_guard.TEST_Argument_Guard

# Optionally, one can set up the authorization as a local XMLRPC service
# so that the authorization runs in a separate process from the AM, which
# allows AMs written in different languages to use the same authorization
# code base. If a URL of an authorizer is provided, it is contacted
# by the AM to provide authorization services. Otherwise, an internal
# instance of the 'authorizer' above is contacted.
# 
remote_authorizer=http://localhost:8888

ABAC Overview
-------------

ABAC (http://abac.deterlab.net) is a first-order logic system that supports
creating signed assertions and proving whether a given statement can be 
proven from a provided set of assertions. ABAC statements are typically of
one of these two forms:
    * [Signer][Set]<--[Member].
         "Signer asserts that Member is in a given set"
	 e.g. "AM.MAY_SHUTDOWN<--MSB

    * [Signer].[SetA]<--[Autority].[SetB]
         "Signer asserts that anyone that Authority places in Set B 
         is in Set A."
	 e.g. "AM.MAY_SHUTDOWN<--IMINDS_CH.MAY_SHUTDOWN"

ABAC Policy File Format
-----------------------

The ABAC policy file is a JSON file with these tags (most optional):

{
	# Linking a mnenonic name to an X509 certificate, 
	# e.g. "AM : "~/.gcf/am-cert.pem"
	"identities" : ....

	# List of python classes that generate bindings of values to variables
	# e.g. $MONTH=11 is set by gcf.geni.auth.binders.StandardBinder
	"binders" : ...

	# Dictionary of constant bindings of names to values e.g.
	# QUOTA_AUTHORITY_VM_TOTAL" : "20"
	"constants" : ...

	# List of ABAC assertions to be made if (python) condition is met
	# e.g.
	#	{
	#            "condition" : "$USER_NUM_SLICES > 2",
	#            "assertion" : "AM.EXCEEDS_QUOTA<-$CALLER"
	#            },
	"conditional_assertions" : ...

	# Fixed (unconditional) ABAC statements to be included in
	# query calculations, e.g. 
	# "AM.MAY_SHUTDOWN<--CH_IMINDS.MAY_SHUTDOWN"
	"policies": ...

	# List of statements EACH of which must be proven (if 'is_positive')
	# or must NOT be proven (if not 'is_positive') to allow authorization
	# e.g.
	# {
	#           "statement" : "AM.IS_AUTHORIZED<-$CALLER",
	#            "is_positive" : true,
	#            "message" : "Authorization Falure"
	#            },
	#        {
	#            "statement" : "AM.EXCEEDS_QUOTA<-$CALLER",
	#            "is_positive" : false,
	#            "message" : "Quota Exceeded"
	#            },

	"queries": ....
}

Example Policy Files
-----------------------

An example policy file is provided in $GCF/examples/example_am_policies.json.

An exmaple policy MAP file is provided in
$GCF/examples/example_am_policy_map.json.

Example Policy Capabilities
---------------------------

The intent of the policy-based authorization is to provide sufficient
expressivity to satisfy the authorization requirements of a given 
aggregate manager. Obviously, these can vary widely. That said, we expect
that there will be some standard authorization criteria a given
aggregate may want to consider.
   - SFA Authorization: Does the given call satisfy SFA criteria? (Is
there a credential signed by a trusted authority providing the authorization
to perform given operation in given context?)
   - Quotas. A given aggregate may wish to place quotas on the amount
or number of resources allowed to be allocated to a given entity (user,
slice, project, authority) at a given time or over time. Depending on 
the resource manager provided, different 'measurements' can be provided
to the aggrregate manager, allowing the binding of variables against
which resource quotas can be tested, e.g. "$AUTHORITY_VM_TOTAL > 2" or
"$PROJECT_BW_HOURS > 1000000".
   - Blacklist/Whitelist. Policies can assert that a given invoker 
(caller or associated authority) must be on a given whitelist or must
not be on a given blacklist. (Such lists would be externally managed).
   - Schedule violation. A given aggregate may wish to assert that
certain users may access resources only in certain times of day or week.
  - Topology management. A given aggregate may wish to limit which
external resources a given slice may connect to (e.g. what remote
resources may be stitched to) by a given user.
   - Privileged operations. A given aggregate may require special credentials
for performing particular operations (e.g. slice shutdown).
