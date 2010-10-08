### $Id$
### $URL$
import re
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
    # remove any escaped no alpah numeric characters
    #hrn = re.sub('\\\[^a-zA-Z0-9]', '', hrn)
    # remove any escaped '.' (i.e. '\.')
    hrn = hrn.replace('\\.', '')
    parts = hrn.split(".")
    return parts[-2] + "_" + parts[-1]

# assuming hrn is the hrn of an authority, return the plc authority name
def hrn_to_pl_authname(hrn):
    # remove any escaped '.' (i.e. '\.')
    hrn = hrn.replace('\\.', '')
    parts = hrn.split(".")
    return parts[-1]

# assuming hrn is the hrn of an authority, return the plc login_base
def hrn_to_pl_login_base(hrn):
    # remove any escaped '.' (i.e. '\.')
    hrn = hrn.replace('\\.', '')
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
    type = hrn_parts.pop(2)
    
         
    # Remove the authority name (e.g. '.sa')
    if type == 'authority':
        hrn_parts = hrn_parts[:-1]

    # convert hrn_parts (list) into hrn (str) by doing the following
    # 1. remove blank elements
    # 2. escape '.'            # '.' exists in protogeni object names and are not delimiters
    # 3. replace ':' with '.'  # ':' is the urn hierarchy delimiter
    # 4. join list elements using '.' 
    hrn = '.'.join([part.replace('.', '\\.').replace(':', '.') for part in hrn_parts if part]) 
    
    return str(hrn), str(type) 
    
    
def hrn_to_urn(hrn, type=None):
    """
    convert an hrn and type to a urn string
    """
    # if  this is already a urn dont do anything 
    if not hrn or hrn.startswith(URN_PREFIX):
        return hrn

    if type == 'authority':
        authority = hrn
        name = 'sa'   
    else:
        authority = get_authority(hrn)
        name = get_leaf(hrn)   
   
    # We have to do the following conversion
    # '\\.'  -> '.'    # where '.' belongs in the urn name
    # '.'    -> ':"    # where ':' is the urn hierarchy delimiter
    # by doing the following
    # 1. split authority around '\\.'
    # 2. replace '.' with ':' in all parts
    # 3. join parts around '.'  
    parts = authority.split('\\.')
    authority = '.'.join([part.replace('.', ':') for part in parts])
    
    if type == None:
        urn = "+".join(['',authority,name])
    else:
        urn = "+".join(['',authority,type,name])

        
    return URN_PREFIX + urn
