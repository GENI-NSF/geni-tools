#!/usr/bin/env python

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

"""Create a certificate authority and some basic certs and keys.

A CA is created, as well as certificates and keys for two authorities:
a clearinghouse and an aggregate manager. Finally, a user cert and
key is created for a user named Alice.
"""

import sys

# Check python version. Requires 2.6 or greater, but less than 3.
if sys.version_info < (2, 6):
    raise Exception('Must use python 2.6 or greater.')
elif sys.version_info >= (3,):
    raise Exception('Not python 3 ready')

import optparse
import os.path
import geni
import sfa.trust.gid as gid
import sfa.trust.certificate as cert
import sfa.trust.credential as cred

CA_CERT_FILE = 'ca-cert.pem'
CA_KEY_FILE = 'ca-key.pem'
CH_CERT_FILE = 'ch-cert.pem'
CH_KEY_FILE = 'ch-key.pem'
AM_CERT_FILE = 'am-cert.pem'
AM_KEY_FILE = 'am-key.pem'

def create_cert(subject, issuer_key=None, issuer_cert=None, intermediate=False):
    urn = 'urn:publicid:IDN+%s' % subject
    newgid = gid.GID(create=True, subject=subject,
                     urn=urn)
    keys = cert.Keypair(create=True)
    newgid.set_pubkey(keys)
    if intermediate:
        newgid.set_intermediate_ca(intermediate)
        
    if issuer_key:
        newgid.set_issuer(issuer_key, cert=issuer_cert)
        newgid.set_parent(issuer_cert)
    else:
        # create a self-signed cert
        newgid.set_issuer(keys, subject=subject)
    newgid.encode()
    newgid.sign()
    return newgid, keys

def create_user_credential(user_gid, issuer_keyfile, issuer_certfile):
    ucred = cred.Credential()
    ucred.set_gid_caller(user_gid)
    ucred.set_gid_object(user_gid)
    ucred.set_lifetime(3600)
    ucred.set_privileges("embed:1, bind:1")
    ucred.encode()
    ucred.set_issuer_keys(issuer_keyfile, issuer_certfile)
    ucred.sign()
    return ucred

def make_certs(dir):
    # Create the CA cert
    (ca_cert, ca_key) = create_cert('geni.net:gpo+authority+sa',)
    ca_cert.save_to_file(os.path.join(dir, CA_CERT_FILE))
    ca_key.save_to_file(os.path.join(dir, CA_KEY_FILE))
    # Make a cert for the clearinghouse
    (ch_gid, ch_keys) = create_cert('geni.net:gpo:gcf+authority+ch', ca_key, ca_cert, True)
    ch_gid.save_to_file(os.path.join(dir, CH_CERT_FILE))
    ch_keys.save_to_file(os.path.join(dir, CH_KEY_FILE))
    # Make a cert for the aggregate manager
    (am_gid, am_keys) = create_cert('geni.net:gpo:gcf+authority+am', ca_key, ca_cert, True)
    am_gid.save_to_file(os.path.join(dir, AM_CERT_FILE))
    am_keys.save_to_file(os.path.join(dir, AM_KEY_FILE))
    # Make a GID/Cert for Alice
    (alice_gid, alice_keys) = create_cert('geni.net:gpo:gcf+user+alice', ch_keys, ch_gid)
    alice_gid.save_to_file(os.path.join(dir, 'alice-cert.pem'))
    alice_keys.save_to_file(os.path.join(dir, 'alice-key.pem'))

# Make a Credential for Alice
#alice_cred = create_user_credential(alice_gid, CH_KEY_FILE, CH_CERT_FILE)
#alice_cred.save_to_file('../alice-user-cred.xml')

def parse_args(argv):
    parser = optparse.OptionParser()
    parser.add_option("-d", "--directory", default='.',
                      help="directory for created cert files", metavar="DIR")
    return parser.parse_args()

def main(argv=None):
    if argv is None:
        argv = sys.argv
    opts, args = parse_args(argv)
    if opts.directory:
        make_certs(opts.directory)
    else:
        exercise_am(opts.host, opts.port, opts.keyfile, opts.certfile)
    return 0

if __name__ == "__main__":
    sys.exit(main())
