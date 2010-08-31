from distutils.core import setup
setup(name='omni',
      version="1.0.1",
      package_dir={'': 'src/geni'},      
      packages=['omni','omni.frameworks','omni.omnispec', 'omni.util', 'omni.xmlrpc'],     
      py_modules=['omni'],        
      author='gpo',
      author_email='help@geni.net',
      url='http://www.geni.net',
      requires=['gcf_lib',],
      provides=['omni',],
      )
