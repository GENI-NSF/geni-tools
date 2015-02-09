#!/usr/bin/env python

#----------------------------------------------------------------------
# Copyright (c) 2012-2015 Raytheon BBN Technologies
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

import os
import pprint
import re
import sys

import gcf.oscript as omni
from gcf.omnilib.util.omnierror import OmniError
from gcf.omnilib.util.files import *
  

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
  parser.set_usage(omni_usage+"\nmyscript.py supports additional commands.\n\n\tCommands and their arguments are:\n\t\t\t[add stuff here]")

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
  options, args = omni.parse_args(sys.argv[1:], parser=parser)
  if options.myScriptPrivateOption:
    # do something special for your private script's options
    print "Got myScriptOption"



  ##############################################################################
  # Try to read 2nd argument as an RSpec filename. Pull the AM URL and
  # and maybe slice name from that file.
  # Then construct omni args appropriately: command, slicename, action or rspecfile or datetime
  ##############################################################################
  omniargs = []
  if args and len(args)>1:
    sliceurn = None
    # Try to read args[1] as an RSpec filename to read
    rspecfile = args[1]
    rspec = None
    if rspecfile:
      print "Looking for slice name and AM URL in RSpec file %s" % rspecfile
      try:
        rspec = readFile(rspecfile)
      except:
        print "Failed to read rspec from '%s'. Not an RSpec? Will try to get AM/slice from args." % rspecfile

    if rspec:
    # Now parse the comments, whch look like this:
#<!-- Resources at AM:
#	URN: unspecified_AM_URN
#	URL: https://localhost:8001
# -->
# Reserved resources for:\n\tSlice: %s
# at AM:\n\tURN: %s\n\tURL: %s

      if not ("Resources at AM" in rspec or "Reserved resources for" in rspec):
        sys.exit("Could not find slice name or AM URL in RSpec '%s'" % rspec)
      amurn = None
      amurl = None
      # Pull out the AM URN and URL
      match = re.search(r"at AM:\n\tURN: (\S+)\n\tURL: (\S+)\n", rspec)
      if match:
        amurn = match.group(1)
        amurl = match.group(2)
        print "  Found AM %s (%s)" % (amurn, amurl)
        omniargs.append("-a")
        omniargs.append(amurl)

      # Pull out the slice name or URN if any
      if "Reserved resources for" in rspec:
        match = re.search(r"Reserved resources for:\n\tSlice: (\S+)\n\t", rspec)
        if match:
          sliceurn = match.group(1)
          print "  Found slice %s" % sliceurn

    command = args[0]
    rest = []
    if len(args) > 2:
      rest = args[2:]

    # If the command requires a slice and we didn't get a readable rspec from the rspecfile,
    # Then treat that as the slice
    if not sliceurn and rspecfile and not rspec:
      sliceurn = rspecfile
      rspecfile = None

    # construct the args in order
    omniargs.append(command)
    if sliceurn:
      omniargs.append(sliceurn)
    if rspecfile and command.lower() in ('createsliver', 'allocate'):
      omniargs.append(rspecfile)
    for arg in rest:
      omniargs.append(arg)
  elif len(args) == 1:
    omniargs = args
  else:
    print "Got no command or rspecfile. Run '%s -h' for more information."%sys.argv[0]
    return

  ##############################################################################
  # And now call omni, and omni sees your parsed options and arguments
  ##############################################################################
  print "Call Omni with args %s:\n" % omniargs
  try:
    text, retItem = omni.call(omniargs, options)
  except OmniError, oe:
    sys.exit("\nOmni call failed: %s" % oe)

  print "\nGot Result from Omni:\n"

  # Process the dictionary returned in some way
  if isinstance(retItem, dict):
    import json
    print json.dumps(retItem, ensure_ascii=True, indent=2)
  else:
    print pprint.pformat(retItem)

  # Give the text back to the user
  print text

  if type(retItem) == type({}):
    numItems = len(retItem.keys())
  elif type(retItem) == type([]):
    numItems = len(retItem)
  elif retItem is None:
    numItems = 0
  else:
    numItems = 1
  if numItems:
    print "\nThere were %d item(s) returned." % numItems

if __name__ == "__main__":
  sys.exit(main())
