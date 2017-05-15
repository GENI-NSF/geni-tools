#----------------------------------------------------------------------
# Copyright (c) 2011-2016 Raytheon BBN Technologies
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

# Framework for talking to a CH that speaks the Uniform Federation API
# http://groups.geni.net/geni/wiki/UniformClearinghouseAPI
# Specifically, this framework can be used to talk to the GENI Clearinghouse at ch.geni.net

from __future__ import absolute_import

from .framework_base import Framework_Base
from ..util import OmniError
from ..util.dates import naiveUTC
from ..util.dossl import _do_ssl
from ..util import credparsing as credutils
#from ..util.handler_utils import _lookupAggURNFromURLInNicknames
from ..util.handler_utils import _load_cred

from ...geni.util.tz_util import tzd
from ...geni.util.urn_util import is_valid_urn, URN, string_to_urn_format,\
    nameFromURN, is_valid_urn_bytype, string_to_urn_format
from ...geni.util.speaksfor_util import determine_speaks_for
from ...sfa.trust import gid as gid
from ...sfa.trust.credential_factory import CredentialFactory
from ...sfa.trust.credential import Credential
from ...sfa.trust.abac_credential import ABACCredential

import datetime
import dateutil
import logging
import os
from pprint import pprint
import string
import sys
import uuid

class Framework(Framework_Base):
    def __init__(self, config, opts):
        Framework_Base.__init__(self,config)
        config['cert'] = os.path.expanduser(config['cert'])
        self.fwtype = "GENI Clearinghouse"
        self.opts = opts
        if not os.path.exists(config['cert']):
            sys.exit("CHAPI Framework certfile '%s' doesn't exist" % config['cert'])
        if not os.path.getsize(config['cert']) > 0:
            sys.exit("CHAPI Framework certfile '%s' is empty" % config['cert'])
        config['key'] = os.path.expanduser(config['key'])
        if not os.path.exists(config['key']):
            sys.exit("CHAPI Framework keyfile '%s' doesn't exist" % config['key'])
        if not os.path.getsize(config['key']) > 0:
            sys.exit("CHAPI Framework keyfile '%s' is empty" % config['key'])
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

        self.ch_url = config['ch']
        self.ch = self.make_client(self.ch_url, self.key, self.cert,
                                   verbose=config['verbose'], timeout=opts.ssltimeout)

        self._ma = None
        self._ma_url = None
        if config.has_key('ma') and config['ma'].strip() != "":
            self._ma_url = config['ma']
            self.logger.info("Member Authority is %s (from config)", self._ma_url)

        self._sa = None
        self._sa_url = None
        if config.has_key('sa') and config['sa'].strip() != "":
            self._sa_url = config['sa']
            self.logger.info("Slice Authority is %s (from config)", self._sa_url)

        # FIXME: Pull truth from GetVersion if possible
        if not config.has_key('useprojects'):
            config['useprojects'] = 'True'
        if config['useprojects'].strip().lower() in ['f', 'false']:
            self.useProjects = False
        else:
            self.useProjects = True

        # Does this CH need a usercred / slicecred passed to methods
        # Default False. Right thing would be to try to get this from GetVersion if possible.
        if not config.has_key('needcred'):
            config['needcred'] = 'False'
        if config['needcred'].strip().lower() in ['t', 'true']:
            self.needcred = True
        else:
            self.needcred = False

        # Does this CH speak APIv2 APIs, in which case use them
        # Default False for now. Right thing would be to query GetVersion to determine truth.
        if not config.has_key('speakv2'):
            config['speakv2'] = 'False'
        if config['speakv2'].strip().lower() in ['t', 'true']:
            self.speakV2 = True
        else:
            self.speakV2 = False
        if self.speakV2:
            self.logger.debug("CH speaks CHAPI v2")
        else:
            self.logger.debug("CH speaks CHAPI v1")

        self.cert = config['cert']
        try:
            self.cert_string = file(self.cert, 'r').read()
        except Exception, e:
            sys.exit('CHAPI Framework failed to read cert file %s: %s' % (self.cert, e))

        try:
            self.cert_gid = gid.GID(filename=self.cert)
        except Exception, e:
            sys.exit('CHAPI Framework failed to parse cert read from %s: %s' % (self.cert, e))

        self.cred_nonOs = None
        # ***
        # Do the whole speaksfor test here
        # ***
        if self.opts.speaksfor:
            credSs, options = self._add_credentials_and_speaksfor(None, None)
            creds = []
            for cred in credSs:
                try:
                    c = CredentialFactory.createCred(credString=credutils.get_cred_xml(cred))
                    creds.append(c)
                except Exception, e:
                    s = None
                    if isinstance(cred, dict):
                        s = "Type: '%s': %s" % (cred['geni_type'], cred['geni_value'][:60])
                    else:
                        s = str(cred)[:60]
                    self.logger.error("Failed to read credential: %s. Cred: %s...", e, s)
            speaker_gid = \
                determine_speaks_for(self.logger, creds, self.cert_gid, options, None)
            if speaker_gid != self.cert_gid:
                self.logger.info("Speaks-for Invocation: %s speaking for %s" % \
                                     (self.cert_gid.get_urn(), \
                                          speaker_gid.get_urn()))
                self.cert_gid = speaker_gid

        self.user_urn = self.cert_gid.get_urn()
        self.user_cred = self.init_user_cred( opts )

    def list_slice_authorities(self):

        self.logger.debug("Looking up SAs at %s %s", self.fwtype, self.ch_url)
        options = {'filter':['SERVICE_URN', 'SERVICE_URL']}
        if not self.speakV2:
            (res, message) = _do_ssl(self, None, ("List slice authorities at %s %s" % (self.fwtype, self.ch_url)),
                                     self.ch.lookup_slice_authorities,
                                     options)
        else:
            options['match'] = {'SERVICE_TYPE': "SLICE_AUTHORITY"}
            self.logger.debug("Using API v2, with options: %s", options)
            (res, message) = _do_ssl(self, None, ("List slice authorities at %s %s" % (self.fwtype, self.ch_url)),
                                     self.ch.lookup, 'SERVICE', [],
                                     options)
        auths = dict()
        if res is not None:
            if res['value'] is not None and res['code'] == 0:
                for d in res['value']:
                    auths[d['SERVICE_URN']] = d['SERVICE_URL']
            else:
                msg = "Server Error listing SAs %d: %s" % (res['code'], res['output'])
                if res.has_key('protogeni_error_url'):
                    msg += " (Log url - look here for details on any failures: %s)" % res['protogeni_error_url']
                self.logger.warn(msg)
        else:
            msg = "Server Error listing SAs - no results"
            if message and message.strip() != "":
                msg += "- " + message
            self.logger.warn(msg)

        return auths

    def list_member_authorities(self):
        self.logger.debug("Looking up MAs at %s %s", self.fwtype, self.ch_url)
        options = {'filter':['SERVICE_URN', 'SERVICE_URL']}
        if not self.speakV2:
            (res, message) = _do_ssl(self, None, ("List member authorities at %s %s" % (self.fwtype, self.ch_url)),
                                     self.ch.lookup_member_authorities,
                                     options)
        else:
            options['match'] = {'SERVICE_TYPE':"MEMBER_AUTHORITY"}
            self.logger.debug("Using API v2, with options: %s", options)
            (res, message) = _do_ssl(self, None, ("List member authorities at %s %s" % (self.fwtype, self.ch_url)), 
                                     self.ch.lookup, "SERVICE", [],
                                     options)
        auths = dict()
        if res is not None:
            if res['value'] is not None and res['code'] == 0:
                for d in res['value']:
                    auths[d['SERVICE_URN']] = d['SERVICE_URL']
            else:
                msg = "Server Error listing MAs %d: %s" % (res['code'], res['output'])
                if res.has_key('protogeni_error_url'):
                    msg += " (Log url - look here for details on any failures: %s)" % res['protogeni_error_url']
                self.logger.warn(msg)
        else:
            msg = "Server Error listing MAs - no results"
            if message and message.strip() != "":
                msg += "- " + message
            self.logger.warn(msg)

        return auths

    def ma(self):
        if self._ma is not None:
            return self._ma
        url = self.ma_url()
        self._ma = self.make_client(url, self.key, self.cert,
                                   verbose=self.config['verbose'], timeout=self.opts.ssltimeout)
        return self._ma

    def ma_url(self):
        if self._ma_url is not None:
            return self._ma_url
        mas = self.list_member_authorities()
        if len(mas.keys()) == 0:
            raise OmniError("No member authorities listed at %s %s!" % (self.fwtype, self.ch_url))
        if len(mas.keys()) > 1:
            self.logger.warn("%d member authorities were listed - taking the first: %s (%s)", len(mas.keys()), mas.keys()[0], mas[mas.keys()[0]])
        self.logger.info("Member Authority is %s %s", mas.keys()[0], mas[mas.keys()[0]])
        self._ma_url = mas[mas.keys()[0]]
        return self._ma_url

    def sa(self):
        if self._sa is not None:
            return self._sa
        url = self.sa_url()
        self._sa = self.make_client(url, self.key, self.cert,
                                   verbose=self.config['verbose'], timeout=self.opts.ssltimeout)
        return self._sa

    def sa_url(self):
        if self._sa_url is not None:
            return self._sa_url
        sas = self.list_slice_authorities()
        if len(sas.keys()) == 0:
            raise OmniError("No slice authorities listed at %s %s!" % (self.fwtype, self.ch_url))
        if len(sas.keys()) > 1:
            self.logger.warn("%d slice authorities were listed - taking the first: %s (%s)", len(sas.keys()), sas.keys()[0], sas[sas.keys()[0]])
        self.logger.info("Slice Authority is %s %s", sas.keys()[0], sas[sas.keys()[0]])
        self._sa_url = sas[sas.keys()[0]]
        return self._sa_url

    # Add new speaks for options and credentials based on provided opts 
    def _add_credentials_and_speaksfor(self, credentials, options):
        # FIXME: Tune log messages
#        self.logger.debug("add_c_n_spkfor start with self.opts.speaksfor = '%s'" % self.opts.speaksfor)
#        self.logger.debug("add_c_n_spkfor start with self.opts.cred = %s" % self.opts.cred)
        if credentials is None:
            credentials = []
        if options is None:
            options = {}
        new_credentials = credentials
        new_options = options
        if self.opts.speaksfor and not options.has_key("speaking_for"):
            options['speaking_for'] = self.opts.speaksfor # At CHs this is speaking_for
            options['geni_speaking_for'] = self.opts.speaksfor # At AMs this is geni_speaking_for
        if self.cred_nonOs is not None:
            self.logger.debug("Using credentials already loaded")
            for cred in self.cred_nonOs:
                if not cred in new_credentials:
                    new_credentials.append(cred)
        elif self.opts.cred:
            self.cred_nonOs = []
            for cred_filename in self.opts.cred:
                try:
                    # Use helper to load cred, but don't unwrap/wrap there.
                    # We want it wrapped to preserve the wrapping it had
                    oldDev = self.opts.devmode
                    self.opts.devmode = True
                    cred_contents = _load_cred(self, cred_filename)
                    self.opts.devmode = oldDev
                    new_cred = self.wrap_cred(cred_contents)
                    if not new_cred in self.cred_nonOs:
                        self.cred_nonOs.append(new_cred)
                    if not new_cred in new_credentials:
                        new_credentials.append(new_cred)
                except Exception, e:
                    self.logger.warn("Failed to read credential from %s: %s", cred_filename, e)
        if self.logger.isEnabledFor(logging.DEBUG):
            msg = "add_c_n_spkfor new_creds = ["
            first = True
            for cred in new_credentials:
                if not first:
                    msg += ", "
                if isinstance(cred, dict):
                    msg += cred['geni_type'] + ": " + cred['geni_value'][:180] + "..."
                else:
                    msg += str(cred)[:180] + "..."
                first = False
            self.logger.debug("%s]; new_options = %s" % (msg, new_options))
        return new_credentials, new_options

    def get_user_cred(self, struct=False):
        message = ""
        msg = None
        creds = []
        options = {}

        if struct==True and self.user_cred_struct is not None:
            return self.user_cred_struct, msg

        if self.user_cred == None:
            creds, options = self._add_credentials_and_speaksfor(creds, options)
            self.logger.debug("Getting user credential from %s MA %s",
                              self.fwtype, self.ma_url())
            # This call is the same for CHAPI V1 and V2
            (res, message) = _do_ssl(self, None, ("Get user credential from %s %s" % (self.fwtype, self.ma_url())),
                                     self.ma().get_credentials,
                                     self.user_urn,
                                     creds,
                                     options)
            if res is not None:
                if res['code'] == 0:
                    if res['value'] is None:
                        self.logger.error("No SFA-type user credential returned!")
                        self.logger.debug("Got: %s", res['value'])
                    else:
                        self.user_cred_struct = self._select_sfa_cred(res['value'], True)
                        if self.user_cred_struct:
                            self.user_cred = self.user_cred_struct['geni_value']
                            if self.user_cred_struct.has_key('geni_version'):
                                if not isinstance(self.user_cred_struct['geni_version'], str):
                                    self.logger.debug("Got non string geni_version on user cred. %s is type %s", 
                                                      self.user_cred_struct['geni_version'], type(self.user_cred_struct['geni_version']))
                                    self.user_cred_struct['geni_version'] = str(self.user_cred_struct['geni_version'])
                    if self.user_cred is None:
                        self.logger.error("No SFA-type user credential returned!")
                        self.logger.debug("Got: %s", res['value'])
                else:
                    msg = res['output']
                    if msg is None or msg.strip() == "":
                        msg = "Error %d" % res['code']
                    if message is not None and message.strip() != "":
                        msg = msg + ". %s" % message
                    if res.has_key('protogeni_error_url'):
                        msg += " (Log url - look here for details on any failures: %s)" % res['protogeni_error_url']
                    self.logger.error("Failed to get user credential. Server says: %s", msg)
            else:
                msg = message

        if struct==True:
            if self.user_cred is not None and self.user_cred_struct is None:
                if not isinstance(self.user_cred, dict):
                    self.user_cred_struct = self.wrap_cred(self.user_cred)
                else:
                    self.user_cred_struct = self.user_cred
            return self.user_cred_struct, msg
        else:
            return self.user_cred, msg

    def get_slice_cred(self, slice_urn, struct=False):
        scred = []
        options = {'match': 
                   {'SLICE_URN': slice_urn,
                    'SLICE_EXPIRED': False,
                    }}

        # PG implementation needs a user cred
        if self.needcred:
            uc, msg = self.get_user_cred(True)
            if uc is not None:
                scred.append(uc)

        scred, options = self._add_credentials_and_speaksfor(scred, options)

        # This call is the same for CHAPI v1 and V2
        (res, message) = _do_ssl(self, None, ("Get credentials for slice %s on %s SA %s" % (slice_urn,
                                                                                            self.fwtype, self.sa_url())),
                                 self.sa().get_credentials, slice_urn, scred, 
                                 options)

        # FIXME: Handle typical error return codes with special messages

        cred = None
        if res is not None:
            if res['code'] == 0:
                d = res['value']
                if d is not None:
                    credstruct = self._select_sfa_cred(d, True)
                    if struct==False and credstruct:
                        cred = credstruct['geni_value']
                    else:
                        cred = credstruct
                        if cred.has_key('geni_version'):
                            if not isinstance(cred['geni_version'], str):
                                self.logger.debug("Got non string geni_version on cred. %s is type %s", cred['geni_version'], type(cred['geni_version']))
                                cred['geni_version'] = str(cred['geni_version'])
                    if cred is None:
                        self.logger.debug("Malformed list of creds: Got: %s", d)
                        raise OmniError("No slice credential returned for slice %s" % slice_urn)
                else:
                    self.logger.debug("Malformed slice cred return. Got: %s", res)
                    raise OmniError("Malformed return getting slice credential")
            else:
                msg = "Server Error getting slice %s credential: %d: %s" % (slice_urn, res['code'], res['output'])
                if message is not None and str(message).strip() != "":
                    msg += " (%s)" % message
                if res.has_key('protogeni_error_url'):
                    msg += " (Log url - look here for details on any failures: %s)" % res['protogeni_error_url']
                if res['code'] == 3 and 'Unknown slice urn' in res['output']:
                    msg = "Server says: Unknown slice %s" % slice_urn
                    msg1 = msg
                    self.logger.debug(msg1)
                raise OmniError(msg)
        else:
            msg = "Server Error getting slice %s credential" % slice_urn
            if message is not None and message.strip() != "":
                msg = msg + ". %s" % message
            raise OmniError(msg)
        return cred

    def list_ssh_keys(self, username=None):
        scred = []
        # FIXME: Use member_name_to_urn?
        fetch_urn = self.user_urn
        if username is None or username.strip() == "":
            username = nameFromURN(self.user_urn)
        else:
            if is_valid_urn(username):
                fetch_urn = username
                username = nameFromURN(fetch_urn)
            else:
                fetch_urn = URN(authority=URN(urn=self.user_urn).getAuthority(), type='user', name=username).urn_string()
            if not is_valid_urn_bytype(fetch_urn, 'user', self.logger):
                return [], "%s is not a valid user name or urn" % username

        options = {'match': {'KEY_MEMBER': fetch_urn}, 'filter': ['KEY_PUBLIC','KEY_PRIVATE']}

        # PG implementation requires a user cred
        if self.needcred:
            uc, msg = self.get_user_cred(True)
            if uc is not None:
                scred.append(uc)

        scred, options = self._add_credentials_and_speaksfor(scred, options)

        self.logger.debug("Getting %s SSH keys from %s MA %s",
                          username, self.fwtype, self.ma_url())
        if not self.speakV2:
            (res, message) = _do_ssl(self, None, ("Get %s SSH keys from %s %s" % (username, self.fwtype, self.ma_url())),
                                     self.ma().lookup_keys,
                                     scred,
                                     options)
        else:
            (res, message) = _do_ssl(self, None, 
                                     ("Get %s SSH keys from %s %s" % (username, self.fwtype, self.ma_url())),
                                     self.ma().lookup,
                                     "KEY", 
                                     scred, options)
            # In V1, we get a dictionary of KEY_MEMBER => KEY_PUBLIC, KEY_PRIVATE
            # In V2, we get a dictionary of KEY_ID => KEY_MEMBER, KEY_PUBLIC, KEY_PRIVATE
            # We only asked for one person so flip back to V1 format
            if res and res['code'] == 0:
                res['value'] = {fetch_urn : res['value'].values()}

        keys = []
        msg = None
        if res is not None:
            if res['code'] == 0:
                if res.has_key('value') and res['value'] is not None:
                    d = res['value']
                    for uid, key_tups in d.items():
                        for key_tup in key_tups:
                            kstr = {}
                            if 'KEY_PUBLIC' in key_tup:
                                kstr['public_key'] = key_tup['KEY_PUBLIC']
                            else:
                                self.logger.debug("No public key? %s", key_tup)
                            if 'KEY_PRIVATE' in key_tup and key_tup['KEY_PRIVATE']:
                                kstr['private_key'] = key_tup['KEY_PRIVATE']
                            else:
                                self.logger.debug("No private key")
                            if kstr != {}:
                                keys.append(kstr)
                else:
                    msg = "Malformed server return getting SSH keys"
                    if message is not None and message.strip() != "":
                        msg = msg + ". %s" % message
                    self.logger.error(msg)
                    self.logger.debug("Got: %s", res)
            else:
                msg = "Server Error getting SSH keys: %d: %s" % (res['code'], res['output'])
                if message is not None and message.strip() != "":
                    msg = msg + " (%s)" % message
                if res.has_key('protogeni_error_url'):
                    msg += " (Log url - look here for details on any failures: %s)" % res['protogeni_error_url']
                self.logger.error(msg)
        else:
            msg = "Server error getting SSH keys"
            if message is not None and message.strip() != "":
                msg = msg + ": %s" % message

        return keys, msg

    def _select_sfa_cred(self, creds, struct=False):
        if creds is None:
            return None
        for cred in creds:
            if cred.has_key('geni_type') \
                    and cred['geni_type'] == Credential.SFA_CREDENTIAL_TYPE \
                    and cred.has_key('geni_value'):
                if struct:
                    return cred
                return cred['geni_value']

    def create_slice(self, urn):
        scred = []

        # PG implementation needs a user cred
        if self.needcred:
            uc, msg = self.get_user_cred(True)
            if uc is not None:
                scred.append(uc)

        try:
            slice_urn = self.slice_name_to_urn(urn)
        except Exception, e:
            self.logger.error(e)
            return None

        project = None
        auth = None
        sURNObj = URN(urn=slice_urn)
        slice_name = sURNObj.getName()
        auth = sURNObj.getAuthority()
        s_auths = string_to_urn_format(auth).split(':')
        auth = s_auths[0]
        if len(s_auths) > 1:
            project = s_auths[-1]
            self.logger.debug("From slice URN extracted project '%s'", project)

        if project is None and self.useProjects:
            if self.opts.project:
                # use the command line option --project
                project = self.opts.project
            elif self.config.has_key('default_project'):
                # otherwise, default to 'default_project' in 'omni_config'
                project = self.config['default_project']
            else:
                self.logger.info("No project specified")
                return None

        if auth is None:
            if not self.config.has_key('authority'):
                raise OmniError("Invalid configuration: no authority defined")
            auth = self.config['authority'].strip()
            self.logger.debug("From config got authority '%s'", auth)

        project_urn = None
        if project is not None:
            project_urn = URN(authority = auth,
                              type = 'project',
                              name = project).urn_string()
            self.logger.debug("Built project_urn '%s'", project_urn)

        options = {'fields': 
                   {'SLICE_NAME': slice_name,
                    }}
        if project_urn is not None:
            options['fields']['SLICE_PROJECT_URN'] = project_urn

        self.logger.debug("Submitting with options: %s", options)

        scred, options = self._add_credentials_and_speaksfor(scred, options)

        if not self.speakV2:
            (res, message) = _do_ssl(self, None, ("Create slice %s on %s %s" % (slice_name, self.fwtype, self.sa_url())),
                                     self.sa().create_slice, scred, options)
        else:
            (res, message) = _do_ssl(self, None, ("Create slice %s on %s %s" % (slice_name, self.fwtype, self.sa_url())),
                                     self.sa().create, "SLICE", scred, options)
        if res is not None:
            if res['code'] == 0:
                d = res['value']
                if d is not None and d.has_key('SLICE_URN'):
                    slice_urn = d['SLICE_URN']
                else:
                    self.logger.error("Malformed response from create slice: %s", d)
            else:
                # Duplicate is code 5 but v1.3 chapi erroneously
                # returns code 4 so check the output string too
                if res['code'] == 5 or \
                        res['output'].startswith("[DUPLICATE] DUPLICATE_ERROR"):
                    # duplicate
                    self.logger.info("Slice %s already existed - returning existing slice", slice_name)
                    if res.has_key('protogeni_error_url'):
                        self.logger.debug(" (Log url - look here for details on any failures: %s)" % res['protogeni_error_url'])
                    # Here we preserve current functionality -
                    # continue and pretend we created the slice. We
                    # could of course instead return an error
                    #msg = res['output']
                else:
                    # This includes if the slice already exists.
                    msg = "Error from server creating slice. Code %d: %s" % ( res['code'], res['output'])
                    if message and message.strip() != "":
                        msg = msg + " (%s)" % message
                    if res['code'] == 3 and "Unknown project" in res['output']:
                        msg = "Unknown project '%s'. Project names are case sensitive. Did you mis-type or mis-configure Omni?" % project
                    if res.has_key('protogeni_error_url'):
                        msg += " (Log url - look here for details on any failures: %s)" % res['protogeni_error_url']
                    self.logger.error(msg)
                    return None
        else:
            msg = "Error creating slice"
            if message is not None and message.strip() != "":
                msg = msg + ". %s" % message
            self.logger.error(msg)
            return None

        options['match'] = {'SLICE_URN': slice_urn,
                            'SLICE_EXPIRED': False,
                            }
        scred, options = self._add_credentials_and_speaksfor(scred, options)

        # This call is the same in V1 and V2
        (res, message) = _do_ssl(self, None, 
                                 ("Get credentials for slice %s on %s %s" % (slice_name, self.fwtype, self.sa_url())),
                                 self.sa().get_credentials, slice_urn, scred, 
                                 options)

        cred = None
        if res is not None:
            if res['code'] == 0:
                d = res['value']
                if d is not None:
                    cred = self._select_sfa_cred(d)
                    if cred is None:
                        self.logger.error("No slice credential returned for new slice %s" % slice_name)
                        self.logger.debug("Got %s", d)
                else:
                    self.logger.error("Malformed return getting slice credential for new slice %s" % slice_name)
                    self.logger.debug("Got %s", res)
            else:
                msg = "Error from server getting credential for new slice %s: %d: %s (%s)" % (slice_name, res['code'], res['output'], message)
                if res['code'] == 3:
                    self.logger.debug(msg)
                    msg = "Slice '%s' unknown. Does this slice already exist with a name using different case?" % slice_name
                if res.has_key('protogeni_error_url'):
                    msg += " (Log url - look here for details on any failures: %s)" % res['protogeni_error_url']
                self.logger.error(msg)
        else:
            msg = "Error getting credential for new slice %s" % slice_name
            if message is not None and message.strip() != "":
                msg = msg + ". %s" % message
            self.logger.error(msg)

        return cred

    def delete_slice(self, urn):
        # You cannot delete slices. Here, we check the slice is valid
        # and print the slice expiration. We could of course skip all that.

        if urn is None or urn.strip() == "":
            return "%s does not support deleting slices. (And no slice name was specified)" % self.fwtype

        scred = []
        # PG implemenation needs a user cred
        if self.needcred:
            uc, msg = self.get_user_cred(True)
            if uc is not None:
                scred.append(uc)

        project = None
        auth = None
        slice_urn = None
        if is_valid_urn(urn):
            sURNObj = URN(urn=urn)
            slice_name = sURNObj.getName()
            auth = sURNObj.getAuthority()
            s_auths = string_to_urn_format(auth).split(':')
            auth = s_auths[0]
            if len(s_auths) > 1:
                project = s_auths[-1]
                self.logger.debug("From slice URN extracted project '%s'", project)
            slice_urn = urn
        else:
            slice_name = urn

        if project is None and self.useProjects:
            if self.opts.project:
                # use the command line option --project
                project = self.opts.project
            elif self.config.has_key('default_project'):
                # otherwise, default to 'default_project' in 'omni_config'
                project = self.config['default_project']
            else:
                return "%s at %s does not support deleting slices. (And no project was specified)" % (self.fwtype, self.sa_url())

        if auth is None:
            if not self.config.has_key('authority'):
                return "%s does not support deleting slices. (And invalid configuration: no authority defined to construct slice urn)" % self.fwtype
            auth = self.config['authority'].strip()
            self.logger.debug("From config got authority '%s'", auth)

        if slice_urn is None:
            slice_urn = URN(authority=auth + ":" + project, type='slice', name=slice_name).urn_string()
            self.logger.debug("Constructed urn %s", slice_urn)

        if not is_valid_urn_bytype(slice_urn, 'slice', self.logger):
            return "%s does not support deleting slices. (And slice urn %s invalid)" % (self.fwtype, slice_urn)

        options = {'match': 
                   {'SLICE_URN': slice_urn,
                    'SLICE_EXPIRED': False,
                    }}
        options['filter'] = ['SLICE_URN', 'SLICE_EXPIRATION']
        self.logger.debug("Submitting with options: %s", options)

        scred, options = self._add_credentials_and_speaksfor(scred, options)

        if not self.speakV2:
            (res, message) = _do_ssl(self, None, ("Lookup slice %s on %s %s" % (slice_name, self.fwtype, self.sa_url())),
                                     self.sa().lookup_slices, scred, options)
        else:
            (res, message) = _do_ssl(self, None, ("Lookup slice %s on %s %s" % (slice_name, self.fwtype, self.sa_url())),
                                     self.sa().lookup, "SLICE", scred, options)
        slice_expiration = None
        msg = None
        if res is not None:
            if res['code'] == 0:
                d = res['value']
                if d is not None:
                    if d.has_key(slice_urn) and \
                                     d[slice_urn].has_key('SLICE_EXPIRATION'):
                        slice_expiration = d[slice_urn]['SLICE_EXPIRATION']
                        exp = naiveUTC(dateutil.parser.parse(slice_expiration, tzinfos=tzd))
                        if exp < naiveUTC(datetime.datetime.utcnow()):
                            self.logger.warn("Got expired slice %s at %s?", slice_urn, slice_expiration)
                    else:
                        # Likely the slice is already expired
                        msg = "%s does not support deleting slices. And Slice %s was not found - has it already expired?" % (self.fwtype, slice_name)
                else:
                    self.logger.error("Malformed response from lookup slice: %s", d)
                    msg = "%s does not support deleting slices. (And server error looking up slice %s)" % (self.fwtype, slice_name)
            else:
                # This includes if the slice already exists.
                msg = "%s does not support deleting slices. (And server error looking up slice %s)" % (self.fwtype, slice_name)
                if res['code'] == 3 and "Unknown slice urns" in res['output']:
                    msg += " - unknown slice"
                else:
                    msg += ". Code %d: %s" % ( res['code'], res['output'])
                    if message and message.strip() != "":
                        msg = msg + " (%s)" % message
#                if res.has_key('protogeni_error_url'):
#                    msg += " (Log url - look here for details on any failures: %s)" % res['protogeni_error_url']
        else:
            msg = "%s does not support deleting slices. (And server error looking up slice %s)" % (self.fwtype, slice_name)
            if message is not None and message.strip() != "":
                msg = msg + ". %s" % message

        if msg is None:
            msg = "%s does not support deleting slices - delete your resources and let slice %s expire instead" % (self.fwtype,
                                                                                                                   slice_name)
            if slice_expiration is not None:
                msg = msg + " at %s (UTC)." % slice_expiration
            else:
                msg = msg + "."
        return msg

    def list_aggregates(self):
        # TODO: list of field names from getVersion - should we get all or assume we have URN and URL
        options = {'filter':['SERVICE_URN', 'SERVICE_URL']}
        if not self.speakV2:
            (res, message) = _do_ssl(self, None, ("List Aggregates at %s %s" % (self.fwtype, self.ch_url)), 
                                     self.ch.lookup_aggregates,
                                     options
                                     )
        else:
            options['match']= {'SERVICE_TYPE' : 'AGGREGATE_MANAGER'}
            (res, message) = _do_ssl(self, None, ("List Aggregates at %s %s" % (self.fwtype, self.ch_url)), 
                                     self.ch.lookup, "SERVICE",
                                     [], options # Empty credential list
                                     )
        if message and message.strip() != "":
            self.logger.warn(message)
        aggs = dict()
        if res is not None:
            if res['value'] is not None and res['code'] == 0:
                for d in res['value']:
                    aggs[d['SERVICE_URN']] = d['SERVICE_URL']
            else:
                msg = "Server Error listing aggregates %d: %s" % (res['code'], res['output'])
                if res.has_key('protogeni_error_url'):
                    msg += " (Log url - look here for details on any failures: %s)" % res['protogeni_error_url']
                self.logger.warn(msg)
        else:
            self.logger.warn("Server Error listing aggregates - no results")

        return aggs

    def list_my_slices(self, user):
        '''List slices owned by the user (name or URN) provided, returning a list of slice URNs.'''

        scred = []
        # PG implementation needs a user cred
        if self.needcred:
            uc, msg = self.get_user_cred(True)
            if uc is not None:
                scred.append(uc)
            else:
                self.logger.debug("Failed to get user credential: %s", msg)

        userurn = self.member_name_to_urn(user)

        options = {'match': 
                   {'SLICE_EXPIRED': False, # Seems to be ignored
                        }}
        scred, options = self._add_credentials_and_speaksfor(scred, options)

        if not self.speakV2:
            (res, message) = _do_ssl(self, None, ("List Slices for %s at %s %s" % (user, self.fwtype, self.sa_url())), 
                                     self.sa().lookup_slices_for_member, userurn, scred, options)
        else:
            (res, message) = _do_ssl(self, None, ("List Slices for %s at %s %s" % (user, self.fwtype, self.sa_url())), 
                                     self.sa().lookup_for_member, "SLICE", userurn, scred, options)


        slices = None
        if res is not None:
            if res['code'] == 0:
                slices = res['value']
            else:
                msg = "Failed to list slices for %s" % user
                msg += ". Server said: %s" % res['output']
                if res.has_key('protogeni_error_url'):
                    msg += " (Log url - look here for details on any failures: %s)" % res['protogeni_error_url']
                raise OmniError(msg)
        else:
            msg = "Failed to list slices for %s" % user
            if message is not None and message.strip() != "":
                msg += ": %s" % message
            raise OmniError(msg)

        # Return is a struct with the URN
        slicenames = list()
        if slices and isinstance(slices, list):
            for tup in slices:
                slice = tup['SLICE_URN']
                slicelower = string.lower(slice)
                if not string.find(slicelower, "+slice+"):
                    self.logger.debug("Skipping non slice URN '%s'", slice)
                    continue
                slicename = slice
                # Returning this key is non-standard..
                if tup.has_key('EXPIRED'):
                    exp = tup['EXPIRED']
                    if exp == True:
                        self.logger.debug("Skipping expired slice %s", slice)
                        continue
                slicenames.append(slicename)
        return slicenames

    def list_my_projects(self, user):
        '''List projects owned by the user (name or URN) provided, returning a list of structs, containing
        PROJECT_URN, PROJECT_UID, EXPIRED, and PROJECT_ROLE. EXPIRED is a boolean.'''

        if not self.useProjects:
            msg = "%s at %s does not support projects: no projects to list" % (self.fwtype, self.sa_url())
            self.logger.info(msg)
            return (None, msg)

        scred = []
        # If PG supported projects, it would likely need a user cred
        if self.needcred:
            uc, msg = self.get_user_cred(True)
            if uc is not None:
                scred.append(uc)

        userurn = self.member_name_to_urn(user)

        options = {}
        scred, options = self._add_credentials_and_speaksfor(scred, options)

        if not self.speakV2:
            (res, message) = _do_ssl(self, None, ("List Projects for %s at %s %s" % (user, self.fwtype, self.sa_url())), 
                                     self.sa().lookup_projects_for_member, userurn, scred, options)
        else:
            (res, message) = _do_ssl(self, None, ("List Projects for %s at %s %s" % (user, self.fwtype, self.sa_url())), 
                                     self.sa().lookup_for_member, "PROJECT", userurn, scred, options)

        projects = None
        if res is not None:
            if res['code'] == 0:
                projects = res['value']
            else:
                msg = "Failed to list projects for %s" % user
                msg += ". Server said: %s" % res['output']
                if res.has_key('protogeni_error_url'):
                    msg += " (Log url - look here for details on any failures: %s)" % res['protogeni_error_url']
                raise OmniError(msg)
        else:
            msg = "Failed to list projects for %s" % user
            if message is not None and message.strip() != "":
                msg += ": %s" % message
            raise OmniError(msg)

        # listslices returned just a list of URNs
        # listprojects in the patch returned the full tuple that adds the user's role, if the project is expired, and the project UID

        return (projects, res['output'])

    def slice_name_to_urn(self, name):
        """Convert a slice name to a slice urn."""

        if name is None or name.strip() == '':
            raise OmniError('Empty slice name')

        project = None
        auth = None

        if is_valid_urn(name):
            urn = URN(None, None, None, name)
            if not urn.getType() == "slice":
                raise OmniError("Invalid Slice name: got a non Slice URN %s" % name)
            if not is_valid_urn_bytype(name, 'slice', self.logger):
                raise OmniError("Invalid slice name '%s'" % name)

            urn_fmt_auth = string_to_urn_format(urn.getAuthority())

            # if config has an authority, make sure it matches
            if self.config.has_key('authority'):
                auth = self.config['authority']
                if not urn_fmt_auth.startswith(auth):
                    self.logger.warn("CAREFUL: slice' authority (%s) doesn't match current configured authority (%s)" % (urn_fmt_auth, auth))
                    self.logger.info("This may be OK though if you are using delegated slice credentials...")
#                    raise OmniError("Invalid slice name: slice' authority (%s) doesn't match current configured authority (%s)" % (urn_fmt_auth, auth))

            if self.useProjects:
                # Make sure the auth has a project
                s_auths = urn_fmt_auth.split(':')
                auth = s_auths[0]
                if len(s_auths) > 1 and s_auths[-1].strip() != "":
                    project = s_auths[-1]
                    # FIXME: Validate the project
                    self.logger.debug("From slice URN extracted project '%s'", project)
                    return name
                else:
                    # Can we get a project from options or config?
                    if self.opts.project:
                        # use the command line option --project
                        project = self.opts.project
                        self.logger.warn("Invalid slice URN - no project. Using project from commandline.")
                    elif self.config.has_key('default_project'):
                        # otherwise, default to 'default_project' in 'omni_config'
                        project = self.config['default_project']
                        self.logger.warn("Invalid slice URN - no project specified. Will use default from config")
                    else:
                        raise OmniError("Invalid slice URN missing project. Specify a project with --project or a default_project in your omni_config")

                    # Fall through so we can produce a new URN
                    name = urn.getName()
            else:
                # Valid slice URN (not using projects) - use it
                return name

        # No valid slice urn provided

        if not auth:
            if not self.config.has_key('authority'):
                raise OmniError("Invalid configuration: no authority defined")
            else:
                auth = self.config['authority']
        if self.useProjects:
            if not project:
                if self.opts.project:
                    # use the command line option --project
                    project = self.opts.project
                    self.logger.debug("Using project from commandline.")
                elif self.config.has_key('default_project'):
                    # otherwise, default to 'default_project' in 'omni_config'
                    project = self.config['default_project']
                    self.logger.debug("Will use default_project from config")
                else:
                    raise OmniError("Project name required. Specify a project with --project or a default_project in your omni_config")
            auth = auth + ':' + project
        urnstr = URN(auth, "slice", name).urn_string()
        if not is_valid_urn_bytype(urnstr, 'slice', self.logger):
            raise OmniError("Invalid slice name '%s'" % name)
        return urnstr

    def project_name_to_urn(self, name):
        """Convert a project name to a project urn."""

        if name is None or name.strip() == '':
            raise OmniError('Empty project name')

        auth = None

        if is_valid_urn(name):
            urn = URN(None, None, None, name)
            if not urn.getType() == "project":
                raise OmniError("Invalid Project name: got a non Project URN %s" % name)
            if not is_valid_urn_bytype(name, 'project', self.logger):
                raise OmniError("Invalid project name '%s'" % name)

            urn_fmt_auth = string_to_urn_format(urn.getAuthority())

            # if config has an authority, make sure it matches
            if self.config.has_key('authority'):
                auth = self.config['authority']
                if not urn_fmt_auth == auth:
                    self.logger.warn("CAREFUL: slice' authority (%s) doesn't match current configured authority (%s)" % (urn_fmt_auth, auth))
                    self.logger.info("This may be OK though if you are using delegated slice credentials...")
#                    raise OmniError("Invalid project name: slice' authority (%s) doesn't match current configured authority (%s)" % (urn_fmt_auth, auth))

                # Valid project URN - use it
                return name

        # No valid project urn provided

        if not auth:
            if not self.config.has_key('authority'):
                raise OmniError("Invalid configuration: no authority defined")
            else:
                auth = self.config['authority']
        urnstr = URN(auth, "project", name).urn_string()
        if not is_valid_urn_bytype(urnstr, 'project', self.logger):
            raise OmniError("Invalid project name '%s'" % name)
        return urnstr

    def member_name_to_urn(self, name):
        """Convert a member name to a member urn."""

        if name is None or name.strip() == '':
            raise OmniError('Empty member name')

        if is_valid_urn(name):
            urn = URN(None, None, None, name)
            if not urn.getType() == "user":
                raise OmniError("Invalid member name: got a non member URN '%s'", name)
            if not is_valid_urn_bytype(name, 'user', self.logger):
                raise OmniError("Invalid user name '%s'" % name)
            # if config has an authority, make sure it matches
            if self.config.has_key('authority'):
                auth = self.config['authority']
                urn_fmt_auth = string_to_urn_format(urn.getAuthority())
                if urn_fmt_auth != auth:
                    self.logger.warn("CAREFUL: member's authority (%s) doesn't match current configured authority (%s)" % (urn_fmt_auth, auth))
            return name

        if not self.config.has_key('authority'):
            raise OmniError("Invalid configuration: no authority defined")

        auth = self.config['authority']
        urnstr = URN(auth, "user", name).urn_string()
        if not is_valid_urn_bytype(urnstr, 'user', self.logger):
            raise OmniError("Invalid user name '%s'" % name)
        return urnstr

    def get_slice_expiration(self, urn):
        scred = []
        # PG implementation needs a user cred
        if self.needcred:
            uc, msg = self.get_user_cred(True)
            if uc is not None:
                scred.append(uc)
        options = {'match': 
                   {'SLICE_URN': urn,
                    'SLICE_EXPIRED': False,
                    }}
        options['filter'] = ['SLICE_URN', 'SLICE_EXPIRATION', 'SLICE_EXPIRED']
        self.logger.debug("Submitting lookup_slices with options: %s", options)
        scred, options = self._add_credentials_and_speaksfor(scred, options)
        res = None
        if not self.speakV2:
            (res, message) = _do_ssl(self, None, ("Lookup slice %s on %s %s" % (urn, self.fwtype,self.sa_url())),\
                                         self.sa().lookup_slices, scred, options)
        else:
            (res, message) = _do_ssl(self, None, ("Lookup slice %s on %s %s" % (urn, self.fwtype,self.sa_url())),\
                                         self.sa().lookup, "SLICE", scred, options)

        slice_expiration = None
        msg = None
        if res is not None:
            if res['code'] == 0:
                d = res['value']
                if d is not None:
                    if d.has_key(urn):
                        if d[urn].has_key('SLICE_EXPIRED'):
                            expired = d[urn]['SLICE_EXPIRED']
                        if d[urn].has_key('SLICE_EXPIRATION'):
                            slice_expiration = d[urn]['SLICE_EXPIRATION']
                            exp = naiveUTC(dateutil.parser.parse(slice_expiration, tzinfos=tzd))
                            if exp < naiveUTC(datetime.datetime.utcnow()):
#                                if not expired:
#                                    self.logger.debug('CH says it is not expired, but expiration is in past?')
                                self.logger.warn("CH says slice %s expired at %s UTC", urn, slice_expiration)
#                            elif expired:
#                                self.logger.debug('CH says slice expired, but expiration %s is not in past?', slice_expiration)
#                            self.logger.debug("lookup_slices on %s found expiration %s", urn, exp)
                            return exp
                    else:
                        self.logger.error("Slice %s was not found - has it already expired?" % urn)
                else:
                    self.logger.error("Malformed response from lookup slice: %s", d)
            else:
                msg = "Server Error looking up slice %s" % urn
                if res['code'] == 3 and "Unknown slice urns" in res['output']:
                    msg += " - unknown slice"
                else:
                    msg += ". Code %d: %s" % ( res['code'], res['output'])
                    if message and message.strip() != "":
                        msg = msg + " (%s)" % message
                if res.has_key('protogeni_error_url'):
                    msg += " (Log url - look here for details on any failures: %s)" % res['protogeni_error_url']
                self.logger.error(msg)
        else:
            msg = "Server Error looking up slice %s" % urn
            if message is not None and message.strip() != "":
                msg = msg + ". %s" % message
            self.logger.error(msg)

        return None

    def renew_slice(self, urn, expiration_dt):
        """Renew a slice.

        urn is framework urn, already converted via slice_name_to_urn.
        requested_expiration is a datetime object.

        Returns the expiration date as a datetime. If there is an error,
        print it and return None.
        """
        scred = []
        # PG implementation needs a slice cred
        if self.needcred:
            sc = self.get_slice_cred_struct(urn)
            if sc is not None:
                scred.append(sc)

        expiration = naiveUTC(expiration_dt).isoformat()
        self.logger.info('Requesting new slice expiration %r', expiration)
        options = {'fields':{'SLICE_EXPIRATION':expiration}}
        options['match'] = {'SLICE_URN': urn,
                            'SLICE_EXPIRED': False,
                            }
        res = None

        scred, options = self._add_credentials_and_speaksfor(scred, options)

        if not self.speakV2:
            (res, message) = _do_ssl(self, None, 
                                     ("Renew slice %s on %s %s until %s" % (urn, self.fwtype, self.sa_url(), expiration_dt)), 
                                     self.sa().update_slice, urn, scred, options)
        else:
            (res, message) = _do_ssl(self, None, 
                                     ("Renew slice %s on %s %s until %s" % (urn, self.fwtype, self.sa_url(), expiration_dt)), 
                                     self.sa().update, "SLICE", urn, scred, options)

        b = False
        if res is not None:
            if res['code'] == 0:
                b = True
            else:
                message = res['output']
                if res.has_key('protogeni_error_url'):
                    message += " (Log url - look here for details on any failures: %s)" % res['protogeni_error_url']
        if message is not None and message.strip() != "":
            self.logger.error(message)

        if b:
            # Fetch new expiration and make sure it is what was requested
            slice_expiration = self.get_slice_expiration(urn)

            if slice_expiration is not None:
                try:
                    sliceexp = naiveUTC(slice_expiration)
                    # If request is diff from sliceexp then log a warning
                    if abs(sliceexp - naiveUTC(expiration_dt)) > datetime.timedelta.resolution:
                        self.logger.warn("Renewed %s slice %s expiration %s UTC is different than requested: %s UTC", self.fwtype, urn, sliceexp, expiration_dt)
                        return sliceexp
#                    else:
#                        self.logger.debug("Requested %s close to new %s", expiration_dt, slice_expiration)
                except Exception, e:
                    self.logger.debug("Exception checking if requested %s is close to new %s: %s", expiration_dt, slice_expiration, e)
                    pass

                # Was able to look up new expiration and either it is close or had an error comparing it. Report what they got.
                return slice_expiration
            # Did not manage to look up the new expiration, but the SA said the renew succeeded. Tell user they got their request
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
        cred, message = self.get_user_cred(struct=True)
        if cred and not isinstance(cred, dict):
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
        return self.get_slice_cred(urn, struct=True)

    def get_version(self):
        # Do getversion at the CH (service registry), MA, and SA
        response = dict()
        versionstruct = dict()
        types = {'ch': ('Clearinghouse', self.ch_url, self.ch), 'ma':
                     ('Member Authority', self.ma_url(), self.ma()),
                 'sa': ('Slice Authority', self.sa_url(), self.sa())}

        for service in types.keys():
            (response, message) = _do_ssl(self, None, ("GetVersion of %s %s %s using cert %s" % (self.fwtype,types[service][0], types[service][2], self.config['cert'])), types[service][2].get_version)
            _ = message #Appease eclipse
            if response is None:
                self.logger.error("Failed to get version of %s %s: %s", self.fwtype,types[service][0], message)
                continue
            if isinstance(response, dict) and response.has_key('code'):
                code = response['code']
                if code:
                    self.logger.error("Failed to get version of %s %s: Received error code: %d: %s", self.fwtype,types[service][0], code,
                                      response['output'])
                else:
                    versionstruct[types[service][0]] = response['value']
                    if not versionstruct[types[service][0]].has_key('url'):
                        versionstruct[types[service][0]]["url"] = types[service][1]
            else:
                versionstruct[types[service][0]] = response
                if not versionstruct[types[service][0]].has_key('url'):
                    versionstruct[types[service][0]]["url"] = types[service][1]
        return versionstruct, message


    def _get_member_email(self, urn):
        if urn is None or urn.strip() == "" or not is_valid_urn_bytype(urn, 'user', None):
            return None
        creds = []
        # PG implementation seems to want a user cred
        if self.needcred:
            uc, msg = self.get_user_cred(True)
            if uc is not None:
                creds.append(uc)
        options = {'match': {'MEMBER_URN': urn}, 'filter': ['MEMBER_EMAIL']}
        creds, options = self._add_credentials_and_speaksfor(creds, options)
        if not self.speakV2:
            res, mess = _do_ssl(self, None, "Looking up member email",
                                self.ma().lookup_identifying_member_info, creds, options)
        else:
            res, mess = _do_ssl(self, None, "Looking up member email",
                                self.ma().lookup, "MEMBER", creds, options)

        logr = self._log_results((res, mess), 'Lookup member email')
        if logr == True:
            if not res['value'] and isinstance(res['value'], dict) and len(res['value'].values()) > 0 and res['value'].values()[0].has_key('MEMBER_EMAIL'):
                self.logger.debug("Got malformed return looking up member email: %s", res)
                return None
            else:
                return res['value'].values()[0]['MEMBER_EMAIL']
        else:
            return None

    def _get_member_keys(self, urn):
        if urn is None or urn.strip() == "" or not is_valid_urn_bytype(urn, 'user', None):
            return None
        # FIXME: Duplicates logic in list_ssh_keys, which has more
        # error checking
        creds = []
        # Could grab KEY_PRIVATE here too, but not useful I think
        options = {'match': {'KEY_MEMBER': urn}, 'filter': ['KEY_PUBLIC']}

        # PG implementation seems to want a user cred
        if self.needcred:
            uc, msg = self.get_user_cred(True)
            if uc is not None:
                creds.append(uc)

        creds, options = self._add_credentials_and_speaksfor(creds, options)

        if not self.speakV2:
            res, mess = _do_ssl(self, None, "Looking up member %s SSH keys" % urn,
                                self.ma().lookup_keys, creds, options)
        else:
            res, mess = _do_ssl(self, None, "Looking up member %s SSH keys" % urn,
                                self.ma().lookup, "KEY", creds, options)
            # In V1, we get a dictionary of KEY_MEMBER => KEY_PUBLIC, KEY_PRIVATE
            # In V2, we get a dictionary of KEY_ID => KEY_MEMBER, KEY_PUBLIC, KEY_PRIVATE
            # We only asked for one person so flip back to V1 format
            if res['code'] == 0:
                res['value'] = {urn : res['value'].values()}

        logr = self._log_results((res, mess), 'Lookup member %s SSH keys' % urn)
        if logr == True:
            if not res['value']:
                return None
            else:
                # FIXME: Check we got answer for requested user
                # FIXME: Handle a user has no public key
                return [val['KEY_PUBLIC'] for val in res['value'].values()[0]]
        else:
            return None

    # get the members (urn, email) and their ssh keys and role in the slice
    def get_members_of_slice(self, urn):
        # FIXME: This seems to list members even of an expired slice,
        # if that is the most recent slice by this name
        # Shouldn't the SA check this?

        slice_urn = self.slice_name_to_urn(urn)

        creds = []
        if self.needcred:
            # FIXME: At PG both a user cred and a slice cred seem to work
            # Which is correct?
#            uc, msg = self.get_user_cred(True)
#            if uc is not None:
#                creds.append(uc)
            sc = self.get_slice_cred_struct(slice_urn)
            if sc is not None:
                creds.append(sc)

        slice_expiration = self.get_slice_expiration(slice_urn)

        expired = False
        expmess = ""
        if slice_expiration is not None:
            exp = naiveUTC(slice_expiration)
            if exp < naiveUTC(datetime.datetime.utcnow()):
                expired = True
                expmess = " (EXPIRED at %s UTC)" % exp
        else:
            # Probably the slice doesn't exist or you don't have
            # rights on it
            return ([], "Error looking up slice %s - check the logs" % slice_urn)

        options = {'match': 
                   {'SLICE_URN': slice_urn,
                    'SLICE_EXPIRED': False,  # FIXME: This gets ignored
                    }}

        creds, options = self._add_credentials_and_speaksfor(creds, options)
        if not self.speakV2:
            res, mess = _do_ssl(self, None, "Looking up %s slice %s members at %s" % (self.fwtype, slice_urn, self.sa_url()),
                                self.sa().lookup_slice_members, slice_urn, 
                                creds, options)
        else:
            res, mess = _do_ssl(self, None, "Looking up %s slice %s members at %s" % (self.fwtype, slice_urn, self.sa_url()),
                                self.sa().lookup_members, "SLICE", slice_urn, 
                                creds, options)
        members = []
        logr = self._log_results((res, mess), 'Get members for %s slice %s%s' % (self.fwtype, slice_urn, expmess))
        if logr == True:
            if res['value']:
                for member_vals in res['value']:
                    member_urn = member_vals['SLICE_MEMBER']
                    member_role = member_vals['SLICE_ROLE']
                    member = {'URN': member_urn}
                    member['EMAIL'] = self._get_member_email(member_urn)
                    member['KEYS'] = self._get_member_keys(member_urn)
                    member['ROLE'] = member_role
                    members.append(member)
        else:
            mess = logr
        if (not mess or mess.strip() == "") and expmess != "":
            mess = expmess
        return members, mess

    # get the members (urn, email) and their role in the project
    def get_members_of_project(self, project_name):
        '''Look up members of the project with the given name.
        Return is a list of member dictionaries
        containing PROJECT_MEMBER (URN), EMAIL, [if found: PROJECT_MEMBER_UID], and PROJECT_ROLE.
        '''
        # Bail if projects not supported
        if not self.useProjects:
            return [], "%s %s does not use projects" % (self.fwtype, self.sa_url())
        # FIXME: return the raw struct and do the member lookup as a separate thing?
        # FIXME: Note if the project is expired and when it expired?
        project_urn = self.project_name_to_urn(project_name)

        creds = []
        # If PG supported projects, they'd want a user cred
        if self.needcred:
            uc, msg = self.get_user_cred(True)
            if uc is not None:
                creds.append(uc)

        options = {'match': 
                   {'PROJECT_URN': project_urn,
                    'PROJECT_EXPIRED': False,  # FIXME: This gets ignored
                    }}

        creds, options = self._add_credentials_and_speaksfor(creds, options)
        if not self.speakV2:
            res, mess = _do_ssl(self, None, "Looking up %s project %s members at %s" % (self.fwtype, project_urn, self.sa_url()),
                                self.sa().lookup_project_members, project_urn, 
                                creds, options)
        else:
            res, mess = _do_ssl(self, None, "Looking up %s project %s members at %s" % (self.fwtype, project_urn, self.sa_url()),
                                self.sa().lookup_members, "PROJECT", project_urn, 
                                creds, options)
        members = []
        logr = self._log_results((res, mess), 'Get members for %s project %s' % (self.fwtype, project_urn))
        if logr == True:
            if res['value']:
                for member_vals in res['value']:
                    # Entries: PROJECT_MEMBER, PROJECT_ROLE, optional: PROJECT_MEMBER_UID
                    # self.logger.debug("Got member value: %s", member_vals)
                    member_urn = member_vals['PROJECT_MEMBER']
                    member_role = member_vals['PROJECT_ROLE']
                    member = {'PROJECT_MEMBER': member_urn}
                    member['EMAIL'] = self._get_member_email(member_urn)
                    member['PROJECT_ROLE'] = member_role
                    if member_vals.has_key('PROJECT_MEMBER_UID'):
                        member['PROJECT_MEMBER_UID'] = member_vals['PROJECT_MEMBER_UID']
                    members.append(member)
        else:
            mess = logr
        return members, mess

    # add a new member to a slice
    def add_member_to_slice(self, slice_urn, member_name, role = 'MEMBER'):
        role2 = str(role).upper()
        if role2 == 'LEAD':
            raise OmniError("Cannot add a lead to a slice. Try role 'ADMIN'")
        if role2 not in ['LEAD','ADMIN', 'MEMBER', 'AUDITOR']:
            raise OmniError("Unknown role '%s'. Use ADMIN, MEMBER, or AUDITOR" % role)
        slice_urn = self.slice_name_to_urn(slice_urn)
        creds = []
        if self.needcred:
            # FIXME: Either user or slice cred work at PG. Which is correct?
            sc = self.get_slice_cred_struct(slice_urn)
            if sc is not None:
                creds.append(sc)
        member_urn = self.member_name_to_urn(member_name)
        options = {'members_to_add': [{'SLICE_MEMBER': member_urn,
                                       'SLICE_ROLE': role}]}
#        options['match'] = {'SLICE_URN': slice_urn,
#                            'SLICE_EXPIRED': False,
#                            }
        creds, options = self._add_credentials_and_speaksfor(creds, options)
        if not self.speakV2:
            res, mess = _do_ssl(self, None, "Adding member %s to %s slice %s at %s" %  (member_urn, self.fwtype, slice_urn, self.sa_url()),
                                self.sa().modify_slice_membership,
                                slice_urn, creds, options)
        else:
            res, mess = _do_ssl(self, None, "Adding member %s to %s slice %s at %s" %  (member_urn, self.fwtype, slice_urn, self.sa_url()),
                                self.sa().modify_membership, "SLICE",
                                slice_urn, creds, options)

        # FIXME: do own result checking to detect DUPLICATE

        logr = self._log_results((res, mess), 'Add member %s to %s slice %s' % (member_urn, self.fwtype, slice_urn))
        if logr == True:
            success = logr
        else:
            success = False
            mess = logr
        return (success, mess)

    # remove a member from a slice
    def remove_member_from_slice(self, slice_urn, member_name):
        slice_urn = self.slice_name_to_urn(slice_urn)
        creds = []
        if self.needcred:
            # FIXME: Either user or slice cred work at PG. Which is correct?
            sc = self.get_slice_cred_struct(slice_urn)
            if sc is not None:
                creds.append(sc)
        member_urn = self.member_name_to_urn(member_name)
        options = {'members_to_remove': [ member_urn]}
        creds, options = self._add_credentials_and_speaksfor(creds, options)
        if not self.speakV2:
            res, mess = _do_ssl(self, None, "Removing member %s from %s slice %s at %s" %  (member_urn, self.fwtype, slice_urn, self.sa_url()),
                                self.sa().modify_slice_membership,
                                slice_urn, creds, options)
        else:
            res, mess = _do_ssl(self, None, "Removing member %s from %s slice %s at %s" %  (member_urn, self.fwtype, slice_urn, self.sa_url()),
                                self.sa().modify_membership, "SLICE", 
                                slice_urn, creds, options)

        logr = self._log_results((res, mess), 'Remove member %s from %s slice %s' % (member_urn, self.fwtype, slice_urn))
        if logr == True:
            success = logr
        else:
            success = False
            mess = logr
        return (success, mess)

    # handle logging or results for db functions
    def _log_results(self, results, action):
        (res, message) = results
        if res is not None:
            if res.has_key('code') and res.has_key('value') and res['code'] == 0:
                self.logger.debug('Successfully completed ' + action)
                return True
            else:
                msg = action + ' failed'
                if message and message.strip() != "":
                    msg += ". " + message
                if res.has_key('output') and res['output'].strip() !=  "":
                    msg += ". Server said: " + res['output']
                if res.has_key('protogeni_error_url'):
                    msg += " (Log url - look here for details on any failures: %s)" % res['protogeni_error_url']
                # In APIv3 if you renew while allocated then the slice
                # has not yet been recorded and will be unknown
                if self.opts.api_version > 2 and "ARGUMENT_ERROR (Unknown slice urns: [[None]])" in msg and "Record sliver" in msg:
                    msg = msg + " ...  deleting a slice only allocated or never recorded causes this. Expected & harmless."
                    self.logger.debug(msg)
                elif "ARGUMENT_ERROR (Unknown sli" in msg and "Update sliver" in action:
                    # Called update but the sliver is not known
                    msg = "Cannot update sliver - not registered. Register the sliver. " + msg
                    self.logger.debug(msg)
                elif "ARGUMENT_ERROR (Unknown sli" in msg and "Record sliver" in action and "deleted" in action:
                    # Called delete but the sliver is not known. Harmless.
                    msg = "Sliver was not registered to delete it. " + msg
                    self.logger.debug(msg)
                else:
                    self.logger.warn(msg)
                return msg
        else:
            msg = action + ' failed'
            if message and message.strip() != "":
                msg += ". Server said: " + message
            else:
                msg += " for unknown reason"
            self.logger.warn(msg)
            return msg
        return False

    # A poor check for valid sliver URNs, to avoid complaining about
    # technically illegal characters in sliver names
    def _weakSliverValidCheck(self, sliver_urn):
        if not is_valid_urn(sliver_urn):
            self.logger.debug("Invalid sliver urn '%s'", sliver_urn)
            return False
        urnObj = URN(urn=sliver_urn)
        if not urnObj.getType().lower() == 'sliver':
            self.logger.debug("Sliver URN '%s' not of type sliver, but '%s'", sliver_urn, urnObj.getType())
            return False
        name = urnObj.getName()
        if len(name) == 0:
            self.logger.debug("Sliver URN '%s' has empty name", sliver_urn)
            return False
        auth = urnObj.getAuthority()
        if len(auth) == 0:
            self.logger.debug("Sliver URN '%s' has empty authority", sliver_urn)
            return False
        return True

    # Guess the aggregate URN from the sliver URN
    def _getAggFromSliverURN(self, sliver_urn):
        if not self._weakSliverValidCheck(sliver_urn):
            return None
        idx1 = sliver_urn.find('+sliver+')
        auth = sliver_urn[0 : idx1]
        return auth + '+authority+am'

    # Helper for actually recording a new sliver with the given expiration
    def _record_one_new_sliver(self, sliver_urn, slice_urn, agg_urn,
                               creator_urn, expiration):
        creds = []
        if self.needcred:
            # FIXME: At PG should this be user or slice cred?
            # They don't seem to be requiring either one?
#            uc, msg = self.get_user_cred(True)
#            if uc is not None:
#                creds.append(uc)
            sc = self.get_slice_cred_struct(slice_urn)
            if sc is not None:
                creds.append(sc)

        if not is_valid_urn(agg_urn):
            self.logger.debug("Not a valid AM URN: %s", agg_urn)
            agg_urn = None
        if sliver_urn is None or sliver_urn.strip() == "":
            self.logger.warn("Empty sliver urn to record")
            return ""

        # The full check punishes the experimenter for an AM's
        # malformed sliver URNs, which I think is wrong and confusing.
#        if not is_valid_urn_bytype(sliver_urn, 'sliver', self.logger):
        if not self._weakSliverValidCheck(sliver_urn):
            self.logger.debug("Invalid sliver urn but continuing: '%s'", sliver_urn)
#                   return ""

        if not agg_urn:
            agg_urn = self._getAggFromSliverURN(sliver_urn)
            if not is_valid_urn(agg_urn):
                self.logger.warn("Invalid aggregate URN '%s' for recording new sliver from sliver urn '%s'", agg_urn, sliver_urn)
                return ""
        elif sliver_urn.startswith(slice_urn) and ('al2s' in agg_urn or 'foam' in agg_urn):
            # Work around a FOAM/AL2S bug producing bad sliver URNs
            # See http://groups.geni.net/geni/ticket/1294
            self.logger.debug("Malformed sliver URN '%s'. Assuming this is OK anyhow at this FOAM based am: %s. See http://groups.geni.net/geni/ticket/1294", sliver_urn, agg_urn)
        else:
            # The authority of the agg_urn should be the start of the authority of the sliver auth
            # this allows a sliver at exogeni.net:bbn to be recorded under the AM exogeni.net
            agg_auth = agg_urn[0 : agg_urn.find('authority+')]
            idx1 = sliver_urn.find('sliver+')
            auth = sliver_urn[0 : idx1]
            slice_auth = slice_urn[0 : slice_urn.find('slice+')]
            if not auth.startswith(agg_auth):
                self.logger.debug("Skipping sliver '%s' that doesn't appear to come from the specified AM '%s'", sliver_urn,
                                  agg_urn)
                return ""
        # FIXME: This assumes the sliver was created now, which isn't strictly true on create,
        # and is certainly wrong if we are doing a create because the update failed
        fields = {"SLIVER_INFO_URN": sliver_urn,
                  "SLIVER_INFO_SLICE_URN": slice_urn,
                  "SLIVER_INFO_AGGREGATE_URN": agg_urn,
                  "SLIVER_INFO_CREATOR_URN": creator_urn,
                  "SLIVER_INFO_CREATION": datetime.datetime.utcnow().isoformat()}

        options = {'fields' : fields}
        if (expiration):
            # Note that if no TZ specified, UTC is assumed
            fields["SLIVER_INFO_EXPIRATION"] = str(expiration)

        self.logger.debug("Recording new slivers with options: %s", options)
        creds, options = self._add_credentials_and_speaksfor(creds, options)
        if not self.speakV2:
            res = _do_ssl(self, None, "Recording sliver '%s' creation at %s %s" % (sliver_urn, self.fwtype, self.sa_url()),
                          self.sa().create_sliver_info, creds, options)
        else:
            res = _do_ssl(self, None, "Recording sliver '%s' creation at %s %s" % (sliver_urn, self.fwtype, self.sa_url()),
                          self.sa().create, "SLIVER_INFO", creds, options)
        return self._log_results(res, "Record sliver '%s' creation at %s" % (sliver_urn, self.fwtype))

    # write new sliver_info to the database using chapi
    # Manifest is the XML when using APIv1&2 and none otherwise
    # expiration is the slice expiration
    # slivers is the return struct from APIv3+ or None
    # If am_urn is not provided, infer it from the url
    # If both are not provided, infer the AM from the sliver URNs
    # If the URN is in the agg nicknames or getversion or I think in the service registry,
    # It should already be filled in here
    def create_sliver_info(self, manifest, slice_urn,
                              aggregate_url, expiration, slivers, am_urn):
        if is_valid_urn(am_urn):
            self.logger.debug("Using AM URN %s", am_urn)
            agg_urn = am_urn
        elif aggregate_url is None or aggregate_url.strip() == "":
            self.logger.warn("Empty aggregate URL for recording new slivers")
            # Just get the URN from the manifest or slivers
            agg_urn = None
        else:
            # Have a URL but no URN

            # FIXME: I can't actually call this here cause the config here is missing nicknames
#            turn = _lookupAggURNFromURLInNicknames(self.logger, self.config, aggregate_url)
#            if is_valid_urn(turn):
#                agg_urn = turn
#            else:
            agg_urn = self.lookup_agg_urn_by_url(aggregate_url)
#            if not is_valid_urn(agg_urn):
#                self.logger.warn("Invalid aggregate URN %s for recording new sliver from url %s", agg_urn, aggregate_url)
#                return
        creator_urn = self.user_urn
        slice_urn = self.slice_name_to_urn(slice_urn)
        if not is_valid_urn(slice_urn):
            self.logger.warn("Invalid slice URN '%s' for recording new slivers", slice_urn)
            return
        creds = []
        msg = ""

        if manifest and manifest.strip() != "" and (slivers is None or len(slivers) == 0):
            # APIv1/2: find slivers in manifest
            self.logger.debug("Finding new slivers to record in manifest")
            # Loop through manifest finding all slivers to record
            foundSlivers = False
            while True:
                idx1 = manifest.find('sliver_id=') # Start of 'sliver_id='
                if idx1 < 0: break # No more slivers
                idx2 = manifest.find('"', idx1) + 1 # Start of URN
                if idx2 == 0:
                    # didn't find start of sliver id?
                    self.logger.debug("Malformed sliver_id in rspec? %s", manifest[:30])
                    manifest = manifest[9:]
                    continue
                idx3 = manifest.find('"', idx2) # End of URN
                if idx3 == 0:
                    # didn't find end of sliver id?
                    self.logger.debug("Malformed sliver_id in rspec? %s", manifest[idx2-15:idx2+80])
                    manifest = manifest[idx2:]
                    continue
                sliver_urn = manifest[idx2 : idx3]
                manifest = manifest[idx3+1:]
                foundSlivers = True
                msg = msg + str(self._record_one_new_sliver(sliver_urn,
                                                        slice_urn, agg_urn, creator_urn, expiration))
            # End of while loop over slivers in manifest

            # Ticket #574
            # If we have an am_urn and have a manifest and this is a FOAM manifest/AM, then we have no sliver_urns yet probably.
            # If we call sliverstatus here, we could get from geni_urn the UID that really IDs the sliver.
            # But that would be expensive, and we don't really care.
            # Instead, create a UID and attach that to the AM URN piece and record that as the sliver URN.
            # A hack, but it works
            if not foundSlivers and "resources/rspec/ext/openflow" in manifest and "manifest" in manifest and "sliver" in manifest and is_valid_urn(agg_urn):
                # Extract the authority from the agg_urn
                amURNO = URN(urn=agg_urn)
                auth = amURNO.getAuthority()
                # generate a UID
                sliver_uuid = uuid.uuid1() # uid based on current host and current time
                # Make a sliver URN from that
                sliver_urn = URN(authority=auth, type="sliver", name=str(sliver_uuid)).urn_string()
                self.logger.debug("Recording sliver_info had manifest with no sliver_ids (FOAM?). Created a single sliver urn to record: %s", sliver_urn)
                # Record one new sliver with that
                msg = msg + str(self._record_one_new_sliver(sliver_urn,
                                                        slice_urn, agg_urn, creator_urn, expiration))

        elif slivers and len(slivers) > 0:
            # APIv3 style sliver to record
            self.logger.debug("Recording new slivers in struct")
            for sliver in slivers:
                if not (isinstance(sliver, dict) and \
                            (sliver.has_key('geni_sliver_urn') or sliver.has_key('geni_urn'))):
                    continue
                if sliver.has_key('geni_sliver_urn'):
                    sliver_urn = sliver['geni_sliver_urn']
                else:
                    sliver_urn = sliver['geni_urn']
                exp = expiration
                if sliver.has_key('geni_expires'):
                    exp = sliver['geni_expires']
                msg = msg + str(self._record_one_new_sliver(sliver_urn,
                                                        slice_urn, agg_urn, creator_urn, exp))
            # End of loop over slivers
        else:
            self.logger.debug("Got no manifest AND no slivers to record")
        # End of if/else block for API Version
        return msg

    # use the database to convert an aggregate url to the corresponding urn
    # FIXME: other CHs do similar things - implement this elsewhere
    def lookup_agg_urn_by_url(self, agg_url):
        if agg_url is None or agg_url.strip() == "":
            self.logger.warn("Empty Aggregate URL to look up")
            return None

        # FIXME: This relies on an exact match. See handler_utils for
        # tricks we do locally that perhaps we should do here.

        options = {'filter': ['SERVICE_URN'],
                   'match': {'SERVICE_URL': agg_url}}
        if not self.speakV2:
            res, mess = _do_ssl(self, None, "Lookup aggregate urn at %s for '%s'" % (self.fwtype, agg_url),
                                self.ch.lookup_aggregates, options)
        else:
            options['match']['SERVICE_TYPE'] = 'AGGREGATE_MANAGER'
            res, mess = _do_ssl(self, None, "Lookup aggregate urn at %s for '%s'" % (self.fwtype, agg_url),
                                self.ch.lookup, "SERVICE", [], options)
        logr = self._log_results((res, mess), "Convert aggregate url '%s' to urn using %s DB" % (agg_url, self.fwtype))
        if logr == True:
            self.logger.debug("Got CH AM listing '%s' for URL '%s'", res['value'], agg_url)
            if len(res['value']) == 0:
                return None
            else:
                return res['value'][0]['SERVICE_URN']
        else:
            return None

    # given the slice urn and aggregate urn, find the sliver urns from the db
    # Return an empty list if none found
    def list_sliverinfo_urns(self, slice_urn, aggregate_urn):
        creds = []
        slice_urn = self.slice_name_to_urn(slice_urn)
        if not is_valid_urn(slice_urn):
            self.logger.warn("No slice to lookup slivers")
            return []
        if not is_valid_urn(aggregate_urn):
            self.logger.warn("Invalid aggregate URN '%s' for querying slivers", aggregate_urn)
            return []
        if self.needcred:
            # FIXME: At PG should this be user or slice cred?
#            uc, msg = self.get_user_cred(True)
#            if uc is not None:
#                creds.append(uc)
            sc = self.get_slice_cred_struct(slice_urn)
            if sc is not None:
                creds.append(sc)

        slice_expiration = self.get_slice_expiration(slice_urn)

        expired = False
        expmess = ""
        if slice_expiration is not None:
            exp = naiveUTC(slice_expiration)
            if exp < naiveUTC(datetime.datetime.utcnow()):
                expired = True
                expmess = " (EXPIRED at %s UTC)" % exp
        else:
            # Usually means the slice doesn't exist or you don't have
            # rights on it
            return []

        # FIXME: Query the sliver expiration and skip expired slivers?
        options = {'filter': [],
                   'match': {'SLIVER_INFO_SLICE_URN': slice_urn,
                             "SLIVER_INFO_AGGREGATE_URN": aggregate_urn}}
        # FIXME: Limit to SLICE_EXPIRED: False?
        creds, options = self._add_credentials_and_speaksfor(creds, options)
        if not self.speakV2:
            res, mess = _do_ssl(self, None, "Lookup slivers in %s%s at %s" % (slice_urn, expmess,aggregate_urn),
                                self.sa().lookup_sliver_info, creds, options)
        else:
            res, mess = _do_ssl(self, None, "Lookup slivers in %s%s at %s" % (slice_urn, expmess,aggregate_urn),
                                self.sa().lookup, "SLIVER_INFO", creds, options)

        logr = self._log_results((res, mess), 'Lookup slivers in %s%s at %s' % (slice_urn, expmess,aggregate_urn))
        if logr == True:
            self.logger.debug("Slice %s AM %s found slivers: %s", slice_urn, aggregate_urn, res['value'])
            return res['value'].keys()
        else:
            return []

    # update the expiration time on a sliver
    # If we get an argument error indicating the sliver was not yet recorded, try
    # to record it
    def update_sliver_info(self, agg_urn, slice_urn, sliver_urn, expiration):
        if expiration is None:
            self.logger.warn("Empty new expiration to record for sliver '%s'", sliver_urn)
            return None
        if sliver_urn is None or sliver_urn.strip() == "":
            self.logger.warn("Empty sliver_urn to update record of sliver expiration")
            return

        # Just make sure this is a reasonable URN of type sliver,
        # without validating the name portion - since we really don't
        # care so much what names the AM uses
        if not self._weakSliverValidCheck(sliver_urn):
            if is_valid_urn(agg_urn) and sliver_urn.startswith(slice_urn) and ('al2s' in agg_urn or 'foam' in agg_urn):
                # Work around a FOAM/AL2S bug producing bad sliver URNs
                # See http://groups.geni.net/geni/ticket/1294
                self.logger.debug("Malformed sliver URN '%s'. Assuming this is OK anyhow at this FOAM based am: %s. See http://groups.geni.net/geni/ticket/1294", sliver_urn, agg_urn)
            else:
                self.logger.warn("Cannot update sliver expiration record: Invalid sliver urn '%s'", sliver_urn)
                return
        if not is_valid_urn(agg_urn):
            agg_urn = self._getAggFromSliverURN(sliver_urn)

        slice_urn = self.slice_name_to_urn(slice_urn)

        creds = []
        if self.needcred:
            # FIXME: At PG should this be user or slice cred?
#            uc, msg = self.get_user_cred(True)
#            if uc is not None:
#                creds.append(uc)
            sc = self.get_slice_cred_struct(slice_urn)
            if sc is not None:
                creds.append(sc)

        # Note that if no TZ is specified, UTC is assumed
        fields = {'SLIVER_INFO_EXPIRATION': str(expiration)}

        options = {'fields' : fields}
        creds, options = self._add_credentials_and_speaksfor(creds, options)
        self.logger.debug("Passing options: %s", options)
        if not self.speakV2:
            res = _do_ssl(self, None, "Recording sliver '%s' updated expiration" % sliver_urn, \
                              self.sa().update_sliver_info, sliver_urn, creds, options)
        else:
            res = _do_ssl(self, None, "Recording sliver '%s' updated expiration" % sliver_urn, \
                              self.sa().update, "SLIVER_INFO", sliver_urn, creds, options)
        msg = self._log_results(res, "Update sliver '%s' expiration" % sliver_urn)
        if "Register the sliver" in str(msg) and "ARGUMENT_ERROR" in str(msg) and is_valid_urn(slice_urn) and is_valid_urn(agg_urn):
            # SA didn't know about this sliver

            msg = str(msg)
            nm = self._record_one_new_sliver(sliver_urn,
                                               slice_urn, agg_urn, self.user_urn, expiration)
            if nm != True:
                msg += str(msg)
            else:
                msg = "Recorded sliver '%s' with new expiration" % sliver_urn
        return msg

# Note: Valid 'match' fields for lookup_sliver_info are the same as is
# passed in create_sliver_info. However, you can only look up by
# sliver/slice if you are a member of the relevant slice, and only by
# creator for yourself. Not by the times. These are also the columns returned
# SLIVER_INFO_URN
# SLIVER_INFO_SLICE_URN
# SLIVER_INFO_AGGREGATE_URN
# SLIVER_INFO_CREATOR_URN
# SLIVER_INFO_EXPIRATION
# SLIVER_INFO_CREATION

    # delete the sliver from the chapi database
    def delete_sliver_info(self, sliver_urn):
        creds = []
        if self.needcred:
            # FIXME: At PG should this be user or slice cred?
            # If slice, then must refactor to get slice urn
            uc, msg = self.get_user_cred(True)
            if uc is not None:
                creds.append(uc)
#            sc = self.get_slice_cred_struct(slice_urn)
#            if sc is not None:
#                creds.append(sc)
        options = {}
        if sliver_urn is None or sliver_urn.strip() == "":
            self.logger.debug("Empty sliver_urn to record deletion but continuing")
# Delete it anyway
#            return
        if not self._weakSliverValidCheck(sliver_urn):
            self.logger.debug("Invalid sliver urn but continuing: %s", sliver_urn)
# Delete it anyway
#            return
        creds, options = self._add_credentials_and_speaksfor(creds, options)
        if not self.speakV2:
            res = _do_ssl(self, None, "Recording sliver '%s' deleted" % sliver_urn,
                          self.sa().delete_sliver_info, sliver_urn, creds, options)
        else:
            res = _do_ssl(self, None, "Recording sliver '%s' deleted" % sliver_urn,
                          self.sa().delete, "SLIVER_INFO", sliver_urn, creds, options)
        return self._log_results(res, "Record sliver '%s' deleted" % sliver_urn)

    # Find all slivers the SA lists for the given slice
    # Return a struct by AM URN containing a struct: sliver_urn = sliver info struct
    # Compare with list_sliverinfo_urns which only returns the sliver URNs
    def list_sliver_infos_for_slice(self, slice_urn):
        slivers_by_agg = {}
        slice_urn = self.slice_name_to_urn(slice_urn)
        creds = []
        if self.needcred:
            # FIXME: At PG should this be user or slice cred?
#            uc, msg = self.get_user_cred(True)
#            if uc is not None:
#                creds.append(uc)
            sc = self.get_slice_cred_struct(slice_urn)
            if sc is not None:
                creds.append(sc)

        slice_expiration = self.get_slice_expiration(slice_urn)

        expired = False
        expmess = ""
        if slice_expiration is not None:
            exp = naiveUTC(slice_expiration)
            if exp < naiveUTC(datetime.datetime.utcnow()):
                expired = True
                expmess = " (EXPIRED at %s UTC)" % exp
        else:
            # User not authorized or slice doesn't exist
            return slivers_by_agg

        options = {"match" : {"SLIVER_INFO_SLICE_URN" : slice_urn}}

        # FIXME: Limit to SLICE_EXPIRED: False?
        creds, options = self._add_credentials_and_speaksfor(creds, options)
        if not self.speakV2:
            res, mess = _do_ssl(self, None, "Find slivers for slice %s%s" % (slice_urn,expmess), \
                                    self.sa().lookup_sliver_info, creds, options)
        else:
            res, mess = _do_ssl(self, None, "Find slivers for slice %s%s" % (slice_urn,expmess), \
                                    self.sa().lookup, "SLIVER_INFO", creds, options)

        logr = self._log_results((res, mess), "Find slivers for slice %s%s" % (slice_urn,expmess))
 
        if logr == True:
            for sliver_urn, sliver_info in res['value'].items():
                self.logger.debug("Slice '%s' found sliver '%s': %s", slice_urn, sliver_urn, sliver_info)
                # FIXME: If the sliver seems to have expired, skip it?
                agg_urn = sliver_info['SLIVER_INFO_AGGREGATE_URN']
                if agg_urn not in slivers_by_agg:
                    slivers_by_agg[agg_urn] = {}
                slivers_by_agg[agg_urn][sliver_urn] = sliver_info

        return slivers_by_agg

###############
## GD Additions
###############

    def user_lookup_by_urn (self, urn):
        creds = []
        if self.needcred:
            uc, msg = self.get_user_cred(True)
            if uc is not None:
                creds.append(uc)

        options = {'match':{'MEMBER_URN':urn},'filter':['MEMBER_EMAIL','MEMBER_FIRSTNAME','MEMBER_LASTNAME','MEMBER_UID','MEMBER_URN','MEMBER_USERNAME']}
        creds, options = self._add_credentials_and_speaksfor(creds, options)
        (data, fail) = _do_ssl(self, None, ("Lookup user at %s" % (self.ma_url())),\
                                     self.ma().lookup,"MEMBER", creds, options)

        if data["code"] != 0:
            output = data["output"]
            msg = "Error looking up user"
            if output is not None and output.strip() != "":
                msg = msg + ". %s" % output
            self.logger.error(msg)
            return None

        return (data["value"], data["output"])

    def slice_lookup_by_uuid(self, uid):
        scred = []
        # PG implementation needs a user cred
        if self.needcred:
            uc, msg = self.get_user_cred(True)
            if uc is not None:
                scred.append(uc)
        options = {'match': 
                   {'SLICE_UID': uid,
                    'SLICE_EXPIRED': 'f',
                    }}
        options['filter'] = ['SLICE_URN','SLICE_UID','SLICE_EXPIRATION']
        self.logger.debug("Submitting lookup_slices with options: %s", options)
        scred, options = self._add_credentials_and_speaksfor(scred, options)
        res = None
        if not self.speakV2:
            (res, message) = _do_ssl(self, None, ("Lookup slice_uid %s on %s %s" % (uid, self.fwtype,self.sa_url())),\
                                         self.sa().lookup_slices, scred, options)
        else:
            (res, message) = _do_ssl(self, None, ("Lookup slice_uid %s on %s %s" % (uid, self.fwtype,self.sa_url())),\
                                         self.sa().lookup, "SLICE", scred, options)

        msg = None
        urn = None
        if res is not None:
            if res['code'] == 0:
                d = res['value']
                if d is not None:
                        return d
                else:
                    self.logger.error("Malformed response from lookup slice by uuid : %s", d)
            else:
                msg = "Server Error looking up slice %s" % uid
                if res['code'] == 3 and "Unknown slice urns" in res['output']:
                    msg += " - unknown slice"
                else:
                    msg += ". Code %d: %s" % ( res['code'], res['output'])
                    if message and message.strip() != "":
                        msg = msg + " (%s)" % message
                if res.has_key('protogeni_error_url'):
                    msg += " (Log url - look here for details on any failures: %s)" % res['protogeni_error_url']
                self.logger.error(msg)
        else:
            msg = "Server Error looking up slice_uid %s" % uid
            if message is not None and message.strip() != "":
                msg = msg + ". %s" % message
            self.logger.error(msg)

        return None

    def slice_lookup_by_urn(self, urn):
        scred = []
        # PG implementation needs a user cred
        if self.needcred:
            uc, msg = self.get_user_cred(True)
            if uc is not None:
                scred.append(uc)
        options = {'match': 
                   {'SLICE_URN': urn,
                    'SLICE_EXPIRED': 'f',
                    }}
        options['filter'] = ['SLICE_URN','SLICE_UID','SLICE_EXPIRATION']
        self.logger.debug("Submitting lookup_slices by urn with options: %s", options)
        scred, options = self._add_credentials_and_speaksfor(scred, options)
        res = None
        if not self.speakV2:
            (res, message) = _do_ssl(self, None, ("Lookup slice_urn %s on %s %s" % (urn, self.fwtype,self.sa_url())),\
                                         self.sa().lookup_slices, scred, options)
        else:
            (res, message) = _do_ssl(self, None, ("Lookup slice_urn %s on %s %s" % (urn, self.fwtype,self.sa_url())),\
                                         self.sa().lookup, "SLICE", scred, options)

        msg = None
        if res is not None:
            if res['code'] == 0:
                d = res['value']
                if d is not None:
                    if (len(d.keys()) == 1):
                        return d
                    else:
                        self.logger.error("Slice_urn %s was not found - has it already expired?" % urn)
                else:
                    self.logger.error("Malformed response from lookup slice by urn : %s", d)
            else:
                msg = "Server Error looking up slice %s" % urn
                if res['code'] == 3 and "Unknown slice urns" in res['output']:
                    msg += " - unknown slice"
                else:
                    msg += ". Code %d: %s" % ( res['code'], res['output'])
                    if message and message.strip() != "":
                        msg = msg + " (%s)" % message
                if res.has_key('protogeni_error_url'):
                    msg += " (Log url - look here for details on any failures: %s)" % res['protogeni_error_url']
                self.logger.error(msg)
        else:
            msg = "Server Error looking up slice_urn %s" % urn
            if message is not None and message.strip() != "":
                msg = msg + ". %s" % message
            self.logger.error(msg)

        return None

    def list_my_slices_with_role(self, user):
        '''List slices owned by the user (name or URN) provided, returning a list of slice URNs.'''

        scred = []
        # PG implementation needs a user cred
        if self.needcred:
            uc, msg = self.get_user_cred(True)
            if uc is not None:
                scred.append(uc)
            else:
                self.logger.debug("Failed to get user credential: %s", msg)

        userurn = self.member_name_to_urn(user)

        options = {'match': 
                   {'SLICE_EXPIRED': 'f', # Seems to be ignored
                        }}
        scred, options = self._add_credentials_and_speaksfor(scred, options)

        if not self.speakV2:
            (res, message) = _do_ssl(self, None, ("List Slices for %s at %s %s" % (user, self.fwtype, self.sa_url())), 
                                     self.sa().lookup_slices_for_member, userurn, scred, options)
        else:
            (res, message) = _do_ssl(self, None, ("List Slices for %s at %s %s" % (user, self.fwtype, self.sa_url())), 
                                     self.sa().lookup_for_member, "SLICE", userurn, scred, options)


        slices = None
        if res is not None:
            if res['code'] == 0:
                slices = res['value']
            else:
                msg = "Failed to list slices for %s" % user
                msg += ". Server said: %s" % res['output']
                if res.has_key('protogeni_error_url'):
                    msg += " (Log url - look here for details on any failures: %s)" % res['protogeni_error_url']
                raise OmniError(msg)
        else:
            msg = "Failed to list slices for %s" % user
            if message is not None and message.strip() != "":
                msg += ": %s" % message
            raise OmniError(msg)

        # Return is a struct with the URN
        #slicenames = list()
        slicenames = {}
        if slices and isinstance(slices, list):
            for tup in slices:
                slice = tup['SLICE_URN']
                slicelower = string.lower(slice)
                if not string.find(slicelower, "+slice+"):
                    self.logger.debug("Skipping non slice URN '%s'", slice)
                    continue
                slicename = slice
                # Returning this key is non-standard..
                if tup.has_key('EXPIRED'):
                    exp = tup['EXPIRED']
                    if exp == True:
                        self.logger.debug("Skipping expired slice %s", slice)
                        continue
                if tup.has_key('SLICE_ROLE'):
                    role = string.lower(tup['SLICE_ROLE'])
                else:
                   role = ''
                slicenames[slicename] = role
        return slicenames




    def modify_slice_membership(self, slice_urn, memberships_json_file):
        import json
        memberships = {}

        try:
                memberships = json.load(open(memberships_json_file,'r'))
                if(len(memberships) == 0):
                        mess = 'Nothing to do for any user'
                        success = False
                        return (success, mess)
        except ValueError:
                mess = 'Error decoding Memebership JSON'
                success = False
                return (success, mess)
        except Exception:
                raise
                mess = 'Some Error reading Memebership JSON file'
                success = False
                return (success, mess)

        member_urns = memberships.keys()
        members_to_add =[]
        members_to_remove = []
        members_to_change = []
        for member_urn in member_urns:
                actions = memberships[member_urn]
                if(actions.startswith('Add as ')):
                        role = (actions[7:]).upper()
                        members_to_add.append({'SLICE_MEMBER': member_urn,'SLICE_ROLE':role})
                if(actions.startswith('Change to ')):
                        role = (actions[10:]).upper()
                        members_to_change.append({'SLICE_MEMBER': member_urn,'SLICE_ROLE':role})
                if(actions.startswith('Remove from Slice')):
                        members_to_remove.append(member_urn)
        slice_urn = self.slice_name_to_urn(slice_urn)
        creds = []
        if self.needcred:
            # FIXME: Neither user or slice cred work at PG. Which is correct?
            sc = self.get_slice_cred_struct(slice_urn)
            if sc is not None:
                creds.append(sc)
        options = {}
        if(len(members_to_add) > 0):
                options['members_to_add'] = members_to_add
        if(len(members_to_remove) > 0):
                options['members_to_remove'] = members_to_remove
        if(len(members_to_change) > 0):
                options['members_to_change'] = members_to_change
        creds, options = self._add_credentials_and_speaksfor(creds, options)
        res, mess = _do_ssl(self, None, "Modifying members %s to %s slice %s at %s" %  (str(member_urns), self.fwtype, slice_urn, self.sa_url()),
                            self.sa().modify_slice_membership,
                            slice_urn, creds, options)

        # FIXME: do own result checking to detect DUPLICATE

        logr = self._log_results((res, mess), 'Modify members %s to %s slice %s' % (str(member_urns), self.fwtype, slice_urn))
        if logr == True:
            success = logr
        else:
            success = False
            mess = logr
        return (success, mess)



