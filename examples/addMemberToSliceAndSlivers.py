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

# Add the given user (by portal username, not email address or
# username at their IdP) to the given slice.
# Also add that user and their SSH keys to all existing slivers (where
# performoperationalaction geni_update_users is supported).
# Will operate on all slivers registered at the CH (slivers reserved
# through Omni), plus any extras you specify with a -a argument

# Assumptions
# - user has SSH keys registered at the portal
# - your omni_config uses framework type `chapi`
# - AM supports poa geni_update_users

# Note that ExoGENI AMs do not support poa geni_update_users

# Usage: addMemberToSliceAndSlivers.py <slicename> <username>

import datetime
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
  parser.set_usage(omni_usage+"\naddMemberToSliceAndSlivers.py adds " + 
                   "the given member to the given slice and installs " +
                   "their SSH keys on all slivers known to the CH plus at all specified aggregates.\n " +
                   "Takes slice name and username as arguments")

  # options is an optparse.Values object, and args is a list
  options, args = omni.parse_args(sys.argv[1:], parser=parser)

  if len(args) < 2:
    print "Usage: addMemberToSliceAndSlivers.py <slicename> <username>"
    sys.exit(-1)

  sliceName = args[0]
  userName = args[1]
  omniargs = ['addslicemember', sliceName, userName]

  print "Calling Omni to add %s to slice %s\n" % (userName, sliceName)
  try:
    text, retItem = omni.call(omniargs, options)
    if not retItem:
      print "\nFailed to add member to slice: %s" % text
      sys.exit(-1)
  except OmniError, oe:
    print "\nOmni call failed: %s\n" % oe
    sys.exit(-1)
  print text
  print "\n"

  omniargs = ['--useSliceMembers', '--ignoreConfigUsers', '--useSliceAggregates', '-V3', 'poa', sliceName, 'geni_update_users']
  print "Calling Omni to add %s SSH keys to slice %s slivers\n" % (userName, sliceName)
  try:
    text, retItem = omni.call(omniargs, options)
  except OmniError, oe:
    print "\nOmni call failed: %s\n" % oe
    sys.exit(-1)
  print text
  print "\n"


if __name__ == "__main__":
  sys.exit(main())
