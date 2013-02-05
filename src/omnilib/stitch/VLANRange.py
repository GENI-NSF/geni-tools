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

class VLANRange( set ):
    def __init__( self, vlan=None ):
        if vlan is None:
            super( VLANRange, self).__init__()                    
        elif type(vlan) in (VLAN, int):
            super( VLANRange, self).__init__([vlan])                    
        elif type(vlan) in (list, tuple):
            retRange = VLANRange()
            for item in vlan:
                newItem = VLAN(item)
                retRange.add( newItem )
            super( VLANRange, self).__init__(vlan)                    
        elif type(vlan) in (VLANRange):
            super( VLANRange, self).__init__(vlan)                    
        else:
            raise TypeError("Value must be one of 'int', 'VLAN', or 'VLANRange' instead is '%s'" % type(vlan))

        
    @classmethod
    def _isValidVLAN( cls, other ):
        if type(other) in (VLANRange, VLAN):
            return True
        else:
            return False
    
    # Inherit from parent object (set):
    #   __contains__, __sub__, __and__, __eq__
    def __add__( self, other ):
        newRange = VLANRange( other )
        super( VLANRange, self).__add__(newRange)                    

    def fromString( self, string ):
        # Valid inputs are like:
        #   any
        #   1-20
        #   1-20, 454, 700-801
        pass

    def toString( self ):
        pass
    

if __name__ == "__main__":
#    a = VLAN( -1000 )
#    b = VLAN( -1 )
    c = VLAN( 0 )
    d = VLAN( 1 )
    e = VLAN( 2 )
    f = VLAN( 500 )
    g = VLAN( 4095 )
#    h = VLAN( 4096 )
#    i = VLAN( 10000 )
#    j = VLAN( "abc" )
#    k = VLAN( {} )
#    l = VLAN( VLAN(100) )

    VLANRange()
    VLANRange( 3 )
    VLANRange( VLAN(3) )
    VLANRange( VLANRange(3) )
