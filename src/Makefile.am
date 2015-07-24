omni: $(srcdir)/omni.py
	cp omni.py omni

stitcher: $(srcdir)/stitcher.py
	cp stitcher.py stitcher

omni-configure: $(srcdir)/omni-configure.py
	cp omni-configure.py omni-configure

# Distribute but do not install
EXTRA_DIST =  \
	omni.py \
	omni-configure.py \
	stitcher.py

CLEANFILES =  \
	omni \
	omni-configure \
	stitcher

bin_SCRIPTS = \
	omni \
	omni-configure \
	stitcher

dist_pkgdata_SCRIPTS = \
	delegateSliceCred.py \
	clear-passphrases.py \
	gcf-am.py \
	gcf-ch.py \
	gcf-test.py \
	gen-certs.py

dist_pkgdata_DATA = \
	omni_log_conf_sample.conf

nobase_dist_python_DATA = \
	gcf/gcf_version.py \
	gcf/geni/am1.py \
	gcf/geni/am/aggregate.py \
	gcf/geni/am/am2.py \
	gcf/geni/am/am3.py \
	gcf/geni/am/am_method_context.py \
	gcf/geni/am/api_error_exception.py \
	gcf/geni/am/fakevm.py \
	gcf/geni/am/__init__.py \
	gcf/geni/am/proxyam.py \
	gcf/geni/am/resource.py \
	gcf/geni/am/test_ams.py \
	gcf/geni/auth/abac_authorizer.py \
	gcf/geni/auth/abac_resource_manager.py \
	gcf/geni/auth/argument_guard.py \
	gcf/geni/auth/authorizer_client.py \
	gcf/geni/auth/authorizer_server.py \
	gcf/geni/auth/base_authorizer.py \
	gcf/geni/auth/binders.py \
	gcf/geni/auth/__init__.py \
	gcf/geni/auth/resource_binder.py \
	gcf/geni/auth/sfa_authorizer.py \
	gcf/geni/auth/util.py \
	gcf/geni/ca.py \
	gcf/geni/ch.py \
	gcf/geni/config.py \
	gcf/geni/gch.py \
	gcf/geni/__init__.py \
	gcf/geni/pgch.py \
	gcf/geni/SecureThreadedXMLRPCServer.py \
	gcf/geni/SecureXMLRPCServer.py \
	gcf/geni/util/cert_util.py \
	gcf/geni/util/ch_interface.py \
	gcf/geni/util/cred_util.py \
	gcf/geni/util/error_util.py \
	gcf/geni/util/__init__.py \
	gcf/geni/util/rspec_schema.py \
	gcf/geni/util/rspec_util.py \
	gcf/geni/util/secure_xmlrpc_client.py \
	gcf/geni/util/speaksfor_util.py \
	gcf/geni/util/tz_util.py \
	gcf/geni/util/urn_util.py \
	gcf/__init__.py \
	gcf/omnilib/amhandler.py \
	gcf/omnilib/chhandler.py \
	gcf/omnilib/frameworks/framework_apg.py \
	gcf/omnilib/frameworks/framework_base.py \
	gcf/omnilib/frameworks/framework_chapi.py \
	gcf/omnilib/frameworks/framework_gcf.py \
	gcf/omnilib/frameworks/framework_gch.py \
	gcf/omnilib/frameworks/framework_gib.py \
	gcf/omnilib/frameworks/framework_of.py \
	gcf/omnilib/frameworks/framework_pgch.py \
	gcf/omnilib/frameworks/framework_pg.py \
	gcf/omnilib/frameworks/framework_sfa.py \
	gcf/omnilib/frameworks/__init__.py \
	gcf/omnilib/handler.py \
	gcf/omnilib/__init__.py \
	gcf/omnilib/stitch/defs.py \
	gcf/omnilib/stitch/GENIObject.py \
	gcf/omnilib/stitch/gmoc.py \
	gcf/omnilib/stitchhandler.py \
	gcf/omnilib/stitch/__init__.py \
	gcf/omnilib/stitch/launcher.py \
	gcf/omnilib/stitch/ManifestRSpecCombiner.py \
	gcf/omnilib/stitch/objects.py \
	gcf/omnilib/stitch/RSpecParser.py \
	gcf/omnilib/stitch/scs.py \
	gcf/omnilib/stitch/utils.py \
	gcf/omnilib/stitch/VLANRange.py \
	gcf/omnilib/stitch/workflow.py \
	gcf/omnilib/util/abac.py \
	gcf/omnilib/util/credparsing.py \
	gcf/omnilib/util/dates.py \
	gcf/omnilib/util/dossl.py \
	gcf/omnilib/util/faultPrinting.py \
	gcf/omnilib/util/files.py \
	gcf/omnilib/util/handler_utils.py \
	gcf/omnilib/util/__init__.py \
	gcf/omnilib/util/json_encoding.py \
	gcf/omnilib/util/namespace.py \
	gcf/omnilib/util/omnierror.py \
	gcf/omnilib/util/paths.py \
	gcf/omnilib/xmlrpc/client.py \
	gcf/omnilib/xmlrpc/__init__.py \
	gcf/oscript.py \
	gcf/sfa/__init__.py \
	gcf/sfa/README.txt \
	gcf/sfa/trust/abac_credential.py \
	gcf/sfa/trust/certificate.py \
	gcf/sfa/trust/credential_factory.py \
	gcf/sfa/trust/credential_legacy.py \
	gcf/sfa/trust/credential.py \
	gcf/sfa/trust/gid.py \
	gcf/sfa/trust/__init__.py \
	gcf/sfa/trust/rights.py \
	gcf/sfa/util/enumeration.py \
	gcf/sfa/util/faults.py \
	gcf/sfa/util/genicode.py \
	gcf/sfa/util/__init__.py \
	gcf/sfa/util/sfalogging.py \
	gcf/sfa/util/sfatime.py \
	gcf/sfa/util/xrn.py \
	gcf/stitcher_logging.conf \
	gcf/stitcher_logging_deft.py

EXTRA_DIST += \
	omni_unittest.py
