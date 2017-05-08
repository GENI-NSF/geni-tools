#----------------------------------------------------------------------
# Copyright (c) 2010-2016 Raytheon BBN Technologies
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
'''
URN creation and verification utilities.
'''

import re
from ...sfa.util.xrn import Xrn # for URN_PREFIX

class URN(object):
    """ 
    A class that creates and extracts values from URNs
    URN Convention:
    urn:publicid:IDN+<authority>+<type>+<name>
    Authority, type, and name are public ids transcribed into URN format
    By convention a CH's name should be "ch" and an AM's should be "am"
    The authority of the CH should be the prefix for all of your AM and user authorities
    For instance: CH authority = "gcf//gpo//bbn", AM authority = "gcf//gpo/bbn//am1", user authority = "gcf//gpo//bbn"
    
    EXAMPLES:
        
    ch_urn = URN("gcf//gpo//bbn", "authority", "sa").urn_string() for a clearinghouse URN
    am1_urn = URN("gcf//gpo//bbn//site1", "authority", "am").urn_string() for an AM at this authority
        Looks like urn:publicid:IDN+gcf:gpo:bbn:site1+authority+am
    am2_urn = URN("gcf//gpo//bbn//site2", "authority", "am").urn_string() for a second AM at this authority
        Looks like urn:publicid:IDN+gcf:gpo:bbn:site2+authority+am
    user_urn = URN("gcf//gpo//bbn", "user", "jane").urn_string() for a user made by the clearinghouse    
        Looks like urn:publicid:IDN+gcf:gpo:bbn+user+jane
    slice_urn = URN("gcf//gpo//bbn", "slice", "my-great-experiment").urn_string()
        Looks like urn:publicid:IDN+gcf:gpo:bbn+slice+my-great-experiment
    resource_at_am1_urn = URN("gcf//gpo//bbn/site1", "node", "LinuxBox23").urn_string() for Linux Machine 23 managed by AM1 (at site 1)
        Looks like urn:publicid:IDN+gcf:gpo:bbn:site1+node+LinuxBox23
    """
    def __init__(self, authority=None, type=None, name=None, urn=None):
        if not urn is None:
            if not is_valid_urn(urn):
                raise ValueError("Invalid URN %s" % urn)
        
            spl = urn.split('+')
            if len(spl) < 4:
                raise ValueError("Invalid URN %s" % urn)
            self.authority = urn_to_string_format(spl[1])
            self.type = urn_to_string_format(spl[2])
            self.name = urn_to_string_format('+'.join(spl[3:]))
            self.urn = urn
        else:
            if not authority or not type or not name:
                raise ValueError("Must provide either all of authority, type, and name, or a urn must be provided")
            
            
            for i in [authority, type, name]:
                if i.strip() == '':
                    raise ValueError("Parameter to create_urn was empty string")
            
            self.authority = authority
            self.type = type
            self.name = name

            # FIXME: check these are valid more?
            if not is_valid_urn_string(authority):
                authority = string_to_urn_format(authority)
            if not is_valid_urn_string(type):
                type = string_to_urn_format(type)
            if not is_valid_urn_string(name):
                name = string_to_urn_format(name)
            
            self.urn = '%s+%s+%s+%s' % (Xrn.URN_PREFIX, authority, type, name)
            if not is_valid_urn(self.urn):
                raise ValueError("Failed to create valid URN from args %s, %s, %s" % (self.authority, self.type, self.name))
    
    def __str__(self):
        return self.urn_string()
    
    def urn_string(self):
        return self.urn
    
    def getAuthority(self):
        '''Get the authority in un-escaped publicid format'''
        return self.authority
    def getType(self):
        '''Get the URN type in un-escaped publicid format'''
        return self.type
    def getName(self):
        '''Get the name in un-escaped publicid format'''
        return self.name
    
    
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

# FIXME: See sfa/util/xrn/Xrn.URN_PREFIX which is ...:IDN
publicid_urn_prefix = 'urn:publicid:'    
    
def nameFromURN(instr):
    '''Get the name from the given URN, or empty if not a valid URN'''
    if not instr:
        return ""
    try:
        urn = URN(urn=instr)
        return urn.getName()
    except Exception, e:
#        print 'exception parsing urn: %s' % e
        return ""

# validate urn
# Note that this is not sufficient but it is necessary
def is_valid_urn_string(instr):
    '''Could this string be part of a URN'''
    if instr is None or not (isinstance(instr, str) or
                             isinstance(instr, unicode)):
        return False
    #No whitespace
    # no # or ? or /
    if isinstance(instr, unicode):
        instr = instr.encode('utf8')
    if re.search("[\s|\?\/\#]", instr) is None:
        return True
    return False

# Note that this is not sufficient but it is necessary
def is_valid_urn(inurn):
    ''' Check that this string is a valid URN'''
    # FIXME: This could pull out the type and do the type specific
    # checks that are currently below
    # FIXME: This should check for non empty authority and name pieces
    return is_valid_urn_string(inurn) and \
        inurn.startswith(publicid_urn_prefix) and \
        len(inurn.split('+')) > 3

def is_valid_urn_bytype(inurn, urntype, logger=None):
    if not is_valid_urn(inurn):
        return False
    urnObj = URN(urn=inurn)
    if not urntype:
        urntype = ""
    urntype = urntype.lower()
    if not urnObj.getType().lower() == urntype:
        if logger:
            logger.warn("URN %s not of right type: %s, not %s", inurn, urnObj.getType().lower(), urntype)
        return False
    if len(urnObj.getAuthority()) == 0:
        if logger:
            logger.warn("URN %s has empty authority", inurn)
        return False
    name = urnObj.getName()
    if urntype == 'slice':
        # Slice names are <=19 characters, only alphanumeric plus hyphen (no hyphen in first character): '^[a-zA-Z0-9][-a-zA-Z0-9]{0,18}$'
        if len(name) > 19:
            if logger:
                logger.warn("URN %s too long. Slice names are max 19 characters", inurn)
            return False
        if not re.match("^[a-zA-Z0-9][-a-zA-Z0-9]{0,18}$", name):
            if logger:
                logger.warn("Slice names may only be alphanumeric plus hyphen (no leading hyphen): %s", name)
            return False
    elif urntype == 'sliver':
        # May use only alphanumeric characters plus hyphen
        # Note that EG uses a ':' as well.
        if not re.match("^[-a-zA-Z0-9_\.]+$", name):
            if logger:
                logger.warn("Sliver names may only be alphanumeric plus hyphen, underscore, or period: %s", name)
            return False
    elif urntype == 'user':
        # Usernames should begin with a letter and be alphanumeric or underscores; no hyphen or '.': ('^[a-zA-Z][\w]{0,7}$').
        # Usernames are limited to 8 characters.
        if len(name) > 8:
            if logger:
                logger.warn("URN %s too long. User names are max 8 characters", inurn)
            return False
        if not re.match("^[a-zA-Z][\w]{0,7}$", name):
            if logger:
                logger.warn("User names may only be alphanumeric plus underscore, beginning with a letter: %s", name)
            return False
    elif len(name) == 0:
        if logger:
            logger.warn("Empty name in URN %s", inurn)
        return False
    return True

def urn_to_publicid(urn):
    '''Convert a URN like urn:publicid:... to a publicid'''
    # Remove prefix
    if urn is None or not is_valid_urn(urn):
        # Erroneous urn for conversion
        raise ValueError('Invalid urn: ' + urn)
    publicid = urn[len(publicid_urn_prefix):]
    # return the un-escaped string
    return urn_to_string_format(publicid)

def publicid_to_urn(id):
    '''Convert a publicid to a urn like urn:publicid:.....'''
    # prefix with 'urn:publicid:' and escape chars
    return publicid_urn_prefix + string_to_urn_format(id)

def string_to_urn_format(instr):
    '''Make a string URN compatible, collapsing whitespace and escaping chars'''
    if instr is None or instr.strip() == '':
        raise ValueError("Empty string cant be in a URN")
    # Collapse whitespace
    instr = ' '.join(instr.strip().split())
    for a, b in publicid_xforms:
        instr = instr.replace(a, b)
    return instr

def urn_to_string_format(urnstr):
    '''Turn a part of a URN into publicid format, undoing transforms'''
    if urnstr is None or urnstr.strip() == '':
        return urnstr
    publicid = urnstr
    # Validate it is reasonable URN string?
    for a, b in reversed(publicid_xforms):
        publicid = publicid.replace(b, a)
    return publicid
