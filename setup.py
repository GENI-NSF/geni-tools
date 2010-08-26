from distutils.core import setup
setup(name='gcf',
      version="1.0b1",
      package_dir={'': 'src'},                   
      packages=['geni.util','sfa','sfa.trust','sfa.util'],
      py_modules=['geni.__init__', 'geni.SecureXMLRPCServer'],
      author='gpo',
      author_email='help@geni.net',
      url='http://www.geni.net',
      )
