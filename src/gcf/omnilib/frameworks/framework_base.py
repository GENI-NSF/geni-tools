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

import json
import logging
import os
import sys

import M2Crypto.SSL

from ..util.paths import getAbsPath
from ..util import OmniError
from ..util import credparsing as credutils
from ..util import json_encoding
from ..xmlrpc import client as xmlrpcclient

from ...sfa.trust.credential import Credential

class Framework_Base():
    """
    Framework_Base is an abstract class that identifies the minimal set of functions
    that must be implemented in order to add a control framework to omni.  
    
    Instructions for adding a new framework:
    
    Create "framework_X" in the frameworks directory, where X is your control framework.
    
    Create a Framework class in the file that inherits "Framework_Base" and fill out each of the functions.
    
    Edit the sample "omni_config" file and add a section for your framework, giving the section
    the same name as X used in framework_X.  For instance, 'sfa' or 'gcf'.  Your framework's section
    of the omni config *MUST* have a cert and key entry, which omni will use when talking to 
    the GENI Aggregate managers.
    
    """
    
    def __init__(self, config):
        self.cert = getAbsPath(config['cert'])
        if not os.path.exists(self.cert):
            sys.exit("Frameworks certfile %s doesn't exist" % self.cert)
        if not os.path.getsize(self.cert) > 0:
            sys.exit("Frameworks certfile %s is empty" % self.cert)

        self.key = getAbsPath(config['key'])
        if not os.path.exists(self.key):
            sys.exit("Frameworks keyfile %s doesn't exist" % self.key)
        if not os.path.getsize(self.key) > 0:
            sys.exit("Frameworks keyfile %s is empty" % self.key)
        self.sslctx = None

    def init_user_cred( self, opts ):
        """Initialize user credential either from file (if
        --usercredfile) or else to None.

        Must call this method in framework's __init__ in order for
        --usercredfile to be handled properly.
        Returns the usercred - in XML string format.
        """
        
        try:
            if self.user_cred_struct is not None:
                pass
        except:
            self.user_cred_struct = None

        # read the usercred from supplied file
        cred = None
        if opts.usercredfile and os.path.exists(opts.usercredfile) and os.path.isfile(opts.usercredfile) and os.path.getsize(opts.usercredfile) > 0:
            # read the user cred from the given file
            if hasattr(self, 'logger'):
                logger = self.logger
            else:
                logger = logging.getLogger("omni.framework")
            logger.info("Getting user credential from file %s", opts.usercredfile)
#            cred = _load_cred(logger, opts.usercredfile)
            with open(opts.usercredfile, 'r') as f:
                cred = f.read()
            try:
                cred = json.loads(cred, encoding='ascii', cls=json_encoding.DateTimeAwareJSONDecoder)
                if cred and isinstance(cred, dict) and \
                        cred.has_key('geni_type') and \
                        cred.has_key('geni_value') and \
                        cred['geni_type'] == Credential.SFA_CREDENTIAL_TYPE and \
                        cred['geni_value'] is not None:
                    self.user_cred_struct = cred
            except Exception, e:
                logger.debug("Failed to get a JSON struct from cred in file %s. Treat as a string: %s", opts.usercredfile, e)
            cred2 = credutils.get_cred_xml(cred)
            if cred2 is None or cred2 == "":
                logger.info("Did NOT get valid user cred from %s", opts.usercredfile)
                if opts.devmode:
                    logger.info(" ... but using it anyhow")
                else:
                    cred = None
            else:
                # This would force a saved user cred in struct to be XML. Is that correct?
                #cred = cred2
                target = ""
                try:
                    target = credutils.get_cred_target_urn(logger, cred)
                    if "+authority+sa" in target:
                        self.logger.debug("Got target %s - PG user creds list the user as the owner only", target)
                        target = credutils.get_cred_owner_urn(logger, cred)
                except:
                    if not opts.devmode:
                        logger.warn("Failed to parse target URN from user cred?")
                logger.info("Read user %s credential from file %s", target, opts.usercredfile)
        elif opts.usercredfile:
            if hasattr(self, 'logger'):
                logger = self.logger
            else:
                logger = logging.getLogger("omni.framework")
            logger.info("NOT getting user credential from file %s - file doesn't exist or is empty", opts.usercredfile)

        return cred
        
    def get_version(self):
        """
        Returns a dict of the GetVersion return from the control framework. And an error message if any.
        """
        raise NotImplementedError('get_version')

    def get_user_cred(self):
        """
        Returns a user credential from the control framework as a string. And an error message if any.
        """
        raise NotImplementedError('get_user_cred')
    
    def get_slice_cred(self, urn):
        """
        Retrieve a slice with the given urn and returns the signed credential as a string.
        """
        raise NotImplementedError('get_slice_cred')
    
    def create_slice(self, urn):    
        """
        If the slice already exists in the framework, it returns that.  Otherwise it creates the slice
        and returns the new slice as a string.
        """
        raise NotImplementedError('create_slice')

    def delete_slice(self, urn):
        """
        Removes the slice from the control framework.
        """
        raise NotImplementedError('delete_slice')

    def list_aggregates(self):
        """
        Get a list of available GENI Aggregates from the control framework.
        Returns: a dictionary where keys are urns and values are aggregate urls
        """
        raise NotImplementedError('list_aggregates')

    def list_my_slices(self, username):
        """
        Get a list of slices for this user.
        Returns: a list of slice URNs
        """
        raise NotImplementedError('list_my_slices')

    def list_my_projects(self, username):
        """
        '''List projects owned by the user (name or URN) provided, returning a list of structs, containing
        PROJECT_URN, PROJECT_UID, EXPIRED, and PROJECT_ROLE. EXPIRED is a boolean.'''
        """
        raise NotImplementedError('list_my_projects')

    def list_ssh_keys(self, username=None):
        """
        Get a list of SSH key pairs for the given user or the configured current user if not specified.
        Private key will be omitted if not known or found.
        Returns: a list of structs containing SSH key pairs ('public_key', 'private_key' (may be omitted))
        """
        raise NotImplementedError('list_ssh_keys')

    def slice_name_to_urn(self, name):
        """Convert a slice name to a slice urn."""
        # Default implementation just converts to generic URN.
        raise NotImplementedError('slice_name_to_urn')

    def renew_slice(self, urn, requested_expiration):
        """Renew a slice.

        urn is framework urn, already converted via slice_name_to_urn.
        requested_expiration is a datetime object.

        Returns the expiration date as a datetime. If there is an error,
        print it and return None.
        """
        raise NotImplementedError('renew_slice')

    def make_client(self, url, keyfile, certfile, verbose=False, timeout=None,
                    allow_none=False):
        """Create an API client. This is currently an XML-RPC client
        over SSL with a client side certificate."""
        return xmlrpcclient.make_client(url, keyfile, certfile,
                                                 verbose=verbose,
                                                 timeout=timeout,
                                                 allow_none=allow_none)

    # See xmlrpc/client.py where this would be used to use M2Crypto for the SSL client
    # supporting entering the password only once. But this had problems and is not used.
    def ssl_context(self, retries=2):
        """Returns an SSL Context or an exception is raised."""
        if hasattr(self, 'logger'):
            logger = self.logger
        else:
            logger = logging.getLogger("omni.framework")
        logger.warning("*** Creating an SSL Context! ***")
        if not self.sslctx:
            # Initialize the M2Crypto SSL Context
            attempts = 0
            while attempts <= retries:
                sslctx = M2Crypto.SSL.Context()
                try:
                    sslctx.load_cert_chain(self.cert, self.key)
                    self.sslctx = sslctx
                    break
                except M2Crypto.SSL.SSLError, err:
                    logger.error('Wrong pass phrase for private key.')
                    attempts = attempts + 1
                    if attempts > retries:
                        logger.error("Wrong pass phrase after %d tries.",
                                     attempts)
                        raise OmniError(err)
                    else:
                        logger.info('.... please retry.')
        return self.sslctx

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
        if hasattr(self, 'logger'):
            logger = self.logger
        else:
            logger = logging.getLogger("omni.framework")
        if isinstance(cred, dict):
            logger.debug("Called wrap on a cred that's already a dict? %s", cred)
            return cred
        elif not isinstance(cred, str):
            logger.warn("Called wrap on non string cred? Stringify. %s", cred)
            cred = str(cred)
        cred_type, cred_version = credutils.get_cred_type(cred)
        ret = dict(geni_type=cred_type, geni_version=cred_version, \
                       geni_value=cred)
        return ret

    # get the slice members (urn, email) and their public ssh keys and
    # slice role
    def get_members_of_slice(self, slice_urn):
        raise NotImplementedError('get_members_of_slice')

    # get the members (urn, email) and their role in the project
    def get_members_of_project(self, project_name):
        '''Look up members of the project with the given name.
        Return is a list of member dictionaries
        containing PROJECT_MEMBER (URN), EMAIL, PROJECT_MEMBER_UID, and PROJECT_ROLE.
        '''
        raise NotImplementedError('get_members_of_project')

    # add a new member to a slice (giving them rights to get a slice credential)
    def add_member_to_slice(self, slice_urn, member_name, role = 'MEMBER'):
        raise NotImplementedError('add_member_to_slice')

    # remove a member from a slice 
    def remove_member_from_slice(self, slice_urn, member_name):
        raise NotImplementedError('remove_member_from_slice')

    # Record new slivers at the CH database 
    # write new sliver_info to the database using chapi
    # Manifest is the XML when using APIv1&2 and none otherwise
    # expiration is the slice expiration
    # slivers is the return struct from APIv3+ or None
    # If am_urn is not provided, infer it from the url
    # If both are not provided, infer the AM from the sliver URNs
    def create_sliver_info(self, manifest, slice_urn,
                              aggregate_url, expiration, slivers, am_urn):
        raise NotImplementedError('create_sliver_info')

    # use the CH database to convert an aggregate url to the corresponding urn
    def lookup_agg_urn_by_url(self, agg_url):
        raise NotImplementedError('lookup_agg_urn_by_url')

    # given the slice urn and aggregate urn, find the associated sliver urns from the CH db
    # Return an empty list if none found
    def list_sliverinfo_urns(self, slice_urn, aggregate_urn):
        raise NotImplementedError('list_sliverinfo_urns')

    # update the expiration time for a sliver recorded at the CH,
    # If we get an argument error indicating the sliver was not yet recorded, try
    # to record it
    def update_sliver_info(self, aggregate_urn, slice_urn, sliver_urn, expiration):
        raise NotImplementedError('update_sliver_info')

    # delete the sliver from the CH database of slivers in a slice
    def delete_sliver_info(self, sliver_urn):
        raise NotImplementedError('delete_sliver_info')

    # Find all slivers the SA lists for the given slice
    # Return a struct by AM URN containing a struct: sliver_urn = sliver info struct
    # Compare with list_sliverinfo_urns which only returns the sliver URNs
    def list_sliver_infos_for_slice(self, slice_urn):
        return {}
        
