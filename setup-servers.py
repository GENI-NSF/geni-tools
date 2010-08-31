from distutils.core import setup
setup(name='gcf-servers',
      version="1.0.1",
      package_dir={'': 'src'},                   
      py_modules=['gcf-ch','gcf-am','gcf-test','gen-certs','geni.am','geni.ch'],
      author='gpo',
      author_email='help@geni.net',
      url='http://www.geni.net',
      requires=['gcf_lib',],
      )
