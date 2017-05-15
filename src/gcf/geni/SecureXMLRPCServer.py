#----------------------------------------------------------------------
# Copyright (c) 2010-2016 Raytheon BBN Technologies
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

"""A simple XML RPC server supporting SSL.

Based on this article:
   http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/81549

"""

from __future__ import absolute_import

import ssl
import base64
import textwrap
import os

from SimpleXMLRPCServer import SimpleXMLRPCServer
from SimpleXMLRPCServer import SimpleXMLRPCRequestHandler

class SecureXMLRPCRequestHandler(SimpleXMLRPCRequestHandler):
    """A request handler that grabs the socket peer's certificate and
    makes it available while the request is handled.

    This implementation can only be used in a single-threaded, one
    request at a time model. The peer certificate is stashed on the
    XML RPC server at the start of a call and removed at the end of a
    call. This is the only way I could find to access this
    information.
    """

    def setup(self):
        SimpleXMLRPCRequestHandler.setup(self)
        # This first is humanreadable subjectAltName URI, etc
        self.server.peercert = self.request.getpeercert()
        self.server.der_cert = self.request.getpeercert(binary_form=True)
        # This last is what a GID is created from
        self.server.pem_cert = self.der_to_pem(self.server.der_cert)
        if self.server.logRequests:
            self.log_message("Got call from client cert: %s", self.server.peercert)

    def finish(self):
        # XXX do we want to delete the peercert attribute?
        # If so, use:        del self.server.peercert
        self.server.peercert = None
        self.server.der_cert = None
        self.server.pem_cert = None
        SimpleXMLRPCRequestHandler.finish(self)
        
    def der_to_pem(self, der_cert_bytes):
        "base64 encode the der cert and wrap with proper begin/end lines."
        # Cribbed from ssl.DER_cert_to_PEM_cert, which fails to
        # put the newline in front of the PEM_FOOTER
        f = base64.standard_b64encode(der_cert_bytes)
        return (ssl.PEM_HEADER + '\n' +
                textwrap.fill(f, 64) +
                '\n' + ssl.PEM_FOOTER + '\n')
        

class SecureXMLRPCServer(SimpleXMLRPCServer):
    """An extension to SimpleXMLRPCServer that adds SSL support."""

    def __init__(self, addr, requestHandler=SecureXMLRPCRequestHandler,
                 logRequests=False, allow_none=False, encoding=None,
                 bind_and_activate=True, keyfile=None, certfile=None,
                 ca_certs=None):
        SimpleXMLRPCServer.__init__(self, addr, requestHandler, logRequests,
                                    allow_none, encoding, False)
        if certfile and ((not os.path.exists(certfile)) or os.path.getsize(certfile) < 1):
            raise Exception("certfile %s doesn't exist or is empty" % certfile)

        if keyfile and ((not os.path.exists(keyfile)) or
                        os.path.getsize(keyfile) < 1):
            raise Exception("keyfile %s doesn't exist or is empty" % keyfile)
        self.socket = ssl.wrap_socket(self.socket,
                                      keyfile=keyfile,
                                      certfile=certfile,
                                      server_side=True,
                                      cert_reqs=ssl.CERT_REQUIRED,
#                                      ssl_version=ssl.PROTOCOL_TLSv1,
                                      ssl_version=ssl.PROTOCOL_SSLv23, # Ideally we'd accept any TLS but no SSL. Sigh.
                                      ca_certs=ca_certs)
#                                      ciphers='HIGH:MEDIUM:!ADH:!SSLv2:!MD5:!RC4:@STRENGTH') # Hopefully this effectively excludes SSLv2 and 3?
        if bind_and_activate:
            # This next throws a socket.error on error, eg
            # Address already in use or Permission denied. 
            # Catch for clearer error message?
            self.server_bind()
            self.server_activate()

    # Return the PEM cert for current XMLRPC client connection
    # This works for the single threaded case. Need to override
    # This method for the threaded case
    def get_pem_cert(self):
        return self.pem_cert
