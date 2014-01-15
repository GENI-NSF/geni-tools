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

from geni.util.urn_util import is_valid_urn, URN, string_to_urn_format,\
    nameFromURN
import sfa.trust.gid as gid

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
        
        self.ch = self.make_client(config['ch']+'/CH', self.key, self.cert,
                                   verbose=config['verbose'])
        self.ma = self.make_client(config['ch']+'/MA', self.key, self.cert,
                                   verbose=config['verbose'])
        self.sa = self.make_client(config['ch']+'/SA', self.key, self.cert,
                                   verbose=config['verbose'])

        self.cert = config['cert']
        self.cert_string = file(self.cert, 'r').read()
        self.cert_gid = gid.GID(filename=self.cert)
        self.user_urn = self.cert_gid.get_urn()
        self.user_cred = self.init_user_cred( opts )
        self.logger = config['logger']

    # Add new options and credentials based on provided opts 
    def _augment_credentials_and_options(self, credentials, options):
        self.logger.info("GSC self.opts.speaksfor = %s" % self.opts.speaksfor)
        self.logger.info("GSC self.opts.cred = %s" % self.opts.cred)
        new_credentials = credentials
        new_options = options
        if self.opts.speaksfor:
            options['speaking_for'] = self.opts.speaksfor
        if self.opts.cred:
            for cred_filename in self.opts.cred:
                cred_contents = open(cred_filename).read()
                new_cred = {'geni_type' : 'geni_abac',
                            'geni_value' : cred_contents,
                            'geni_version' : '1.0'}
                new_credentials.append(new_cred)
        self.logger.info("GSC new_creds = %s new_options = %s" % (new_credentials, new_options))
        return new_credentials, new_options

    def get_user_cred(self):
        message = ""
        creds = []
        options = {}

        creds, options = self._augment_credentials_and_options(creds, options)

        if self.user_cred == None:
            self.logger.debug("Getting user credential from CHAPI MA %s", self.config['ch'])
            (res, message) = _do_ssl(self, None, ("Create user credential on CHAPI MA %s" % self.ma),
                                     self.ma.get_credentials,
                                     self.user_urn,
                                     creds,
                                     options)
            if res is not None:
                if res['code'] == 0:
                    self.user_cred = self._select_cred(res['value'])
                else:
                    message = res['output']
                    self.logger.error(message)
                    
        return self.user_cred, message
    
    def get_slice_cred(self, slice_urn):
        # self.get_user_cred()
        # scred = ''
        # if self.user_cred is not None:
        #     scred = self.user_cred
        scred = []
        options = {}

        scred, options = self._augment_credentials_and_options(scred, options)

        slice_name = nameFromURN(slice_urn)
        # how do we get this information into options?

        (res, message) = _do_ssl(self, None, ("Get credentials for slice %s on CHAPI SA %s" % (slice_urn, self.config['ch'])),
                                 self.sa.get_credentials, slice_urn, scred, 
                                 options)

        cred = None
        if res is not None:
            if res['code'] == 0:
                d = res['value']
                if d is not None:
                    cred = self._select_cred(d)
            else:
                message = res['output']
                self.logger.error(message)
        return cred

    def list_my_ssh_keys(self):
        # self.get_user_cred()
        # scred = ''
        # if self.user_cred is not None:
        #     scred = self.user_cred
        scred = []

        options = {'match': {'KEY_MEMBER': self.user_urn}}
        self.logger.debug("Getting my SSH keys from CHAPI MA %s", self.config['ch'])
        (res, message) = _do_ssl(self, None, ("Get public SSH keys MA %s" % self.ma),
                                 self.ma.lookup_keys,
                                 scred,
                                 options)

        keys = []
        message = None
        if res is not None:
            if res['code'] == 0:
                d = res['value']
                for uid, key_tups in d.items():
                    for key_tup in key_tups:
                        if 'KEY_PUBLIC' in key_tup:
                            keys.append(key_tup['KEY_PUBLIC'])
            else:
                message = res['output']
                self.logger.error(message)

        return keys

    def _select_cred(self, creds):
        for cred in creds:
            if cred['geni_type'] == 'geni_sfa':
                return cred['geni_value']

    def create_slice(self, urn):
        # self.get_user_cred()
        # scred = ''
        # if self.user_cred is not None:
        #     scred = self.user_cred
        scred = []

        if self.opts.project:
            # use the command line option --project
            project = self.opts.project
        elif self.config.has_key('default_project'):
            # otherwise, default to 'default_project' in 'omni_config'
            project = self.config['default_project']
        else:
            # None means there was no project defined
            # name better be a urn (which is checked below)
            project = None

        if not self.config.has_key('authority'):
            raise Exception("Invalid configuration: no authority defined")
        auth = self.config['authority']

        project_urn = URN(authority = auth,
                          type = 'project',
                          name = project).urn_string()
        slice_name = nameFromURN(urn)
        # how do we get this information into options?
        options = {'fields': 
                   {'SLICE_NAME': slice_name,
                    # 'SLICE_DESCRIPTION': "",  # not provided
                    'SLICE_PROJECT_URN': project_urn,
                    }}
        (res, message) = _do_ssl(self, None, ("Create slice %s on CHAPI SA %s" % (slice_name, self.config['ch'])),\
                                     self.sa.create_slice, scred, options)
        if res is not None:
            if res['code'] == 0:
                d = res['value']
                if d is not None:
                    slice_urn = d['SLICE_URN']
            else:
                message = res['output']
                self.logger.error(message)
                return None

        (res, message) = _do_ssl(self, None, ("Get credentials for slice %s on CHAPI SA %s" % (slice_name, self.config['ch'])),
                                 self.sa.get_credentials, slice_urn, scred, 
                                 options)

        cred = None
        if res is not None:
            if res['code'] == 0:
                d = res['value']
                if d is not None:
                    cred = self._select_cred(d)
            else:
                message = res['output']
                self.logger.error(message)

        return cred
    
    def delete_slice(self, urn):
        self.logger.error("CHAPI SA does not allow delete_slice")
        return False
     
    def list_aggregates(self):
        # TODO: list of field names from getVersion - should we get all or assume we have URN and URL
        (res, message) = _do_ssl(self, None, ("List Aggregates at CHAPI CH %s" % self.config['ch']), 
                                 self.ch.lookup_aggregates,
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

        # self.get_user_cred()
        # scred = ''
        # if self.user_cred is not None:
        #     scred = self.user_cred
        scred = []

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

        options = {}

        (res, message) = _do_ssl(self, None, ("List Slices for %s at CHAPI SA %s" % (user, self.config['ch'])), 
                                    self.sa.lookup_slices_for_member, userurn, scred, options)

        slices = None
        if res is not None:
            if res['code'] == 0:
                slices = res['value']
            else:
                message = res['output']
        if message is not None:
            self.logger.error(message)

        # Return is a urn. Strip out the name
        slicenames = list()
        if slices and isinstance(slices, list):
            for slice in [tup['SLICE_URN'] for tup in slices]:
                slicelower = string.lower(slice)
                if not string.find(slicelower, "+slice+"):
                    continue
                slicename = slice[string.index(slicelower,"+slice+") + len("+slice+"):]
                slicenames.append(slicename)
        return slicenames
    
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

        # only require a project if name isn't a URN
        if self.opts.project:
            # use the command line option --project
            project = self.opts.project
        elif self.config.has_key('default_project'):
            # otherwise, default to 'default_project' in 'omni_config'
            project = self.config['default_project']
        else:
            # None means there was no project defined
            # name better be a urn (which is checked below)
            project = None

        auth = self.config['authority']
        if project:
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

    def renew_slice(self, urn, expiration_dt):
        """See framework_base for doc.
        """
        # self.get_user_cred()
        # scred = ''
        # if self.user_cred is not None:
        #     scred = self.user_cred
        scred = []

        expiration = expiration_dt.strftime("%Y-%m-%d %H:%M:%S")
        options = {'fields':{'SLICE_EXPIRATION':expiration}}
        res = None
        (res, message) = _do_ssl(self, None, ("Renew slice %s on CHAPI SA %s until %s" % (urn, self.config['ch'], expiration_dt)), 
                                  self.sa.update_slice, urn, scred, options)

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


    def get_member_email(self, urn):
        creds = []
        options = {'match': {'MEMBER_URN': urn}, 'filter': ['MEMBER_EMAIL']}
        res, mess = _do_ssl(self, None, "Looking up member email",
                            self.ma.lookup_identifying_member_info, creds, options)
        self.log_results((res, mess), 'Lookup member email')
        if not res['value']:
            return None
        return res['value'].values()[0]['MEMBER_EMAIL']

    def get_member_keys(self, urn):
        creds = []
        options = {'match': {'KEY_MEMBER': urn}, 'filter': ['KEY_PUBLIC']}
        res, mess = _do_ssl(self, None, "Looking up member keys",
                            self.ma.lookup_keys, creds, options)
        self.log_results((res, mess), 'Lookup member keys')
        if not res['value']:
            return None
        return [val['KEY_PUBLIC'] for val in res['value'].values()[0]]

    # get the members (urn, email) and their ssh keys
    def get_members_of_slice(self, slice_urn):
        creds = []
        options = {}
        res, mess = _do_ssl(self, None, "Looking up slice member",
                            self.sa.lookup_slice_members, slice_urn, 
                            creds, options)
        self.log_results((res, mess), 'Get members for slice')
        members = []
        for member_vals in res['value']:
            member_urn = member_vals['SLICE_MEMBER']
            member = {'URN': member_urn}
            member['EMAIL'] = self.get_member_email(member_urn)
            member['KEYS'] = self.get_member_keys(member_urn)
            members.append(member)
        return members, mess

    # add a new member to a slice
    def add_member_to_slice(self, slice_urn, member_urn, role = 'MEMBER'):
        creds = []
        options = {'members_to_add': [{'SLICE_MEMBER': member_urn,
                                       'SLICE_ROLE': role}]}
        res, mess = _do_ssl(self, None, "Adding member to slice",
                            self.sa.modify_slice_membership,
                            slice_urn, creds, options)
        success = self.log_results((res, mess), 'Add member to slice')
        return (success, mess)

    # handle logging or results for db functions
    def log_results(self, results, action):
        (res, message) = results
        if res is not None:
            if res['code'] == 0:
                self.logger.debug('Successfully completed ' + action)
                return True
            else:
                self.logger.warn(action + ' failed, message: ' + res['output'])
        else:
            self.logger.warn(action + ' failed for unknown reason')
        return False

    # write new sliver_info to the database using chapi
    def db_create_sliver_info(self, sliver_urn, slice_urn, creator_urn,
                              aggregate_urn, expiration):
        creds = []
        fields = {"SLIVER_INFO_URN": sliver_urn,
                  "SLIVER_INFO_SLICE_URN": slice_urn,
                  "SLIVER_INFO_AGGREGATE_URN": aggregate_urn,
                  "SLIVER_INFO_CREATOR_URN": creator_urn}
        options = {'fields' : fields}
        if (expiration):
            fields["SLIVER_INFO_EXPIRATION"] = str(expiration)
        res = _do_ssl(self, None, "Recording sliver creation",
                      self.sa.create_sliver_info, creds, options)
        self.log_results(res, "Create sliver info")

    # use the database to convert an aggregate url to the corresponding urn
    def db_agg_url_to_urn(self, agg_url):
        options = {'filter': ['SERVICE_URN'],
                   'match': {'SERVICE_URL': agg_url}}
        res, mess = _do_ssl(self, None, "Lookup aggregate urn",
                            self.ch.lookup_aggregates, options)
        self.log_results((res, mess), 'Convert agg url to urn')
        if len(res['value']) == 0:
            return None
        return res['value'][0]['SERVICE_URN']

    # given the slice urn and aggregate urn, find the slice urn from the db
    def db_find_sliver_urns(self, slice_urn, aggregate_urn):
        creds = []
        options = {'filter': [],
                   'match': {'SLIVER_INFO_SLICE_URN': slice_urn,
                             "SLIVER_INFO_AGGREGATE_URN": aggregate_urn}}
        res, mess = _do_ssl(self, None, "Lookup sliver urn",
                            self.sa.lookup_sliver_info, creds, options)
        self.log_results((res, mess), 'Find sliver urn')
        return res['value'].keys()
        
    # update the expiration time on a sliver
    def db_update_sliver_info(self, sliver_urn, expiration):
        creds = []
        fields = {'SLIVER_INFO_EXPIRATION': str(expiration)}
        options = {'fields' : fields}
        res = _do_ssl(self, None, "Recording sliver update", \
                self.sa.update_sliver_info, sliver_urn, creds, options)
        self.log_results(res, "Update sliver info")
        
    # delete the sliver from the chapi database
    def db_delete_sliver_info(self, sliver_urn):
        creds = []
        options = {}
        res = _do_ssl(self, None, "Recording sliver delete",
                      self.sa.delete_sliver_info, sliver_urn, creds, options)
        self.log_results(res, "Delete sliver info")

    def db_find_slivers_for_slice(self, slice_urn):
        slivers_by_agg = {}
        creds = []
        options = {"match" : {"SLIVER_INFO_SLICE_URN" : slice_urn}}
        res, mess = _do_ssl(self, None, "Find slivers for slice", \
                          self.sa.lookup_sliver_info, creds, options)
        
        if res['code'] == 0:
            for sliver_urn, sliver_info in res['value'].items():
                agg_urn = sliver_info['SLIVER_INFO_AGGREGATE_URN']
                if agg_urn not in slivers_by_agg:
                    slivers_by_agg[agg_urn] = []
                slivers_by_agg[agg_urn].append(sliver_urn)

        self.log_results((res, mess), "Find slivers for slice")

        return slivers_by_agg
        

