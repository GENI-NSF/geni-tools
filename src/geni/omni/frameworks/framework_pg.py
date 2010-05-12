#----------------------------------------------------------------------
# Copyright (c) 2010 Raytheon BBN Technologies
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
from ..xmlrpc.client import make_client
import logging
import os

# The key is a converted pkcs12 file. Start with your ProtoGENI
# encrypted.p12 file (found in the .ssl directory or downloaded
# from the emulab site web page). Then convert it to pem using
# openssl:
#
#   $ openssl pkcs12 -in encrypted.p12 -out pgcert.pem -nodes
#
# That command will create a pgcert.pem file, which contains
# the private key you need. This resulting key is not password
# protected. See the openssl pkcs12 man page for more info.


class Framework(object):
    """The ProtoGENI backend for Omni. This class defines the
    interface to the Protogeni Control Framework.
    """

    def __init__(self, config):
        self.logger = logging.getLogger("omni.protogeni")
        config['cert'] = os.path.expanduser(config['cert'])
        config['key'] = os.path.expanduser(config['key'])
        if not config.has_key('verbose'):
            config['verbose'] = False
        self.config = config
        self.logger.debug("Configured with key file %s", config['key'])
        
        self.ch = make_client(self.config['ch'], self.config['key'],
                              self.config['cert'], self.config['verbose'])
        self.sa = make_client(self.config['sa'], self.config['key'],
                              self.config['cert'], self.config['verbose'])
        
    def get_user_cred(self):
        pg_response = self.sa.GetCredential()
        code = pg_response['code']
        if code:
            self.logger.error("Received error code: %d", code)
            output = pg_response['output']
            self.logger.error("Received error message: %s", output)
            return None
        else:
            return pg_response['value']
    
    def get_slice_cred(self, urn):
        return self.ch.CreateSlice(urn)
    
    def create_slice(self, urn):    
        return self.get_slice_cred(urn)
    
    def delete_slice(self, urn):
        self.ch.DeleteSlice(urn)
     
    def list_aggregates(self):
        cred = self.get_user_cred()
        self.logger.debug("Credential = %r", cred)
        args = {}
        args['credential'] = cred
        pg_response = self.ch.ListComponents(args)
        code = pg_response['code']
        if code:
            self.logger.error("Received error code: %d", code)
            output = pg_response['output']
            self.logger.error("Received error message: %s", output)
            return dict()
        # value is a list of dicts, each containing info about an aggregate
        agg_dicts = pg_response['value']
        result = dict()
        for agg_dict in agg_dicts:
            self.logger.debug("Keys: %r", agg_dict.keys())
            result[agg_dict['urn']] = agg_dict['url']
        for key, value in result.items():
            self.logger.debug('Found aggregate %r: %r', key, value)
        # At this point we have ProtoGENI ComponentManagers. We need
        # to iterate through this list and determine if they have the
        # GENI AM enabled. If so, replace the CM URL the AM URL. If
        # not, remove it from the list.
        return dict()
