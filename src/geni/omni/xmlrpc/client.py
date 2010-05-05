import xmlrpclib

class SafeTransportWithCert(xmlrpclib.SafeTransport):

    def __init__(self, use_datetime=0, keyfile=None, certfile=None):
        xmlrpclib.SafeTransport.__init__(self, use_datetime)
        self.__x509 = dict()
        if keyfile:
            self.__x509['key_file'] = keyfile
        if certfile:
            self.__x509['cert_file'] = certfile

    def make_connection(self, host):
        host_tuple = (host, self.__x509)
        return xmlrpclib.SafeTransport.make_connection(self, host_tuple)

def make_client(url, keyfile, certfile, verbose=False):
    """Create an SSL connection to an XML RPC server.
    Returns the XML RPC server proxy.
    """
    cert_transport = SafeTransportWithCert(keyfile=keyfile, certfile=certfile)
    return xmlrpclib.ServerProxy(url, transport=cert_transport,
                                 verbose=verbose)