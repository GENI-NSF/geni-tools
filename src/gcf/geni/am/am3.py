#----------------------------------------------------------------------
# Copyright (c) 2012-2015 Raytheon BBN Technologies
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
"""
The GPO Reference Aggregate Manager v3, showing how to implement
the GENI AM API version 3. This AggregateManager has only fake resources.
Invoked from gcf-am.py
The GENI AM API is defined in the AggregateManager class.
"""

# Note: This AM uses SFA authorization to check that the caller
# has appropriate credentials to make the call. If this AM is used in 
# conjunction with the policy-based authorization capability (in gcf.geni.auth)
# then this code needs to only extract expiration times from the credentials
# which can be done using the gcf.sfa.credential module

from __future__ import absolute_import

import base64
import collections
import datetime
import dateutil.parser
import logging
import os
import traceback
import uuid
import xml.dom.minidom as minidom
import xmlrpclib
import zlib

from .aggregate import Aggregate
from .fakevm import FakeVM
from ... import geni
from ..util.tz_util import tzd
from ..util.urn_util import publicid_to_urn
from ..util import urn_util as urn
from ..SecureXMLRPCServer import SecureXMLRPCServer

from ...sfa.trust.credential import Credential
from ...sfa.trust.abac_credential import ABACCredential
from ...gcf_version import GCF_VERSION

from ...omnilib.util import credparsing as credutils

from ..auth.base_authorizer import *
from .am_method_context import AMMethodContext
from .api_error_exception import ApiErrorException

# See sfa/trust/rights.py
# These are names of operations
# from the rights.py privilege_table
# Credentials may list privileges that
# map to these operations, giving the caller permission
# to perform the functions
RENEWSLIVERPRIV = 'renewsliver'

# Map the Allocate, Provision and POA calls to the CreateSliver privilege.
ALLOCATE_PRIV = 'createsliver'
PROVISION_PRIV = 'createsliver'
PERFORM_ACTION_PRIV = 'createsliver'
DELETESLIVERPRIV = 'deleteslice'
SLIVERSTATUSPRIV = 'getsliceresources'
SHUTDOWNSLIVERPRIV = 'shutdown'

# Publicid format resource namespace. EG Resource URNs
# will be <namespace>:resource:<resourcetype>_<resourceid>
# This is something like the name of your AM
# See gen-certs.CERT_AUTHORITY
RESOURCE_NAMESPACE = 'geni//gpo//gcf'

# MAX LEASE is 7 days (arbitrarily)
REFAM_MAXLEASE_MINUTES = 7 * 24 * 60

# Expiration on Allocated resources is 10 minutes.
ALLOCATE_EXPIRATION_SECONDS = 10 * 60

# GENI Allocation States
STATE_GENI_UNALLOCATED = 'geni_unallocated'
STATE_GENI_ALLOCATED = 'geni_allocated'
STATE_GENI_PROVISIONED = 'geni_provisioned'

# GENI Operational States
# These are in effect when the allocation state is PROVISIONED.
OPSTATE_GENI_PENDING_ALLOCATION = 'geni_pending_allocation'
OPSTATE_GENI_NOT_READY = 'geni_notready'
OPSTATE_GENI_CONFIGURING = 'geni_configuring'
OPSTATE_GENI_STOPPING = 'geni_stopping'
OPSTATE_GENI_READY = 'geni_ready'
OPSTATE_GENI_READY_BUSY = 'geni_ready_busy'
OPSTATE_GENI_FAILED = 'geni_failed'


def isGeniCred(cred):
    """Filter (for use with filter()) to yield all 'geni_sfa' credentials
    regardless over version.
    """
    if not isinstance(cred, dict):
        msg = "Bad Arguments: Received credential of unknown type %r"
        msg = msg % (type(cred))
        raise ApiErrorException(AM_API.BAD_ARGS, msg)
    return ('geni_type' in cred
            and str(cred['geni_type']).lower() in [Credential.SFA_CREDENTIAL_TYPE, 
                                                   ABACCredential.ABAC_CREDENTIAL_TYPE])

class AM_API(object):
    BAD_ARGS = 1
    FORBIDDEN = 3
    BAD_VERSION = 4
    TOO_BIG = 6
    REFUSED = 7
    UNAVAILABLE = 11
    SEARCH_FAILED = 12
    UNSUPPORTED = 13
    ALREADY_EXISTS = 17
    # --- Non-standard errors below here. ---
    OUT_OF_RANGE = 19

class Sliver(object):
    """A sliver is a single resource assigned to a single slice
    at an aggregate.
    """

    def __init__(self, parent_slice, resource):
        self._id = str(uuid.uuid4())
        self._resource = resource
        self._slice = parent_slice
        self._expiration = None
        self._start_time = None
        self._end_time = None
        self._allocation_state = STATE_GENI_UNALLOCATED
        self._operational_state = OPSTATE_GENI_PENDING_ALLOCATION
        self._urn = None
        global RESOURCE_NAMESPACE
        self._base = RESOURCE_NAMESPACE
        self._setUrnFromParent(resource.urn(self._base))
        self._shutdown = False

    def resource(self):
        return self._resource

    def slice(self):
        return self._slice

    def setAllocationState(self, new_state):
        # FIXME: Do some error checking on the state transition
        self._allocation_state = new_state

    def allocationState(self):
        return self._allocation_state

    def setOperationalState(self, new_state):
        # FIXME: Do some error checking on the state transition
        self._operational_state = new_state

    def operationalState(self):
        return self._operational_state

    def setExpiration(self, new_expiration):
        self._expiration = new_expiration

    def expiration(self):
        return self._expiration

    def setStartTime(self, new_start_time):
        self._start_time = new_start_time

    def startTime(self):
        return self._start_time

    def setEndTime(self, new_end_time):
        self._end_time = new_end_time

    def endTime(self):
        return self._end_time

    def _setUrnFromParent(self, parent_urn):
        authority = urn.URN(urn=parent_urn).getAuthority()
        self._urn = str(urn.URN(authority=authority,
                                type='sliver',
                                name=self._id))

    def urn(self):
        if self._urn is None:
            self._setUrnFromParent(self._resource.urn(self._base))
        return self._urn

    def delete(self):
        if self.allocationState() == STATE_GENI_PROVISIONED:
            self._resource.deprovision()
        self.resource().reset()
        self._resource = None
        self.setAllocationState(STATE_GENI_UNALLOCATED)
        self.setOperationalState(OPSTATE_GENI_PENDING_ALLOCATION)

    def shutdown(self):
        self._shutdown = True

    def isShutdown(self):
        return self._shutdown

    def status(self, geni_error=''):
        """Returns a status dict for this sliver. Used in numerous
        return values for AM API v3 calls.
        """
        expire_with_tz = self.expiration().replace(tzinfo=dateutil.tz.tzutc())
        expire_string = expire_with_tz.isoformat()
        start_with_tz = self.startTime().replace(tzinfo=dateutil.tz.tzutc())
        start_string = start_with_tz.isoformat()
        end_with_tz = self.endTime().replace(tzinfo=dateutil.tz.tzutc())
        end_string = end_with_tz.isoformat()
        return dict(geni_sliver_urn=self.urn(),
                    geni_expires=expire_string,
                    geni_start_time=start_string,
                    geni_end_time=end_string,
                    geni_allocation_status=self.allocationState(),
                    geni_operational_status=self.operationalState(),
                    geni_error=geni_error)


class Slice(object):
    """A slice has a URN, a list of resources, and an expiration time in UTC."""

    def __init__(self, urn):
        self.id = str(uuid.uuid4())
        self.urn = urn
        self._slivers = list()
        self._resources = dict()
        self._shutdown = False

    def getURN(self): return self.urn

    def add_resource(self, resource):
        sliver = Sliver(self, resource)
        self._slivers.append(sliver)
        return sliver

    def delete_sliver(self, sliver):
        sliver.delete()
        self._slivers.remove(sliver)

    def slivers(self):
        return self._slivers

    def resources(self):
        return [sliver.resource() for sliver in self._slivers]

    def shutdown(self):
        for sliver in self.slivers():
            sliver.shutdown()
        self._shutdown = True

    def isShutdown(self):
        return self._shutdown


class ReferenceAggregateManager(object):
    '''A reference Aggregate Manager that manages fake resources.'''

    # root_cert is a single cert or dir of multiple certs
    # that are trusted to sign credentials
    def __init__(self, root_cert, urn_authority, url, **kwargs):
        self._urn_authority = urn_authority
        self._url = url
        self._cred_verifier = geni.CredentialVerifier(root_cert)
        self._api_version = 3
        self._am_type = "gcf"
        self._slices = dict()
        self._agg = Aggregate()
        self._agg.add_resources([FakeVM(self._agg) for _ in range(20)])
        self._my_urn = publicid_to_urn("%s %s %s" % (self._urn_authority, 'authority', 'am'))
        self.max_lease = datetime.timedelta(minutes=REFAM_MAXLEASE_MINUTES)
        self.max_alloc = datetime.timedelta(seconds=ALLOCATE_EXPIRATION_SECONDS)
        self.logger = logging.getLogger('gcf.am3')
        self.logger.info("Running %s AM v%d code version %s", self._am_type, self._api_version, GCF_VERSION)

    def GetVersion(self, options):
        '''Specify version information about this AM. That could
        include API version information, RSpec format and version
        information, etc. Return a dict.'''
        self.logger.info("Called GetVersion")
        self.expire_slivers()
        reqver = [dict(type="GENI",
                       version="3",
                       schema="http://www.geni.net/resources/rspec/3/request.xsd",
                       namespace="http://www.geni.net/resources/rspec/3",
                       extensions=[])]
        adver = [dict(type="GENI",
                      version="3",
                      schema="http://www.geni.net/resources/rspec/3/ad.xsd",
                      namespace="http://www.geni.net/resources/rspec/3",
                      extensions=[])]
        api_versions = dict()
        api_versions[str(self._api_version)] = self._url
        credential_types = [dict(geni_type = Credential.SFA_CREDENTIAL_TYPE,
                                 geni_version = "3")]
        versions = dict(geni_api=self._api_version,
                        geni_api_versions=api_versions,
                        geni_am_type='gcf',
                        geni_am_code=GCF_VERSION,
                        geni_request_rspec_versions=reqver,
                        geni_ad_rspec_versions=adver,
                        geni_credential_types=credential_types)
        result = self.successResult(versions)
        # Add the top-level 'geni_api' per the AM API spec.
        result['geni_api'] = versions['geni_api']
        return result

    # The list of credentials are options - some single cred
    # must give the caller required permissions.
    # The semantics of the API are unclear on this point, so
    # this is just the current implementation
    def ListResources(self, credentials, options):
        '''Return an RSpec of resources managed at this AM.
        If geni_available is specified in the options,
        then only report available resources. If geni_compressed
        option is specified, then compress the result.'''
        self.logger.info('ListResources(%r)' % (options))
        self.expire_slivers()

        # Note this list of privileges is really the name of an operation
        # from the privilege_table in sfa/trust/rights.py
        # Credentials will specify a list of privileges, each of which
        # confers the right to perform a list of operations.
        # EG the 'info' privilege in a credential allows the operations
        # listslices, listnodes, policy

        # could require list or listnodes?
        privileges = ()
        self.getVerifiedCredentials(None,
                                    credentials, 
                                    options,
                                    privileges)

        # If we get here, the credentials give the caller
        # all needed privileges to act on the given target.

        if 'geni_rspec_version' not in options:
            # This is a required option, so error out with bad arguments.
            self.logger.error('No geni_rspec_version supplied to ListResources.')
            return self.errorResult(AM_API.BAD_ARGS,
                                    'Bad Arguments: option geni_rspec_version was not supplied.')
        if 'type' not in options['geni_rspec_version']:
            self.logger.error('ListResources: geni_rspec_version does not contain a type field.')
            return self.errorResult(AM_API.BAD_ARGS,
                                    'Bad Arguments: option geni_rspec_version does not have a type field.')
        if 'version' not in options['geni_rspec_version']:
            self.logger.error('ListResources: geni_rspec_version does not contain a version field.')
            return self.errorResult(AM_API.BAD_ARGS,
                                    'Bad Arguments: option geni_rspec_version does not have a version field.')

        # Look to see what RSpec version the client requested
        # Error-check that the input value is supported.
        rspec_type = options['geni_rspec_version']['type']
        if isinstance(rspec_type, str):
            rspec_type = rspec_type.lower().strip()
        rspec_version = options['geni_rspec_version']['version']
        if rspec_type != 'geni':
            self.logger.error('ListResources: Unknown RSpec type %s requested', rspec_type)
            return self.errorResult(AM_API.BAD_VERSION,
                                    'Bad Version: requested RSpec type %s is not a valid option.' % (rspec_type))
        if rspec_version != '3':
            self.logger.error('ListResources: Unknown RSpec version %s requested', rspec_version)
            return self.errorResult(AM_API.BAD_VERSION,
                                    'Bad Version: requested RSpec version %s is not a valid option.' % (rspec_version))
        self.logger.info("ListResources requested RSpec %s (%s)", rspec_type, rspec_version)

        if 'geni_slice_urn' in options:
            self.logger.error('ListResources: geni_slice_urn is no longer a supported option.')
            msg = 'Bad Arguments:'
            msg += 'option geni_slice_urn is no longer a supported option.'
            msg += ' Use "Describe" instead.'
            return self.errorResult(AM_API.BAD_ARGS, msg)

#        if 'geni_slice_urn' in options:
#            slice_urn = options['geni_slice_urn']
#            if slice_urn in self._slices:
#                result = self.manifest_rspec(slice_urn)
#            else:
#                # return an empty rspec
#                return self._no_such_slice(slice_urn)
#        else:
        all_resources = self._agg.catalog(None)
        available = 'geni_available' in options and options['geni_available']
        resource_xml = ""
        for r in all_resources:
            if available and not r.available:
                continue
            resource_xml = resource_xml + self.advert_resource(r)
        result = self.advert_header() + resource_xml + self.advert_footer()
        # Optionally compress the result
        if 'geni_compressed' in options and options['geni_compressed']:
            try:
                result = base64.b64encode(zlib.compress(result))
            except Exception, exc:
                self.logger.error("Error compressing and encoding resource list: %s", traceback.format_exc())
                raise Exception("Server error compressing resource list", exc)
        return self.successResult(result)

    # The list of credentials are options - some single cred
    # must give the caller required permissions.
    # The semantics of the API are unclear on this point, so
    # this is just the current implementation
    def Allocate(self, slice_urn, credentials, rspec, options):
        """Allocate slivers to the given slice according to the given RSpec.
        Return an RSpec of the actually allocated resources.
        """
        self.logger.info('Allocate(%r)' % (slice_urn))
        self.expire_slivers()
        # Note this list of privileges is really the name of an operation
        # from the privilege_table in sfa/trust/rights.py
        # Credentials will specify a list of privileges, each of which
        # confers the right to perform a list of operations.
        # EG the 'info' privilege in a credential allows the operations
        # listslices, listnodes, policy
        privileges = (ALLOCATE_PRIV,)

        creds=self.getVerifiedCredentials(slice_urn, credentials, options, privileges)
        # If we get here, the credentials give the caller
        # all needed privileges to act on the given target.

        # Grab the user_urn
        user_urn = gid.GID(string=options['geni_true_caller_cert']).get_urn()


        rspec_dom = None
        try:
            rspec_dom = minidom.parseString(rspec)
        except Exception, exc:
            self.logger.error("Cannot create sliver %s. Exception parsing rspec: %s" % (slice_urn, exc))
            return self.errorResult(AM_API.BAD_ARGS,
                                    'Bad Args: RSpec is unparseable')

        # Look at the version of the input request RSpec
        # Make sure it is supported
        # Then make sure that you return an RSpec in the same format
        # EG if both V1 and V2 are supported, and the user gives V2 request,
        # then you must return a V2 manifest and not V1

        available = self.resources(available=True)

        # Note: This only handles unbound nodes. Any attempt by the client
        # to specify a node is ignored.
        unbound = list()
        for elem in rspec_dom.documentElement.getElementsByTagName('node'):
            unbound.append(elem)
        if len(unbound) > len(available):
            # There aren't enough resources
            self.logger.error('Too big: requesting %d resources but I only have %d',
                              len(unbound), len(available))
            return self.errorResult(AM_API.TOO_BIG,
                                    'Too Big: insufficient resources to fulfill request')

        resources = list()
        for elem in unbound:
            client_id = elem.getAttribute('client_id')
            resource = available.pop(0)
            resource.external_id = client_id
            resource.available = False
            resources.append(resource)

        # determine max expiration time from credentials
        # do not create a sliver that will outlive the slice!
        expiration = self.min_expire(creds, self.max_alloc,
                                     ('geni_end_time' in options
                                      and options['geni_end_time']))

        # determine end time as min of the slice 
        # and the requested time (if any)
        end_time = self.min_expire(creds, 
                                   requested=('geni_end_time' in options 
                                              and options['geni_end_time']))

        # determine the start time as bounded by slice expiration and 'now'
        now = datetime.datetime.utcnow()
        start_time = now
        if 'geni_start_time' in options:
            # Need to parse this into datetime
            start_time_raw = options['geni_start_time']
            start_time = self._naiveUTC(dateutil.parser.parse(start_time_raw))
        start_time = max(now, start_time)
        if (start_time > self.min_expire(creds)):
            return self.errorResult(AM_API.BAD_ARGS, 
                                    "Can't request start time on sliver after slice expiration")

        # determine max expiration time from credentials
        # do not create a sliver that will outlive the slice!
        expiration = self.min_expire(creds, self.max_alloc,
                                     ('geni_end_time' in options
                                      and options['geni_end_time']))

        # If we're allocating something for future, give a window
        # from start time in which to reserve
        if start_time > now:
            expiration = min(start_time + self.max_alloc, 
                             self.min_expire(creds))

        # if slice exists, check accept only if no  existing sliver overlaps
        # with requested start/end time. If slice doesn't exist, create it
        if slice_urn in self._slices:
            newslice = self._slices[slice_urn]
            # Check if any current slivers overlap with requested start/end
            one_slice_overlaps = False
            for sliver in newslice.slivers():
                if sliver.startTime() < end_time and \
                        sliver.endTime() > start_time:
                    one_slice_overlaps = True
                    break

            if one_slice_overlaps:
                template = "Slice %s already has slivers at requested time"
                self.logger.error(template % (slice_urn))
                return self.errorResult(AM_API.ALREADY_EXISTS,
                                        template % (slice_urn))
        else:
            newslice = Slice(slice_urn)

        for resource in resources:
            sliver = newslice.add_resource(resource)
            sliver.setExpiration(expiration)
            sliver.setStartTime(start_time)
            sliver.setEndTime(end_time)
            sliver.setAllocationState(STATE_GENI_ALLOCATED)
        self._agg.allocate(slice_urn, newslice.resources())
        self._agg.allocate(user_urn, newslice.resources())
        self._slices[slice_urn] = newslice

        # Log the allocation
        self.logger.info("Allocated new slice %s" % slice_urn)
        for sliver in newslice.slivers():
            self.logger.info("Allocated resource %s to slice %s as sliver %s",
                             sliver.resource().id, slice_urn, sliver.urn())

        manifest = self.manifest_rspec(slice_urn)
        result = dict(geni_rspec=manifest,
                      geni_slivers=[s.status() for s in newslice.slivers()])
        return self.successResult(result)

    def Provision(self, urns, credentials, options):
        """Allocate slivers to the given slice according to the given RSpec.
        Return an RSpec of the actually allocated resources.
        """
        self.logger.info('Provision(%r)' % (urns))
        self.expire_slivers()

        the_slice, slivers = self.decode_urns(urns)
        # Note this list of privileges is really the name of an operation
        # from the privilege_table in sfa/trust/rights.py
        # Credentials will specify a list of privileges, each of which
        # confers the right to perform a list of operations.
        # EG the 'info' privilege in a credential allows the operations
        # listslices, listnodes, policy
        privileges = (PROVISION_PRIV,)
        creds = self.getVerifiedCredentials(the_slice.urn, credentials, options, privileges)

        if 'geni_rspec_version' not in options:
            # This is a required option, so error out with bad arguments.
            self.logger.error('No geni_rspec_version supplied to Provision.')
            return self.errorResult(AM_API.BAD_ARGS,
                                    'Bad Arguments: option geni_rspec_version was not supplied.')
        if 'type' not in options['geni_rspec_version']:
            self.logger.error('Provision: geni_rspec_version does not contain a type field.')
            return self.errorResult(AM_API.BAD_ARGS,
                                    'Bad Arguments: option geni_rspec_version does not have a type field.')
        if 'version' not in options['geni_rspec_version']:
            self.logger.error('Provision: geni_rspec_version does not contain a version field.')
            return self.errorResult(AM_API.BAD_ARGS,
                                    'Bad Arguments: option geni_rspec_version does not have a version field.')

        # Look to see what RSpec version the client requested
        # Error-check that the input value is supported.
        rspec_type = options['geni_rspec_version']['type']
        if isinstance(rspec_type, str):
            rspec_type = rspec_type.lower().strip()
        rspec_version = options['geni_rspec_version']['version']
        if rspec_type != 'geni':
            self.logger.error('Provision: Unknown RSpec type %s requested', rspec_type)
            return self.errorResult(AM_API.BAD_VERSION,
                                    'Bad Version: requested RSpec type %s is not a valid option.' % (rspec_type))
        if rspec_version != '3':
            self.logger.error('Provision: Unknown RSpec version %s requested', rspec_version)
            return self.errorResult(AM_API.BAD_VERSION,
                                    'Bad Version: requested RSpec version %s is not a valid option.' % (rspec_version))
        self.logger.info("Provision requested RSpec %s (%s)", rspec_type, rspec_version)

        # Only provision slivers that are in the scheduled time frame
        now = datetime.datetime.utcnow()
        provisionable_slivers = \
            [sliver for sliver in slivers \
                 if now >= sliver.startTime() and now <= sliver.endTime()]
        slivers = provisionable_slivers

        if len(slivers) == 0:
            return self.errorResult(AM_API.UNAVAILABLE,
                                    "No slivers available to provision at this time")

        max_expiration = self.min_expire(creds, self.max_lease, 
                                     ('geni_end_time' in options
                                      and options['geni_end_time']))
        for sliver in slivers:
            # Extend the lease and set to PROVISIONED
            expiration = min(sliver.endTime(), max_expiration)
            sliver.setEndTime(expiration)
            sliver.setExpiration(expiration)
            sliver.setAllocationState(STATE_GENI_PROVISIONED)
            sliver.setOperationalState(OPSTATE_GENI_NOT_READY)
        result = dict(geni_rspec=self.manifest_rspec(the_slice.urn),
                      geni_slivers=[s.status() for s in slivers])
        return self.successResult(result)

    def Delete(self, urns, credentials, options):
        """Stop and completely delete the named slivers and/or slice.
        """
        self.logger.info('Delete(%r)' % (urns))
        self.expire_slivers()

        the_slice, slivers = self.decode_urns(urns)
        privileges = (DELETESLIVERPRIV,)

        self.getVerifiedCredentials(the_slice.urn, credentials, options, privileges)

        # Grab the user_urn
        user_urn = gid.GID(string=options['geni_true_caller_cert']).get_urn()

        # If we get here, the credentials give the caller
        # all needed privileges to act on the given target.
        if the_slice.isShutdown():
            self.logger.info("Slice %s not deleted because it is shutdown",
                             the_slice.urn)
            return self.errorResult(AM_API.UNAVAILABLE,
                                    ("Unavailable: Slice %s is unavailable."
                                     % (the_slice.urn)))
        resources = [sliver.resource() for sliver in slivers]
        self._agg.deallocate(the_slice.urn, resources)
        self._agg.deallocate(user_urn, resources)
        for sliver in slivers:
            slyce = sliver.slice()
            slyce.delete_sliver(sliver)
            # If slice is now empty, delete it.
            if not slyce.slivers():
                self.logger.debug("Deleting empty slice %r", slyce.urn)
                del self._slices[slyce.urn]
        return self.successResult([s.status() for s in slivers])

    def PerformOperationalAction(self, urns, credentials, action, options):
        """Peform the specified action on the set of objects specified by
        urns.
        """
        self.logger.info('PerformOperationalAction(%r)' % (urns))
        self.expire_slivers()

        the_slice, slivers = self.decode_urns(urns)
        # Note this list of privileges is really the name of an operation
        # from the privilege_table in sfa/trust/rights.py
        # Credentials will specify a list of privileges, each of which
        # confers the right to perform a list of operations.
        # EG the 'info' privilege in a credential allows the operations
        # listslices, listnodes, policy
        privileges = (PERFORM_ACTION_PRIV,)
        _ = self.getVerifiedCredentials(the_slice.urn, credentials, options, privileges)

        # A place to store errors on a per-sliver basis.
        # {sliverURN --> "error", sliverURN --> "error", etc.}
        astates = []
        ostates = []
        if action == 'geni_start':
            astates = [STATE_GENI_PROVISIONED]
            ostates = [OPSTATE_GENI_NOT_READY]
        elif action == 'geni_restart':
            astates = [STATE_GENI_PROVISIONED]
            ostates = [OPSTATE_GENI_READY]
        elif action == 'geni_stop':
            astates = [STATE_GENI_PROVISIONED]
            ostates = [OPSTATE_GENI_READY]
        else:
            msg = "Unsupported: action %s is not supported" % (action)
            raise ApiErrorException(AM_API.UNSUPPORTED, msg)

        # Handle best effort. Look ahead to see if the operation
        # can be done. If the client did not specify best effort and
        # any resources are in the wrong state, stop and return an error.
        # But if the client specified best effort, trundle on and
        # do the best you can do.
        errors = collections.defaultdict(str)
        for sliver in slivers:
            # ensure that the slivers are provisioned
            if (sliver.allocationState() not in astates
                or sliver.operationalState() not in ostates):
                msg = "%d: Sliver %s is not in the right state for action %s."
                msg = msg % (AM_API.UNSUPPORTED, sliver.urn(), action)
                errors[sliver.urn()] = msg
        best_effort = False
        if 'geni_best_effort' in options:
            best_effort = bool(options['geni_best_effort'])
        if not best_effort and errors:
            raise ApiErrorException(AM_API.UNSUPPORTED,
                                    "\n".join(errors.values()))

        # Perform the state changes:
        for sliver in slivers:
            if (action == 'geni_start'):
                if (sliver.allocationState() in astates
                    and sliver.operationalState() in ostates):
                    sliver.setOperationalState(OPSTATE_GENI_READY)
            elif (action == 'geni_restart'):
                if (sliver.allocationState() in astates
                    and sliver.operationalState() in ostates):
                    sliver.setOperationalState(OPSTATE_GENI_READY)
            elif (action == 'geni_stop'):
                if (sliver.allocationState() in astates
                    and sliver.operationalState() in ostates):
                    sliver.setOperationalState(OPSTATE_GENI_NOT_READY)
            else:
                # This should have been caught above
                msg = "Unsupported: action %s is not supported" % (action)
                raise ApiErrorException(AM_API.UNSUPPORTED, msg)
        return self.successResult([s.status(errors[s.urn()])
                                   for s in slivers])


    def Status(self, urns, credentials, options):
        '''Report as much as is known about the status of the resources
        in the sliver. The AM may not know.
        Return a dict of sliver urn, status, and a list of dicts resource
        statuses.'''
        # Loop over the resources in a sliver gathering status.
        self.logger.info('Status(%r)' % (urns))
        self.expire_slivers()
        the_slice, slivers = self.decode_urns(urns)
        privileges = (SLIVERSTATUSPRIV,)
        self.getVerifiedCredentials(the_slice.urn, credentials, options, privileges)

        geni_slivers = list()
        for sliver in slivers:
            expiration = self.rfc3339format(sliver.expiration())
            start_time = self.rfc3339format(sliver.startTime())
            end_time = self.rfc3339format(sliver.endTime())
            allocation_state = sliver.allocationState()
            operational_state = sliver.operationalState()
            geni_slivers.append(dict(geni_sliver_urn=sliver.urn(),
                                     geni_expires=expiration,
                                     geni_start_time=start_time,
                                     geni_end_time=end_time,
                                     geni_allocation_status=allocation_state,
                                     geni_operational_status=operational_state,
                                     geni_error=''))
        result = dict(geni_urn=the_slice.urn,
                      geni_slivers=[s.status() for s in slivers])
        return self.successResult(result)

    def Describe(self, urns, credentials, options):
        """Generate a manifest RSpec for the given resources.
        """
        self.logger.info('Describe(%r)' % (urns))
        self.expire_slivers()
        # APIv3 spec says that a slice with nothing local should
        # give an empty manifest, not an error
        try:
            the_slice, slivers = self.decode_urns(urns)
        except ApiErrorException, ae:
            if ae.code == AM_API.SEARCH_FAILED and "Unknown slice" in ae.output:
                # This is ok
                slivers = []
                the_slice = Slice(urns[0])
            else:
                raise ae

        privileges = (SLIVERSTATUSPRIV,)
        self.getVerifiedCredentials(the_slice.urn, credentials, options, privileges)

        if 'geni_rspec_version' not in options:
            # This is a required option, so error out with bad arguments.
            self.logger.error('No geni_rspec_version supplied to Describe.')
            return self.errorResult(AM_API.BAD_ARGS,
                                    'Bad Arguments: option geni_rspec_version was not supplied.')
        if 'type' not in options['geni_rspec_version']:
            self.logger.error('Describe: geni_rspec_version does not contain a type field.')
            return self.errorResult(AM_API.BAD_ARGS,
                                    'Bad Arguments: option geni_rspec_version does not have a type field.')
        if 'version' not in options['geni_rspec_version']:
            self.logger.error('Describe: geni_rspec_version does not contain a version field.')
            return self.errorResult(AM_API.BAD_ARGS,
                                    'Bad Arguments: option geni_rspec_version does not have a version field.')

        # Look to see what RSpec version the client requested
        # Error-check that the input value is supported.
        rspec_type = options['geni_rspec_version']['type']
        if isinstance(rspec_type, str):
            rspec_type = rspec_type.lower().strip()
        rspec_version = options['geni_rspec_version']['version']
        if rspec_type != 'geni':
            self.logger.error('Describe: Unknown RSpec type %s requested', rspec_type)
            return self.errorResult(AM_API.BAD_VERSION,
                                    'Bad Version: requested RSpec type %s is not a valid option.' % (rspec_type))
        if rspec_version != '3':
            self.logger.error('Describe: Unknown RSpec version %s requested', rspec_version)
            return self.errorResult(AM_API.BAD_VERSION,
                                    'Bad Version: requested RSpec version %s is not a valid option.' % (rspec_version))
        self.logger.info("Describe requested RSpec %s (%s)", rspec_type, rspec_version)

        manifest_body = ""
        for sliver in slivers:
            manifest_body += self.manifest_sliver(sliver)
        manifest = self.manifest_header() + manifest_body + self.manifest_footer()
        self.logger.debug("Result is now \"%s\"", manifest)
        # Optionally compress the manifest
        if 'geni_compressed' in options and options['geni_compressed']:
            try:
                manifest = base64.b64encode(zlib.compress(manifest))
            except Exception, exc:
                self.logger.error("Error compressing and encoding resource list: %s", traceback.format_exc())
                raise Exception("Server error compressing resource list", exc)
        value = dict(geni_rspec=manifest,
                     geni_urn=the_slice.urn,
                     geni_slivers=[s.status() for s in slivers])
        return self.successResult(value)

    def Renew(self, urns, credentials, expiration_time, options):
        '''Renew the local sliver that is part of the named Slice
        until the given expiration time (in UTC with a TZ per RFC3339).
        Requires at least one credential that is valid until then.
        Return False on any error, True on success.'''

        self.logger.info('Renew(%r, %r)' % (urns, expiration_time))
        self.expire_slivers()
        the_slice, slivers = self.decode_urns(urns)

        privileges = (RENEWSLIVERPRIV,)
        creds = self.getVerifiedCredentials(the_slice.urn, credentials, options, privileges)

        # All the credentials we just got are valid
        expiration = self.min_expire(creds, self.max_lease)
        requested = dateutil.parser.parse(str(expiration_time), tzinfos=tzd)


        # Per the AM API, the input time should be TZ-aware
        # But since the slice cred may not (per ISO8601), convert
        # it to naiveUTC for comparison
        requested = self._naiveUTC(requested)


        # If geni_extend_alap option provided, use the earlier 
        # of the requested time and max expiration as the expiration time
        if 'geni_extend_alap' in options and options['geni_extend_alap']:
            if expiration < requested:
                self.logger.info("Got geni_extend_alap: revising slice %s renew request from %s to %s", urns, requested, expiration)
                requested = expiration

        now = datetime.datetime.utcnow()
        if requested > expiration:
            # Fail the call, the requested expiration exceeds the slice expir.
            msg = (("Out of range: Expiration %s is out of range"
                   + " (past last credential expiration of %s).")
                   % (expiration_time, expiration))
            self.logger.error(msg)
            return self.errorResult(AM_API.OUT_OF_RANGE, msg)
        elif requested < now:
            msg = (("Out of range: Expiration %s is out of range"
                   + " (prior to now %s).")
                   % (expiration_time, now.isoformat()))
            self.logger.error(msg)
            return self.errorResult(AM_API.OUT_OF_RANGE, msg)
        else:
            # Renew all the named slivers
            for sliver in slivers:
                sliver.setExpiration(requested)
                end_time = max(sliver.endTime(), requested)
                sliver.setEndTime(end_time)

        geni_slivers = [s.status() for s in slivers]
        return self.successResult(geni_slivers)

    def Shutdown(self, slice_urn, credentials, options):
        '''For Management Authority / operator use: shut down a badly
        behaving sliver, without deleting it to allow for forensics.'''
        self.logger.info('Shutdown(%r)' % (slice_urn))
        self.expire_slivers()
        privileges = (SHUTDOWNSLIVERPRIV,)
        self.getVerifiedCredentials(slice_urn, credentials, options, privileges)

        the_urn = urn.URN(urn=slice_urn)
        if the_urn.getType() != 'slice':
            self.logger.error('URN %s is not a slice URN.', slice_urn)
            return self.errorResult(AM_API.BAD_ARGS, "Bad Args: Not a slice URN")
        the_slice, _ = self.decode_urns([slice_urn])
        if the_slice.isShutdown():
            self.logger.error('Slice %s is already shut down.', slice_urn)
            return self.errorResult(AM_API.FORBIDDEN, "Already shut down.")
        the_slice.shutdown()
        return self.successResult(True)

    def successResult(self, value):
        code_dict = dict(geni_code=0,
                         am_type=self._am_type,
                         am_code=0)
        return dict(code=code_dict,
                    value=value,
                    output="")

    def _no_such_slice(self, slice_urn):
        return self.errorResult(AM_API.SEARCH_FAILED,
                                ('Search Failed: no slice "%s" found'
                                 % (slice_urn)))

    def errorResult(self, code, output, am_code=None):
        code_dict = dict(geni_code=code,
                         am_type=self._am_type)
        if am_code is not None:
            code_dict['am_code'] = am_code
        return dict(code=code_dict,
                    value="",
                    output=output)

    def getVerifiedCredentials(self, slice_urn, credentials, options, privileges):
        """Verify that at least one geni_cred in credentials has 
        all the privileges listed in privileges on slice named
        slice_urn.
        options here are passed to the verify_from_string method 
        of the cred verifier.
        Raise Exception if no credentials with enough privileges are found. 
        Return the credentials returned by the credential verifier otherwise.
        """
        # Note that verify throws an exception on failure.
        # Use the client PEM format cert as retrieved
        # from the https connection by the SecureXMLRPCServer
        # to identify the caller.
        credentials = [self.normalize_credential(c) for c in credentials]
        credentials = [c['geni_value'] for c in filter(isGeniCred, credentials)]
        try:
            creds = self._cred_verifier.verify_from_strings(self._server.get_pem_cert(),
                                                            credentials,
                                                            slice_urn,
                                                            privileges,
                                                            options)
        except Exception, e:
            raise xmlrpclib.Fault('Insufficient privileges', str(e))

        return creds

    def _naiveUTC(self, dt):
        """Converts dt to a naive datetime in UTC.

        if 'dt' has a timezone then
        convert to UTC
        strip off timezone (make it "naive" in Python parlance)
        """
        if dt.tzinfo:
            tz_utc = dateutil.tz.tzutc()
            dt = dt.astimezone(tz_utc)
            dt = dt.replace(tzinfo=None)
        return dt

    def advert_resource(self, resource):
        tmpl = '''  <node component_manager_id="%s" 
        component_name="%s" 
        component_id="%s" 
        exclusive="%s">
    <sliver_type name="fake-vm"/>
    <available now="%s"/>
  </node>
'''
        resource_id = str(resource.id)
        resource_exclusive = str(False).lower()
        resource_available = str(resource.available).lower()
        resource_urn = resource.urn(self._urn_authority)
        return tmpl % (self._my_urn,
                       resource_id,
                       resource_urn,
                       resource_exclusive,
                       resource_available)

    # See https://www.protogeni.net/trac/protogeni/wiki/RspecAdOpState
    def advert_header(self):
        schema_locs = ["http://www.geni.net/resources/rspec/3",
                       "http://www.geni.net/resources/rspec/3/ad.xsd",
                       "http://www.geni.net/resources/rspec/ext/opstate/1",
                       "http://www.geni.net/resources/rspec/ext/opstate/1/ad.xsd"]
        header = '''<?xml version="1.0" encoding="UTF-8"?>
<rspec xmlns="http://www.geni.net/resources/rspec/3"
       xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
       xsi:schemaLocation="%s"
       type="advertisement">
<!-- Operational states for fake-vm nodes -->
<rspec_opstate xmlns="http://www.geni.net/resources/rspec/ext/opstate/1"
  aggregate_manager_id="%s"
  start="geni_notready">
  <sliver_type name="fake-vm"/>
  <state name="geni_notready">
    <action name="geni_start" next="geni_ready">
      <description>Transition the node to a ready state.</description>
    </action>
    <description>Fake VMs are immediately ready once started.</description>
  </state>
  <state name="geni_ready">
    <description>The Fake VM node is up and ready to use.</description>
    <action name="geni_restart" next="geni_ready">
      <description>Reboot the node</description>
    </action>
    <action name="geni_stop" next="geni_notready">
      <description>Power down or stop the node.</description>
    </action>
  </state>
</rspec_opstate>
'''
        return header % (' '.join(schema_locs), self._my_urn)

    def advert_footer(self):
        return '</rspec>'

    def manifest_header(self):
        header = '''<?xml version="1.0" encoding="UTF-8"?>
<rspec xmlns="http://www.geni.net/resources/rspec/3"
       xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
       xsi:schemaLocation="http://www.geni.net/resources/rspec/3 http://www.geni.net/resources/rspec/3/manifest.xsd"
       type="manifest">
'''
        return header

    def manifest_sliver(self, sliver):
        tmpl = '''<node client_id="%s"
        component_id="%s"
        component_manager_id="%s"
        sliver_id="%s"/>
'''
        return tmpl % (sliver.resource().external_id,
                       sliver.resource().urn(self._urn_authority),
                       self._my_urn, sliver.urn())

    def manifest_slice(self, slice_urn):
        res = ''
        for sliver in self._slices[slice_urn].slivers():
            res = res + self.manifest_sliver(sliver)
        return res

    def manifest_footer(self):
        return '</rspec>\n'

    def manifest_rspec(self, slice_urn):
        return self.manifest_header() + self.manifest_slice(slice_urn) + self.manifest_footer()

    def resources(self, available=None):
        """Get the list of managed resources. If available is not None,
        it is interpreted as boolean and only resources whose availability
        matches will be included in the returned list.
        """
        result = self._agg.catalog()
        if available is not None:
            result = [r for r in result if r.available is available]
        return result

    def rfc3339format(self, dt):
        """Return a string representing the given datetime in rfc3339 format.
        """
        # Add UTC TZ, to have an RFC3339 compliant datetime, per the AM API
        self._naiveUTC(dt)
        time_with_tz = dt.replace(tzinfo=dateutil.tz.tzutc())
        return time_with_tz.isoformat()

    def expire_slivers(self):
        """Look for expired slivers and clean them up. Ultimately this
        should be run by a daemon, but until then, it is called at the
        beginning of all methods.
        """
        expired = list()
        now = datetime.datetime.utcnow()
        for slyce in self._slices.values():
            for sliver in slyce.slivers():
                self.logger.debug('Checking sliver %s (expiration = %r) at %r',
                                  sliver.urn(), sliver.expiration(), now)
                if sliver.expiration() < now:
                    self.logger.debug('Expring sliver %s (expiration = %r) at %r',
                                      sliver.urn(), sliver.expiration(), now)
                    expired.append(sliver)
        self.logger.info('Expiring %d slivers', len(expired))
        for sliver in expired:
            slyce = sliver.slice()
            slyce.delete_sliver(sliver)
            # If slice is now empty, delete it.
            if not slyce.slivers():
                self.logger.debug("Deleting empty slice %r", slyce.urn)
                del self._slices[slyce.urn]

    def decode_urns(self, urns, **kwargs):
        """Several methods need to map URNs to slivers and/or deduce
        a slice based on the slivers specified.

        When called from AMMethodContext, kwargs will have 2 keys
        (credentials and options), with the same values as the credentials
        and options parameters of the AMv3 API entry points. This can be 
        usefull for delegates derived from the ReferenceAggregateManager, 
        but is not used in this reference implementation.

        Returns a slice and a list of slivers.
        """
        slivers = list()
        for urn_str in urns:
            myurn = urn.URN(urn=urn_str)
            urn_type = myurn.getType()
            if urn_type == 'slice':
                if self._slices.has_key(urn_str):
                    the_slice = self._slices[urn_str]
                    slivers.extend(the_slice.slivers())
                else:
                    raise ApiErrorException(AM_API.SEARCH_FAILED,
                                            'Unknown slice "%s"' % (urn_str))
            elif urn_type == 'sliver':
                # Gross linear search. Maybe keep a map of known sliver urns?
                needle = None
                for a_slice in self._slices.values():
                    for sliver in a_slice.slivers():
                        if sliver.urn() == urn_str:
                            needle = sliver
                            break
                    if needle:
                        break
                if needle:
                    slivers.append(needle)
                else:
                    raise ApiErrorException(AM_API.SEARCH_FAILED,
                                            'Unknown sliver "%s"' % (urn_str))
            else:
                raise Exception("Bad URN type '%s'" % urn_type)
        # Now verify that everything is part of the same slice
        all_slices = set([o.slice() for o in slivers])
        if len(all_slices) == 1:
            the_slice = all_slices.pop()
            if the_slice.isShutdown():
                msg = 'Refused: slice %s is shut down.' % (the_slice.urn)
                raise ApiErrorException(AM_API.REFUSED, msg)
            return the_slice, slivers
        else:
            raise Exception('Objects specify multiple slices')

    def normalize_credential(self, cred, ctype=Credential.SFA_CREDENTIAL_TYPE, cversion='3'):
        """This is a temporary measure to play nice with omni
        until it supports the v3 credential arg (list of dicts)."""
        # Play nice...
        if isinstance(cred, dict):
            return cred
        elif not isinstance(cred, str):
            cred = str(cred)
        cred_type, cred_version = credutils.get_cred_type(cred)
        return dict(geni_type=cred_type, geni_version=cred_version, \
                       geni_value=cred)

    def min_expire(self, creds, max_duration=None, requested=None):
        """Compute the expiration time from the supplied credentials,
        a max duration, and an optional requested duration. The shortest
        time amongst all of these is the resulting expiration.
        """
        now = datetime.datetime.utcnow()
        expires = [self._naiveUTC(c.expiration) for c in creds]
        if max_duration:
            expires.append(now + max_duration)
        if requested:
            requested = self._naiveUTC(dateutil.parser.parse(str(requested), tzinfos=tzd))
            # Ignore requested time in the past.
            if requested > now:
                expires.append(self._naiveUTC(requested))
        return min(expires)


class AggregateManager(object):
    """The public API for a GENI Aggregate Manager.  This class provides the
    XMLRPC interface and invokes a delegate for all the operations.
    """

    def __init__(self, trust_roots_dir, delegate, authorizer=None,
                 resource_manager=None):
        self._trust_roots_dir = trust_roots_dir
        self._delegate = delegate
        self.logger = logging.getLogger('gcf.am3')
        self.authorizer = authorizer
        self.resource_manager = resource_manager

    def _exception_result(self, exception):
        output = str(exception)
        self.logger.warning(output)
        # XXX Code for no slice here?
        return dict(code=dict(geni_code=102,
                              am_type="gcf",
                              am_code=0),
                    value="",
                    output=output)

    def _api_error(self, exception):
        self.logger.warning(exception)
        return dict(code=dict(geni_code=exception.code,
                              am_type='gcf'),
                    value="",
                    output=exception.output)

    def GetVersion(self, options=dict()):
        '''Specify version information about this AM. That could
        include API version information, RSpec format and version
        information, etc. Return a dict.'''
        try:
            return self._delegate.GetVersion(options)
        except ApiErrorException as e:
            return self._api_error(e)
        except Exception as e:
            traceback.print_exc()
            return self._exception_result(e)

    def ListResources(self, credentials, options):
        '''Return an RSpec of resources managed at this AM.
        If geni_available is specified in the options,
        then only report available resources. If geni_compressed
        option is specified, then compress the result.'''
        args = {}
        with AMMethodContext(self, AM_Methods.LIST_RESOURCES_V3,
                             self.logger, self.authorizer, 
                             self.resource_manager,
                             credentials,
                             args, options, is_v3=True) as amc:
            if not amc._error:
                amc._result = \
                    self._delegate.ListResources(credentials, amc._options)
        return amc._result

    def Allocate(self, slice_urn, credentials, rspec, options):
        """Allocate resources to a slice. This is a low-effort call
        and the resources will have short expiration times. If the
        experimenter really wants the resources they must call
        'Provision'. This is step 1 in the process of acquiring
        usable resources from an aggregate.
        """
        args = {'slice_urn' : slice_urn, 'rspec' : rspec}
        with AMMethodContext(self, AM_Methods.ALLOCATE_V3,
                             self.logger, self.authorizer, 
                             self.resource_manager,
                             credentials,
                             args, options, is_v3=True, 
                             resource_bindings=True) as amc:
            if not amc._error:
                slice_urn = amc._args['slice_urn']
                rspec = amc._args['rspec']
                amc._result = \
                    self._delegate.Allocate(slice_urn, credentials, 
                                            rspec, amc._options)
        return amc._result

    def Provision(self, urns, credentials, options):
        """Make a reservation 'real' by instantiating the resources
        reserved in a previous allocate invocation. This is step 2 in
        the process of acquiring usable resources from an aggregate.
        """
        args = {'urns' : urns }
        with AMMethodContext(self, AM_Methods.PROVISION_V3,
                             self.logger, self.authorizer, 
                             self.resource_manager,
                             credentials,
                             args, options, is_v3=True) as amc:
            if not amc._error:
                urns = amc._args['urns']
                amc._result = \
                    self._delegate.Provision(urns, credentials, amc._options)
        return amc._result

    def Delete(self, urns, credentials, options):
        """Delete the given resources.
        """
        args = {'urns' : urns }
        with AMMethodContext(self, AM_Methods.DELETE_V3,
                             self.logger, self.authorizer, 
                             self.resource_manager,
                             credentials,
                             args, options, is_v3=True) as amc:
            if not amc._error:
                urns = amc._args['urns']
                amc._result = \
                    self._delegate.Delete(urns, credentials, amc._options)
        return amc._result

    def PerformOperationalAction(self, urns, credentials, action, options):
        """Perform the given action on the objects named by the given URNs.
        Once resources have been provisioned, they must be started (booted).
        This is the third and final step in the process of acquiring usable
        resources from an aggregate.
        """
        args = {'urns' : urns, 'action' : action }
        with AMMethodContext(self, AM_Methods.PERFORM_OPERATIONAL_ACTION_V3,
                             self.logger, self.authorizer, 
                             self.resource_manager,
                             credentials,
                             args, options, is_v3=True) as amc:
            if not amc._error:
                urns = amc._args['urns']
                action = amc._args['action']
                amc._result = \
                    self._delegate.PerformOperationalAction(urns, credentials, 
                                                            action, 
                                                            amc._options)
        return amc._result

    def Status(self, urns, credentials, options):
        """Report the status of the specified resources.
        """
        args = {'urns' : urns }
        with AMMethodContext(self, AM_Methods.STATUS_V3,
                             self.logger, self.authorizer, 
                             self.resource_manager,
                             credentials,
                             args, options, is_v3 = True) as amc:
            if not amc._error:
                urns = amc._args['urns']
                amc._result = \
                    self._delegate.Status(urns, credentials, amc._options)
        return amc._result

    def Describe(self, urns, credentials, options):
        """Describe the specified resources.
        Return a manifest RSpec of the resources as well
        as their current status.
        """
        args = {'urns' : urns }
        with AMMethodContext(self, AM_Methods.DESCRIBE_V3,
                             self.logger, self.authorizer, 
                             self.resource_manager,
                             credentials,
                             args, options, is_v3 = True) as amc:
            if not amc._error:
                urns = amc._args['urns']
                amc._result = \
                    self._delegate.Describe(urns, credentials, amc._options)
        return amc._result

    def Renew(self, urns, credentials, expiration_time, options):
        """Extend the life of the given slice until the given
        expiration time."""
        args = {'urns' : urns, 'expiration_time' : expiration_time }
        with AMMethodContext(self, AM_Methods.RENEW_V3,
                             self.logger, self.authorizer, 
                             self.resource_manager,
                             credentials,
                             args, options, is_v3 = True,
                             resource_bindings=True) as amc:
            if not amc._error:
                urns = amc._args['urns']
                expiration_time = amc._args['expiration_time']
                amc._result = \
                    self._delegate.Renew(urns, credentials, expiration_time, 
                                         amc._options)
        return amc._result

    def Shutdown(self, slice_urn, credentials, options):
        '''For Management Authority / operator use: shut down a badly
        behaving sliver, without deleting it to allow for forensics.'''
        args = {'slice_urn' : slice_urn }
        with AMMethodContext(self, AM_Methods.SHUTDOWN_V3,
                             self.logger, self.authorizer, 
                             self.resource_manager,
                             credentials,
                             args, options, is_v3 = True) as amc:
            if not amc._error:
                slice_urn = amc._args['slice_urn']
                amc._result = \
                    self._delegate.Shutdown(slice_urn, credentials, 
                                            amc._options)
        return amc._result


class AggregateManagerServer(object):
    """An XMLRPC Aggregate Manager Server. Delegates calls to given delegate,
    or the default printing AM."""

    def __init__(self, addr, keyfile=None, certfile=None,
                 trust_roots_dir=None,
                 ca_certs=None, base_name=None,
                 authorizer=None, resource_manager=None,
                 delegate=None):
        # ca_certs arg here must be a file of concatenated certs
        if ca_certs is None:
            raise Exception('Missing CA Certs')
        elif not os.path.isfile(os.path.expanduser(ca_certs)):
            raise Exception('CA Certs must be an existing file of accepted root certs: %s' % ca_certs)

        # Decode the addr into a URL. Is there a pythonic way to do this?
        server_url = "https://%s:%d/" % addr
        if delegate is None:
            delegate = ReferenceAggregateManager(trust_roots_dir, base_name,
                                                 server_url)

        # FIXED: set logRequests=true if --debug
        logRequest=logging.getLogger().getEffectiveLevel()==logging.DEBUG
        self._server = SecureXMLRPCServer(addr, keyfile=keyfile,
                                          certfile=certfile, ca_certs=ca_certs, 
                                          logRequests=logRequest)
        aggregate_manager = AggregateManager(trust_roots_dir, delegate, 
                                             authorizer, resource_manager)
        self._server.register_instance(aggregate_manager)
        # Set the server on the delegate so it can access the
        # client certificate.
        delegate._server = self._server

        if not base_name is None:
            global RESOURCE_NAMESPACE
            RESOURCE_NAMESPACE = base_name

    def serve_forever(self):
        self._server.serve_forever()

    def register_instance(self, instance):
        # Pass the AM instance to the generic XMLRPC server,
        # which lets it know what XMLRPC methods to expose
        self._server.register_instance(instance)
