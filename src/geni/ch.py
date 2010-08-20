#----------------------------------------------------------------------
# Copyright (c) 2010 Raytheon BBN Technologies
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
"""
Reference GENI GCF Clearinghouse. Uses SFA Certificate and credential objects.
Run from gch.py
Will produce signed user credentials from a GID, return a
list of aggregates read from a config file, and create a new Slice Credential.

"""

import datetime
import logging
import os
import traceback
import uuid

from SecureXMLRPCServer import SecureXMLRPCServer
from credential import CredentialVerifier, create_credential, publicid_to_urn, is_valid_urn, string_to_urn_format, create_gid
import sfa.trust.gid as gid

# Substitute eg "openflow//stanford"
# Be sure this matches init-ca.py:CERT_AUTHORITY 
# This is in publicid format
SLICE_AUTHORITY = "geni//gpo//gcf"

# Credential lifetimes in seconds
# Extend slice lifetimes to actually use the resources
USER_CRED_LIFE = 86400
SLICE_CRED_LIFE = 3600

# The list of Aggregates that this Clearinghouse knows about
# should be defined in the geni_aggregates file
# ListResources will refer the client to these aggregates
# Clearinghouse.runserver currently does the register_aggregate_pair
# calls for each row in that file
# but this should be doable dynamically
# Some sample pairs:
# GPOMYPLC = ('urn:publicid:IDN+plc:gpo1+authority+sa',
#             'http://myplc1.gpolab.bbn.com:12348')
# TESTGCFAM = ('urn:publicid:IDN+geni.net:gpo+authority+gcf', 
#              'https://127.0.0.1:8001') 
# OTHERGPOMYPLC = ('urn:publicid:IDN+plc:gpo+authority+site2',
#                    'http://128.89.81.74:12348')
# ELABINELABAM = ('urn:publicid:IDN+elabinelab.geni.emulab.net',
#                 'https://myboss.elabinelab.geni.emulab.net:443/protogeni/xmlrpc/am')

class SampleClearinghouseServer(object):
    """A sample clearinghouse with barebones functionality."""

    def __init__(self, delegate):
        self._delegate = delegate
        
    def GetVersion(self):
        return self._delegate.GetVersion()

    def CreateSlice(self, urn=None):
        return self._delegate.CreateSlice(urn_req=urn)

    def DeleteSlice(self, urn):
        return self._delegate.DeleteSlice(urn)

    def ListAggregates(self):
        return self._delegate.ListAggregates()
    
    def CreateUserCredential(self, cert):
        return self._delegate.CreateUserCredential(cert)


class Clearinghouse(object):

    def __init__(self):
        self.logger = logging.getLogger('gch')
        self.slices = {}
        self.aggs = []

    def load_aggregates(self, aggfile):
        """Loads aggregates from a file.
        
        The file has one aggregate per line. Each line contains a URN
        and a URL separated by a comma.
           
        Returns True if aggregates were loaded, False otherwise.
        """
        if not os.path.isfile(aggfile):
            self.logger.warn('Aggregate file %r does not exist.', aggfile)
            return
        
        line_num = 0
        for line in file(aggfile):
            line_num += 1
            spl = line.split(',')
            if len(spl) != 2:
                msg = ('File %s, line %d is malformed.'
                       + ' Expected "URN, URL", found %r')
                self.logger.warn(msg, aggfile, line_num, line)
                continue
            (urn, url) = spl
            urn = urn.strip()
            url = url.strip()
            if not urn:
                self.logger.warn('Empty URN on line %d of %s',
                                 line_num, aggfile)
                continue
            if not url:
                self.logger.warn('Empty URL on line %d of %s',
                                 line_num, aggfile)
                continue
            if urn in [x for (x, _) in self.aggs]:
                self.logger.warn('Duplicate URN %s at line %d of %s',
                                 urn, line_num, aggfile)
                continue
            self.logger.info("Registering AM %s at %s", urn, url)
            self.aggs.append((urn, url))
        
    def runserver(self, addr, keyfile=None, certfile=None,
                  ca_certs=None, aggfile=None, authority=None):
        """Run the clearinghouse server."""
        # ca_certs is a file of 1 ch cert possibly (itself), or a dir of several for peering
        # If not supplied just use the certfile as the only trusted root
        self.keyfile = keyfile
        self.certfile = certfile

        # Error check the keyfile, certfile all exist
        if keyfile is None or not os.path.isfile(os.path.expanduser(keyfile)):
            raise Exception("Missing CH key file %s" % keyfile)
        if certfile is None or not os.path.isfile(os.path.expanduser(certfile)):
            raise Exception("Missing CH cert file %s" % certfile)

        if ca_certs is None:
            ca_certs = certfile
            self.logger.info("Using only my CH cert as a trusted root cert")

        self.trusted_root_files = CredentialVerifier(ca_certs).root_cert_files
            
        if not os.path.exists(os.path.expanduser(ca_certs)):
            raise Exception("Missing CA cert(s): %s" % ca_certs)

        global SLICE_AUTHORITY
        SLICE_AUTHORITY = authority

        # Load up the aggregates
        self.load_aggregates(aggfile)
        # FIXME: if there are no aggregates, should we continue?
        self.logger.info("%d Aggregate Managers registered from aggregates file %r", len(self.aggs), aggfile)

        # This is the arg to _make_server
        ca_certs_onefname = CredentialVerifier.getCAsFileFromDir(ca_certs)

        # This is used below by CreateSlice
        self.ca_cert_fnames = []
        if os.path.isfile(os.path.expanduser(ca_certs)):
            self.ca_cert_fnames = [os.path.expanduser(ca_certs)]
        elif os.path.isdir(os.path.expanduser(ca_certs)):
            self.ca_cert_fnames = [os.path.join(os.path.expanduser(ca_certs), name) for name in os.listdir(os.path.expanduser(ca_certs)) if name != CredentialVerifier.CATEDCERTSFNAME]

        # Create the xmlrpc server, load the rootkeys and do the ssl thing.
        self._server = self._make_server(addr, keyfile, certfile,
                                         ca_certs_onefname)
        self._server.register_instance(SampleClearinghouseServer(self))
        self.logger.info('GENI CH Listening on port %d...' % (addr[1]))
        self._server.serve_forever()

    def _make_server(self, addr, keyfile=None, certfile=None,
                     ca_certs=None):
        """Creates the XML RPC server."""
        # ca_certs is a file of concatenated certs
        return SecureXMLRPCServer(addr, keyfile=keyfile, certfile=certfile,
                                  ca_certs=ca_certs)

    def GetVersion(self):
        self.logger.info("Called GetVersion")
        version = dict()
        version['gch_api'] = 1
        return version

    # FIXME: Change that URN to be a name and non-optional
    # Currently client.py doesnt supply it, and
    # Omni takes a name and constructs a URN to supply
    def CreateSlice(self, urn_req = None):
        self.logger.info("Called CreateSlice URN REQ %r" % urn_req)
        slice_gid = None

        if urn_req and self.slices.has_key(urn_req):
            # If the Slice has expired, treat this as
            # a request to renew
            slice_cred = self.slices[urn_req]
            if slice_cred.expiration <= datetime.datetime.utcnow():
                # Need to renew this slice
                self.logger.info("CreateSlice on %r found existing cred that expired at %r - will renew", urn_req, slice_cred.expiration)
                slice_gid = slice_cred.get_gid_object()
            else:
                self.logger.debug("Slice cred is still valid at %r until %r - return it", datetime.datetime.utcnow(), slice_cred.expiration)
                return slice_cred.save_to_string()
        
        # First ensure we have a slice_urn
        if urn_req:
            # FIXME: Validate urn_req has the right form
            # to be issued by this CH
            if not is_valid_urn(urn_req):
                # FIXME: make sure it isnt empty, etc...
                urn = publicid_to_urn(urn_req)
            else:
                urn = urn_req
        else:
            # Generate a unique URN for the slice
            # based on this CH location and a UUID

            # Where was the slice created?
            (ipaddr, port) = self._server.socket._sock.getsockname()
            # FIXME: Get public_id start from a properties file
            # Create a unique name for the slice based on uuid
            slice_name = uuid.uuid4().__str__()[4:12]
            public_id = 'IDN %s slice %s//%s:%d' % (SLICE_AUTHORITY, slice_name,
                                                                   ipaddr,
                                                                   port)
            # this func adds the urn:publicid:
            # and converts spaces to +'s, and // to :
            urn = publicid_to_urn(public_id)

        # Now create a GID for the slice (signed credential)
        if slice_gid is None:
            try:
                slice_gid = create_gid(string_to_urn_format(SLICE_AUTHORITY + " slice"), urn, self.keyfile, self.certfile)[0]
            except Exception, exc:
                self.logger.error("Cant create slice gid for slice urn %s: %s", urn, traceback.format_exc())
                raise Exception("Failed to create slice %s. Cant create slice gid" % urn, exc)

        # Now get the user GID which will have permissions on this slice.
        # Get client x509 cert from the SSL connection
        # It doesnt have the chain but should be signed
        # by this CHs cert, which should also be a trusted
        # root at any federated AM. So everyone can verify it as is.
        # Note that if a user from a different CH (installed
        # as trusted by this CH for some reason) called this method,
        # that user would be used here - and can still get a valid slice
        try:
            user_gid = gid.GID(string=self._server.pem_cert)
        except Exception, exc:
            self.logger.error("CreateSlice failed to create user_gid from SSL client cert: %s", traceback.format_exc())
            raise Exception("Failed to create slice %s. Cant get user GID from SSL client certificate." % urn, exc)

        # OK have a user_gid so can get a slice credential
        # authorizing this user on the slice
        try:
            slice_cred = self.create_slice_credential(user_gid,
                                                      slice_gid)
        except Exception, exc:
            self.logger.error('CreateSlice failed to get slice credential for user %r, slice %r: %s', user_gid.get_hrn(), slice_gid.get_hrn(), traceback.format_exc())
            raise Exception('CreateSlice failed to get slice credential for user %r, slice %r' % (user_gid.get_hrn(), slice_gid.get_hrn()), exc)
        self.logger.info('Created slice %r' % (urn))
        
        self.slices[urn] = slice_cred
        
        return slice_cred.save_to_string()

    def DeleteSlice(self, urn_req):
        self.logger.info("Called DeleteSlice %r" % urn_req)
        if self.slices.has_key(urn_req):
            self.slices.pop(urn_req)
            self.logger.info("Deleted slice")
            return True
        self.logger.info('Slice was not found')
        # Slice not found!
        # FIXME: Raise an error so client knows why this failed?
        return False

    def ListAggregates(self):
        self.logger.info("Called ListAggregates")
        # TODO: Allow dynamic registration of aggregates
        return self.aggs
    
    def CreateUserCredential(self, user_gid):
        '''Return string representation of a user credential
        issued by this CH with caller/object this user_gid (string)
        with user privileges'''
        # FIXME: Validate arg - non empty, my user
        user_gid = gid.GID(string=user_gid)
        self.logger.info("Called CreateUserCredential for GID %s" % user_gid.get_hrn())
        try:
            ucred = create_credential(user_gid, user_gid, USER_CRED_LIFE, 'user', self.keyfile, self.certfile, self.trusted_root_files)
        except Exception, exc:
            self.logger.error("Failed to create user credential for %s: %s", user_gid.get_hrn(), traceback.format_exc())
            raise Exception("Failed to create user credential for %s" % user_gid.get_hrn(), exc)
        return ucred.save_to_string()
    
    def create_slice_credential(self, user_gid, slice_gid):
        '''Create a Slice credential object for this user_gid (object) on given slice gid (object)'''
        # FIXME: Validate the user_gid and slice_gid
        # are my user and slice
        return create_credential(user_gid, slice_gid, SLICE_CRED_LIFE, 'slice', self.keyfile, self.certfile, self.trusted_root_files )

