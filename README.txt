
Description
===========

This software implements a sample GENI Aggregate Manager. It also
includes a sample GENI Clearinghouse and command line client. This
software is intended to demonstrate the GENI Aggregate Manager API.


Software Dependencies
=====================

The GCF package is intended to be run on a modern Linux distribution
(circa 2010 or 2009). Python 2.6 is required. This software is not
Python 3 compatible.

This software requires a number of readily available software
packages. Most modern Linux distributions should have these packages
available via their native package management suite (eg. yum or apt).

1. Python M2Crypto package

  The M2Crypto package provides utilities for handling X.509
  certificates and SSL connections. M2Crypto is required by the
  certificate class in sfa/trust. M2Crypto should be readily available
  on most Linux distributions.

  More information is available at:
    http://chandlerproject.org/bin/view/Projects/MeTooCrypto

2. Python dateutil package

  The dateutil package provides date parsing routines to Python. It
  should be readily available on most Linux distributions.

  More information is available at:
    http://labix.org/python-dateutil

3. Python OpenSSL package

  The OpenSSL package provides a python API to the OpenSSL
  package. There is an implicit dependency on OpenSSL, but that
  should be handled by the Linux package manager (yum, apt, etc.)

  More information is available at:
    https://launchpad.net/pyopenssl

4. xmlsec1 package

  The XML Security Library provides implementations of XML Digital
  Signatures (RFC 3275) and W3C XML Encryption. The program xmlsec1
  from this package is used to sign credentials.  

  More information is available at:
    http://www.aleksey.com/xmlsec/
    http://www.w3.org/TR/xmlenc-core/
    http://www.ietf.org/rfc/rfc3275.txt


Included Software
=================

This package includes software from PlanetLab. All of the PlanetLab
software is in the src/sfa directory. More information, including the
license, can be found in src/sfa/README.txt.


Instructions
============

1. Initialize the certificate authority and generate keys and certificates:

 $ src/init-ca.py

 This creates a certificate authority key and certificate and then
 creates keys and certificates for a clearinghouse (ch), an aggregate
 manager (am), and a researcher (alice).
 The directory for the output, the researcher name, and which keys to
 generate are configurable via commandline options. Cert URNs and
 some privileges are modifiable via constants.
 Note you can generate multiple AM credentials and multiple user
 credentials using this script.

Optional: Create a directory containing all known and trusted (federated)
clearinghouse and certificate authority certificates (see below for an 
explanation).

2. Start the clearinghouse server:

 $ src/gch.py -r <ca-cert.pem or trusted_chs_and_cas_dir/> \
   	      -c ch-cert.pem -k ch-key.pem -u alice-cert.pem

 Note the requirement to supply (-u arg) a user credential (a test CH
 artifact). If the trusted certificates directory doesn't include the
 CH cert for the user contacting this CH, then we default to issuing
 Slice credentials in the name of this command-line user. A testing artifact.

 The -r argument could be a file with the GCF CA certificate. However
 to support federation, it should be a directory with all trusted / federated
 CH and CA certificates or certificate chains (PEM format). 

 Optional arguments include -H to specify a full hostname, -p to
 listen on a port other than 8000, and --debug for debugging output.

 See geni/ch.py constants to change the known Aggregates, slice URNs,
 etc. EG by adding other known federated aggregates, a single gch
 instance can point a client at multiple GENI AM API compliant
 Aggregate Managers from whatever control framework.
 
3. Start the aggregate manager server:

 $ src/gam.py -r <ca-cert.pem or trusted_chs_and_cas_dir/> \
   	      -c am-cert.pem -k am-key.pem

 NOTE: The -r ca-cert.pem is a file name with the AMs' CA cert, or
 better still, a directory with all trusted CH and CA certs.
 This is the 1 or many certs that should be trusted to sign slice
 credentials, or listResources requests. IE to federate, put the CA
 (and maybe CH) certs from all federates into a directory.

 Optional arguments include -H to specify a full hostname, -p to
 listen on a port other than 8001, and --debug for debugging output.

4. Run the GCF installation testing client:

 $ src/client.py -c alice-cert.pem -k alice-key.pem \
     --ch https://localhost:8000/ --am https://localhost:8001/

 The output should show some basic API testing, and possibly some
 debug output. Errors will be marked by exception traces or 'failed'.

 Optional arguments --debug and --debug-rpc enable more debug output.

 Note that you can use user credentials from any federated control 
 framework, as long as the appropriate CH and CA PEM certificates 
 were supplied to the -r arguments to gch and gam above.

5. See README-omni.txt for instructions on running the OMNI GENI
 Client. Omni is a sample command line interface for doing arbitrary
 commands against multiple Aggregate Managers.

6. Federating: Interacting with multiple Control Frameworks.

 To allow another Aggregate Manager to accept user
 credentials or slice credentials from this clearinghouse, you will
 need to copy the generated ca-cert.pem and ch-cert.pem (see step 1) to 
 that AM's server:
 a) For a GENI AM, copy the certificates to the trusted_roots dir used for 
 startup (as in steps 2 and 3 above)
 b) For a PlanetLab AM, the trusted_roots dir is at /etc/sfa/trusted_roots
 AND FIXME: ?Concat? ?Register in a DB?
 c) For a PG AM FIXME FIXME
 d) For an OpenFlow AM FIXME FIXME

Further Reading
===============

See FIXME
<Wiki on the GENI AM API, RSpecs, ?>

