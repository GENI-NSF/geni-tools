#----------------------------------------------------------------------
# Copyright (c) 2011-2014 Raytheon BBN Technologies
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

from omnilib.frameworks.framework_base import Framework_Base
from omnilib.util.dates import naiveUTC
from omnilib.util.dossl import _do_ssl
import omnilib.util.credparsing as credutils

from geni.util.urn_util import is_valid_urn, URN, string_to_urn_format,\
    nameFromURN, is_valid_urn_bytype, string_to_urn_format
import sfa.trust.gid as gid

import datetime
import dateutil
import os
import string
import sys
from pprint import pprint

class Framework(Framework_Base):
    def __init__(self, config, opts):
        Framework_Base.__init__(self,config)
        config['cert'] = os.path.expanduser(config['cert'])
        self.fwtype = "GENI Clearinghouse"
        self.opts = opts
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

        # FIXME: We should configure this framework type with the URL of the CH, and use
        # that to look up the MA and SA URLs
        self.ch_url = config['ch'] + ':8444/CH'
        self.ch = self.make_client(self.ch_url, self.key, self.cert,
                                   verbose=config['verbose'])
        self.ma_url = config['ch'] + '/MA'
        self.ma = self.make_client(self.ma_url, self.key, self.cert,
                                   verbose=config['verbose'])
        self.sa_url = config['ch'] + '/SA'
        self.sa = self.make_client(self.sa_url, self.key, self.cert,
                                   verbose=config['verbose'])

        if not config.has_key('useProjects'):
            config['useProjects'] = True
        self.useProjects = config['useProjects']

        self.cert = config['cert']
        try:
            self.cert_string = file(self.cert, 'r').read()
        except Exception, e:
            sys.exit('CHAPI Framework failed to read cert file %s: %s' % (self.cert, e))

        try:
            self.cert_gid = gid.GID(filename=self.cert)
        except Exception, e:
            sys.exit('CHAPI Framework failed to parse cert read from %s: %s' % (self.cert, e))

        self.user_urn = self.cert_gid.get_urn()
        if self.opts.speaksfor: self.user_urn = self.opts.speaksfor
        self.user_cred = self.init_user_cred( opts )
        self.logger = config['logger']

    # Add new speaks for options and credentials based on provided opts 
    def _add_credentials_and_speaksfor(self, credentials, options):
        # FIXME: Tune log messages
        self.logger.debug("add_c_n_spkfor start with self.opts.speaksfor = %s" % self.opts.speaksfor)
        self.logger.debug("add_c_n_spkfor start with self.opts.cred = %s" % self.opts.cred)
        if credentials is None:
            credentials = []
        if options is None:
            options = {}
        new_credentials = credentials
        new_options = options
        if self.opts.speaksfor:
            options['speaking_for'] = self.opts.speaksfor # At AMs this is geni_speaking_for
        if self.opts.cred:
            for cred_filename in self.opts.cred:
                try:
                    cred_contents = open(cred_filename).read()
                    # FIXME: Infer cred type and wrap only as necessary
                    new_cred = {'geni_type' : 'geni_abac',
                                'geni_value' : cred_contents,
                                'geni_version' : '1'}
                    new_credentials.append(new_cred)
                except Exception, e:
                    self.logger.warn("Failed to read credential from %s: %s", cred_filename, e)
        self.logger.debug("add_c_n_spkfor new_creds = %s new_options = %s" % (new_credentials, new_options))
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
                              self.fwtype, self.ma_url)
            (res, message) = _do_ssl(self, None, ("Get user credential from %s %s" % (self.fwtype, self.ch_url)),
                                     self.ma.get_credentials,
                                     self.user_urn,
                                     creds,
                                     options)
            if res is not None:
                if res['code'] == 0:
                    if res['value'] is None:
                        self.logger.error("No SFA user credential returned!")
                        self.logger.debug("Got %s", res['value'])
                    else:
                        self.user_cred_struct = self._select_sfa_cred(res['value'], True)
                        if self.user_cred_struct:
                            self.user_cred = self.user_cred_struct['geni_value']
                    if self.user_cred is None:
                        self.logger.error("No SFA user credential returned!")
                        self.logger.debug("Got %s", res['value'])
                else:
                    msg = res['output']
                    if msg is None or msg.strip() == "":
                        msg = "Error %d" % res['code']
                    if message is not None and message.strip() != "":
                        msg = msg + ". %s" % message
                    self.logger.error(msg)
            else:
                msg = message

        if struct==True:
            return self.user_cred_struct, msg
        else:
            return self.user_cred, msg

    def get_slice_cred(self, slice_urn, struct=False):
        scred = []
        options = {'match': 
                   {'SLICE_URN': slice_urn,
                    'SLICE_EXPIRED': 'f',
                    }}

        scred, options = self._add_credentials_and_speaksfor(scred, options)

        (res, message) = _do_ssl(self, None, ("Get credentials for slice %s on %s SA %s" % (slice_urn,
                                                                                            self.fwtype, self.sa_url)),
                                 self.sa.get_credentials, slice_urn, scred, 
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
                    if cred is None:
                        self.logger.debug("Malformed list of creds: Got %s", d)
                        raise Exception("No slice credential returned for slice %s" % slice_urn)
                else:
                    self.logger.debug("Malformed slice cred return. Got %s", res)
                    raise Exception("Malformed return getting slice credential")
            else:
                raise Exception("Server Error getting slice %s credential: %d: %s (%s)" % (slice_urn, res['code'], res['output'], message))
        else:
            msg = "Server Error getting slice %s credential" % slice_urn
            if message is not None and message.strip() != "":
                msg = msg + ". %s" % message
            raise Exception(msg)
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

        options = {'match': {'KEY_MEMBER': fetch_urn}, 'filter': ['KEY_PUBLIC']}

        scred, options = self._add_credentials_and_speaksfor(scred, options)

        self.logger.debug("Getting %s SSH keys from %s MA %s",
                          username, self.fwtype, self.ma_url)
        (res, message) = _do_ssl(self, None, ("Get %s public SSH keys from %s %s" % (username, self.fwtype, self.ch_url)),
                                 self.ma.lookup_keys,
                                 scred,
                                 options)

        keys = []
        msg = None
        if res is not None:
            if res['code'] == 0:
                if res.has_key('value') and res['value'] is not None:
                    d = res['value']
                    for uid, key_tups in d.items():
                        for key_tup in key_tups:
                            if 'KEY_PUBLIC' in key_tup:
                                keys.append(key_tup['KEY_PUBLIC'])
                            else:
                                self.logger.debug("No public key? %s", key_tup)
                else:
                    msg = "Malformed server return getting SSH keys"
                    if message is not None and message.strip() != "":
                        msg = msg + ". %s" % message
                    self.logger.error(msg)
                    self.logger.debug("Got %s", res)
            else:
                msg = "Server Error getting SSH keys: %d: %s" % (res['code'], res['output'])
                if message is not None and message.strip() != "":
                    msg = msg + " (%s)" % message
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
            if cred.has_key('geni_type') and cred['geni_type'] == 'geni_sfa' and cred.has_key('geni_value'):
                if struct:
                    return cred
                return cred['geni_value']

    def create_slice(self, urn):
        scred = []

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
            self.logger.debug("From slice URN extracted project %s", project)

        if project is None:
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
                raise Exception("Invalid configuration: no authority defined")
            auth = self.config['authority'].strip()
            self.logger.debug("From config got authority %s", auth)

        project_urn = None
        if project is not None:
            project_urn = URN(authority = auth,
                              type = 'project',
                              name = project).urn_string()
            self.logger.debug("Built project_urn %s", project_urn)

        options = {'fields': 
                   {'SLICE_NAME': slice_name,
                    }}
        if project_urn is not None:
            options['fields']['SLICE_PROJECT_URN'] = project_urn

        self.logger.debug("Submitting with options %s", options)

        scred, options = self._add_credentials_and_speaksfor(scred, options)

        (res, message) = _do_ssl(self, None, ("Create slice %s on %s %s" % (slice_name, self.fwtype, self.ch_url)),\
                                     self.sa.create_slice, scred, options)
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
                    # Here we preserve current functionality -
                    # continue and pretend we created the slice. We
                    # could of course instead return an error
                    #msg = res['output']
                else:
                    # This includes if the slice already exists.
                    msg = "Error from server creating slice. Code %d: %s" % ( res['code'], res['output'])
                    if message and message.strip() != "":
                        msg = msg + " (%s)" % message
                    self.logger.error(msg)
                    return None
        else:
            msg = "Error creating slice"
            if message is not None and message.strip() != "":
                msg = msg + ". %s" % message
            self.logger.error(msg)
            return None

        options['match'] = {'SLICE_URN': slice_urn,
                            'SLICE_EXPIRED': 'f',
                            }
        scred, options = self._add_credentials_and_speaksfor(scred, options)

        (res, message) = _do_ssl(self, None, ("Get credentials for slice %s on %s %s" % (slice_name,
                                                                                         self.fwtype, self.ch_url)),
                                 self.sa.get_credentials, slice_urn, scred, 
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
                self.logger.error("Error from server getting credential for new slice %s: %d: %s (%s)", slice_name, res['code'], res['output'], message)
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
                self.logger.debug("From slice URN extracted project %s", project)
            slice_urn = urn
        else:
            slice_name = urn

        if project is None:
            if self.opts.project:
                # use the command line option --project
                project = self.opts.project
            elif self.config.has_key('default_project'):
                # otherwise, default to 'default_project' in 'omni_config'
                project = self.config['default_project']
            else:
                return "%s does not support deleting slices. (And no project was specified)" % self.fwtype

        if auth is None:
            if not self.config.has_key('authority'):
                return "%s does not support deleting slices. (And invalid configuration: no authority defined to construct slice urn)" % self.fwtype
            auth = self.config['authority'].strip()
            self.logger.debug("From config got authority %s", auth)

        if slice_urn is None:
            slice_urn = URN(authority=auth + ":" + project, type='slice', name=slice_name).urn_string()
            self.logger.debug("Constructed urn %s", slice_urn)

        if not is_valid_urn_bytype(slice_urn, 'slice', self.logger):
            return "%s does not support deleting slices. (And slice urn %s invalid)" % (self.fwtype, slice_urn)

        options = {'match': 
                   {'SLICE_URN': slice_urn,
                    'SLICE_EXPIRED': 'f',
                    }}
        options['filter'] = ['SLICE_URN', 'SLICE_EXPIRATION']
        self.logger.debug("Submitting with options %s", options)

        scred, options = self._add_credentials_and_speaksfor(scred, options)

        (res, message) = _do_ssl(self, None, ("Lookup slice %s on %s %s" % (slice_name, self.fwtype, self.ch_url)),\
                                     self.sa.lookup_slices, scred, options)
        slice_expiration = None
        msg = None
        if res is not None:
            if res['code'] == 0:
                d = res['value']
                if d is not None:
                    if d.has_key(slice_urn) and \
                                     d[slice_urn].has_key('SLICE_EXPIRATION'):
                        slice_expiration = d[slice_urn]['SLICE_EXPIRATION']
                        exp = dateutil.parser.parse(slice_expiration)
                        if exp < dattime.datetime.utcnow():
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
        else:
            msg = "%s does not support deleting slices. (And server error looking up slice %s)" % (self.fwtype, slice_name)
            if message is not None and message.strip() != "":
                msg = msg + ". %s" % message

        if msg is None:
            msg = "%s does not support deleting slices - delete your resources and let slice %s expire instead" % (self.fwtype,
                                                                                                                   slice_name)
            if slice_expiration is not None:
                msg = msg + " at %s UTC." % slice_expiration
            else:
                msg = msg + "."
        return msg

    def list_aggregates(self):
        # TODO: list of field names from getVersion - should we get all or assume we have URN and URL
        options = {'filter':['SERVICE_URN', 'SERVICE_URL']}
        (res, message) = _do_ssl(self, None, ("List Aggregates at %s %s" % (self.fwtype, self.ch_url)), 
                                 self.ch.lookup_aggregates,
                                 options
                                 )
        if message and message.strip() != "":
            self.logger.warn(message)
        aggs = dict()
        if res is not None:
            if res['value'] is not None and res['code'] == 0:
                for d in res['value']:
                    aggs[d['SERVICE_URN']] = d['SERVICE_URL']
            else:
                self.logger.warn("Server Error listing aggregates %d: %s", res['code'], res['output'])
        else:
            self.logger.warn("Server Error listing aggregates - no results")

        return aggs

    def list_my_slices(self, user):
        '''List slices owned by the user (name or URN) provided, returning a list of slice URNs.'''

        scred = []

        userurn = self.member_name_to_urn(user)

        options = {'match': 
                   {'SLICE_EXPIRED': 'f', # Seems to be ignored
                        }}
        scred, options = self._add_credentials_and_speaksfor(scred, options)

        (res, message) = _do_ssl(self, None, ("List Slices for %s at %s %s" % (user, self.fwtype, self.ch_url)), 
                                    self.sa.lookup_slices_for_member, userurn, scred, options)

        slices = None
        if res is not None:
            if res['code'] == 0:
                slices = res['value']
            else:
                msg = "Failed to list slices for %s" % user
                msg += ". Server said: %s" % res['output']
                raise Exception(msg)
        else:
            msg = "Failed to list slices for %s" % user
            if message is not None and message.strip() != "":
                msg += ": %s" % message
            raise Exception(msg)

        # Return is a struct with the URN
        slicenames = list()
        if slices and isinstance(slices, list):
            for tup in slices:
                slice = tup['SLICE_URN']
                slicelower = string.lower(slice)
                if not string.find(slicelower, "+slice+"):
                    self.logger.debug("Skipping non slice URN %s", slice)
                    continue
                slicename = slice
                exp = tup['EXPIRED']
                if exp == True:
                    self.logger.debug("Skipping expired slice %s", slice)
                    continue
                slicenames.append(slicename)
        return slicenames

    def slice_name_to_urn(self, name):
        """Convert a slice name to a slice urn."""

        if name is None or name.strip() == '':
            raise Exception('Empty slice name')

        project = None
        auth = None

        if is_valid_urn(name):
            urn = URN(None, None, None, name)
            if not urn.getType() == "slice":
                raise Exception("Invalid Slice name: got a non Slice URN %s" % name)
            if not is_valid_urn_bytype(name, 'slice', self.logger):
                raise Exception("Invalid slice name %s" % name)

            urn_fmt_auth = string_to_urn_format(urn.getAuthority())

            # if config has an authority, make sure it matches
            if self.config.has_key('authority'):
                auth = self.config['authority']
                if not urn_fmt_auth.startswith(auth):
                    self.logger.warn("CAREFUL: slice' authority (%s) doesn't match current configured authority (%s)" % (urn_fmt_auth, auth))
                    self.logger.info("This may be OK though if you are using delegated slice credentials...")
#                    raise Exception("Invalid slice name: slice' authority (%s) doesn't match current configured authority (%s)" % (urn_fmt_auth, auth))

            if self.useProjects:
                # Make sure the auth has a project
                s_auths = urn_fmt_auth.split(':')
                auth = s_auths[0]
                if len(s_auths) > 1 and s_auths[-1].strip() != "":
                    project = s_auths[-1]
                    # FIXME: Validate the project
                    self.logger.debug("From slice URN extracted project %s", project)
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
                        raise Exception("Invalid slice URN missing project. Specify a project with --project or a default_project in your omni_config")

                    # Fall through so we can produce a new URN
                    name = urn.getName()
            else:
                # Valid slice URN (not using projects) - use it
                return name

        # No valid slice urn provided

        if not auth:
            if not self.config.has_key('authority'):
                raise Exception("Invalid configuration: no authority defined")
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
                    raise Exception("Project name required. Specify a project with --project or a default_project in your omni_config")
            auth = auth + ':' + project
        return URN(auth, "slice", name).urn_string()

    def member_name_to_urn(self, name):
        """Convert a member name to a member urn."""

        if name is None or name.strip() == '':
            raise Exception('Empty member name')

        if is_valid_urn(name):
            urn = URN(None, None, None, name)
            if not urn.getType() == "user":
                raise Exception("Invalid member name: got a non member URN %s", name)
            if not is_valid_urn_bytype(name, 'user', self.logger):
                raise Exception("Invalid user name %s" % name)
            # if config has an authority, make sure it matches
            if self.config.has_key('authority'):
                auth = self.config['authority']
                urn_fmt_auth = string_to_urn_format(urn.getAuthority())
                if urn_fmt_auth != auth:
                    self.logger.warn("CAREFUL: member's authority (%s) doesn't match current configured authority (%s)" % (urn_fmt_auth, auth))
            return name

        if not self.config.has_key('authority'):
            raise Exception("Invalid configuration: no authority defined")

        auth = self.config['authority']
        return URN(auth, "user", name).urn_string()

    def get_slice_expiration(self, urn):
        scred = []
        options = {'match': 
                   {'SLICE_URN': urn,
#                    'SLICE_EXPIRED': 'f',
                    }}
        options['filter'] = ['SLICE_URN', 'SLICE_EXPIRATION', 'SLICE_EXPIRED']
        self.logger.debug("Submitting with options %s", options)
        scred, options = self._add_credentials_and_speaksfor(scred, options)
        res = None
        (res, message) = _do_ssl(self, None, ("Lookup slice %s on %s %s" % (urn, self.fwtype,self.ch_url)),\
                                     self.sa.lookup_slices, scred, options)
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
                            exp = dateutil.parser.parse(slice_expiration)
                            if exp < datetime.datetime.utcnow():
#                                if not expired:
#                                    self.logger.debug('CH says it is not expired, but expiration is in past?')
                                self.logger.warn("Slice %s expired at %s", urn, slice_expiration)
#                            elif expired:
#                                self.logger.debug('CH says slice expired, but expiration %s is not in past?', slice_expiration)
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

        expiration = naiveUTC(expiration_dt).isoformat()
        self.logger.info('Requesting new slice expiration %r', expiration)
        options = {'fields':{'SLICE_EXPIRATION':expiration}}
        options['match'] = {'SLICE_URN': urn,
                            'SLICE_EXPIRED': 'f',
                            }
        res = None

        scred, options = self._add_credentials_and_speaksfor(scred, options)

        (res, message) = _do_ssl(self, None, ("Renew slice %s on %s %s until %s" % (urn, 
                                                                                    self.fwtype, self.ch_url, expiration_dt)), 
                                  self.sa.update_slice, urn, scred, options)

        b = False
        if res is not None:
            if res['code'] == 0:
                b = True
            else:
                message = res['output']
        if message is not None and message.strip() != "":
            self.logger.error(message)

        if b:
            # Fetch new expiration and make sure it is what was requested
            slice_expiration = self.get_slice_expiration(urn)

            if slice_expiration is not None:
                try:
                    sliceexp = naiveUTC(slice_expiration)
                    # If request is diff from sliceexp then log a warning
                    if sliceexp - naiveUTC(expiration_dt) > datetime.timedelta.resolution:
                        self.logger.warn("Renewed %s slice %s expiration %s different than request %s", self.fwtype, urn, sliceexp, expiration_dt)
                except:
                    pass
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
        # Do getversion at the CH (service registry), MA, and SA
        response = dict()
        versionstruct = dict()
        types = {'ch': ('Clearinghouse', self.ch_url, self.ch), 'ma':
                     ('Member Authority', self.ma_url, self.ma),
                 'sa': ('Slice Authority', self.sa_url, self.sa)}

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
        options = {'match': {'MEMBER_URN': urn}, 'filter': ['MEMBER_EMAIL']}
        res, mess = _do_ssl(self, None, "Looking up member email",
                            self.ma.lookup_identifying_member_info, creds, options)

        logr = self._log_results((res, mess), 'Lookup member email')
        if logr == True:
            if not res['value']:
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
        options = {'match': {'KEY_MEMBER': urn}, 'filter': ['KEY_PUBLIC']}

        creds, options = self._add_credentials_and_speaksfor(creds, options)

        res, mess = _do_ssl(self, None, "Looking up member %s SSH keys" % urn,
                            self.ma.lookup_keys, creds, options)

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

    # get the members (urn, email) and their ssh keys
    def get_members_of_slice(self, urn):
        # FIXME: This seems to list members even of an expired slice,
        # if that is the most recent slice by this name
        # Shouldn't the SA check this?

        creds = []
        slice_urn = self.slice_name_to_urn(urn)

        slice_expiration = self.get_slice_expiration(slice_urn)

        expired = False
        expmess = ""
        if slice_expiration is not None:
            exp = naiveUTC(slice_expiration)
            if exp < naiveUTC(datetime.datetime.utcnow()):
                expired = True
                expmess = " (EXPIRED at %s)" % slice_expiration

        options = {'match': 
                   {'SLICE_URN': slice_urn,
                    'SLICE_EXPIRED': 'f',  # FIXME: This gets ignored
                    }}

        creds, options = self._add_credentials_and_speaksfor(creds, options)
        res, mess = _do_ssl(self, None, "Looking up %s slice %s members" % (self.fwtype, slice_urn),
                            self.sa.lookup_slice_members, slice_urn, 
                            creds, options)
        members = []
        logr = self._log_results((res, mess), 'Get members for %s slice %s%s' % (self.fwtype, slice_urn, expmess))
        if logr == True:
            if res['value']:
                for member_vals in res['value']:
                    member_urn = member_vals['SLICE_MEMBER']
                    # FIXME: Return this too?
#                    member_role = member_vals['SLICE_ROLE']
                    member = {'URN': member_urn}
                    member['EMAIL'] = self._get_member_email(member_urn)
                    member['KEYS'] = self._get_member_keys(member_urn)
                    members.append(member)
        else:
            mess = logr
        if (not mess or mess.strip() == "") and expmess != "":
            mess = expmess
        return members, mess

    # add a new member to a slice
    def add_member_to_slice(self, slice_urn, member_name, role = 'MEMBER'):
        creds = []
        role2 = str(role).upper()
        if role2 == 'LEAD':
            raise Exception("Cannot add a lead to a slice. Try role 'ADMIN'")
        if role2 not in ['LEAD','ADMIN', 'MEMBER', 'AUDITOR']:
            raise Exception("Unknown role '%s'. Use ADMIN, MEMBER, or AUDITOR" % role)
        slice_urn = self.slice_name_to_urn(slice_urn)
        member_urn = self.member_name_to_urn(member_name)
        options = {'members_to_add': [{'SLICE_MEMBER': member_urn,
                                       'SLICE_ROLE': role}]}
#        options['match'] = {'SLICE_URN': slice_urn,
#                            'SLICE_EXPIRED': 'f',
#                            }
        creds, options = self._add_credentials_and_speaksfor(creds, options)
        res, mess = _do_ssl(self, None, "Adding member %s to %s slice %s" %  (member_urn, self.fwtype, slice_urn),
                            self.sa.modify_slice_membership,
                            slice_urn, creds, options)

        # FIXME: do own result checking to detect DUPLICATE

        logr = self._log_results((res, mess), 'Add member %s to %s slice %s' % (member_urn, self.fwtype, slice_urn))
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
                # In APIv3 if you renew while allocated then the slice
                # has not yet been recorded and will be unknown
                if self.opts.api_version > 2 and "ARGUMENT_ERROR (Unknown slice urns: [[None]])" in msg and ("Update sliver" in msg or "Record sliver" in msg):
                    msg = msg + " ... renewing or deleting a slice only allocated causes this. Expected & harmless."
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

    # Helper for actually recording a new sliver with the given expiration
    def _record_one_new_sliver(self, sliver_urn, slice_urn, agg_urn,
                               creator_urn, expiration):
        creds = []
        if sliver_urn is None or sliver_urn.strip() == "":
            self.logger.warn("Empty sliver_urn to record")
            return ""
        if not is_valid_urn_bytype(sliver_urn, 'sliver', self.logger):
            self.logger.warn("Invalid sliver urn %s", sliver_urn)
#                   return ""
        idx1 = sliver_urn.find('sliver+')
        auth = sliver_urn[0 : idx1]
        if not agg_urn:
            agg_urn = auth + 'authority+cm'
            if not is_valid_urn(agg_urn):
                self.logger.warn("Invalid aggregate URN %s for recording new sliver from sliver urn %s", agg_urn, sliver_urn)
                return ""
        else:
            if not agg_urn.startswith(auth):
                self.logger.debug("Skipping sliver %s that doesn't appear to come from the specified AM %s", sliver_urn,
                                  agg_urn)
                return ""
        fields = {"SLIVER_INFO_URN": sliver_urn,
                  "SLIVER_INFO_SLICE_URN": slice_urn,
                  "SLIVER_INFO_AGGREGATE_URN": agg_urn,
                  "SLIVER_INFO_CREATOR_URN": creator_urn}
        options = {'fields' : fields}
        if (expiration):
            # FIXME: put in naiveUTC? Format as ISO8601 or RFC3339?
            fields["SLIVER_INFO_EXPIRATION"] = str(expiration)
        self.logger.debug("Recording new slivers with options %s", options)
        creds, options = self._add_credentials_and_speaksfor(creds, options)
        res = _do_ssl(self, None, "Recording sliver %s creation at %s" % (sliver_urn, self.fwtype),
                      self.sa.create_sliver_info, creds, options)
        return self._log_results(res, "Record sliver %s creation at %s" % (sliver_urn, self.fwtype))

    # write new sliver_info to the database using chapi
    # Manifest is the XML when using APIv1&2 and none otherwise
    # expiration is the slice expiration
    # slivers is the return struct from APIv3+ or None
    # If am_urn is not provided, infer it from the url
    # If both are not provided, infer the AM from the sliver URNs
    def db_create_sliver_info(self, manifest, slice_urn,
                              aggregate_url, expiration, slivers, am_urn):
        if am_urn and is_valid_urn(am_urn):
            self.logger.debug("Using AM URN %s", am_urn)
            agg_urn = am_urn
        elif aggregate_url is None or aggregate_url.strip() == "":
            self.logger.warn("Empty aggregate for recording new slivers")
            # Just get the URN from the manifest?
            agg_urn = None
        else:
            # FIXME: Use agg nick cache
            agg_urn = self.db_agg_url_to_urn(aggregate_url)
            if agg_urn and not is_valid_urn(agg_urn):
                self.logger.warn("Invalid aggregate URN %s for recording new sliver from url %s", agg_urn, aggregate_url)
                return
        creator_urn = self.user_urn
        slice_urn = self.slice_name_to_urn(slice_urn)
        creds = []
        msg = ""

        if manifest and manifest.strip() != "" and (slivers is None or len(slivers) == 0):
            # APIv1/2: find slivers in manifest
            self.logger.debug("Finding new slivers to record in manfiest")
            # Loop through manifest finding all slivers to record
            while True:
                idx1 = manifest.find('sliver_id=') # Start of 'sliver_id='
                if idx1 < 0: break # No more slivers
                idx2 = manifest.find('"', idx1) + 1 # Start of URN
                if idx2 == 0:
                    # didn't find start of sliver id?
                    self.logger.warn("Malformed sliver_id in rspec? %s", manifest[:30])
                    manifest = manifest[9:]
                    continue
                idx3 = manifest.find('"', idx2) # End of URN
                if idx3 == 0:
                    # didn't find end of sliver id?
                    self.logger.warn("Malformed sliver_id in rspec? %s", manifest[idx2-15:idx2+80])
                    manifest = manifest[idx2:]
                    continue
                sliver_urn = manifest[idx2 : idx3]
                manifest = manifest[idx3+1:]
                msg = msg + str(self._record_one_new_sliver(sliver_urn,
                                                        slice_urn, agg_urn, creator_urn, expiration))
            # End of while loop over slivers in manifest
        elif slivers and len(slivers) > 0:
            # APIv3 style sliver to record
            self.logger.debug("Recording new slivers in struct")
            for sliver in slivers:
                if not (isinstance(sliver, dict) and \
                            sliver.has_key('geni_sliver_urn')):
                    continue
                sliver_urn = sliver['geni_sliver_urn']
                exp = None
                if sliver.has_key('geni_expires'):
                    exp = sliver['geni_expires']
                msg = msg + str(self._record_one_new_sliver(sliver_urn,
                                                        slice_urn, agg_urn, creator_urn, exp))
            # End of loop over slivers
        # End of if/else block for API Version
        return msg

    # use the database to convert an aggregate url to the corresponding urn
    def db_agg_url_to_urn(self, agg_url):
        if agg_url is None or agg_url.strip() == "":
            self.logger.warn("Empty Aggregate URL to look up")
            return None

        # FIXME: Use the agg nick cache first?

        options = {'filter': ['SERVICE_URN'],
                   'match': {'SERVICE_URL': agg_url}}
        res, mess = _do_ssl(self, None, "Lookup aggregate urn at %s" % (self.fwtype),
                            self.ch.lookup_aggregates, options)
        logr = self._log_results((res, mess), 'Convert aggregate url to urn using %s DB' % (self.fwtype))
        if logr == True:
            if len(res['value']) == 0:
                return None
            else:
                return res['value'][0]['SERVICE_URN']
        else:
            return None

    # given the slice urn and aggregate urn, find the sliver urns from the db
    def db_find_sliver_urns(self, slice_urn, aggregate_urn):
        creds = []
        slice_urn = self.slice_name_to_urn(slice_urn)
        if aggregate_urn is None or aggregate_urn.strip() == "":
            self.logger.warn("Empty aggregate for querying slivers")
            # FIXME: Extract from sliver_urn
            return []
        if not is_valid_urn(aggregate_urn):
            self.logger.warn("Invalid aggregate URN %s for querying slivers", aggregate_urn)
            return []

        slice_expiration = self.get_slice_expiration(slice_urn)

        expired = False
        expmess = ""
        if slice_expiration is not None:
            exp = naiveUTC(slice_expiration)
            if exp < naiveUTC(datetime.datetime.utcnow()):
                expired = True
                expmess = " (EXPIRED at %s)" % slice_expiration

        options = {'filter': [],
                   'match': {'SLIVER_INFO_SLICE_URN': slice_urn,
                             "SLIVER_INFO_AGGREGATE_URN": aggregate_urn}}
        # FIXME: Limit to SLICE_EXPIRED: 'f'?
        creds, options = self._add_credentials_and_speaksfor(creds, options)
        res, mess = _do_ssl(self, None, "Lookup slivers in %s%s at %s" % (slice_urn, expmess,aggregate_urn),
                            self.sa.lookup_sliver_info, creds, options)
        logr = self._log_results((res, mess), 'Lookup slivers in %s%s at %s' % (slice_urn, expmess,aggregate_urn))
        if logr == True:
            return res['value'].keys()
        else:
            return []

    # update the expiration time on a sliver
    def db_update_sliver_info(self, sliver_urn, expiration):
        creds = []
        if expiration is None:
            self.logger.warn("Empty new expiration to record for sliver %s", sliver_urn)
            return None
        # FIXME: put in naiveUTC? Format as ISO8601 or RFC3339?
        if sliver_urn is None or sliver_urn.strip() == "":
            self.logger.warn("Empty sliver_urn to update expiration")
            return
        if not is_valid_urn_bytype(sliver_urn, 'sliver'):
            self.logger.warn("Invalid sliver urn %s", sliver_urn)
            return
        fields = {'SLIVER_INFO_EXPIRATION': str(expiration)}
        options = {'fields' : fields}
        creds, options = self._add_credentials_and_speaksfor(creds, options)
        res = _do_ssl(self, None, "Recording sliver %s updated expiration" % sliver_urn, \
                self.sa.update_sliver_info, sliver_urn, creds, options)
        return self._log_results(res, "Update sliver %s expiration" % sliver_urn)

    # delete the sliver from the chapi database
    def db_delete_sliver_info(self, sliver_urn):
        creds = []
        options = {}
        if sliver_urn is None or sliver_urn.strip() == "":
            self.logger.warn("Empty sliver_urn to record deletion")
# Delete it anyway
#            return
        if not is_valid_urn_bytype(sliver_urn, 'sliver'):
            self.logger.warn("Invalid sliver urn %s", sliver_urn)
# Delete it anyway
#            return
        creds, options = self._add_credentials_and_speaksfor(creds, options)
        res = _do_ssl(self, None, "Recording sliver %s deleted" % sliver_urn,
                      self.sa.delete_sliver_info, sliver_urn, creds, options)
        return self._log_results(res, "Record sliver %s deleted" % sliver_urn)

    def db_find_slivers_for_slice(self, slice_urn):
        slivers_by_agg = {}
        creds = []
        slice_urn = self.slice_name_to_urn(slice_urn)

        slice_expiration = self.get_slice_expiration(slice_urn)

        expired = False
        expmess = ""
        if slice_expiration is not None:
            exp = naiveUTC(slice_expiration)
            if exp < naiveUTC(datetime.datetime.utcnow()):
                expired = True
                expmess = " (EXPIRED at %s)" % slice_expiration

        options = {"match" : {"SLIVER_INFO_SLICE_URN" : slice_urn}}
        # FIXME: Limit to SLICE_EXPIRED: 'f'?
        creds, options = self._add_credentials_and_speaksfor(creds, options)
        res, mess = _do_ssl(self, None, "Find slivers for slice %s%s" % (slice_urn,expmess), \
                          self.sa.lookup_sliver_info, creds, options)

        logr = self._log_results((res, mess), "Find slivers for slice %s%s" % (slice_urn,expmess))
 
        if logr == True:
            for sliver_urn, sliver_info in res['value'].items():
                agg_urn = sliver_info['SLIVER_INFO_AGGREGATE_URN']
                if agg_urn not in slivers_by_agg:
                    slivers_by_agg[agg_urn] = []
                slivers_by_agg[agg_urn].append(sliver_urn)

        return slivers_by_agg
