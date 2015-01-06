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

"""A version of SimpleXMLRPCRequestHandler supporting multithreading
                                                                                
Based on this article:                                                          
   http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/81549                
                                                                                
"""

from __future__ import absolute_import

import ssl
import base64
import textwrap
import os
import threading
import SocketServer

from .SecureXMLRPCServer import SecureXMLRPCServer
from .SecureXMLRPCServer import SecureXMLRPCRequestHandler


class SecureThreadedXMLRPCRequestHandler(SecureXMLRPCRequestHandler):
    """A request handler that grabs the socket peer's certificate and           
    makes it available while the request is handled.
    """
                                                                                
    request_specific_info = threading.local() # thread specific storage         

    def setup(self):
        SecureXMLRPCRequestHandler.setup(self)

        # Clear single-thread versions of info - not used and hides bugs
        self.server.peercert = None
        self.server.der_cert = None
        self.server.pem_cert = None

        # Now save all this information in a thread specific data structure.    
        # This is so we can have multiple requests active on this server        
        # with a thread assigned to each request.                               
        SecureThreadedXMLRPCRequestHandler.request_specific_info.peercert = \
            self.request.getpeercert()
        SecureThreadedXMLRPCRequestHandler.request_specific_info.der_cert = \
            self.request.getpeercert(binary_form=True)

        # This last is what a GID is created from                               
        SecureThreadedXMLRPCRequestHandler.request_specific_info.pem_cert = \
            self.der_to_pem(SecureThreadedXMLRPCRequestHandler.request_specific_info.der_cert)
        SecureThreadedXMLRPCRequestHandler.request_specific_info.thread_name = \
            threading.current_thread().name
        SecureThreadedXMLRPCRequestHandler.request_specific_info.requestline = \
            "<requestline not set by XMLRPC server>"

        #print "Setup by thread %s" % threading.current_thread().name

        if self.server.logRequests:
            self.log_message('Setup by thread %s' % \
                                    SecureThreadedXMLRPCRequestHandler.request_specific_info.thread_name )

    @staticmethod
    def get_pem_cert() :
        return SecureThreadedXMLRPCRequestHandler.request_specific_info.pem_cert

class SecureThreadedXMLRPCServer(SocketServer.ThreadingMixIn, SecureXMLRPCServer):
    """An extension to SecureMLRPCServer that adds multi-threading per RPC"""

    def __init__(self, addr, requestHandler=SecureThreadedXMLRPCRequestHandler,
                 logRequests=False, allow_none=False, encoding=None,
                 bind_and_activate=True, keyfile=None, certfile=None,
                 ca_certs=None):
        SecureXMLRPCServer.__init__(self, addr, requestHandler=requestHandler, \
                                        logRequests=logRequests, allow_none=allow_none, \
                                        encoding=encoding, \
                                        bind_and_activate=bind_and_activate, \
                                        keyfile=keyfile, certfile=certfile, ca_certs=ca_certs)



    # Threaded version of get_pem_cert: pull from 
    # request_specific_info (per thread)
    def get_pem_cert(self) :
        return SecureThreadedXMLRPCRequestHandler.get_pem_cert()

