#----------------------------------------------------------------------
# Copyright (c) 2010-2016 Raytheon BBN Technologies
# Copyright (c) 2019 Inria by David Margery for the Fed4FIRE+ project
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

"""A simple XML RPC server supporting getting client cert from HTTP header.

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
from ..sfa.trust.certificate import Certificate
from OpenSSL import crypto

class XMLRPCRequestHandler(SimpleXMLRPCRequestHandler):
    """A request handler that grabs the peer's certificate from
    the http headers and makes it available while the request is handled

    This implementation can only be used in a single-threaded, one
    request at a time model. The peer certificate is stashed on the
    XML RPC server at the start of a call and removed at the end of a
    call. This is the only way I could find to access this
    information.
    """

    def parse_request(self):
        SimpleXMLRPCRequestHandler.parse_request(self)
        client_cert_string=self.headers.get(self.server.certheader_name, "")
        # going through headers in python loose end of line caraters
        # massage the string back to proper PEM format
        client_cert_string=client_cert_string.replace(' ',"\n")
        client_cert_string=client_cert_string.replace("BEGIN\n","BEGIN ")
        client_cert_string=client_cert_string.replace("END\n","END ")

        if client_cert_string is "":
            self.server.pem_cert = None
            self.send_error(400, "Bad request - client cert required")
        else:
            self.server.pem_cert = client_cert_string

        if self.server.logRequests:
            client_cert=Certificate(string=client_cert_string)
            self.log_message("Got call from client cert: %s", client_cert.get_printable_subject())
        return True



class XMLRPCServer(SimpleXMLRPCServer):
    """An extension to SimpleXMLRPCServer that expects TLS transaction.
    has been proxied through a production quality web server, and that the
    client's peer cert is passed to it as an http header
"""

    def __init__(self, addr, requestHandler=XMLRPCRequestHandler,
                 logRequests=False, allow_none=False, encoding=None,
                 bind_and_activate=True, certheader='X-Geni-Client-Cert'):
        SimpleXMLRPCServer.__init__(self, addr, requestHandler, logRequests,
                                    allow_none, encoding, False)
        self.certheader_name=certheader
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
