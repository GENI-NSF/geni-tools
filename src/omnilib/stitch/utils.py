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
from omnilib.util import OmniError

class StitchingError(OmniError):
    '''Errors due to stitching problems'''
    pass

class StitchingCircuitFailedError(StitchingError):
    '''A given stitching attempt failed, but a different circuit from the SCS might work.'''
    pass

class StitchingRetryAggregateNewVlanError(StitchingError):
    '''Allocation at a single AM failed cause VLAN unavailable. Try a different tag locally before going to the SCS.'''
    pass

class StitchingServiceFailedError(StitchingError):
    '''SCS service returned an error.'''
    def __init__(self, msg=None, struct=None):
        self.value = msg
        self.returnstruct = struct
        # FIXME: gen a message from struct and make that arg here
        StitchingError.__init__(self, struct)

#    def __repr__(self):
    def __str__(self):
        if not self.returnstruct:
            return super(StitchingServiceFailedError, self).__repr__()
        message = "StitchingServiceFailedError: "
        if self.value:
            message += self.value
            message += "\n"
        retStruct = self.returnstruct

        if isinstance(retStruct, dict) and retStruct.has_key('code'):
            if retStruct['code'].has_key('geni_code') and retStruct['code']['geni_code'] != 0:
                message2 = "Error from Stitching Service: code " + str(retStruct['code']['geni_code'])
            if retStruct.has_key('output'):
                message2 += ": %s" % retStruct['output']
            message += "%s" % message2
        return message
    pass

def stripBlankLines(strWithBlanks):
    '''Remove any blank lines from the given string'''
    if not strWithBlanks:
        return strWithBlanks
    if strWithBlanks.strip() == '':
        return ''
    lines = strWithBlanks.splitlines()
    str2 = ''
    for line in lines:
        l = line.strip()
        if l != '':
            str2 = str2 + line + '\n'
    return str2
