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
  # update usage for help message
  omni_usage = parser.get_usage()
  parser.set_usage(omni_usage+"\nmyscript.py supports additional commands.\n\n\tCommands and their arguments are:\n\t\t\tdoNonNativeList [optional: slicename]")

  ##############################################################################
  # Add additional optparse.OptionParser style options for your
  # script as needed.
  # Be sure not to re-use options already in use by omni for
  # different meanings, otherwise you'll raise an OptionConflictError
  ##############################################################################
  parser.add_option("--myScriptPrivateOption",
                    help="A non-omni option added by %s"%sys.argv[0],
                    action="store_true", default=False)
  # options is an optparse.Values object, and args is a list
  options, args = parser.parse_args(sys.argv[1:])
  if options.myScriptPrivateOption:
    # do something special for your private script's options
    print "Got myScriptOption"



  ##############################################################################
  # figure out that doNonNativeList means to do listresources with the
  # --omnispec argument and parse out slicename arg
  ##############################################################################
  omniargs = []
  if args and len(args)>0:
    if args[0] == "doNonNativeList":
      print "Doing omnispec listing"
      omniargs.append("--omnispec")
      omniargs.append("listresources")
      if len(args)>1:
        print "Got slice name %s" % args[1]
        slicename=args[1]
        omniargs.append(slicename)
    else:
      omniargs = args
  else:
    print "Got no command. Run '%s -h' for more information."%sys.argv[0]
    return

  ##############################################################################
  # And now call omni, and omni sees your parsed options and arguments
  ##############################################################################
  text, retItem = omni.call(omniargs, options)

  # Process the dictionary returned in some way
  print retItem

  # Give the text back to the user
  print text

  if type(retItem) == type({}):
    numItems = len(retItem.keys())
  elif type(retItem) == type([]):
    numItems = len(retItem)
  if numItems:
    print "\nThere were %d items returned." % numItems

if __name__ == "__main__":
  sys.exit(main())
