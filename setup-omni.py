from distutils.core import setup
setup(name='omni',
      version="1.0.1",
      package_dir={'': 'src/'},      
      packages=['omnilib','omnilib.frameworks','omnilib.omnispec', 'omnilib.util', 'omnilib.xmlrpc'],     
      scripts=['src/omni.py'],
      author='gpo',
      author_email='help@geni.net',
      url='http://www.geni.net',
      provides=['omni',],
      )
