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
import sys
import logging
import os
import M2Crypto.SSL
from omnilib.util.paths import getAbsPath
from omnilib.util import OmniError
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

        self.key = getAbsPath(config['key'])
        if not os.path.exists(self.key):
            sys.exit("Frameworks keyfile %s doesn't exist" % self.key)
        self.sslctx = None

    def init_user_cred( self, opts ):
        """Initialize user credential either from file (if
        --usercredfile) or else to None.

        Must call this method in framework's __init__ in order for
        --usercredfile to be handled properly.
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
            with open(opts.usercredfile, 'r') as f:
                cred = f.read()
        return cred
        
    def get_user_cred(self):
        """
        Returns a user credential from the control framework as a string. And an error messge if any.
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
        Returns: a list of slice names
        """
        raise NotImplementedError('list_my_slices')

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
