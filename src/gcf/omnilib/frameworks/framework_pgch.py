#----------------------------------------------------------------------
# Copyright (c) 2012-2015 Raytheon BBN Technologies
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

import logging
from urlparse import urlparse

from .framework_pg import Framework as pg_framework
from ..util.dossl import _do_ssl
from ..util.handler_utils import _get_user_urn
from ..util import OmniError
from ...geni.util.urn_util import is_valid_urn, URN, string_to_urn_format
from ...sfa.util.xrn import urn_to_hrn, hrn_to_urn

class Framework(pg_framework):
    """Framework to talk to the GENI Clearinghouse (or similar) using PG CH APIs.
    The difference here is that there is a project name which is appended to the 
    SA hostname to construct the authority field in the slice URN.
    """

    def __init__(self, config, opts):
        fwtype = "GENI Clearinghouse"
        pg_framework.__init__(self,config, opts)
        self.fwtype = "GENI Clearinghouse"
        self.opts = opts
        self.logger = logging.getLogger("omni.pgch")

    def list_my_slices(self, user):
        '''List slices owned by the user (name or hrn or URN) provided, returning a list of slice URNs.'''
        userhrn = self.user_name_to_hrn(user)
        return self._list_my_slices(userhrn)

    def user_name_to_hrn(self, name):
        '''Convert a username to an HRN. Accept an HRN or URN though. Authority
        is taken from the SA hostname.'''

        if name is None or name.strip() == '':
            raise Exception('Empty user name')

        # If the name is a URN, convert it
        if is_valid_urn(name):
            (hrn, type) = urn_to_hrn(name)
            if type != 'user':
                raise Exception("Not a user! %s is of type %s" % (name, type))
            self.logger.debug("Treating name %s as a URN, with hrn %s", name, hrn)
            name = hrn

        # Otherwise, construct the hrn (or maybe this is one)

        if not self.config.has_key('sa'):
            raise Exception("Invalid configuration: no slice authority (sa) defined")

        if self.config.has_key('authority') and self.config['authority'].strip()!='':
            auth = self.config['authority']
            # Must escape any periods so that SFA XRN code treats this whole thing as the authority name
            auth = auth.replace('.', '\.')
        else:
            # Get the authority from the SA hostname
            url = urlparse(self.config['sa'])
            sa_host = url.hostname
            try:
                sa_hostname, sa_domain = sa_host.split(".",1)
                auth = sa_hostname
            except:
                # Funny SA
                self.logger.debug("Found no . in sa hostname. Using whole hostname")
                auth = sa_host

        # Assume for now that if the name looks like auth.name, then it is a valid hrn
        if name.startswith(auth + '.'):
            self.logger.debug("Treating %s as an hrn", name)
            return name

        hrn = auth + '.' + name
        self.logger.debug("Treating %s as just the name, with full hrn %s", name, hrn)

        return hrn

    def slice_name_to_urn(self, name):
        """Convert a slice name and project name to a slice urn."""
        #
        # Sample URN:
        #   urn:publicid:IDN+portal:myproject+slice+myexperiment
        #

        if name is None or name.strip() == '':
            raise Exception('Empty slice name')

        if not self.config.has_key('sa'):
            raise Exception("Invalid configuration: no slice authority (sa) defined")

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


        if self.config.has_key('authority') and self.config['authority'].strip()!='':
            auth = self.config['authority']
            # It appears that here we don't need to escape the periods, at least for now. 
            # Probably because we generate a URN here and not an HRN.
#            # Must escape any periods so that SFA XRN code treats this whole thing as the authority name
#            auth = auth.replace('.', '\.')
        else:
            # Get the authority from the SA hostname
            url = urlparse(self.config['sa'])
            sa_host = url.hostname
            try:
                sa_hostname, sa_domain = sa_host.split(".",1)
                auth = sa_hostname
            except:
                # Funny SA
                self.logger.debug("Found no . in sa hostname. Using whole hostname")
                auth = sa_host


        # Authority is of form: host:project
        # if project isn't defined, you should have provided a full slice urn
        baseauth = auth
        if project:
            auth = baseauth+":"+project

        # Check whether name is a urn (and return it if it is)
        # Could use is_valid_urn_bytype here, or just let the SA/AM do the check
        if is_valid_urn(name):
            urn = URN(None, None, None, urn=name)
            if not string_to_urn_format(urn.getType()) == "slice":
                errmsg = "Invalid Slice name: got a non Slice URN %s"% name
                self.logger.error(errmsg)
                raise OmniError, errmsg                
            # if config has an authority, make sure it matches
            urn_auth = string_to_urn_format(urn.getAuthority())
            # check to make sure the URN matches the configured authority
            if not urn_auth.startswith(baseauth):
                self.logger.warn("Slice authority (%s) didn't start with expected authority name: %s", urn_auth, baseauth)
            # check to make sure the URN matches the configured project (but only if the project is configured)
            if project and urn_auth != auth:
                self.logger.warn("CAREFUL: slice' authority (%s) doesn't match current configured authority (%s)" % (urn_auth, auth))
                self.logger.info("This may be OK though if you are using delegated slice credentials...")
            return name

        # would like to check this earlier, but can't because have to wait to see if name is a complete urn
        if not project:
            errmsg = "Invalid configuration: no default project defined"
            self.logger.error(errmsg)
            raise OmniError, errmsg

        return URN(auth, "slice", name).urn_string()

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

        # PGCH implements getversion only once
#        sa_response = None
#        (sa_response, message2) = _do_ssl(self, None, ("GetVersion of %s SA %s using cert %s" % (self.fwtype, self.config['sa'], self.config['cert'])), self.sa.GetVersion)
#        _ = message2 #Appease eclipse
#        if sa_response is not None:
#            if isinstance(sa_response, dict) and sa_response.has_key('value'):
#                versionstruct['sa-version'] = sa_response['value']
#            else:
#                versionstruct['sa-version'] = sa_response

        return versionstruct, message

    def list_ssh_keys(self, username=None):
        if username is None or username.strip() == "":
            username = _get_user_urn(self.logger, self.config)
        if not is_valid_urn(username):
            hrn = self.user_name_to_hrn(username)
            username = hrn_to_urn(hrn, 'user')
        self.logger.debug("Looking up user %s" % username)
        key_list, message = self._list_ssh_keys(username)
        return key_list, message

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

            # Removed code to test that the URL is something that
            # speaks the AM API - expensive and at our portal
            # shouldn't be necessary

            cm_dict['am_url'] = am_url
            result.append(cm_dict)
        return result

