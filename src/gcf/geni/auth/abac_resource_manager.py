#----------------------------------------------------------------------       
# Copyright (c) 2010-2014 Raytheon BBN Technologi
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

# Class to provide current and requested resources
# so that the authorizer can enforce resource quota policies

import xml.dom.minidom
import types

class Base_Resource_Manager:
    
    def __init__(self):
        pass

    # Return a dictionary of all resource types
    # currently allocated, by allocating user and slice
    # e.g.
    # { "NODE" : { "by_user" : {user1 : num1, user2 : num2, ...},
    #              "by_slice" : {slice1 : num1, slice2 : num2, ...}},
    #   "LINK" : { "by_user" : {user1 : num1, user2 : num2, ...},
    #              "by_slice" : {slice1 : num1, slice2 : num2, ...}},
    #   ...
    #   }
    def get_current_allocations(self, aggregate_manager):
        return {}

    # Return a dictionary of all requested resource (from a request_rspec)
    # by type
    # e.g.
    # {"NODE" : num_nodes, "LINK" : num_links}
    def get_requested_allocations(self, aggregate_manager, args):
        return {}

class GCFAM_Resource_Manager(Base_Resource_Manager):

    def __init__(self):
        Base_Resource_Manager.__init__(self)

    def get_current_allocations(self, aggregate_manager):

        by_slice_info = {}
        by_user_info = {}
        slices = aggregate_manager._delegate._slices
        for slice_urn, slice_obj in slices.items():
            if hasattr(slice_obj, 'resources') and \
                    type(slice_obj.resources) == types.MethodType:
                resources = slice_obj.resources()
            else:
                resources = slice_obj.resources
            by_slice_info[slice_urn] = len(resources)

        containers = aggregate_manager._delegate._agg.containers
        for urn, slivers in containers.items():
            if urn.find("+slice+") >= 0:
                # It is a slice_urn
                by_slice_info[urn] = len(slivers)
            else:
                # It is a user URN
                by_user_info[urn] = len(slivers)

        resource_info = {}
        resource_info['NODE'] = {'by_slice' : by_slice_info, 
                                 'by_user' : by_user_info}

        return resource_info


    # *** Need to get this from GCF AM (or the AM as it is)
    def get_requested_allocations(self, aggregate_manager, args):
        if 'rspec' not in args: return {}

        resource_info = {}

        rspec_raw = args['rspec']
        rspec = xml.dom.minidom.parseString(rspec_raw)
        nodes = rspec.getElementsByTagName('node')
        resource_info['NODE'] = len(nodes)

        return resource_info

        


        
