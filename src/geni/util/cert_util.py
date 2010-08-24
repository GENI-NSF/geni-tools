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
'''
Certificate (GID in SFA terms) creation and verification utilities.
'''


from sfa.trust.gid import GID
from geni.util.urn_util import is_valid_urn

def create_cert(subject, urn, issuer_keyfile, issuer_certfile):
    '''Create a GID for given subject and URN issued by given key/cert,
    generating new keys.
    Return newgid, keys'''
    import sfa.trust.certificate as cert
    # FIXME: Validate the gid_urn has the right prefix
    # to be a URN and match the issuer
    # FIXME: Validate the issuer key/cert exist and match and are valid
    if not is_valid_urn(urn):
        raise ValueError("Invalid GID URN %s" % urn)
    newgid = GID(create=True, subject=subject, urn=urn)
    keys = cert.Keypair(create=True)
    newgid.set_pubkey(keys)
    issuer_key = cert.Keypair(filename=issuer_keyfile)
    issuer_cert = GID(filename=issuer_certfile)
    newgid.set_issuer(issuer_key, cert=issuer_cert)
    newgid.set_parent(issuer_cert)
    newgid.encode()
    newgid.sign()
    return newgid, keys

