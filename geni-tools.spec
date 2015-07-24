%define _pydir /usr/lib/python2.6/site-packages

Name:           geni-tools
Version:        2.10
Release:        1%{?dist}
Summary:        GENI command line tools
BuildArch:      noarch
License:        GENI Public License
URL:            https://github.com/GENI-NSF/geni-tools
Source0:        https://github.com/GENI-NSF/geni-tools/releases/download/v2.10/geni-tools-2.10.tar.gz
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

%{_pydir}/gcf/__init__.py
%{_pydir}/gcf/__init__.pyc
%{_pydir}/gcf/__init__.pyo
%{_pydir}/gcf/gcf_version.py
%{_pydir}/gcf/gcf_version.pyc
%{_pydir}/gcf/gcf_version.pyo
%{_pydir}/gcf/geni/SecureThreadedXMLRPCServer.py
%{_pydir}/gcf/geni/SecureThreadedXMLRPCServer.pyc
%{_pydir}/gcf/geni/SecureThreadedXMLRPCServer.pyo
%{_pydir}/gcf/geni/SecureXMLRPCServer.py
%{_pydir}/gcf/geni/SecureXMLRPCServer.pyc
%{_pydir}/gcf/geni/SecureXMLRPCServer.pyo
%{_pydir}/gcf/geni/__init__.py
%{_pydir}/gcf/geni/__init__.pyc
%{_pydir}/gcf/geni/__init__.pyo
%{_pydir}/gcf/geni/am/__init__.py
%{_pydir}/gcf/geni/am/__init__.pyc
%{_pydir}/gcf/geni/am/__init__.pyo
%{_pydir}/gcf/geni/am/aggregate.py
%{_pydir}/gcf/geni/am/aggregate.pyc
%{_pydir}/gcf/geni/am/aggregate.pyo
%{_pydir}/gcf/geni/am/am2.py
%{_pydir}/gcf/geni/am/am2.pyc
%{_pydir}/gcf/geni/am/am2.pyo
%{_pydir}/gcf/geni/am/am3.py
%{_pydir}/gcf/geni/am/am3.pyc
%{_pydir}/gcf/geni/am/am3.pyo
%{_pydir}/gcf/geni/am/am_method_context.py
%{_pydir}/gcf/geni/am/am_method_context.pyc
%{_pydir}/gcf/geni/am/am_method_context.pyo
%{_pydir}/gcf/geni/am/api_error_exception.py
%{_pydir}/gcf/geni/am/api_error_exception.pyc
%{_pydir}/gcf/geni/am/api_error_exception.pyo
%{_pydir}/gcf/geni/am/fakevm.py
%{_pydir}/gcf/geni/am/fakevm.pyc
%{_pydir}/gcf/geni/am/fakevm.pyo
%{_pydir}/gcf/geni/am/proxyam.py
%{_pydir}/gcf/geni/am/proxyam.pyc
%{_pydir}/gcf/geni/am/proxyam.pyo
%{_pydir}/gcf/geni/am/resource.py
%{_pydir}/gcf/geni/am/resource.pyc
%{_pydir}/gcf/geni/am/resource.pyo
%{_pydir}/gcf/geni/am/test_ams.py
%{_pydir}/gcf/geni/am/test_ams.pyc
%{_pydir}/gcf/geni/am/test_ams.pyo
%{_pydir}/gcf/geni/am1.py
%{_pydir}/gcf/geni/am1.pyc
%{_pydir}/gcf/geni/am1.pyo
%{_pydir}/gcf/geni/auth/__init__.py
%{_pydir}/gcf/geni/auth/__init__.pyc
%{_pydir}/gcf/geni/auth/__init__.pyo
%{_pydir}/gcf/geni/auth/abac_authorizer.py
%{_pydir}/gcf/geni/auth/abac_authorizer.pyc
%{_pydir}/gcf/geni/auth/abac_authorizer.pyo
%{_pydir}/gcf/geni/auth/abac_resource_manager.py
%{_pydir}/gcf/geni/auth/abac_resource_manager.pyc
%{_pydir}/gcf/geni/auth/abac_resource_manager.pyo
%{_pydir}/gcf/geni/auth/argument_guard.py
%{_pydir}/gcf/geni/auth/argument_guard.pyc
%{_pydir}/gcf/geni/auth/argument_guard.pyo
%{_pydir}/gcf/geni/auth/authorizer_client.py
%{_pydir}/gcf/geni/auth/authorizer_client.pyc
%{_pydir}/gcf/geni/auth/authorizer_client.pyo
%{_pydir}/gcf/geni/auth/authorizer_server.py
%{_pydir}/gcf/geni/auth/authorizer_server.pyc
%{_pydir}/gcf/geni/auth/authorizer_server.pyo
%{_pydir}/gcf/geni/auth/base_authorizer.py
%{_pydir}/gcf/geni/auth/base_authorizer.pyc
%{_pydir}/gcf/geni/auth/base_authorizer.pyo
%{_pydir}/gcf/geni/auth/binders.py
%{_pydir}/gcf/geni/auth/binders.pyc
%{_pydir}/gcf/geni/auth/binders.pyo
%{_pydir}/gcf/geni/auth/resource_binder.py
%{_pydir}/gcf/geni/auth/resource_binder.pyc
%{_pydir}/gcf/geni/auth/resource_binder.pyo
%{_pydir}/gcf/geni/auth/sfa_authorizer.py
%{_pydir}/gcf/geni/auth/sfa_authorizer.pyc
%{_pydir}/gcf/geni/auth/sfa_authorizer.pyo
%{_pydir}/gcf/geni/auth/util.py
%{_pydir}/gcf/geni/auth/util.pyc
%{_pydir}/gcf/geni/auth/util.pyo
%{_pydir}/gcf/geni/ca.py
%{_pydir}/gcf/geni/ca.pyc
%{_pydir}/gcf/geni/ca.pyo
%{_pydir}/gcf/geni/ch.py
%{_pydir}/gcf/geni/ch.pyc
%{_pydir}/gcf/geni/ch.pyo
%{_pydir}/gcf/geni/config.py
%{_pydir}/gcf/geni/config.pyc
%{_pydir}/gcf/geni/config.pyo
%{_pydir}/gcf/geni/gch.py
%{_pydir}/gcf/geni/gch.pyc
%{_pydir}/gcf/geni/gch.pyo
%{_pydir}/gcf/geni/pgch.py
%{_pydir}/gcf/geni/pgch.pyc
%{_pydir}/gcf/geni/pgch.pyo
%{_pydir}/gcf/geni/util/__init__.py
%{_pydir}/gcf/geni/util/__init__.pyc
%{_pydir}/gcf/geni/util/__init__.pyo
%{_pydir}/gcf/geni/util/cert_util.py
%{_pydir}/gcf/geni/util/cert_util.pyc
%{_pydir}/gcf/geni/util/cert_util.pyo
%{_pydir}/gcf/geni/util/ch_interface.py
%{_pydir}/gcf/geni/util/ch_interface.pyc
%{_pydir}/gcf/geni/util/ch_interface.pyo
%{_pydir}/gcf/geni/util/cred_util.py
%{_pydir}/gcf/geni/util/cred_util.pyc
%{_pydir}/gcf/geni/util/cred_util.pyo
%{_pydir}/gcf/geni/util/error_util.py
%{_pydir}/gcf/geni/util/error_util.pyc
%{_pydir}/gcf/geni/util/error_util.pyo
%{_pydir}/gcf/geni/util/rspec_schema.py
%{_pydir}/gcf/geni/util/rspec_schema.pyc
%{_pydir}/gcf/geni/util/rspec_schema.pyo
%{_pydir}/gcf/geni/util/rspec_util.py
%{_pydir}/gcf/geni/util/rspec_util.pyc
%{_pydir}/gcf/geni/util/rspec_util.pyo
%{_pydir}/gcf/geni/util/secure_xmlrpc_client.py
%{_pydir}/gcf/geni/util/secure_xmlrpc_client.pyc
%{_pydir}/gcf/geni/util/secure_xmlrpc_client.pyo
%{_pydir}/gcf/geni/util/speaksfor_util.py
%{_pydir}/gcf/geni/util/speaksfor_util.pyc
%{_pydir}/gcf/geni/util/speaksfor_util.pyo
%{_pydir}/gcf/geni/util/tz_util.py
%{_pydir}/gcf/geni/util/tz_util.pyc
%{_pydir}/gcf/geni/util/tz_util.pyo
%{_pydir}/gcf/geni/util/urn_util.py
%{_pydir}/gcf/geni/util/urn_util.pyc
%{_pydir}/gcf/geni/util/urn_util.pyo
%{_pydir}/gcf/omnilib/__init__.py
%{_pydir}/gcf/omnilib/__init__.pyc
%{_pydir}/gcf/omnilib/__init__.pyo
%{_pydir}/gcf/omnilib/amhandler.py
%{_pydir}/gcf/omnilib/amhandler.pyc
%{_pydir}/gcf/omnilib/amhandler.pyo
%{_pydir}/gcf/omnilib/chhandler.py
%{_pydir}/gcf/omnilib/chhandler.pyc
%{_pydir}/gcf/omnilib/chhandler.pyo
%{_pydir}/gcf/omnilib/frameworks/__init__.py
%{_pydir}/gcf/omnilib/frameworks/__init__.pyc
%{_pydir}/gcf/omnilib/frameworks/__init__.pyo
%{_pydir}/gcf/omnilib/frameworks/framework_apg.py
%{_pydir}/gcf/omnilib/frameworks/framework_apg.pyc
%{_pydir}/gcf/omnilib/frameworks/framework_apg.pyo
%{_pydir}/gcf/omnilib/frameworks/framework_base.py
%{_pydir}/gcf/omnilib/frameworks/framework_base.pyc
%{_pydir}/gcf/omnilib/frameworks/framework_base.pyo
%{_pydir}/gcf/omnilib/frameworks/framework_chapi.py
%{_pydir}/gcf/omnilib/frameworks/framework_chapi.pyc
%{_pydir}/gcf/omnilib/frameworks/framework_chapi.pyo
%{_pydir}/gcf/omnilib/frameworks/framework_gcf.py
%{_pydir}/gcf/omnilib/frameworks/framework_gcf.pyc
%{_pydir}/gcf/omnilib/frameworks/framework_gcf.pyo
%{_pydir}/gcf/omnilib/frameworks/framework_gch.py
%{_pydir}/gcf/omnilib/frameworks/framework_gch.pyc
%{_pydir}/gcf/omnilib/frameworks/framework_gch.pyo
%{_pydir}/gcf/omnilib/frameworks/framework_gib.py
%{_pydir}/gcf/omnilib/frameworks/framework_gib.pyc
%{_pydir}/gcf/omnilib/frameworks/framework_gib.pyo
%{_pydir}/gcf/omnilib/frameworks/framework_of.py
%{_pydir}/gcf/omnilib/frameworks/framework_of.pyc
%{_pydir}/gcf/omnilib/frameworks/framework_of.pyo
%{_pydir}/gcf/omnilib/frameworks/framework_pg.py
%{_pydir}/gcf/omnilib/frameworks/framework_pg.pyc
%{_pydir}/gcf/omnilib/frameworks/framework_pg.pyo
%{_pydir}/gcf/omnilib/frameworks/framework_pgch.py
%{_pydir}/gcf/omnilib/frameworks/framework_pgch.pyc
%{_pydir}/gcf/omnilib/frameworks/framework_pgch.pyo
%{_pydir}/gcf/omnilib/frameworks/framework_sfa.py
%{_pydir}/gcf/omnilib/frameworks/framework_sfa.pyc
%{_pydir}/gcf/omnilib/frameworks/framework_sfa.pyo
%{_pydir}/gcf/omnilib/handler.py
%{_pydir}/gcf/omnilib/handler.pyc
%{_pydir}/gcf/omnilib/handler.pyo
%{_pydir}/gcf/omnilib/stitch/GENIObject.py
%{_pydir}/gcf/omnilib/stitch/GENIObject.pyc
%{_pydir}/gcf/omnilib/stitch/GENIObject.pyo
%{_pydir}/gcf/omnilib/stitch/ManifestRSpecCombiner.py
%{_pydir}/gcf/omnilib/stitch/ManifestRSpecCombiner.pyc
%{_pydir}/gcf/omnilib/stitch/ManifestRSpecCombiner.pyo
%{_pydir}/gcf/omnilib/stitch/RSpecParser.py
%{_pydir}/gcf/omnilib/stitch/RSpecParser.pyc
%{_pydir}/gcf/omnilib/stitch/RSpecParser.pyo
%{_pydir}/gcf/omnilib/stitch/VLANRange.py
%{_pydir}/gcf/omnilib/stitch/VLANRange.pyc
%{_pydir}/gcf/omnilib/stitch/VLANRange.pyo
%{_pydir}/gcf/omnilib/stitch/__init__.py
%{_pydir}/gcf/omnilib/stitch/__init__.pyc
%{_pydir}/gcf/omnilib/stitch/__init__.pyo
%{_pydir}/gcf/omnilib/stitch/defs.py
%{_pydir}/gcf/omnilib/stitch/defs.pyc
%{_pydir}/gcf/omnilib/stitch/defs.pyo
%{_pydir}/gcf/omnilib/stitch/gmoc.py
%{_pydir}/gcf/omnilib/stitch/gmoc.pyc
%{_pydir}/gcf/omnilib/stitch/gmoc.pyo
%{_pydir}/gcf/omnilib/stitch/launcher.py
%{_pydir}/gcf/omnilib/stitch/launcher.pyc
%{_pydir}/gcf/omnilib/stitch/launcher.pyo
%{_pydir}/gcf/omnilib/stitch/objects.py
%{_pydir}/gcf/omnilib/stitch/objects.pyc
%{_pydir}/gcf/omnilib/stitch/objects.pyo
%{_pydir}/gcf/omnilib/stitch/scs.py
%{_pydir}/gcf/omnilib/stitch/scs.pyc
%{_pydir}/gcf/omnilib/stitch/scs.pyo
%{_pydir}/gcf/omnilib/stitch/utils.py
%{_pydir}/gcf/omnilib/stitch/utils.pyc
%{_pydir}/gcf/omnilib/stitch/utils.pyo
%{_pydir}/gcf/omnilib/stitch/workflow.py
%{_pydir}/gcf/omnilib/stitch/workflow.pyc
%{_pydir}/gcf/omnilib/stitch/workflow.pyo
%{_pydir}/gcf/omnilib/stitchhandler.py
%{_pydir}/gcf/omnilib/stitchhandler.pyc
%{_pydir}/gcf/omnilib/stitchhandler.pyo
%{_pydir}/gcf/omnilib/util/__init__.py
%{_pydir}/gcf/omnilib/util/__init__.pyc
%{_pydir}/gcf/omnilib/util/__init__.pyo
%{_pydir}/gcf/omnilib/util/abac.py
%{_pydir}/gcf/omnilib/util/abac.pyc
%{_pydir}/gcf/omnilib/util/abac.pyo
%{_pydir}/gcf/omnilib/util/credparsing.py
%{_pydir}/gcf/omnilib/util/credparsing.pyc
%{_pydir}/gcf/omnilib/util/credparsing.pyo
%{_pydir}/gcf/omnilib/util/dates.py
%{_pydir}/gcf/omnilib/util/dates.pyc
%{_pydir}/gcf/omnilib/util/dates.pyo
%{_pydir}/gcf/omnilib/util/dossl.py
%{_pydir}/gcf/omnilib/util/dossl.pyc
%{_pydir}/gcf/omnilib/util/dossl.pyo
%{_pydir}/gcf/omnilib/util/faultPrinting.py
%{_pydir}/gcf/omnilib/util/faultPrinting.pyc
%{_pydir}/gcf/omnilib/util/faultPrinting.pyo
%{_pydir}/gcf/omnilib/util/files.py
%{_pydir}/gcf/omnilib/util/files.pyc
%{_pydir}/gcf/omnilib/util/files.pyo
%{_pydir}/gcf/omnilib/util/handler_utils.py
%{_pydir}/gcf/omnilib/util/handler_utils.pyc
%{_pydir}/gcf/omnilib/util/handler_utils.pyo
%{_pydir}/gcf/omnilib/util/json_encoding.py
%{_pydir}/gcf/omnilib/util/json_encoding.pyc
%{_pydir}/gcf/omnilib/util/json_encoding.pyo
%{_pydir}/gcf/omnilib/util/namespace.py
%{_pydir}/gcf/omnilib/util/namespace.pyc
%{_pydir}/gcf/omnilib/util/namespace.pyo
%{_pydir}/gcf/omnilib/util/omnierror.py
%{_pydir}/gcf/omnilib/util/omnierror.pyc
%{_pydir}/gcf/omnilib/util/omnierror.pyo
%{_pydir}/gcf/omnilib/util/paths.py
%{_pydir}/gcf/omnilib/util/paths.pyc
%{_pydir}/gcf/omnilib/util/paths.pyo
%{_pydir}/gcf/omnilib/xmlrpc/__init__.py
%{_pydir}/gcf/omnilib/xmlrpc/__init__.pyc
%{_pydir}/gcf/omnilib/xmlrpc/__init__.pyo
%{_pydir}/gcf/omnilib/xmlrpc/client.py
%{_pydir}/gcf/omnilib/xmlrpc/client.pyc
%{_pydir}/gcf/omnilib/xmlrpc/client.pyo
%{_pydir}/gcf/oscript.py
%{_pydir}/gcf/oscript.pyc
%{_pydir}/gcf/oscript.pyo
%{_pydir}/gcf/sfa/README.txt
%{_pydir}/gcf/sfa/__init__.py
%{_pydir}/gcf/sfa/__init__.pyc
%{_pydir}/gcf/sfa/__init__.pyo
%{_pydir}/gcf/sfa/trust/__init__.py
%{_pydir}/gcf/sfa/trust/__init__.pyc
%{_pydir}/gcf/sfa/trust/__init__.pyo
%{_pydir}/gcf/sfa/trust/abac_credential.py
%{_pydir}/gcf/sfa/trust/abac_credential.pyc
%{_pydir}/gcf/sfa/trust/abac_credential.pyo
%{_pydir}/gcf/sfa/trust/certificate.py
%{_pydir}/gcf/sfa/trust/certificate.pyc
%{_pydir}/gcf/sfa/trust/certificate.pyo
%{_pydir}/gcf/sfa/trust/credential.py
%{_pydir}/gcf/sfa/trust/credential.pyc
%{_pydir}/gcf/sfa/trust/credential.pyo
%{_pydir}/gcf/sfa/trust/credential_factory.py
%{_pydir}/gcf/sfa/trust/credential_factory.pyc
%{_pydir}/gcf/sfa/trust/credential_factory.pyo
%{_pydir}/gcf/sfa/trust/credential_legacy.py
%{_pydir}/gcf/sfa/trust/credential_legacy.pyc
%{_pydir}/gcf/sfa/trust/credential_legacy.pyo
%{_pydir}/gcf/sfa/trust/gid.py
%{_pydir}/gcf/sfa/trust/gid.pyc
%{_pydir}/gcf/sfa/trust/gid.pyo
%{_pydir}/gcf/sfa/trust/rights.py
%{_pydir}/gcf/sfa/trust/rights.pyc
%{_pydir}/gcf/sfa/trust/rights.pyo
%{_pydir}/gcf/sfa/util/__init__.py
%{_pydir}/gcf/sfa/util/__init__.pyc
%{_pydir}/gcf/sfa/util/__init__.pyo
%{_pydir}/gcf/sfa/util/enumeration.py
%{_pydir}/gcf/sfa/util/enumeration.pyc
%{_pydir}/gcf/sfa/util/enumeration.pyo
%{_pydir}/gcf/sfa/util/faults.py
%{_pydir}/gcf/sfa/util/faults.pyc
%{_pydir}/gcf/sfa/util/faults.pyo
%{_pydir}/gcf/sfa/util/genicode.py
%{_pydir}/gcf/sfa/util/genicode.pyc
%{_pydir}/gcf/sfa/util/genicode.pyo
%{_pydir}/gcf/sfa/util/sfalogging.py
%{_pydir}/gcf/sfa/util/sfalogging.pyc
%{_pydir}/gcf/sfa/util/sfalogging.pyo
%{_pydir}/gcf/sfa/util/sfatime.py
%{_pydir}/gcf/sfa/util/sfatime.pyc
%{_pydir}/gcf/sfa/util/sfatime.pyo
%{_pydir}/gcf/sfa/util/xrn.py
%{_pydir}/gcf/sfa/util/xrn.pyc
%{_pydir}/gcf/sfa/util/xrn.pyo
%{_pydir}/gcf/stitcher_logging.conf
%{_pydir}/gcf/stitcher_logging_deft.py
%{_pydir}/gcf/stitcher_logging_deft.pyc
%{_pydir}/gcf/stitcher_logging_deft.pyo
%doc %{_docdir}/%{name}/CHANGES
%doc %{_docdir}/%{name}/CONTRIBUTING.md
%doc %{_docdir}/%{name}/CONTRIBUTORS.md
%doc %{_docdir}/%{name}/INSTALL.centos
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
