import base64
import datetime
import dateutil.parser
import logging
import os
import traceback;
import uuid
import xml.dom.minidom as minidom
import zlib

import geni
from geni.util.urn_util import publicid_to_urn
from geni.am.am2 import AggregateManager
from geni.am.am2 import AggregateManagerServer
from geni.am.am2 import ReferenceAggregateManager
from geni.SecureXMLRPCServer import SecureXMLRPCServer
from geni.ch_interface import *
from omnilib.xmlrpc.client import make_client
from resource import Resource
from aggregate import Aggregate
import tempfile
from fakevm import FakeVM

SR_URL = "https://marilac.gpolab.bbn.com/sr/sr_controller.php"


class ProxyAggregateManager(ReferenceAggregateManager):

    "A manager that responds to AM API and passes on requests to another AM"

    # URL of MA controller in CH
    ma_url = None

    # URL of actual AM to which we're connecting
    am_url = None

    # *** TO DO ***
    # keep a cache of member_id => key/cert
    # And a cache of connections

    def __init__(self, am_url, root_cert, urn_authority):
        super(ProxyAggregateManager, self).__init__(root_cert, urn_authority);
        self.am_url = am_url
#        print("SELF.AM_URL = " + self.am_url)
        dictargs = dict(service_type=3) # Member Authority
        ma_services = invokeCH(SR_URL, 'get_services_of_type', self.logger, dictargs);
        if(ma_services['code'] == 0):
            ma_service_row = ma_services['value'][0]
            self.ma_url = ma_service_row['service_url']
            # print("MA_URL " + str(self.ma_url)) 
        self.logger = logging.getLogger('gcf.pxam')

    # Helper function to create a proxy client that talks 
    # to real AM using inside keys
    def make_proxy_client(self):
        pc = self._server.peercert;
#        print(str(pc))
        san = pc.get('subjectAltName');
        uri = None
        uuid = None
        for e in san:
            key = e[0];
            value = e[1];
            if(key == 'URI' and "IDN+" in value):
                uri = value;
            if(key == 'URI' and 'uuid' in value):
                uuid_parts = value.split(':');
                uuid = uuid_parts[2];
#        print "URI = " + str(uri) +  " UUID = " + str(uuid)
        args = dict(member_id = uuid)
        row = invokeCH(self.ma_url, 'lookup_keys_and_certs', self.logger, args)
        
        if(row['code'] == 0):
            row_raw = row['value'];
            private_key = row_raw['private_key']
            certificate = row_raw['certificate']
            (key_fid, key_fname) = tempfile.mkstemp()
            os.write(key_fid, private_key);
            os.close(key_fid);
            (cert_fid, cert_fname) = tempfile.mkstemp();
            os.write(cert_fid, certificate);
            os.close(cert_fid);
            
        client = make_client(self.am_url, key_fname, cert_fname)
        client.key_fname = key_fname;
        client.cert_fname = cert_fname;
        return client;

    def close_proxy_client(self, client):
        os.unlink(client.key_fname);
        os.unlink(client.cert_fname);

    def GetVersion(self, options):
        client = self.make_proxy_client();
        client_ret = client.GetVersion();
        print("GetVersion.CLIENT_RET = " + str(client_ret));
        self.close_proxy_client(client);
        return client_ret;

    def ListResources(self, credentials, options):
        client = self.make_proxy_client();
        # Why do I need to add this?
        options['geni_rspec_version'] = dict(type='geni', version='3');
#        print("OPTS = " + str(options));
#        print("CREDS = " + str(credentials));
        client_ret = client.ListResources(credentials, options);
        print("ListResources.CLIENT_RET = " + str(client_ret));
        # Why do I need to do this?
        client_ret = client_ret['value'];
        self.close_proxy_client(client);
        return client_ret;

    def CreateSliver(self, slice_urn, credentials, rspec, users, options):
#        print("URN = " + str(slice_urn));
#        print("OPTS = " + str(options));
#        print("CREDS = " + str(credentials));
#        print("RSPEC = " + str(rspec));
#        print("USERS = " + str(users));
        client = self.make_proxy_client();
        client_ret = client.CreateSliver(slice_urn, credentials, rspec, users, options);
        print("CreateSliver.CLIENT_RET = " + str(client_ret));
        self.close_proxy_client(client);
        return client_ret;
            
    def DeleteSliver(self, slice_urn, credentials, options):
        client = self.make_proxy_client();
        client_ret = client.DeleteSliver(slice_urn, credentials, options);
        self.close_proxy_client(client);
        return client_ret;

    def SliverStatus(self, slice_urn, credentials, options):
        client = self.make_proxy_client();
        client_ret = client.SliverStatus(slice_urn, credentials, options);
        self.close_proxy_client(client);
        return client_ret;

    def RenewSliver(self, slice_urn, credentials, expiration_time, options):
        client = self.make_proxy_client();
        client_ret = client.RenewSliver(slice_urn, credentials, expiration_time, options);
        self.close_proxy_client(client);
        return client_ret;

    def Shutdown(self, slice_urn, credentials, options):
        client = self.make_proxy_client();
        client_ret = client.Shutdown(slice_urn, credentials, options);
        self.close_proxy_client(client);
        return client_ret;

class ProxyAggregateManagerServer(AggregateManagerServer):
    "A server that provides the AM API to tools, but passes requests"
    "to a real configured AM, after logging and authorizing"

    def __init__(self, addr, am_url, keyfile=None, certfile=None,
                 trust_roots_dir=None,
                 ca_certs=None, base_name=None):
        # ca_certs arg here must be a file of concatenated certs
        if ca_certs is None:
            raise Exception('Missing CA Certs')
        elif not os.path.isfile(os.path.expanduser(ca_certs)):
            raise Exception('CA Certs must be an existing file of accepted root certs: %s' % ca_certs)

        delegate = ProxyAggregateManager(am_url, trust_roots_dir, base_name)
        self._server = SecureXMLRPCServer(addr, keyfile=keyfile,
                                          certfile=certfile, ca_certs=ca_certs)
        self._server.register_instance(AggregateManager(delegate))
        # Set the server on the delegate so it can access the
        # client certificate.
        delegate._server = self._server

        if not base_name is None:
            global RESOURCE_NAMESPACE
            RESOURCE_NAMESPACE = base_name

   
