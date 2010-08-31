install: servers-install lib-install omni-install

servers-install: clean
	python setup-servers.py install

lib-install: clean
	python setup-lib.py install

omni-install: clean
	python setup-omni.py install


clean: servers-clean lib-clean omni-clean
	rm MANIFEST ;\
	rm -rf build/ ;\

servers-clean:
	python setup-servers.py clean

lib-clean:
	python setup-lib.py clean
	
omni-clean:
	python setup-omni.py clean



	



source: servers-source lib-source omni-source

servers-source: clean
	python setup-servers.py sdist -t MANIFEST.in.servers

lib-source: clean
	python setup-lib.py sdist -t MANIFEST.in.lib

omni-source: clean
	python setup-omni.py sdist -t MANIFEST.in.omni




rpm: lib-rpm servers-rpm omni-rpm

servers-rpm: clean
	cp MANIFEST.in.servers MANIFEST.in ;\
	python setup-servers.py bdist_rpm --requires="gcf-lib" ;\
	rm MANIFEST.in

lib-rpm: clean
	cp MANIFEST.in.lib MANIFEST.in ;\
	python setup-lib.py bdist_rpm --requires="python=2.6 m2crypto xmlsec1-openssl-devel libxslt-python python-ZSI python-lxml python-setuptools python-dateutil" ;\
	rm MANIFEST.in
	
omni-rpm: clean
	cp MANIFEST.in.omni MANIFEST.in ;\
	python setup-omni.py bdist_rpm --requires="gcf-lib";\
	rm MANIFEST.in



	
deb: lib-deb servers-deb omni-deb

lib-deb: lib-rpm
	VER=`perl -n -e 'print $$1 if /version="(.*)",/ ' setup-lib.py` ; \
	cp dist/gcf-lib-$$VER-1.noarch.rpm build/ ;\
	cd build ;\
	rm -rf gcf-lib-$$VER ;\
	alien --generate --scripts gcf-lib-$$VER-1.noarch.rpm ;\
	cd gcf-lib-$$VER/debian ;\
	perl -p -i -e 's/Depends.*/Depends: python2.6, m2crypto, libxmlsec1-dev, libxmlsec1-openssl, xmlsec1, python2.6-libxslt1, python-zsi, python2.6-lxml, python2.6-setuptools, python-dateutil/' control ;\
	cd .. ;\
	dpkg-buildpackage -rfakeroot;\
	cd ..;\
	cp *.deb ../dist/ ;\
	
servers-deb: servers-rpm
	VER=`perl -n -e 'print $$1 if /version="(.*)",/ ' setup-servers.py` ; \
	cp dist/gcf-servers-$$VER-1.noarch.rpm build/ ;\
	cd build ;\
	rm -rf gcf-servers-$$VER ;\
	alien --generate --scripts gcf-servers-$$VER-1.noarch.rpm ;\
	cd gcf-servers-$$VER/debian ;\
	perl -p -i -e 's/Depends.*/Depends: gcf-lib/' control ;\
	cd .. ;\
	dpkg-buildpackage -rfakeroot;\
	cd ..;\
	cp *.deb ../dist/ ;\
	
omni-deb: omni-rpm
	VER=`perl -n -e 'print $$1 if /version="(.*)",/ ' setup-omni.py` ; \
	cp dist/omni-$$VER-1.noarch.rpm build/ ;\
	cd build ;\
	rm -rf omni-$$VER ;\
	alien --generate --scripts omni-$$VER-1.noarch.rpm ;\
	cd omni-$$VER/debian ;\
	perl -p -i -e 's/Depends.*/Depends: gcf-lib/' control ;\
	cd .. ;\
	dpkg-buildpackage -rfakeroot;\
	cd ..;\
	cp *.deb ../dist/ ;\
