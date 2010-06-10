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

URN_PREFIX = "urn:publicid:IDN"

def urn_to_hrn(urn):
    """
    convert a urn to hrn
    return a tuple (hrn, type)
    """

    # if this is already a hrn dont do anything
    if not urn or not urn.startswith(URN_PREFIX):
        return urn, None

    name = urn[len(URN_PREFIX):]
    hrn_parts = name.split("+")
    
    # type is always the second to last element in the list
    type = hrn_parts.pop(-2)

    # convert hrn_parts (list) into hrn (str) by doing the following    
    # remove blank elements
    # replace ':' with '.'
    # join list elements using '.'
    hrn = '.'.join([part.replace(':', '.') for part in hrn_parts if part]) 
   
    return str(hrn), str(type) 

def get_authority(xrn):
    hrn, type = urn_to_hrn(xrn)
    if type and type == 'authority':
        return hrn
    
    parts = hrn.split(".")
    return ".".join(parts[:-1])

def get_leaf(hrn):
    parts = hrn.split(".")
    return ".".join(parts[-1:])

def hrn_to_urn(hrn, type=None):
    """
    convert an hrn and type to a urn string
    """
    # if  this is already a urn dont do anything 
    if not hrn or hrn.startswith(URN_PREFIX):
        return hrn

    authority = get_authority(hrn)
    name = get_leaf(hrn)
    
    if authority.startswith("plc"):
        if type == None:
            urn = "+".join(['',authority.replace('.',':'),name])
        else:
            urn = "+".join(['',authority.replace('.',':'),type,name])

    else:
        urn = "+".join(['',authority,type,name])
        
    return URN_PREFIX + urn

class Framework(Framework_Base):
    def __init__(self, config):
        config['cert'] = os.path.expanduser(config['cert'])
        config['key'] = os.path.expanduser(config['key'])        
        self.config = config
        
        self.registry = make_client(config['registry'], config['key'], config['cert'])
        self.slicemgr = make_client(config['slicemgr'], config['key'], config['cert'])
        self.cert_string = file(config['cert'],'r').read()
        
    def get_user_cred(self):
        return self.registry.get_self_credential(self.cert_string, "user", self.config['user'])
    
    def get_slice_cred(self, urn):
        user_cred = self.get_user_cred()
        return self.registry.get_credential(user_cred, 'slice', urn)
    
    def create_slice(self, urn):    
        ''' Gets the credential for a slice, creating the slice 
            if it doesn't already exist
        '''
        hrn, type = urn_to_hrn(urn)

        try:
            slice_cred = self.get_slice_cred(urn)
        except:
            # Slice doesn't exist, create it
            user_cred = self.get_user_cred()
            auth_cred = self.registry.get_credential(user_cred, "authority", self.config['authority'])
            expiration = int(time.time()) + 60 * 60 * 24
            authority = self.config['authority']
            user = self.config['user']
                           
            record = {'peer_authority': '', u'description': u'a slice', u'url': \
                      u'http://www.testslice.com', u'expires': u'%s' % expiration, \
                      u'authority': u'%s' % authority, u'researcher': [u'%s' % user], \
                      'hrn': u'%s' % hrn, u'PI': [u'%s' % user], 'type': u'slice', \
                      u'name': u'%s' % hrn}
    
            self.registry.register(auth_cred, record)
            slice_cred = self.get_slice_cred(urn)

        return slice_cred
        
    
    def delete_slice(self, urn):
        ''' Deletes the slice '''
        user_cred = self.get_user_cred()
        auth_cred = self.registry.get_credential(user_cred, "authority", self.config['authority'])
     
        return self.registry.remove(auth_cred, 'slice', urn)
 
    
    def list_aggregates(self):
        user_cred = self.get_user_cred()
        sites = self.registry.get_geni_aggregates(user_cred)
        aggs = {}
        
        for site in sites:
            if not site.has_key('url'):
                url = site['addr'] + ":" + str(site['port'])
                if not url.startswith('http://'):
                    url = 'http://' + url
            else:
                url = site['url']
            aggs[site['urn']] = url

        return aggs
