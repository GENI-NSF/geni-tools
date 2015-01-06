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

import datetime
import logging
import os
import sys
from urlparse import urlparse

from .framework_base import Framework_Base
from ..util.dates import naiveUTC
from ..util.dossl import _do_ssl
from ..util.handler_utils import _get_user_urn
from ..util import credparsing as credutils
from ...geni.util.urn_util import is_valid_urn, URN, string_to_urn_format

from ...sfa.util.xrn import get_leaf

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


class Framework(Framework_Base):
    """The ProtoGENI backend for Omni. This class defines the
    interface to the Protogeni Control Framework.
    """

    def __init__(self, config, opts):
        Framework_Base.__init__(self, config)
        fwtype = "PG"
        self.fwtype = fwtype
        self.opts = opts
        self.logger = logging.getLogger("omni.protogeni")
        config['cert'] = os.path.expanduser(config['cert'])
        if not os.path.exists(config['cert']):
            sys.exit('%s Framework certfile %s doesnt exist' % (fwtype, config['cert']))
        if not os.path.getsize(config['cert']) > 0:
            sys.exit('%s Framework certfile %s is empty' % (fwtype, config['cert']))
        config['key'] = os.path.expanduser(config['key'])
        if not os.path.exists(config['key']):
            sys.exit('%s Framework keyfile %s doesnt exist' % (fwtype, config['key']))
        if not os.path.getsize(config['key']) > 0:
            sys.exit('%s Framework keyfile %s is empty' % (fwtype, config['key']))
        if not config.has_key('verbose'):
            config['verbose'] = False
        else:
            config['verbose'] = config['verbose'].lower().strip() in ['true', '1', 't', 'yes', 'on', 'y']
        if opts.verbosessl:
            self.logger.debug('Setting Verbose SSL logging based on option')
            config['verbose'] = True
        if config['verbose']:
            self.logger.info('Verbose logging is on')
        self.config = config
        self.logger.debug("Configured with key file %s", config['key'])
        
        self.logger.debug('Using clearinghouse %s', self.config['ch'])
        self.ch = self.make_client(self.config['ch'], self.key, self.cert,
                                   self.config['verbose'], opts.ssltimeout)
        self.logger.debug('Using slice authority %s', self.config['sa'])
        self.sa = self.make_client(self.config['sa'], self.key, self.cert,
                                   self.config['verbose'], opts.ssltimeout)
        self.user_cred = self.init_user_cred( opts )
        
        # For now, no override aggregates.
        self.aggs = None
        # Hardcode the PG in ELab instance because it does not
        # show up in the clearinghouse.
        #self.aggs = {
            # Tom's inner emulab
            #'urn:publicid:IDN+elabinelab.geni.emulab.net':
            #    'https://myboss.elabinelab.geni.emulab.net:443/protogeni/xmlrpc/am'
            # Leigh's inner emulab
            # 'urn:publicid:IDN+myelab.testbed.emulab.net':
                # 'https://myboss.myelab.testbed.emulab.net:443/protogeni/xmlrpc/am'
            # Utah ProtoGENI
            #'urn:publicid:IDN+emulab.net':
                #'https://boss.emulab.net:443/protogeni/xmlrpc/am'
        #}
        
    def _get_log_url(self, response):
        url = None
        if not response or not isinstance(response, dict) or not response.has_key('protogeni_error_url'):
            return url
        return response['protogeni_error_url']

    def get_user_cred(self):
        message = ""
        if self.user_cred == None:
            self.logger.debug("Getting user credential from %s SA %s", self.fwtype, self.config['sa'])
            pg_response = dict()
            # Next 2 lines for debugging only
            #params = {'cert': self.config['cert']}
            #(pg_response, message) = _do_ssl(self, None, ("Get %s user credential from SA %s using cert %s" % (self.fwtype, self.config['sa'], self.config['cert'])), self.sa.GetCredential, params)
            (pg_response, message) = _do_ssl(self, None, ("Get %s user credential from SA %s using cert %s" % (self.fwtype, self.config['sa'], self.config['cert'])), self.sa.GetCredential)
            _ = message #Appease eclipse
            if pg_response is None:
                self.logger.error("Failed to get your %s user credential: %s", self.fwtype, message)
                # FIXME: Return error message?
                return None, message
                                  
            code = pg_response['code']
            log = self._get_log_url(pg_response)
            if code:
                self.logger.error("Failed to get a %s user credential: Received error code: %d", self.fwtype, code)
                output = pg_response['output']
                self.logger.error("Received error message: %s", output)
                if message is None or message == "":
                    message = output
                else:
                    message = message + "; " + output
                if log:
                    self.logger.error("See log: %s", log)
                #return None
            else:
                self.user_cred = pg_response['value']
                if log:
                    self.logger.debug("%s log url: %s", self.fwtype, log)
        return self.user_cred, message
    
    def get_slice_cred(self, urn):
        mycred, message = self.get_user_cred()
        if mycred is None:
            self.logger.error("Cannot get %s slice %s without a user credential: %s", self.fwtype, urn, message)
            return None

        # Note params may be used again later in this method
        params = {'credential': mycred,
                  'type': 'Slice',
                  'urn': urn}
        self.logger.debug("Resolving %s at slice authority", urn)
        (response, message) = _do_ssl(self, None, ("Resolve %s slice %s at SA %s" % (self.fwtype, urn, self.config['sa'])), self.sa.Resolve, params)
        # response is a dict with three keys: code, value and output
        self.logger.debug("Got resolve response %r", response)
        if response is None:
            raise Exception("Failed to find %s slice %s: %s" % (self.fwtype, urn, message))
        log = self._get_log_url(response)
        if log:
            self.logger.debug("%s resolve slice log: %s", self.fwtype, log)
        if response['code']:
            # Unable to resolve, slice does not exist
            raise Exception('Cannot access %s slice %s (does not exist or you are not a member).' % (self.fwtype, urn))
        else:
            # Slice exists, get credential and return it
            self.logger.debug("Resolved slice %s, getting credential", urn)
            (response, message) = _do_ssl(self, None, ("Get %s slice credential for %s from SA %s" % (self.fwtype, urn, self.config['sa'])), self.sa.GetCredential, params)
            if response is None:
                raise Exception("Failed to get %s slice %s credential: %s" % (self.fwtype, urn, message))

            log = self._get_log_url(response)

            # When the CM is busy, it returns error 14: 'slice is busy; try again later'
            # FIXME: All server calls should check for that 'try again later' and retry,
            # as dossl does when the AM raises that message in an XMLRPC fault
            if response['code']:
                if log:
                    self.logger.error("%s GetCredential for slice log: %s", self.fwtype, log)
                raise Exception("Failed to get %s slice %s credential: Error: %d, Message: %s" % (self.fwtype, urn, response['code'], response['output']))
            if not response.has_key('value'):
                self.logger.debug("Got GetCredential response %r", response)
                if log:
                    self.logger.error("%s GetCredential for slice log: %s", self.fwtype, log)
                raise Exception("Failed to get valid %s slice credential for %s. Response had no value." % (self.fwtype, urn))
            if not type(response['value']) is str:
                self.logger.debug("Got GetCredential response %r", response)
                if log:
                    self.logger.error("%s GetCredential for slice log: %s", self.fwtype, log)
                raise Exception("Failed to get valid %s slice credential for %s. Got non string: %r" % (self.fwtype, urn, response['value']))

            if log:
                self.logger.debug("%s GetCredential for slice log: %s", self.fwtype, log)
            return response['value']

    def slice_name_to_urn(self, name):
        """Convert a slice name to a slice urn."""
        #
        # Sample URNs:
        #   urn:publicid:IDN+pgeni3.gpolab.bbn.com+slice+tom1
        #   urn:publicid:IDN+elabinelab.geni.emulab.net+slice+tom1
        #

        if name is None or name.strip() == '':
            raise Exception('Empty slice name')

        # Could use is_valid_urn_bytype here, or just let the SA/AM do the check
        if is_valid_urn(name):
            urn = URN(None, None, None, name)
            if not urn.getType() == "slice":
                raise Exception("Invalid Slice name: got a non Slice URN %s", name)
            # if config has an authority, make sure it matches
            if self.config.has_key('sa'):
                url = urlparse(self.config['sa'])
                sa_host = url.hostname
                try:
                    auth = sa_host[sa_host.index('.')+1:]
                except:
                    # funny SA?
                    self.logger.debug("Found no . in sa hostname. Using whole hostname")
                    auth = sa_host
                urn_fmt_auth = string_to_urn_format(urn.getAuthority())
                if urn_fmt_auth != auth:
                    self.logger.warn("CAREFUL: slice' authority (%s) doesn't match current configured authority (%s)" % (urn_fmt_auth, auth))
                    self.logger.info("This may be OK though if you are using delegated slice credentials...")
#                    raise Exception("Invalid slice name: slice' authority (%s) doesn't match current configured authority (%s)" % (urn_fmt_auth, auth))
            return name

        if not self.config.has_key('sa'):
            raise Exception("Invalid configuration: no slice authority (sa) defined")

        url = urlparse(self.config['sa'])
        sa_host = url.hostname
        try:
            auth = sa_host[sa_host.index('.')+1:]
        except:
            # Funny SA
            self.logger.debug("Found no . in sa hostname. Using whole hostname")
            auth = sa_host

        return URN(auth, "slice", name).urn_string()
    
    def create_slice(self, urn):
        """Create a slice at the PG Slice Authority.
        If the slice exists, just return a credential for the existing slice.
        If the slice does not exist, create it and return a credential.
        """
        mycred, message = self.get_user_cred()
        if mycred is None:
            self.logger.error("Cannot create a %s slice without a valid user credential: %s", self.fwtype, message)
            return None
        # Note: params is used again below through either code path.
        params = {'credential': mycred,
                  'type': 'Slice',
                  'urn': urn}
        self.logger.debug("Resolving %s at slice authority", urn)
        (response, message) = _do_ssl(self, None, ("Look up slice %s at %s slice authority %s" % (urn, self.fwtype, self.config['sa'])), self.sa.Resolve, params)
        # response is a dict with three keys: code, value and output
        self.logger.debug("Got resolve response %r", response)
        if response is None:
            #exception trying to resolve the slice is not the same as a PG error
            self.logger.error("Failed to resolve slice %s at %s slice authority: %s" % (urn, self.fwtype, message))
            # FIXME: Return error message?
            return None
        elif response['code']:
            # Unable to resolve, create a new slice
            self.logger.debug("Creating new slice %s", urn)
            (response, message) = _do_ssl(self, None, ("Create %s slice %s at SA %s" % (self.fwtype, urn, self.config['sa'])), self.sa.Register, params)
            self.logger.debug("Got register response %r", response)
            if response is None:
                self.logger.error("Failed to create new %s slice %s: %s", self.fwtype, urn, message)
                # FIXME: Return an error message?
                return None
            log = self._get_log_url(response)
            if response['code']:
                if response['code'] == 3 and 'Unknown project' in response['output']:
                    self.logger.error("Unknown project in slice URN '%s'. Project names are case sensitive. Did you mis-type or mis-configure Omni?" % urn)
                    self.logger.debug('Failed to create new %s slice %s: %s (code %d)', self.fwtype, urn, response['output'], response['code'])
                elif response['code'] == 5 or \
                        response['output'].startswith("[DUPLICATE] DUPLICATE_ERROR"):
                    self.logger.error("Failed to create slice '%s' because a similarly named slice already exists. Slice names are case insensitive at creation time.", urn)
                    self.logger.debug('Failed to create new %s slice %s: %s (code %d)', self.fwtype, urn, response['output'], response['code'])
                else:
                    self.logger.error('Failed to create new %s slice %s: %s (code %d)', self.fwtype, urn, response['output'], response['code'])
                if log:
                    self.logger.info("%s log url: %s", self.fwtype, log)
            elif log:
                self.logger.debug("%s log url: %s", self.fwtype, log)
            return response['value']
        else:
            # Slice exists, get credential and return it
            self.logger.debug("Resolved slice %s, getting credential", urn)
            (response, message) = _do_ssl(self, None, ("Get %s slice %s credential from SA %s" % (self.fwtype, urn, self.config['sa'])), self.sa.GetCredential, params)
            if response is None:
                self.logger.error("Failed to get credential for existing %s slice %s", self.fwtype, urn)
                # FIXME: Return an error message?
                return None
            log = self._get_log_url(response)
            if response['code']:
                self.logger.error('Failed to get credential for existing %s slice %s: %s (code %d)', self.fwtype, urn, response['output'], response['code'])
                if log:
                    self.logger.info("%s log url: %s", self.fwtype, log)
            elif log:
                self.logger.debug("%s log url: %s", self.fwtype, log)
            if not response.has_key('value'):
                self.logger.debug("Got GetCredential response %r", response)
                raise Exception("Failed to get valid %s slice credential for %s. Response had no value." % (self.fwtype, urn))
            if not type(response['value']) is str:
                self.logger.debug("Got GetCredential response %r", response)
                raise Exception("Failed to get valid %s slice credential for %s. Got non string: %r" % (self.fwtype, urn, response['value']))
            return response['value']

    def delete_slice(self, urn):
        """Delete the PG Slice. PG doesn't do this though, so instead we
        return a string including the slice expiration time.
        """
        mycred, message = self.get_user_cred()
        _ = message # Appease eclipse
        if mycred is None:
            prtStr = "Cannot get a valid user credential. Regardless, %s slices cannot be deleted - they expire automatically." % self.fwtype
            self.logger.error(prtStr)
            return prtStr
        # Note: params is used again below through either code path.
        params = {'credential': mycred,
                  'type': 'Slice',
                  'urn': urn}
        (response, message) = _do_ssl(self, None, ("Get %s Slice %s credential from SA %s" % (self.fwtype, urn, self.config['sa'])), self.sa.GetCredential, params)
        if response is None or response['code']:
            msg = "Cannot confirm %s slice exists. Regardless, %s slices cannot be deleted - they expire automatically. Unable to get slice credential for slice %s: %s"
            if response is None:
                msg = msg % (self.fwtype, self.fwtype, urn, message)
            else:
                msg = msg % (self.fwtype, self.fwtype, urn, response['output'])
            self.logger.warning(msg)
            return msg
        else:
            slice_cred = response['value']

        # If we get here the slice exists and we have the credential
        slicecred_exp = credutils.get_cred_exp(self.logger, slice_cred)
        return '%s does not support deleting slices. Slice %s will be automatically removed when it expires at %s UTC.' % (self.fwtype, urn, slicecred_exp)

    def list_my_slices(self, user):
        slice_list = self._list_my_slices( user )
        return slice_list

    def list_ssh_keys(self, username=None):
        if username is not None and username.strip() != "":
            name = get_leaf(_get_user_urn(self.logger, self.config))
            if name != get_leaf(username):
                return None, "%s can get SSH keys for current user (%s) only, not %s" % (self.fwtype, name, username)
        key_list, message = self._list_ssh_keys()
        return key_list, message

    def list_aggregates(self):
        if self.aggs:
            return self.aggs
        cm_dicts = self._get_components()
        if cm_dicts is None:
            cm_dicts = []
        am_dicts = self._find_geni_ams(cm_dicts)
        if am_dicts is None:
            am_dicts = []
        result = dict()
        for am_dict in am_dicts:
            self.logger.debug("Keys: %r", am_dict.keys())
            result[am_dict['urn']] = am_dict['am_url']
        for key, value in result.items():
            self.logger.debug('Found aggregate %r: %r', key, value)
        return result

    def renew_slice(self, urn, expiration_dt):
        """See framework_base for doc.
        """
        mycred, message = self.get_user_cred()
        if mycred is None:
            self.logger.error("Cannot renew slice %s without a valid user credential: %s", urn, message)
            return None
        # Note: params is used again below through either code path.
        params = {'credential': mycred,
                  'type': 'Slice',
                  'urn': urn}
        (response, message) = _do_ssl(self, None, ("Get %s Slice %s credential from SA %s" % (self.fwtype, urn, self.config['sa'])), self.sa.GetCredential, params)
        if response is None or response['code']:
            msg = "Cannot renew slice. Unable to get slice credential for slice %s: %s"
            if response is None:
                msg = msg % (urn, message)
            else:
                log = self._get_log_url(response)
                if log:
                    msg = msg % (urn, response['output'] + (". %s log url: %s" % (self.fwtype, log)))
                else:
                    msg = msg % (urn, response['output'])
            self.logger.warning(msg)
            return None
        else:
            log = self._get_log_url(response)
            if log:
                self.logger.debug("%s slice GetCredential log: %s", self.fwtype, log)
            slice_cred = response['value']
            expiration = naiveUTC(expiration_dt).isoformat()
            self.logger.info('Requesting new slice expiration %r', expiration)
            params = {'credential': slice_cred,
                      'expiration': expiration}
            (response, message) = _do_ssl(self, None, ("Renew slice %s at SA %s" % (urn, self.config['sa'])), self.sa.RenewSlice, params)
            if response is None or response['code']:
                # request failed, print a message and return None
                msg = "Failed to renew slice %s: %s"
                if response is None:
                    msg = msg % (urn, message)
                else:
                    log = self._get_log_url(response)
                    if log:
                        msg = msg % (urn, ("%s SA said: " % self.fwtype) + response['output'] + (". %s log url: %s" % (self.fwtype, log)))
                    else:
                        msg = msg % (urn, ("%s SA said: " % self.fwtype) + response['output'])
                self.logger.warning(msg)
                return None
            else:
                # Success. requested expiration worked, return it.

                log = self._get_log_url(response)
                if log:
                    self.logger.debug("%s RenewSlice log: %s", self.fwtype, log)

                # response['value'] is the new slice
                # cred. parse the new expiration date out of
                # that and return that
                sliceexp = naiveUTC(credutils.get_cred_exp(self.logger, response['value']))
                # If request is diff from sliceexp then log a warning
                if abs(sliceexp - naiveUTC(expiration_dt)) > datetime.timedelta.resolution:
                    self.logger.warn("Renewed %s slice %s expiration %s different than request %s", self.fwtype, urn, sliceexp, expiration_dt)
                return sliceexp

    # def _get_slices(self):
    #     """Gets the ProtoGENI slices from the ProtoGENI
    #     Clearinghouse. Returns a list of dictionaries as documented
    #     in https://www.protogeni.net/trac/protogeni/wiki/ClearingHouseAPI2#List
    #     """
    #     cred, message = self.get_user_cred()
    #     if not cred:
    #         raise Exception("No user credential available. %s" % message)
    #     pg_response = self.ch.List({'credential': cred, 'type': 'Slices'})

    #     code = pg_response['code']
    #     if code:
    #         self.logger.error("Received error code: %d", code)
    #         output = pg_response['output']
    #         self.logger.error("Received error message: %s", output)
    #         # Return an empty list.
    #         return list()
    #     # value is a list of dicts, each containing info about an aggregate
    #     return pg_response['value']

    def _list_my_slices(self, user):
        """Gets the ProtoGENI slices from the ProtoGENI Slice Authority. """
        cred, message = self.get_user_cred()
        if not cred:
            raise Exception("No user credential available. %s" % message)
        (pg_response, message) = _do_ssl(self, None, "Resolve user %s at %s SA %s" % (user, self.fwtype, self.config['sa']), self.sa.Resolve, {'credential': cred, 'type': 'User', 'hrn': user})
        if pg_response is None:
            self.logger.error("Cannot list slices: %s", message)
            raise Exception(message)
#            return list()

        log = self._get_log_url(pg_response)
        code = pg_response['code']
        if code:
            self.logger.error("Received error code: %d", code)
            output = pg_response['output']
            self.logger.error("Received error message from %s: %s", self.fwtype, output)
            msg = "Error %d: %s" % (code, output)
            if log:
                self.logger.error("%s log url: %s", self.fwtype, log)
            raise Exception(msg)
#           # Return an empty list.
#            return list()

        # Resolve keys include uuid, slices, urn, subauthorities, name, hrn, gid, pubkeys, email, uid

        # value is a dict, containing a list of slice URNs
        return pg_response['value']['slices']

    def _list_ssh_keys(self, userurn = None):
        """Gets the ProtoGENI stored SSH public keys from the ProtoGENI Slice Authority. """
        cred, message = self.get_user_cred()
        if not cred:
            raise Exception("No user credential available. %s" % message)
        usr = 'current user'
        if userurn is not None:
            usr = 'user ' + get_leaf(userurn)
            (pg_response, message) = _do_ssl(self, None, "Get %s SSH Keys at %s SA %s" % (usr, self.fwtype, self.config['sa']), self.sa.GetKeys, {'credential': cred, 'member_urn': userurn})
        else:
            (pg_response, message) = _do_ssl(self, None, "Get %s SSH Keys at %s SA %s" % (usr, self.fwtype, self.config['sa']), self.sa.GetKeys, {'credential': cred})
        if pg_response is None:
            msg = "Cannot get %s's public SSH keys: %s" % (usr, message)
            self.logger.error(msg)
            return list(), msg

        log = self._get_log_url(pg_response)
        code = pg_response['code']
        if code:
            output = pg_response['output']
            msg = "%s Server error %d: %s" % (self.fwtype, code, output)
            if log:
                msg += " (log url: %s)" % log
            self.logger.error(msg)
            # Return an empty list.
            return list(), msg

        # value is an array. For each entry, type=ssh, key=<key>
        if not isinstance(pg_response['value'], list):
            self.logger.error("Non list response for value: %r" % pg_response['value']);
            return pg_response['value'], None

        keys = list()
        for key in pg_response['value']:
            if not key.has_key('key'):
                self.logger.error("GetKeys list missing key value?");
                continue
            keys.append({'public_key': key['key']})
        return keys, None
        
    def _get_components(self):
        """Gets the ProtoGENI component managers from the ProtoGENI
        Clearinghouse. Returns a list of dictionaries as documented
        in https://www.protogeni.net/trac/protogeni/wiki/ClearingHouseAPI2#ListComponents
        """
        cred, message = self.get_user_cred()
        if not cred:
            raise Exception("Cannot get %s components - no user credential available. %s" % (self.fwtype, message))
        (pg_response, message) = _do_ssl(self, None, "List Components at %s CH %s" % (self.fwtype, self.config['ch']), self.ch.ListComponents, {'credential': cred})

        if (pg_response is None) or (pg_response['code']):
            self.logger.error("Cannot list %s components: %s", self.fwtype, message)
            if pg_response:
                self.logger.error("Received error code: %d", pg_response['code'])
                output = pg_response['output']
                self.logger.error("Received error message: %s", output)
                log = self._get_log_url(pg_response)
                if log:
                    self.logger.error("%s log url: %s", self.fwtype, log)
            # Return an empty list.
            return list()
        # value is a list of dicts, each containing info about an aggregate
        return pg_response['value']
    
    def _find_geni_ams(self, cm_dicts):
        """Finds ComponentManagers that also support the GENI AM API.
        Returns a list of dicts containing those CMs that implement the AM API.
        The AM URL is included in the dict in the key 'am_url'.
        """
        result = list()
        for cm_dict in cm_dicts:
            if cm_dict.has_key("url"):
                cm_url = cm_dict['url']
            else:
                self.logger.error("Missing url key for CM %s", cm_dict)
                continue
            if not cm_dict.has_key("urn"):
                self.logger.error("Missing urn key for CM %s", cm_dict)
                cm_dict["urn"] = ''
            self.logger.debug('Checking for AM at %s', cm_url)
            am_url = self._cm_to_am(cm_url)
            self.logger.debug('AM URL = %s', am_url)
            # Test the am_url...
            # timeout is in seconds
            client = self.make_client(am_url, self.key, self.cert,
                                      self.config['verbose'],
                                      timeout=5)
            # This refactoring means we print verbose errors for 404 Not Found messages like
            # we get when there is no AM for the CM
            # Old version skipped xmlrpclib.ProtocolError,
            # ssl.SSLError, socket.error
            (version, message) = _do_ssl(self, ("404 Not Found", "Name or service not known", "timed out"), "Test PG AM for GENI API compatibilitity at %s" % am_url, client.GetVersion)
            # FIXME: look at the message and say something re-assuring
            # on OK errors?
            _ = message #Appease eclipse
            self.logger.debug('version = %r', version)
            if version is not None:
                if version.has_key('geni_api'):
                    cm_dict['am_url'] = am_url
                    result.append(cm_dict)
        return result

    def _cm_to_am(self, url):
        """Convert a CM url to an AM url."""
        # Replace the trailing "cm" with "am"
        if url.endswith('/protogeni/xmlrpc/cm'):
            return url[:-2] + 'am'
        else:
            return url

    def get_version(self):
        # Here we call getversion at the CH, then append the getversion at the SA
        pg_response = dict()
        versionstruct = dict()
        (pg_response, message) = _do_ssl(self, None, ("GetVersion of %s CH %s using cert %s" % (self.fwtype, self.config['ch'], self.config['cert'])), self.ch.GetVersion)
        _ = message #Appease eclipse
        if pg_response is None:
            self.logger.error("Failed to get version of %s CH: %s", self.fwtype, message)
            # FIXME: Return error message?
            return None, message

        code = pg_response['code']
        log = self._get_log_url(pg_response)
        if code:
            self.logger.error("Failed to get version of %s CH: Received error code: %d", self.fwtype, code)
            output = pg_response['output']
            self.logger.error("Received error message: %s", output)
            if log:
                self.logger.error("See log: %s", log)
                #return None
        else:
            versionstruct = pg_response['value']
            if log:
                self.logger.debug("%s log url: %s", self.fwtype, log)

        sa_response = None
        (sa_response, message2) = _do_ssl(self, None, ("GetVersion of %s SA %s using cert %s" % (self.fwtype, self.config['sa'], self.config['cert'])), self.sa.GetVersion)
        _ = message2 #Appease eclipse
        if sa_response is not None:
            if isinstance(sa_response, dict) and sa_response.has_key('value'):
                versionstruct['sa-version'] = sa_response['value']
            else:
                versionstruct['sa-version'] = sa_response

        return versionstruct, message
