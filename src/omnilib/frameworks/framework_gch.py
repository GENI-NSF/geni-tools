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

# Framework for talking to the GENI Clearinghouse

from omnilib.frameworks.framework_base import Framework_Base
from omnilib.util.dossl import _do_ssl
import omnilib.util.credparsing as credutils
from geni.util.urn_util import is_valid_urn, URN, string_to_urn_format
import os
import sys
from geni.util.ch_interface import *;

class Framework(Framework_Base):
    def __init__(self, config, opts):
        Framework_Base.__init__(self,config)        
        config['cert'] = os.path.expanduser(config['cert'])
        if not os.path.exists(config['cert']):
            sys.exit('GCH Framework certfile %s doesnt exist' % config['cert'])
        config['key'] = os.path.expanduser(config['key'])        
        if not os.path.exists(config['key']):
            sys.exit('GCH Framework keyfile %s doesnt exist' % config['key'])
        if not config.has_key('verbose'):
            config['verbose'] = False
        self.config = config
        
        self.ch = self.make_client(config['ch'], self.key, self.cert,
                                   verbose=config['verbose'])
        self.cert_string = file(config['cert'],'r').read()
        self.user_cred = self.init_user_cred( opts )
        self.logger = config['logger']
        
    def get_user_cred(self):
        message = ""
        if self.user_cred == None:
            (self.user_cred, message) = _do_ssl(self, None, ("Create user credential on GCH CH %s" % self.config['ch']), self.ch.CreateUserCredential, self.cert_string)

        return self.user_cred, message
    
    def get_slice_cred(self, slice_urn):
        
#        print "SLICE URN = " + str(slice_urn)
        (cred, message) = \
            _do_ssl(self, None, \
                        ("GetSliceCredential slice %s on GCH CH %s" % (slice_urn, self.config['ch'])),
                    self.ch.GetSliceCredential, '', self.cert_string, slice_urn);

        if (cred['code'] == 0):
            cred = cred['value']['slice_credential'];
#        print "CRED = " + str(cred)
#        print "MSG = " + str(message)
        # FIXME: use any message?
        _ = message #Appease eclipse
        return cred
    
    def create_slice(self, slice_name, project_id, owner_id):    
        print "In Create Slice"
        try:
            (slice_info, message) = _do_ssl(self, None, \
                                                ("Create Slice %s on GCF CH %s" % \
                                                     (slice_name, self.config['ch'])), 
                                            self.ch.CreateSlice, slice_name, project_id, owner_id)
        except Exception:
            raise;
        if (slice_info['code'] == 0):
            slice_info = slice_info['value'];
        else:
            raise Exception("Falure to create slice " + slice_name);

        return slice_info;

    
    def delete_slice(self, urn):
        (bool, message) = _do_ssl(self, None, ("Delete Slice %s on GCH CH %s" % (urn, self.config['ch'])), self.ch.DeleteSlice, urn)
        # FIXME: use any message?
        _ = message #Appease eclipse
        return bool
     
    def list_aggregates(self):
        (sites, message) = _do_ssl(self, None, ("List Aggregates at GCH CH %s" % self.config['ch']), self.ch.ListAggregates)
        if sites is None:
            # FIXME: use any message?
            _ = message #Appease eclipse
            sites = []
        aggs = {}
        for (urn, url) in sites:
            aggs[urn] = url
        
        return aggs

    
    def slice_name_to_urn(self, name):
        "This method is unsupported in this framework"
        raise Exception("Can't generate a URN from a slice name in this framework")

    def renew_slice(self, urn, expiration_dt):
        """See framework_base for doc.
        """
        expiration = expiration_dt.isoformat()
        (bool, message) = _do_ssl(self, None, ("Renew slice %s on GCH CH %s until %s" % (urn, self.config['ch'], expiration_dt)), self.ch.RenewSlice, urn, expiration)
        if bool:
            return expiration_dt
        else:
            # FIXME: use any message?
            _ = message #Appease eclipse
            return None

    def get_user_cred_struct(self):
        """
        Returns a user credential from the control framework as a string in a struct. And an error message if any.
        Struct is as per AM API v3:
        {
           geni_type: <string>,
           geni_version: <string>,
           geni_value: <the credential as a string>
        }
        """
        cred, message = self.get_user_cred()
        if cred:
            cred = self.wrap_cred(cred)
        return cred, message

    def get_slice_cred_struct(self, urn):
        """
        Retrieve a slice with the given urn and returns the signed
        credential as a string in the AM API v3 struct:
        {
           geni_type: <string>,
           geni_version: <string>,
           geni_value: <the credential as a string>
        }
        """
        cred = self.get_slice_cred(urn)
        return self.wrap_cred(cred)

    def wrap_cred(self, cred):
        """
        Wrap the given cred in the appropriate struct for this framework.
        """
        ret = dict(geni_type="geni_sfa", geni_version="2", geni_value=cred)
        if credutils.is_valid_v3(self.logger, cred):
            ret["geni_version"] = "3"
        return ret
