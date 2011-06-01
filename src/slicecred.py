#!/usr/bin/env python

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

"""Script to generate a slice credential. For use by the
portal.

"""

import sys
import ConfigParser
from geni.util.urn_util import URN
import geni.util.cert_util as cert_util
import geni.util.cred_util as cred_util
import sfa.trust

def main(argv=None):
    if argv is None:
        argv = sys.argv
    configFile = argv[1]
    sliceName = argv[2]
    keyfile = argv[3]
    certfile = argv[4]
    user_cert_file = argv[5]
    outFileName = argv[6]

    confparser = ConfigParser.RawConfigParser()
    foundFile = confparser.read(configFile)
    if not foundFile:
        print "Unable to read file %s" % (configFile)
        return 2
    authority = confparser.get('global', 'base_name')
    print "%r" % (authority)

    urn = URN(authority, "slice", sliceName).urn_string()
    print "URN = %s" % (urn)

    (slice_cert, slice_keypair) = cert_util.create_cert(urn, keyfile, certfile)
    print "slice_cert = %r; slice_keypair = %r" % (slice_cert, slice_keypair)
    slice_cert.save_to_file("%s.pem" % (sliceName))

    user_cert = sfa.trust.gid.GID()
    user_cert.load_from_file(user_cert_file)
    print "user_cert = %r" % (user_cert)

    # 30 days
    life_secs = 60 * 60 * 24 * 30

    trust_roots = cred_util.CredentialVerifier(certfile).root_cert_files
    print "trust_roots = %r" % (trust_roots)
    print "trust_roots2 = %r" % ([certfile])

    slice_cred = cred_util.create_credential(user_cert, slice_cert, life_secs,
                                             'slice', keyfile, certfile,
                                             #trust_roots)
                                             [certfile])
    print "slice_cred = %r" % (slice_cred)
    slice_cred.save_to_file(outFileName)
    print "credential saved to = %r" % (outFileName)

    return 0

def x_create_credential(caller_gid, object_gid, life_secs, typename,
                      issuer_keyfile, issuer_certfile, trusted_roots):
    pass

if __name__ == "__main__":
    sys.exit(main())
