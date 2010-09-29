
GENI Reference Control Framework
================================


Description
===========

This software implements a sample GENI Aggregate Manager. It also
includes a sample GENI Clearinghouse and command line test client. This
software is intended to demonstrate the GENI Aggregate Manager API.


Installation & Getting Started
==============================

See INSTALL.txt for instructions on installing this package, and
the 4 step test run using the test client.
Omni users should follow those instructions to ensure software 
dependencies are met.

Software Dependencies
=====================

The GCF package is intended to be run on a modern Linux distribution
(circa 2010 or 2009). Python 2.6 is required. This software is not
Python 3 compatible.

This software requires a number of readily available software
packages. Most modern Linux distributions should have these packages
available via their native package management suite (eg. yum or apt).

For details, see INSTALL.txt.


Included Software
=================

This package includes software from PlanetLab. All of the PlanetLab
software is in the src/sfa directory. More information, including the
license, can be found in src/sfa/README.txt.


Usage Instructions
============

Basic install & running instructions are in INSTALL.txt.

Full details on options for each step are described below.

0. Edit gcf_config (installed to /etc/gcf-servers/omni_config or can
   also be read from the current directory) to configure your
   clearinghouse and aggregate manager.  The default values should be
   fine for most settings, but you should change the base_name (URN)
   to be specific to you.  The keys and certificates will be generated
   in src/gen-certs.py in Step 1 to the destinations you enter in
   gcf_config.
 
1. Generate keys and certificates for your users, clearinghouse, and 
   aggregate manager.

   $ python src/gen-certs.py

   This creates keys and certificates for a clearinghouse (ch), an
   aggregate manager (am), and a researcher (alice).  Cert URNs and
   some privileges are modifiable via constants.  Note you can
   generate multiple AM credentials and multiple user credentials
   using this script.

   Note that you should customize the certificates generated at your
   site using the constants in gcf_config, if you will use these
   certificates to interact with any other GENI site. In particular,
   URNs must be globally unique.

   By default the gcf_config file is found in the local directory or
   /etc/gcf-servers/.  Override the default locations by specifying
   the -f argument.

   A directory for trusted_roots is used or created, and your CH
   certificate is copied there. This is used in Federation (see
   below).

2. Start the clearinghouse server:

   $ python src/gcf-ch.py   
 
   To override the settings in gcf_config, you can use these command
   line options:

   $ python src/gcf-ch.py -r <ch-cert.pem or trusted_roots_dir/> \
                          -c ch-cert.pem -k ch-key.pem \
                          -f <path-to-gcf_config-file>

   The optional -r argument could be a file with the GCF CH
   certificate.  If you want to allow users from other Clearinghouses
   to make calls on this clearinghouse, install their root
   certificates too.  To support this, it should be a directory with
   all trusted / federated certificates (PEM format).  Note that the
   CH certificate is used in generating slice credentials.

   The gcf_config file am_* properties lists the Aggregate Managers that have
   federated with this Clearinghouse. For some other examples see
   src/geni/ch.py.  This is how a single gcf-ch can contact multiple
   AM API compliant agggregate managers from whatever control
   framework.  Aggregate URNs here are for human consumption and need
   not be accurate.

   By default the gcf_config file is found in the local
   directory. Override that by specifying the -f argument.

   Other optional arguments include -H to specify a full hostname, -p
   to listen on a port other than 8000, and --debug for debugging
   output.  Note that listening on localhost/127.0.0.1 (the default)
   is not the same as listening on a real hostname / IP address. Be
   sure to listen on the desired interface and address the Aggregate
   Manager / Clearinghouse consistently.

   See gcf_config clearinghouse section for relevant constants.  Note
   that slice URNs are globally unique, and constrained to be proper
   children of their Clearinghouse (Slice Authority).  Another
   constant you may want to change is the lifetime of Slice
   credentials. By default they last 3600 seconds. That is likely too
   short to actually use any allocated resources.
 
3. Start the aggregate manager server:

   $ python src/gcf-am.py
 
   To override the settings in gcf_config, you can use these command
   line options:

 $ python src/gcf-am.py -r <ch-cert.pem or trusted_chs_and_cas_dir/> \
                        -c am-cert.pem -k am-key.pem \
                        -f <path-to-gcf_config-file>

   By default the gcf_config file is found in the local
   directory. Override that by specifying the -f argument. See the
   aggregate_manager section.  Note in particular that you name your
   aggregate manager, and could generate multiple aggregate manager
   certificates be editing gcf_config and re-running gen-certs.

   NOTE: The -r ch-cert.pem is a file name with the CH cert, or better
   still, a directory with all trusted root certs.  These certs will
   be used to verify slices and resource requests from the control
   frameworks that you have federated with.

   Optional arguments include -H to specify a full hostname, -p to
   listen on a port other than 8001, and --debug for debugging output.
   Note that listening on localhost/127.0.0.1 (the default) is not the
   same as listening on a real hostname / IP address. Be sure to
   listen on the desired interface and address the Aggregate Manager /
   Clearinghouse consistently.

4. Run the GCF installation testing client:

   $ python src/gcf-test.py
 
   To override the settings in gcf_config, you can use these command
   line options:

   $ python src/gcf-test.py -c alice-cert.pem -k alice-key.pem \
                            --ch https://localhost:8000/ \
                            --am https://localhost:8001/ \
                            -f <path-to-gcf_config-file>

   The output should show some basic API testing, and possibly some
   debug output. Errors will be marked by exception traces or
   'failed'.

   By default the gcf_config file is found in the local
   directory. Override that by specifying the -f argument.

   Optional arguments --debug and --debug-rpc enable more debug
   output.

   Note that you can use user credentials from any federated control
   framework, as long as the appropriate CH certificates were supplied
   to the -r arguments to gcf-ch and gcf-am above.

5. See README-omni.txt for instructions on running the OMNI GENI
   Client. Omni is a sample command line interface for doing arbitrary
   commands against multiple Aggregate Managers.

6. Federating: Interacting with multiple Control Frameworks.
 
   With federation, a user from one control framework can use their
   certificate and slice credentials to allocate resources from
   aggregates affiliated with other control frameworks.  In a
   federated network, each clearinghouse lists to its users all of the
   known aggregate managers that its users can allocate from.  Second,
   each aggregate manager has a list of trusted root certificates for
   each federated control framework.

6.1 Sharing keys -- Do this for each Aggregate Manager

   For each Aggregate Manager that should accept credentials from your
   Clearinghouse:

   To add your GCF certificate to an SFA based aggregate manager, copy
   the CH certificate file (ch-cert.pem) to /etc/sfa/trusted_roots/ on
   the AM's server.
 
   After adding your certificates, restart sfa (sudo /etc/init.d/sfa
   restart).

   To add an SFA certificate to a GCF based aggregate manager, copy
   your SFA key from /etc/sfa/trusted_roots/<should be a .gid file> to
   your GCF trusted roots directory created in steps 2 and 3
   above. This is not particularly necessary for the Clearinghouse
   (gcf-ch), but is necessary for the Aggregate Manager (gcf-am).

   To add a any root certificate to an OpenFlow (Expedient) aggregate manager, 
   copy the file to
     /etc/expedient/gcf-x509.crt as [something].crt
   In /etc/expedient/apache/ca-certs, do:
     sudo make
   This should run the local Makefile, creating a symlink [something].0
   to the .crt file in the gcf-x509.crt directory.

6.2 Listing Aggregates -- Do this on all peered clearinghouses

   To list your GCF AM to SFA users, add your GCF address to 
    	 /etc/sfa/geni_aggregates.xml.

   The form is 
       <aggregate addr="hostname" hrn="hrn" port="port" url="hostname:port"/>

   URL and addr/port are redundant, but fill in both.  The hrn can be
   anything, but its intent is to be a shorthand dotted notation of
   your URN, such as 'plc.princeton' or 'geni.gpo.bbn'. Be sure it is
   unique.

   To list your SFA aggregate manager in your GCF clearinghouse, edit
   the 'gcf_config' file in your root gcf/ directory and add an
   entry for the SFA AM. The form is documented in the sample file.
   Enter a new am_# property with a value like "URN,URL" (without quotes) with
   one such entry per line. An example is:

     'am_5 = urn:publicid:IDN+plc:gpo1+authority+sa, http://sfa.gpolab.bbn.com:12348'

   The URN should be unique. While it need not be fully accurate, that
   is useful. You can find the URN using the openssl commandline:

     openssl x509 -in [gid] -text | grep "Subject Alternative" 


Further Reading
===============

The GENI API pages on the GENI wiki have full details on GENI identifiers,
credentials and certificates.

See http://groups.geni.net/geni/wiki/GeniApi
