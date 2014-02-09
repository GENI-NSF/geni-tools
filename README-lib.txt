GCF Geni Library Package

Description
===========

This library includes useful utility functions for use in implementing
GENI AM API compatible services.


Software Dependencies
=====================

Dependencies should be handled by the package install.
On RPM based systems:

python 2.6
m2crypto	
xmlsec1-openssl-devel
libxslt-python
python-ZSI
python-lxml
python-setuptools
python-dateutil


Installation
============

python setup.py install


Documentation
=============

This library provides convenience functions on top of the SFA library.
The functions can be found in the modules located in src/gcf/geni/util/.
These include functions for URN creation, secure XML-RPC client
creation, credential creation and verification, and certificate
creation.

Please see the source files themselves for further documentation.

Example usage after installation:

# To create a URN
from gcf.geni.util.urn_util import URN
ch_urn = URN("gcf//gpo//bbn1","authority","sa").urn_string()
am_urn = URN("gcf//gpo//bbn1//am1","authority","am").urn_string()

# To create a certificate:
from gcf.geni.util.urn_util import URN
from gcf.geni.util.cert_util import create_cert
urn = URN("gcf//gpo//bbn1", "user", "alice").urn_string()
alice_cert = create_cert(urn, issuer_key, issuer_certificate).save_to_string()


Further examples can be found in the GENI Control Framework
distribution in the GENI Clearinghouse and GENI Aggregate Manager
implementations.  This includes examples of creating and verifying
credentials.
