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

import logging
import os
import sys
from urlparse import urlparse

from omnilib.frameworks.framework_base import Framework_Base
from omnilib.util.dossl import _do_ssl
import omnilib.util.credparsing as credutils
from geni.util.urn_util import is_valid_urn, URN, string_to_urn_format

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

    def __init__(self, config):
        Framework_Base.__init__(self,config)        
        self.logger = logging.getLogger("omni.protogeni")
        config['cert'] = os.path.expanduser(config['cert'])
        if not os.path.exists(config['cert']):
            sys.exit('PG Framework certfile %s doesnt exist' % config['cert'])
        config['key'] = os.path.expanduser(config['key'])
        if not os.path.exists(config['key']):
            sys.exit('PG Framework keyfile %s doesnt exist' % config['key'])
        if not config.has_key('verbose'):
            config['verbose'] = False
        else:
            config['verbose'] = config['verbose'].lower() in ['true', '1', 't', 'yes', 'on']
        if config['verbose']:
            self.logger.info('Verbose logging is on')
        self.config = config
        self.logger.debug("Configured with key file %s", config['key'])
        
        self.logger.debug('Using clearinghouse %s', self.config['ch'])
        self.ch = self.make_client(self.config['ch'], self.key, self.cert,
                                   self.config['verbose'])
        self.logger.debug('Using slice authority %s', self.config['sa'])
        self.sa = self.make_client(self.config['sa'], self.key, self.cert,
                                   self.config['verbose'])
        self.user_cred = None
        
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
        
    def get_user_cred(self):
        if self.user_cred == None:
            pg_response = dict()
            pg_response = _do_ssl(self, None, ("Get PG user credential from SA %s using cert %s" % (self.config['sa'], self.config['cert'])), self.sa.GetCredential)
            if pg_response is None:
                self.logger.error("Failed to get your PG user credential")
                return None
                                  
            code = pg_response['code']
            if code:
                self.logger.error("Failed to get a PG user credential: Received error code: %d", code)
                output = pg_response['output']
                self.logger.error("Received error message: %s", output)
                #return None
            else:
                self.user_cred = pg_response['value']
        return self.user_cred
    
    def get_slice_cred(self, urn):
        mycred = self.get_user_cred()
        if mycred is None:
            self.logger.error("Cannot get PG slice %s without a user credential", urn)
            return None

        # Note params may be used again later in this method
        params = {'credential': mycred,
                  'type': 'Slice',
                  'urn': urn}
        self.logger.debug("Resolving %s at slice authority", urn)
        response = _do_ssl(self, None, ("Resolve PG slice %s at SA %s" % (urn, self.config['sa'])), self.sa.Resolve, params)
        # response is a dict with three keys: code, value and output
        self.logger.debug("Got resolve response %r", response)
        if response is None:
            raise Exception("Failed to find PG slice %s", urn)
        if response['code']:
            # Unable to resolve, slice does not exist
            raise Exception('PG Slice %s does not exist.' % (urn))
        else:
            # Slice exists, get credential and return it
            self.logger.debug("Resolved slice %s, getting credential", urn)
            response = _do_ssl(self, None, ("Get PG slice credential for %s from SA %s" % (urn, self.config['sa'])), self.sa.GetCredential, params)
            if response is None:
                raise Exception("Failed to get PG slice %s credential" % urn)
            if not response.has_key('value'):
                self.logger.debug("Got GetCredential response %r", response)
                raise Exception("Failed to get valid PG slice credential for %s. Response had no value." % urn)
            if not type(response['value']) is str:
                self.logger.debug("Got GetCredential response %r", response)
                raise Exception("Failed to get valid PG slice credential for %s. Got non string: %r" % (urn, response['value']))

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

        if is_valid_urn(name):
            urn = URN(None, None, None, name)
            if not urn.getType() == "slice":
                raise Exception("Invalid Slice name: got a non Slice URN %s", name)
            # if config has an authority, make sure it matches
            if self.config.has_key('sa'):
                url = urlparse(self.config['sa'])
                sa_host = url.hostname
                auth = sa_host[sa_host.index('.')+1:]
                urn_fmt_auth = string_to_urn_format(urn.getAuthority())
                if urn_fmt_auth != auth:
                    raise Exception("Invalid slice name: slice' authority (%s) doesn't match current configured authority (%s)" % (urn_fmt_auth, auth))
            return name

        if not self.config.has_key('sa'):
            raise Exception("Invalid configuration: no slice authority (sa) defined")

        url = urlparse(self.config['sa'])
        sa_host = url.hostname
        auth = sa_host[sa_host.index('.')+1:]

        return URN(auth, "slice", name).urn_string()
    
    def create_slice(self, urn):
        """Create a slice at the PG Slice Authority.
        If the slice exists, just return a credential for the existing slice.
        If the slice does not exist, create it and return a credential.
        """
        mycred = self.get_user_cred()
        if mycred is None:
            self.logger.error("Cannot create a PG slice without a valid user credential")
            return None
        # Note: params is used again below through either code path.
        params = {'credential': mycred,
                  'type': 'Slice',
                  'urn': urn}
        self.logger.debug("Resolving %s at slice authority", urn)
        response = _do_ssl(self, None, ("Look up slice %s at PG slice authority %s" % (urn, self.config['sa'])), self.sa.Resolve, params)
        # response is a dict with three keys: code, value and output
        self.logger.debug("Got resolve response %r", response)
        if response is None:
            #exception trying to resolve the slice is not the same as a PG error
            self.logger.error("Failed to resolve slice %s at PG slice authority", urn)
            return None
        elif response['code']:
            # Unable to resolve, create a new slice
            self.logger.debug("Creating new slice %s", urn)
            response = _do_ssl(self, None, ("Create PG slice %s at SA %s" % (urn, self.config['sa'])), self.sa.Register, params)
            self.logger.debug("Got register response %r", response)
            if response is None:
                self.logger.error("Failed to create new PG slice %s", urn)
                return None
            elif response['code']:
                self.logger.error('Failed to create new PG slice %s: %s (code %d)', urn, response['output'], response['code'])
            return response['value']
        else:
            # Slice exists, get credential and return it
            self.logger.debug("Resolved slice %s, getting credential", urn)
            response = _do_ssl(self, None, ("Get PG slice %s credential from SA %s" % (urn, self.config['sa'])), self.sa.GetCredential, params)
            if response is None:
                self.logger.error("Failed to get credential for existing PG slice %s", urn)
                return None
            elif response['code']:
                self.logger.error('Failed to get credential for existing PG slice %s: %s (code %d)', urn, response['output'], response['code'])
            return response['value']

    def delete_slice(self, urn):
        """Delete the PG Slice. PG doesn't do this though, so instead we
        return a string including the slice expiration time.
        """
        mycred = self.get_user_cred()
        if mycred is None:
            prtStr = "Cannot get a valid user credential. Regardless, ProtoGENI slices cannot be deleted - they expire automatically."
            self.logger.error(prtStr)
            return prtStr
        # Note: params is used again below through either code path.
        params = {'credential': mycred,
                  'type': 'Slice',
                  'urn': urn}
        response = _do_ssl(self, None, ("Get PG Slice %s credential from SA %s" % (urn, self.config['sa'])), self.sa.GetCredential, params)
        if response is None or response['code']:
            msg = "Cannot confirm PG slice exists. Regardless, ProtoGENI slices cannot be deleted - they expire automatically. Unable to get slice credential for slice %s: %s"
            if response is None:
                msg = msg % (urn, 'Exception')
            else:
                msg = msg % (urn, response['output'])
            self.logger.warning(msg)
            return msg
        else:
            slice_cred = response['value']

        # If we get here the slice exists and we have the credential
        slicecred_exp = credutils.get_cred_exp(self.logger, slice_cred)
        return 'ProtoGENI does not support deleting slices. Slice %s will be automatically removed when it expires at %s UTC.' % (urn, slicecred_exp)

    def list_my_slices(self, user):
        slice_list = self._list_my_slices( user )
        return slice_list

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
        mycred = self.get_user_cred()
        if mycred is None:
            self.logger.error("Cannot renew slice %s without a valid user credential", urn)
            return None
        # Note: params is used again below through either code path.
        params = {'credential': mycred,
                  'type': 'Slice',
                  'urn': urn}
        response = _do_ssl(self, None, ("Get PG Slice %s credential from SA %s" % (urn, self.config['sa'])), self.sa.GetCredential, params)
        if response is None or response['code']:
            msg = "Cannot renew slice. Unable to get slice credential for slice %s: %s"
            if response is None:
                msg = msg % (urn, 'Exception')
            else:
                msg = msg % (urn, response['output'])
            self.logger.warning(msg)
            return None
        else:
            slice_cred = response['value']
            expiration = expiration_dt.isoformat()
            self.logger.info('Requesting new slice expiration %r', expiration)
            params = {'credential': slice_cred,
                      'expiration': expiration}
            response = _do_ssl(self, None, ("Renew slice %s at SA %s" % (urn, self.config['sa'])), self.sa.RenewSlice, params)
            if response is None or response['code']:
                # request failed, print a message and return None
                msg = "Failed to renew slice %s: %s"
                if response is None:
                    msg = msg % (urn, 'Exception')
                else:
                    msg = msg % (urn, response['output'])
                self.logger.warning(msg)
                return None
            else:
                # Success. requested expiration worked, return it.

                # FIXME: response['value'] is the new slice
                # cred. Could parse the new expiration date out of
                # that and return that instead
                return expiration_dt

    # def _get_slices(self):
    #     """Gets the ProtoGENI slices from the ProtoGENI
    #     Clearinghouse. Returns a list of dictionaries as documented
    #     in https://www.protogeni.net/trac/protogeni/wiki/ClearingHouseAPI2#List
    #     """
    #     cred = self.get_user_cred()
    #     if not cred:
    #         raise Exception("No user credential available.")
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
        cred = self.get_user_cred()
        if not cred:
            raise Exception("No user credential available.")        
        pg_response = self.sa.Resolve({'credential': cred, 'type': 'User', 'hrn': user})
        code = pg_response['code']
        if code:
            self.logger.error("Received error code: %d", code)
            output = pg_response['output']
            self.logger.error("Received error message: %s", output)
            # Return an empty list.
            return list()
        # value is a dict, containing a list of slices
        return pg_response['value']['slices']

        
    def _get_components(self):
        """Gets the ProtoGENI component managers from the ProtoGENI
        Clearinghouse. Returns a list of dictionaries as documented
        in https://www.protogeni.net/trac/protogeni/wiki/ClearingHouseAPI2#ListComponents
        """
        cred = self.get_user_cred()
        if not cred:
            raise Exception("Cannot get PG components - no user credential available.")
        pg_response = _do_ssl(self, None, "List Components at PG CH %s" % self.config['ch'], self.ch.ListComponents, {'credential': cred})

        if (pg_response is None) or (pg_response['code']):
            self.logger.error("Cannot list PG components")
            if pg_response:
                self.logger.error("Received error code: %d", pg_response['code'])
                output = pg_response['output']
                self.logger.error("Received error message: %s", output)
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
            cm_url = cm_dict['url']
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
            # Old version skipped xmlrpclib.ProtocolError, ssl.SSLError, socket.error
            version = _do_ssl(self, "404 Not Found", "Test PG AM for GENI API compatibilitity at %s" % am_url, client.GetVersion)
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
