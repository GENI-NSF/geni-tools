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

# delegate a slice credential
# get the owner's gid/key (person running this
# get the user (Delegatee)'s gid
# load the slice cred to delegate (local or remote)
# check that the cred to delegate is owned by subject of the given gid
# check that the owner gid matches the given key
# check that have a good gid to delegate to

# by default I think give same rights as were there, but without delegate? 
# Make delegate an option?

# need a mode which simply prints the given cred's rights, marking
# which are delegatable 
# and also a way to print the cred expiration time

# need a way to specify which of the cred's rights to delegate, and
# which to mark delegatable
# Note that this is messy since PG slice creds just say * and PL slice creds


# error check that desired expiration time <= original
# error check that desired rights are subset of original rights and
# that each desired right is marked delegatable on orig
 
# FIXME: Must the delegee's cert be signed by same as me? or can it be anyone?
import sfa.trust.credential as cred
import sfa.trust.rights as privs
from sfa.trust.gid import GID
from sfa.trust.certificate import Keypair, Certificate
import optparse
import logging
import os
import string
import sys

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
    # FIXME: Allow requesting new expiration time <= orig,
    # and new rights <= orig
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

    if (not (type(slicecredstr) is str and slicecredstr.startswith("<"))):
        sys.exit("Not a slice cred in file %s" % opts.slicecred)

    slicecred = cred.Credential(string=slicecredstr)

# get the owner's gid/key (person running this
    owner_key = Keypair(filename=opts.key)
    owner_cert = GID(filename=opts.cert)
# get the user (Delegatee)'s gid
    delegee_cert = GID(filename=opts.delegeegid)

    # confirm cert/key of owner are a pair, haven't expired
    # confirm cert to delegate to hasn't expired
    # Must cert to delegate to by issued by same entity? I think not


    # validate the slice cred further?
    # valid
    # delegatable
    # owned by user whose cert we got
    if not owner_cert.get_urn() == slicecred.get_gid_caller().get_urn():
        sys.exit("Can't delegate slice: not owner (mismatched URNs)")
    if not owner_cert.save_to_string(False) == slicecred.get_gid_caller().save_to_string(False):
        sys.exit("Can't delegate slice: not owner (mismiatched GIDs)")


    object_gid = slicecred.get_gid_object()
    object_hrn = object_gid.get_hrn()        
    delegee_hrn = delegee_cert.get_hrn()
    
    #user_key = Keypair(filename=keyfile)
    #user_hrn = self.get_gid_caller().get_hrn()
    subject_string = "%s delegated to %s" % (object_hrn, delegee_hrn)
    dcred = cred.Credential(subject=subject_string)
    dcred.set_gid_caller(delegee_cert)
    dcred.set_gid_object(object_gid)
    dcred.set_parent(slicecred)
    dcred.set_expiration(slicecred.get_expiration())
    dcred.set_privileges(slicecred.get_privileges())
    dcred.get_privileges().delegate_all_privileges(opts.delegatable)
    #dcred.set_issuer_keys(keyfile, delegee_gidfile)
    dcred.set_issuer_keys(opts.key, opts.cert)
    dcred.encode()
    dcred.sign()

    if opts.debug:
        dcred.dump(True)

    bad = u'!"#%\'()*+,-./:;<=>?@[\]^_`{|}~'
    if isinstance(delegee_hrn, unicode):
        table = dict((ord(char), unicode('-')) for char in bad)
    else:
        assert isinstance(delegee_hrn, str)
        table = string.maketrans(bad, '-' * len(bad))
    
    newname = delegee_hrn.translate(table) + "-delegated-" + opts.slicecred
    dcred.save_to_file(newname)
    logger.info("Saved delegated slice cred to %s" % newname)
    print dcred
