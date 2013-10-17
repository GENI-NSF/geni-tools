#----------------------------------------------------------------------
# Copyright (c) 2011-2013 Raytheon BBN Technologies
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
import omnilib.util.credparsing as credutils

from geni.util.urn_util import is_valid_urn, URN, string_to_urn_format

import os
import string
import sys
from pprint import pprint

class Framework(Framework_Base):
    def __init__(self, config, opts):
        Framework_Base.__init__(self,config)        
        config['cert'] = os.path.expanduser(config['cert'])
        if not os.path.exists(config['cert']):
            sys.exit('CHAPI Framework certfile %s doesnt exist' % config['cert'])
        if not os.path.getsize(config['cert']) > 0:
            sys.exit('CHAPI Framework certfile %s is empty' % config['cert'])
        config['key'] = os.path.expanduser(config['key'])        
        if not os.path.exists(config['key']):
            sys.exit('CHAPI Framework keyfile %s doesnt exist' % config['key'])
        if not os.path.getsize(config['key']) > 0:
            sys.exit('CHAPI Framework keyfile %s is empty' % config['key'])
        if not config.has_key('verbose'):
            config['verbose'] = False
        self.config = config
        
        self.ch = self.make_client(config['ch']+'/CH', self.key, self.cert,
                                   verbose=config['verbose'])
        self.ma = self.make_client(config['ch']+'/MA', self.key, self.cert,
                                   verbose=config['verbose'])
        self.sa = self.make_client(config['ch']+'/SA', self.key, self.cert,
                                   verbose=config['verbose'])

        self.cert_string = file(config['cert'],'r').read()
        self.user_cred = self.init_user_cred( opts )
        self.logger = config['logger']

    def get_user_cred(self):
        message = ""
        if self.user_cred == None:
            self.logger.debug("Getting user credential from CHAPI MA %s", self.config['ch'])
            (res, message) = _do_ssl(self, None, ("lookup public member info on CHAPI CH %s" % self.config['ch']),
                                     self.ma.lookup_public_member_info, 
                                     self.cert_string,
                                     {'match':{'USER_URN':[]}})
        if res is not None:
            if res['output'] is not None:
                message = res['output']
            self.user_cred = res['value']

        return self.user_cred, message
    
    def get_slice_cred(self, urn):
        self.get_user_cred()
        scred = ''
        if self.user_cred:
            scred = self.user_cred
        (res, message) = _do_ssl(self, None, ("Get slice credentials  %s on CHAPI SA %s" % (urn, self.config['ch'])),
                                  self.sa.lookup_slices,
                                  scred,
                                  {'match':{'SLICE_URN':[urn]},
                                   'filter':['SLICE_CREDENTIAL']})
        cred = None
        if res is not None:
            if res['output'] is not None:
                message = res['output']
                cred = res['value']
        if message is not None:
            self.logger.error(message)
        return cred
    
    def create_slice(self, urn):
        # TODO: cred is user's for create?
        self.get_user_cred()
        scred = ''
        if self.user_cred is not None:
            scred = self.user_cred

        # how do we get this information into options?
        options = {'SLICE_NAME': urn,
                   'SLICE_DESCRIPTION': "",
                   'SLICE_EMAIL': "",
                   'PROJECT_URN': urn}
        (res, message) = _do_ssl(self, None, ("Create slice %s on CHAPI SA %s" % (urn, self.config['ch'])),
                                 self.sa.create_slice, scred, options)
        cred = None
        if res is not None:
            if res['output'] is not None:
                message = res['output']
                d = res['value']
                if d is not None:
                    cred = d['SLICE_CREDENTIAL']
        if message is not None:
            self.logger.error(message)
        return cred
    
    def delete_slice(self, urn):
        self.logger.error("CHAPI SA does not allow delete_slice")
        return False
     
    def list_aggregates(self):
        # TODO: list of field names from getVersion - should we get all or assume we have URN and URL
        (res, message) = _do_ssl(self, None, ("List Aggregates at CHAPI CH %s" % self.config['ch']), 
                                 self.ch.get_aggregates,
                                 {'filter':['SERVICE_URN', 'SERVICE_URL']})
        if message:
            self.logger.warn(message)
        aggs = dict()
        if res['value'] is not None:
            for d in res['value']:
                aggs[d['SERVICE_URN']] = d['SERVICE_URL']
        
        return aggs

    def list_my_slices(self, user):
        '''List slices owned by the user (name or URN) provided, returning a list of slice URNs.'''

        if user is None or user.strip() == '':
            raise Exception('Empty user name')

        # construct a urn from that user
        if is_valid_urn(user):
            # FIXME: Validate type, authority?
            userurn = user
        else:
            if not self.config.has_key('authority'):
                raise Exception("Invalid configuration: no authority defined")

            auth = self.config['authority']
            userurn = URN(auth, "user", user).urn_string()

        # TODO: sa.lookup_slices (username), then ma.lookup_public/private_member_info 
        # TODO: can we filter lookup_slices with username directly, or do we need to go back to MA?

        # invoke ListMySlices(urn)
        (slices, message) = _do_ssl(self, None, ("List Slices for %s at CHAPI SA %s" % (user, self.config['ch'])), 
                                    self.sa.ListMySlices, userurn)
        # FIXME: use any message?
        _ = message #Appease eclipse

#        # Return is a urn. Strip out the name
#        slicenames = list()
#        if slices and isinstance(slices, list):
#            for slice in slices:
#                slicelower = string.lower(slice)
#                if not string.find(slicelower, "+slice+"):
#                    continue
#                slicename = slice[string.index(slicelower,"+slice+") + len("+slice+"):]
#                slicenames.append(slicename)
#        return slicenames

        return slices
    
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
        cred = self.get_slice_cred(urn)
        (res, message) = _do_ssl(self, None, ("Renew slice %s on CHAPI SA %s until %s" % (urn, self.config['ch'], expiration_dt)), 
                                  self.sa.update_slice, urn, cred, {'SLICE_EXPIRATION':expiration})

        b = False
        if res is not None:
            if res['code'] == 0:
                b = True
            else:
                message = res['output']
        if message is not None:
            self.logger.error(message)

        if b:
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
        if isinstance(cred, dict):
            self.logger.warn("Called wrap on a cred that's already a dict? %s", cred)
            return cred
        elif not isinstance(cred, str):
            self.logger.warn("Called wrap on non string cred? Stringify. %s", cred)
            cred = str(cred)
        ret = dict(geni_type="geni_sfa", geni_version="2", geni_value=cred)
        if credutils.is_valid_v3(self.logger, cred):
            ret["geni_version"] = "3"
        return ret

    def get_version(self):
        pl_response = dict()
        versionstruct = dict()
        (pl_response, message) = _do_ssl(self, None, ("GetVersion of CHAPI CH %s using cert %s" % (self.config['ch'], self.config['cert'])), self.ch.get_version)
        _ = message #Appease eclipse
        if pl_response is None:
            self.logger.error("Failed to get version of CHAPI CH: %s", message)
            # FIXME: Return error message?
            return None, message
        if isinstance(pl_response, dict) and pl_response.has_key('code'):
            code = pl_response['code']
            if code:
                self.logger.error("Failed to get version of CHAPI CH: Received error code: %d", code)
                output = pl_response['output']
                self.logger.error("Received error message: %s", output)
            else:
                versionstruct = pl_response['value']
        else:
            versionstruct = pl_response
        return versionstruct, message
