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
from omnilib.xmlrpc.client import make_client
from omnilib.frameworks.framework_base import Framework_Base
from omnilib.util.dossl import _do_ssl
from geni.util.urn_util import is_valid_urn, URN, string_to_urn_format
import logging
import os
import time
import sys


# FIXME: Use the constant from namespace
URN_PREFIX = "urn:publicid:IDN"

DEFAULT_SLICE_TIME = 86400 * 14 # 2 weeks in seconds

# FIXME: Use sfa util code!
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

def create_selfsigned_cert2(framework, filename, user, key):
    """ Creates a self-signed cert with CN of issuer and subject = user.
    The file is stored in 'filename' and the public/private key is found in key """
    
    from OpenSSL import crypto
    # Create a self-signed cert to talk to the registry with
    cert = crypto.X509()
    cert.set_serial_number(3)
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(60*60*24*365*5) # five years
    cert.set_version(2)

    req = crypto.X509Req()
    subj = req.get_subject()
    setattr(subj, "CN", user)
    cert.set_subject(subj)

    key = _do_ssl(framework, None, "Load private key from %s" % key, crypto.load_privatekey, crypto.FILETYPE_PEM, file(key).read())
    cert.set_pubkey(key)

    cert.set_issuer(subj)
    cert.sign(key, "md5")
    
        
    f = open(filename,'w')
    f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))
    f.close()
    

def create_selfsigned_cert(filename, user, key):
    ''' Unused function'''
    config = """[ req ]
            distinguished_name = req_distinguished_name
            attributes = req_attributes
            prompt = no
            
            [ req_distinguished_name ]
            C = US
            ST = .
            L = .
            O = GENI
            OU = GENI
            CN = %s
            emailAddress = .
            
            [ req_attributes ]
            unstructuredName =""" % user
    
    f = open("/tmp/tmp_openssl_config",'w')
    f.write(config)
    f.close()
    os.popen('openssl req -new -x509 -nodes -sha1 -config /tmp/tmp_openssl_config -key %s > %s' % (key, filename))
    os.remove("/tmp/tmp_openssl_config")
    

class Framework(Framework_Base):
    def __init__(self, config):
        config['cert'] = os.path.expanduser(config['cert'])
        config['key'] = os.path.expanduser(config['key'])        

        self.config = config
        self.logger = logging.getLogger('omni.sfa')

        # Download a cert from PLC if necessary
        if not os.path.exists(config['cert']):
            res = raw_input("Your certificate file (%s) was not found, would you like me to download it for you to %s? (Y/n)" % (config['cert'],config['cert']))
            if not res.lower().startswith('n'):
                # Create a self-signed cert to talk to the registry with
                create_selfsigned_cert2(self, config['cert'], config['user'], config['key'])
                try:
                    # use the self signed cert to get the gid
                    self.registry = make_client(config['registry'], self.ssl_context())
                    self.user_cred = None
                    self.cert_string = file(config['cert'],'r').read()
                    cred = self.get_user_cred()
                    if cred is None:
                        os.remove(self.config['cert'])
                        sys.exit("Failed to download your user credential from the PL registry")
                    gid = 'Not found'
                    res = _do_ssl(self, None, ("Look up GID for user %s from SFA registry %s" % (config['user'], config['registry'])), self.registry.Resolve, config['user'], cred)
                    if res is None:
                        os.remove(self.config['cert'])
                        sys.exit("Failed to download your user certificate from the PL registry")
                    elif type(res) is dict:
                        gid = res['gid']
                    else:
                        gid = res[0]['gid']
                    # Finally, copy the gid to the cert location
                    f = open(self.config['cert'],'w')
                    f.write(gid)
                    f.close()
                except Exception, exc:
                    os.remove(self.config['cert'])
                    sys.exit("Failed to download a user certificate from the PL registry: %s" % exc)
            else:            
                sys.exit("SFA Framework certfile %s doesn't exist" % config['cert'])
                
                
        if not os.path.exists(config['key']):
            sys.exit('SFA Framework keyfile %s doesnt exist' % config['key'])

        Framework_Base.__init__(self,config)        

        if not config.has_key('verbose'):
            config['verbose'] = False
        self.logger.info('SFA Registry: %s', config['registry'])
        self.registry = make_client(config['registry'], self.ssl_context(), allow_none=True)
        self.logger.info('SFA Slice Manager: %s', config['slicemgr'])
        self.slicemgr = make_client(config['slicemgr'], self.ssl_context())
        self.cert_string = file(config['cert'],'r').read()
        self.user_cred = None
        
    def get_user_cred(self):
        if self.user_cred is None:
            self.user_cred = _do_ssl(self, None, ("Get SFA user credential from registry %s for user %s using cert file %s" % (self.config['registry'], self.config['user'], self.config['cert'])), self.registry.GetSelfCredential, self.cert_string, self.config['user'], "user")
        return self.user_cred
    
    def get_slice_cred(self, urn):
        user_cred = self.get_user_cred()
        if user_cred is None:
            self.logger.error("Cannot get a slice credential without a user credential")
            return None

        return _do_ssl(self, None, ("Get SFA slice credential for slice %s from registry %s" % (urn, self.config['registry'])), self.registry.GetCredential, user_cred, urn, 'slice')
    
    def create_slice(self, urn):    
        ''' Gets the credential for a slice, creating the slice 
            if it doesn't already exist
        '''
        hrn, type = urn_to_hrn(urn)

        slice_cred = self.get_slice_cred(urn)
        if slice_cred is None:
            # Slice doesn't exist, create it
            user_cred = self.get_user_cred()
            if user_cred is None:
                self.logger.error("Cannot create the SFA slice - could not get your user credential.")
                return None

            auth_cred = _do_ssl(self, None, ("Get SFA authority credential from registry %s for authority %s" % (self.config['registry'], self.config['authority'])), self.registry.GetCredential, user_cred, self.config['authority'], "authority")
            if auth_cred is None:
                self.logger.error("Cannot create SFA slice - could not get the authority credential.")
                return None

            # Note this is in UTC
            expiration =  int(time.mktime(time.gmtime())) + DEFAULT_SLICE_TIME 
            authority = self.config['authority']
            user = self.config['user']
                           
            record = {'peer_authority': '', u'description': u'a slice', u'url': \
                      u'http://www.testslice.com', 'expires': "%d" % expiration, \
                      u'authority': u'%s' % authority, u'researcher': [u'%s' % user], \
                      'hrn': u'%s' % hrn, u'PI': [u'%s' % user], 'type': u'slice', \
                      u'name': u'%s' % hrn}
    
            _do_ssl(self, None, ("Register new slice %s at SFA registry %s" % (urn, self.config['registry'])), self.registry.Register, record, auth_cred)

            # For some reason the slice doesn't seem to have the correct expiration time, 
            # so call renew_slice
            #self.renew_slice(urn, datetime.datetime.utcnow() + datetime.timedelta(seconds=DEFAULT_SLICE_TIME))            

            slice_cred = self.get_slice_cred(urn)

        #print slice_cred
        return slice_cred
        
    
    def delete_slice(self, urn):
        ''' Deletes the slice '''
        user_cred = self.get_user_cred()
        if user_cred is None:
            self.logger.error("Cannot delete SFA slice - could not get your user credential.")
            return None

        auth_cred = _do_ssl(self, None, ("Get SFA authority cred for %s from registry %s" % (self.config['authority'], self.config['registry'])), self.registry.GetCredential, user_cred, self.config['authority'], 'authority')
        if auth_cred is None:
            self.logger.error("Cannot delete SFA slice - could not retrieve authority credential")
            return None
     
        return _do_ssl(self, None, ("Delete SFA slice %s at registry %s" % (urn, self.config['registry'])), self.registry.Remove, urn, auth_cred, 'slice')
 
    def renew_slice(self, urn, requested_expiration):
        """Renew a slice.
        
        urn is framework urn, already converted via slice_name_to_urn.
        requested_expiration is a datetime object.
        
        Returns the expiration date as a datetime. If there is an error,
        print it and return None.
        """
        slice_cred = self.get_slice_cred(urn)
        if slice_cred is None:
            self.logger.error("Failed to renew slice %s: could not get a slice credential", urn)
            return None
        user_cred = self.get_user_cred()
        if user_cred is None:
            self.logger.error("Failed to renew slice %s: could not get a user credential", urn)
            return None
        try:
            records = _do_ssl(self, None, ("Lookup SFA slice %s at registry %s" % (urn, self.config['registry'])), self.registry.Resolve, urn, user_cred)
            if records != None:
                if type(records) is not dict:
                    self.logger.debug("Taking first record returned by SFA registry.resolve")
                    records = records[0]
                else:
                    self.logger.debug("Exactly 1 record returned by SFA registry.resolve as a dict")
                slice_record = records[0]
                slice_record['expires'] = int(time.mktime(requested_expiration.timetuple()))
            else:
                self.logger.warning("Failed to find SFA slice record. Cannot renew slice %s", urn)
                return None
            res = _do_ssl(self, None, ("Renew SFA slice %s at registry %s" % (urn, self.config['registry'])), self.registry.Update, slice_record, slice_cred)
            if res == 1:
                return requested_expiration
            else:
                self.logger.warning("Failed to renew slice %s" % urn)
                return None

        except Exception, exc:
            self.logger.warning("Failed to renew slice %s: %s" , urn, exc)
            return None
       
    def list_aggregates(self):
        aggs = {}
        user_cred = self.get_user_cred()
        if user_cred is None:
            self.logger.error("Cannot list aggregates from SFA registry without a user credential")
            return aggs

        sites = _do_ssl(self, None, "List Aggregates at SFA registry %s" % self.config['registry'], self.registry.get_aggregates, user_cred)
        if sites is None:
            sites = []
        for site in sites:
            aggs[site['urn']] = site['url']

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
                auth = self.config['authority'].replace('.', ':')
                urn_fmt_auth = string_to_urn_format(urn.getAuthority())
                if urn_fmt_auth != auth:
                    raise Exception("Invalid slice name: slice' authority (%s) doesn't match current configured authority (%s)" % (urn_fmt_auth, auth))
            return name

        if not self.config.has_key('authority'):
            raise Exception("Invalid configuration: no authority defined")

        auth = self.config['authority'].replace('.',':')

        return URN(auth, "slice", name).urn_string()
        
