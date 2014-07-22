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

import datetime
import dateutil.parser
import gcf.sfa.trust.gid as gid
import gcf.sfa.trust.credential as credential
import types
import xml.dom.minidom

# Class to provide requested resource states
# so that the authorizer can enforce resource quota policies

class Base_Resource_Manager:
    
    def __init__(self):
        pass

    # Return a list of proposed allocated slivers
    # with sliver_urn, slice_urn, user_urn, start_time, end_time plus a list
    # of all masurements about the sliver
    # {meas : value}
    # e.g.
    # [
    #   {'sliver_urn' : sliver1, 'slice_urn' : slice1, 'user_urn' : user1, 
    #    'start_time' : t0, 'end_time' : t1',
    #     'measurements' : {'M1' : 3, 'M2' : 4}}
    #   ...
    # ]
    def get_requested_allocation_state(self, aggregate_manager, 
                                       arguments, options,  creds):
        return []

# Class for a Resource Manager for the GCF AM
# We only compute a single metric, i.e. NODE (the number of nodes allocated)
class GCFAM_Resource_Manager(Base_Resource_Manager):

    def __init__(self):
        Base_Resource_Manager.__init__(self)

    # Return combindation of current and requested allocations
    # *** Needs to handle renew
    def get_requested_allocation_state(self, aggregate_manager,
                                       arguments, options, creds):
        curr_allocations = \
            self.get_current_allocations(aggregate_manager, arguments, 
                                         options, creds)
        req_allocations = \
            self.get_requested_allocations(aggregate_manager, arguments, 
                                           options, creds)

        return curr_allocations + req_allocations

    # Get all current slivers and return them in proper format
    def get_current_allocations(self, aggregate_manager,
                                arguments, options, credentials):

        sliver_info = []
        slices = aggregate_manager._delegate._slices
        user_urn = gid.GID(string=options['geni_true_caller_cert']).get_urn()

        for slice_urn, slice_obj in slices.items():
            for sliver in slice_obj.slivers():
                entry = {'sliver_urn' : sliver.urn(),
                         'slice_urn' : slice_urn,
                         'user_urn' : user_urn,
                         'start_time' : str(sliver.startTime()),
                         'end_time' : str(sliver.endTime()),
                         'measurements' : {'NODE' : 1}}
                sliver_info.append(entry)

        return sliver_info

    # Take the given rspec (if provided) and determine how
    # many nodes are being requested over what time ranges
    # and compute the sliver info accordingly
    def get_requested_allocations(self, aggregate_manager, 
                                  arguments, options, credentials):
        if 'rspec' not in arguments: return []
        if 'slice_urn' not in arguments: return []

        amd = aggregate_manager._delegate

        sliver_info = []
        slice_urn = arguments['slice_urn']
        user_urn = gid.GID(string=options['geni_true_caller_cert']).get_urn()

        start_time = datetime.datetime.utcnow()
        if 'geni_start_time' in options:
            raw_start_time = options['geni_start_time']
            start_time = amd._naiveUTC(dateutil.parser.parse(raw_start_time))

        creds = [credential.Credential(string=c) for c in credentials]
        if 'geni_end_time' in options:
            raw_end_time = options['geni_end_time']
            end_time = amd.min_expire(creds, requested=raw_end_time)
        else:
            end_time = amd.min_expire(creds)

        rspec_raw = arguments['rspec']
        rspec = xml.dom.minidom.parseString(rspec_raw)
        nodes = rspec.getElementsByTagName('node')
        for node in nodes:
                entry = {'sliver_urn' : 'not_set_yet',
                         'slice_urn' : slice_urn,
                         'user_urn' : user_urn,
                         'start_time' : str(start_time),
                         'end_time' : str(end_time),
                         'measurements' : {'NODE' : 1}}
                sliver_info.append(entry)

        return sliver_info

        

