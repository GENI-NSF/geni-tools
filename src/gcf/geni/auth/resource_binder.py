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

from .util import *

# A class to compute resource bindings from a set of 
# sliver entries. We take only those slivers that match the 
# current user/slice/project/authority context and update their
# state accordingly.

# We create the following bindings:
# $<DOMAIN>_<METRIC>_<STAT>
# where 
#   DOMAIN is USER, SLICE, PROJECT or AUTHORITY
#   METRIC is the metric defined in provided sliver allocation info
#   STAT is TOTAL [Sum of metrics of all relevant slivers]
#           HOURS [Sum metric * (end_time - start_time) of relevant slivers]
#           MAX [Maximum concurrent total metric over relevant slivers

class ResourceBinder:

    def __init__(self, user_urn, slice_urn, project_urn, authority_urn):
        self._user_urn = user_urn
        self._slice_urn = slice_urn
        self._project_urn = project_urn
        self._authority_urn = authority_urn

        self._measurement_states = {}

    # For a given sliver, try to update measurement for each aspect 
    def updateForSliver(self, sliver_info):
        sliver_urn = sliver_info['sliver_urn']
        slice_urn = sliver_info['slice_urn']
        user_urn = sliver_info['user_urn']
        start_time = sliver_info['start_time']
        end_time = sliver_info['end_time']
        measurements = sliver_info['measurements']

        project_urn = convert_slice_urn_to_project_urn(slice_urn)
        authority_urn = convert_user_urn_to_authority_urn(user_urn)

        self._update_sliver(slice_urn, self._slice_urn, 'SLICE', 
                            start_time, end_time, measurements)
        self._update_sliver(user_urn, self._user_urn, 'USER', 
                            start_time, end_time, measurements)
        self._update_sliver(project_urn, self._project_urn, 'PROJECT', 
                            start_time, end_time, measurements)
        self._update_sliver(authority_urn, self._authority_urn, 'AUTHORITY', 
                            start_time, end_time, measurements)

    # Update measurements based on a sliver if it is relevant 
    # to our calling context
    def _update_sliver(self, sliver_context_urn, self_urn, urn_type, 
                       start_time, end_time, measurements):
        # If this isn't a sliver we care about, ignore
        if sliver_context_urn == None \
                or self_urn == None \
                or sliver_context_urn != self_urn: 
            return

        # Update for each measurement
        for meas_type, value in measurements.items():
            self._update_measurement(urn_type, start_time, end_time, 
                                     meas_type, value)

    # For a given sliver and URN/MEAS type, 
    # update the relevant measurement state
    def _update_measurement(self, urn_type, start_time, end_time, 
                            meas_type, value):
        key = "%s:%s" % (urn_type, meas_type)
        if key not in self._measurement_states:
            self._measurement_states[key] = \
                ResourceMeasurementState(urn_type, meas_type)
        measurement_state = self._measurement_states[key]
        measurement_state.update(start_time, end_time, value)


    # Grab all bindings from all measurement states
    def getBindings(self):
        bindings = {}
        for meas_state in self._measurement_states.values():
            meas_state_bindings = meas_state.getBindings()
            bindings = dict(bindings.items() + meas_state_bindings.items())
        return bindings

# A class to maintain state about a 
# particular urn_type (USER, SLICE, PROJECT, AUTHORITY)
# and a particular meas_type (from the aggregate on a per-sliver basis)
#
# From these individual sliver measurements we compute
# TOTAL: Total of the metric over all relevant slivers
# HOURS :  Total metric-hours over all relevant slivers
# MAX : Max concurrent of that metric over all relevant slivers
class ResourceMeasurementState:
    def __init__(self, urn_type, meas_type):
        self._urn_type = urn_type
        self._meas_type = meas_type
        
        # Maintain running ottals for TOTAL and HOURS
        self._meas_total = 0
        self._meas_hours = 0

        
    # Update for a given sliver measurement with time bounds
    def update(self, start_time, end_time, value):
        # Update TOTAL
        self._meas_total = self._meas_total + value

        # Update HOURS
        dt = (end_time - start_time).total_seconds()
        num_hours = dt / 3600.0
        self._meas_hours = self._meas_hours + (value * num_hours)

    # Grab the bindings provided by this state
    def getBindings(self):
        bindings = {}

        total_key = "%s_%s_%s" % (self._urn_type, self._meas_type, 'TOTAL')
        bindings[total_key] = str(self._meas_total)

        hours_key = "%s_%s_%s" % (self._urn_type, self._meas_type, 'HOURS')
        bindings[hours_key] = str(self._meas_hours)

        # *** TO DO: MAX ***

        return bindings
