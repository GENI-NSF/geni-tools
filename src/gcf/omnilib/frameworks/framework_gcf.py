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

from .framework_base import Framework_Base
from ..util.dossl import _do_ssl
from ..util import credparsing as credutils

from ...geni.util.urn_util import is_valid_urn, URN, string_to_urn_format

import datetime
import os
import string
import sys

class Framework(Framework_Base):
    def __init__(self, config, opts):
        Framework_Base.__init__(self,config)        
        config['cert'] = os.path.expanduser(config['cert'])
        if not os.path.exists(config['cert']):
            sys.exit('GCF Framework certfile %s doesnt exist' % config['cert'])
        if not os.path.getsize(config['cert']) > 0:
            sys.exit('GCF Framework certfile %s is empty' % config['cert'])
        config['key'] = os.path.expanduser(config['key'])        
        if not os.path.exists(config['key']):
            sys.exit('GCF Framework keyfile %s doesnt exist' % config['key'])
        if not os.path.getsize(config['key']) > 0:
            sys.exit('GCF Framework keyfile %s is empty' % config['key'])
        if not config.has_key('verbose'):
            config['verbose'] = False
        if str(config['verbose']).lower().strip() in ('t', 'true', 'y', 'yes', '1', 'on'):
            config['verbose'] = True
        else:
            config['verbose'] = False

        self.logger = config['logger']

        if opts.verbosessl:
            self.logger.debug('Setting Verbose SSL logging based on option')
            config['verbose'] = True
        if config['verbose']:
            self.logger.info('Verbose logging is on')
        self.config = config
        
        self.ch = self.make_client(config['ch'], self.key, self.cert,
                                   verbose=config['verbose'], timeout=opts.ssltimeout)
        self.cert_string = file(config['cert'],'r').read()
        self.user_cred = self.init_user_cred( opts )
        
    def get_user_cred(self):
        message = ""
        if self.user_cred == None:
            self.logger.debug("Getting user credential from GCF CH %s", self.config['ch'])
            (self.user_cred, message) = _do_ssl(self, None, ("Create user credential on GCF CH %s" % self.config['ch']), self.ch.CreateUserCredential, self.cert_string)

        return self.user_cred, message
    
    def get_slice_cred(self, urn):
        (cred, message) = _do_ssl(self, None, ("Create slice %s on GCF CH %s" % (urn, self.config['ch'])), self.ch.CreateSlice, urn)
        # FIXME: use any message?
        _ = message #Appease eclipse
        return cred
    
    def create_slice(self, urn):    
        return self.get_slice_cred(urn)
    
    def delete_slice(self, urn):
        (bool, message) = _do_ssl(self, None, ("Delete Slice %s on GCF CH %s" % (urn, self.config['ch'])), self.ch.DeleteSlice, urn)
        # FIXME: use any message?
        _ = message #Appease eclipse
        return bool
     
    def list_aggregates(self):
        (sites, message) = _do_ssl(self, None, ("List Aggregates at GCF CH %s" % self.config['ch']), self.ch.ListAggregates)
        if sites is None:
            # FIXME: use any message?
            _ = message #Appease eclipse
            sites = []
        aggs = {}
        for (urn, url) in sites:
            aggs[urn] = url
        
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

        # invoke ListMySlices(urn)
        (slices, message) = _do_ssl(self, None, ("List Slices for %s at GCF CH %s" % (user, self.config['ch'])), self.ch.ListMySlices, userurn)
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
        (bool, message) = _do_ssl(self, None, ("Renew slice %s on GCF CH %s until %s" % (urn, self.config['ch'], expiration_dt)), self.ch.RenewSlice, urn, expiration)
        if bool:
            slicecred = self.get_slice_cred(urn)
            if slicecred:
                sliceexp = credutils.get_cred_exp(self.logger, slicecred)

                # If request is diff from sliceexp then log a warning
                if sliceexp - expiration_dt > datetime.timedelta.resolution:
                    self.logger.warn("Renewed GCF slice %s expiration %s different than request %s", urn, sliceexp, expiration_dt)
                return sliceexp
            else:
                self.logger.debug("Failed to get renewd GCF slice cred. Use request.")
                return expiration_dt
        else:
            # FIXME: use any message?
            _ = message #Appease eclipse
            return None

    def get_version(self):
        pl_response = dict()
        versionstruct = dict()
        (pl_response, message) = _do_ssl(self, None, ("GetVersion of GCF CH %s using cert %s" % (self.config['ch'], self.config['cert'])), self.ch.GetVersion)
        _ = message #Appease eclipse
        if pl_response is None:
            self.logger.error("Failed to get version of GCF CH: %s", message)
            # FIXME: Return error message?
            return None, message
        if isinstance(pl_response, dict) and pl_response.has_key('code'):
            code = pl_response['code']
            if code:
                self.logger.error("Failed to get version of GCF CH: Received error code: %d", code)
                output = pl_response['output']
                self.logger.error("Received error message: %s", output)
            else:
                versionstruct = pl_response['value']
        else:
            versionstruct = pl_response
        return versionstruct, message
