from distutils.core import setup

import py2exe
import sys

setup(console=['C:\Program Files\gcf\gcf-2.4\src\omni-configure.py'],
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
