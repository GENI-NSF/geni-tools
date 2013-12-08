# coding: utf-8
# ====================================================================
#  GENI Meta-Operations Objects
#  gmoc.py
#
#  Classes for communicating with the GENI Meta-Operations Center
#
#  Created by the Indiana University GlobalNOC <syseng@grnoc.iu.edu>
#
#  Copyright (C) 2012, Trustees of Indiana University
#    All Rights Reserved
#
#  Permission is hereby granted, free of charge, to any person 
#  obtaining a copy of this software and/or hardware specification 
#  (the “Work”) to deal in the Work without restriction, including
#  without limitation the rights to use, copy, modify, merge, 
#  publish, distribute, sublicense, and/or sell copies of the Work, 
#  and to permit persons to whom the Work is furnished to do so, 
#  subject to the following conditions:
#
#  The above copyright notice and this permission notice shall be 
#  included in all copies or substantial portions of the Work.
#
#  THE WORK IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, 
#  EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES 
#  OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
#  NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
#  HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
#  WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING 
#  FROM, OUT OF OR IN CONNECTION WITH THE WORK OR THE USE OR OTHER 
#  DEALINGS IN THE WORK.
# ====================================================================

# File edited to exclude most unused code

import re

# Version
GMOC_CLIENT_VERSION       = '1.2.0'

# stolen from Stanford University
URN_PREFIX = 'urn:publicid:IDN'

# stolen from Raytheon BBN Technologies
# Translate publicids to URN format.
# The order of these rules matters
# because we want to catch things like double colons before we
# translate single colons. This is only a subset of the rules.
# See the GENI Wiki: GAPI_Identifiers
# See http://www.faqs.org/rfcs/rfc3151.html
publicid_xforms = [('%',  '%25'),
                   (';',  '%3B'),
                   ('+',  '%2B'),
                   (' ',  '+'  ), # note you must first collapse WS
                   ('#',  '%23'),
                   ('?',  '%3F'),
                   ("'",  '%27'),
                   ('::', ';'  ),
                   (':',  '%3A'),
                   ('//', ':'  ),
                   ('/',  '%2F')]

# I haven't worked an honest day in my life
def isValidURN(urn):
    if not isinstance(urn, str):
        return False

    if re.search("[\s|\?\/]", urn) is None:
        if urn.startswith(URN_PREFIX):
            return True

    return False 

# finally some GRNOC code
def validateText(urn):
    return urn
   
def validateURN(urn):
    if isValidURN(str(urn)):
        return str(urn)

    return None

# --------------------------------------------------------------------

def _getObjID():
    return lambda self: getattr(self, '__id')

def _setObjID(validator):
    def __setObjID(self, value):
        if not validator is None:
            validVal = validator(value)
            if not validVal is None:
                self.__id = validVal
            else:
                raise ValueError("identifier could not be validated")
        else:
            self.__id = value

    return __setObjID

def _getProp(propName):
    return lambda self: getattr(self, '__' + propName)

def _setProp(propName, propType):
    def __setProp(self, value):
        oldVal = getattr(self, '__' + propName)
        if not value is None:
            if not isinstance(value, propType):
                raise TypeError(propName + " (" + str(value) +") must be of type '" + propType.__name__ + "' instead it is of type '" + str(type(value).__name__) +"'")
        
        setattr(self, '__' + propName, value)
    
    return __setProp

# --------------------------------------------------------------------

class GMOCObject(object):
    """Base class for GMOC objects"""

    def __init__(self, id):
        self.id = id

    def _setListProp(self, propName, propValue, propType, propRefSetter = None):
        # make sure we really have a list
        if not isinstance(propValue, list):
            raise TypeError(propName + " must be a list")

        # unset the reference to this object in our current list
        # in case the new list doesn't intersect
        if propRefSetter != None:
            currentList = getattr(self, '_' + propName)
            for element in currentList:
                setattr(element, propRefSetter, None)

            for element in propValue:
                if isinstance(element, propType):
                    setattr(element, propRefSetter, self)
                else:
                    raise TypeError("all elements in " + propName + " must be of type " + propType.__name__)

        setattr(self, '_' + propName, propValue)

    def validate(self):
        if self.id == None:
            raise ValueError("Object must have a valid identifier")


