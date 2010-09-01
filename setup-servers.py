from distutils.core import setup
setup(name='gcf-servers',
      version="1.0.1",
      package_dir={'': 'src'},                   
      py_modules=['geni.am','geni.ch','geni.config'],
      data_files=[('/etc/gcf-servers', ['gcf_config'])],
      scripts=['src/gcf-ch.py','src/gcf-am.py','src/gcf-test.py','src/gen-certs.py'],
      author='gpo',
      author_email='help@geni.net',
      url='http://www.geni.net',
      requires=['gcf_lib',],
      provides=['gcf_servers'],
      )
