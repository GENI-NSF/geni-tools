
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

  On rpm systems the required packages are 
     	 xmlsec1
	 xmlsec1-openssl-devel

  On debian systems the packages are 
     	 libxmlsec1
	 xmlsec1
	 libxmlsec1-openssl
	 libxmlsec1-dev

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

1. Generate keys and certificates for your users, clearinghouse, and aggregate manager.

 $ python src/gen-certs.py

 This  creates keys and certificates for a clearinghouse (ch), an aggregate
 manager (am), and a researcher (alice).
 The directory for the output, the researcher name, and which keys to
 generate are configurable via command line options. Cert URNs and
 some privileges are modifiable via constants. 
 Note you can generate multiple AM credentials and multiple user
 credentials using this script.

 Note that you should customize the certificates generated at your
 site using the constants at the top of this file, if you will use
 these certificates to interact with any other GENI site. In particular, 
 URNs must be globally unique. If you change the cert prefix, be sure
 to make corresponding edits to geni/ch.py SLICEPUBID_PREFIX.

Optional: Create a directory containing all known and trusted (federated)
 certificates (see below for an explanation).

2. Start the clearinghouse server:

 $ python src/gch.py -r <ch-cert.pem or trusted_roots_dir/> \
   	      -c ch-cert.pem -k ch-key.pem -g geni_aggregates

 The optional -r argument could be a file with the GCF CH certificate. 
 If you want to allow users from other Clearinghouses to make
 calls on this clearinghouse, install their root certificates too.
 To support this, it should be a directory with all trusted / federated
 certificates (PEM format). 
 Note that the CH certificate is used in generating slice credentials.


 The geni_aggregates file lists the Aggregate Managers that have
 federated with this Clearinghouse. For some other examples 
 see src/geni/ch.py.  This is how a single gch can contact multiple
 AM API compliant agggregate managers from whatever control framework.
 Aggregate URNs here are for human consumption and need not be accurate.

 Other optional arguments include -H to specify a full hostname, -p to
 listen on a port other than 8000, and --debug for debugging output. 
 Note that listening on localhost/127.0.0.1 (the default) is not the same 
 as listening on a real hostname / IP address. Be sure to listen on the
 desired interface and address the Aggregate Manager / Clearinghouse
 consistently.

 See geni/ch.py constants to change the slice URNs, etc. Note that slice URNs
 are globally unique, and constrained to be proper children of their
 Clearinghouse (Slice Authority).
 Another constant you may want to change is the lifetime of Slice
 credentials. By default they last 3600 seconds. That is likely too
 short to actually use any allocated resources.
 
3. Start the aggregate manager server:

 $ python src/gam.py -r <ch-cert.pem or trusted_chs_and_cas_dir/> \
   	      -c am-cert.pem -k am-key.pem

 NOTE: The -r ch-cert.pem is a file name with the CH cert, or
 better still, a directory with all trusted root certs.
 These certs will be used to verify slices and resource requests from the control
 frameworks that you have federated with.

 Optional arguments include -H to specify a full hostname, -p to
 listen on a port other than 8001, and --debug for debugging output.
 Note that listening on localhost/127.0.0.1 (the default) is not the same 
 as listening on a real hostname / IP address. Be sure to listen on the
 desired interface and address the Aggregate Manager / Clearinghouse
 consistently.

4. Run the GCF installation testing client:

 $ python src/client.py -c alice-cert.pem -k alice-key.pem \
     --ch https://localhost:8000/ --am https://localhost:8001/

 The output should show some basic API testing, and possibly some
 debug output. Errors will be marked by exception traces or 'failed'.

 Optional arguments --debug and --debug-rpc enable more debug output.

 Note that you can use user credentials from any federated control 
 framework, as long as the appropriate CH certificates 
 were supplied to the -r arguments to gch and gam above.

5. See README-omni.txt for instructions on running the OMNI GENI
 Client. Omni is a sample command line interface for doing arbitrary
 commands against multiple Aggregate Managers.

6. Federating: Interacting with multiple Control Frameworks.
 
 With federation, a user from one control framework can use their
 certificate and slice credentials to allocate resources from
 aggregates affiliated with other control frameworks.  In a federated
 network, each clearinghouse lists to its users all of the known
 aggregate managers that its users can allocate from.  Second, each
 aggregate manager has a list of trusted root certificates for each
 federated control framework.

 -- Step 1) Sharing keys -- Do this for each Aggregate Manager
 For each Aggregate Manager that should accept credentials from your
 Clearinghouse:

 To add your GCF certificate to an SFA based aggregate manager, copy the 
 CH certificate file (ch-cert.pem) to /etc/sfa/trusted_roots/ on the 
 AM's server. 
 
 After adding your certificates, restart sfa (sudo /etc/init.d/sfa restart).

 To add an SFA certificate to a GCF based aggregate manager, copy your
 SFA key from /etc/sfa/trusted_roots/<should be a .gid file> to your GCF
 trusted roots directory created in steps 2 and 3 above. This is
 not particularly necessary for the Clearinghouse (gch), but is 
 necessary for the Aggregate Manager (gam).


 -- Step 2) Listing Aggregates -- Do this on all peered clearinghouses

 To list your GCF AM to SFA users, add your GCF address to /etc/sfa/geni_aggregates.xml.
 The form is <aggregate addr="hostname" hrn="hrn" port="port" url="hostname:port"/>

   URL and addr/port are redundant, but fill in both.  The hrn can be 
   anything, but its intent is to be a shorthand dotted notation of your 
   URN, such as 'plc.princeton' or 'geni.gpo.bbn'. Be sure it is unique.


 To list your SFA aggregate manager in your GCF clearinghouse, edit
 the 'geni_aggregates' file in your root gcf/ directory and add an
 entry for the SFA AM. The form is "URN,URL" (without quotes) with one
 such entry per line. An example is: 
 'urn:publicid:IDN+plc:gpo1+authority+sa, http://sfa.gpolab.bbn.com:12348'

 The URN should be unique. While it need not be fully accurate, that
 is useful. You can find the URN using the openssl commandline:
      openssl x509 -in [gid] -text | grep "Subject Alternative" 


Further Reading
===============

The GENI API pages on the GENI wiki have full details on GENI identifiers,
credentials and certificates. See www.geni.net

See FIXME
<Wiki on the GENI AM API, RSpecs, ?>

