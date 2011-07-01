#!/usr/bin/python

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
'''
Delegate a credential to another experimenter.
Takes a saved credential, the owner's certificate and key, and the certificate
to delegate to.
Allows you to control if the delegated credential is delegatable, and what
the expiration date is of the new credential.
TODO: Support partial privilege delegation.
If you supply trusted root certificates, validates the full PKI chain.
'''

# need a mode which simply prints the given cred's rights, marking
# which are delegatable
# and also a way to print the original cred's expiration time (so you know what is valid)

# need a way to specify which of the cred's rights to delegate, and
# which to mark delegatable
# Note that this is messy since PG slice creds just say * and PL slice creds

import datetime
import dateutil
import logging
import optparse
import os
import string
import sys
from xml.dom.minidom import Document, parseString

import sfa.trust.credential as cred
import sfa.trust.rights as privs
from sfa.trust.gid import GID
from sfa.trust.certificate import Keypair, Certificate

def configure_logging(opts):
    """Configure logging. INFO level by defult, DEBUG level if opts.debug"""
    level = logging.INFO
    logging.basicConfig(level=level)
    if opts.debug:
        level = logging.DEBUG
    logger = logging.getLogger("delegateSlice")
    logger.setLevel(level)
    return logger

def load_slice_cred(slicefilename):
    if slicefilename and os.path.exists(slicefilename) and os.path.isfile(slicefilename) and os.path.getsize(slicefilename) > 0:
        # read the slice cred from the given file
        logger.info("Getting slice credential from file %s", slicefilename)
        cred = None
        with open(slicefilename, 'r') as f:
            cred = f.read()
            return cred
    return None

def naiveUTC(dt):
    """Converts dt to a naive datetime in UTC.

    If 'dt' has a timezone then
    convert to UTC
    strip off timezone (make it "naive" in Python parlance)
    """
    if dt.tzinfo:
        tz_utc = dateutil.tz.tzutc()
        dt = dt.astimezone(tz_utc)
        dt = dt.replace(tzinfo=None)
    return dt

if __name__ == '__main__':
    parser = optparse.OptionParser()
    parser.add_option("--cert", action="store", default=None,
                      help="Filename of slice owner cert")
    parser.add_option("--key", action="store", default=None,
                      help="Filename of slice owner key")
    parser.add_option("--slicecred", action="store", default=None,
                      help="Filename of slice cred to delegate")
    parser.add_option("--delegatable", action="store_true", default=False,
                      help="Should rights in new cred be delegatable")
    parser.add_option("--delegeegid", action="store", type="string", default=None,
                      help="Filename of Cert to delegate to")
    parser.add_option("--debug", action="store_true", default=False)
    parser.add_option("--trusted-root", action="append", default=None, dest="trustedroot",
                      help="Filenames of trusted cert/cred signer certs. If supplied, verifies the credential.")
    parser.add_option("--newExpiration", action="store", default=None,
                      help="Expiration of new credential. Defaults to same as original.")
    # FIXME: Allow requesting new rights <= orig
    opts, args = parser.parse_args(sys.argv[1:])

    logger = configure_logging(opts)

    if not opts.cert:
        sys.exit("No user cert given")
    if not opts.key:
        sys.exit("No user key given")
    if not opts.slicecred:
        sys.exit("No slice to delegate given")
    if not opts.delegeegid:
        sys.exit("No user cert to delegate to given")

    slicecredstr = load_slice_cred(opts.slicecred)
    if slicecredstr is None:
        sys.exit("No slice credential found")

    # Handle user supplied a set of trusted roots to use to validate the creds/certs
    roots = None
    if opts.trustedroot:
        temp = opts.trustedroot
        for root in temp:
            if root is None or str(root).strip == "":
                continue
            if os.path.isdir(root):
                for file in os.listdir(root):
                    temp.append(os.path.join(root, file))
            elif os.path.isfile(root):
                if roots is None:
                    roots = []
                roots.append(os.path.expanduser(root))

    if (not (type(slicecredstr) is str and slicecredstr.startswith("<"))):
        sys.exit("Not a slice cred in file %s" % opts.slicecred)

    slicecred = cred.Credential(string=slicecredstr)

    newExpiration = None
    if opts.newExpiration:
        try:
            newExpiration = naiveUTC(dateutil.parser.parse(opts.newExpiration))
        except Exception, exc:
            sys.exit("Failed to parse desired new expiration %s: %s" % (opts.newExpiration, exc))

    # Confirm desired new expiration <= existing expiration
    slicecred_exp = naiveUTC(slicecred.get_expiration())
    if newExpiration is None:
        newExpiration = slicecred_exp
        logger.info("Delegated cred will expire at same time as original: %s UTC" % newExpiration)
    elif newExpiration > slicecred_exp:
        sys.exit('Cannot delegate credential until %s UTC past existing expirationn %s UTC' % (newExpiration, slicecred_exp))
    elif newExpiration <= datetime.datetime.utcnow():
        sys.exit('Cannot delegate credential until %s UTC - in the past' % (newExpiration))
    else:
        logger.info('Delegated cred will expire at %s UTC- sooner than original date of %s UTC' % (newExpiration, slicecred_exp))

    # get the owner's gid/key (person running this)
    owner_key = Keypair(filename=opts.key)
    owner_cert = GID(filename=opts.cert)

    # get the user (Delegatee)'s gid
    delegee_cert = GID(filename=opts.delegeegid)

    # confirm cert hasn't expired
    if owner_cert.cert.has_expired():
        sys.exit("Cred owner %s cert has expired at %s" % (owner_cert.cert.get_subject(), owner_cert.cert.get_expiration()))

    # confirm cert to delegate to hasn't expired
    if delegee_cert.cert.has_expired():
        sys.exit("Delegee %s cert has expired at %s" % (delegee_cert.cert.get_subject(), delegee_cert.cert.get_expiration()))

    try:
        # Note roots may be None if user supplied None, in which case we don't actually verify everything
        if not slicecred.verify(trusted_certs=roots, trusted_certs_required=False, schema=os.path.abspath("src/sfa/trust/credential.xsd")):
            sys.exit("Failed to validate credential")
    except Exception, exc:
        raise
#        sys.exit("Failed to validate credential: %s" % exc)

    # confirm cred says rights are delegatable
    if not slicecred.get_privileges().get_all_delegate():
        sys.exit("Slice says not all privileges are delegatable")

    # owned by user whose cert we got
    if not owner_cert.get_urn() == slicecred.get_gid_caller().get_urn():
        sys.exit("Can't delegate slice: not owner (mismatched URNs)")
    if not owner_cert.save_to_string(False) == slicecred.get_gid_caller().save_to_string(False):
        sys.exit("Can't delegate slice: not owner (mismatched GIDs)")

    object_gid = slicecred.get_gid_object()

    # OK, inputs are verified
    logger.info("Delegating %s's rights to %s to %s until %s UTC", owner_cert.get_urn(), object_gid.get_urn(), delegee_cert.get_urn(), newExpiration)
    logger.info("Original rights to delegate: %s" % slicecred.get_privileges().save_to_string())
    if opts.delegatable:
        logger.info("New credential will be delegatable")

    # Now construct and sign the delegated credential
    object_hrn = object_gid.get_hrn()
    delegee_hrn = delegee_cert.get_hrn()
    subject_string = "%s delegated to %s" % (object_hrn, delegee_hrn)
    dcred = cred.Credential(subject=subject_string)
    dcred.set_gid_caller(delegee_cert)
    dcred.set_gid_object(object_gid)
    dcred.set_parent(slicecred)
    dcred.set_expiration(newExpiration)

    # FIXME: permit partial rights delegation
    dcred.set_privileges(slicecred.get_privileges())
    dcred.get_privileges().delegate_all_privileges(opts.delegatable)

    dcred.set_issuer_keys(opts.key, opts.cert)
    dcred.encode()
    dcred.sign()

    # Verify the result is still good
    try:
        # Note roots may be None if user supplied None, in which case we don't actually verify everything
        if not dcred.verify(trusted_certs=roots, trusted_certs_required=False, schema=os.path.abspath("src/sfa/trust/credential.xsd")):
            sys.exit("Failed to validate credential")
    except Exception, exc:
        raise
#        sys.exit("Failed to validate credential: %s" % exc)

#    logger.info( 'Generated delegated credential')
    if opts.debug:
        dcred.dump(True)
    else:
        logger.info("Created delegated credential %s", dcred)

    # Save the result to a file
    bad = u'!"#%\'()*+,-./:;<=>?@[\]^_`{|}~'
    if isinstance(delegee_hrn, unicode):
        table = dict((ord(char), unicode('-')) for char in bad)
    else:
        assert isinstance(delegee_hrn, str)
        table = string.maketrans(bad, '-' * len(bad))

    newname = delegee_hrn.translate(table) + "-delegated-" + opts.slicecred
    dcred.save_to_file(newname)

    logger.info("Saved delegated slice cred to %s" % newname)
