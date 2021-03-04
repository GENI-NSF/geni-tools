Name:           geni-tools
Version:        2.11
Release:        1%{?dist}
Summary:        GENI command line tools
BuildArch:      noarch
License:        GENI Public License
URL:            https://github.com/GENI-NSF/geni-tools
Source0:        https://github.com/GENI-NSF/geni-tools/releases/download/v2.11/geni-tools-2.11.tar.gz
Group:          Applications/Internet
Requires:       m2crypto
Requires:       python-dateutil
Requires:       pyOpenSSL

# BuildRequires: gettext
# Requires(post): info
# Requires(preun): info

%description

Commonly used command line tools for GENI, including omni, stitcher,
and readyToLogin. Also includes utilities, sample scripts, and
reference implementations.

%prep
%setup -q
#iconv -f iso8859-1 -t utf-8 -o ChangeLog.conv ChangeLog && mv -f ChangeLog.conv ChangeLog
#iconv -f iso8859-1 -t utf-8 -o THANKS.conv THANKS && mv -f THANKS.conv THANKS

%build
%configure
make %{?_smp_mflags}


%install
rm -rf $RPM_BUILD_ROOT
%make_install
# Include the copyright file
install -m 0644 debian/copyright $RPM_BUILD_ROOT/%{_defaultdocdir}/%{name}/copyright

%clean
rm -rf $RPM_BUILD_ROOT

%files
%defattr(-,root,root)
%{_bindir}/addMemberToSliceAndSlivers
%{_bindir}/omni
%{_bindir}/omni-configure
%{_bindir}/readyToLogin
%{_bindir}/stitcher

%{python_sitelib}/gcf/__init__.py
%{python_sitelib}/gcf/__init__.pyc
%{python_sitelib}/gcf/__init__.pyo
%{python_sitelib}/gcf/gcf_version.py
%{python_sitelib}/gcf/gcf_version.pyc
%{python_sitelib}/gcf/gcf_version.pyo
%{python_sitelib}/gcf/geni/SecureThreadedXMLRPCServer.py
%{python_sitelib}/gcf/geni/SecureThreadedXMLRPCServer.pyc
%{python_sitelib}/gcf/geni/SecureThreadedXMLRPCServer.pyo
%{python_sitelib}/gcf/geni/SecureXMLRPCServer.py
%{python_sitelib}/gcf/geni/SecureXMLRPCServer.pyc
%{python_sitelib}/gcf/geni/SecureXMLRPCServer.pyo
%{python_sitelib}/gcf/geni/__init__.py
%{python_sitelib}/gcf/geni/__init__.pyc
%{python_sitelib}/gcf/geni/__init__.pyo
%{python_sitelib}/gcf/geni/am/__init__.py
%{python_sitelib}/gcf/geni/am/__init__.pyc
%{python_sitelib}/gcf/geni/am/__init__.pyo
%{python_sitelib}/gcf/geni/am/aggregate.py
%{python_sitelib}/gcf/geni/am/aggregate.pyc
%{python_sitelib}/gcf/geni/am/aggregate.pyo
%{python_sitelib}/gcf/geni/am/am2.py
%{python_sitelib}/gcf/geni/am/am2.pyc
%{python_sitelib}/gcf/geni/am/am2.pyo
%{python_sitelib}/gcf/geni/am/am3.py
%{python_sitelib}/gcf/geni/am/am3.pyc
%{python_sitelib}/gcf/geni/am/am3.pyo
%{python_sitelib}/gcf/geni/am/am_method_context.py
%{python_sitelib}/gcf/geni/am/am_method_context.pyc
%{python_sitelib}/gcf/geni/am/am_method_context.pyo
%{python_sitelib}/gcf/geni/am/api_error_exception.py
%{python_sitelib}/gcf/geni/am/api_error_exception.pyc
%{python_sitelib}/gcf/geni/am/api_error_exception.pyo
%{python_sitelib}/gcf/geni/am/fakevm.py
%{python_sitelib}/gcf/geni/am/fakevm.pyc
%{python_sitelib}/gcf/geni/am/fakevm.pyo
%{python_sitelib}/gcf/geni/am/proxyam.py
%{python_sitelib}/gcf/geni/am/proxyam.pyc
%{python_sitelib}/gcf/geni/am/proxyam.pyo
%{python_sitelib}/gcf/geni/am/resource.py
%{python_sitelib}/gcf/geni/am/resource.pyc
%{python_sitelib}/gcf/geni/am/resource.pyo
%{python_sitelib}/gcf/geni/am/test_ams.py
%{python_sitelib}/gcf/geni/am/test_ams.pyc
%{python_sitelib}/gcf/geni/am/test_ams.pyo
%{python_sitelib}/gcf/geni/am1.py
%{python_sitelib}/gcf/geni/am1.pyc
%{python_sitelib}/gcf/geni/am1.pyo
%{python_sitelib}/gcf/geni/auth/__init__.py
%{python_sitelib}/gcf/geni/auth/__init__.pyc
%{python_sitelib}/gcf/geni/auth/__init__.pyo
%{python_sitelib}/gcf/geni/auth/abac_authorizer.py
%{python_sitelib}/gcf/geni/auth/abac_authorizer.pyc
%{python_sitelib}/gcf/geni/auth/abac_authorizer.pyo
%{python_sitelib}/gcf/geni/auth/abac_resource_manager.py
%{python_sitelib}/gcf/geni/auth/abac_resource_manager.pyc
%{python_sitelib}/gcf/geni/auth/abac_resource_manager.pyo
%{python_sitelib}/gcf/geni/auth/argument_guard.py
%{python_sitelib}/gcf/geni/auth/argument_guard.pyc
%{python_sitelib}/gcf/geni/auth/argument_guard.pyo
%{python_sitelib}/gcf/geni/auth/authorizer_client.py
%{python_sitelib}/gcf/geni/auth/authorizer_client.pyc
%{python_sitelib}/gcf/geni/auth/authorizer_client.pyo
%{python_sitelib}/gcf/geni/auth/authorizer_server.py
%{python_sitelib}/gcf/geni/auth/authorizer_server.pyc
%{python_sitelib}/gcf/geni/auth/authorizer_server.pyo
%{python_sitelib}/gcf/geni/auth/base_authorizer.py
%{python_sitelib}/gcf/geni/auth/base_authorizer.pyc
%{python_sitelib}/gcf/geni/auth/base_authorizer.pyo
%{python_sitelib}/gcf/geni/auth/binders.py
%{python_sitelib}/gcf/geni/auth/binders.pyc
%{python_sitelib}/gcf/geni/auth/binders.pyo
%{python_sitelib}/gcf/geni/auth/resource_binder.py
%{python_sitelib}/gcf/geni/auth/resource_binder.pyc
%{python_sitelib}/gcf/geni/auth/resource_binder.pyo
%{python_sitelib}/gcf/geni/auth/sfa_authorizer.py
%{python_sitelib}/gcf/geni/auth/sfa_authorizer.pyc
%{python_sitelib}/gcf/geni/auth/sfa_authorizer.pyo
%{python_sitelib}/gcf/geni/auth/util.py
%{python_sitelib}/gcf/geni/auth/util.pyc
%{python_sitelib}/gcf/geni/auth/util.pyo
%{python_sitelib}/gcf/geni/ca.py
%{python_sitelib}/gcf/geni/ca.pyc
%{python_sitelib}/gcf/geni/ca.pyo
%{python_sitelib}/gcf/geni/ch.py
%{python_sitelib}/gcf/geni/ch.pyc
%{python_sitelib}/gcf/geni/ch.pyo
%{python_sitelib}/gcf/geni/config.py
%{python_sitelib}/gcf/geni/config.pyc
%{python_sitelib}/gcf/geni/config.pyo
%{python_sitelib}/gcf/geni/gch.py
%{python_sitelib}/gcf/geni/gch.pyc
%{python_sitelib}/gcf/geni/gch.pyo
%{python_sitelib}/gcf/geni/pgch.py
%{python_sitelib}/gcf/geni/pgch.pyc
%{python_sitelib}/gcf/geni/pgch.pyo
%{python_sitelib}/gcf/geni/util/__init__.py
%{python_sitelib}/gcf/geni/util/__init__.pyc
%{python_sitelib}/gcf/geni/util/__init__.pyo
%{python_sitelib}/gcf/geni/util/cert_util.py
%{python_sitelib}/gcf/geni/util/cert_util.pyc
%{python_sitelib}/gcf/geni/util/cert_util.pyo
%{python_sitelib}/gcf/geni/util/ch_interface.py
%{python_sitelib}/gcf/geni/util/ch_interface.pyc
%{python_sitelib}/gcf/geni/util/ch_interface.pyo
%{python_sitelib}/gcf/geni/util/cred_util.py
%{python_sitelib}/gcf/geni/util/cred_util.pyc
%{python_sitelib}/gcf/geni/util/cred_util.pyo
%{python_sitelib}/gcf/geni/util/error_util.py
%{python_sitelib}/gcf/geni/util/error_util.pyc
%{python_sitelib}/gcf/geni/util/error_util.pyo
%{python_sitelib}/gcf/geni/util/rspec_schema.py
%{python_sitelib}/gcf/geni/util/rspec_schema.pyc
%{python_sitelib}/gcf/geni/util/rspec_schema.pyo
%{python_sitelib}/gcf/geni/util/rspec_util.py
%{python_sitelib}/gcf/geni/util/rspec_util.pyc
%{python_sitelib}/gcf/geni/util/rspec_util.pyo
%{python_sitelib}/gcf/geni/util/secure_xmlrpc_client.py
%{python_sitelib}/gcf/geni/util/secure_xmlrpc_client.pyc
%{python_sitelib}/gcf/geni/util/secure_xmlrpc_client.pyo
%{python_sitelib}/gcf/geni/util/speaksfor_util.py
%{python_sitelib}/gcf/geni/util/speaksfor_util.pyc
%{python_sitelib}/gcf/geni/util/speaksfor_util.pyo
%{python_sitelib}/gcf/geni/util/tz_util.py
%{python_sitelib}/gcf/geni/util/tz_util.pyc
%{python_sitelib}/gcf/geni/util/tz_util.pyo
%{python_sitelib}/gcf/geni/util/urn_util.py
%{python_sitelib}/gcf/geni/util/urn_util.pyc
%{python_sitelib}/gcf/geni/util/urn_util.pyo
%{python_sitelib}/gcf/omnilib/__init__.py
%{python_sitelib}/gcf/omnilib/__init__.pyc
%{python_sitelib}/gcf/omnilib/__init__.pyo
%{python_sitelib}/gcf/omnilib/amhandler.py
%{python_sitelib}/gcf/omnilib/amhandler.pyc
%{python_sitelib}/gcf/omnilib/amhandler.pyo
%{python_sitelib}/gcf/omnilib/chhandler.py
%{python_sitelib}/gcf/omnilib/chhandler.pyc
%{python_sitelib}/gcf/omnilib/chhandler.pyo
%{python_sitelib}/gcf/omnilib/frameworks/__init__.py
%{python_sitelib}/gcf/omnilib/frameworks/__init__.pyc
%{python_sitelib}/gcf/omnilib/frameworks/__init__.pyo
%{python_sitelib}/gcf/omnilib/frameworks/framework_apg.py
%{python_sitelib}/gcf/omnilib/frameworks/framework_apg.pyc
%{python_sitelib}/gcf/omnilib/frameworks/framework_apg.pyo
%{python_sitelib}/gcf/omnilib/frameworks/framework_base.py
%{python_sitelib}/gcf/omnilib/frameworks/framework_base.pyc
%{python_sitelib}/gcf/omnilib/frameworks/framework_base.pyo
%{python_sitelib}/gcf/omnilib/frameworks/framework_chapi.py
%{python_sitelib}/gcf/omnilib/frameworks/framework_chapi.pyc
%{python_sitelib}/gcf/omnilib/frameworks/framework_chapi.pyo
%{python_sitelib}/gcf/omnilib/frameworks/framework_gcf.py
%{python_sitelib}/gcf/omnilib/frameworks/framework_gcf.pyc
%{python_sitelib}/gcf/omnilib/frameworks/framework_gcf.pyo
%{python_sitelib}/gcf/omnilib/frameworks/framework_gch.py
%{python_sitelib}/gcf/omnilib/frameworks/framework_gch.pyc
%{python_sitelib}/gcf/omnilib/frameworks/framework_gch.pyo
%{python_sitelib}/gcf/omnilib/frameworks/framework_gib.py
%{python_sitelib}/gcf/omnilib/frameworks/framework_gib.pyc
%{python_sitelib}/gcf/omnilib/frameworks/framework_gib.pyo
%{python_sitelib}/gcf/omnilib/frameworks/framework_of.py
%{python_sitelib}/gcf/omnilib/frameworks/framework_of.pyc
%{python_sitelib}/gcf/omnilib/frameworks/framework_of.pyo
%{python_sitelib}/gcf/omnilib/frameworks/framework_pg.py
%{python_sitelib}/gcf/omnilib/frameworks/framework_pg.pyc
%{python_sitelib}/gcf/omnilib/frameworks/framework_pg.pyo
%{python_sitelib}/gcf/omnilib/frameworks/framework_pgch.py
%{python_sitelib}/gcf/omnilib/frameworks/framework_pgch.pyc
%{python_sitelib}/gcf/omnilib/frameworks/framework_pgch.pyo
%{python_sitelib}/gcf/omnilib/frameworks/framework_sfa.py
%{python_sitelib}/gcf/omnilib/frameworks/framework_sfa.pyc
%{python_sitelib}/gcf/omnilib/frameworks/framework_sfa.pyo
%{python_sitelib}/gcf/omnilib/handler.py
%{python_sitelib}/gcf/omnilib/handler.pyc
%{python_sitelib}/gcf/omnilib/handler.pyo
%{python_sitelib}/gcf/omnilib/stitch/GENIObject.py
%{python_sitelib}/gcf/omnilib/stitch/GENIObject.pyc
%{python_sitelib}/gcf/omnilib/stitch/GENIObject.pyo
%{python_sitelib}/gcf/omnilib/stitch/ManifestRSpecCombiner.py
%{python_sitelib}/gcf/omnilib/stitch/ManifestRSpecCombiner.pyc
%{python_sitelib}/gcf/omnilib/stitch/ManifestRSpecCombiner.pyo
%{python_sitelib}/gcf/omnilib/stitch/RSpecParser.py
%{python_sitelib}/gcf/omnilib/stitch/RSpecParser.pyc
%{python_sitelib}/gcf/omnilib/stitch/RSpecParser.pyo
%{python_sitelib}/gcf/omnilib/stitch/VLANRange.py
%{python_sitelib}/gcf/omnilib/stitch/VLANRange.pyc
%{python_sitelib}/gcf/omnilib/stitch/VLANRange.pyo
%{python_sitelib}/gcf/omnilib/stitch/__init__.py
%{python_sitelib}/gcf/omnilib/stitch/__init__.pyc
%{python_sitelib}/gcf/omnilib/stitch/__init__.pyo
%{python_sitelib}/gcf/omnilib/stitch/defs.py
%{python_sitelib}/gcf/omnilib/stitch/defs.pyc
%{python_sitelib}/gcf/omnilib/stitch/defs.pyo
%{python_sitelib}/gcf/omnilib/stitch/gmoc.py
%{python_sitelib}/gcf/omnilib/stitch/gmoc.pyc
%{python_sitelib}/gcf/omnilib/stitch/gmoc.pyo
%{python_sitelib}/gcf/omnilib/stitch/launcher.py
%{python_sitelib}/gcf/omnilib/stitch/launcher.pyc
%{python_sitelib}/gcf/omnilib/stitch/launcher.pyo
%{python_sitelib}/gcf/omnilib/stitch/objects.py
%{python_sitelib}/gcf/omnilib/stitch/objects.pyc
%{python_sitelib}/gcf/omnilib/stitch/objects.pyo
%{python_sitelib}/gcf/omnilib/stitch/scs.py
%{python_sitelib}/gcf/omnilib/stitch/scs.pyc
%{python_sitelib}/gcf/omnilib/stitch/scs.pyo
%{python_sitelib}/gcf/omnilib/stitch/utils.py
%{python_sitelib}/gcf/omnilib/stitch/utils.pyc
%{python_sitelib}/gcf/omnilib/stitch/utils.pyo
%{python_sitelib}/gcf/omnilib/stitch/workflow.py
%{python_sitelib}/gcf/omnilib/stitch/workflow.pyc
%{python_sitelib}/gcf/omnilib/stitch/workflow.pyo
%{python_sitelib}/gcf/omnilib/stitchhandler.py
%{python_sitelib}/gcf/omnilib/stitchhandler.pyc
%{python_sitelib}/gcf/omnilib/stitchhandler.pyo
%{python_sitelib}/gcf/omnilib/util/__init__.py
%{python_sitelib}/gcf/omnilib/util/__init__.pyc
%{python_sitelib}/gcf/omnilib/util/__init__.pyo
%{python_sitelib}/gcf/omnilib/util/abac.py
%{python_sitelib}/gcf/omnilib/util/abac.pyc
%{python_sitelib}/gcf/omnilib/util/abac.pyo
%{python_sitelib}/gcf/omnilib/util/credparsing.py
%{python_sitelib}/gcf/omnilib/util/credparsing.pyc
%{python_sitelib}/gcf/omnilib/util/credparsing.pyo
%{python_sitelib}/gcf/omnilib/util/dates.py
%{python_sitelib}/gcf/omnilib/util/dates.pyc
%{python_sitelib}/gcf/omnilib/util/dates.pyo
%{python_sitelib}/gcf/omnilib/util/dossl.py
%{python_sitelib}/gcf/omnilib/util/dossl.pyc
%{python_sitelib}/gcf/omnilib/util/dossl.pyo
%{python_sitelib}/gcf/omnilib/util/faultPrinting.py
%{python_sitelib}/gcf/omnilib/util/faultPrinting.pyc
%{python_sitelib}/gcf/omnilib/util/faultPrinting.pyo
%{python_sitelib}/gcf/omnilib/util/files.py
%{python_sitelib}/gcf/omnilib/util/files.pyc
%{python_sitelib}/gcf/omnilib/util/files.pyo
%{python_sitelib}/gcf/omnilib/util/handler_utils.py
%{python_sitelib}/gcf/omnilib/util/handler_utils.pyc
%{python_sitelib}/gcf/omnilib/util/handler_utils.pyo
%{python_sitelib}/gcf/omnilib/util/json_encoding.py
%{python_sitelib}/gcf/omnilib/util/json_encoding.pyc
%{python_sitelib}/gcf/omnilib/util/json_encoding.pyo
%{python_sitelib}/gcf/omnilib/util/namespace.py
%{python_sitelib}/gcf/omnilib/util/namespace.pyc
%{python_sitelib}/gcf/omnilib/util/namespace.pyo
%{python_sitelib}/gcf/omnilib/util/omnierror.py
%{python_sitelib}/gcf/omnilib/util/omnierror.pyc
%{python_sitelib}/gcf/omnilib/util/omnierror.pyo
%{python_sitelib}/gcf/omnilib/util/paths.py
%{python_sitelib}/gcf/omnilib/util/paths.pyc
%{python_sitelib}/gcf/omnilib/util/paths.pyo
%{python_sitelib}/gcf/omnilib/xmlrpc/__init__.py
%{python_sitelib}/gcf/omnilib/xmlrpc/__init__.pyc
%{python_sitelib}/gcf/omnilib/xmlrpc/__init__.pyo
%{python_sitelib}/gcf/omnilib/xmlrpc/client.py
%{python_sitelib}/gcf/omnilib/xmlrpc/client.pyc
%{python_sitelib}/gcf/omnilib/xmlrpc/client.pyo
%{python_sitelib}/gcf/oscript.py
%{python_sitelib}/gcf/oscript.pyc
%{python_sitelib}/gcf/oscript.pyo
%{python_sitelib}/gcf/sfa/README.txt
%{python_sitelib}/gcf/sfa/__init__.py
%{python_sitelib}/gcf/sfa/__init__.pyc
%{python_sitelib}/gcf/sfa/__init__.pyo
%{python_sitelib}/gcf/sfa/trust/__init__.py
%{python_sitelib}/gcf/sfa/trust/__init__.pyc
%{python_sitelib}/gcf/sfa/trust/__init__.pyo
%{python_sitelib}/gcf/sfa/trust/abac_credential.py
%{python_sitelib}/gcf/sfa/trust/abac_credential.pyc
%{python_sitelib}/gcf/sfa/trust/abac_credential.pyo
%{python_sitelib}/gcf/sfa/trust/certificate.py
%{python_sitelib}/gcf/sfa/trust/certificate.pyc
%{python_sitelib}/gcf/sfa/trust/certificate.pyo
%{python_sitelib}/gcf/sfa/trust/credential.py
%{python_sitelib}/gcf/sfa/trust/credential.pyc
%{python_sitelib}/gcf/sfa/trust/credential.pyo
%{python_sitelib}/gcf/sfa/trust/credential_factory.py
%{python_sitelib}/gcf/sfa/trust/credential_factory.pyc
%{python_sitelib}/gcf/sfa/trust/credential_factory.pyo
%{python_sitelib}/gcf/sfa/trust/credential_legacy.py
%{python_sitelib}/gcf/sfa/trust/credential_legacy.pyc
%{python_sitelib}/gcf/sfa/trust/credential_legacy.pyo
%{python_sitelib}/gcf/sfa/trust/gid.py
%{python_sitelib}/gcf/sfa/trust/gid.pyc
%{python_sitelib}/gcf/sfa/trust/gid.pyo
%{python_sitelib}/gcf/sfa/trust/rights.py
%{python_sitelib}/gcf/sfa/trust/rights.pyc
%{python_sitelib}/gcf/sfa/trust/rights.pyo
%{python_sitelib}/gcf/sfa/util/__init__.py
%{python_sitelib}/gcf/sfa/util/__init__.pyc
%{python_sitelib}/gcf/sfa/util/__init__.pyo
%{python_sitelib}/gcf/sfa/util/enumeration.py
%{python_sitelib}/gcf/sfa/util/enumeration.pyc
%{python_sitelib}/gcf/sfa/util/enumeration.pyo
%{python_sitelib}/gcf/sfa/util/faults.py
%{python_sitelib}/gcf/sfa/util/faults.pyc
%{python_sitelib}/gcf/sfa/util/faults.pyo
%{python_sitelib}/gcf/sfa/util/genicode.py
%{python_sitelib}/gcf/sfa/util/genicode.pyc
%{python_sitelib}/gcf/sfa/util/genicode.pyo
%{python_sitelib}/gcf/sfa/util/sfalogging.py
%{python_sitelib}/gcf/sfa/util/sfalogging.pyc
%{python_sitelib}/gcf/sfa/util/sfalogging.pyo
%{python_sitelib}/gcf/sfa/util/sfatime.py
%{python_sitelib}/gcf/sfa/util/sfatime.pyc
%{python_sitelib}/gcf/sfa/util/sfatime.pyo
%{python_sitelib}/gcf/sfa/util/xrn.py
%{python_sitelib}/gcf/sfa/util/xrn.pyc
%{python_sitelib}/gcf/sfa/util/xrn.pyo
%{python_sitelib}/gcf/stitcher_logging.conf
%{python_sitelib}/gcf/stitcher_logging_deft.py
%{python_sitelib}/gcf/stitcher_logging_deft.pyc
%{python_sitelib}/gcf/stitcher_logging_deft.pyo
%doc %{_docdir}/%{name}/CHANGES
%doc %{_docdir}/%{name}/CONTRIBUTING.md
%doc %{_docdir}/%{name}/CONTRIBUTORS.md
%doc %{_docdir}/%{name}/INSTALL-centos.md
%doc %{_docdir}/%{name}/INSTALL.fedora
%doc %{_docdir}/%{name}/INSTALL.macos
%doc %{_docdir}/%{name}/INSTALL.txt
%doc %{_docdir}/%{name}/INSTALL.ubuntu
%doc %{_docdir}/%{name}/LICENSE.txt
%doc %{_docdir}/%{name}/README-clearpassphrases.txt
%doc %{_docdir}/%{name}/README-gcf.txt
%doc %{_docdir}/%{name}/README-omni.txt
%doc %{_docdir}/%{name}/README-omniconfigure.txt
%doc %{_docdir}/%{name}/README-stitching.txt
%doc %{_docdir}/%{name}/README.md
%doc %{_docdir}/%{name}/README.txt
%doc %{_docdir}/%{name}/TROUBLESHOOTING.txt
%doc %{_docdir}/%{name}/copyright
%{_datadir}/%{name}/agg_nick_cache.base
%{_datadir}/%{name}/clear-passphrases.py
%{_datadir}/%{name}/clear-passphrases.pyc
%{_datadir}/%{name}/clear-passphrases.pyo
%{_datadir}/%{name}/delegateSliceCred.py
%{_datadir}/%{name}/delegateSliceCred.pyc
%{_datadir}/%{name}/delegateSliceCred.pyo
%{_datadir}/%{name}/expirationofmyslices.py
%{_datadir}/%{name}/expirationofmyslices.pyc
%{_datadir}/%{name}/expirationofmyslices.pyo
%{_datadir}/%{name}/gcf-am.py
%{_datadir}/%{name}/gcf-am.pyc
%{_datadir}/%{name}/gcf-am.pyo
%{_datadir}/%{name}/gcf-ch.py
%{_datadir}/%{name}/gcf-ch.pyc
%{_datadir}/%{name}/gcf-ch.pyo
%{_datadir}/%{name}/gcf-test.py
%{_datadir}/%{name}/gcf-test.pyc
%{_datadir}/%{name}/gcf-test.pyo
%{_datadir}/%{name}/gcf_config.sample
%{_datadir}/%{name}/gen-certs.py
%{_datadir}/%{name}/gen-certs.pyc
%{_datadir}/%{name}/gen-certs.pyo
%{_datadir}/%{name}/myscript.py
%{_datadir}/%{name}/myscript.pyc
%{_datadir}/%{name}/myscript.pyo
%{_datadir}/%{name}/omni_config.sample
%{_datadir}/%{name}/omni_log_conf_sample.conf
%{_datadir}/%{name}/remote-execute.py
%{_datadir}/%{name}/remote-execute.pyc
%{_datadir}/%{name}/remote-execute.pyo
%{_datadir}/%{name}/renewSliceAndSlivers.py
%{_datadir}/%{name}/renewSliceAndSlivers.pyc
%{_datadir}/%{name}/renewSliceAndSlivers.pyo

%changelog
* Fri Jul 24 2015 Tom Mitchell <tmitchell@bbn.com> - 2.10-1%{?dist}
- TBD for version 2.10
* Thu Jun 4 2015 Tom Mitchell <tmitchell@bbn.com> - 2.9-1%{?dist}
- Initial RPM packaging
