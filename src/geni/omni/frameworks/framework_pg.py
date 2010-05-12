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
        
        # TODO: use a real PG key and cert
        self.sa = make_client(self.config['sa'], self.config['key'],
                              self.config['cert'], self.config['verbose'])
        
    def get_user_cred(self):
        return self.sa.GetCredential()
    
    def get_slice_cred(self, urn):
        return self.ch.CreateSlice(urn)
    
    def create_slice(self, urn):    
        return self.get_slice_cred(urn)
    
    def delete_slice(self, urn):
        self.ch.DeleteSlice(urn)
     
    def list_aggregates(self):
        sites = self.ch.ListAggregates()
        aggs = {}
        for (urn, url) in sites:
            aggs[urn] = url
        
        return aggs
