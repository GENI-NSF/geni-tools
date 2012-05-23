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
from omnilib.frameworks.framework_base import Framework_Base
from omnilib.util.dossl import _do_ssl
from geni.util.urn_util import is_valid_urn, URN, string_to_urn_format
import os
import sys

class Framework(Framework_Base):
    def __init__(self, config, opts):
        Framework_Base.__init__(self,config)        
        config['cert'] = os.path.expanduser(config['cert'])
        if not os.path.exists(config['cert']):
            sys.exit('GCF Framework certfile %s doesnt exist' % config['cert'])
        config['key'] = os.path.expanduser(config['key'])        
        if not os.path.exists(config['key']):
            sys.exit('GCF Framework keyfile %s doesnt exist' % config['key'])
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
            try:
                (self.user_cred, message) = _do_ssl(self, None, ("Create user credential on GCF CH %s" % self.config['ch']), self.ch.CreateUserCredential, self.cert_string)
            except Exception:
                raise 

        return self.user_cred, message
    
    def get_slice_cred(self, slice_urn):
        
#        print "SLICE URN = " + str(slice_urn)
        try:
            (cred, message) = \
                _do_ssl(self, None, \
                            ("GetSliceCredential slice %s on GCF CH %s" % \
                                 (slice_urn, self.config['ch'])), 
                        self.ch.GetSliceCredential, '', self.cert_string, \
                            slice_urn);
        except Exception:
            raise 

        if (cred['code'] == 0):
            cred = cred['value']['slice_credential'];
        else:
            raise Exception("Failed to get slice credential");

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
        try:
            (bool, message) = _do_ssl(self, None, ("Delete Slice %s on GCF CH %s" % (urn, self.config['ch'])), self.ch.DeleteSlice, urn)
        except Exception:
            raise;

        # FIXME: use any message?
        _ = message #Appease eclipse
        return bool
     
    def list_aggregates(self):
        try:
            (sites, message) = _do_ssl(self, None, ("List Aggregates at GCF CH %s" % self.config['ch']), self.ch.ListAggregates)
        except Exception:
            raise;

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
        raise Exception("Can't generate a URN from a slice URN in this framework: need to provide full URN including project name");


    def renew_slice(self, urn, expiration_dt):
        """See framework_base for doc.
        """
        expiration = expiration_dt.isoformat()
        try:
            (bool, message) = _do_ssl(self, None, ("Renew slice %s on GCF CH %s until %s" % (urn, self.config['ch'], expiration_dt)), self.ch.RenewSlice, urn, expiration)
        except Exception:
            raise;

        if bool:
            return expiration_dt
        else:
            # FIXME: use any message?
            _ = message #Appease eclipse
            return None
