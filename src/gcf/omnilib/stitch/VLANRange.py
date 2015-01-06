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
'''Utility classes to represent a VLAN tag and a VLAN range'''

class VLAN( int ):
    # VLANs are [0, 4095] (inclusive)
    # Worry about reserved VLANs? 0, 1, 4095?
    __minvlan = 0
    __maxvlan = 4095
    
    def __init__( self, value ):
        if type(value) is VLAN:
            super(VLAN, self).__init__(value)        
        elif type(value) is not int:
            raise TypeError("Value must be of type 'int' instead is of type '%s'" % type(value))
        elif value < self.__minvlan:
            raise TypeError("Int must be >= %s instead is %s" % (self.__minvlan, value))
        elif value > self.__maxvlan:
            raise TypeError("Int must be <= %s instead is %s" % (self.__maxvlan, value))
        super(VLAN, self).__init__(value)        

    @classmethod
    def minvlan(cls):
        return cls.__minvlan

    @classmethod
    def maxvlan(cls):
        return cls.__maxvlan

class VLANRange( set ):
    '''A set of ints or VLANs representing a range of VLAN tags.'''
    def __init__( self, vlan=None ):
        if vlan is None:
            super( VLANRange, self).__init__()
        elif isinstance(vlan, VLAN) or isinstance(vlan, int):
            super( VLANRange, self).__init__([vlan])
        elif isinstance(vlan, list) or isinstance(vlan, tuple):
            retRange = VLANRange()
            for item in vlan:
                newItem = VLAN(item)
                retRange.add( newItem )
            super( VLANRange, self).__init__(vlan)
        elif isinstance(vlan, set):
            super( VLANRange, self).__init__(vlan)
        elif isinstance(vlan, VLANRange):
            super( VLANRange, self).__init__(vlan)
        else:
            raise TypeError("Value must be one of 'int', 'VLAN', or 'VLANRange' instead is '%s'" % type(vlan))

        
    @classmethod
    def _isValidVLAN( cls, other ):
        if isinstance(other, VLANRange) or isinstance(other, VLAN):
            return True
        else:
            return False
    
    # Inherit from parent object (set):
    #   __contains__, __sub__, __and__, __eq__
    # FIXME: set has no __add__. There is __and__ or add, but no __add__. What is intended here?
#    def __add__( self, other ):
#        newRange = VLANRange( other )
#        super( VLANRange, self).__add__(newRange)                    

    @classmethod
    def fromString( cls, stringIn ):
        '''Construct a VLAN range from a string like: 'any', '1,5,7,10-15'''
        # Valid inputs are like:
        #   any
        #   1-20
        #   1-20, 454, 700-801
        newObj = VLANRange()

        inputs = str(stringIn).strip()
        if inputs == "":
            return newObj
        items = inputs.split(",")
        for item in items:
            splitItem = item.split("-")
            parsedItems = [parse.strip().lower() for parse in splitItem]
#            print parsedItems
            minValue = -1
            maxValue = -1
            if len(parsedItems) == 1:                
                first = parsedItems[0]
                try:
                    minValue = int(first)
                    maxValue = minValue
                except:
                    if (type(first) is str) and ((first == "any") or (first == "") or (first == "*")):
                            minValue = VLAN.minvlan()
                            maxValue = VLAN.maxvlan()
                    else:
                        raise ValueError("String value must be 'any', a integer, or a range of integers instead is %s " % str(parsedItems))
            elif len(parsedItems) == 2:
                intItems = [int(integer) for integer in parsedItems]
                first, second = intItems
                if (type(first) is int) and (type(second) is int):
                    minValue, maxValue = first, second
                else:
                    raise ValueError("Both values must be integers instead received %s " % str(item))
            else:
                raise ValueError("Range should contain at most 2 values instead received %s " % str(item))
#            print minValue, maxValue
            for newVLAN in xrange(minValue,maxValue+1):
                newObj.add( newVLAN )
        return newObj

    def __str__( self ):
        out = ""
        if len(self) == 0:
            return out
        hasNum = False
        min = VLAN.maxvlan()+1
        max = VLAN.minvlan()-1
        for num in sorted(self):
            if min <= VLAN.maxvlan() and (max+1) == num:
                max = num
                continue
            elif min <= VLAN.maxvlan() and num > max+1:
                if hasNum:
                    out += ','
                if max > min+1:
                    out += str(min)+'-'+str(max)
                    hasNum = True
                else:
                    out += str(min)
                    hasNum = True
                    if max > min:
                        out += ',' + str(max)
                min = num
                max = num
                continue
            else:
                min = num
                max = num
        if hasNum:
            out += ','
        if min == VLAN.minvlan() and max == VLAN.maxvlan():
            out = 'any'
        elif max > min+1:
            out += str(min)+'-'+str(max)
        else:
            out += str(min)
            if max > min:
                out += ',' + str(max)
        return out


if __name__ == "__main__":
    print "\nSome operations on VLANRanges...\n"

#    a = VLANRange( 3 )
    a = VLANRange.fromString("3,4-6,8")
    print "a is: "+str(a)
    b = VLANRange( 8 )
    print "b is: "+str(b)
    c = VLANRange( 8 )
    print "c is: "+str(c)

    print "\nIs VLAN 3 in the range of a? (True)"
    print VLAN(3) in a
    print 3 in a
    print "\nIs VLAN 2 in the range of a? (False)"
    print VLAN(2) in a
    print 2 in a

    print "\nIntersection of a and b? ( VLANRange([8]) )"
    print a & b
    print a.intersection(b)

    print "\nIs a == b? (False)"
    print a == b
    print "\nIs c == b? (True)"
    print c == b

    print "\nNew range with an int removed from it"
    print a - b
    print "Type of new object is: "+ str(type(a - b).__name__)


    # e = VLANRange.fromString("")
    # print "\ne is: "+str(e)

    # d = VLANRange()
    # d = VLANRange.fromString("any")
    # print "d is: "+str(d)

    # print "\nIntersection of a and d? ( VLANRange([8]) )"
    # print a.intersection(d)
    
