#!/usr/bin/env python

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

"""
Create some basic x509 identity certificates and keys.

Certificates and keys are created for two authorities:
a clearinghouse and an aggregate manager.
Finally, a user cert and
key is created for a user (named Alice by default). Options allow
controlling which certs are created.
This file shows how to constructe GAPI compliant certificates.
See sfa.trust.certificate for the class definition and
geni.util.cert_util for the utility create_cert function.
"""

import sys

# Check python version. Requires 2.6 or greater, but less than 3.
if sys.version_info < (2, 6):
    raise Exception('Must use python 2.6 or greater.')
elif sys.version_info >= (3,):
    raise Exception('Not python 3 ready')

import logging
import optparse
import os.path
import string
import uuid

import gcf.geni as geni
import gcf.sfa.trust.gid as gid
import gcf.sfa.trust.certificate as cert
from gcf.geni.util.cert_util import create_cert
from gcf.geni.util.urn_util import is_valid_urn_bytype
from gcf.geni.config import read_config

# Default paths to files. Overridden by values in gcf_config
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
# See sfa/util/xrn.py eg
# Only authorities can sign credentials.
AUTHORITY_CERT_TYPE = 'authority'
CH_CERT_SUBJ = 'sa' 
AM_CERT_SUBJ = 'am'

def getAbsPath(path):
    """Return None or a normalized absolute path version of the argument string.
    Does not check that the path exists."""
    if path is None:
        return None
    if path.strip() == "":
        return None
    path = os.path.normcase(os.path.expanduser(path))
    if os.path.isabs(path):
        return path
    else:
        return os.path.abspath(path)

def make_ch_cert(dir, uuidArg=uuid.uuid4()):
    '''Make a self-signed cert for the clearinghouse saved to 
    given directory and returned.'''
    # Create a cert with urn like geni.net:gpo:gcf+authority+sa
    urn = geni.URN(CERT_AUTHORITY, AUTHORITY_CERT_TYPE, CH_CERT_SUBJ).urn_string()
    
    if not uuidArg:
        uuidArg = uuid.uuid4()

    # add lifeDays arg to change # of days cert lasts
    (ch_gid, ch_keys) = create_cert(urn, ca=True, uuidarg=uuidArg)
    ch_gid.save_to_file(os.path.join(dir, CH_CERT_FILE))
    ch_keys.save_to_file(os.path.join(dir, CH_KEY_FILE))

    # Create the rootcadir / trusted_roots dir if necessary
    rootcapath = getAbsPath(config['global']['rootcadir'])
    if rootcapath is not None:
        if not os.path.exists(rootcapath):
            # Throws an exception on error
            os.makedirs(rootcapath)
        # copy the CH cert to the trusted_roots dir'
        if '/' in CH_CERT_FILE:
            fname = CH_CERT_FILE[CH_CERT_FILE.rfind('/')+1:]
        else:
            fname = CH_CERT_FILE
        
        ch_gid.save_to_file(os.path.join(getAbsPath(config['global']['rootcadir']), fname))

    print "Created CH cert/keys in %s/%s, %s, and in %s" % (dir, CH_CERT_FILE, CH_KEY_FILE, 
                                                         getAbsPath(config['global']['rootcadir']) + "/" + fname)
    return (ch_keys, ch_gid)

def make_am_cert(dir, ch_cert, ch_key, uuidArg=uuid.uuid4()):
    '''Make a cert for the aggregate manager signed by given CH cert/key
    and saved in given dir. NOT RETURNED.
    AM publicid will be from gcf_config base_name//am-name'''
    # Create a cert with urn like geni.net:gpo:gcf:am1+authority+am
    auth_name = CERT_AUTHORITY + "//" + config['aggregate_manager']['name']
    urn = geni.URN(auth_name, AUTHORITY_CERT_TYPE, AM_CERT_SUBJ).urn_string()

    if not uuidArg:
        uuidArg = uuid.uuid4()

    # add lifeDays arg to change # of days cert lasts
    (am_gid, am_keys) = create_cert(urn, ch_key, ch_cert, ca=True, uuidarg=uuidArg)
    am_gid.save_to_file(os.path.join(dir, AM_CERT_FILE))
    am_keys.save_to_file(os.path.join(dir, AM_KEY_FILE))
    print "Created AM cert/keys in %s/%s and %s" % (dir, AM_CERT_FILE, AM_KEY_FILE)

def make_user_cert(dir, username, ch_keys, ch_gid, public_key=None, email=None, uuidArg=uuid.uuid4()):
    '''Make a GID/Cert for given username signed by given CH GID/keys, 
    saved in given directory. Not returned.'''
    # Create a cert like PREFIX+TYPE+name
    # ie geni.net:gpo:gcf+user+alice
    urn = geni.URN(CERT_AUTHORITY, USER_CERT_TYPE, username).urn_string()
    logging.basicConfig(level=logging.INFO)
    if not is_valid_urn_bytype(urn, 'user', logging.getLogger("gen-certs")):
        sys.exit("Username %s invalid" % username)

    if not uuidArg:
        uuidArg = uuid.uuid4()

    # add lifeDays arg to change # of days cert lasts
    (alice_gid, alice_keys) = create_cert(urn, issuer_key=ch_keys,
                                          issuer_cert=ch_gid,
                                          ca=False,
                                          public_key=public_key,
                                          email=email,
                                          uuidarg=uuidArg)
    alice_gid.save_to_file(os.path.join(dir, USER_CERT_FILE))
    if public_key is None:
        alice_keys.save_to_file(os.path.join(dir, USER_KEY_FILE))
    
# Make a Credential for Alice
#alice_cred = create_user_credential(alice_gid, CH_KEY_FILE, CH_CERT_FILE)
#alice_cred.save_to_file('../alice-user-cred.xml')
    print "Created Experimenter %s certificate in %s" % (username, os.path.join(dir, USER_CERT_FILE))
    if public_key is None:
        print "Created Experimenter %s key in %s" % (username, os.path.join(dir, USER_KEY_FILE))

def parse_args(argv):
    parser = optparse.OptionParser()
    parser.add_option("-d", "--directory", default='.',
                      help="directory for created cert files", metavar="DIR")
    parser.add_option("-c", "--configfile",  help="config file path", metavar="FILE")
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
    parser.add_option("--email", default=None,
                      help="Set experimenter email")
    parser.add_option("--uuid", default=None,
                      help="Set experimenter uuid to this value")
    parser.add_option("--pubkey", help="public key", default=None)
    parser.add_option("--authority", default=None, help="The Authority of the URN in publicid format (such as 'geni.net//gpo//gcf'). Overrides base_name from gcf_config file.")
    return parser.parse_args()

def main(argv=None):
    if argv is None:
        argv = sys.argv
    (opts, args) = parse_args(argv)
    # Ignore args, appease eclipse.
    _ = args
    global config, CERT_AUTHORITY
    optspath = None
    if not opts.configfile is None:
        optspath = os.path.expanduser(opts.configfile)

    config = read_config(optspath)  
    CERT_AUTHORITY=config['global']['base_name']
    username = "alice"
    if opts.username:
        # We'll check this is legal once we have a full URN
        username = opts.username
    dir = "."
    if opts.directory:
        dir = opts.directory

    if not opts.authority is None:
        # FIXME: Check it's legal? Should be 'an internationalized
        # domain name'
        CERT_AUTHORITY = opts.authority
        
    global CH_CERT_FILE, CH_KEY_FILE, AM_CERT_FILE, AM_KEY_FILE, USER_CERT_FILE, USER_KEY_FILE
    CH_CERT_FILE = getAbsPath(config['clearinghouse']['certfile'])
    CH_KEY_FILE = getAbsPath(config['clearinghouse']['keyfile'])
    AM_CERT_FILE = getAbsPath(config['aggregate_manager']['certfile'])
    AM_KEY_FILE =getAbsPath(config['aggregate_manager']['keyfile'])
    USER_CERT_FILE = getAbsPath(config['gcf-test']['certfile'])
    USER_KEY_FILE = getAbsPath(config['gcf-test']['keyfile'])

    # If username != alice then substitute actual username
    # in user_cert_file and user_key_file as appropriate 
    # like USER_CERT_FILE = s/alice/$username/
    # Of course if the user edits the file to have something
    # other than alice in the filename then this does something odd
    if username != 'alice':
        USER_CERT_FILE = string.replace(USER_CERT_FILE, 'alice', username)
        USER_KEY_FILE = string.replace(USER_KEY_FILE, 'alice', username)
    
    try:
        for p in [CH_CERT_FILE, CH_KEY_FILE, AM_CERT_FILE, AM_KEY_FILE, USER_CERT_FILE, USER_KEY_FILE]:
            if '/' in p:
                os.mkdir(p[:p.rfind('/')])
    except:
        pass
    
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
        make_user_cert(dir, username, ch_keys, ch_cert,
                       public_key=opts.pubkey,
                       email=opts.email,
                       uuidArg=opts.uuid)

    return 0

if __name__ == "__main__":
    sys.exit(main())
