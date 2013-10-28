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
import json
import logging
import os
import sys

import M2Crypto.SSL

from omnilib.util.paths import getAbsPath
from omnilib.util import OmniError
import omnilib.util.credparsing as credutils
import omnilib.util.json_encoding as json_encoding
import omnilib.xmlrpc.client

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
                target = ""
                try:
                    target = credutils.get_cred_target_urn(logger, cred)
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

    def list_my_ssh_keys(self):
        """
        Get a list of SSH public keys for this user.
        Returns: a list of SSH public keys
        """
        raise NotImplementedError('list_my_ssh_keys')

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
        return omnilib.xmlrpc.client.make_client(url, keyfile, certfile,
                                                 verbose=verbose,
                                                 timeout=timeout,
                                                 allow_none=allow_none)

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
        raise NotImplementedError('get_user_cred_struct')

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
        raise NotImplementedError('get_slice_cred_struct')

    def wrap_cred(self, cred):
        """
        Wrap the given cred in the appropriate struct for this framework.
        """
        raise NotImplementedError('wrap_cred')

    # write new sliver_info to the database using chapi
    def db_create_sliver_info(self, sliver_urn, slice_urn, creator_urn,
                              aggregate_urn, expiration):
        raise NotImplementedError('db_create_sliver_info')

    # use the database to convert an aggregate url to the corresponding urn
    def db_agg_url_to_urn(self, agg_url):
        raise NotImplementedError('db_agg_url_to_urn')

    # given the slice urn and aggregate urn, find the slice urn from the db
    def db_find_sliver_urn(self, slice_urn, aggregate_urn):
        raise NotImplementedError('db_find_sliver_urn')
        
    # update the expiration time on a sliver
    def db_update_sliver_info(self, sliver_urn, expiration):
        raise NotImplementedError('db_update_sliver_info')
        
    # delete the sliver from the chapi database
    def db_delete_sliver_info(self, sliver_urn):
        raise NotImplementedError('db_delete_sliver_info')
