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

from __future__ import absolute_import

import os
import sys

'''Openflow / Expedient as CH. Follows GCF model. https://server:443/expedient_geni/clearinghouse/rpc/'''
from .framework_base import Framework_Base
from ..util.dossl import _do_ssl
from ...geni.util.urn_util import is_valid_urn, URN, string_to_urn_format


class Framework(Framework_Base):
    def __init__(self, config):
        Framework_Base.__init__(self,config)        
        config['cert'] = os.path.expanduser(config['cert'])
        if not os.path.exists(config['cert']):
            sys.exit('OpenFlow Framework certfile %s doesnt exist' % config['cert'])
        if not os.path.getsize(config['cert']) > 0:
            sys.exit('OpenFlow Framework certfile %s is empty' % config['cert'])
        config['key'] = os.path.expanduser(config['key'])        
        if not os.path.exists(config['key']):
            sys.exit('OpenFlow Framework keyfile %s doesnt exist' % config['key'])
        if not os.path.getsize(config['key']) > 0:
            sys.exit('OpenFlow Framework keyfile %s is empty' % config['key'])
        if not config.has_key('verbose'):
            config['verbose'] = False
        self.config = config
        
        self.ch = self.make_client(config['ch'], self.key, self.cert,
                                   verbose=config['verbose'])
        self.cert_string = file(config['cert'],'r').read()
        self.user_cred = None
        self.logger = config['logger']
        
    def get_user_cred(self):
        message = ""
        if self.user_cred == None:
            (self.user_cred, message) = _do_ssl(self, None, ("Create user credential on OpenFlow CH %s" % self.config['ch']), self.ch.CreateUserCredential, self.cert_string)
        return self.user_cred, message
    
    def get_slice_cred(self, urn):
        (cred, message) = _do_ssl(self, None, ("Create slice %s on OpenFlow CH %s" % (urn, self.config['ch'])), self.ch.CreateSlice, urn)
        _ = message #Appease eclipse
        return cred
    
    def create_slice(self, urn):    
        return self.get_slice_cred(urn)
    
    def delete_slice(self, urn):
        (bool, message) = _do_ssl(self, None, ("Delete Slice %s on OpenFlow CH %s" % (urn, self.config['ch'])), self.ch.DeleteSlice, urn)
        _ = message #Appease eclipse
        return bool
     
    def list_aggregates(self):
        # 10/7/10: We believe ListAggregates is not implemented yet.
        # So either we log an error and return an empty list, or we just raise the exception
        # I choose to leave it alone - raise the exception. And when it works, it will work.
        (sites, message) = _do_ssl(self, None, ("List Aggregates at OpenFlow CH %s" % self.config['ch']), self.ch.ListAggregates)
        _ = message #Appease eclipse
        if sites is None:
            sites = []
        aggs = {}
        for (urn, url) in sites:
            aggs[urn] = url
        
        return aggs

    
    def slice_name_to_urn(self, name):
        """Convert a slice name to a slice urn."""

        if name is None or name.strip() == '':
            raise Exception('Empty slice name')

        if is_valid_urn(name):
            urn = URN(None, None, None, name)
            if not urn.getType() == "slice":
                raise Exception("Invalid Slice name: got a non Slice URN %s", name)
            # if config has an authority, make sure it matches
            if self.config.has_key('authority'):
                auth = self.config['authority']
                urn_fmt_auth = string_to_urn_format(urn.getAuthority())
                if urn_fmt_auth != auth:
                    self.logger.warn("CAREFUL: slice' authority (%s) doesn't match current configured authority (%s)" % (urn_fmt_auth, auth))
                    self.logger.info("This may be OK though if you are using delegated slice credentials...")
#                    raise Exception("Invalid slice name: slice' authority (%s) doesn't match current configured authority (%s)" % (urn_fmt_auth, auth))
            return name

        if not self.config.has_key('authority'):
            raise Exception("Invalid configuration: no authority defined")

        auth = self.config['authority']
        return URN(auth, "slice", name).urn_string()

    def renew_slice(self, urn, expiration_dt):
        """See framework_base for doc.
        """
        expiration = expiration_dt.isoformat()
        (bool, message) = _do_ssl(self, None, ("Renew slice %s on OpenFlow CH %s until %s" % (urn, self.config['ch'], expiration_dt)), self.ch.RenewSlice, urn, expiration)
        _ = message #Appease eclipse
        if bool:
            return expiration_dt
        else:
            return None
