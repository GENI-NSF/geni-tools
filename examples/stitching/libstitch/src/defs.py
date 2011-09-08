#!/usr/bin/python
#----------------------------------------------------------------------
# Copyright (c) 2011 Raytheon BBN Technologies
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
'''Define various constants, like XML tag names.'''

##RSpec XML Tag names
AGGR_TAG="aggregate"
DESC_TAG="description"
LIFE_TAG="lifetime"
USER_TAG="user"
NETW_TAG="network"
STCHRSRC_TAG="stitchingResource"
STCH_TAG="stitching"
HOP_TAG="hop"
LINK_TAG="link"
PATH_TAG="path"
ADDR_TAG="address"
SERVS_TAG="services"
LOGIN_TAG="login"
URL_ID="url"
RMOTLINK_TAG="remoteLinkId"
INTRFACE_TAG="interface"
IP_TAG="ip"
HOSTNAME_TAG="hostname"
NODE_TAG="node"
PORT_TAG="port"
COMPRSRC_TAG="computeResource"
COMPNODE_TAG="computeNode"
COMPSLIC_TAG="computeSlice"
PLABNODE_TAG="planetlabNodeSliver"
NETIFACE_TAG="networkInterface"
NETIFACEURN_TAG="networkInterfaceUrn"
EXTRSRCID_TAG="externalResourceId"
ATACHLINKURN_TAG="attachedLinkUrn"
IPADDR_TAG="ipAddress"
DTYP_TAG="deviceType"
CAPA_TAG="capacity"
VLANRANG_TAG="vlanRange"
VLANTRAN_TAG="vlanTranslation"
VLANRANGAVAI_TAG="vlanRangeAvailability"
PEERNETIFACE_TAG="peerNetworkInterface"
ID_TAG="id"
RSPEC_TAG="rspec"
LIFETIME_TAG="lifetime"
STRT_TAG="start"
END_TAG="end"
SWTCCAPADESC_TAG="switchingCapabilityDescriptor"
SWTCCAPADESC_TAG_OLD="SwitchingCapabilityDescriptors" #before noon 7/15
SWTCCAPASPEC_TAG="switchingCapabilitySpecificInfo"
SWTCCAPASPEC_L2SC_TAG="switchingCapabilitySpecificInfo_L2sc" # PG uses this

##Shared Regexes
rspecHintRegex = "<!-- Resources at AM:\s+URN: (\S+)\s+URL: (\S+)\s+ -->"
maxURNSliceNameRegex = "(^urn:.*:rspec=)(.+?)($|:.+$)"
maxNodeNameRegex = "(^urn:.*:domain=)(.+?)(:node=)(.+?)($|:.+$)"
ipAddrExcludeSub = "(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\/?.*"
template_source_regex = "^(.*)(%SOURCE%)(.*)$"

##Various global Constants
tmpfile_strlen = 10
tmpfile_extension = "rspec"
aggrPollIntervalSec = 5
pollMaxAttempts = 10
graph_filename = "graph.png"
defaultExpDuration = 36000
template_login_script = "template_login.sh"
template_setup_script = "template_setup.sh"
templates_dir = "templates"
cache_dir = "cache"

##Variables likely to be removed
advert_rspec="protogeni-advertise.xml"

term_colors = [
    '\033[91m',
    '\033[92m',
    '\033[93m',
    '\033[94m',
    '\033[95m'
]
term_end = '\033[0m'

verbose_loglevel = 5
logger_name = 'libstitch'
