install: servers-install lib-install

servers-install: clean
	python setup-servers.py install

lib-install: clean
	python setup-lib.py install



clean: servers-clean lib-clean
	rm MANIFEST ;\
	rm -rf build/ ;\

servers-clean:
	python setup-servers.py clean

lib-clean:
	python setup-lib.py clean
	




	



source: servers-source lib-source

servers-source: clean
	python setup-servers.py sdist

lib-source: clean
	python setup-lib.py sdist -t MANIFEST.in.lib






rpm: lib-rpm servers-rpm

servers-rpm: clean
	cp MANIFEST.in.servers MANIFEST.in ;\
	python setup-servers.py bdist_rpm --requires="gcf-lib" ;\
	rm MANIFEST.in

lib-rpm: clean
	cp MANIFEST.in.lib MANIFEST.in ;\
	python setup-lib.py bdist_rpm --requires="python=2.6 m2crypto xmlsec1-openssl-devel libxslt-python python-ZSI python-lxml python-setuptools python-dateutil" ;\
	rm MANIFEST.in



	
deb: lib-deb servers-deb

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
	