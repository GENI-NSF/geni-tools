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
    omni.py -f sfa listresources > sfa-resources.rspec

    
    The currently supported control frameworks are SFA, PG and GCF.

    Extending Omni to support additional types of Aggregate Managers
    with different RSpec formats requires adding a new omnispec/rspec
    conversion file.

    Extending Omni to support additional frameworks with their own
    clearinghouse APIs requires adding a new Framework extension class.

    Return Values of various omni commands:
       [string dictionary] = omni.py getversion
       [string xmldoc] = omni.py listresources -n
       [string dictionary] = omni.py listresources
       On success: [string sliceurnstring] = omni.py createslice SLICENAME
       On fail: [string None] = omni.py createslice SLICENAME
       [string successFailBoolean] = omni.py createsliver SLICENAME RSPEC_FILENAME
       [string successFailBoolean] = omni.py deletesliver SLICENAME
       [string successFailBoolean] = omni.py deleteslice SLICENAME
       On success: [string dateTimeRenewedTo] = omni.py renewslice SLICENAME
       On fail: [string None] = omni.py renewslice SLICENAME
       On success: [string dateTimeRenewedTo] = omni.py renewsliver SLICENAME
       On fail: [string None] = omni.py renewsliver SLICENAME
       [string listOfSliceNames] = omni.py listmyslices USER
    
"""

import datetime
from copy import copy
import json
import logging
import optparse
import os
import pprint
import ssl
import sys
import traceback
import xml.dom.minidom as md
import xmlrpclib
import zlib
import ConfigParser

import dateutil.parser
from omnilib.omnispec.translation import rspec_to_omnispec, omnispec_to_rspec
from omnilib.omnispec.omnispec import OmniSpec
from omnilib.util.faultPrinting import cln_xmlrpclib_fault
import omnilib.xmlrpc.client

import sfa.trust.credential as cred
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
        

    def _handle(self, args):
        if len(args) == 0:
            sys.exit('Insufficient number of arguments - Missing command to run')
        
        call = args[0].lower()
        if call.startswith('_'):
            return
        if not hasattr(self,call):
            sys.exit('Unknown function: %s' % call)
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
            aggs =  self._do_ssl("List Aggregates from control framework", self.framework.list_aggregates)
            if aggs is  None:
                return {}
            return aggs


    def listmyslices(self, args):
        """Provides a list of slices of user provided as first argument """
        if len(args) > 0:
            username = args[0].strip()
        else:
            sys.exit('listmyslices requires 1 arg: user')

        retStr = ""
        slices=None
        slices = self._listmyslices( username )
        if slices is None:
            slices = []
        elif len(slices) > 0:
            retStr += "User '%s' has slices: \n\t%s"%(username,"\n\t".join(slices))
        else:
            retStr += "User '%s' has NO slices.\n"%username

        return retStr, slices


    def _listmyslices( self, username ):
        slices =  self._do_ssl("List Slices from Slice Authority", self.framework.list_my_slices, username)
        return slices

    def listresources(self, args):
        '''Optional arg is a slice name limiting results. Call ListResources
        on all aggregates and prints the omnispec/rspec to stdout.'''
        rspecs = {}
        options = {}

        options['geni_compressed'] = False;
        
        # check command line args
        if self.opts.native and not self.opts.aggregate:
            # If native is requested, the user must supply an aggregate.
            msg = 'Specifying a native RSpec requires specifying an aggregate.'
            # Calling exit here is a bit of a hammer.
            # Maybe there's a gentler way.
            sys.exit(msg)

        # An optional slice name might be specified.
        slicename = None
        if len(args) > 0:
            slicename = args[0].strip()

        # Get the credential for this query
        if slicename is None or slicename == "":
            cred = None
            cred = self._do_ssl("Get User Credential from control framework", self.framework.get_user_cred)

            if cred is None:
                sys.exit('Cannot list resources: no user credential')

        else:
            urn = self.framework.slice_name_to_urn(slicename)
            cred = self._get_slice_cred(urn)
            if cred is None:
                sys.exit('Cannot list resources for slice %s: No slice credential'
                         % (urn))
            self.logger.info('Gathering resources reserved for slice %s..' % slicename)

            options['geni_slice_urn'] = urn

        
        # Connect to each available GENI AM to list their resources
        for client in self._getclients():
            if cred is None:
                self.logger.debug("Have null credential in call to ListResources!")
            self.logger.debug("Connecting to AM: %s at %s", client.urn, client.url)
            rspec = None
            self.logger.debug("Doing listresources with options %r", options)
            rspec = self._do_ssl(("List Resources at %s" % (client.url)), client.ListResources, [cred], options)

            if not rspec is None:
                if options.get('geni_compressed', False):
                    rspec = zlib.decompress(rspec.decode('base64'))
                rspecs[(client.urn, client.url)] = rspec

        if self.opts.native:
            # If native, return the one native rspec. There is only
            # one because we checked for that at the beginning.
            if slicename != None:
                self.logger.info('Resources at %s for slice %s:' % (self.opts.aggregate, slicename))
            else:
                self.logger.info('Resources at %s:' % (self.opts.aggregate))
            if rspecs and rspecs != {}:
                rspec = rspecs.values()[0]
                try:
                    newl = ''
                    if '\n' not in rspec:
                        newl = '\n'
                    return md.parseString(rspec).toprettyxml(indent=' '*2, newl=newl), rspec
                except:
                    return rspec, rspec
            else:
                self.logger.info('No resources available')
        else:
            # Convert the rspecs to omnispecs
            omnispecs = {}
            for ((urn,url), rspec) in rspecs.items():                        
                self.logger.debug("Getting RSpec items for urn %s (%s)", urn, url)
                # Throws exception if unparsable
                # No catch means 1 bad Agg and we lose all ospecs
                try:
                    omnispecs[url] = rspec_to_omnispec(urn,rspec)
                except Exception, e:
                    self.logger.error("Failed to parse RSpec from AM %s (%s): %s", urn, url, e)

            if omnispecs and omnispecs != {}:
                jspecs = json.dumps(omnispecs, indent=4)
                self.logger.info('Full resource listing:')
                # jspecs is a string, omnispecs is a dictionary
                return jspecs, omnispecs
            else:
                if rspecs and rspecs != {}:
                    self.logger.info('No parsable resources available.')
                    #print 'Unparsable responses:'
                    #pprint.pprint(rspecs)
                else:
                    self.logger.info('No resources available')
            
    def _ospec_to_rspecs(self, specfile):
        """Convert the given omnispec file into a dict of url => rspec."""
        jspecs = {}

        try:
            jspecs = json.loads(file(specfile,'r').read())
#            jspecs = json.loads(open(specfile,mode='r').read())
        except Exception, exc:
            sys.exit("Parse error reading omnispec %s: %s" % (specfile, exc))

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
            sys.exit('createsliver requires 2 args: slicename and omnispec filename')

        # check command line args
        if self.opts.native and not self.opts.aggregate:
            # If native is requested, the user must supply an aggregate.
            msg = 'Specifying a native RSpec requires specifying an aggregate.'
            # Calling exit here is a bit of a hammer.
            # Maybe there's a gentler way.
            sys.exit(msg)

        name = args[0]
        # FIXME: catch errors getting slice URN to give prettier error msg?
        urn = self.framework.slice_name_to_urn(name.strip())
        slice_cred = self._get_slice_cred(urn)
        if slice_cred is None:
            sys.exit('Cannot create sliver %s: No slice credential'
                     % (urn))

        retVal += self._print_slice_expiration(urn)

        # Load up the user's edited omnispec
        specfile = args[1]
        if specfile is None or not os.path.isfile(specfile):
            sys.exit('File of resources to request missing: %s' % specfile)

        rspecs = None
        if self.opts.native:
            # read the native rspec into a string, and add it to the rspecs dict
            rspecs = {}
            try:
                rspec = file(specfile).read()
                rspecs[self.opts.aggregate] = rspec
            except Exception, exc:
                sys.exit('Unable to read rspec file %s: %s'
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

            try:
                for key in user['keys'].split(','):        
                    newkeys.append(file(os.path.expanduser(key.strip())).read())
            except Exception, exc:
                self.logger.warn("Failed to read user key from %s: %s" %(user['keys'], exc))
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

#                self.logger.warning("""You're creating a sliver in an AM (%s) that is either not listed by
#                your Clearinghouse or it is not in the optionally provided list of aggregates in
#                your configuration file.  By creating this sliver, you will be unable to check its
#                status or delete it.""" % (url))
                
                res = raw_input("Would you like to continue? (y/N) ")
                if not res.lower().startswith('y'):
                    return
                
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
            result = self._do_ssl(("Create Sliver %s at %s" % (urn, url)), client.CreateSliver, urn, [slice_cred], rspec, slice_users)

            if result != None and isinstance(result, str) and (result.startswith('<rspec') or result.startswith('<resv_rspec')):
                try:
                    newl = ''
                    if '\n' not in result:
                        newl = '\n'
                    retVal = 'Asked %s to reserve resources. Result:\n%s' % (url, md.parseString(result).toprettyxml(indent=' '*2, newl=newl))
                except:
                    retVal = 'Asked %s to reserve resources. Result: %s' % (url, result)
            else:
                retVal = 'Asked %s to reserve resources. Result: %s' % (url, result)

            if '<RSpec type="SFA">' in rspec:
                # Figure out the login name
                self.logger.info("Please run the omni sliverstatus call on your slice to determine your login name to PL resources")
        return retVal, result

    def deletesliver(self, args):
        if len(args) == 0 or args[0] == None or args[0].strip() == "":
            sys.exit('deletesliver requires arg of slice name')

        name = args[0]

        # FIXME: catch errors getting slice URN to give prettier error msg?
        urn = self.framework.slice_name_to_urn(name)
        slice_cred = self._get_slice_cred(urn)
        if slice_cred is None:
            sys.exit('Cannot delete sliver %s: No slice credential'
                     % (urn))

        if self.opts.orca_slice_id:
            self.logger.info('Using ORCA slice id %r', self.opts.orca_slice_id)
            urn = self.opts.orca_slice_id
        # Connect to each available GENI AM 
        for client in self._getclients():
            if self._do_ssl(("Delete Sliver %s on %s" % (urn, client.url)), client.DeleteSliver, urn, [slice_cred]):
                return "Deleted sliver %s on %s at %s" % (urn, client.urn, client.url), True
            else:
                return "Failed to delete sliver %s on %s at %s" % (urn, client.urn, client.url), False
            
    def renewsliver(self, args):
        if len(args) < 2 or args[0] == None or args[0].strip() == "":
            sys.exit('renewsliver requires arg of slice name and new expiration time in UTC')

        name = args[0]

        # FIXME: catch errors getting slice URN to give prettier error msg?
        urn = self.framework.slice_name_to_urn(name)
        slice_cred = self._get_slice_cred(urn)
        if slice_cred is None:
            sys.exit('Cannot renew sliver %s: No slice credential'
                     % (urn))

        time = None
        try:
            time = dateutil.parser.parse(args[1])
        except Exception, exc:
            sys.exit('renewsliver couldnt parse new expiration time from %s: %r' % (args[1], exc))


        retVal = ''
        slicecred_obj = cred.Credential(string=slice_cred)
        retVal += self._print_slice_expiration(urn, slice_cred)
        if time > slicecred_obj.expiration:
            sys.exit('Cannot renew sliver %s until %s which is after slice expiration time %s' % (urn, time, slicecred_obj.expiration))
        elif time <= datetime.datetime.utcnow():
            self.logger.info('Sliver %s will be set to expire now' % urn)
        else:
            self.logger.debug('Slice expires at %s after requested time %s' % (slicecred_obj.expiration, time))

#        print 'Renewing Sliver %s until %s' % (urn, time)
        retVal += 'Renewing Sliver %s until %r\n' % (urn, time)

        if self.opts.orca_slice_id:
            self.logger.info('Using ORCA slice id %r', self.opts.orca_slice_id)
            urn = self.opts.orca_slice_id
        for client in self._getclients():
            # Note that the time arg includes UTC offset as needed
            res = self._do_ssl(("Renew Sliver %s on %s" % (urn, client.url)), client.RenewSliver, urn, [slice_cred], time.isoformat())
            if not res:
                retVal += "Failed to renew sliver %s on %s (%s)" % (urn, client.urn, client.url)
                retTime = None
            else:
                retVal += "Renewed sliver %s at %s (%s) until %s\n" % (urn, client.urn, client.url, time.isoformat())
                retTime = time.isoformat()
        return retVal, retTime

    def sliverstatus(self, args):
        if len(args) == 0 or args[0] == None or args[0].strip() == "":
            sys.exit('sliverstatus requires arg of slice name')

        name = args[0]

        # FIXME: catch errors getting slice URN to give prettier error msg?
        urn = self.framework.slice_name_to_urn(name)
        slice_cred = self._get_slice_cred(urn)
        if slice_cred is None:
            sys.exit('Cannot get sliver status for %s: No slice credential'
                     % (urn))

        if self.opts.orca_slice_id:
            self.logger.info('Using ORCA slice id %r', self.opts.orca_slice_id)
            urn = self.opts.orca_slice_id

        retVal = 'Status of Slice %s:' % urn
        retItem = False
        for client in self._getclients():
            status = self._do_ssl("Sliver status of %s at %s" % (urn, client.url), client.SliverStatus, urn, [slice_cred])
            if status:
                retVal += "Sliver at %s:" % (client.url)
                retVal += pprint.pformat(status)
                retItem = status
            else:
                retItem = False
# FIX ME: Check that status is the right thing to return here
        return retVal, retItem
                
    def shutdown(self, args):
        if len(args) == 0 or args[0] == None or args[0].strip() == "":
            sys.exit('shutdown requires arg of slice name')

        name = args[0]

        # FIXME: catch errors getting slice URN to give prettier error msg?
        urn = self.framework.slice_name_to_urn(name)
        slice_cred = self._get_slice_cred(urn)
        if slice_cred is None:
            sys.exit('Cannot shutdown slice %s: No slice credential'
                     % (urn))
        if self.opts.orca_slice_id:
            self.logger.info('Using ORCA slice id %r', self.opts.orca_slice_id)
            urn = self.opts.orca_slice_id

        retVal = ""

        for client in self._getclients():
            if self._do_ssl("Shutdown %s on %s" % (urn, client.url), client.Shutdown, urn, [slice_cred]):
                retVal += "Shutdown Sliver %s at %s on %s\n" % (urn, client.urn, client.url)
            else:
                self.logger.warn( "Failed to shutdown sliver %s on AM %s at %s" % (urn, client.urn, client.url) )
    
                retVal += "Failed to shutdown sliver %s on AM %s at %s" % (urn, client.urn, client.url)
        return retVal
    def _do_ssl(self, reason, fn, *args):
        """ Attempts to make an xmlrpc call, and will repeat the attempt
        if it failed due to a bad passphrase for the ssl key.  Also does some
        exception handling.  Returns the xmlrpc return if everything went okay, 
        otherwise returns None."""
        
        # Change exception name?
        max_attempts = 2
        attempt = 0
        
        failMsg = "Call for %s failed." % reason
        while(attempt < max_attempts):
            attempt += 1
            try:
                result = fn(*args)
                return result
            except ssl.SSLError, exc:
                if exc.errno == 336265225:
                    self.logger.debug("Doing %s got %s", reason, exc)
                    self.logger.error('Wrong pass phrase for private key.')
                    if attempt < max_attempts:
                        self.logger.info('.... please retry.')
                    else:
                        self.logger.error("Wrong pass phrase after %d tries" % max_attempts)
                elif exc.errno == 1 and exc.strerror.find("error:14094418") > -1:
                    # Handle SSLError: [Errno 1] _ssl.c:480: error:14094418:SSL routines:SSL3_READ_BYTES:tlsv1 alert unknown ca
                    import sfa.trust.gid as gid
                    certiss = ''
                    certsubj = ''
                    try:
                        certObj = gid.GID(filename=self.framework.cert)
                        certiss = certObj.get_issuer()
                        certsubj = certObj.get_urn()
                    except:
                        pass
                    self.logger.error("Server does not trust the CA (%s) that signed your (%s) user certificate! Use an account at another clearinghouse or find another server. Can't do %s.", certiss, certsubj, reason)
                    if not self.logger.isEnabledFor(logging.DEBUG):
                        self.logger.error('    ..... Run with --debug for more information')
                    self.logger.debug(traceback.format_exc())
                    return None
                else:
                    self.logger.error("%s: Unknown SSL error %s" % (failMsg, exc))
                    if not self.logger.isEnabledFor(logging.DEBUG):
                        self.logger.error('    ..... Run with --debug for more information')
                    self.logger.debug(traceback.format_exc())

                    return None
            except xmlrpclib.Fault, fault:
                self.logger.error("%s Server says: %s" % (failMsg, cln_xmlrpclib_fault(fault)))
                return None

            except NotImplementedError, exc:
                self.logger.error("%s: %s" % (failMsg, exc))
                self.logger.error("Command NOT IMPLEMENTED on this control framework.")
                self.logger.debug(traceback.format_exc())
                return None                

            except Exception, exc:
                self.logger.error("%s: %s" % (failMsg, exc))
                if not self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.error('    ..... Run with --debug for more information')
                self.logger.debug(traceback.format_exc())
                return None

    def getversion(self, args):
        retVal = ""
        version = None
        for client in self._getclients():
            version = self._do_ssl("GetVersion at %s" % (str(client.url)), client.GetVersion)
            if not version is None:
                pp = pprint.PrettyPrinter(indent=4)
                retVal += "urn: %s (url: %s) has version: \n\t%s\n\n" % (client.urn, client.url, pp.pformat(version))
        return (retVal, version)
            

    def createslice(self, args):
        retVal = ""
        if len(args) == 0 or args[0] == None or args[0].strip() == "":
            sys.exit('createslice requires arg of slice name')

        name = args[0]

        # FIXME: catch errors getting slice URN to give prettier error msg?
        urn = self.framework.slice_name_to_urn(name)
        
        slice_cred = self._do_ssl("Create Slice %s" % urn, self.framework.create_slice, urn)
        if slice_cred:
            retVal += "Created slice with Name %s, URN %s" % (name, urn)
            success = urn
        else:
            retVal += "Create Slice Failed for slice name %s." % (name)
            success = None
            if not self.logger.isEnabledFor(logging.DEBUG):
                retVal += "   Try re-running with --debug for more information."
        return retVal, success
        
    def deleteslice(self, args):
        if len(args) == 0 or args[0] == None or args[0].strip() == "":
            sys.exit('deleteslice requires arg of slice name')

        name = args[0]

        # FIXME: catch errors getting slice URN to give prettier error msg?
        urn = self.framework.slice_name_to_urn(name)

        res = self._do_ssl("Delete Slice %s" % urn, self.framework.delete_slice, urn)
        # return True if successfully deleted slice, else False
        if res is None:
            retVal = False
        else:
            retVal = True
        return "Delete Slice %s result: %r" % (name, res), retVal


    def getslicecred(self, args):
        if len(args) == 0 or args[0] == None or args[0].strip() == "":
            sys.exit('getslicecred requires arg of slice name')

        name = args[0]

        # FIXME: catch errors getting slice URN to give prettier error msg?
        urn = self.framework.slice_name_to_urn(name)
        cred = self._get_slice_cred(urn)

        print self._print_slice_expiration(urn)

        # FIXME: Print the non slice cred bit to STDERR so
        # capturing just stdout givs just the cred?
        print "Slice cred for %s: %s" % (urn, cred)
        self.logger.info( "Slice cred for %s: %s" % (urn, cred))
        
    def _print_slice_expiration(self, urn, string=None):
        '''Check when the slice expires and print out to STDOUT'''
        # FIXME: push this to config?
        shorthours = 3
        middays = 1

        if string is None:
            if urn is None or urn == '':
                return
            string = self._get_slice_cred(urn)
        if string is None:
            # failed to get a slice string. Can't check
            return

        slicecred_obj = cred.Credential(string=string)
        sliceexp = slicecred_obj.expiration
        now = datetime.datetime.utcnow()
        if sliceexp <= now:
            retVal = 'Slice %s has expired at %s' % (urn, sliceexp)
        elif sliceexp - datetime.timedelta(hours=shorthours) <= now:
            retVal = 'Slice %s expires in <= %d hours' % (urn, shorthours)
            self.logger.debug('Slice %s expires on %s' % (urn, sliceexp))
            self.logger.debug('It is now %s' % (datetime.datetime.now()))
        elif sliceexp - datetime.timedelta(days=middays) <= now:
            retVal = 'Slice %s expires within %d day' % (urn, middays)
        else:
            self.logger.debug('Slice %s expires on %s' % (urn, sliceexp))
        return retVal
    def _get_slice_cred(self, urn):
        '''Try a couple times to get the given slice credential.
        Retry on wrong pass phrase.'''

        return self._do_ssl("Get Slice Cred %s" % urn, self.framework.get_slice_cred, urn)

    def listaggregates(self, args):
        """Print the aggregates federated with the control framework."""
        retStr = ""
        retVal = {}
        for (urn, url) in self._listaggregates().items():
            retStr += "%s: %s" % (urn, url)
            retVal[urn] = url
        return retStr, retVal 

    def renewslice(self, args):
        """Renew the slice at the clearinghouse so that the slivers can be
        renewed.
        """
        if len(args) != 2 or args[0] == None or args[0].strip() == "":
            sys.exit('renewslice <slice name> <expiration date>')
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
            sys.exit(msg)

        # Try to renew the slice
        out_expiration = self._do_ssl("Renew Slice %s" % urn, self.framework.renew_slice, urn, in_expiration)

        if out_expiration:
            retVal = "Slice %s now expires at %s" % (name, out_expiration)
            retTime = out_expiration
        else:
            retVal = "Failed to renew slice %s" % (name)
            retTime = None
        retVal += self._print_slice_expiration(urn)
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
                sys.exit("Config file '%s'or '%s' does not exist"
                     % (opts.configfile, configfile))

    # Find the first valid config file
    for cf in configfiles:         
        filename = os.path.expanduser(cf)
        if os.path.exists(filename):
            break
    
    # Did we find a valid config file?
    if not os.path.exists(filename):
        sys.exit(""" Could not find an omni configuration file in local directory or in ~/.gcf/omni_config
                     An example config file can be found in the source tarball or in /etc/omni/templates/""")            

    logger.info("Loading config file %s", filename)
    
    confparser = ConfigParser.RawConfigParser()
    try:
        confparser.read(filename)
    except ConfigParser.Error as exc:
        sys.exit("Config file %s could not be parsed: %s"
                 % (filename, str(exc)))

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
        sys.exit('Missing framework %s in configuration file' % cf)
    
    # Copy the control framework into a dictionary
    config['selected_framework'] = {}
    for (key,val) in confparser.items(cf):
        config['selected_framework'][key] = val
    
    return config

def load_framework(config):
    cf_type = config['selected_framework']['type']

    framework_mod = __import__('omnilib.frameworks.framework_%s' % cf_type, fromlist=['omnilib.frameworks'])
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
    # Print the output
    if verbose:
        print_opts = ""
        if opts.framework is not config['omni']['default_cf']:
            print_opts += " -%s %s"%('f', str(opts.framework))
        if opts.debug is True:
            print_opts += " --%s %s"%('debug', str(opts.debug))
        if opts.ssl is False:
            print_opts += " --no-ssl"
        if opts.aggregate is not None:
            print_opts += " -%s %s"%('a', str(opts.aggregate))
        if opts.native is not False:
            print_opts += " -%s %s"%('n', str(opts.native))
        if (opts.configfile is not None):
            print_opts += " -%s %s"%('c', str(opts.configfile))
        print_opts += " "

        s = "Command 'omni.py"+print_opts+" ".join(args) + "' Returned"
        headerLen = (80 - (len(s) + 2)) / 4
        header = "- "*headerLen+" "+s+" "+"- "*headerLen
        print "-"*80
        print header
        print retVal
        print "="*80
    
    return retVal, retItem

def call( cmd, opts, verbose=False ):
    # create argv containing cmds and options
    argv = [str(cmd)]
    argv.extend(opts) 
    
    # do initial setup 
    framework, config, args, opts = initialize(argv)
    # process the user's call
    result = API_call( framework, config, args, opts, verbose=verbose )
    return result

def main(argv=None):
    # do initial setup & process the user's call
    framework, config, args, opts = initialize(sys.argv[1:])
    retVal = API_call(framework, config, args, opts, verbose=True)
#    if retVal is not None:
#        print retVal[0]
        
if __name__ == "__main__":
    sys.exit(main())
