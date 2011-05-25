#----------------------------------------------------------------------
# Copyright (c) 2011 Raytheon BBN Technologies
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
import httplib
import socket
import sys
import xmlrpclib
import M2Crypto.SSL

class SafeTransportWithCert(xmlrpclib.SafeTransport):

    def __init__(self, use_datetime=0, ssl_context=None,
                 timeout=None):
        xmlrpclib.SafeTransport.__init__(self, use_datetime)
        self._ssl_context = ssl_context
        self._timeout = timeout
        # Backward compatibility with Python 2.6
        # Python 2.7 introduces a connection cache.
        if not hasattr(self, '_connection'):
            self._connection = (None, None)

    def make_connection27(self, host):
        if self._connection and host == self._connection[0]:
            return self._connection[1]
        else:
            chost, self._extra_headers, x509 = self.get_host_info(host)
            # ignore the x509 stuff, we don't need it because
            # it is handled by the SSL Context. This one liner
            # avoids an eclipse warning
            _ = x509
            conn = ContextHTTPSConnection(chost, context=self._ssl_context)
            if self._timeout:
                conn._conn.timeout = self._timeout
            # Cache the result for Python 2.7
            self._connection = host, conn
            return self._connection[1]

    def make_connection(self, host):
        conn = self.make_connection27(host)
        if sys.version_info < (2, 7):
            # Wrap the HTTPConnection for backward compatibility
            httpconn = httplib.HTTP()
            httpconn._setup(conn)
            conn = httpconn
        return conn


class ContextHTTPSConnection(httplib.HTTPSConnection):

    def __init__(self, host, port=None,
                 strict=None, timeout=socket._GLOBAL_DEFAULT_TIMEOUT,
                 source_address=None, context=None):
        httplib.HTTPConnection.__init__(self, host, port, strict, timeout)
        self.ssl_context = context

    def connect(self):
        "Connect to a host on a given (SSL) port."

        sock = socket.create_connection((self.host, self.port),
                                        self.timeout)
        # Make sure the _tunnel_host attribute exists. It was
        # introduced between Python 2.6.2 and Python 2.6.6.
        if hasattr(self, '_tunnel_host') and self._tunnel_host:
            self.sock = sock
            self._tunnel()
        if not self.ssl_context:
            # Initialize the M2Crypto SSL Context
            self.ssl_context = M2Crypto.SSL.Context()
        self.sock = M2Crypto.SSL.Connection(self.ssl_context, sock)
        # sock.conn.addr = sock.addr
        self.sock.setup_ssl()
        self.sock.set_connect_state()
        self.sock.connect_ssl()

def make_client(url, ssl_context, verbose=False, timeout=None,
                allow_none=False):
    """Create an SSL connection to an XML RPC server.
    Returns the XML RPC server proxy.
    """
    cert_transport = None
    if ssl_context:
        cert_transport = SafeTransportWithCert(ssl_context=ssl_context,
                                               timeout=timeout)
    return xmlrpclib.ServerProxy(url, transport=cert_transport,
                                 verbose=verbose, allow_none=allow_none)
