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

import datetime
import dateutil.parser
import types
import xml.dom.minidom

from ...sfa.trust import gid
from ...sfa.trust import credential
from ..util.tz_util import tzd
from .base_authorizer import AM_Methods, V2_Methods

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
    def get_requested_allocation_state(self, aggregate_manager, method_name,
                                       arguments, options,  creds):
        return []

# Class for a Resource Manager for the GCF AM
# We only compute a single metric, i.e. NODE (the number of nodes allocated)
class GCFAM_Resource_Manager(Base_Resource_Manager):

    def __init__(self):
        Base_Resource_Manager.__init__(self)

    # Return combindation of current and requested allocations
    def get_requested_allocation_state(self, aggregate_manager, method_name,
                                       arguments, options, credentials):


        if method_name in (AM_Methods.CREATE_SLIVER_V2, AM_Methods.ALLOCATE_V3):

            creds = [credential.Credential(string=c) for c in credentials]

            # Concatenate the current allocations and requested, since
            # these must be distinct
            curr_allocations = \
                self.get_current_allocations(aggregate_manager, arguments, 
                                             method_name, 
                                             options, creds)
            req_allocations = \
                self.get_requested_allocations(aggregate_manager, arguments, 
                                               method_name,
                                               options, creds)

            return curr_allocations + req_allocations

        elif method_name in (AM_Methods.RENEW_SLIVER_V2, AM_Methods.RENEW_V3):

            amd = aggregate_manager._delegate
            creds = [credential.Credential(string=c) for c in credentials]

            # Grab current allocations
            curr_allocations = \
                self.get_current_allocations(aggregate_manager, arguments, 
                                             method_name, 
                                             options, creds)
            # get slice credential expiration time
            expiration = amd.min_expire(creds, max_duration=amd.max_lease)
            # get requested end time
            requested_str = arguments['expiration_time']
            requested = dateutil.parser.parse(requested_str, tzinfos=tzd)
            requested = amd._naiveUTC(requested)
            # if --alap use credential end time
            if "geni_extend_alap" in options:
                requested = min(expiration, requested)

            requested = str(requested)

            # go over all slivers in curr_allocations and change end time
            # of those we're trying to change 
            # (slivers of slice or specific slivers)
            if 'urns' in arguments:
                # Handle V3 case
                urns = arguments['urns']
            else:
                # Handle V2 case
                urns = [arguments['slice_urn']]
            the_slice, slivers = amd.decode_urns(urns)
            sliver_urns = [the_sliver.urn() for the_sliver in slivers]
            for sliver_info in curr_allocations:
                if sliver_info['sliver_urn'] in sliver_urns:
                    sliver_info['end_time'] = requested

            return curr_allocations

        else:
            return []


    # Get all current slivers and return them in proper format
    def get_current_allocations(self, aggregate_manager,
                                arguments, method_name, options, creds):

        sliver_info = []
        slices = aggregate_manager._delegate._slices
        user_urn = gid.GID(string=options['geni_true_caller_cert']).get_urn()

        for slice_urn, slice_obj in slices.items():
            self.add_sliver_info_for_slice(slice_obj, sliver_info, 
                                           method_name,
                                           slice_urn, user_urn)

        return sliver_info

    # Add entry for each sliver of slice
    # Account for difference between GCF AM V2 and V3 representations
    def add_sliver_info_for_slice(self, slice_obj, sliver_info, method_name,
                                  slice_urn, user_urn):
        if method_name in V2_Methods:
            for sliver_name, sliver_urn in slice_obj.resources.items():
                entry = {'sliver_urn' : sliver_urn,
                         'slice_urn' : slice_urn,
                         'user_urn' : user_urn,
                         'start_time' : str(datetime.datetime.utcnow()),
                         'end_time' : str(slice_obj.expiration),
                         'measurements' : {'NODE' : 1}}
                sliver_info.append(entry)
        else:
            for sliver in slice_obj.slivers():
                entry = {'sliver_urn' : sliver.urn(),
                         'slice_urn' : slice_urn,
                         'user_urn' : user_urn,
                         'start_time' : str(sliver.startTime()),
                         'end_time' : str(sliver.endTime()),
                         'measurements' : {'NODE' : 1}}
                sliver_info.append(entry)


    # Take the given rspec (if provided) and determine how
    # many nodes are being requested over what time ranges
    # and compute the sliver info accordingly
    def get_requested_allocations(self, aggregate_manager, 
                                  arguments, method_name, options, creds):
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
