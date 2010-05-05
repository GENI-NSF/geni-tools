from geni.omni.xmlrpc.client import make_client
import os
import time

class Framework(object):
    def __init__(self, config):
        config['cert'] = os.path.expanduser(config['cert'])
        config['key'] = os.path.expanduser(config['key'])        
        self.config = config
        
        self.ch = make_client(config['ch'], config['key'], config['cert'])
        self.cert_string = file(config['cert'],'r').read()
        
    def get_user_cred(self):
        return self.ch.create_user_credential(self.cert_string)
    
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
