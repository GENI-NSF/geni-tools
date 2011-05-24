#!/usr/bin/env python

import sys
import ConfigParser
from geni.util.urn_util import URN
import geni.util.cert_util as cert_util
import geni.util.cred_util as cred_util
import sfa

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
