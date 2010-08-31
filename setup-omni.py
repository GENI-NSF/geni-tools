from distutils.core import setup
setup(name='omni',
      version="1.0.1",
      package_dir={'': 'src/'},      
      packages=['geni.omni','geni.omni.frameworks','geni.omni.omnispec', 'geni.omni.util', 'geni.omni.xmlrpc'],     
      scripts=['src/omni.py'],
      author='gpo',
      author_email='help@geni.net',
      url='http://www.geni.net',
      provides=['omni',],
      )
