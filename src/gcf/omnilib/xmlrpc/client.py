#----------------------------------------------------------------------
# Copyright (c) 2011-2015 Raytheon BBN Technologies
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
import urllib
import xmlrpclib

class SafeTransportWithCert(xmlrpclib.SafeTransport):

    def __init__(self, use_datetime=0, keyfile=None, certfile=None,
                 timeout=None):
        # Ticket #776: As of Python 2.7.9, server certs are verified by default.
        # But we don't have those. To preserve old functionality with new python,
        # pass an explicit context
        # Thanks to Ezra Kissel
        import sys
        if sys.version_info >= (2,7,9):
            import ssl
            xmlrpclib.SafeTransport.__init__(self, use_datetime, context=ssl._create_unverified_context())
        else:
            xmlrpclib.SafeTransport.__init__(self, use_datetime)
        self.__x509 = dict()
        if keyfile:
            self.__x509['key_file'] = keyfile
        if certfile:
            self.__x509['cert_file'] = certfile
        self._timeout = timeout

    def make_connection(self, host):
        host_tuple = (host, self.__x509)
        conn = xmlrpclib.SafeTransport.make_connection(self, host_tuple)
        if self._timeout:
            if hasattr(conn, '_conn'):
                # Python 2.6
                conn._conn.timeout = self._timeout
            else:
                # Python 2.7
                conn.timeout = self._timeout
        return conn

class SafeTransportNoCert(xmlrpclib.SafeTransport):
    # A standard SafeTransport that honors the requested SSL timeout
    def __init__(self, use_datetime=0, timeout=None):
        # Ticket #776: As of Python 2.7.9, server certs are verified by default.
        # But we don't have those. To preserve old functionality with new python,
        # pass an explicit context
        # Thanks to Ezra Kissel
        import sys
        if sys.version_info >= (2,7,9):
            import ssl
            xmlrpclib.SafeTransport.__init__(self, use_datetime, context=ssl._create_unverified_context())
        else:
            xmlrpclib.SafeTransport.__init__(self, use_datetime)
        self.__x509 = dict()
        self._timeout = timeout

    def make_connection(self, host):
        host_tuple = (host, self.__x509)
        conn = xmlrpclib.SafeTransport.make_connection(self, host_tuple)
        if self._timeout:
            if hasattr(conn, '_conn'):
                # Python 2.6
                conn._conn.timeout = self._timeout
            else:
                # Python 2.7
                conn.timeout = self._timeout
        return conn

def make_client(url, keyfile, certfile, verbose=False, timeout=None,
                allow_none=False):
    """Create a connection to an XML RPC server, using SSL with client certificate
    authentication if requested.
    Returns the XML RPC server proxy.
    """
    cert_transport = None
    if keyfile and certfile:
        if not os.path.exists(certfile):
            raise Exception("certfile %s doesn't exist" % certfile)
        if not os.path.getsize(certfile) > 0:
            raise Exception("certfile %s is empty" % certfile)

        if not os.path.exists(keyfile):
            raise Exception("keyfile %s doesn't exist" % keyfile)
        if not os.path.getsize(keyfile) > 0:
            raise Exception("keyfile %s is empty" % keyfile)

        cert_transport = SafeTransportWithCert(keyfile=keyfile,
                                               certfile=certfile,
                                               timeout=timeout)
    else:
        # Note that the standard transport you get for https connections
        # does not take the requested timeout. So here we extend
        # that standard transport to get our timeout honored if we are using
        # SSL / https
        if isinstance(url, unicode):
            url2 = url.encode('ISO-8859-1')
        else:
            url2 = url
        type, uri = urllib.splittype(url2.lower())
        if type == "https":
            cert_transport = SafeTransportNoCert(timeout=timeout)

    return xmlrpclib.ServerProxy(url, transport=cert_transport,
                                 verbose=verbose, allow_none=allow_none)

#----------------------------------------------------------------------
#
# Everything below here is related to an attempted switch to M2Crypto
# for the SSL infrastructure. In the end, the M2Crypto implementation
# had a number of problems, and those problems were different depending
# on the exact version of Python and M2Crypto in use. We had three
# different platforms (Linux/Python/M2Crypto) which suffered from three
# differents sets of problems.
#
# This code is preserved in case it can be resurrected in the future.
#
# The benefit of M2Crypto integration was single entry of the user's
# private key password. M2Crypto offers SSL Contexts, which allow this
# feature. Python 2.x does not appear to allow any way to do this.
# Python 3.2 introduces SSL Contexts, but that is too new for us to
# rely on.
#
#----------------------------------------------------------------------
import httplib
import socket
import sys
import M2Crypto.SSL

class SafeTransportWithCertM2Crypto(xmlrpclib.SafeTransport):

    def __init__(self, use_datetime=0, ssl_context=None,
                 timeout=socket._GLOBAL_DEFAULT_TIMEOUT):
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
            conn = ContextHTTPSConnectionM2Crypto(chost, context=self._ssl_context,
                                          timeout=self._timeout)
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


class ContextHTTPSConnectionM2Crypto(httplib.HTTPSConnection):

    def __init__(self, host, port=None,
                 strict=None, timeout=socket._GLOBAL_DEFAULT_TIMEOUT,
                 source_address=None, context=None):
        httplib.HTTPConnection.__init__(self, host, port, strict, timeout)
        self.ssl_context = context
        self.sockTimeout = None
        if timeout != socket._GLOBAL_DEFAULT_TIMEOUT:
            self.sockTimeout = M2Crypto.SSL.timeout(sec=float(timeout))

    def connect(self):
        "Connect to a host on a given (SSL) port."
        if not self.ssl_context:
            # Initialize the M2Crypto SSL Context
            self.ssl_context = M2Crypto.SSL.Context()
        self.sock = M2Crypto.SSL.Connection(self.ssl_context)
        self.sock.set_post_connection_check_callback(None)
        if self.sockTimeout is not None:
            self.sock.set_socket_read_timeout(self.sockTimeout)
            self.sock.set_socket_write_timeout(self.sockTimeout)
        self.sock.connect((self.host, self.port))


def make_client_m2crypto(url, ssl_context, verbose=False,
                timeout=socket._GLOBAL_DEFAULT_TIMEOUT,
                allow_none=False):
    """Create an SSL connection to an XML RPC server.
    Returns the XML RPC server proxy.
    """
    cert_transport = None
    if ssl_context:
        cert_transport = SafeTransportWithCertM2Crypto(ssl_context=ssl_context,
                                                       timeout=timeout)
    return xmlrpclib.ServerProxy(url, transport=cert_transport,
                                 verbose=verbose, allow_none=allow_none)
