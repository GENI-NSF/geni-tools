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

# FIXME
# May need to re download PG and PL certs. PG cert may have expired. PL cert
# may have been regenerated and the new one on your slice cred
# To redownload PL do a getversion at PL after deleting your cert file
# Once you delegate
# If using Omni, to get Omni to infer the slice URN correctly, you must tell
# Omni you are using the framework/SA of the original slice cred. So copy
# the cert/key entries from the new slice cred owner to the original framework,
# and be sure to include -a in all Omni commands

import datetime
import dateutil
import json
import logging
import optparse
import os
import string
import sys

import gcf.sfa.trust.credential as cred
import gcf.sfa.trust.rights as privs
from gcf.sfa.trust.gid import GID
from gcf.sfa.trust.certificate import Keypair, Certificate
import gcf.omnilib.util.credparsing as credutils
import gcf.omnilib.util.json_encoding as json_encoding
from gcf.geni.util.tz_util import tzd

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

        try:
            cred = json.loads(cred, encoding='ascii', cls=json_encoding.DateTimeAwareJSONDecoder)
        except Exception, e:
            logger.debug("Failed to get a JSON struct from cred in file %s. Treat as a string.", slicefilename)
            logger.debug(e)
            #handler.logger.debug(e)

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
    usage = "\nDelegate a saved slice credential to another user.\n\
EG Use Omni to save a slice credential, get your co-worker's user cert\n\
via email, and then delegate your slice credential to them so they can\n\
help on your experiment.\n\
The omni command to save the slicecred would be something like:\n\
omni.py --slicecred mySliceCred.xml -o getslicecred mySliceName\n\
\n%prog \n\
\t--cert <filename of your cert, eg ~/.gcf/plc-jdoe-cert.pem>\n\
\t--key <filename of your key, eg ~/.gcf/plc-jdoe-key.pem>\n\
\t--slicecred <filename of saved slice credential to delegate,\n\
\t\teg mySliceCred.xml>\n\
\t--delegeegid <filename of co-workers cert you want to delegate to>\n\
\t--trusted-root <filename of a trusted root certificate, eg that for\n\
\t\tplc of pg-utah>\n\
\t\tOptional. Supply this argument 1 or more times to\n\
\t\tinclude the certificates for your Slice Authority\n\
\t\tand Clearinghouse/Registry, and the script will\n\
\t\tattempt to validate the credential you have generated\n\
\t[--delegatable -- an optional argument that makes the new credential\n\
\t\tdelegatable too, so your friend could re-delegate\n\
\t\tthis credential]\n\
\t[--newExpiration <datetime string> Option argument to set a new\n\
\t\texpiration time shorter than the original, for the\n\
\t\tnew credential]."

    parser = optparse.OptionParser(usage=usage)
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
        sys.exit("No user cert given: use --cert option")
    elif not (os.path.exists(opts.cert) and os.path.isfile(opts.cert) and os.path.getsize(opts.cert) > 0):
        sys.exit("User cert file (--cert option) %s missing or empty" % opts.cert)
    if not opts.key:
        sys.exit("No user key given: use --key option")
    elif not (os.path.exists(opts.key) and os.path.isfile(opts.key) and os.path.getsize(opts.key) > 0):
        sys.exit("User key file (--key option)  %s missing or empty" % opts.key)
    if not opts.slicecred:
        sys.exit("No slice to delegate given: use --slicecred option")
    if not opts.delegeegid:
        sys.exit("No user cert to delegate to given: use --delegeegid option")
    elif not (os.path.exists(opts.delegeegid) and os.path.isfile(opts.delegeegid) and os.path.getsize(opts.delegeegid) > 0):
        sys.exit("User cert file to delegate to (--delegee gid option) %s missing or empty" % opts.delegeegid)

    slicecredstr = load_slice_cred(opts.slicecred)
    if slicecredstr is None:
        sys.exit("No slice credential found (missing or empty): %s" % opts.slicecred)

    # Handle user supplied a set of trusted roots to use to validate the creds/certs
    roots = None
    root_objects = []
    if opts.trustedroot:
        temp = opts.trustedroot
        for root in temp:
            if root is None or str(root).strip == "":
                continue
            if os.path.isdir(root):
                for file in os.listdir(root):
                    temp.append(os.path.join(root, file))
            elif os.path.isfile(root) and os.path.getsize(root) > 0:
                if roots is None:
                    roots = []
                roots.append(os.path.expanduser(root))

        for f in roots:
            try:
                # Failures here include unreadable files
                # or non PEM files
                root_objects.append(GID(filename=f))
            except Exception, exc:
                logger.error("Failed to load trusted cert from %s: %r", f, exc)

    writeStruct = False
    if isinstance(slicecredstr, dict):
        writeStruct = True
        slicecredstr = credutils.get_cred_xml(slicecredstr)

    if (not (type(slicecredstr) is str and slicecredstr.startswith("<"))):
        sys.exit("Not a slice cred in file %s - cannot delegate" % opts.slicecred)

    slicecred = cred.Credential(string=slicecredstr)

    newExpiration = None
    if opts.newExpiration:
        try:
            newExpiration = naiveUTC(dateutil.parser.parse(opts.newExpiration, tzinfos=tzd))
        except Exception, exc:
            sys.exit("Failed to parse desired new expiration %s - cannot delegate: %s" % (opts.newExpiration, exc))

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
        sys.exit("Cred owner %s cert has expired at %s - cannot delegate" % (owner_cert.cert.get_subject(), owner_cert.cert.get_notAfter()))

    # confirm cert to delegate to hasn't expired
    if delegee_cert.cert.has_expired():
        sys.exit("Delegee %s cert has expired at %s - cannot delegate" % (delegee_cert.cert.get_subject(), delegee_cert.cert.get_notAfter()))

    if len(root_objects) > 0:
        try:
            owner_cert.verify_chain(trusted_certs=root_objects)
        except Exception, exc:
            logger.warn("Owner cert did not validate - cannot delegate: %s", exc)
            raise

    try:
        # Note roots may be None if user supplied None, in which case we don't actually verify everything
        if not slicecred.verify(trusted_certs=roots, trusted_certs_required=False, schema=os.path.abspath("src/gcf/sfa/trust/credential.xsd")):
            sys.exit("Failed to validate credential - cannot delegate")
    except Exception, exc:
        logger.warn("Supplied slice cred didn't verify - cannot delegate")
        raise
#        sys.exit("Failed to validate credential: %s" % exc)

    # confirm cred says rights are delegatable
    if not slicecred.get_privileges().get_all_delegate():
        sys.exit("Slice says not all privileges are delegatable - cannot delegate.")

    # owned by user whose cert we got
    if not owner_cert.get_urn() == slicecred.get_gid_caller().get_urn():
        sys.exit("Can't delegate slice: certificate from '--cert' option is for %s but the slice credential is owned by %s." % (owner_cert.get_urn(), slicecred.get_gid_caller().get_urn()))
    if not owner_cert.save_to_string(False) == slicecred.get_gid_caller().save_to_string(False):
        sys.exit("Can't delegate slice: not owner (mismatched GIDs but same URN - try downloading your cert again)")

    object_gid = slicecred.get_gid_object()

    if len(root_objects) > 0:
        try:
            delegee_cert.verify_chain(trusted_certs=root_objects)
        except Exception, exc:
            logger.warn("Delegee cert did not validate - cannot delegate: %s", exc)
            raise

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
        if not dcred.verify(trusted_certs=roots, trusted_certs_required=False, schema=os.path.abspath("src/gcf/sfa/trust/credential.xsd")):
            sys.exit("Failed to validate delegated credential - not saving")
    except Exception, exc:
        logger.warn("Delegated slice cred does not verify - not saving")
        raise
#        sys.exit("Failed to validate credential: %s" % exc)

#    logger.info( 'Generated delegated credential')
    if opts.debug:
        dcred.dump(True)
    else:
        logger.info("Created delegated credential %s", dcred.get_summary_tostring())

    # Save the result to a file
    bad = u'!"#%\'()*+,-./:;<=>?@[\]^_`{|}~'
    if isinstance(delegee_hrn, unicode):
        table = dict((ord(char), unicode('-')) for char in bad)
    else:
        assert isinstance(delegee_hrn, str)
        table = string.maketrans(bad, '-' * len(bad))

    # splice slicecred into filename and dir
    path = os.path.dirname(opts.slicecred)
    filename = os.path.basename(opts.slicecred)

    newname = os.path.join(path, delegee_hrn.translate(table) + "-delegated-" + filename)
    if not writeStruct:
        dcred.save_to_file(newname)
    else:
        dcredstr = dcred.save_to_string()
        dcredStruct = dict(geni_type=cred.Credential.SFA_CREDENTIAL_TYPE, 
                           geni_version="3", geni_value=dcredstr)
        credout = json.dumps(dcredStruct, cls=json_encoding.DateTimeAwareJSONEncoder)
        with open(newname, 'w') as file:
            file.write(credout + "\n")

    logger.info("\n\nSaved delegated slice cred to:\n\t %s" % newname)
    logger.info("To use this with omni, be sure to supply '--slicecred %s'" % (newname))
    logger.info("And if you delegated a slice from 1 slice authority to a user in another, you must specify the full slice URN of '%s'" % (object_gid.get_urn()))
    logger.info("EG if you delegated a ProtoGENI slice to a PlanetLab user account and want to list resources:\n\t python src/omni.py -a http://www.some-PLC-affiliated-AM.org:12346 --slicecred %s --api-version 2 -t GENI 3 -o listresources %s" % (newname, object_gid.get_urn()))
