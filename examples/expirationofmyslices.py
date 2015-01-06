#!/usr/bin/env python

#----------------------------------------------------------------------
# Copyright (c) 2011-2015 Raytheon BBN Technologies
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and/or hardware specification (the "Work") to
# deal in the Work without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Work, and to permit persons to whom the Work
# is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Work.
#
# THE WORK IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE WORK OR THE USE OR OTHER DEALINGS
# IN THE WORK.
#----------------------------------------------------------------------

import sys
import gcf.oscript as omni

################################################################################
# Requires that you have omni installed or the path to gcf/src in your
# PYTHONPATH.
#
# For example put the following in your bashrc:
#     export PYTHONPATH=${PYTHONPATH}:path/to/gcf/src
#
################################################################################

def main(argv=None):
  ##############################################################################
  # Get a parser from omni that understands omni options
  ##############################################################################
  parser = omni.getParser()
  parser.set_usage("%s [options] username"%sys.argv[0])
  options, args = omni.parse_args(sys.argv[1:], parser=parser)

  # pull username from the command line
  if len(args) > 0:
    username = args[0].strip()
  else:
    username = None
#    if not username:
#      sys.exit( "Must provide a username as the first argument of script" )

  ##############################################################################
  # And now call omni, and omni sees your parsed options and arguments
  # (1) Run equivalent of 'omni.py listmyslices username'
  # (2) For each returned slicename run equivalent of: 
  #        'omni.py print_slice_expiration slicename'
  ##############################################################################
  # (1) Run equivalent of 'omni.py listmyslices username'
  if username:
    text, sliceList = omni.call( ['listmyslices', username], options )
  else:
    text, sliceList = omni.call( ['listmyslices'], options )
    username = "(you)"
  
  #  print some summary info
  printStr = "="*80+"\n"
  if len(sliceList)>0:
    printStr += "User %s has %d slice(s):\n"%(username, len(sliceList))
  else:
    printStr += "User %s has NO slices\n"%(username)

  # (2) For each returned slicename run equivalent of: 
  #        'omni.py print_slice_expiration slicename'
  
  for slicename in sliceList:
    omniargs = []
    omniargs.append('print_slice_expiration')
    omniargs.append(slicename)
    text, expiration = omni.call( omniargs, options )        

    printStr += "%s\n"%(str(expiration))
  printStr += "="*80            
  return printStr

if __name__ == "__main__":
  sys.exit(main())
