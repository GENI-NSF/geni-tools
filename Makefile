install:
	python setup.py install

rpm:
	python setup.py bdist_rpm

src:
	python setup.py sdist

deb:
	python setup.py bdist_rpm
	# More to go here...

