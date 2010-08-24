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

"""
Create a certificate authority and some basic certs and keys.

Certificates and keys are created for two authorities:
a clearinghouse and an intermediate CA - an aggregate manager. 
Finally, a user cert and
key is created for a user (named Alice by default). Options allow
controlling which certs are created.
This file shows how to constructe GAPI compliant certificates.
See sfa.trust.certificate for the class definition.
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
import sfa.util.namespace
from geni.config import read_config

CH_CERT_FILE = 'ch-cert.pem'
CH_KEY_FILE = 'ch-key.pem'
AM_CERT_FILE = 'am-cert.pem'
AM_KEY_FILE = 'am-key.pem'
USER_KEY_FILE = 'alice-key.pem'
USER_CERT_FILE = 'alice-cert.pem'

config = None

# URN prefix for the CH(SA)/AM/Experimenter certificates
# Be sure that URNs are globally unique to support peering.
# Slice names must be <CERT_PREFIX>+slice+<your slice name>
# Note this is in publicid format and will be converted to 
# URN format for encoding in certificates. EG
# ' ' -> '+'
# '//' -> ':'
# This value is configured in gcf_config and
# authority commandline arg over-rides this value
CERT_AUTHORITY = None # configured in gcf_config

# For the subject of user/experiments certs, eg gcf+user+<username>
# cert types match constants in sfa/trust/rights.py
# for, among other things, determining privileges
USER_CERT_TYPE = 'user'

# For CHs and AMs. EG gcf+authority+am
# See sfa/util/namespace.py eg
# Only authorities can sign credentials.
AUTHORITY_CERT_TYPE = 'authority'
CH_CERT_SUBJ = 'sa' 
AM_CERT_SUBJ = 'am'

# Prefix is like geni.net:gpo
# type is authority or user
# subj is am or sa, or the username
def create_cert(prefix, type, subj, issuer_key=None, issuer_cert=None, intermediate=False):
    '''Create a new certificate and return it and the associated keys.
    If issure cert and key are given, they sign the certificate. Otherwise
    it is a self-signed certificate. If intermediate then mark this 
    as an intermediate CA certiciate (can sign).
    Subject of the cert is prefix+type+subj
    Note that prefix, type and subject are in publicid format and
    will be converted to URN format.
    '''
    
    # Validate each of prefix, type, subj per rules
    # in credential.py
    if prefix is None or prefix.strip() == '':
        raise ValueError("Missing cert subject prefix")
    if type is None or type.strip() == '':
        raise ValueError("Missing cert subject type")
    if subj is None or subj.strip() == '':
        raise ValueError("Missing cert subject subj")
    prefix = geni.string_to_urn_format(prefix)
    type = geni.string_to_urn_format(type)
    subj = geni.string_to_urn_format(subj)

    # FIXME: Could use credential.publicid_to_urn...
    subject = "%s+%s+%s" % (prefix, type, subj)
    urn = '%s+%s' % (sfa.util.namespace.URN_PREFIX, subject)

    newgid = gid.GID(create=True, subject=subject,
                     urn=urn)
    keys = cert.Keypair(create=True)
    newgid.set_pubkey(keys)
    if intermediate:
        newgid.set_intermediate_ca(intermediate)
        
    if issuer_key and issuer_cert:
        newgid.set_issuer(issuer_key, cert=issuer_cert)
        newgid.set_parent(issuer_cert)
    else:
        # create a self-signed cert
        newgid.set_issuer(keys, subject=subject)

    newgid.encode()
    newgid.sign()
    return newgid, keys

def make_ch_cert(dir):
    '''Make a self-signed cert for the clearinghouse saved to 
    given directory and returned.'''
    # Create a cert with urn like geni.net:gpo:gcf+authority+sa
    (ch_gid, ch_keys) = create_cert(CERT_AUTHORITY, AUTHORITY_CERT_TYPE,CH_CERT_SUBJ)
    ch_gid.save_to_file(os.path.join(dir, CH_CERT_FILE))
    ch_keys.save_to_file(os.path.join(dir, CH_KEY_FILE))
    os.popen('mkdir %s' % (os.path.join(dir, 'trusted_roots')))
    ch_gid.save_to_file(os.path.join(config['global']['rootcadir'], CH_CERT_FILE))
    print "Created CH cert/keys in %s/%s, %s, and %s" % (dir, CH_CERT_FILE, CH_KEY_FILE, 
                                                         dir + "/trusted_roots/" + CH_CERT_FILE)
    return (ch_keys, ch_gid)

def make_am_cert(dir, ch_cert, ch_key):
    '''Make a cert for the aggregate manager signed by given CH cert/key
    and saved in given dir. NOT RETURNED.'''
    # Create a cert with urn like geni.net:gpo:gcf+authority+am
    auth_name = CERT_AUTHORITY + "//" + config['aggregate_manager']['name']
    (am_gid, am_keys) = create_cert(auth_name, AUTHORITY_CERT_TYPE,AM_CERT_SUBJ, ch_key, ch_cert, True)
    am_gid.save_to_file(os.path.join(dir, AM_CERT_FILE))
    am_keys.save_to_file(os.path.join(dir, AM_KEY_FILE))
    print "Created AM cert/keys in %s/%s and %s" % (dir, AM_CERT_FILE, AM_KEY_FILE)

def make_user_cert(dir, username, ch_keys, ch_gid):
    '''Make a GID/Cert for given username signed by given CH GID/keys, 
    saved in given directory. Not returned.'''
    # Create a cert like PREFIX+TYPE+name
    # ie geni.net:gpo:gcf+user+alice
    (alice_gid, alice_keys) = create_cert(CERT_AUTHORITY, USER_CERT_TYPE, username, ch_keys, ch_gid)
    alice_gid.save_to_file(os.path.join(dir, USER_CERT_FILE))
    alice_keys.save_to_file(os.path.join(dir, USER_KEY_FILE))
    
# Make a Credential for Alice
#alice_cred = create_user_credential(alice_gid, CH_KEY_FILE, CH_CERT_FILE)
#alice_cred.save_to_file('../alice-user-cred.xml')
    print "Created Experimenter %s cert/keys in %s" % (username, dir)

def parse_args(argv):
    parser = optparse.OptionParser()
    parser.add_option("-d", "--directory", default='.',
                      help="directory for created cert files", metavar="DIR")
    parser.add_option("-f", "--configfile", default="gcf_config", help="config file path", metavar="FILE")
    parser.add_option("-u", "--username", default='alice',
                      help="Experimenter username")
    parser.add_option("--notAll", action="store_true", default=False,
                      help="Do NOT create all cert/keys: Supply other options to generate particular certs.")
    parser.add_option("--ch", action="store_true", default=False,
                      help="Create CH (SA) cert/keys")
    parser.add_option("--am", action="store_true", default=False,
                      help="Create AM cert/keys")
    parser.add_option("--exp", action="store_true", default=False,
                      help="Create experimenter cert/keys")
    parser.add_option("--authority", default=None, help="The Authority of the URN in publicid format (such as 'geni.net//gpo//gcf')")
    return parser.parse_args()

def main(argv=None):
    if argv is None:
        argv = sys.argv
    opts, args = parse_args(argv)
    global config, CERT_AUTHORITY
    configpath = os.path.expanduser(opts.configfile)
    config = read_config(configpath)  
    CERT_AUTHORITY=config['global']['base_name']
    username = "alice"
    if opts.username:
        username = opts.username
    dir = "."
    if opts.directory:
        dir = opts.directory

    if not opts.authority is None:
        CERT_AUTHORITY = opts.authority
        
    global CH_CERT_FILE, CH_KEY_FILE, AM_CERT_FILE, AM_KEY_FILE, USER_CERT_FILE, USER_KEY_FILE
    CH_CERT_FILE = config['clearinghouse']['certfile']
    CH_KEY_FILE = config['clearinghouse']['keyfile']
    AM_CERT_FILE = config['aggregate_manager']['certfile']
    AM_KEY_FILE = config['aggregate_manager']['keyfile']
    USER_CERT_FILE = config['client']['certfile']
    USER_KEY_FILE = config['client']['keyfile']

    ch_keys = None
    ch_cert = None
    if not opts.notAll or opts.ch:
        (ch_keys, ch_cert) = make_ch_cert(dir)
    else:
        if not opts.notAll or opts.exp:
            try:
                ch_cert = gid.GID(filename=os.path.join(dir,CH_CERT_FILE))
                ch_keys = cert.Keypair(filename=os.path.join(dir,CH_KEY_FILE))
            except Exception, exc:
                sys.exit("Failed to read CH(SA) cert/key from %s/%s and %s: %s" % (dir, CH_CERT_FILE, CH_KEY_FILE, exc))

    if not opts.notAll or opts.am:
        make_am_cert(dir, ch_cert, ch_keys)

    if not opts.notAll or opts.exp:
        make_user_cert(dir, username, ch_keys, ch_cert)

    return 0

if __name__ == "__main__":
    sys.exit(main())
