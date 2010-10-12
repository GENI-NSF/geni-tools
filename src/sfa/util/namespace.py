#----------------------------------------------------------------------
# Copyright (c) 2008 Board of Trustees, Princeton University
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
### $Id$
### $URL$
import re
from sfa.util.faults import *
URN_PREFIX = "urn:publicid:IDN"

def __get_hierarchy_delim_indexes(hrn):
    # find all non escaped '.'
    hierarchy_delim = '([a-zA-Z0-9][\.])'
    parts = re.findall(hierarchy_delim, hrn)
    # list of indexes for every  hierarchy delimieter
    indexes = []
    for part in parts:
        indexes.append(hrn.index(part) + 1)
    return indexes 

def get_leaf(hrn):
    delim_indexes = __get_hierarchy_delim_indexes(hrn)
    if not delim_indexes:
        return hrn
    
    last_delim_index = delim_indexes[-1:][0] + 1
    return hrn[last_delim_index:] 

def get_authority(xrn):
    hrn, type = urn_to_hrn(xrn)
    if type and type == 'authority':
        return hrn
  
    delim_indexes = __get_hierarchy_delim_indexes(hrn)
    if not delim_indexes:
        return ''
    last_delim_index = delim_indexes[-1:][0] 
    return hrn[:last_delim_index] 
    
def hrn_to_pl_slicename(hrn):
    # remove any escaped no alpah numeric characters
    #hrn = re.sub('\\\[^a-zA-Z0-9]', '', hrn)
    hrn = re.sub(r'\\(.)', '', hrn)
    parts = hrn.split(".")
    return parts[-2] + "_" + parts[-1]

# assuming hrn is the hrn of an authority, return the plc authority name
def hrn_to_pl_authname(hrn):
    # remove any escaped no alpah numeric characters
    hrn = re.sub(r'\\(.)', '', hrn)
    parts = hrn.split(".")
    return parts[-1]

# assuming hrn is the hrn of an authority, return the plc login_base
def hrn_to_pl_login_base(hrn):
    # remove any escaped no alpah numeric characters
    hrn = re.sub(r'\\(.)', '', hrn)
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
    urn_parts = name.split("+")
    type = urn_parts.pop(2)
    
         
    # Remove the authority name (e.g. '.sa')
    if type == 'authority':
        urn_parts = urn_parts[:-1]

    # convert hrn_parts (list) into hrn (str) by doing the following
    # 1. remove blank elements
    # 2. escape all non alpha numeric chars (excluding ':')
    # 3. replace ':' with '.'  (':' is the urn hierarchy delimiter)
    # 4. join list elements using '.' 
    #hrn = '.'.join([part.replace('.', '\\.').replace(':', '.') for part in hrn_parts if part]) 
    hrn = '.'.join([re.sub(r'([^a-zA-Z0-9\:])', r'\\\1', part).replace(':', '.') for part in urn_parts if part]) 
    
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
  
    # convert from hierarchy delimiter from '.' to ':'   
    authority = re.sub(r'([a-zA-Z0-9])[\.]', r'\1:', authority) 
    # unescape escaped characters
    authority = re.sub(r'\\(.)', r'\1', authority)
    
    if type == None:
        urn = "+".join(['',authority,name])
    else:
        urn = "+".join(['',authority,type,name])

        
    return URN_PREFIX + urn
