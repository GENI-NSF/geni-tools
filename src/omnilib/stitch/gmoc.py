# coding: utf-8
# ====================================================================
#  GENI Meta-Operations Objects
#  gmoc.py
#
#  Classes for communicating with the GENI Meta-Operations Center
#
#  Created by the Indiana University GlobalNOC <syseng@grnoc.iu.edu>
#
#  Copyright (C) 2012, Trustees of Indiana University
#    All Rights Reserved
#
#  Permission is hereby granted, free of charge, to any person 
#  obtaining a copy of this software and/or hardware specification 
#  (the “Work”) to deal in the Work without restriction, including
#  without limitation the rights to use, copy, modify, merge, 
#  publish, distribute, sublicense, and/or sell copies of the Work, 
#  and to permit persons to whom the Work is furnished to do so, 
#  subject to the following conditions:
#
#  The above copyright notice and this permission notice shall be 
#  included in all copies or substantial portions of the Work.
#
#  THE WORK IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, 
#  EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES 
#  OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
#  NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
#  HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
#  WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING 
#  FROM, OUT OF OR IN CONNECTION WITH THE WORK OR THE USE OR OTHER 
#  DEALINGS IN THE WORK.
# ====================================================================

import datetime
import json
import random
import re
#import rrdtool
import string
import sys
import time
import uuid

#from httplib2 import Http
from urllib import urlencode, quote
from urlparse import urlparse
from xml.dom.minidom import getDOMImplementation


# Version
GMOC_CLIENT_VERSION       = '1.2.0'

# # Constants
# AM_STATE_UNKNOWN             = 'Unknown'
# AM_STATE_DEGRADED            = 'Degraded'
# AM_STATE_DOWN                = 'Down'
# AM_STATE_UP                  = 'Up'

# CIRCUIT_ADMIN_UNKNOWN        = 'Unknown'
# CIRCUIT_ADMIN_AVAILABLE      = 'Available'
# CIRCUIT_ADMIN_DECOMMISSIONED = 'Decommissioned'
# CIRCUIT_ADMIN_MAINTENANCE    = 'Maintenance'
# CIRCUIT_ADMIN_NORMAL         = 'NormalOperation'
# CIRCUIT_ADMIN_PLANNING       = 'Planning'
# CIRCUIT_ADMIN_PROVISIONING   = 'Provisioning'

# CIRCUIT_TYPE_UNKNOWN         = 'unspecified'
# CIRCUIT_TYPE_100ME           = '100ME'
# CIRCUIT_TYPE_1GE             = '1GE'
# CIRCUIT_TYPE_10GE            = '10GE'
# CIRCUIT_TYPE_40GE            = '40GE'
# CIRCUIT_TYPE_100GE           = '100GE'
# CIRCUIT_TYPE_ETHCHAN         = 'ETHCHAN'
# CIRCUIT_TYPE_OC192           = 'OC192'
# CIRCUIT_TYPE_WIFI            = 'WIFI'
# CIRCUIT_TYPE_WIMAX           = 'WIMAX'

# GMOC_DEBUG_OFF               = 0x00
# GMOC_DEBUG_ON                = 0x01
# GMOC_DEBUG_VERBOSE           = 0x02
# GMOC_DEBUG_OMGWTFBBQ         = 0x03

# GMOC_SUCCESS                 = 0x00
# GMOC_ERROR_BAD_ID            = 0x01
# GMOC_ERROR_BAD_PROPS         = 0x02
# GMOC_ERROR_NO_OBJECT         = 0x04
# GMOC_ERROR_BAD_CONNECT       = 0x08
# GMOC_ERROR_BAD_SCHEMA        = 0x10
# GMOC_ERROR_INVALID           = 0x20

# INTF_ADMIN_UNKNOWN           = 'Unknown'
# INTF_ADMIN_AVAILABLE         = 'Available'
# INTF_ADMIN_DECOMMISSIONED    = 'Decommissioned'
# INTF_ADMIN_MAINTENANCE       = 'Maintenance'
# INTF_ADMIN_NORMAL            = 'NormalOperation'
# INTF_ADMIN_PLANNING          = 'Planning'
# INTF_ADMIN_PROVISIONING      = 'Provisioning'

# INTF_STATE_UNKNOWN           = 'Unknown'
# INTF_STATE_DEGRADED          = 'Degraded'
# INTF_STATE_DOWN              = 'Down'
# INTF_STATE_UP                = 'Up'

# NETADDR_TYPE_IPV4            = 'IPv4'
# NETADDR_TYPE_IPV6            = 'IPv6'
# NETADDR_TYPE_MAC             = 'MAC'

# ORG_TYPE_BACKBONE            = 'backbone'
# ORG_TYPE_CAMPUS              = 'campus'
# ORG_TYPE_META                = 'meta'
# ORG_TYPE_RACK_VENDOR         = 'rack-vendor'
# ORG_TYPE_REGIONAL            = 'regional'

# RESOURCE_STATE_UNKNOWN       = 'Unknown'
# RESOURCE_STATE_DEGRADED      = 'Degraded'
# RESOURCE_STATE_DOWN          = 'Down'
# RESOURCE_STATE_UP            = 'Up'

# SA_TYPE_PROTOGENI            = 'protogeni'

# SLIVER_STATE_UNKNOWN         = 'Unknown'
# SLIVER_STATE_DEGRADED        = 'Degraded'
# SLIVER_STATE_DOWN            = 'Down'
# SLIVER_STATE_UP              = 'Up'


# --------------------------------------------------------------------

# stolen from Stanford University
URN_PREFIX = 'urn:publicid:IDN'
AUTH_PREFIX = 'gmoc.geni.net'

# stolen from Raytheon
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

# more steals
def string_to_urn_format(instr):
    '''Make a string URN compatible, collapsing whitespace and escaping chars'''
    if instr is None or instr.strip() == '':
        raise ValueError("Empty string cant be in a URN")
    # Collapse whitespace
    instr = ' '.join(instr.strip().split())
    for a, b in publicid_xforms:
        instr = instr.replace(a, b)
    return instr

# I haven't worked an honest day in my life
def isValidURN(urn):
    if not isinstance(urn, str):
        return False

    if re.search("[\s|\?\/]", urn) is None:
        if urn.startswith(URN_PREFIX):
            return True

    return False 

# finally some GRNOC code
def validateText(urn):
    return urn
   
def validateURN(urn):
    if isValidURN(str(urn)):
        return str(urn)

    return None

def validateContactURN(urn):
    if isValidURN(urn):
        return urn
    elif isinstance(urn, str):
        emailParts = urn.split('@', 2)
        if len(emailParts) == 2:
            return URN_PREFIX + '+gmoc.geni.net+contact+' + emailParts[0] + '_' + emailParts[1]
        else:
            return None

    return None

def validateLocationURN(urn):
    if isValidURN(urn):
        return urn
    elif isinstance(urn, str):
        return URN_PREFIX + '+' + AUTH_PREFIX + '+location+' + urn

    return None

def validateOrganizationURN(urn):
    if isValidURN(urn):
        return urn
    elif isinstance(urn, str):
        return URN_PREFIX + '+' + AUTH_PREFIX + '+organization+' + urn

    return None

def validatePOPURN(urn):
    if isValidURN(urn):
        return urn
    elif isinstance(urn, str):
        return URN_PREFIX + '+' + AUTH_PREFIX + '+pop+' + urn

    return None

def validateAuthorityURN(urn):
    if isValidURN(urn):
        return urn
    elif isinstance(urn, str):
        return URN_PREFIX + '+' + urn + '+authority+sa'

    return None

def validateSliceURN(urn):
    if isValidURN(urn):
        return urn
    elif isinstance(urn, str):
        return URN_PREFIX + '+' + AUTH_PREFIX + '+slice+' + urn

    return None

# based on code from Tim Pietzcker at Stack Overflow
# http://stackoverflow.com/questions/2532053/validate-hostname-string-in-python
def validateAggregate(id):
    allowed = re.compile("(?!-)[A-Z\d-]{1,63}(?<!-)$", re.IGNORECASE)
    patternFull = re.compile("^.+(\d+\:)?$")

    if not patternFull.match(id):
        return None

    if len(id) > 255:
        return None

    if id[-1:] == ".":
        id = id[:-1] # strip exactly one dot from the right, if present

    idParts = id.split(".")
    lastPart = idParts[len(idParts) - 1].split(":")[0]
    idParts[len(idParts) - 1] = lastPart

    if all(allowed.match(x) for x in idParts):
        return id
    else:
        return None
                    
def validateSliverURN(urn):
    if isValidURN(urn):
        return urn
    elif isinstance(urn, str):
        return URN_PREFIX + '+' + AUTH_PREFIX + '+sliver+' + urn

    return None

def validateCircuitURN(urn):
    if isValidURN(urn):
        return urn
    elif isinstance(urn, str):
        return URN_PREFIX + '+' + AUTH_PREFIX + '+link+' + urn

    return None

def validateResourceURN(urn):
    if isValidURN(urn):
        return urn
    elif isinstance(urn, str):
        return URN_PREFIX + '+' + AUTH_PREFIX + '+resource+' + urn

    return None

def validateInterfaceURN(urn):
    if isValidURN(urn):
        return urn
    elif isinstance(urn, str):
        return URN_PREFIX + '+' + AUTH_PREFIX + '+interface+' + urn

    return None


# --------------------------------------------------------------------

def _getObjID():
    return lambda self: getattr(self, '__id')

def _setObjID(validator):
    def __setObjID(self, value):
        if not validator is None:
            validVal = validator(value)
            if not validVal is None:
                self.__id = validVal
            else:
                raise ValueError("identifier could not be validated")
        else:
            self.__id = value

    return __setObjID

def _getProp(propName):
    return lambda self: getattr(self, '__' + propName)

def _setProp(propName, propType):
    def __setProp(self, value):
        oldVal = getattr(self, '__' + propName)
        if not value is None:
            if not isinstance(value, propType):
                raise TypeError(propName + " (" + str(value) +") must be of type '" + propType.__name__ + "' instead it is of type '" + str(type(value).__name__) +"'")
        
        setattr(self, '__' + propName, value)
    
    return __setProp

class GMOCMeta(type):
    def __new__(meta, cls, bases, clsDict):
        if '__ID__' in clsDict:
            clsDict['__id'] = None
            clsDict['id'] = property(_getObjID(), _setObjID(clsDict['__ID__']))

        if '__simpleProps__' in clsDict:
            for prop in clsDict['__simpleProps__']:
                clsDict['__' + prop[0]] = None
                clsDict[prop[0]] = property(_getProp(prop[0]), _setProp(prop[0], prop[1]))

        return super(GMOCMeta, meta).__new__(meta, cls, bases, clsDict)


# --------------------------------------------------------------------

class GMOCObject(object):
    """Base class for GMOC objects"""

    def __init__(self, id):
        self.id = id
        self._measurements = []
        self._last_modified = 0

    def _setListProp(self, propName, propValue, propType, propRefSetter = None):
        # make sure we really have a list
        if not isinstance(propValue, list):
            raise TypeError(propName + " must be a list")

        # unset the reference to this object in our current list
        # in case the new list doesn't intersect
        if propRefSetter != None:
            currentList = getattr(self, '_' + propName)
            for element in currentList:
                setattr(element, propRefSetter, None)

            for element in propValue:
                if isinstance(element, propType):
                    setattr(element, propRefSetter, self)
                else:
                    raise TypeError("all elements in " + propName + " must be of type " + propType.__name__)

        setattr(self, '_' + propName, propValue)

    def _putIntoList(self, propName, propObj, propType):
        if propObj != None:
            if isinstance(propObj, propType):
                oldProp = getattr(propObj, '_' + propName)
                if not propObj in oldProp:
                    oldProp.append(self)
                    setattr(propObj, '_' + propName, oldProp)
            else:
                raise TypeError("property must be of type " + propType.__name__)

    def validate(self):
        if self.id == None:
            raise ValueError("Object must have a valid identifier")

    @property
    def measurements(self):
        return self._measurements

    def addMeasurement(self, value):
        raise ValueError("Measurement type " + value.type + " is not allowed")

    @property
    def last_modified(self):
        return self._last_modified


# # --------------------------------------------------------------------

# class GMOCMeasurementTypeInfo(object):
#     """TypeInfo class for time series data"""

#     def __init__(self, name, columns, units):
#         self.name = name

#         if isinstance(columns, list):
#             self.columns = columns
#         else:
#             self.columns = []

#         if isinstance(units, list):
#             self.units = units
#         else:
#             self.units = []

#     def toXML(self, doc, parent):
#         pass

# class GMOCMeasurement(object):
#     """Base class for measurement objects"""        

#     def __init__(self, reporter = None, type = None, columns = [], units = [], step = 15, heartbeat = 60):
#         self.reporter = reporter
#         self.type = type
#         self.step = step
#         self.start = None
#         self.end = None
#         self.heartbeat = heartbeat
#         self._values = []
#         self._name = None
#         self._tag = None

#         if isinstance(columns, list):
#             self.columns = columns

#         if isinstance(units, list):
#             self.units = units

#     def addData(self, ts, measurements):
#         if not isinstance(ts, int):
#             raise ValueError("Timestamp must be an integer for measurement " + self._name)

#         idx = 0
#         values = []
#         for col in self.columns:
#             if col in measurements:
#                 values.append(measurements[col])
#             else:
#                 values.append(None)
#             idx += 1

#         entry = ( ts, values )
#         self._values.append(entry)

#         if self.start == None or self.start > ts:
#             self.start = ts

#         if self.end == None or self.end < ts:
#             self.end = ts

#     def loadRRD(self, rrdfile, startTime = None, endTime = None):
#         endTimeDT = datetime.datetime.utcnow()
#         startTimeDT = endTimeDT - datetime.timedelta(seconds = self.step)

#         if endTime == None:
#             endTime = int(time.mktime(endTimeDT.timetuple())) 
#         else:
#             if not isinstance(startTime, int):
#                 raise TypeError("Timestamp must be an integer for measurement " + self._name)
#             startTimeDt = datetime.datetime.fromtimestamp(startTime)

#         if startTime == None:
#             startTime = int(time.mktime(startTimeDT.timetuple()))
#         else:
#             if not isinstance(endTime, int):
#                 raise TypeError("Timestamp must be an integer for measurement " + self._name)
#             startTimeDT = datetime.datetime.fromtimestamp(startTime)

#         if startTime >= endTime:
#             raise ValueError("End time can not be before the Start time")

#         [metadata, specs, vals] = rrdtool.fetch(rrdfile, "AVERAGE", "-s", startTimeDT.strftime("%s"), "-e", endTimeDT.strftime("%s"))
#         [rrd_time, rrd_end_time, rrd_interval] = metadata

#         self.start = startTime
#         self.end = endTime
#         self.step = rrd_interval

#         while len(vals) > 0:
#             row = vals.pop(0)
#             idx = 0
#             if row[0] is not None:
#                 rowVals = { }
#                 for col in self.columns:
#                     rowVals[col] = row[idx]
#                     idx += 1

#                 self.addData(rrd_time, rowVals)

#                 if rrd_time < startTime:
#                     self.start = rrd_time

#                 self.end = rrd_time

#             rrd_time += rrd_interval

#     def clearData(self):
#         self._values = []

#     def typeToXML(self, doc, parent):
#         if parent == None:
#             parent = doc.documentElement

#         node = doc.createElement("type_info")
#         node.setAttribute("name", self.type)

#         # handle column names
#         column_names = ",".join(self.columns)
#         cnode = doc.createElement("column_names")
#         tnode = doc.createTextNode(column_names)
#         cnode.appendChild(tnode)
#         node.appendChild(cnode)

#         # handle units
#         unit_names = ",".join(self.units)
#         cnode = doc.createElement("column_units")
#         tnode = doc.createTextNode(unit_names)
#         cnode.appendChild(tnode)
#         node.appendChild(cnode)

#         parent.appendChild(node)

#         return node
        
#     def dataToXML(self, doc, parent):
#         if parent == None:
#             parent = doc.documentElement

#         node = doc.createElement("data_group")
#         node.setAttribute("name", self._name)
#         node.setAttribute("interval_type", "open_closed")
#         node.setAttribute("start", str(self.start))
#         node.setAttribute("end", str(self.end))
#         node.setAttribute("step", str(self.step))
#         node.setAttribute("heartbeat", str(self.heartbeat))

#         cnode = doc.createElement("column_names")
#         tnode = doc.createTextNode(",".join(self.columns))
#         cnode.appendChild(tnode)
#         node.appendChild(cnode)

#         cnode = doc.createElement("type")
#         tnode = doc.createTextNode(self.type)
#         cnode.appendChild(tnode)
#         node.appendChild(cnode)

#         cnode = doc.createElement("node_name")
#         tnode = doc.createTextNode(self.reporter)
#         cnode.appendChild(tnode)
#         node.appendChild(cnode)

#         cnode = doc.createElement("tags")
#         tnode = doc.createTextNode(self._tag)
#         cnode.appendChild(tnode)
#         node.appendChild(cnode)

#         openStart = self.start - self.step
#         rows = str(openStart)
#         for col in self.columns:
#             rows += ","
#         rows += ";\n"

#         for d in self._values:
#             rows += str(d[0])
#             for e in d[1]:
#                 rows += "," + str(e)
#             rows += ";\n"

#         cnode = doc.createElement("data")
#         tnode = doc.createTextNode(rows)
#         cnode.appendChild(tnode)
#         node.appendChild(cnode)

#         parent.appendChild(node)

#         return node


# # --------------------------------------------------------------------

# class CPUUtilization(GMOCMeasurement):
#     """Measurement class for CPU Utilization"""

#     def __init__(self, reporter = None):
#         super(CPUUtilization, self).__init__(reporter, "node_cpu", [ "cpu_idle" ], [ "percent" ])


# # --------------------------------------------------------------------

# class DiskUtilization(GMOCMeasurement):
#     """Measurement class for Disk Utilization"""

#     def __init__(self, reporter = None):
#         super(DiskUtilization, self).__init__(reporter, "node_disk", [ "disk_part_max_used" ], [ "percent" ])


# # --------------------------------------------------------------------

# class OpenFlowSliverStats(GMOCMeasurement):
#     """Measurement class for OpenFlow sliver statistics"""

#     def __init__(self, reporter = None):
#         super(OpenFlowSliverStats, self).__init__(reporter, "openflow_sliver_stats", [ "ro_rules", "rw_rules", "tx_msgs", "rx_msgs", "drop_msgs", "tx_msgs_flow_mod", "tx_msgs_flow_remove", "tx_msgs_error", "tx_msgs_packet_in", "tx_msgs_packet_out", "tx_msgs_vendor", "tx_msgs_other", "rx_msgs_flow_mod", "rx_msgs_flow_remove", "rx_msgs_error", "rx_msgs_packet_in", "rx_msgs_packet_out", "rx_msgs_vendor", "rx_msgs_other" ], [ "N", "N", "msgs/s", "msgs/s", "msgs/s", "msgs/s", "msgs/s", "msgs/s", "msgs/s", "msgs/s", "msgs/s", "msgs/s", "msgs/s", "msgs/s", "msgs/s", "msgs/s", "msgs/s", "msgs/s", "msgs/s" ])


# # --------------------------------------------------------------------

# class FlowvisorDatapathStats(GMOCMeasurement):
#     """Measurement class for Flowvisor datapath statistics"""

#     def __init__(self, reporter = None):
#         super(FlowvisorDatapathStats, self).__init__(reporter, "flowvisor_dpid_stats", [ "ports", "ro_rules", "rw_rules", "tx_msgs", "rx_msgs", "drop_msgs", "tx_msgs_flow_mod", "tx_msgs_flow_remove", "tx_msgs_error", "tx_msgs_packet_in", "tx_msgs_packet_out", "tx_msgs_vendor", "tx_msgs_other", "rx_msgs_flow_mod", "rx_msgs_flow_remove", "rx_msgs_error", "rx_msgs_packet_in", "rx_msgs_packet_out", "rx_msgs_vendor", "rx_msgs_other" ], [ "N", "N", "N", "msgs/s", "msgs/s", "msgs/s", "msgs/s", "msgs/s", "msgs/s", "msgs/s", "msgs/s", "msgs/s", "msgs/s", "msgs/s", "msgs/s", "msgs/s", "msgs/s", "msgs/s", "msgs/s", "msgs/s" ])


# # --------------------------------------------------------------------

# class SliverState(GMOCMeasurement):
#     """Measurement class for the sliver state metric"""

#     def __init__(self, reporter = None):
#         super(SliverState, self).__init__(reporter, "foam_sliver_state", [ "approved", "enabled", "pending", "rejected" ], [ "N", "N", "N", "N" ])


# # --------------------------------------------------------------------

# class FlowvisorSliceStats(GMOCMeasurement):
#     """Measurement class for Flowvisor slice statistics"""

#     def __init__(self, reporter = None):
#         super(FlowvisorSliceStats, self).__init__(reporter, "flowvisor_slice_stats", [ "ro_rules", "rw_rules", "tx_msgs", "rx_msgs", "drop_msgs", "tx_msgs_flow_mod", "tx_msgs_flow_remove", "tx_msgs_error", "tx_msgs_packet_in", "tx_msgs_packet_out", "tx_msgs_vendor", "tx_msgs_other", "rx_msgs_flow_mod", "rx_msgs_flow_remove", "rx_msgs_error", "rx_msgs_packet_in", "rx_msgs_packet_out", "rx_msgs_vendor", "rx_msgs_other" ], [ "N", "N", "msgs/s", "msgs/s", "msgs/s", "msgs/s", "msgs/s", "msgs/s", "msgs/s", "msgs/s", "msgs/s", "msgs/s", "msgs/s", "msgs/s", "msgs/s", "msgs/s", "msgs/s", "msgs/s", "msgs/s" ])


# # --------------------------------------------------------------------

# class DatapathStats(GMOCMeasurement):
#     """"Measurement class for datapath statistics"""

#     def __init__(self, reporter = None):
#         super(DatapathStats, self).__init__(reporter, "datapath_stats", [ "ports", "ro_rules", "rw_rules", "tx_msgs", "rx_msgs", "drop_msgs", "tx_msgs_flow_mod", "tx_msgs_flow_remove", "tx_msgs_error", "tx_msgs_packet_in", "tx_msgs_packet_out", "tx_msgs_vendor", "tx_msgs_other", "rx_msgs_flow_mod", "rx_msgs_flow_remove", "rx_msgs_error", "rx_msgs_packet_in", "rx_msgs_packet_out", "rx_msgs_vendor", "rx_msgs_other" ], [ "N", "N", "N", "msgs/s", "msgs/s", "msgs/s", "msgs/s", "msgs/s", "msgs/s", "msgs/s", "msgs/s", "msgs/s", "msgs/s", "msgs/s", "msgs/s", "msgs/s", "msgs/s", "msgs/s", "msgs/s", "msgs/s" ])


# # --------------------------------------------------------------------

# class FOAMSliverCount(GMOCMeasurement):
#     """Measurement class for FOAM sliver counts"""

#     def __init__(self, reporter = None):
#         super(FOAMSliverCount, self).__init__(reporter, "foam_state", [ "slivers" ], [ "N" ])


# # --------------------------------------------------------------------

# class VMCount(GMOCMeasurement):
#     """Measurement class for virtual machine count on a hypervisor"""

#     def __init__(self, reporter = None):
#         super(VMCount, self).__init__(reporter, "vm_count", [ "vms_active", "vms_free" ], [ "N", "N" ])


# # --------------------------------------------------------------------

# class PLSliverNetworkStats(GMOCMeasurement):
#     """Measurement class for PlanetLab sliver networking statistics"""

#     def __init__(self, reporter = None):
#         super(PLSliverNetworkStats, self).__init__(reporter, "plnode_sliver_network", [ "rx_packets", "tx_packets", "rx_bytes", "tx_bytes" ], [ "pkts/s", "pkts/s", "Bps", "Bps" ])


# # --------------------------------------------------------------------

# class PLSliverState(GMOCMeasurement):
#     """Measurement class for PlanetLab sliver state metrics"""

#     def __init__(self, reporter = None):
#         super(PLSliverState, self).__init__(reporter, "plnode_sliver_state", [ "cpu_host", "disk_host", "disk_used", "mem_host", "processes", "resident_set_size", "uptime", "virtual_mem_size" ], [ "%%", "%%", "KB", "%%", "N", "KB", "min", "KB" ])


# # --------------------------------------------------------------------

# class NetworkStats(GMOCMeasurement):
#     """Measurement class for network statistics"""

#     def __init__(self, reporter = None):
#         super(NetworkStats, self).__init__(reporter, "network_stats", [ "rx_pps", "tx_pps", "rx_bps", "tx_bps" ], [ "pkts/s", "pkts/s", "bits/s", "bits/s" ])


# # --------------------------------------------------------------------

# class TargetPingable(GMOCMeasurement):
#     """Measurement class for host pingability"""

#     def __init__(self, reporter = None):
#         super(TargetPingable, self).__init__(reporter, "target_pingable", [ "result" ], [ "nagios_stat"])


# # --------------------------------------------------------------------

# class AMAPIGetVersion(GMOCMeasurement):
#     """Measurement class for the GENI AM API getversion call"""

#     def __init__(self, reporter = None):
#         super(AMAPIGetVersion, self).__init__(reporter, "geni_am_getversion", [ "result" ], [ "nagios_stat" ])


# # --------------------------------------------------------------------

# class AMAPIListResources(GMOCMeasurement):
#     """Measurement class for the GENI AM API listresources call"""

#     def __init__(self, reporter = None):
#         super(AMAPIListResources, self).__init__(reporter, "geni_am_listresources", [ "result" ], [ "nagios_stat" ])


# # --------------------------------------------------------------------

# class PhysicalAddress(object):
#     """Physical location as a mailing address"""

#     def __init__(self, street = None, city = None, state = None, postcode = None):
#         self.street = street
#         self.street2 = None
#         self.city = city
#         self.state = state
#         self.postcode = postcode
#         self.country = 'US'

#     def validate(self):
#         if self.street == None:
#             raise ValueError("PhysicalAddress must have a valid street (first line)")
#         elif self.city == None:
#             raise ValueError("PhysicalAddress must have a valid city")
#         elif self.state == None:
#             raise ValueError("PhysicalAddress must have a valid state/province")
#         elif self.postcode == None:
#             raise ValueError("PhysicalAddress must have a valid postal code")

#     def toXML(self, doc, parent):
#         self.validate()

#         if parent == None:
#             parent = doc.documentElement

#         node = doc.createElement('address')
#         node.setAttribute('street1', self.street)
        
#         if self.street2 != None:
#             node.setAttribute('street2', self.street2)

#         node.setAttribute('city', self.city)
#         node.setAttribute('state', self.state)
#         node.setAttribute('postal_code', self.postcode)
        
#         if self.country != None:
#             node.setAttribute('country', self.country)

#         parent.appendChild(node)

#         return node


# # --------------------------------------------------------------------

# class GeoLocation(object):
#     """Geocoordinates of a physical location"""
#     __metaclass__ = GMOCMeta
#     __simpleProps__ = [ ['longitude', float], ['latitude', float] ]

#     def __init__(self, longitude, latitude):
#         self.longitude = longitude
#         self.latitude = latitude

#     def validate(self):
#         if self.longitude == None:
#             raise ValueError("GeoLocation must have a valid longitude")
#         elif self.latitude == None:
#             raise ValueError("GeoLocation must have a valid latitude")

#     def toXML(self, doc, parent):
#         self.validate()

#         if parent == None:
#             parent = doc.documentElement

#         node = doc.createElement('geo_location')
#         node.setAttribute('longitude', str(self.longitude))
#         node.setAttribute('latitude', str(self.latitude))
#         parent.appendChild(node)

#         return node


# # --------------------------------------------------------------------

# class Location(GMOCObject):
#     """Physical location"""
#     __metaclass__ = GMOCMeta
#     __ID__ = validateLocationURN
#     __simpleProps__ = [ ['address', PhysicalAddress], ['geo', GeoLocation] ]

#     def __init__(self, id, address = None, geo = None):
#         super(Location, self).__init__(id)
#         self.address = address
#         self.geo = geo

#     def validate(self):
#         super(Location, self).validate()
    
#         if self.address == None and self.geo == None:
#             raise ValueError("Location " + self.id + " must have either a valid address or geolocation")

#         if self.geo != None:
#             self.geo.validate()

#         if self.address != None:
#             self.address.validate()

#     def toXML(self, doc, parent):
#         self.validate()

#         if parent == None:
#             parent = doc.documentElement

#         node = doc.createElement('location')
#         node.setAttribute('name', self.id)

#         if self.address != None:
#             self.address.toXML(doc, node)

#         if self.geo != None:
#             self.geo.toXML(doc, node)

#         parent.appendChild(node)

#         return node


# # --------------------------------------------------------------------

# class Contact(GMOCObject):
#     """A user that is responsible for some GENI thing"""
#     __metaclass__ = GMOCMeta
#     __ID__ = validateContactURN

#     def __init__(self, id, givenName = None, lastName = None, email = None, phone = None):
#         super(Contact, self).__init__(id)
#         self.givenName = givenName
#         self.lastName = lastName
#         self.email = email
#         self.phone = phone

#     def validate(self):
#         super(Contact, self).validate()
        
#         # if any of the other properties are set, we have to validate all of them
#         # but it's okay if just the ID is set
#         if self.givenName != None or self.lastName != None or self.email != None:
#             if self.givenName == None:
#                 raise ValueError("contact " + self.id + " must have a valid given name")
#             elif self.lastName == None:
#                 raise ValueError("contact " + self.id + " must have a valid last name")
#             elif self.email == None:
#                 raise ValueError("contact " + self.id + " must have a valid email address")

#     def toXML(self, doc, parent = None):
#         self.validate()

#         if parent == None:
#             parent = doc.documentElement

#         node = doc.createElement('contact')
#         node.setAttribute('urn', self.id)

#         if self.givenName != None or self.lastName != None or self.email != None:
#             node.setAttribute('given_name', self.givenName)
#             node.setAttribute('last_name', self.lastName)
#             node.setAttribute('email', self.email)

#             if self.phone != None:
#                 node.setAttribute('phone', self.phone)

#         parent.appendChild(node)

#         return node



# # --------------------------------------------------------------------

# class Organization(GMOCObject):
#     """An organization that participates in GENI"""
#     __metaclass__ = GMOCMeta
#     __ID__ = validateOrganizationURN
#     __simpleProps__ = [ ['location', Location], ['primaryContact', Contact], ['escalationContact', Contact], ['url', str] ]

#     def __init__(self, id, type = ORG_TYPE_CAMPUS, location = None, primaryContact = None, escalationContact = None, url = None):
#         super(Organization, self).__init__(id)
#         self.__type = type
#         self.location = location
#         self.primaryContact = primaryContact
#         self.escalationContact = escalationContact
#         self.url = url

#     def validate(self):
#         super(Organization, self).validate()

#         if self.location != None or self.primaryContact != None:
#             if self.location == None:
#                 raise ValueError("Organization " + self.id + " must have a valid location")
#             elif self.primaryContact == None:
#                 raise ValueError("Organization " + self.primaryContact + " must have a valid primary contact")

#             self.location.validate()
#             self.primaryContact.validate()

#     def toXML(self, doc, parent):
#         self.validate()

#         if parent == None:
#             parent = doc.documentElement

#         node = doc.createElement('organization')
#         node.setAttribute('name', self.id)

#         if self.location != None or self.primaryContact != None:
#             node.setAttribute('location', self.location.id)
#             node.setAttribute('primary_contact', self.primaryContact.id)
#             node.setAttribute('type', self.type)
#             if self.escalationContact != None:
#                 node.setAttribute('secondary_contact', self.escalationContact.id)

#         parent.appendChild(node)

#         return node

#     @property
#     def type(self):
#         return self.__type

#     @type.setter
#     def type(self, value):
#         if value == ORG_TYPE_CAMPUS or value == ORG_TYPE_BACKBONE or value == ORG_TYPE_RACK_VENDOR or value == ORG_TYPE_META or value == ORG_TYPE_REGIONAL:
#             self.__type = value
#         else:
#             raise ValueError("type must be one of ORG_TYPE_BACKBONE, ORG_TYPE_CAMPUS, ORG_TYPE_RACK_VENDOR, ORG_TYPE_META, or ORG_TYPE_REGIONAL")


# # --------------------------------------------------------------------

# class POP(GMOCObject):
#     """A point of presence (POP) in the GENI mesoscale network"""
#     __metaclass__ = GMOCMeta
#     __ID__ = validatePOPURN
#     __simpleProps__ = [ ['location', Location], ['operator', Organization] ]

#     def __init__(self, id, location = None, operator = None):
#         super(POP, self).__init__(id)
#         self.location = location
#         self.operator = operator
#         self._aggregates = []
#         self._authorities = []

#     def validate(self):
#         super(POP, self).validate()

#         if self.location != None or self.operator != None:
#             if self.location == None:
#                 raise ValueError("POP " + self.id + " must have a valid location")
#             elif self.operator == None:
#                 raise ValueError("POP " + self.id + " must have a valid operator")

#             self.location.validate()
#             self.operator.validate()

#     def toXML(self, doc, parent):
#         self.validate()

#         if parent == None:
#             parent = doc.documentElement

#         node = doc.createElement('pop')
#         node.setAttribute('name', self.id)

#         if self.location != None or self.operator != None:
#             node.setAttribute('location', self.location.id)
#             node.setAttribute('operator', self.operator.id)

#         parent.appendChild(node)

#         return node

#     @property
#     def aggregates(self):
#         return self._aggregates

#     @property
#     def sliceAuthorities(self):
#         return self._authorities

#     @property
#     def resources(self):
#         resources = {}

#         for sa in self._authorities:
#             for slice in sa.slices:
#                 for res in slice.resources:
#                     resources[res.id] = res

#         return resources.values()

#     @aggregates.setter
#     def aggregates(self, aggList):
#         self._setListProp('aggregates', aggList, Aggregate, '_pop')

#     @sliceAuthorities.setter
#     def sliceAuthorities(self, saList):
#         self._setListProp('authorities', saList, SliceAuthority, '_pop')


# # --------------------------------------------------------------------

# class SliceAuthority(GMOCObject):
#     """A slice authority that defines and manages slice data"""
#     __metaclass__ = GMOCMeta
#     __ID__ = validateAuthorityURN
#     __simpleProps__ = [ ['type', str], ['version', str], ['operator', Organization] ]

#     def __init__(self, id, type = None, version = None, operator = None, pop = None):
#         super(SliceAuthority, self).__init__(id)
#         self.type = type
#         self.version = version
#         self.operator = operator
#         self.pop = pop
#         self._slices = []
#         self._users = []
            
#     def validate(self):
#         super(SliceAuthority, self).validate()

#         if self.type != None or self.version != None or self.operator != None:
#             if self.type == None:
#                 raise ValueError("SliceAuthority " + self.id + " must have a valid type")
#             elif self.version == None:
#                 raise ValueError("SliceAuthority " + self.id + " must have a valid version")
#             elif self.operator == None:
#                 raise ValueError("SliceAuthority " + self.id + " must have a valid operator")
#             elif self.pop == None:
#                 raise ValueError("SliceAuthority " + self.id + " must have a valid POP")

#             self.operator.validate()
#             self.pop.validate()

#     def toXML(self, doc, parent):
#         self.validate()

#         if parent == None:
#             parent = doc.documentElement

#         node = doc.createElement('sa')
#         node.setAttribute('urn', self.id)
#         node.setAttribute('name', self.id)    # redundant hack
        
#         if self.pop != None:
#             node.setAttribute('pop', self.pop.id)

#         if self.type != None or self.version != None or self.operator != None:
#             node.setAttribute('type', self.type)
#             node.setAttribute('version', self.version)
#             node.setAttribute('organization', self.operator.id)

#         for slice in self.slices:
#             slice.toXML(doc, node)

#         for user in self.users:
#             user.validate()
#             unode = doc.createElement('user')
#             unode.setAttribute('urn', user.id)
#             node.appendChild(unode)

#         parent.appendChild(node)

#         return node

#     @property
#     def pop(self):
#         return self._pop

#     @property
#     def slices(self):
#         return self._slices

#     @property
#     def users(self):
#         return self._users

#     @pop.setter
#     def pop(self, value):
#         self._putIntoList('authorities', value, POP)
#         self._pop = value

#     @slices.setter
#     def slices(self, sliceList):
#         self._setListProp('slices', sliceList, Slice, '_sa')

#     @users.setter
#     def users(self, userList):
#         self._setListProp('users', userList, Contact)


# # --------------------------------------------------------------------

# class Slice(GMOCObject):
#     """A slice in the GENI network"""
#     __metaclass__ = GMOCMeta
#     __ID__ = validateURN
#     __simpleProps__ = [ ['created', datetime.datetime], ['expires', datetime.datetime], ['creator', Contact], ['operator', Organization], ['primaryContact', str] ]

#     def __init__(self, id, uuid = None, created = None, expires = None, creator = None, operator = None, sa = None):
#         super(Slice, self).__init__(id)
#         self.uuid = uuid
#         self.creator = creator
#         self.created = created
#         self.expires = expires
#         self.operator = operator
#         self.sliceAuthority = sa
#         self._primaryContact = None
#         self._slivers = []

#         if created == None:
#             self.created = datetime.datetime.utcnow()

#     def addMeasurement(self, value):
#         sa = self.sliceAuthority

#         if value.reporter == None:
#             value.reporter = sa.id

#         if value.type == "flowvisor_slice_stats":
#             value._name = value.reporter + "-" + value.type + "-slice_" + self.id                                                                                                                                    
#             value._tag = "slice:" + self.id    
#         else:
#             raise TypeError("Measurement type '" + value.type + "' is not valid for Slice objects")

#         self._measurements.append(value)

#     def validate(self):
#         super(Slice, self).validate()

#         if self.operator != None or self.creator != None:
#             if self.operator == None:
#                 raise ValueError("Slice " + self.id + " must have a valid operator")
#             elif self.creator == None:
#                 raise ValueError("Slice " + self.id + " must have a valid creator")
#             elif self.sliceAuthority == None:
#                 raise ValueError("Slice " + self.id + " must have a valid slice authority")

#             self.creator.validate()
#             self.operator.validate()
#             self.sliceAuthority.validate()

#     def toXML(self, doc, parent):
#         self.validate()

#         if parent == None:
#             parent = doc.documentElement

#         node = doc.createElement('slice')
#         node.setAttribute('urn', self.id)

#         if self.operator != None or self.creator != None:
#             node.setAttribute('operator', self.operator.id)

#             if self.creator != None:
#                 node.setAttribute('creator', self.creator.id)

#                 if self.created != None:
#                     node.setAttribute('created', str(int(time.mktime(self.created.timetuple()))))

#                     if self.expires != None:
#                         node.setAttribute('expires', str(int(time.mktime(self.expires.timetuple()))))
           
#                     if self.uuid != None:
#                         node.setAttribute('uuid', str(self.uuid))
 
#                     if self.primaryContact != None:
#                         node.setAttribute('primary_contact', self.primaryContact)
#                     else:
#                         node.setAttribute('primary_contact', self.creator.email)

#         parent.appendChild(node)

#         return node

#     @property
#     def uuid(self):
#         return self.__uuid

#     @property
#     def sliceAuthority(self):
#         return self._sa

#     @property
#     def slivers(self):
#         return self._slivers

#     @property
#     def resources(self):
#         resources = {}

#         for sliver in self._slivers:
#             for res in sliver.resources:
#                 resources[res.id] = res

#         return resources.values()

#     @uuid.setter
#     def uuid(self, value):
#         if value != None:
#             if type(value) == uuid.UUID:
#                 self.__uuid = value
#             elif isinstance(value, str):
#                 self.__uuid = uuid.UUID(value)
#             else:
#                 raise TypeError("uuid must be a valid UUID")
#         else:
#             self.__uuid = None

#     @sliceAuthority.setter
#     def sliceAuthority(self, value):
#         self._putIntoList('slices', value, SliceAuthority)
#         self._sa = value

#     @slivers.setter
#     def slivers(self, sliverList):
#         self._setListProp('slivers', sliverList, Sliver, '_slice')


# # --------------------------------------------------------------------

# class Aggregate(GMOCObject):
#     """An aggregate manager"""
#     __metaclass__ = GMOCMeta
#     __ID__ = validateAggregate
#     __simpleProps__ = [ ['type', str], ['version', str], ['operator', Organization] ]

#     def __init__(self, id, type = None, version = None, pop = None, operator = None):
#         super(Aggregate, self).__init__(id)
#         self.type = type
#         self.version = version
#         self.pop = pop
#         self.operator = operator
#         self.__state = AM_STATE_UNKNOWN
#         self._slivers = []
#         self._resources = []

#     def addMeasurement(self, value):
#         if value.reporter == None:
#             value.reporter = self.id
        
#         if value.type == "node_cpu" or value.type == "node_disk" or value.type == "geni_am_getversion" or value.type == "geni_am_listresources":
#             value._name = value.reporter + "-" + value.type + "-aggregate_" + self.id                                                                                                                               
#             value._tag = "aggregate:" + self.id  
#         elif value.type == "foam_state":
#             if self.type == None or not self.type.upper() == "FOAM":
#                 raise ValueError("Aggregate " + self.id + " is not FOAM")

#             value._name = value.reporter + "-" + value.type
#             value._tag = self.id
#         else:
#             raise TypeError("Measurement type '" + value.type + "' is invalid for Aggregate objects.")

#         self._measurements.append(value)

#     def validate(self):
#         super(Aggregate, self).validate()

#         if self.pop == None:
#             raise ValueError("Aggregate " + self.id + " must have a valid POP")

#         if self.type != None or self.version != None or self.operator != None:
#             if self.type == None:
#                 raise TypeError("Aggregate " + self.id + " must have a valid type")
#             elif self.version == None:
#                 raise TypeError("Aggregate " + self.id + " must have a valid version")
#             elif self.pop == None:
#                 raise TypeError("Aggregate " + self.id + " must have a valid POP")
#             elif self.operator == None:
#                 raise TypeError("Aggregate " + self.id + " must have a valid operator")

#             self.pop.validate()
#             self.operator.validate()

#     def toXML(self, doc, parent):
#         self.validate()

#         if parent == None:
#             parent = doc.documentElement

#         node = doc.createElement('aggregate')
#         node.setAttribute('name', self.id)
# #        node.setAttribute('type', self.type)
        
# #        if self.pop != None:
# #            node.setAttribute('pop', self.pop.id)

#         if self.type != None or self.version != None or self.operator != None:
#             node.setAttribute('type', self.type)
#             node.setAttribute('version', self.version)
#             node.setAttribute('pop', self.pop.id)
#             node.setAttribute('organization', self.operator.id)

#         for sliver in self.slivers:
#             sliver.toXML(doc, node)

#         parent.appendChild(node)

#         return node

#     @property
#     def pop(self):
#         return self._pop

#     @property
#     def state(self):
#         return self.__state

#     @property
#     def slivers(self):
#         return self._slivers

#     @property
#     def resources(self):
#         return self._resources

#     @property
#     def slices(self):
#         slices = {}

#         for sliver in self._slivers:
#             slice = sliver.slice
#             slices[slice.id] = slice

#         return slices.values()

#     @pop.setter
#     def pop(self, value):
#         self._putIntoList('aggregates', value, POP)
#         self._pop = value

#     @state.setter
#     def state(self, value):
#         if value == AM_STATE_UNKNOWN or value == AM_STATE_DEGRADED or value == AM_STATE_DOWN or value == AM_STATE_UP:
#             self.__state = value
#         else:
#             raise ValueError("state must be one of AM_STATE_UNKNOWN, AM_STATE_DEGRADED, AM_STATE_DOWN, or AM_STATE_UP")

#     @slivers.setter
#     def slivers(self, sliverList):
#         self._setListProp('slivers', sliverList, Sliver, '_aggregate')

#     @resources.setter
#     def resources(self, resList):
#         self._setListProp('resources', resList, Resource, '_aggregate')

#         for resource in resList:
#             resource._pop = self.pop


# # --------------------------------------------------------------------

# class ResourceMapping(GMOCObject):
#     pass

# class Sliver(GMOCObject):
#     """A sliver"""
#     __metaclass__ = GMOCMeta
#     __ID__ = validateSliverURN
#     __simpleProps__ = [ ['expires', datetime.datetime], ['creator', Contact], ['created', datetime.datetime], ['approved', bool] ]

#     def __init__(self, id, expires = None, state = SLIVER_STATE_UNKNOWN, creator = None, slice = None, aggregate = None):
#         super(Sliver, self).__init__(id)
#         self.expires = expires
#         self.state = state
#         self.creator = creator
#         self.__uuid = None
#         self.created = datetime.datetime.utcnow()
#         self._resources = []
#         self.slice = slice
#         self.aggregate = aggregate
#         self.approved = False

#     def addMeasurement(self, value):
#         if value.reporter == None:
#             value.reporter = self.id

#         agg = self._aggregate
#         if not isinstance(agg, Aggregate):
#             raise ValueError("Sliver " + self.id + " must have a valid aggregate")

#         if value.type == "openflow_sliver_stats":
#             value._name = value.reporter + "-" + value.type + "-sliver_" + self.id + "-aggregate_" + agg.id
#             value._tag = "sliver:" + self.id + ",aggregate:" + agg.id
#         elif value.type == "foam_sliver_state" or value.type == " plnode_sliver_network" or value.type == "plnode_sliver_state":
#             value._name = value.reporter + "-" + value.type + "-sliver_" + self.id
#             value._tag = "sliver:" + self.id
#         else:
#             raise TypeError("Measurement type '" + value.type + "' is not valid for Sliver objects.")

#         self._measurements.append(value)

#     def validate(self):
#         super(Sliver, self).validate()

#         if self.expires != None or self.creator != None:
#             if self.expires == None:
#                 raise ValueError("Sliver " + self.id + " must have a valid expiry time")
#             elif self.creator == None:
#                 raise ValueError("Sliver " + self.id + " must have a valid creator")
#             elif self.slice == None:
#                 raise ValueError("Sliver " + self.id + " must have a valid slice")
#             elif self.aggregate == None:
#                 raise ValueError("Sliver " + self.id + " must have a valid aggregate")
        
#             self.slice.validate()
#             self.aggregate.validate()

#     def toXML(self, doc, parent):
#         self.validate()

#         if parent == None:
#             parent = doc.documentElement

#         node = doc.createElement('sliver')
#         node.setAttribute('local_name', self.id)

#         if self.uuid != None:
#             node.setAttribute('uuid', str(self.uuid))
#         else:
#             node.setAttribute('uuid', '')

#         if self.expires != None or self.creator != None:
#             created = self.created
#             if created == None:
#                 created = datetime.datetime.now()

#             node.setAttribute('created', str(int(time.mktime(created.timetuple()))))
#             node.setAttribute('expires', str(int(time.mktime(self.expires.timetuple()))))
#             node.setAttribute('creator', self.creator.id)
#             node.setAttribute('slice_urn', self.slice.id)
#             node.setAttribute('slice_uuid', str(self.slice.uuid))
#             node.setAttribute('state', self.state)
        
#             if self.approved == True:
#                 node.setAttribute("approved", "true")
#             else:
#                 node.setAttribute("approved", "false")

#             for resMap in self._resources:
#                 resMap.toXML(doc, node)

#         parent.appendChild(node)

#         return node

#     @property
#     def state(self):
#         return self.__state

#     @property
#     def uuid(self):
#         return self.__uuid

#     @property
#     def resources(self):
#         resList = list()
#         for resMap in self._resources:
#             resList.append(resMap.resource)

#         return resList

#     @property
#     def aggregate(self):
#         return self._aggregate

#     @property
#     def slice(self):
#         return self._slice

#     @slice.setter
#     def slice(self, value):
#         self._putIntoList('slivers', value, Slice)
#         self._slice = value

#     @state.setter
#     def state(self, value):
#         if value == SLIVER_STATE_UNKNOWN or value == SLIVER_STATE_DEGRADED or value == SLIVER_STATE_DOWN or value == SLIVER_STATE_UP:
#             self.__state = value
#         else:
#             raise ValueError("state must be one of SLIVER_STATE_UNKNOWN, SLIVER_STATE_DEGRADED, SLIVER_STATE_DOWN, SLIVER_STATE_UP")

#     @uuid.setter
#     def uuid(self, value):
#         if type(value) == uuid.UUID:
#             self.__uuid = value
#         elif isinstance(value, str):
#             self.__uuid = uuid.UUID(value)
#         else:
#             raise TypeError("uuid must be a UUID")

#     @aggregate.setter
#     def aggregate(self, value):
#         self._putIntoList('slivers', value, Aggregate)
#         self._aggregate = value


# # --------------------------------------------------------------------

# class Resource(GMOCObject):
#     """A resource in the GENI network"""
#     __metaclass__ = GMOCMeta
#     __ID__ = validateURN
#     __simpleProps__ = [ ['type', str], ['operator', Organization], ['description', str] ]

#     def __init__(self, id, type = None, state = RESOURCE_STATE_UNKNOWN, pop = None, operator = None, description = None, aggregate = None):
#         super(Resource, self).__init__(id)
#         self.type = type
#         self.__state = state
#         self.pop = pop
#         self.operator = operator
#         self.aggregate = aggregate
#         self._intfs = []
#         self._slivers = []
#         self.description = description

#     def addMeasurement(self, value):
#         if value.reporter == None:
#             value.reporter = self.id

#         if value.type == "node_cpu" or value.type == "node_disk" or value.type == "vm_count" or value.type == "target_pingable":
#             value._name = value.reporter + "-" + value.type + "-resource_" + self.id                                                                                                                               
#             value._tag = "resource:" + self.id  
#         elif value.type == "flowvisor_dpid_stats":
#             value._name = value.reporter + "-" + value.type + "-dpid_" + self.id
#             value._tag = "dpid:" + self.id
#         elif value.type == "datapath_stats":
#             agg = self.aggregate
#             if not isinstance(agg, Aggregate):
#                 raise ValueError("Resource " + self.id + " does not have a valid aggregate")

#             value._name = value.reporter + "-" + value.type + "-resource_" + self.id + "-aggregate_" + agg.id
#             value._tag = "resource:" + self.id + ",aggregate:" + agg.id
#         else:
#             raise TypeError("Measurement type '" + value.type + "' is not valid for Resource objects.")

#         self._measurements.append(value)

#     def validate(self):
#         super(Resource, self).validate()

#         if self.type != None or self.pop != None or self.operator != None:
#             if self.type == None:
#                 raise ValueError("Resource " + self.id + " must have a valid type")
#             elif self.pop == None:
#                 raise ValueError("Resource " + self.id + " must have a valid POP")
#             elif self.operator == None:
#                 raise ValueError("Resource " + self.id + " must have a valid operator")
#             elif self.aggregate == None:
#                 raise ValueError("Resource " + self.id + " must have a valid aggregate")
        
#             self.pop.validate()
#             self.operator.validate()
#             self.aggregate.validate()

#     def toXML(self, doc, parent):
#         self.validate()

#         if parent == None:
#             parent = doc.documentElement

#         node = doc.createElement('resource')
#         node.setAttribute('name', self.id)

#         if self.type != None or self.pop != None or self.operator != None:
#             node.setAttribute('type', self.type)
#             node.setAttribute('aggregate', self.aggregate.id)
#             node.setAttribute('pop', self.pop.id)
#             node.setAttribute('organization', self.operator.id)

#             if self.description == None:
#                 node.setAttribute('description', '')
#             else:
#                 node.setAttribute('description', self.description)

#             node.setAttribute('state', self.state)

#         for intf in self.interfaces:
#             intf.toXML(doc, node)

#         parent.appendChild(node)

#         return node

#     @property
#     def state(self):
#         return self.__state

#     @property
#     def pop(self):
#         return self._pop

#     @property
#     def interfaces(self):
#         return self._intfs

#     @property
#     def aggregate(self):
#         return self._aggregate

#     @property
#     def slivers(self):
#         sliverList = list()
#         for resMap in self._slivers:
#             sliverList.append(resMap.sliver)

#         return sliverList

#     @property
#     def slices(self):
#         slices = {}

#         for resMap in self._slivers:
#             sliver = resMap.sliver
#             if sliver != None:
#                 slice = sliver.slice
#                 slices[slice.id] = slice

#         return slices.values()

#     @state.setter
#     def state(self, value):
#         if value == RESOURCE_STATE_UNKNOWN or value == RESOURCE_STATE_DEGRADED or value == RESOURCE_STATE_DOWN or value == RESOURCE_STATE_UP:
#             self.__state = value
#         else:
#             raise ValueError("state must be one of RESOURCE_STATE_UNKNOWN, RESOURCE_STATE_DEGRADED, RESOURCE_STATE_DOWN, or RESOURCE_STATE_UP")

#     @pop.setter
#     def pop(self, value):
#         if value != None:
#             if isinstance(value, POP):
#                 self._pop = value
#             else:
#                 raise TypeError("pop must be of type POP")            
#         else:
#             self._pop = value

#     @aggregate.setter
#     def aggregate(self, value):
#         self._putIntoList('resources', value, Aggregate)
#         self._aggregate = value

#     @interfaces.setter
#     def interfaces(self, intfList):
#         self._setListProp('intfs', intfList, Interface, '_resource')


# # --------------------------------------------------------------------

# class ResourceMapping(GMOCObject):
#     """A mapping between a sliver and a resource"""
#     __metaclass__ = GMOCMeta
#     __ID__ = validateText

#     def __init__(self, id, type = None, sliver = None, resource = None):
#         super(ResourceMapping, self).__init__(id)
#         self.type = type
#         self._sliver = sliver
#         self._resource = resource

#         self.sliver = sliver
#         self.resource = resource

#     def addMeasurement(self, value):
#         if value.reporter == None:
#             value.reporter = self.resource.id

#         if value.type == "network_stats":
#             value._name = value.reporter + "-" + value.type + "-sliverlocalname_" + self.sliver.id + "-resource_" + self.resource.id
#             value._tag = "sliverlocalname:" + self.sliver.id + ",resource:" + self.resource.id
#         else:
#             raise TypeError("Measurement type '" + value.type + "' is not valid for ResourceMapping objects.")

#         self._measurements.append(value)

#     def validate(self):
#         super(ResourceMapping, self).validate()
#         if self.type == None:
#             raise ValueError("ResourceMapping " + self.id + " must have a valid type")
#         elif self.sliver == None:
#             raise ValueError("ResourceMapping " + self.id + " must have a valid sliver")
#         elif self.resource == None:
#             raise ValueError("ResourceMapping " + self.id + " must have a valid resource")

#     def toXML(self, doc, parent):
#         self.validate()

#         if parent == None:
#             parent = doc.documentElement

#         node = doc.createElement('resource_mapping')
#         node.setAttribute('local_name', self.id)
#         node.setAttribute('type', self.type)
#         node.setAttribute('resource', self.resource.id)
#         parent.appendChild(node)

#         return node

#     @property
#     def sliver(self):
#         return self._sliver

#     @property
#     def resource(self):
#         return self._resource

#     @sliver.setter
#     def sliver(self, value):
#         if self.resource != None:
#             slivers = self._resource._slivers
#             if self in slivers:
#                 slivers.remove(self)
#                 self.resource._slivers = slivers

#         if value != None:
#             if not isinstance(value, Sliver):
#                 raise TypeError("sliver must be of type Sliver")

#             if self.resource != None:
#                 slivers = self.resource._slivers
#                 slivers.append(self)
#                 self.resource._slivers = slivers

#         self._sliver = value

#     @resource.setter
#     def resource(self, value):
#         if self.sliver != None:
#             resources = self._sliver._resources
#             if self in resources:
#                 resources.remove(self)
#                 self.sliver._resources = resources

#         if value != None:
#             if not isinstance(value, Resource):
#                 raise TypeError("resource must be of type Resource")

#             if self.sliver != None:
#                 resources = self.sliver._resources
#                 resources.append(self)
#                 self.sliver._resources = resources

#         self._resource = value


# # --------------------------------------------------------------------

# class Interface(GMOCObject):
#     pass

# class Interface(GMOCObject):
#     """An interface on a GENI resource"""
#     __metaclass__ = GMOCMeta
#     __ID__ = validateInterfaceURN
#     __simpleProps__ = [ ['contractedBandwidth', float], ['maxBPS', float], ['parent', Interface] ]

#     def __init__(self, id, opState = INTF_STATE_UNKNOWN, resource = None):
#         super(Interface, self).__init__(id)
#         self.__adminState = INTF_ADMIN_NORMAL
#         self.resource = resource
#         self._addresses = []
#         self._vlans = []
#         self._circuits = []
#         self.__opState = opState
#         self.contractedBandwidth = 0.0
#         self.maxBPS = 0.0
#         self._parent = None

#     def validate(self):
#         super(Interface, self).validate()

#         if self.resource == None:
#             raise ValueError("Interface " + self.id + " must have a valid resource")
 
#         if self.resource != None:
#             self.resource.validate()

#     def toXML(self, doc, parent):
#         self.validate()

#         if parent == None:
#             parent = doc.documentElement

#         node = doc.createElement('interface')
#         node.setAttribute('name', self.id)
        
#         if self.resource != None:
#             if self.parent != None:
#                 node.setAttribute('parent', self.parent.id)
#             node.setAttribute('state', self.opState)

#         for addr in self.addresses:
#             addr.toXML(doc, node)

#         for vlan in self.vlans:
#             vlan.toXML(doc, node)

#         parent.appendChild(node)

#         return node
        

#     @property
#     def opState(self):
#         return self.__opState

#     @property
#     def adminState(self):
#         return self.__adminState

#     @property
#     def addresses(self):
#         return self._addresses

#     @property
#     def resource(self):
#         return self._resource

#     @property
#     def circuits(self):
#         return self._circuits

#     @property
#     def vlans(self):
#         return self._vlans

#     @opState.setter
#     def opState(self, value):
#         if value == INTF_STATE_UNKNOWN or value == INTF_STATE_DEGRADED or value == INTF_STATE_DOWN or value == INTF_STATE_UP:
#             self.__opState = value
#         else:
#             raise ValueError("opState must be one of INTF_STATE_UNKNOWN, INTF_STATE_DEGRADED, INTF_STATE_DOWN, or INTF_STATE_UP")

#     @adminState.setter
#     def adminState(self, value):
#         if value == INTF_ADMIN_UNKNOWN or value == INTF_ADMIN_AVAILABLE or value == INTF_ADMIN_DECOMMISSIONED or value == INTF_ADMIN_MAINTENANCE or value == INTF_ADMIN_NORMAL or value == INTF_ADMIN_PLANNING or value == INTF_ADMIN_PROVISIONING:
#             self.__adminState = value
#         else:
#             raise ValueError("adminState must be one of INTF_ADMIN_AVAILABLE, INTF_ADMIN_AVAILABLE, INTF_ADMIN_DECOMMISSIONED, INTF_ADMIN_MAINTENANCE, INTF_ADMIN_NORMAL, INTF_ADMIN_PLANNING, or INTF_ADMIN_PROVISIONING")

#     @addresses.setter
#     def addresses(self, addrList):
#         if not isinstance(addrList, list):
#             raise TypeError("addrList must be a list")
        
#         for addr in addrList:
#             if not isinstance(addr, NetAddress):
#                 raise TypeError("all elements in addrList must be a NetAddress object")

#         self._addresses = addrList

#     @resource.setter
#     def resource(self, value):
#         self._putIntoList('intfs', value, Resource)
#         self._resource = value

#     @vlans.setter
#     def vlans(self, value):
#         if not isinstance(value, list):
#             raise TypeError("vlans must be a list")

#         for vlan in value:
#             if not isinstance(vlan, VLAN):
#                 raise TypeError("all elements in vlans must be of type VLAN")

#         self._vlans = value


# # --------------------------------------------------------------------    

# class NetAddress(object):
#     """An address on the network"""

#     def __init__(self, addr = None, type = NETADDR_TYPE_IPV4):
#         self.addr = addr
#         self.type = type
    
#         if self.type == NETADDR_TYPE_IPV4:
#             self.maskLength = 24
#         elif self.type == NETADDR_TYPE_IPV6:
#             self.maskLength = 64
#         else:
#             self.maskLength = 0

#     def validate(self):
#         if self.addr == None:
#             raise ValueError("NetAddress must have a valid IPv4, IPv6, or MAC address")

#     def toXML(self, doc, parent):
#         self.validate()

#         if parent == None:
#             parent = doc.documentElement

#         node = doc.createElement('address')
#         node.setAttribute('type', self.type)
        
#         tnode = doc.createTextNode(self.addr)
#         node.appendChild(tnode)
#         parent.appendChild(node)

#         return node

#     @property
#     def type(self):
#         return self.__type

#     @type.setter
#     def type(self, value):
#         if value == NETADDR_TYPE_IPV4 or value == NETADDR_TYPE_IPV6 or value == NETADDR_TYPE_MAC:
#             self.__type = value
#         else:
#             raise ValueError("type must be one of NETADDR_TYPE_IPV4, NETADDR_TYPE_IPV6, or NETADDR_TYPE_MAC")

#     def toString(self):
#         return


# # --------------------------------------------------------------------

# class Network(object):
#     pass

# class Circuit(GMOCObject):
#     """A network link between two or more GENI resource"""
#     __metaclass__ = GMOCMeta
#     __ID__ = validateCircuitURN
#     __simpleProps__ = [ ['channel', str], ['reservedBandwidth', float] ]

#     def __init__(self, id, type = None, network = None):
#         super(Circuit, self).__init__(id)
#         self.__type = type
#         self.__adminState = CIRCUIT_ADMIN_NORMAL
#         self._endpoints = []
#         self.network = network
#         self.channel = None
#         self.reservedBandwidth = 0.0
        
#     def validate(self):
#         super(Circuit, self).validate()

#     def toXML(self, doc, parent):
#         self.validate()

#         if parent == None:
#             parent = doc.documentElement

#         node = doc.createElement('circuit')
#         node.setAttribute('name', self.id)

#         if self.type != None or self.adminState != None:
#             node.setAttribute('type', self.type)
#             node.setAttribute('administrative_state', self.adminState)
         
#             if self.channel != None:
#                 node.setAttribute('channel', self.channel)

#             if self.reservedBandwidth != 0.0:
#                 node.setAttribute('reserved_bw', str(self.reservedBandwidth))

#         for endp in self.endpoints:
#             if endp.resource != None:
#                 inode = doc.createElement('endpoint')
#                 inode.setAttribute('device_name', endp.resource.id)
#                 inode.setAttribute('interface_name', endp.id)
#                 node.appendChild(inode)

#         parent.appendChild(node)

#         return node

#     @property
#     def type(self):
#         return self.__type

#     @property
#     def adminState(self):
#         return self.__adminState

#     @property
#     def endpoints(self):
#         return self._endpoints

#     @property
#     def network(self):
#         return self._network

#     @property
#     def resources(self):
#         resources = {}

#         for endp in self._endpoints:
#             if endp.resource.id != None:
#                 resources[endp.resource.id] = endp.resource

#         return resources.values()

#     @property
#     def addresses(self):
#         addrs = {}

#         for endp in self._endpoints:
#             for addr in endp.addresses:
#                 addrs[addr.toString()] = addr

#         return addrs.values()

#     @type.setter
#     def type(self, value):
#         if value == CIRCUIT_TYPE_UNKNOWN or value == CIRCUIT_TYPE_100ME or value == CIRCUIT_TYPE_1GE or value == CIRCUIT_TYPE_10GE or value == CIRCUIT_TYPE_40GE or value == CIRCUIT_TYPE_100GE or CIRCUIT_TYPE_ETHCHAN or CIRCUIT_TYPE_OC192 or CIRCUIT_TYPE_WIFI or CIRCUIT_TYPE_WIMAX:
#             self.__type = value
#         else:
#             raise ValueError("type must be one of CIRCUIT_TYPE_UNKNOWN, CIRCUIT_TYPE_100ME, CIRCUIT_TYPE_1GE, CIRCUIT_TYPE_10GE, CIRCUIT_TYPE_100GE, CIRCUIT_TYPE_ETHCHAN, CIRCUIT_TYPE_OC192, CIRCUIT_TYPE_WIFI, or CIRCUIT_TYPE_WIMAX")

#     @adminState.setter
#     def adminState(self, value):
#         if value == CIRCUIT_ADMIN_UNKNOWN or value == CIRCUIT_ADMIN_AVAILABLE or value == CIRCUIT_ADMIN_DECOMMISSIONED or value == CIRCUIT_ADMIN_MAINTENANCE or value == CIRCUIT_ADMIN_NORMAL or value == CIRCUIT_ADMIN_PLANNING or CIRCUIT_ADMIN_PROVISIONING:
#             self.__adminState = value
#         else:
#             raise ValueError("adminState must be one of CIRCUIT_ADMIN_UNKNOWN, CIRCUIT_ADMIN_AVAILABLE, CIRCUIT_ADMIN_DECOMMISSIONED, CIRCUIT_ADMIN_MAINTENANCE, CIRCUIT_ADMIN_NORMAL, CIRCUIT_ADMIN_PLANNING, or CIRCUIT_ADMIN_PROVISIONING")

#     @endpoints.setter
#     def endpoints(self, endpList):
#         if not isinstance(endpList, list):
#             raise TypeError("endpList must be a list")

#         for endp in endpList:
#             if not isinstance(endp, Interface):
#                 raise TypeError("all elements in endpList must be an Interface object")
#             else:
#                 self._putIntoList('circuits', endp, Interface)

#         self._endpoints = endpList

#     @network.setter
#     def network(self, value):
#         self._putIntoList('circuits', value, Network)
#         self._network = value


# # --------------------------------------------------------------------

# class Network(GMOCObject):
#     """A network that participates in GENI"""
#     __metaclass__ = GMOCMeta
#     __simpleProps__ = [ ['operator', Organization], ['admin', Organization] ]

#     def __init__(self, id, operator = None, admin = None):
#         super(Network, self).__init__(id)
#         self.operator = operator
#         self.admin = admin
#         self._circuits = []

#     def validate(self):
#         super(Network, self).validate()

#         if self.operator != None or self.admin != None:
#             if self.operator == None:
#                 raise ValueError("Network " + self.name + " must have a valid operator")
#             if self.admin == None:
#                 raise ValueError("Network " + self.name + " must have a valid administrator")

#             self.operator.validate()
#             self.admin.validate()

#     def toXML(self, doc, parent):
#         self.validate()

#         if parent == None:
#             parent = doc.documentElement

#         node = doc.createElement('network')
#         node.setAttribute('name', self.name)

#         if self.operator != None or self.admin != None:
#             node.setAttribute('operator_org_name', self.operator.id)
#             node.setAttribute('admin_org_name', self.admin.id)

#         for ckt in self.circuits:
#             ckt.toXML(doc, node)

#         parent.appendChild(node)

#         return node

#     @property
#     def circuits(self):
#         return self._circuits

#     @circuits.setter
#     def circuits(self, cktList):
#         self._setListProp('circuits', cktList, Circuit, '_network')


# # --------------------------------------------------------------------

# class VLAN(object):
#     """A VLAN in some part of the GENI network"""

#     def __init__(self, tag):
#         self.tag = tag

#     def validate(self):
#         if self.tag == None:
#             raise ValueError("VLAN must have a valid tag")

#     def toXML(self, doc, parent):
#         self.validate()

#         if parent == None:
#             parent = doc.documentElement

#         node = doc.createElement('vlan')
#         tnode = doc.createTextNode(str(self.tag))
#         node.appendChild(tnode)
#         parent.appendChild(node)

#         return node


# # --------------------------------------------------------------------

# class GMOCClient(object):
#     """A client that communicates with the GMOC"""
#     __metaclass__ = GMOCMeta

#     def __init__(self, serviceURL = None, username = None, password = None):
#         self.serviceURL = serviceURL
#         self.username = username
#         self.password = password
#         self.debugLevel = GMOC_DEBUG_OFF
#         self.__error = GMOC_SUCCESS
#         self.__errMsg = None
#         self.__resultStatus = 0

#     @property
#     def serviceURL(self):
#         return self._serviceURL

#     @property
#     def username(self):
#         return self._username

#     @property
#     def password(self):
#         return self._password

#     @property
#     def error(self):
#         return self.__error

#     @property
#     def errorMessage(self):
#         return self.__errMsg

#     @property
#     def resultStatus(self):
#         return self.__resultStatus

#     @serviceURL.setter
#     def serviceURL(self, value):
#         if value != None:
#             parsed = urlparse(value)
#             if parsed[0] == '' or parsed[1] == '':
#                 raise ValueError('serviceURL must be a valid URL')
#             self._serviceURL = value
#         else:
#             raise ValueError('serviceURL must be a valid URL')

#     @username.setter
#     def username(self, value):
#         if isinstance(value, str) and value != None:
#             self._username = value
#         else:
#             raise ValueError("username must be a valid string")

#     @password.setter
#     def password(self, value):
#         if isinstance(value, str) and value != None:
#             self._password = value
#         else:
#             raise ValueError("password must be a valid string")

#     def load(self, obj):
#         return GMOC_SUCCESS

#     def store(self, obj):
#         pop = None

#         # set up our XML document
#         impl = getDOMImplementation()
#         doc = impl.createDocument(None, 'gmoc_topology', None)
#         root = doc.documentElement

#         root.setAttribute('version', '4')
#         root.setAttribute('time', str(int(time.mktime(time.gmtime()))))

#         # try to find out top-level POP object
#         # if we don't have a POP, Aggregate, or SliceAuthority list, 
#         # we don't have enough info to proceed
#         if isinstance(obj, POP):
#             pop = obj
#         elif isinstance(obj, Aggregate):
#             pop = obj.pop
#         elif isinstance(obj, SliceAuthority):
#             pop = obj.pop
#         else:
#             raise TypeError("object passed to store() must be of type POP, Aggregate, or SliceAuthority")

#         # check our POP
#         pop.validate()

#         # add the location node
#         loc = pop.location
#         if loc != None:
#             loc.toXML(doc, root)

#         # add contact nodes
#         oper = pop.operator

#         if oper != None:
#             pUser = oper.primaryContact
#             eUser = oper.escalationContact
#         else:
#             pUser = None
#             eUser = None

#         for sa in pop.sliceAuthorities:
#             for user in sa.users:
#                 user.toXML(doc, root)                

#         if pUser != None:
#             pUser.toXML(doc, root)
#         if eUser != None:
#             eUser.toXML(doc, root)

#         # add the organization node
#         if oper != None:
#             oper.toXML(doc, root)

#         # add the POP node
#         pop.toXML(doc, root)

#         # add slice authority nodes
#         for sa in pop.sliceAuthorities:
#             sa.toXML(doc, root)

#         # add aggregate nodes
#         resources = {}
#         for agg in pop.aggregates:
#             agg.toXML(doc, root)
#             for res in agg.resources:
#                 resources[res.id] = res

#         # add resource nodes
#         for res in resources.values():
#             res.toXML(doc, root)

#         # add networks and circuits
# #        node = doc.createElement('net_topology')
# #        root.appendChild(node)

#         networks = {}
#         for agg in pop.aggregates:
#             for res in agg.resources:
#                 for intf in res.interfaces:
#                     for ckt in intf.circuits:
#                         net = ckt.network
#                         if net != None:
#                             networks[net.name] = net

#         if len(networks) > 0:
#             node = doc.createElement('net_topology')
#             root.appendChild(node)

#         for net in networks.values():
#             net.toXML(doc, node)

#         if self.debugLevel >= GMOC_DEBUG_VERBOSE:
#             print("Submitting:\n")
#             print(doc.toprettyxml())

#         # now that we have an XML document, submit it to the GMOC backend
#         wsEndpoint = self.serviceURL + '/xchange/webservice.pl'
#         wsData = dict(xml = doc.toxml())

#         h = Http()
#         h.disable_ssl_certificate_validation = True
#         h.add_credentials(self.username, self.password)

#         resp, content = h.request(wsEndpoint, 'POST', urlencode(wsData))
        
#         if self.debugLevel == GMOC_DEBUG_OMGWTFBBQ:
#             print(resp)

#         self.__resultStatus = int(resp.status)
#         if self.__resultStatus != 200:
#             if self.debugLevel >= GMOC_DEBUG_OMGWTFBBQ:
#                 print(resp)
#                 print(content)

#             self.__error = GMOC_ERROR_BAD_SCHEMA
#             self.__errMsg = content

#             return GMOC_ERROR_BAD_SCHEMA

#         return GMOC_SUCCESS

#     def storeMeasurements(self, reporter = None, obj = None):
#         typeinfos = {}
#         measurements = {}
        
#         # make sure we have a good reporter
#         if reporter == None:
#             raise ValueError("storeMeasurements() must have a valid reporter")

#         if obj == None:
#             raise ValueError("object passed to storeMeasurements() must be of type POP, Aggregate, or SliceAuthority")

#         # try to find out top-level POP object
#         # if we don't have a POP, Aggregate, or SliceAuthority list, 
#         # we don't have enough info to proceed
#         if isinstance(obj, POP):
#             pop = obj
#         elif isinstance(obj, Aggregate):
#             pop = obj.pop
#         elif isinstance(obj, SliceAuthority):
#             pop = obj.pop
#         else:
#             raise TypeError("object passed to storeMeasurement() must be of type POP, Aggregate, or SliceAuthority")

#         # set up our XML document
#         impl = getDOMImplementation()
#         doc = impl.createDocument(None, 'timeseries_data', None)
#         root = doc.documentElement

#         ts = datetime.datetime.now()

#         root.setAttribute('time', str(int(time.mktime(ts.timetuple()))))
#         root.setAttribute('version', '0.1')
#         root.setAttribute('originator', 'someone')

#         # collect a list of all measurements to submit
#         # Slices
#         for sa in pop.sliceAuthorities:
#             for slice in sa.slices:
#                 for m in slice.measurements:
#                     measurements[m.name] = m

#         # Aggregates, Slivers, Resources, Interfaces, and ResourceMappings
#         for agg in pop.aggregates:
#             for m in agg.measurements:
#                 measurements[m._name] = m
#             for sliver in agg.slivers:
#                 for sm in sliver.measurements:
#                     measurements[sm._name] = sm
#                 for resMap in sliver._resources:
#                     for rmm in resMap.measurements:
#                         measurements[rmm._name] = rmm
#             for res in agg.resources:
#                 for rm in res.measurements:
#                     measurements[rm._name] = rm
#                 for intf in res.interfaces:
#                     for im in intf.measurements:
#                         measurements[im._name] = im
#                 for resMap in res._slivers:
#                     for rmm in resMap.measurements:
#                         measurements[rmm._name] = rmm

#         # serialize typeinfos
#         for mName, mObj in measurements.iteritems():
#             typeinfos[mObj.type] = mObj

#         for m in typeinfos.values():
#             m.typeToXML(doc, root)

#         # serialize nodes
#         cnode = doc.createElement("node_info")
#         cnode.setAttribute("name", reporter.id)
#         lnode = doc.createElement("location")
#         tnode = doc.createTextNode(reporter.pop.id)
#         lnode.appendChild(tnode)
#         cnode.appendChild(lnode)

#         lnode = doc.createElement("tags")
#         cnode.appendChild(lnode)
#         root.appendChild(cnode)

#         # serialize datagroups
#         for mName, mObj in measurements.iteritems():
#             mObj.dataToXML(doc, root)

#         if self.debugLevel == GMOC_DEBUG_VERBOSE:
#             print "Submitting:\n"
#             print doc.toprettyxml()
        
#         # now that we have an XML document, submit it to the GMOC backend
#         wsEndpoint = self.serviceURL + '/measurement_drop/recv_api.pl'

#         # set up the multipart submission data
#         delim = ''.join(random.choice (string.letters) for ii in range (5))
#         contentType = "multipart/form-data; boundary=" + delim
#         wsHeaders = { "Content-Type": contentType }

#         wsBody = "--" + delim + "\r\n" + "Content-Disposition: form-data; name=\"file\"; filename=\"example1.xml\"\r\n"
#         wsBody += "Content-Type: application/xml\r\n\r\n"
#         wsBody += doc.toxml()
#         wsBody += "\r\n--" + delim + "--\r\n"

#         h = Http()
#         h.disable_ssl_certificate_validation = True
#         h.add_credentials(self.username, self.password)
#         h.debugLevel = 1

#         resp, content = h.request(wsEndpoint, 'POST', wsBody, wsHeaders)

#         self.__resultStatus = int(resp.status)
#         if self.__resultStatus != 200:
#             if self.debugLevel >= GMOC_DEBUG_OMGWTFBBQ:
#                 print(resp)
#                 print(content)

#             self.__error = GMOC_ERROR_BAD_SCHEMA
#             self.__errMsg = content

#             return GMOC_ERROR_BAD_SCHEMA

#         return GMOC_SUCCESS


#     def _load_aggregate(self, obj, h):
#         return obj


#     def _load_interface(self, obj, h):
#         return obj


#     def _load_pop(self, obj, h):
#         return obj


#     def _load_resource(self, obj, h):
#         intfs = []

#         if not isinstance(obj, Resource):
#             raise TypeError("Object is not a Resource")

#         wsEndpoint = self.serviceURL + "xchange/dd.cgi?method=get_resource&urn=" + quote(obj.id)
#         resp, content = h.request(wsEndpoint)

#         if self.debugLevel == GMOC_DEBUG_OMGWTFBBQ:
#             print(resp)

#         if resp.status == 200:
#             objData = json.loads(content)
#             obj._last_modified = datetime.datetime.fromtimestamp(int(objData["last_updated"]))
#             obj.type = str(objData["type"])
#             obj.description = str(objData["description"])
#             obj.operator = Organization(str(objData["organization"]))
#             obj.pop = POP(str(objData["pop"]))
            
#             # load interfaces
#             for urn in objData["interfaces"]:
#                 intf = self._load_interface(Interface(urn), h)
#                 intfs.append(intf)
            
#             # set interfaces (this will automatically set each interface's Resource)
#             obj.interfaces = intfs

#         return obj


#     def _load_sa(self, obj, h):
#         return obj


#     def _load_slice(self, obj, h):
#         return obj


#     def _load_sliver(self, obj, h):
#         return obj


#     def load(self, obj):
#         h = Http()
#         h.disable_ssl_certificate_validation = True
#         h.add_credentials(self.username, self.password)

#         if isinstance(obj, Aggregate):
#             self._load_aggregate(obj, h)
#         elif isinstance(obj, Interface):
#             self._load_interface(obj, h)
#         elif isinstance(obj, POP):
#             self._load_pop(obj, h)
#         elif isinstance(obj, Resource):
#             self._load_resource(obj, h)
#         elif isinstance(obj, SliceAuthority):
#             self._load_sa(obj, h)
#         elif isinstance(obj, Slice):
#             self._load_slice(obj, h)
#         elif isinstance(obj, Sliver):
#             self._load_sliver(obj, h)

#         return obj
