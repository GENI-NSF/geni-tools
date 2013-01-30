#----------------------------------------------------------------------
# Copyright (c) 2013 Raytheon BBN Technologies
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
#from gmoc import * #GMOCObject
from gmoc import GMOCMeta, GMOCObject, validateText, validateURN


#class GENIObject(GMOCObject):
class GENIObject(GMOCObject):
#    __metaclass__ = GMOCMeta
#    def __init__(self, id ):
    def __init__(self):
        pass
        # Could do this but really don't want anything but id
        # return super(GENIObject, self).__init__(id)
#        self.id = id
    def __str__(self):
#        retVal = ""+str(self.__class__.__name__)+"( "+str(self.__dict__['__id'])+" )"
        retVal = ""+str(self.__class__.__name__)
        if self.__dict__.has_key('__id'):
            retVal +="( "+str(self.__dict__['__id'])+" )"
        for key, value in self.__dict__.items():
            if key == "__id":
                continue
            retVal += "\n  "+str(key)+" : "+str(value)+""
        return retVal

def validateInt( integer ):
    if type(integer) == int:
        return integer
    else:
        try:
            return int( integer )
        except:
            return None

def validateTrueFalse( boolean ):
    if type(boolean) == bool:
        return boolean
    else:
        try:
            boolean = str(boolean).lower()
            if boolean.strip().lower() in ("true", "t"):
                return True
            elif boolean.strip().lower() in ("false", "f"):
                return False
            else:
                return None
        except:
            return None

# overwriting
def validateTextLike(urn):
    return str(urn)

class URN(GENIObject):
    '''URN'''
    __metaclass__ = GMOCMeta
    __ID__ = validateURN
    def __init__(self, urn):
        self.id = urn
    def __str__(self):
        print self.id

class TrueFalse(GENIObject):
    '''boolean'''
    __metaclass__ = GMOCMeta
    __ID__ = validateTrueFalse
    def __init__(self, boolean):
        self.id = boolean
    def __str__(self):
        print self.id

class TextLike(unicode):
    '''TextLike'''
    __ID__ = validateText
    def __init__(self, text):
        self.id = text


class GENIObjectWithIDURN(GENIObject):
    __metaclass__ = GMOCMeta
    __ID__ = validateInt

    def __init__(self, id, urn=None):
        super(GENIObjectWithIDURN, self).__init__()
        self.id = id
        self._urn = urn

    @property
    def urn(self):
        return self._urn

    @urn.setter
    def urn(self, value):
        if value != None:
            if type(value) == URN:
                self._urn = value
            elif isinstance(value, str):
                self._urn = URN( value )
            else:
                raise TypeError("urn must be a valid URN")
        else:
            self._urn = None
        
