#!/usr/bin/python
#----------------------------------------------------------------------
# Copyright (c) 2011 Raytheon BBN Technologies
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

# Used for empty slice name
class InvalidSliceNameException(Exception):
    def __init__(self):
        pass
    def __str__(self):
        return "Invalid Slice Name"

# Unused
class InvalidRSpecException(Exception):
    def __init__(self):
        pass
    def __str__(self):
        return "Invalid RSpec File"

class RSpecRestrictionException(Exception):
    def __init__(self,rspecName):
        self.rspecName = rspecName
        pass
    def __str__(self):
        return "Unable to calculate Restrictions for AM: "+str(self.rspecName)

class RSpecDependencyException(Exception):
    def __init__(self):
        pass
    def __str__(self):
        return "Invalid RSpec File"

class TopologyCalculationException(Exception):
    def __init__(self,msg):
        self.msg = msg
        pass
    def __str__(self):
        return "Unable to calculate topology: "+str(self.msg)

class UnknownAggrURLException(Exception):
    def __init__(self,aggrURL):
        self.aggrURL = aggrURL
        pass
    def __str__(self):
        return "Supplied aggregate is unknown: "+str(self.aggrURL)
