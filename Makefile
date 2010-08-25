install:
	rm -rf build/
	python setup.py install

rpm:
	rm -rf build/
	rm MANIFEST
	python setup.py bdist_rpm

src:
	rm MANIFEST
	rm -rf build/
	python setup.py sdist

deb:
	python setup.py bdist_rpm
	# More to go here...

