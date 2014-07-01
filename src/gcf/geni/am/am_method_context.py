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

import gcf.sfa.trust.gid as gid

# A class to support wrapping AM API calls from AggregateManager
# to the delegate to check for authorization and perform speaks-for

# Uses python 'with' syntax
#     with AMMethodContext(....) as amc:
#        amc._result = self.delegate(...)
#     return amc._result

class AMMethodContext:

    def __init__(self, aggregate_manager, 
                 method_name, logger, authorizer,
                 credentials, args, options, is_v3=False):
        self._aggregate_manager = aggregate_manager
        self._method_name = method_name
        self._logger = logger
        self._authorizer = authorizer
        self._credentials = credentials
        self._args = args
        self._options = options
        self._caller_cert = self._aggregate_manager._delegate._server.pem_cert
        self._caller_urn = gid.GID(string=self._caller_cert).get_urn()
        self._is_v3 = is_v3
        self._result = None

    # This method is called prior to the 'with AMMethodContext' block
    def __enter__(self):
        try:
            self._logger.info("AM Invocation: %s %s %s %s" % \
                                  (self._method_name, self._caller_urn, 
                                   self._args, self._options))
            credentials = self._credentials
            args = self._args

            if self._is_v3:
                if 'urns' in args: 
                    urns = args['urns']
                    the_slice, the_slivers = \
                        self._aggregate_manager._delegate.decode_urns(urns)
                    if 'slice_urn' not in args:
                        args['slice_urn'] = the_slice.urn
                credentials = self.normalize_credentials(self._credentials)

            self._authorizer.authorize(self._method_name, self._caller_cert, 
                                       credentials, args, 
                                       self._options)
        finally:
            return self

    # Take a V3 list of credentials and adjust for V2 Verification
    def normalize_credentials(self):
        delegate = self._aggregate_manager.delegate
        credentials = [delegate.normalize_credential(c) \
                           for c in self._credentials]
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
            self._result = self._errorReturn(value)
        self._logger.info("Result from %s: %s", self._method_name, 
                          self._result)

    # Return a GENI_style error return for given exception/traceback
    def _errorReturn(self, e):
        return {'code' : -1, 'value' : None, 'output' : str(e) }
        


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
