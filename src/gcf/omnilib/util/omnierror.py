#----------------------------------------------------------------------
# Copyright (c) 2011-2015 Raytheon BBN Technologies
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

class OmniError(Exception):
    """Simple Exception wrapper marking fatal but anticipated omni
    errors (EG missing arguments, error in input file).

    Omni function callers typically catch these, then print the
    message but not the stack trace.

    """
    pass

class NoSliceCredError(OmniError):
    """Errors due to a lack of slice credentials."""
    pass

class RefusedError(OmniError):
    """Errors due to an AM refusal. geni_code=7."""
    pass

class AMAPIError(OmniError):
    '''Raise an Exception if the AM returned an AM API v2+ non-0 error code.
    Include the full code/value/output struct in the error.'''
    def __init__(self, msg=None, struct=None):
        self.value = msg
        self.returnstruct = struct
        # FIXME: gen a message from struct and make that arg here
        OmniError.__init__(self, struct)

#    def __repr__(self):
    def __str__(self):
        if not self.returnstruct:
            return super(AMAPIError, self).__repr__()
        message = "AMAPIError: "
        if self.value:
            message += self.value
            message += "\n"
        retStruct = self.returnstruct

        if isinstance(retStruct, dict) and retStruct.has_key('code'):
            if retStruct['code'].has_key('geni_code') and retStruct['code']['geni_code'] != 0:
                message2 = "Error from Aggregate: code " + str(retStruct['code']['geni_code'])
            amType = ""
            if retStruct['code'].has_key('am_type'):
                amType = retStruct['code']['am_type']
            if retStruct['code'].has_key('am_code'):
                message2 += ". %s AM code: %s" % (amType, str(retStruct['code']['am_code']))
            if retStruct.has_key('output'):
                message2 += ": %s" % retStruct['output']
            message2 += "."
            message += "%s" % message2
        return message
