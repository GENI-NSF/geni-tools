#----------------------------------------------------------------------
# Copyright (c) 2013-2015 Raytheon BBN Technologies
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

# XML tag constants
RSPEC_TAG = 'rspec'
LINK_TAG = 'link'
NODE_TAG = 'node'
PORT_TAG = 'port'
STITCHING_TAG = 'stitching'
PATH_TAG = 'path'
SLIVER_TYPE_TAG = 'sliver_type'
EXPIRES_ATTRIBUTE = 'expires'
# Capabilities element names
CAPABILITIES_TAG = 'capabilities'
CAPABILITY_TAG = 'capability'
CONSUMER_VALUE = 'consumer'
PRODUCER_VALUE = 'producer'
VLANCONSUMER_VALUE = 'vlanconsumer'
VLANPRODUCER_VALUE = 'vlanproducer'

# see geni.util.rspec_schema for namespaces

# This should go away, its value is no longer used
LAST_UPDATE_TIME_TAG = "lastUpdateTime"

# Need the ExoSM URL, as ugly as that is
EXOSM_URL = "https://geni.renci.org:11443/orca/xmlrpc"

# Need to be able to ID Utah AMs for default sliver expirations (see below)
PGU_URN = "urn:publicid:IDN+emulab.net+authority+cm"
IGUDDC_URN = "urn:publicid:IDN+utahddc.geniracks.net+authority+cm"
USTITCH_URN = "urn:publicid:IDN+stitch.geniracks.net+authority+cm"
APT_URN = "urn:publicid:IDN+apt.emulab.net+authority+cm"
CL_URN_END = ".cloudlab.us+authority+cm"

# Default sliver expirations by AM type in days as of September, 2014
# Utah is Utah DDC and ProtoGENI Utah and Utah Stitch and ALL Cloudlab (including Clemson and Wisconsin). And Apt
# See ticket #577
DEF_SLIVER_EXPIRATION_UTAH = 5
DEF_SLIVER_EXPIRATION_IG = 90
DEF_SLIVER_EXPIRATION_GRAM = 7
DEF_SLIVER_EXPIRATION_EG = 14

# Singleton class for getting the default sliver expirations for some AM types
# Allows the config to have an omni_defaults section with values for these defaults to over-ride the values specified here
# Stitchhandler should call defs.DefaultSliverExpirations.getInstance(config, logger)
# Then uses of defs.DEF_...  in objects.py should instead do:
# defs_getter = defs.DefaultSliverExpirations.getInstance()
# defaultUtah = defs_getter.getUtah() ....
class DefaultSliverExpirations(object):
    instance = None

    def __init__(self, config, logger=None):
        self.config = config
        self.logger = logger
        self.utah = None
        self.ig = None
        self.gram = None
        self.eg = None
        self.otherUtahUrns = None

    @classmethod
    def getInstance(cls, config=None, logger=None):
        if DefaultSliverExpirations.instance:
            if config:
                DefaultSliverExpirations.instance.config = config
        else:
            DefaultSliverExpirations.instance = DefaultSliverExpirations(config, logger)
        return DefaultSliverExpirations.instance

    # Parse the new value, allowing for # to denote start of end-of-line comment
    def parseConfig(self, value):
        if not value:
            raise Exception("No value supplied")
        import re
        match = re.match(r'^\s*(\d+)\s*#*', value)
        if not match:
            raise Exception("Could not find integer in value")
        return int(match.group(1))

    # Is this AM one of the AMs subject to the Utah default sliver expiration?
    # Start with hard-codede defaults, but then accept additional Utah URNs from omni_defaults.utah_am_urns (CSV list)
    def isUtah(self, agg):
        if agg is None or not agg.isPG:
            return False
        if not agg.urn:
            return False
        if agg.urn in [PGU_URN, IGUDDC_URN, USTITCH_URN, APT_URN]:
            return True
        if agg.urn.endswith(CL_URN_END):
            return True

        if self.otherUtahUrns is None and self.config and self.config.has_key('omni_defaults') and self.config['omni_defaults'].has_key('utah_am_urns') and self.config['omni_defaults']['utah_am_urns']:
            try:
                urns = str(self.config['omni_defaults']['utah_am_urns']).strip().split(',')
                self.otherUtahUrns = []
                for urn in urns:
                    if not urn:
                        continue
                    u = urn.strip()
                    if u == '':
                        continue
                    self.otherUtahUrns.append(u)
                if self.logger is not None:
                    self.logger.debug("otherUrns IDing Utah AMs: %s", self.otherUtahUrns)
            except Exception, e:
                if self.logger is not None:
                    self.logger.debug("Failed to parse omni_defaults/utah_am_urns: %s", e)
        if self.otherUtahUrns is not None and agg.urn in self.otherUtahUrns:
            return True
        return False

    def getUtah(self):
        if self.utah:
            return self.utah
        self.utah = DEF_SLIVER_EXPIRATION_UTAH
        if self.config and self.config.has_key('omni_defaults') and self.config['omni_defaults'].has_key('def_sliver_expiration_utah') and self.config['omni_defaults']['def_sliver_expiration_utah']:
            try:
                self.utah = self.parseConfig(self.config['omni_defaults']['def_sliver_expiration_utah'])
                self.logger.debug("Resetting default Utah sliver expiration to %s", self.utah)
            except Exception, e:
                self.logger.info("Failed to parse def_sliver_expiration_utah from omni_defaults. Parsing '%s' gave: %s", self.config['omni_defaults']['def_sliver_expiration_utah'], e)
        return self.utah

    def getIG(self):
        if self.ig:
            return self.ig
        self.ig = DEF_SLIVER_EXPIRATION_IG
        if self.config and self.config.has_key('omni_defaults') and self.config['omni_defaults'].has_key('def_sliver_expiration_ig') and self.config['omni_defaults']['def_sliver_expiration_ig']:
            try:
                self.ig = self.parseConfig(self.config['omni_defaults']['def_sliver_expiration_ig'])
                self.logger.debug("Resetting default IG sliver expiration to %s", self.ig)
            except Exception, e:
                self.logger.info("Failed to parse def_sliver_expiration_ig from omni_defaults. Parsing '%s' gave: %s", self.config['omni_defaults']['def_sliver_expiration_ig'], e)
        return self.ig

    def getGram(self):
        if self.gram:
            return self.gram
        self.gram = DEF_SLIVER_EXPIRATION_GRAM
        if self.config and self.config.has_key('omni_defaults') and self.config['omni_defaults'].has_key('def_sliver_expiration_gram') and self.config['omni_defaults']['def_sliver_expiration_gram']:
            try:
                self.gram = self.parseConfig(self.config['omni_defaults']['def_sliver_expiration_gram'])
                self.logger.debug("Resetting default GRAM sliver expiration to %s", self.gram)
            except Exception, e:
                self.logger.info("Failed to parse def_sliver_expiration_gram from omni_defaults. Parsing '%s' gave: %s", self.config['omni_defaults']['def_sliver_expiration_gram'], e)
        return self.gram

    def getEG(self):
        if self.eg:
            return self.eg
        self.eg = DEF_SLIVER_EXPIRATION_EG
        if self.config and self.config.has_key('omni_defaults') and self.config['omni_defaults'].has_key('def_sliver_expiration_eg') and self.config['omni_defaults']['def_sliver_expiration_eg']:
            try:
                self.eg = self.parseConfig(self.config['omni_defaults']['def_sliver_expiration_eg'])
                self.logger.debug("Resetting default EG sliver expiration to %s", self.eg)
            except Exception, e:
                self.logger.info("Failed to parse def_sliver_expiration_eg from omni_defaults. Parsing '%s' gave: %s", self.config['omni_defaults']['def_sliver_expiration_eg'], e)
        return self.eg


# schema paths for switching between v1 and v2
STITCH_V1_BASE = "hpn.east.isi.edu/rspec/ext/stitch/0.1"
STITCH_V2_BASE = "geni.net/resources/rspec/ext/stitch/2"
STITCH_V1_SCHEMA = "http://hpn.east.isi.edu/rspec/ext/stitch/0.1/ http://hpn.east.isi.edu/rspec/ext/stitch/0.1/stitch-schema.xsd"
STITCH_V1_NS = "http://hpn.east.isi.edu/rspec/ext/stitch/0.1"
STITCH_V2_SCHEMA = "http://www.geni.net/resources/rspec/ext/stitch/2/ http://www.geni.net/resources/rspec/ext/stitch/2/stitch-schema.xsd"
STITCH_V2_NS = "http://www.geni.net/resources/rspec/ext/stitch/2"

# Minutes since last VLAN availability check before bothing to check again
CHECK_AVAIL_INTERVAL_MINS=60
