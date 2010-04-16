### $Id: namespace.py 17618 2010-04-08 18:44:31Z jkarlin $
### $URL: http://svn.planet-lab.org/svn/sfa/branches/geni-api/sfa/util/namespace.py $

from sfa.util.faults import *

URN_PREFIX = "urn:publicid:IDN"

def get_leaf(hrn):
    parts = hrn.split(".")
    return ".".join(parts[-1:])

def get_authority(xrn):
    hrn, type = urn_to_hrn(xrn)
    if type and type == 'authority':
        return hrn
    
    parts = hrn.split(".")
    return ".".join(parts[:-1])

def hrn_to_pl_slicename(hrn):
    parts = hrn.split(".")
    return parts[-2] + "_" + parts[-1]

# assuming hrn is the hrn of an authority, return the plc authority name
def hrn_to_pl_authname(hrn):
    parts = hrn.split(".")
    return parts[-1]

# assuming hrn is the hrn of an authority, return the plc login_base
def hrn_to_pl_login_base(hrn):
    return hrn_to_pl_authname(hrn)

def hostname_to_hrn(auth_hrn, login_base, hostname):
    """
    Convert hrn to plantelab name.
    """
    sfa_hostname = ".".join([auth_hrn, login_base, hostname.split(".")[0]])
    return sfa_hostname

def slicename_to_hrn(auth_hrn, slicename):
    """
    Convert hrn to planetlab name.
    """
    parts = slicename.split("_")
    slice_hrn = ".".join([auth_hrn, parts[0]]) + "." + "_".join(parts[1:])

    return slice_hrn

def email_to_hrn(auth_hrn, email):
    parts = email.split("@")
    username = parts[0]
    username = username.replace(".", "_").replace("+", "_") 
    person_hrn = ".".join([auth_hrn, username])
    
    return person_hrn 

def urn_to_hrn(urn):
    """
    convert a urn to hrn
    return a tuple (hrn, type)
    """

    # if this is already a hrn dont do anything
    if not urn or not urn.startswith(URN_PREFIX):
        return urn, None

    name = urn[len(URN_PREFIX):]
    hrn_parts = name.split("+")
    
    # type is always the second to last element in the list
    type = hrn_parts.pop(-2)

    # convert hrn_parts (list) into hrn (str) by doing the following    
    # remove blank elements
    # replace ':' with '.'
    # join list elements using '.'
    hrn = '.'.join([part.replace(':', '.') for part in hrn_parts if part]) 
   
    return str(hrn), str(type) 
    
    
def hrn_to_urn(hrn, type=None):
    """
    convert an hrn and type to a urn string
    """
    # if  this is already a urn dont do anything 
    if not hrn or hrn.startswith(URN_PREFIX):
        return hrn

    authority = get_authority(hrn)
    name = get_leaf(hrn)
    urn = "+".join([unicode(part).replace('.', ':') \
                    for part in ['',authority,type,name]])

    return URN_PREFIX + urn
