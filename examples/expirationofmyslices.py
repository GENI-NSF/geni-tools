#!/usr/bin/python
import sys
import omni

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
  options, args = parser.parse_args(sys.argv[1:])

  # pull username from the command line
  if len(args) > 0:
    username = args[0]
  else:
    sys.exit( "Must provide a username as the first argument of script" )

  ##############################################################################
  # And now call omni, and omni sees your parsed options and arguments
  # (1) Run equivalent of 'omni.py listmyslices username'
  # (2) For each returned slicename run equivalent of: 
  #        'omni.py print_slice_expiration slicename'
  ##############################################################################
  # (1) Run equivalent of 'omni.py listmyslices username'
  text, sliceList = omni.call( ['listmyslices', username], options )        
  
  #  print some summary info
  printStr = "="*80+"\n"
  if len(sliceList)>0:
    printStr += "User %s has %d slices\n"%(username, len(sliceList))
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
