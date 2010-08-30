install:
	rm -rf build/
	python setup.py install

rpm:
	rm -rf build/ ;\
	rm MANIFEST;\
	python setup.py bdist_rpm

source:
	rm MANIFEST ;\
	rm -rf build/ ;\
	python setup.py sdist

deb: rpm
	VER=`perl -n -e 'print $$1 if /version="(.*)",/ ' setup.py` ; \
	cp dist/gcf-$$VER-1.noarch.rpm build/ ;\
	cd build ;\
	rm -rf gcf-$$VER ;\
	alien --generate --scripts gcf-$$VER-1.noarch.rpm ;\
	cd gcf-$$VER/debian ;\
	perl -p -i -e 's/Depends.*/Depends: python2.6, m2crypto, libxmlsec1-dev, libxmlsec1-openssl, xmlsec1, python2.6-libxslt1, python-zsi, python2.6-lxml, python2.6-setuptools, python-dateutil/' control ;\
	cd .. ;\
	dpkg-buildpackage -rfakeroot;\
	cd ..;\
	cp *.deb ../dist/ ;\

