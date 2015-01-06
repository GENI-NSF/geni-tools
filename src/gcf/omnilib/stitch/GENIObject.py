#----------------------------------------------------------------------
# Copyright (c) 2013-2015 Raytheon BBN Technologies
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

from __future__ import absolute_import

# Base class for objects, building on GMOC code

from .gmoc import GMOCObject, validateText

class GENIObject(GMOCObject):
    def __init__(self):
        pass
        # Could do this but really don't want anything but id
        # return super(GENIObject, self).__init__(id)
#        self.id = id

    def __str__(self):
        retVal = ""+str(self.__class__.__name__)
        if self.__dict__.has_key('__id'):
            retVal +="( "+str(self.__dict__['__id'])+" )"
        for key, value in self.__dict__.items():
            if key == "__id":
                continue
            retVal += "\n  "+str(key)+" : "+str(value)+""
        return retVal

# overwriting
def validateTextLike(urn):
    return str(urn)

