from distutils.core import setup

import py2exe
import sys

setup(console=['..\src\omni-configure.py', '..\examples/readyToLogin.py', '..\src\clear-passphrases.py'],
      name="omni-configure",

      py_modules=['sfa','ConfigParser','logging','optparse',
                  'os','sys','string',
                  're','platform','shutil','zipfile','logging','subprocess'],
      

 #     options={
 #         'py2exe':{
 #             'includes':'sfa.trust.certificate,ConfigParser,logging,optparse\
 #               ,os,sys,string,re,platform,shutil,zipfile,logging'
  #            }
  #        }
      
        )
