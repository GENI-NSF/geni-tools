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

import geni

class Resource(object):
    """A Resource has an id, a type, and a boolean indicating availability."""

    STATUS_ALLOCATED = 'allocated'
    STATUS_PROVISIONED = 'provisioned'
    STATUS_CONFIGURING = 'configuring'
    STATUS_READY = 'ready'
    STATUS_FAILED = 'failed'
    STATUS_UNKNOWN = 'unknown'
    STATUS_SHUTDOWN = 'shutdown'

    def __init__(self, rid, rtype):
        self.id = rid
        self.type = rtype
        self.available = True
        self.status = Resource.STATUS_UNKNOWN

    def urn(self):
        # User in SliverStatus
        # NAMESPACE has no business here. The URN should be at an upper level, not here.
        RESOURCE_NAMESPACE = 'geni//gpo//gcf'
        publicid = 'IDN %s//resource//%s_%s' % (RESOURCE_NAMESPACE, self._type, str(self._id))
        return geni.publicid_to_urn(publicid)

    def toxml(self):
        template = ('<resource><urn>%s</urn><type>%s</type><id>%s</id>'
                    + '<available>%r</available></resource>')
        return template % (self.urn(), self._type, self._id, self.available)

    def __eq__(self, other):
        return self._id == other._id

    def __neq__(self, other):
        return self._id != other._id

    @classmethod
    def fromdom(cls, element):
        """Create a Resource instance from a DOM representation."""
        rtype = element.getElementsByTagName('type')[0].firstChild.data
        rid = int(element.getElementsByTagName('id')[0].firstChild.data)
        return Resource(rid, rtype)
