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
from geni.omni.xmlrpc.client import make_client
from geni.omni.frameworks.framework_base import Framework_Base
import os
import time

class Framework(Framework_Base):
    def __init__(self, config):
        config['cert'] = os.path.expanduser(config['cert'])
        config['key'] = os.path.expanduser(config['key'])        
        self.config = config
        
        self.ch = make_client(config['ch'], config['key'], config['cert'])
        self.cert_string = file(config['cert'],'r').read()
        
    def get_user_cred(self):
        return self.ch.CreateUserCredential(self.cert_string)
    
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
