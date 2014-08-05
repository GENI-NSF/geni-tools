#----------------------------------------------------------------------        
# Copyright (c) 2010-2014 Raytheon BBN Technologies                            
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

import os
import gcf.sfa.trust.gid as gid
from gcf.sfa.trust.credential import Credential
from gcf.sfa.trust.certificate import Certificate
from gcf.sfa.trust.abac_credential import ABACCredential
from gcf.geni.util.speaksfor_util import determine_speaks_for
from gcf.geni.SecureThreadedXMLRPCServer import SecureThreadedXMLRPCRequestHandler


# A class to support wrapping AM API calls from AggregateManager
# to the delegate to check for authorization and perform speaks-for

# Uses python 'with' syntax
#     with AMMethodContext(....) as amc:
#        amc._result = self.delegate(...)
#     return amc._result

class AMMethodContext:

    def __init__(self, aggregate_manager, 
                 method_name, logger, authorizer,
                 resource_manager, 
                 argument_guard, 
                 credentials, args, options, 
                 is_v3=False, resource_bindings=False):
        self._aggregate_manager = aggregate_manager
        self._method_name = method_name
        self._logger = logger
        self._authorizer = authorizer
        self._resource_manager = resource_manager
        self._argument_guard = argument_guard
        self._credentials = credentials
        self._args = args
        self._options = options
#        self._caller_cert = self._aggregate_manager._delegate._server.pem_cert
        self._caller_cert = aggregate_manager._delegate._server.get_pem_cert()
        self._caller_urn = gid.GID(string=self._caller_cert).get_urn()
        self._is_v3 = is_v3
        self._resource_bindings = resource_bindings
        self._result = None
        self._error = False

    # This method is called prior to the 'with AMMethodContext' block
    def __enter__(self):
        try:
            self._logger.info("AM Invocation: %s %s %s %s" % \
                                  (self._method_name, self._caller_urn, 
                                   self._args, self._options))
            credentials = self._credentials


            # Possibly modify args and options
            if self._argument_guard:
                self._args, self._options = \
                    self._argument_guard.check_arguments(self._method_name,
                                                         self._args, 
                                                         self._options)
#                self._logger.info("New Args %s New Options %s" % \
#                                      (self._args, self._options))

            args = self._args

            # Change client cert if valid speaks-for invocation
            caller_gid = gid.GID(string=self._caller_cert)
            new_caller_gid = determine_speaks_for(self._logger,
                                                   credentials,
                                                   caller_gid,
                                                   self._options,
                                                   None)

            if new_caller_gid != caller_gid:
                new_caller_urn = new_caller_gid.get_urn()
                self._logger.info("Speaks-for invoation: %s for %s" % 
                                  (self._caller_urn, new_caller_urn))
                self._caller_cert = new_caller_gid.save_to_string()
                self._caller_urn = new_caller_urn

            self._options['geni_true_caller_cert'] = self._caller_cert
            self._options['geni_am_urn'] = \
                self._aggregate_manager._delegate._my_urn

            if self._is_v3:
                if 'urns' in args: 
                    urns = args['urns']
                    the_slice, the_slivers = \
                        self._aggregate_manager._delegate.decode_urns(urns)
                    if the_slice and 'slice_urn' not in args:
                        args['slice_urn'] = the_slice.getURN()
                credentials = self._normalize_credentials(self._credentials)

            if self._authorizer is not None:
                requested_allocation_state = []
                if self._resource_manager and self._resource_bindings:
                    my_am = self._aggregate_manager
                    my_rm = self._resource_manager
                    requested_allocation_state = \
                        my_rm.get_requested_allocation_state(my_am, 
                                                             self._method_name, 
                                                             args, 
                                                             self._options, 
                                                             credentials)
                self._authorizer.authorize(self._method_name, 
                                           self._caller_cert, 
                                           credentials, args, 
                                           self._options,
                                           requested_allocation_state)
        except Exception, e:
            self._handleError(e)
        finally:
            return self

    # Determine if this is a speaks-for invocation and if so,
    # return the cert of the spoken-for entity

    # Take a V3 list of credentials and adjust for V2 Verification
    def _normalize_credentials(self, credentials):
        delegate = self._aggregate_manager._delegate
        credentials = [delegate.normalize_credential(c) \
                           for c in credentials]
        credentials = \
            [c['geni_value'] for c in filter(isGeniCred, credentials)]
        return credentials
            

    # This is called after the 'with AMMethodContext' block
    # If there was an exception within that block, type is the exception
    # type, value is the exception and traceback_object is the stack trace
    # Otherwise, these arguments are all none
    def __exit__(self, type, value, traceback_object):
        if type:
            self._logger.exception("Error in %s" % self._method_name)
            self._handleError(value)

        self._logger.info("Result from %s: %s", self._method_name, 
                          self._result)

    # Return a GENI_style error return for given exception/traceback
    def _errorReturn(self, e):
        code_dict = {'am_type' : 'gcf2', 'geni_code' : -1, 'am_code' : -1}
        return {'code' : code_dict, 'value' : '', 'output' : str(e) }

    def _handleError(self, e):
        self._result = self._errorReturn(e)
        self._error = True
        


def isGeniCred(cred):
    """Filter (for use with filter()) to yield all 'geni_sfa' credentials     
    regardless over version.                                                 
    """
    if not isinstance(cred, dict):
        msg = "Bad Arguments: Received credential of unknown type %r"
        msg = msg % (type(cred))
        raise ApiErrorException(AM_API.BAD_ARGS, msg)
    return ('geni_type' in cred
            and str(cred['geni_type']).lower() in \
                [Credential.SFA_CREDENTIAL_TYPE,
                 ABACCredential.ABAC_CREDENTIAL_TYPE])
