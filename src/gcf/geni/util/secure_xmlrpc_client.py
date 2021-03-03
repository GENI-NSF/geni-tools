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
import httplib
import os
import socket
import ssl
import urllib
import xmlrpclib

class SafeTransportWithCert(xmlrpclib.SafeTransport):
    '''Sample client for talking XMLRPC over SSL supplying
    a client X509 identity certificate.'''

    def __init__(self, use_datetime=0, keyfile=None, certfile=None,
                 timeout=None, ssl_version=ssl.PROTOCOL_TLS, ciphers=None):
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
        self.ssl_version = ssl_version
        self.ciphers = ciphers
        self._connection = (None, None)

    def make_connection(self, host):
        host_tuple = (host, self.__x509)
        if self._connection and host_tuple == self._connection[0]:
            return self._connection[1]
        #conn = xmlrpclib.SafeTransport.make_connection(self, host_tuple)
        chost, self._extra_headers, x509 = self.get_host_info(host_tuple)
        # HTTPSConnection instead of HTTPS is python issue6267 of June 2009 - before the 2.7 maint branch
        import sys
        if sys.version_info < (2,7,0):
            self._connection = host_tuple, TLS1P26HTTPS(chost, None, **(x509 or {}))
        else:
            self._connection = host_tuple, TLS1HTTPSConnection(chost, None, **(x509 or {}))
        conn = self._connection[1]
        if hasattr(conn, '_conn'):
            # Python 2.6
            if self._timeout:
                conn._conn.timeout = self._timeout
            conn._conn.ssl_version = self.ssl_version
            conn._conn.ciphers = self.ciphers
        else:
            # Python 2.7
            if self._timeout:
                conn.timeout = self._timeout
            conn.ssl_version = self.ssl_version
            conn.ciphers = self.ciphers
        return conn

# A custom HTTPSConnection that calls ssl.wrap_socket specifying the desired ssl_version, defaulting to PROTOCOL_TLS instead of PROTOTOCOL_SSLv23
# Used directly by our SafeTransport, and indirectly by the below TLS1P26HTTPS
class TLS1HTTPSConnection(httplib.HTTPSConnection):
    def __init__(self, host, port=None, key_file=None, cert_file=None, strict=None, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, source_address=None, ssl_version=ssl.PROTOCOL_TLS, ciphers=None):
        import sys
        if sys.version_info >= (2,7,0):
            # source_address added for python issue 3972 Jan 2010. Note the 2.7 maint branch was Jul 2010. This is first seen in 2.7 alpha 2.
            httplib.HTTPSConnection.__init__(self, host, port, key_file, cert_file, strict, timeout, source_address)
        else:
            httplib.HTTPSConnection.__init__(self, host, port, key_file, cert_file, strict, timeout)
        self.ssl_version = ssl_version
        self.ciphers = ciphers

    def connect(self):
        import sys
        if sys.version_info >= (2,7,0):
            sock = socket.create_connection((self.host, self.port), self.timeout, self.source_address)
        else:
            sock = socket.create_connection((self.host, self.port), self.timeout)

        # Note these next fixes require python at least from Oct 2009 so 2.6.3
        if sys.version_info >= (2,6,3):
            if self._tunnel_host:
                self.sock = sock
                self._tunnel()

        # Force use of TLSv1 with PROTOCOL_TLS
        # Default is PROTOCOL_SSLv23 which allows either 2 or 3
        # Another option is PROTOCOL_SSLv3
        # We want TLS1 to avoid POODLE vulnerability. In addition, some client/server combinations fail the handshake
        # if you start with SSL23 and the server wants TLS1. See geni-tools issue #745
        if self.ssl_version is None:
            #print "Requested a None ssl version"
            self.ssl_version = ssl.PROTOCOL_TLS
        #print "Wrapping socket to use SSL version %s" % ssl._PROTOCOL_NAMES[self.ssl_version]

        if sys.version_info >= (2,7,0):
            #if self.ciphers is None:
            #    print "Using cipherlist: 'DEFAULT:!aNULL:!eNULL:!LOW:!EXPORT:!SSLv2'"
            #else:
            #    print "Using cipherlist: '%s'" % self.ciphers
            self.sock = ssl.wrap_socket(sock, self.key_file, self.cert_file, ssl_version=self.ssl_version, ciphers=self.ciphers)
        else:
            # Python 2.6 doesn't let you specify the ciphers to use
            self.sock = ssl.wrap_socket(sock, self.key_file, self.cert_file, ssl_version=self.ssl_version)

# For Python2.6 safe transport, use our custom HTTPSConnection
class TLS1P26HTTPS(httplib.HTTPS):
    _connection_class = TLS1HTTPSConnection
    def __init__(self, host='', port=None, key_file=None, cert_file=None,
                 strict=None):
        httplib.HTTPS.__init__(self, host, port, key_file, cert_file, strict)

class SafeTransportNoCert(xmlrpclib.SafeTransport):
    # A standard SafeTransport that honors the requested SSL timeout
    def __init__(self, use_datetime=0, timeout=None, ssl_version=ssl.PROTOCOL_TLS, ciphers=None):
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
        self.ssl_version = ssl_version
        self.ciphers = ciphers

    def make_connection(self, host):
        host_tuple = (host, self.__x509)
        if self._connection and host_tuple == self._connection[0]:
            return self._connection[1]
        #conn = xmlrpclib.SafeTransport.make_connection(self, host_tuple)
        chost, self._extra_headers, x509 = self.get_host_info(host_tuple)
        import sys
        if sys.version_info < (2,7,0):
            self._connection = host_tuple, TLS1P26HTTPS(chost, None, **(x509 or {}))
        else:
            self._connection = host_tuple, TLS1HTTPSConnection(chost, None, **(x509 or {}))
        conn = self._connection[1]
        if hasattr(conn, '_conn'):
            # Python 2.6
            if self._timeout:
                conn._conn.timeout = self._timeout
            conn._conn.ssl_version = self.ssl_version
            conn._conn.ciphers = self.ciphers
        else:
            # Python 2.7
            if self._timeout:
                conn.timeout = self._timeout
            conn.ssl_version = self.ssl_version
            conn.ciphers = self.ciphers
        return conn

# ssl_version would otherwise default to PROTOCOL_SSLv23, but here we insist on TLSv1 (which secretly maybe also allows SSLv3).
# Leave out ciphers to get the default of 'DEFAULT:!aNULL:!eNULL:!LOW:!EXPORT:!SSLv2',
# but we can probably do better. Consider
# "HIGH:MEDIUM:!RC4" (assuming disabled SSLv2 and v3)
# or else "HIGH:MEDIUM:!ADH:!SSLv2:!MD5:!RC4:@STRENGTH", which is what we use (though python2.6 ignores it).
# By specifying TLSv1 this works at servers that have disabled SSLv2 and SSLv3.
def make_client(url, keyfile, certfile, verbose=False, timeout=None,
                allow_none=False, ssl_version=ssl.PROTOCOL_TLS, ciphers="HIGH:MEDIUM:!ADH:!SSLv2:!MD5:!RC4:@STRENGTH"):
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
                                               timeout=timeout, ssl_version=ssl_version, ciphers=ciphers)
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
            cert_transport = SafeTransportNoCert(timeout=timeout, ssl_version=ssl_version, ciphers=ciphers)

    return xmlrpclib.ServerProxy(url, transport=cert_transport,
                                 verbose=verbose, allow_none=allow_none)
