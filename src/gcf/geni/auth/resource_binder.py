#---------------------------------------------------------------------- 
# Copyright (c) 2010-2015 Raytheon BBN Technologies
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

from __future__ import absolute_import

from .util import *
from .binders import Base_Binder
from ...sfa.trust import gid

import dateutil.parser

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

class Resource_Binder(Base_Binder):

    def __init__(self, root_cert):
        Base_Binder.__init__(self, root_cert)
        self._slice_urn = None
        self._project_urn = None
        self._user_urn = None
        self._authority_urn = None

    # Generate bindings for given context and requested state
    # Based on the kind of measurements we're looking for and
    # Aggregation (SUM, MAX, etc.) we're applying to measurements
    def generate_bindings(self, method, caller, creds, args, opts,
                          requested_state = []):
        measurement_states = {}
        self._user_urn = gid.GID(string=caller).get_urn()
        self._authority_urn = \
            convert_user_urn_to_authority_urn(self._user_urn)

        if 'slice_urn' in args: 
            self._slice_urn = args['slice_urn']
            self._project_urn = \
                convert_slice_urn_to_project_urn(self._slice_urn)

        for sliver_info in requested_state:
            self.updateForSliverInfo(sliver_info, measurement_states)

        return self.getBindings(measurement_states)

    # For a given sliver, try to update measurement for each aspect 
    def updateForSliverInfo(self, sliver_info, measurement_states):
        sliver_urn = sliver_info['sliver_urn']
        slice_urn = sliver_info['slice_urn']
        user_urn = sliver_info['user_urn']
        project_urn = None
        authority_urn = None
        start_time = dateutil.parser.parse(sliver_info['start_time'])
        end_time = dateutil.parser.parse(sliver_info['end_time'])
        measurements = sliver_info['measurements']

        if slice_urn:
            project_urn = convert_slice_urn_to_project_urn(slice_urn)
        if user_urn:
            authority_urn = convert_user_urn_to_authority_urn(user_urn)

        if slice_urn:
            self._update_sliver(slice_urn, self._slice_urn, 'SLICE', 
                                start_time, end_time, measurements, 
                                measurement_states, sliver_info)
        if user_urn:
            self._update_sliver(user_urn, self._user_urn, 'USER', 
                                start_time, end_time, measurements,
                                measurement_states, sliver_info)
        if project_urn:
            self._update_sliver(project_urn, self._project_urn, 'PROJECT', 
                                start_time, end_time, measurements,
                                measurement_states, sliver_info)
        if authority_urn:
            self._update_sliver(authority_urn, self._authority_urn, 'AUTHORITY', 
                                start_time, end_time, measurements,
                                measurement_states, sliver_info)


    # Go through all slivers and update measurements if the sliver
    # matches the call context
    def _update_sliver(self, sliver_context_urn, self_urn, urn_type,
                       start_time, end_time, measurements,
                       measurement_states, sliver_info):
        # If this isn't a sliver we care about, ignore
        if sliver_context_urn == None \
                or self_urn == None \
                or sliver_context_urn != self_urn: 
            return

        # Update for each measurement
        for meas_type, value in measurements.items():
            self.update_measurement(urn_type, start_time, end_time, 
                                     meas_type, value, 
                                    measurement_states, sliver_info)

    # For a given sliver and URN/MEAS type, 
    # update the relevant measurement state
    def update_measurement(self, urn_type, start_time, end_time, 
                            meas_type, value, measurement_states, sliver_info):
        key = "%s:%s" % (urn_type, meas_type)
        if key not in measurement_states:
            new_measurement_state = \
                self.get_measurement_state(urn_type, meas_type)
            measurement_states[key] = new_measurement_state
        measurement_state = measurement_states[key]
        measurement_state.update(start_time, end_time, value, sliver_info)

    # Override this method to return different resource states
    # For computing different metrics
    def get_measurement_state(self, urn_type, meas_type):
        return None

    # Grab and return all bindings from all measurement states
    def getBindings(self, measurement_states):
        bindings = {}
        for meas_state in measurement_states.values():
            meas_state_bindings = meas_state.getBindings()
            bindings = dict(bindings.items() + meas_state_bindings.items())
        return bindings

# Resource_Binder subclass to compute total allocation measurements
# for a given context
class TOTAL_Binder(Resource_Binder):
        def __init__(self, root_cert): 
            Resource_Binder.__init__(self, root_cert)

        def get_measurement_state(self, urn_type, meas_type):
            return TOTAL_ResourceMeasurementState(urn_type, meas_type)

# Resource_Binder subclass to compute total allocation measurement-hours
# for a given context
class HOURS_Binder(Resource_Binder):
        def __init__(self, root_cert): 
            Resource_Binder.__init__(self, root_cert)

        def get_measurement_state(self, urn_type, meas_type):
            return HOURS_ResourceMeasurementState(urn_type, meas_type)

# Resource_Binder subclass to compute max SIMULTANEOUS 
# allocation measurement for a given context
class MAX_Binder(Resource_Binder):
        def __init__(self, root_cert): 
            Resource_Binder.__init__(self, root_cert)

        def get_measurement_state(self, urn_type, meas_type):
            return MAX_ResourceMeasurementState(urn_type, meas_type)

# Resource Binder that computes the number of slices to which a user belongs
class User_Slice_Binder(Resource_Binder):
        def __init__(self, root_cert): 
            Resource_Binder.__init__(self, root_cert)

        def get_measurement_state(self, urn_type, meas_type):
            return User_Slice_ResourceMeasurementState(urn_type, meas_type)



# Base class for computing aggregate metrics from alloction metric values
class Base_ResourceMeasurementState:
    def __init__(self, urn_type, meas_type):
        self._urn_type = urn_type
        self._meas_type = meas_type

    # Override this to return the bindings for this measurement state
    def getBindings(self):
        pass

    # Override this method to compute different aggregate metrics
    def update(self, start_time, end_time, value, sliver_info):
        pass

# ResourceMeasurementState sub-Class to compute the 
# total of allocation measurement values
class TOTAL_ResourceMeasurementState(Base_ResourceMeasurementState):
    def __init__(self, urn_type, meas_type):
        Base_ResourceMeasurementState.__init__(self, urn_type, meas_type)
        self._meas_total = 0

    def update(self, start_time, end_time, value, sliver_info):
        self._meas_total = self._meas_total + value

    def getBindings(self):
        total_key = "$%s_%s_%s" % (self._urn_type, self._meas_type, 'TOTAL')
        return {total_key : str(self._meas_total) }

# ResourceMeasurementState sub-Class to compute the 
# measurement-hours of allocation measurements
class HOURS_ResourceMeasurementState(Base_ResourceMeasurementState):
    def __init__(self, urn_type, meas_type):
        Base_ResourceMeasurementState.__init__(self, urn_type, meas_type)
        self._meas_hours = 0

    def update(self, start_time, end_time, value, sliver_info):
        dt = (end_time - start_time)
        num_hours = (dt.days*24) + (dt.seconds/3600.0)
        self._meas_hours = self._meas_hours + (value * num_hours)

    def getBindings(self):
        hours_key = "$%s_%s_%s" % (self._urn_type, self._meas_type, 'HOURS')
        return {hours_key : str(self._meas_hours) }

# ResourceMeasurementState sub-Class to compute the 
# maximum total of SIMULTANOUS allocation measurement values
class MAX_ResourceMeasurementState(Base_ResourceMeasurementState):
    def __init__(self, urn_type, meas_type):
        Base_ResourceMeasurementState.__init__(self, urn_type, meas_type)
        # Maintain list of times
        self._times = set()

        # Maintain list of [value, start, end] tuples
        self._entries = []

    def update(self, start_time, end_time, value, sliver_info):
        # Register times
        self._times.add(start_time)
        self._times.add(end_time)

        # Registry entry for later 'MAX' calculation
        self._entries.append((start_time, end_time, value))


    def getBindings(self):

        # Get a sorted list of all the start/end times
        time_boundaries = [tm for tm in self._times]
        time_boundaries.sort()

        # Collect totals for each window [i:i+1] in bin [i]
        totals = [0 for i in range(len(time_boundaries)-1)]

        # For each entry, add the value to the right bins if
        # entry overlaps the time window of that bin
        # In so doing, compute max_total
        #
        # Note: we treat start_time as first included time
        # end_times as NON-included time
        max_total = 0
        for entry in self._entries:
            entry_start = entry[0]
            entry_end = entry[1]
            value = entry[2]
            for i in range(len(totals)):
                boundary_start = time_boundaries[i]
                boundary_end = time_boundaries[i+1]
                no_overlap =  entry_start >= boundary_end or \
                    entry_end <= boundary_start;
                if not no_overlap:
                    totals[i] = totals[i] + value
                    max_total = max(totals[i], max_total)

        max_key = "$%s_%s_%s" % (self._urn_type, self._meas_type, 'MAX')
        return {max_key : str(max_total) }

# ResourceMeasurementState sub-Class to compute the 
# number of slices at which a user has slivers
class User_Slice_ResourceMeasurementState(Base_ResourceMeasurementState):
    def __init__(self, urn_type, meas_type):
        Base_ResourceMeasurementState.__init__(self, urn_type, meas_type)
        self._active = urn_type == "USER" # Ignore all but user info
        self._slices = set()
        self._projects = set()

    def update(self, start_time, end_time, value, sliver_info):
        if self._active:
            slice_urn = sliver_info['slice_urn']
            self._slices.add(slice_urn)
            project_urn = convert_slice_urn_to_project_urn(slice_urn)
            self._projects.add(project_urn)


    def getBindings(self):
        if self._active:
            user_num_slices_key = "$USER_NUM_SLICES"
            user_num_projects_key = "$USER_NUM_PROJECTS"
            return {
                user_num_slices_key : str(len(self._slices)),
                user_num_projects_key : str(len(self._projects))
                }
        else:
            return {}

