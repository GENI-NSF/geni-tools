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
" Default authorizer class that performs SFA credential verification"

from __future__ import absolute_import

from .base_authorizer import Base_Authorizer, AM_Methods

from ..am.am2 import CREATESLIVERPRIV as CREATESLIVERPRIV_V2
from ..am.am2 import RENEWSLIVERPRIV as RENEWSLIVERPRIV_V2
from ..am.am2 import DELETESLIVERPRIV as DELETESLIVERPRIV_V2
from ..am.am2 import SLIVERSTATUSPRIV as SLIVERSTATUSPRIV_V2
from ..am.am2 import SHUTDOWNSLIVERPRIV as SHUTDOWNSLIVERPRIV_V2

from ..am.am3 import RENEWSLIVERPRIV as RENEWSLIVERPRIV_V3
from ..am.am3 import ALLOCATE_PRIV as ALLOCATE_PRIV_V3
from ..am.am3 import PROVISION_PRIV as PROVISION_PRIV_V3
from ..am.am3 import PERFORM_ACTION_PRIV as PERFORM_ACTION_PRIV_V3
from ..am.am3 import DELETESLIVERPRIV as DELETESLIVERPRIV_V3
from ..am.am3 import SLIVERSTATUSPRIV as SLIVERSTATUSPRIV_V3
from ..am.am3 import SHUTDOWNSLIVERPRIV as SHUTDOWNSLIVERPRIV_V3

from ..util.cred_util import CredentialVerifier

# Note: This authorizer does the standard SFA checking for privileges?
# based on credentials. For aggregtes or authorizers that only wish
# to extract expiration times from credentials, the gcf.sfa.credential
# module to create a Credential object and extract features from that object

class SFA_Authorizer(Base_Authorizer):

    # For each method (V2 and V3) indicate what SFA privileges are required
    METHOD_ATTRIBUTES = {
        # AM API V2 Methods
        AM_Methods.LIST_RESOURCES_V2 : { 'privileges' : (), 
                                         'slice_required' : False },
        AM_Methods.LIST_RESOURCES_FOR_SLICE_V2 : { 'privileges' : (), },
        AM_Methods.CREATE_SLIVER_V2 : {'privileges' : (CREATESLIVERPRIV_V2,) },
        AM_Methods.DELETE_SLIVER_V2 : {'privileges' : (DELETESLIVERPRIV_V2,) } ,
        AM_Methods.RENEW_SLIVER_V2 : {'privileges' :  (RENEWSLIVERPRIV_V2,) },
        AM_Methods.SLIVER_STATUS_V2 : {'privileges' : (SLIVERSTATUSPRIV_V2,) },
        AM_Methods.SHUTDOWN_V2 : {'privileges' : (SHUTDOWNSLIVERPRIV_V2,) },

        # AM API V3 Methods
        AM_Methods.LIST_RESOURCES_V3 : { 'privileges' : (), 
                                         'slice_required' : False },
        AM_Methods.ALLOCATE_V3 : { 'privileges' : (ALLOCATE_PRIV_V3,) },
        AM_Methods.PROVISION_V3 : { 'privileges' : (PROVISION_PRIV_V3,) },
        AM_Methods.DELETE_V3 : { 'privileges' : (DELETESLIVERPRIV_V3,) },
        AM_Methods.PERFORM_OPERATIONAL_ACTION_V3 : \
            { 'privileges' : (PERFORM_ACTION_PRIV_V3,) },
        AM_Methods.STATUS_V3 : { 'privileges' : (SLIVERSTATUSPRIV_V3,) },
        AM_Methods.DESCRIBE_V3 : { 'privileges' : (SLIVERSTATUSPRIV_V3,) },
        AM_Methods.RENEW_V3 : { 'privileges' : (RENEWSLIVERPRIV_V3,) },
        AM_Methods.SHUTDOWN_V3 : { 'privileges' : (SHUTDOWNSLIVERPRIV_V3,) }

    }

    # Create a cred verifier for all credentials on all calls
    def __init__(self, root_cert, opts, argument_guard):
        Base_Authorizer.__init__(self, root_cert, opts)
        self._cred_verifier = CredentialVerifier(root_cert)

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
    def authorize(self, method, caller, creds, args, opts,
                  requested_allocation_state):
        Base_Authorizer.authorize(self, method, caller, creds, args, opts,
                                  requested_allocation_state)


        if method not in self.METHOD_ATTRIBUTES:
            raise Exception("Unrecognized method: %s" % method)

        # Extract slice urn from args if required
        slice_urn = None
        if 'slice_required' not in self.METHOD_ATTRIBUTES[method] or \
                self.METHOD_ATTRIBUTES[method]['slice_required']:
            if 'slice_urn' not in args: 
                raise Exception("No slice_urn argument")
            slice_urn = args['slice_urn']

        privileges = self.METHOD_ATTRIBUTES[method]['privileges']
        try:
            new_creds = \
                self._cred_verifier.verify_from_strings(caller, creds, 
                                                        slice_urn, privileges, 
                                                        opts)
        except Exception, e:
            raise Exception("Insufficient privileges: %s" % str(e))
