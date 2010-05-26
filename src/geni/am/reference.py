#----------------------------------------------------------------------
# Copyright (c) 2010 Raytheon BBN Technologies
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

import base64
import datetime
import logging
import xml.dom.minidom as minidom
import xmlrpclib
import zlib
import dateutil.parser
import geni
import sfa.trust.credential as cred
import sfa.trust.gid as gid

class CredentialVerifier(object):
    
    def __init__(self, root_cert_file):
        self.root_cert_files = [root_cert_file]

    def verify_from_strings(self, gid_string, cred_strings, target_urn,
                            privileges):
        def make_cred(cred_string):
            return cred.Credential(string=cred_string)
        return self.verify(gid.GID(string=gid_string),
                           map(make_cred, cred_strings),
                           target_urn,
                           privileges)
        
    def verify_source(self, source_gid, credential):
        source_urn = source_gid.get_urn()
        cred_source_urn = credential.get_gid_caller().get_urn()
        logging.debug('Verifying source %r against credential %r source %r',
                      source_urn, credential, cred_source_urn)
        result = (cred_source_urn == source_urn)
        if result:
            logging.debug('Source URNs match')
        else:
            logging.debug('Source URNs do not match')
        return result
    
    def verify_target(self, target_urn, credential):
        if not target_urn:
            logging.debug('No target specified, considering it a match.')
            return True
        else:
            cred_target_urn = credential.get_gid_object().get_urn()
            logging.debug('Verifying target %r against credential target %r',
                          target_urn, cred_target_urn)
            result = target_urn == cred_target_urn
            if result:
                logging.debug('Target URNs match.')
            else:
                logging.debug('Target URNs do not match.')
            return result

    def verify_privileges(self, privileges, credential):
        result = True
        privs = credential.get_privileges()
        for priv in privileges:
            if not privs.can_perform(priv):
                logging.debug('Privilege %s not found', priv)
                result = False
        return result

    def verify(self, gid, credentials, target_urn, privileges):
        logging.debug('Verifying privileges')
        result = list()
        for cred in credentials:
            if (self.verify_source(gid, cred) and
                self.verify_target(target_urn, cred) and
                self.verify_privileges(privileges, cred) and
                cred.verify(self.root_cert_files)):
                result.append(cred)
        if result:
            return result
        else:
            # We did not find any credential with sufficient privileges
            # Raise an exception.
            fault_code = 'Insufficient privileges'
            fault_string = 'No credential was found with appropriate privileges.'
            raise xmlrpclib.Fault(fault_code, fault_string)

class Resource(object):

    def __init__(self, id, type):
        self._id = id
        self._type = type
        self.available = True

    def toxml(self):
        template = ('<resource><type>%s</type><id>%s</id>'
                    + '<available>%r</available></resource>')
        return template % (self._type, self._id, self.available)

    def urn(self):
        publicid = 'IDN geni.net//resource//%s_%s' % (self._type, str(self._id))
        return geni.publicid_to_urn(publicid)

    def __eq__(self, other):
        return self._id == other._id

    def __neq__(self, other):
        return self._id != other._id

    @classmethod
    def fromdom(cls, element):
        """Create a Resource instance from a DOM representation."""
        type = element.getElementsByTagName('type')[0].firstChild.data
        id = int(element.getElementsByTagName('id')[0].firstChild.data)
        return Resource(id, type)

class Sliver(object):

    def __init__(self, urn, expiration=datetime.datetime.now()):
        self.urn = urn
        self.resources = list()
        self.expiration = expiration

class ReferenceAggregateManager(object):
    
    def __init__(self, root_cert):
        self._slivers = dict()
        self._resources = [Resource(x, 'Nothing') for x in range(10)]
        self._cred_verifier = CredentialVerifier(root_cert)
        self.max_lease = datetime.timedelta(days=365)

    def GetVersion(self):
        return dict(geni_api=1)

    def ListResources(self, credentials, options):
        print 'ListResources(%r)' % (options)
        privileges = ()
        self._cred_verifier.verify_from_strings(self._server.pem_cert,
                                                credentials,
                                                None,
                                                privileges)
        if not options:
            options = dict()
        if 'geni_slice_urn' in options:
            slice_urn = options['geni_slice_urn']
            if slice_urn in self._slivers:
                sliver = self._slivers[slice_urn]
                result = ('<rspec>'
                          + ''.join([x.toxml() for x in sliver.resources])
                          + '</rspec>')
            else:
                # return an empty rspec
                result = '<rspec/>'
        elif 'geni_available' in options and options['geni_available']:
            result = ('<rspec>' + ''.join([x.toxml() for x in self._resources])
                      + '</rspec>')
        else:
            all_resources = list()
            all_resources.extend(self._resources)
            for sliver in self._slivers:
                all_resources.extend(self._slivers[sliver].resources)
            result = ('<rspec>' + ''.join([x.toxml() for x in all_resources])
                      + '</rspec>')
        # Optionally compress the result
        if 'geni_compressed' in options and options['geni_compressed']:
            result = base64.b64encode(zlib.compress(result))
        return result

    def CreateSliver(self, slice_urn, credentials, rspec, users):
        print 'CreateSliver(%r)' % (slice_urn)
        privileges = ('createsliver',)
        creds = self._cred_verifier.verify_from_strings(self._server.pem_cert,
                                                        credentials,
                                                        slice_urn,
                                                        privileges)
        if slice_urn in self._slivers:
            raise Exception('Sliver already exists.')
        rspec_dom = minidom.parseString(rspec)
        resources = list()
        for elem in rspec_dom.documentElement.childNodes:
            resource = Resource.fromdom(elem)
            if resource not in self._resources:
                raise Exception('Resource not available')
            resources.append(resource)
        # determine max expiration time from credentials
        expiration = datetime.datetime.now() + self.max_lease
        for cred in creds:
            if cred.expiration < expiration:
                expiration = cred.expiration
        sliver = Sliver(slice_urn, expiration)
        # remove resources from available list
        for resource in resources:
            sliver.resources.append(resource)
            self._resources.remove(resource)
            resource.available = False
        self._slivers[slice_urn] = sliver
        return ('<rspec>' + ''.join([x.toxml() for x in sliver.resources])
                + '</rspec>')

    def DeleteSliver(self, slice_urn, credentials):
        print 'DeleteSliver(%r)' % (slice_urn)
        privileges = ('deleteslice',)
        self._cred_verifier.verify_from_strings(self._server.pem_cert,
                                                credentials,
                                                slice_urn,
                                                privileges)
        if slice_urn in self._slivers:
            sliver = self._slivers[slice_urn]
            # return the resources to the pool
            self._resources.extend(sliver.resources)
            for resource in sliver.resources:
                resource.available = True
            del self._slivers[slice_urn]
            return True
        else:
            return False

    def SliverStatus(self, slice_urn, credentials):
        # Loop over the resources in a sliver gathering status.
        print 'SliverStatus(%r)' % (slice_urn)
        privileges = ('getsliceresources',)
        self._cred_verifier.verify_from_strings(self._server.pem_cert,
                                                credentials,
                                                slice_urn,
                                                privileges)
        if slice_urn in self._slivers:
            sliver = self._slivers[slice_urn]
            res_status = list()
            for res in sliver.resources:
                res_status.append(dict(geni_urn=res.urn(),
                                       geni_status='ready',
                                       geni_error=''))
            return dict(geni_urn=sliver.urn,
                        # TODO: need to calculate sliver status
                        geni_status='ready',
                        geni_resources=res_status)
        else:
            self.no_such_slice(slice_urn)

    def RenewSliver(self, slice_urn, credentials, expiration_time):
        print 'RenewSliver(%r, %r)' % (slice_urn, expiration_time)
        privileges = ('renewsliver',)
        creds = self._cred_verifier.verify_from_strings(self._server.pem_cert,
                                                        credentials,
                                                        slice_urn,
                                                        privileges)
        if slice_urn in self._slivers:
            sliver = self._slivers.get(slice_urn)
            requested = dateutil.parser.parse(str(expiration_time))
            for cred in creds:
                if cred.expiration < requested:
                    return False
            sliver.expiration = requested
            return True
        else:
            self.no_such_slice(slice_urn)

    def Shutdown(self, slice_urn, credentials):
        print 'Shutdown(%r)' % (slice_urn)
        # No permission for Renew currently exists.
        if slice_urn in self._slivers:
            return False
        else:
            self.no_such_slice(slice_urn)

    def no_such_slice(self, slice_urn):
        "Raise a no such slice exception."
        fault_code = 'No such slice.'
        fault_string = 'The slice named by %s does not exist' % (slice_urn)
        raise xmlrpclib.Fault(fault_code, fault_string)
