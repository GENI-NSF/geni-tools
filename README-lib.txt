Description
===========

This library includes useful utility functions for use in implementing
GENI AM API compatible services.


Software Dependencies
=====================
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

This library provides convenience functions on top of the SFA library.  The functions
can be found in the modules located in src/geni/util/.  These include functions for 
URN creation, secure XML-RPC client creation, credential creation and verification,
and certificate creation.  

Please see the source files themselves for further documentation.

Example usage after installation:

from geni.util.urn_util import URN
urn = URN("gcf//gpo//bbn1","authority","sa").urn_string()
