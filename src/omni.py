#!/usr/bin/python

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

""" The OMNI client
    This client is a GENI API client that is capable of connecting
    to the supported control frameworks for slice creation and deletion.
    It is also able to parse and create standard RSPECs of all supported 
    control frameworks.
    See README-omni.txt

    Be sure to create an omni config file (typically ~/.gcf/omni_config)
    and supply valid paths to your per control framework user certs and keys.

    Typical usage:
    omni.py -f sfa listresources 
    
    The currently supported control frameworks are SFA, PG and GCF.

    Extending Omni to support additional types of Aggregate Managers
    with different RSpec formats requires adding a new omnispec/rspec
    conversion file.

    Extending Omni to support additional frameworks with their own
    clearinghouse APIs requires adding a new Framework extension class.

    Return Values of various omni commands:
       [string dictionary] = omni.py getversion # dict is keyed by AM url
       [string dictionary] = omni.py listresources
       On success: [string sliceurnstring] = omni.py createslice SLICENAME
       On fail: [string None] = omni.py createslice SLICENAME
       [string rspec] = omni.py createsliver SLICENAME RSPEC_FILENAME
       [string Boolean] = omni.py deletesliver SLICENAME
       [string Boolean] = omni.py deleteslice SLICENAME
       On success: [string dateTimeRenewedTo] = omni.py renewslice SLICENAME
       On fail: [string None] = omni.py renewslice SLICENAME
       On success: [string dateTimeRenewedTo] = omni.py renewsliver SLICENAME
       On fail: [string None] = omni.py renewsliver SLICENAME
       [string listOfSliceNames] = omni.py listmyslices USER
       [string dictionary] = omni .py sliverstatus SLICENAME
       [string Boolean] = omni.py shutdown SLICENAME
    
"""

from copy import copy
import datetime
import dateutil.parser
import json
import logging
import optparse
import os
import pprint
import ssl
import sys
import traceback
import xml.dom
import xml.dom.minidom as md
import xmlrpclib
import zlib
import ConfigParser

from omnilib.omnispec.translation import rspec_to_omnispec, omnispec_to_rspec
from omnilib.omnispec.omnispec import OmniSpec
from omnilib.util.faultPrinting import cln_xmlrpclib_fault
from omnilib.util.dossl import _do_ssl
import omnilib.xmlrpc.client

#import sfa.trust.gid as gid

OMNI_CONFIG_TEMPLATE='/etc/omni/templates/omni_config'

class CallHandler(object):
    """Handle calls on the framework. Valid calls are all
    methods without an underscore: getversion, createslice, deleteslice, 
    getslicecred, listresources, createsliver, deletesliver,
    renewsliver, sliverstatus, shutdown
    """

    def __init__(self, framework, config, opts):
        self.framework = framework
        self.logger = config['logger']
        self.omni_config = config['omni']
        self.config = config
        self.opts = opts
        
    def _raise_omni_error( self, msg ):
        self.logger.error( msg )
        raise OmniError, msg

    def _handle(self, args):
        if len(args) == 0:
            self._raise_omni_error('Insufficient number of arguments - Missing command to run')
        
        call = args[0].lower()
        if call.startswith('_'):
            return
        if not hasattr(self,call):
            self._raise_omni_error('Unknown function: %s' % call)
        return getattr(self,call)(args[1:])

    def _getclients(self, ams=None):
        """Create XML-RPC clients for each aggregate and return them
        as a sequence.
        """
        clients = []
        for (urn, url) in self._listaggregates().items():
            client = make_client(url, self.framework, self.opts)
            client.urn = urn
            client.url = url
            clients.append(client)
        if clients == []:
            self.logger.warn( 'No aggregates found' )
        return clients
        
    def _listaggregates(self):
        """List the aggregates that can be used for the current operation.
        If an aggregate was specified on the command line, use only that one.
        Else if aggregates are specified in the config file, use that set.
        Else ask the framework for the list of aggregates.
        Returns the aggregates as a dict of urn => url pairs.
        """
        if self.opts.aggregate:
            # No URN is specified, so put in 'unspecified_AM_URN'
            return dict(unspecified_AM_URN=self.opts.aggregate.strip())
        elif not self.omni_config.get('aggregates', '').strip() == '':
            aggs = {}
            for url in self.omni_config['aggregates'].strip().split(','):
                url = url.strip()
                if url != '':
                    aggs[url] = url
            return aggs                
        else:
            aggs =  _do_ssl(self.framework, None, "List Aggregates from control framework", self.framework.list_aggregates)
            if aggs is  None:
                return {}
            return aggs


    def listmyslices(self, args):
        """Provides a list of slices of user provided as first argument """
        if len(args) > 0:
            username = args[0].strip()
        else:
            self._raise_omni_error('listmyslices requires 1 arg: user')

        retStr = ""
        slices=None
        slices = self._listmyslices( username )
        if slices is None:
            # only end up here if call to _do_ssl failed
            slices = []
            self.logger.error("Failed to list slices for user '%s'"%(username))
            retStr += "Server error: "
        elif len(slices) > 0:
            self.logger.info("User '%s' has slices: \n\t%s"%(username,"\n\t".join(slices)))
        else:
            self.logger.info("User '%s' has NO slices."%username)

        # summary
        retStr += "Found %d slices for user '%s'.\n"%(len(slices), username)

        return retStr, slices

    def _listmyslices( self, username ):
        slices =  _do_ssl(self.framework, None, "List Slices from Slice Authority", self.framework.list_my_slices, username)
        return slices

    def _listresources(self, args):
        """Queries resources on various aggregates.
        
        Takes an optional slicename.
        Uses optional aggregate option or omni_config aggregate param.

        Doesn't care about omnispec vs native.
        Doesn't care how many aggregates that you query.

        Returns a dictionary of rspecs with the following format:
           rspecs[(urn, url)] = decompressed native rspec        
        """

        # rspecs[(urn, url)] = decompressed native rspec
        rspecs = {}
        options = {}

        options['geni_compressed'] = False;
        
        # An optional slice name might be specified.
        slicename = None
        if len(args) > 0:
            slicename = args[0].strip()

        # Get the credential for this query
        if slicename is None or slicename == "":
            slicename = None
            cred = None
            cred = _do_ssl(self.framework, None, "Get User Credential from control framework", self.framework.get_user_cred)

            if cred is None:
                self.logger.error('Cannot list resources: Could not get user credential')
                return None
        else:
            urn = self.framework.slice_name_to_urn(slicename)
            cred = self._get_slice_cred(urn)
            if cred is None:
                self.logger.error('Cannot list resources for slice %s: could not get slice credential' % (urn))
                return None
            self.logger.info('Gathering resources reserved for slice %s..' % slicename)

            options['geni_slice_urn'] = urn

        # We now have a credential

        # Query each aggregate for resources
        successCnt = 0
        clientList = self._getclients()
        # Connect to each available GENI AM to list their resources
        for client in clientList:
            if cred is None:
                self.logger.debug("Have null credential in call to ListResources!")
            self.logger.debug("Connecting to AM: %s at %s", client.urn, client.url)
            rspec = None
            self.logger.debug("Doing listresources with options %r", options)
            rspec = _do_ssl(self.framework, None, ("List Resources at %s" % (client.url)), client.ListResources, [cred], options)

            if not rspec is None:
                successCnt += 1
                if options.get('geni_compressed', False):
                    rspec = zlib.decompress(rspec.decode('base64'))
                rspecs[(client.urn, client.url)] = rspec

        self.logger.info( "Listed resources on %d out of %d possible aggregates." % (successCnt, len(clientList)))
        return rspecs

    def _printRspec(self, header, content, filename=None):
        """Print header and content to stdout or given file."""

        if filename is None:
            if header is not None:
                self.logger.info(header+":")
            self.logger.info(content)
        else:
            with open(filename,'w') as file:
                self.logger.info( "Writing to '%s'"%(filename))
                if header is not None:
                    file.write( header )
                    file.write( "\n" )
                file.write( content )
                file.write( "\n" )

    def listresources(self, args):
        '''Optional arg is a slice name limiting results. Call ListResources
        on all aggregates and prints the omnispec/rspec to stdout or to file.
        
        -n gives native format; otherwise print omnispec in json format
        -o writes to file instead of stdout; omnispec written to 1 file, native format written to single file per aggregate.'''

        # FIXME: filenames should be improved

        # An optional slice name might be specified.
        slicename = None
        if len(args) > 0:
            slicename = args[0].strip()

        # check command line args
        if self.opts.output:
            self.logger.info("Saving output to a file.")

        # Query the various aggregates for resources
        # rspecs[(urn, url)] = decompressed native rspec
        rspecs = self._listresources( args )
        numAggs = len(rspecs.keys())
        
        # handle empty case
        if not rspecs or rspecs == {}:
            if slicename:
                prtStr = "Got no resources on slice %s"%slicename 
            else:
                prtStr = "Got no resources" 
            self.logger.info( prtStr )
            return prtStr, None

 
        # Convert the rspecs to omnispecs
        returnedRspecs = {}
        omnispecs = {}
        fileCtr = 0
        for ((urn,url), rspec) in rspecs.items():                        
            self.logger.debug("Getting RSpec items for urn %s (%s)", urn, url)

            if self.opts.native:
                # Create HEADER
                if slicename is not None:
                    header = "Resources for slice %s at %s [%s]" % (slicename, urn, url)
                else:
                    header = "Resources at %s [%s]" % (urn, url)
                header = "<!-- "+header+" -->"

                # Create BODY
                returnedRspecs[(urn,url)] = rspec
                try:
                    newl = ''
                    if '\n' not in rspec:
                        newl = '\n'
                    content = md.parseString(rspec).toprettyxml(indent=' '*2, newl=newl)
                except:
                    content = rspec
                filename=None
                # Create FILENAME
                if self.opts.output:
                    fileCtr += 1 
                    if slicename:
                        filename = slicename+"_rspec_"+str(fileCtr)+"_native.xml"
                    else:
                        filename = "rspec_"+str(fileCtr)+"_native.xml"
                        
                # Create FILE
                self._printRspec( header, content, filename)

            else:
                # Throws exception if unparsable
                # No catch means 1 bad Agg and we lose all ospecs
                try:
                    omnispecs[ url ] = rspec_to_omnispec(urn,rspec)
                    returnedRspecs[(urn,url)] = omnispecs[url]
                except Exception, e:
                    self.logger.error("Failed to parse RSpec from AM %s (%s): %s", urn, url, e)

        if not self.opts.native:
            # Create HEADER
            if slicename is not None:
                header = "Resources for slice %s" % (slicename)
            else:
                header = "Resources"
            if self.opts.output:
                header = None

            # Create BODY
            content = json.dumps(omnispecs, indent=4)

            filename=None
            # Create FILENAME
            if self.opts.output:
                if slicename:
                    filename = slicename+"_rspec_omni.json"
                else:
                    filename = "rspec_omni.json"
                        
            # Create FILE
            if numAggs>0:
                self._printRspec( header, content, filename)


        # Create RETURNS
        if slicename:
            retVal = "Retrieved resources for slice %s from %d aggregates."%(slicename, numAggs)
        else:
            retVal = "Retrieved resources from %d aggregates."%(numAggs)
        if numAggs > 0:
            retVal +="\n"
            if self.opts.native:
                retVal += "Wrote rspecs"
                if self.opts.output:
                    retVal +=" to %d files"% fileCtr
            else:
                retVal += "Wrote omnispecs"
                if self.opts.output:
                    retVal +=" to '%s' file"% filename
            retVal +="."

        retItem = returnedRspecs

        return retVal, retItem
            
    def _ospec_to_rspecs(self, specfile):
        """Convert the given omnispec file into a dict of url => rspec."""
        jspecs = {}

        try:
            jspecs = json.loads(file(specfile,'r').read())
        except Exception, exc:
            self._raise_omni_error("Parse error reading omnispec %s: %s" % (specfile, exc))

        # Extract the individual omnispecs from the JSON dict
        omnispecs = {}
        for url, spec_dict in jspecs.items():
            omnispecs[url] = OmniSpec('', '', dictionary=spec_dict)
        
        # Only keep omnispecs that have a resource marked 'allocate'
        rspecs = {}
        for (url, ospec) in omnispecs.items():
            if url is None or url.strip() == "":
                self.logger.warn('omnispec format error: Empty URL')
                continue
            allocate = False
            for r in ospec.get_resources().values():
                if r.get_allocate():
                    allocate = True
                    break
            self.logger.debug( 'For %s allocate = %r' % (url, allocate))
            if allocate:
                rspecs[url] = omnispec_to_rspec(ospec, True)
            else:
                self.logger.debug('Nothing to allocate at %r', url)
        return rspecs

    def createsliver(self, args):
        retVal=''
        if len(args) < 2 or args[0] == None or args[0].strip() == "":
            self._raise_omni_error('createsliver requires 2 args: slicename and omnispec filename')

        # check command line args
        if self.opts.native and not self.opts.aggregate:
            # If native is requested, the user must supply an aggregate.
            msg = 'Specifying a native RSpec requires specifying an aggregate.'
            # Calling exit here is a bit of a hammer.
            # Maybe there's a gentler way.
            self._raise_omni_error(msg)

        name = args[0]
        # FIXME: catch errors getting slice URN to give prettier error msg?
        urn = self.framework.slice_name_to_urn(name.strip())
        slice_cred = self._get_slice_cred(urn)
        if slice_cred is None:
            self._raise_omni_error('Cannot create sliver %s: Could not get slice credential'
                     % (urn))

        retVal += self._print_slice_expiration(urn)+"\n"

        # Load up the user's edited omnispec
        specfile = args[1]
        if specfile is None or not os.path.isfile(specfile):
            self._raise_omni_error('File of resources to request missing: %s' % specfile)

        rspecs = None
        if self.opts.native:
            # read the native rspec into a string, and add it to the rspecs dict
            rspecs = {}
            try:
                rspec = file(specfile).read()
                rspecs[self.opts.aggregate] = rspec
            except Exception, exc:
                self._raise_omni_error('Unable to read rspec file %s: %s'
                         % (specfile, str(exc)))
        else:
            rspecs = self._ospec_to_rspecs(specfile)
        
        # Copy the user config and read the keys from the files into the structure
        slice_users = copy(self.config['users'])

        #slice_users = copy(self.omni_config['slice_users'])
        for user in slice_users:
            newkeys = []
            required = ['urn', 'keys']
            for req in required:
                if not req in user:
                    raise Exception("%s in omni_config is not specified for user %s" % (req,user))

            for key in user['keys'].split(','):        
                try:
                    newkeys.append(file(os.path.expanduser(key.strip())).read())
                except Exception, exc:
                    self.logger.error("Failed to read user key from %s: %s" %(user['keys'], exc))
            user['keys'] = newkeys
            if len(newkeys) == 0:
                self.logger.warn("Empty keys for user %s", user['urn'])
            else:
                self.logger.debug("Newkeys: %r", newkeys)

#            # Now error check the URN. It has to match that in the cert
#            # for AMs of type pg with tag < Tag v4.240? or stable-20110420?
#            # FIXME: Complain if NO urn is that in the cert?
#            # Only do the complaint if there is a PG AM that is old?
#            # Or somehow hold of complaining until per AM we have an issue?
#            certurn = ''
#            try:
#                certurn = gid.GID(filename=self.framework.cert).get_urn()
#            except Exception, exc:
#                self.logger.warn("Failed to get URN from cert %s: %s", self.framework.cert, exc)
#            if certurn != user['urn']:
#                self.logger.warn("Keys MAY not be installed for user %s. In PG prior to stable-20110420, the user URN must match that in your certificate. Your cert has urn %s but you specified that user %s has URN %s. Try making your omni_config user have a matching URN.", user, certurn, user, user['urn'])
#                # FIXME: if len(slice_users) == 1 then use the certurn?

#        if len(slice_users) < 1:
#            self.logger.warn("No user keys found to be uploaded")
        
        # Perform the allocations
        aggregate_urls = self._listaggregates().values()
        for (url, rspec) in rspecs.items():
                
            # Is this AM listed in the CH or our list of aggregates?
            # If not we won't be able to check its status and delete it later
            if not url in aggregate_urls:
                self.logger.info("""Be sure to remember (write down) AM URL %s. You are reserving
                    resources there, and your clearinghouse and config file won't remind you
                    to check that sliver later. Future listresources/sliverstatus/deletesliver 
                    calls need to include the '-a %s' arguments again to act on this sliver.""" % (url, url))
                
            if not self.opts.native:
                try:
                    newl = ''
                    if '\n' not in rspec:
                        newl = '\n'
                    self.logger.debug("Native RSpec for %s is:\n%s", url, md.parseString(rspec).toprettyxml(indent=' '*2, newl=newl))
                except:
                    self.logger.debug("Native RSpec for %s is:\n%s", url, rspec)

            # Okay, send a message to the AM this resource came from
            result = None
            client = make_client(url, self.framework, self.opts)
            result = _do_ssl(self.framework, None, ("Create Sliver %s at %s" % (urn, url)), client.CreateSliver, urn, [slice_cred], rspec, slice_users)

            if result != None and isinstance(result, str) and (result.startswith('<rspec') or result.startswith('<resv_rspec')):
                try:
                    newl = ''
                    if '\n' not in result:
                        newl = '\n'
                    self.logger.info('Asked %s to reserve resources. Result:\n%s' % (url, md.parseString(result).toprettyxml(indent=' '*2, newl=newl)))
                except:
                    self.logger.info('Asked %s to reserve resources. Result: %s' % (url, result))
                # summary
                retVal += 'Reserved resources on %s.' % (url)

            else:
                self.logger.info('Asked %s to reserve resources. Result: %s' % (url, result))
                # summary
                retVal += 'Asked %s to reserve resources. No manifest Rspec returned.' % (url)

            if '<RSpec type="SFA">' in rspec:
                # Figure out the login name
                self.logger.info("Please run the omni sliverstatus call on your slice to determine your login name to PL resources")
        return retVal, result

    def deletesliver(self, args):
        if len(args) == 0 or args[0] == None or args[0].strip() == "":
            self._raise_omni_error('deletesliver requires arg of slice name')

        name = args[0]

        # FIXME: catch errors getting slice URN to give prettier error msg?
        urn = self.framework.slice_name_to_urn(name)
        slice_cred = self._get_slice_cred(urn)
        if slice_cred is None:
            self._raise_omni_error('Cannot delete sliver %s: Could not get slice credential'
                     % (urn))

        if self.opts.orca_slice_id:
            self.logger.info('Using ORCA slice id %r', self.opts.orca_slice_id)
            urn = self.opts.orca_slice_id

        retVal = ""
        retCode = True
        successCnt = 0
        clientList = self._getclients()

        # Connect to each available GENI AM 
        ## The AM API does not cleanly state how to deal with
        ## aggregates which do not have a sliver in this slice.  We
        ## know at least one aggregate (PG) returns an Exception in
        ## this case.
        ## FIX ME: May need to look at handling of this more in the future.
        ## Also, if the user supplied the aggregate list, a failure is
        ## more interesting.  We can figure out what the error strings
        ## are at the various aggregates if they don't know about the
        ## slice and make those more quiet.  Finally, we can try
        ## sliverstatus at places where it fails to indicate places
        ## where you still have resources.
        for client in clientList:
            if _do_ssl(self.framework, None, ("Delete Sliver %s on %s" % (urn, client.url)), client.DeleteSliver, urn, [slice_cred]):
                self.logger.info("Deleted sliver %s on %s at %s" % (urn, client.urn, client.url))
                successCnt += 1
                retCode = retCode and True
            else:
                self.logger.warn("Failed to delete sliver %s on %s at %s" % (urn, client.urn, client.url))
                retCode = False
        retVal = "Deleted slivers on %d out of a possible %d aggregates" % (successCnt, len(clientList))
        return retVal, retCode

    def renewsliver(self, args):
        if len(args) < 2 or args[0] == None or args[0].strip() == "":
            self._raise_omni_error('renewsliver requires arg of slice name and new expiration time in UTC')

        name = args[0]

        # FIXME: catch errors getting slice URN to give prettier error msg?
        urn = self.framework.slice_name_to_urn(name)
        slice_cred = self._get_slice_cred(urn)
        if slice_cred is None:
            self._raise_omni_error('Cannot renew sliver %s: Could not get slice credential'
                     % (urn))

        time = None
        try:
            time = dateutil.parser.parse(args[1])
        except Exception, exc:
            self._raise_omni_error('renewsliver couldnt parse new expiration time from %s: %r' % (args[1], exc))

        retVal = ''
        slicecred_exp = self._get_slice_exp(slice_cred)
        retVal += self._print_slice_expiration(urn, slice_cred) +"\n"
        if time > slicecred_exp:
            self._raise_omni_error('Cannot renew sliver %s until %s UTC because it is after the slice expiration time %s UTC' % (urn, time, slicecred_exp))
        elif time <= datetime.datetime.utcnow():
            self.logger.info('Sliver %s will be set to expire now' % urn)
            time = datetime.datetime.utcnow()
        else:
            self.logger.debug('Slice expires at %s UTC after requested time %s UTC' % (slicecred_exp, time))

        self.logger.info('Renewing Sliver %s until %s UTC' % (urn, time))

        if self.opts.orca_slice_id:
            self.logger.info('Using ORCA slice id %r', self.opts.orca_slice_id)
            urn = self.opts.orca_slice_id

        successCnt = 0
        clientList = self._getclients()
        for client in clientList:
            # Note that the time arg includes UTC offset as needed
            res = _do_ssl(self.framework, None, ("Renew Sliver %s on %s" % (urn, client.url)), client.RenewSliver, urn, [slice_cred], time.isoformat())
            if not res:
                self.logger.warn("Failed to renew sliver %s on %s (%s)" % (urn, client.urn, client.url))
                retTime = None
            else:
                self.logger.info("Renewed sliver %s at %s (%s) until %s UTC" % (urn, client.urn, client.url, time.isoformat()))
                successCnt += 1
                retTime = time.isoformat()
        retVal += "Renewed slivers on %d out of %d aggregates for slice %s until %s UTC\n" % (successCnt, len(clientList), urn, time)
        return retVal, retTime

    def sliverstatus(self, args):
        if len(args) == 0 or args[0] == None or args[0].strip() == "":
            self._raise_omni_error('sliverstatus requires arg of slice name')

        name = args[0]

        # FIXME: catch errors getting slice URN to give prettier error msg?
        urn = self.framework.slice_name_to_urn(name)
        slice_cred = self._get_slice_cred(urn)
        if slice_cred is None:
            self._raise_omni_error('Cannot get sliver status for %s: Could not get slice credential'
                     % (urn))

        if self.opts.orca_slice_id:
            self.logger.info('Using ORCA slice id %r', self.opts.orca_slice_id)
            urn = self.opts.orca_slice_id

        successCnt = 0
        retItem = {}
        clientList = self._getclients()
        if len(clientList) > 0:
            self.logger.info('Status of Slice %s:' % urn)
        else:
            self.logger.warn("No aggregates available")
        for client in clientList:
            status = _do_ssl(self.framework, None, "Sliver status of %s at %s" % (urn, client.url), client.SliverStatus, urn, [slice_cred])
            if status:
                self.logger.info("Sliver at %s:" % (client.url))
                self.logger.info(pprint.pformat(status)+"\n")
                retItem[ client.url ] = status
                successCnt+=1
            else:
                retItem[ client.url ] = False
        retVal = "Returned status of slivers on %d of %d possible aggregates." % (successCnt, len(clientList))
        return retVal, retItem
                
    def shutdown(self, args):
        if len(args) == 0 or args[0] == None or args[0].strip() == "":
            self._raise_omni_error('shutdown requires arg of slice name')

        name = args[0]

        # FIXME: catch errors getting slice URN to give prettier error msg?
        urn = self.framework.slice_name_to_urn(name)
        slice_cred = self._get_slice_cred(urn)
        if slice_cred is None:
            self._raise_omni_error('Cannot shutdown slice %s: Could not get slice credential'
                     % (urn))
        if self.opts.orca_slice_id:
            self.logger.info('Using ORCA slice id %r', self.opts.orca_slice_id)
            urn = self.opts.orca_slice_id

        retVal = ""
        successCnt = 0
        retCode = True
        clientList = self._getclients()
        for client in clientList:
            if _do_ssl(self.framework, None, "Shutdown %s on %s" % (urn, client.url), client.Shutdown, urn, [slice_cred]):
                self.logger.info("Shutdown Sliver %s at %s on %s" % (urn, client.urn, client.url))
                successCnt+=1
                retCode = retCode and True
            else:
                self.logger.warn( "Failed to shutdown sliver %s on AM %s at %s" % (urn, client.urn, client.url) )
                retCode = False
        retVal = "Shutdown slivers of slice %s on %d of %d possible aggregates" % (urn, successCnt, len(clientList))
        return retVal, retCode

    def getversion(self, args):
        retVal = ""
        version = {}
        clients = self._getclients()
        successCnt = 0


        for client in clients:
            thisVersion = _do_ssl(self.framework, None, "GetVersion at %s" % (str(client.url)), client.GetVersion)
            version[ client.url ] = thisVersion
            if thisVersion is None:
                self.logger.warn( "URN: %s (url:%s) call FAILED.\n" % (client.urn, client.url) )
            else:
                # FIXME only print 'peers' on verbose
                pp = pprint.PrettyPrinter(indent=4)
                self.logger.info( "URN: %s (url: %s) has version: \n%s\n" % (client.urn, client.url, pp.pformat(thisVersion)) )
                successCnt += 1

        if len(clients)==0:
            retVal += "No aggregates to query.\n\n"
        else:
            retVal += "Got version for %d out of %d aggregates\n" % (successCnt,len(clients))

        return (retVal, version)
            

    def createslice(self, args):
        retVal = ""
        if len(args) == 0 or args[0] == None or args[0].strip() == "":
            self._raise_omni_error('createslice requires arg of slice name')

        name = args[0]

        # FIXME: catch errors getting slice URN to give prettier error msg?
        urn = self.framework.slice_name_to_urn(name)
        
        slice_cred = _do_ssl(self.framework, None, "Create Slice %s" % urn, self.framework.create_slice, urn)
        if slice_cred:
            slice_exp = self._get_slice_exp(slice_cred)
            printStr = "Created slice with Name %s, URN %s, Expiration %s" % (name, urn, slice_exp) 
            retVal += printStr+"\n"
            self.logger.info( printStr )
            success = urn

        else:
            printStr = "Create Slice Failed for slice name %s." % (name) 
            retVal += printStr+"\n"
            self.logger.error( printStr )
            success = None
            if not self.logger.isEnabledFor(logging.DEBUG):
                self.logger.warn( "   Try re-running with --debug for more information." )
        return retVal, success
        
    def deleteslice(self, args):
        if len(args) == 0 or args[0] == None or args[0].strip() == "":
            self._raise_omni_error('deleteslice requires arg of slice name')

        name = args[0]

        # FIXME: catch errors getting slice URN to give prettier error msg?
        urn = self.framework.slice_name_to_urn(name)

        res = _do_ssl(self.framework, None, "Delete Slice %s" % urn, self.framework.delete_slice, urn)
        # return True if successfully deleted slice, else False
        if (res is None) or (res is False):
            retVal = False
        else:
            retVal = True
        prtStr = "Delete Slice %s result: %r" % (name, res)
        self.logger.info(prtStr)
        return prtStr, retVal

    def getslicecred(self, args):
        if len(args) == 0 or args[0] == None or args[0].strip() == "":
            self._raise_omni_error('getslicecred requires arg of slice name')

        name = args[0]

        # FIXME: catch errors getting slice URN to give prettier error msg?
        urn = self.framework.slice_name_to_urn(name)
        cred = self._get_slice_cred(urn)

        if cred is None:
            retVal = "No slice credential returned for slice %s"%urn
            return retVal, None
        self._print_slice_expiration(urn)

        # Print the non slice cred bit to log stream so
        # capturing just stdout gives just the cred hopefully
        self.logger.info("Retrieved slice cred for slice %s", urn)
#VERBOSE ONLY        self.logger.info("Slice cred for slice %s", urn)
#VERBOSE ONLY        self.logger.info(cred)
#        print cred
        return cred, cred

        
    def _print_slice_expiration(self, urn, sliceCred=None):
        '''Check when the slice expires and print out to STDOUT'''
        # FIXME: push this to config?
        shorthours = 3
        middays = 1

        if sliceCred is None:
            if urn is None or urn == '':
                return ""
            sliceCred = self._get_slice_cred(urn)
        if sliceCred is None:
            # failed to get a slice string. Can't check
            return ""

        sliceexp = self._get_slice_exp(sliceCred)
        now = datetime.datetime.utcnow()
        if sliceexp <= now:
            retVal = 'Slice %s has expired at %s UTC' % (urn, sliceexp)
            self.logger.info('Slice %s has expired at %s UTC' % (urn, sliceexp))
        elif sliceexp - datetime.timedelta(hours=shorthours) <= now:
            retVal = 'Slice %s expires in <= %d hours' % (urn, shorthours)
            self.logger.info('Slice %s expires in <= %d hours' % (urn, shorthours))
            self.logger.debug('Slice %s expires on %s UTC' % (urn, sliceexp))
            self.logger.debug('It is now %s UTC' % (datetime.datetime.utcnow()))
        elif sliceexp - datetime.timedelta(days=middays) <= now:
            retVal = 'Slice %s expires within %d day' % (urn, middays)
            self.logger.info('Slice %s expires within %d day' % (urn, middays))
        else:
            retVal = 'Slice %s expires on %s UTC' % (urn, sliceexp)
            self.logger.debug('Slice %s expires on %s UTC' % (urn, sliceexp))
        return retVal

    def _get_slice_exp(self, credString):
        # Don't fully parse credential: grab the slice expiration from the string directly
        sliceexp = 0

        if credString is None:
            # failed to get a slice string. Can't check
            return sliceexp

        try:
            doc = md.parseString(credString)
            signed_cred = doc.getElementsByTagName("signed-credential")

            # Is this a signed-cred or just a cred?
            if len(signed_cred) > 0:
                cred = signed_cred[0].getElementsByTagName("credential")[0]
            else:
                cred = doc.getElementsByTagName("credential")[0]
            expirnode = cred.getElementsByTagName("expires")[0]
            if len(expirnode.childNodes) > 0:
                sliceexp = dateutil.parser.parse(expirnode.childNodes[0].nodeValue)
        except Exception, exc:
            self.logger.error("Failed to parse credential for expiration time: %s", exc)
            self.logger.debug(traceback.format_exc())

        return sliceexp


    def _get_slice_cred(self, urn):
        '''Try a couple times to get the given slice credential.
        Retry on wrong pass phrase.'''

        return _do_ssl(self.framework, None, "Get Slice Cred for slice %s" % urn, self.framework.get_slice_cred, urn)

    def listaggregates(self, args):
        """Print the aggregates federated with the control framework."""
        retStr = ""
        retVal = {}
        aggList = self._listaggregates().items()
        self.logger.info("Listing %d aggregates..."%len(aggList))
        aggCnt = 0
        for (urn, url) in aggList:
            aggCnt += 1
            self.logger.info( "  Aggregate %d:\n \t%s \n \t%s" % (aggCnt, urn, url) )
#            retStr += "%s: %s\n" % (urn, url)
            retVal[urn] = url
        if len(aggList)==0:
            retStr = "No aggregates found."
        else:
            retStr = "Found %d aggregates." % len(aggList)
        return retStr, retVal 

    def renewslice(self, args):
        """Renew the slice at the clearinghouse so that the slivers can be
        renewed.
        """
        if len(args) != 2 or args[0] == None or args[0].strip() == "":
            self._raise_omni_error('renewslice <slice name> <expiration date>')
        name = args[0]
        expire_str = args[1]
        # convert the slice name to a framework urn
        # FIXME: catch errors getting slice URN to give prettier error msg?
        urn = self.framework.slice_name_to_urn(name)
        # convert the desired expiration to a python datetime
        try:
            in_expiration = dateutil.parser.parse(expire_str)
        except:
            msg = 'Unable to parse date "%s".\nTry "YYYYMMDDTHH:MM:SSZ" format'
            msg = msg % (expire_str)
            self._raise_omni_error(msg)

        # Try to renew the slice
        out_expiration = _do_ssl(self.framework, None, "Renew Slice %s" % urn, self.framework.renew_slice, urn, in_expiration)

        if out_expiration:
            prtStr = "Slice %s now expires at %s UTC" % (name, out_expiration)
            self.logger.info( prtStr )
            retVal = prtStr+"\n"
            retTime = out_expiration
        else:
            prtStr = "Failed to renew slice %s" % (name)
            self.logger.warn( prtStr )
            retVal = prtStr+"\n"
            retTime = None
        retVal +=self._print_slice_expiration(urn)
        return retVal, retTime

def parse_args(argv):
    parser = optparse.OptionParser()
    parser.add_option("-c", "--configfile", 
                      help="config file name", metavar="FILE")
    parser.add_option("-f", "--framework", default="",
                      help="control framework to use for creation/deletion of slices")
    parser.add_option("-n", "--native", default=False, action="store_true",
                      help="use native RSpecs")
    parser.add_option("-a", "--aggregate", metavar="AGGREGATE_URL",
                      help="communicate with a specific aggregate")
    parser.add_option("--debug", action="store_true", default=False,
                       help="enable debugging output")
    parser.add_option("--no-ssl", dest="ssl", action="store_false",
                      default=True, help="do not use ssl")
    parser.add_option("--orca-slice-id",
                      help="use the given orca slice id")
    # Also need an option for filename prefix
    parser.add_option("-o", "--output",  default=False, action="store_true",
                      help="write output of listresources to a file")
    return parser.parse_args(argv)

def configure_logging(opts):
    level = logging.INFO
    logging.basicConfig(level=level)
    if opts.debug:
        level = logging.DEBUG
    logger = logging.getLogger("omni")
    logger.setLevel(level)
    return logger

def load_config(opts, logger):
    # Load up the config file
    configfiles = ['omni_config','~/.gcf/omni_config']

    if opts.configfile:
        # if configfile defined on commandline does not exist, fail
        if os.path.exists( opts.configfile ):
            configfiles.insert(0, opts.configfile)
        else:
            # Check maybe the default directory for the file
            configfile = os.path.join( '~/.gcf', opts.configfile )
            configfile = os.path.expanduser( configfile )
            if os.path.exists( configfile ):
                configfiles.insert(0, configfile)
            else:
                logger.error("Config file '%s'or '%s' does not exist"
                     % (opts.configfile, configfile))
                raise (OmniError, "Config file '%s'or '%s' does not exist"
                     % (opts.configfile, configfile))

    # Find the first valid config file
    for cf in configfiles:         
        filename = os.path.expanduser(cf)
        if os.path.exists(filename):
            break
    
    # Did we find a valid config file?
    if not os.path.exists(filename):
        prtStr = """ Could not find an omni configuration file in local directory or in ~/.gcf/omni_config
                     An example config file can be found in the source tarball or in /etc/omni/templates/"""
        logger.error( prtStr )
        raise OmniError, prtStr

    logger.info("Loading config file %s", filename)
    
    confparser = ConfigParser.RawConfigParser()
    try:
        confparser.read(filename)
    except ConfigParser.Error as exc:
        logger.error("Config file %s could not be parsed: %s"% (filename, str(exc)))
        raise OmniError, "Config file %s could not be parsed: %s"% (filename, str(exc))

    # Load up the omni options
    config = {}
    config['logger'] = logger
    config['omni'] = {}
    for (key,val) in confparser.items('omni'):
        config['omni'][key] = val
        
    # Load up the users the user wants us to see        
    config['users'] = []
    if 'users' in config['omni']:
        for user in config['omni']['users'].split(','):
            d = {}
            for (key,val) in confparser.items(user.strip()):
                d[key] = val
            config['users'].append(d)

    # Load up the framework section
    if not opts.framework:
        opts.framework = config['omni']['default_cf']

    logger.info("Using control framework %s" % opts.framework)

    # Find the control framework
    cf = opts.framework.strip()
    if not confparser.has_section(cf):
        logger.error( 'Missing framework %s in configuration file' % cf )
        raise OmniError, 'Missing framework %s in configuration file' % cf
    
    # Copy the control framework into a dictionary
    config['selected_framework'] = {}
    for (key,val) in confparser.items(cf):
        config['selected_framework'][key] = val
    
    return config

def load_framework(config):
    cf_type = config['selected_framework']['type']

    framework_mod = __import__('omnilib.frameworks.framework_%s' % cf_type, fromlist=['omnilib.frameworks'])
    config['selected_framework']['logger'] = config['logger']
    framework = framework_mod.Framework(config['selected_framework'])
    return framework    

def make_client(url, framework, opts):
    if opts.ssl:
        return omnilib.xmlrpc.client.make_client(url,
                                                 framework.key,
                                                 framework.cert)
    else:
        return omnilib.xmlrpc.client.make_client(url, None, None)



def initialize( argv ):
    opts, args = parse_args(argv)    
    logger = configure_logging(opts)
    config = load_config(opts, logger)        
    framework = load_framework(config)
    return framework, config, args, opts

def API_call( framework, config, args, opts, verbose=False ):
    """Call the function and print the summary.
    """
    # Process the user's call
    handler = CallHandler(framework, config, opts)    
#    Returns string, item
    result = handler._handle(args)

    if result is None:
        retVal = None
        retItem = None
    elif len(result)==2:
        retVal, retItem = result
    else:
        retVal = result
        retItem = None

    # Print the summary of the command result
    if verbose:
        s = "Command '" + str(" ".join(sys.argv)) + "' Returned"
        headerLen = (70 - (len(s) + 2)) / 4
        header = "- "*headerLen+" "+s+" "+"- "*headerLen

        logger = config['logger']
        logger.critical( "-"*70 )
        logger.critical( header )
        # printed not logged so can redirect output to a file
        print retVal
        logger.critical( "="*70 )
    
    return retVal, retItem

def call( cmd, opts, verbose=False ):
    """method to use when calling omni as a library

    Can call like this:
      import omni 
      args = [slicename]
      text, dict = omni.call('listresources', args)
    This is equivalent to: ./omni.py listresources slicename
      """
    # create argv containing cmds and options
    argv = [str(cmd)]
    argv.extend(opts) 
    
    # do initial setup 
    framework, config, args, opts = initialize(argv)
    # process the user's call
    result = API_call( framework, config, args, opts, verbose=verbose )
    return result

class OmniError( Exception ):
    pass

def main(argv=None):
    # do initial setup & process the user's call
    try:
        framework, config, args, opts = initialize(sys.argv[1:])
        retVal = API_call(framework, config, args, opts, verbose=True)
    except OmniError, exc:
        sys.exit()
#        sys.exit("ERROR: "+str(exc))

        
if __name__ == "__main__":
    sys.exit(main())
