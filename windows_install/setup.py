from distutils.core import setup

import py2exe
import sys

setup(console=['..\src\omni.py','..\src\omni-configure.py', '..\examples/readyToLogin.py', '..\src\clear-passphrases.py'],
      name="omni",

      options={
          'py2exe':{
              'includes':'omnilib.frameworks.framework_apg, omnilib.frameworks.framework_base,\
omnilib.frameworks.framework_gcf, omnilib.frameworks.framework_gch,\
omnilib.frameworks.framework_gib, omnilib.frameworks.framework_of,\
omnilib.frameworks.framework_pg, omnilib.frameworks.framework_pgch,\
 omnilib.frameworks.framework_sfa,omnilib,sfa,dateutil,geni,\
 copy,ConfigParser,logging,optparse,os,sys,string,re,platform,shutil,zipfile,logging,subprocess',
              }
            }
        )
