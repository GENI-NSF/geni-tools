#---------------------------------------------------------------------- 
# Copyright (c) 2010-2015 Raytheon BBN Technologies
# 
# Permission is hereby granted, free of charge, to any person obtaining 
# a copy of this software and/or hardware specification (the "Work") to 
# deal in the Work without restriction, including without limitation the 
# rights to use, copy, modify, merge, publish, distribute, sublicense, 
# and/or sell copies of the Work, and to permit persons to whom the Work 
# is furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be 
# included in all copies or substantial portions of the Work. 
# 
# THE WORK IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS 
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF 
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND 
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT 
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, 
# OUT OF OR IN CONNECTION WITH THE WORK OR THE USE OR OTHER DEALINGS
# IN THE WORK.
#---------------------------------------------------------------------- 
" Base class for authorizers of AM calls"

from __future__ import absolute_import

try:
    from ...sfa.trust import gid
except:
    from gcf.sfa.trust import gid

# Name of all AM Methods
class AM_Methods:
    # AM API V2 Methods
    LIST_RESOURCES_V2 = 'ListResources_V2'
    LIST_RESOURCES_FOR_SLICE_V2 = 'ListResourcesForSlice_V2'
    CREATE_SLIVER_V2 = "CreateSliver_V2"
    DELETE_SLIVER_V2 = "DeleteSliver_V2"
    RENEW_SLIVER_V2 = "RenewSliver_V2"
    SLIVER_STATUS_V2 = "SliverStatus_V2"
    SHUTDOWN_V2 = "Shutdown_V2"

    # AM API V3 Methods
    LIST_RESOURCES_V3 = 'ListResources_V3'
    ALLOCATE_V3 = "Allocate_V3"
    PROVISION_V3 = "Provision_V3"
    DELETE_V3 = "Delete_V3"
    PERFORM_OPERATIONAL_ACTION_V3 = "PerformOperationalAction_V3"
    STATUS_V3 = "Status_V3"
    DESCRIBE_V3 = "Describe_V3"
    RENEW_V3 = "Renew_V3"
    SHUTDOWN_V3 = "Shutdown_V3"

V2_Methods = [AM_Methods.LIST_RESOURCES_V2, 
              AM_Methods.LIST_RESOURCES_FOR_SLICE_V2,
              AM_Methods.CREATE_SLIVER_V2, 
              AM_Methods.DELETE_SLIVER_V2, 
              AM_Methods.RENEW_SLIVER_V2,
              AM_Methods.SLIVER_STATUS_V2, 
              AM_Methods.SHUTDOWN_V2];

# Base class for all AM authorizers
# Should call its base method to get proper logging
class Base_Authorizer(object):
    def __init__(self, root_cert, opts):
        self._root_cert = root_cert
        self._opts = opts # Opts provided by user in GCF configuration
        self._logger = None

    # Try to authorize the call. 
    # Success is silent.
    # Failure raise an exception indicating an authorization error 
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
    def authorize(self, method, caller, creds, args, opts,
                  requested_allocation_state):
        if self._logger:
            caller_urn = gid.GID(string=caller).get_urn()
            template = "Authorizing %s %s #Creds = %s Args = %s Opts =%s"
            self._logger.info(template % \
                                  (method, caller_urn, len(creds), \
                                       args.keys(), opts.keys()))

    # Validate that the given set of arguments and options are
    # appropriate for this method
    # Raise an exception if not, or 
    # return a (possiblly revised) set of arguments and options
    def validate_arguments(self, method_name, arguments, options):
        return arguments, options
