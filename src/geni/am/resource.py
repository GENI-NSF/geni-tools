import geni

class Resource(object):
    """A Resource has an id, a type, and a boolean indicating availability."""

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
