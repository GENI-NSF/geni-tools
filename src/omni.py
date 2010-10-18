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
"""

from copy import copy
import json
import logging
import optparse
import os
import pprint
import ssl
import sys
import traceback
import xmlrpclib
import zlib
import ConfigParser

import dateutil.parser
from omnilib.xmlrpc.client import make_client
from omnilib.omnispec.translation import rspec_to_omnispec, omnispec_to_rspec
from omnilib.omnispec.omnispec import OmniSpec

OMNI_CONFIG_TEMPLATE='/etc/omni/templates/omni_config'

class InvalidSSLPasswordException(Exception):
    pass

def getAbsPath(path):
    """Return None or a normalized absolute path version of the argument string.
    Does not check that the path exists."""
    if path is None:
        return None
    if path.strip() == "":
        return None
    path = os.path.normcase(os.path.expanduser(path))
    if os.path.isabs(path):
        return path
    else:
        return os.path.abspath(path)

class CallHandler(object):
    """Handle calls on the framework. Valid calls are all
    methods without an underscore: getversion, createslice, deleteslice, 
    getslicecred, listresources, createsliver, deletesliver,
    renewsliver, sliverstatus, shutdown
    """

    def __init__(self, framework, config, opts):
        self.framework = framework
        self.logger = config['logger']
        self.frame_config = config['selected_framework']
        self.omni_config = config['omni']
        self.config = config
        self.opts = opts
        
        self.frame_config['cert'] = getAbsPath(self.frame_config['cert'])
        if not os.path.exists(self.frame_config['cert']):
            sys.exit("Frameworks certfile %s doesn't exist" % self.frame_config['cert'])

        self.frame_config['key'] = getAbsPath(self.frame_config['key'])
        if not os.path.exists(self.frame_config['key']):
            sys.exit("Frameworks keyfile %s doesn't exist" % self.frame_config['key'])

    def _handle(self, args):
        if len(args) == 0:
            sys.exit('Insufficient number of arguments - Missing command to run')
        
        call = args[0].lower()
        if call.startswith('_'):
            return
        if not hasattr(self,call):
            sys.exit('Unknown function: %s' % call)
        getattr(self,call)(args[1:])

    def _getclients(self, ams=None):
        """Create XML-RPC clients for each aggregate and return them
        as a sequence.
        """
        clients = []
        for (urn, url) in self._listaggregates().items():
            client = make_client(url, self.frame_config['key'],
                                 self.frame_config['cert'])
            client.urn = urn
            client.url = url
            clients.append(client)
        if clients == []:
            print 'No aggregates found'
        return clients
        
    def _listaggregates(self):
        """List the aggregates that can be used for the current operation.
        If an aggregate was specified on the command line, use only that one.
        Else if aggregates are specified in the config file, use that set.
        Else ask the framework for the list of aggregates.
        Returns the aggregates as a dict of urn => url pairs.
        """
        if self.opts.aggregate:
            # No URN is specified, so put in 'unknown'
            return dict(unspecified_AM_URN=self.opts.aggregate)
        elif not self.omni_config.get('aggregates', '').strip() == '':
            aggs = {}
            for url in self.omni_config['aggregates'].strip().split(','):
                aggs[url] = url
            return aggs                
        else:
            try:
                return self._do_ssl("List Aggregates", self.framework.list_aggregates)
            except InvalidSSLPasswordException, exc:
                self.logger.error("Failed to list aggregates")
            except Exception, exc:
                self.logger.error("Failed to list aggregates: %s", exc)
                if not self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.error('    ..... Run with --debug for more information')
                self.logger.debug(traceback.format_exc())
            return {}
            

    def listresources(self, args):
        '''Optional arg is a slice name limiting results. Call ListResources
        on all aggregates and prints the omnispec/rspec to stdout.'''
        rspecs = {}
        options = {}

        options['geni_compressed'] = True;
        
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
            try:
                cred = self._do_ssl("Get User Credential", self.framework.get_user_cred)
            except InvalidSSLPasswordException, exc:
                self.logger.error("Failed to list resources")
                sys.exit()
            except Exception, exc:
                self.logger.error("Failed to list resources: can't get valid user credential: %s", exc)
                if not self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.error('    ..... Run with --debug for more information')
                self.logger.debug(traceback.format_exc())
                sys.exit()

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
            try:
                rspec = self._do_ssl(("List Resources at %s" % (client.url)), client.ListResources, [cred], options)
            except InvalidSSLPasswordException, exc:
                self.logger.error("Failed to list resources from %s (%s)", client.urn, client.url)
            except xmlrpclib.Fault, fault:
                # FIXME: string replace literal \n with actual \n
                self.logger.error('Failed to list resources from %s (%s): %s',
                                  client.urn, client.url, str(fault))
            except Exception, exc:
                self.logger.error("Failed to list resources from %s (%s): %s", client.urn, client.url, exc)
                if not self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.error('    ..... Run with --debug for more information')
                self.logger.debug(traceback.format_exc())

            if rspec != None:
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
                    import xml.dom.minidom as md
                    newl = ''
                    if '\n' not in rspec:
                        newl = '\n'
                    print md.parseString(rspec).toprettyxml(indent=' '*2, newl=newl)
                except:
                    print rspec
            else:
                print 'No resources available'
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
                print jspecs
            else:
                if rspecs and rspecs != {}:
                    print 'No parsable resources available.'
                    #print 'Unparsable responses:'
                    #pprint.pprint(rspecs)
                else:
                    print 'No resources available'
    
    def _ospec_to_rspecs(self, specfile):
        """Convert the given omnispec file into a dict of url => rspec."""
        jspecs = {}
        try:
            jspecs = json.loads(file(specfile,'r').read())
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
            print 'For %s allocate = %r' % (url, allocate)
            if allocate:
                rspecs[url] = omnispec_to_rspec(ospec, True)
            else:
                self.logger.debug('Nothing to allocate at %r', url)
#        print rspecs
        return rspecs

    def createsliver(self, args):
        if len(args) < 2:
            sys.exit('createsliver requires 2 args: slicename and omnispec filename')

        # check command line args
        if self.opts.native and not self.opts.aggregate:
            # If native is requested, the user must supply an aggregate.
            msg = 'Specifying a native RSpec requires specifying an aggregate.'
            # Calling exit here is a bit of a hammer.
            # Maybe there's a gentler way.
            sys.exit(msg)

        name = args[0]
        if name is None or name.strip() == "":
            sys.exit('createsliver got empty slicename')

        urn = self.framework.slice_name_to_urn(name.strip())
        slice_cred = self._get_slice_cred(urn)
        if slice_cred is None:
            sys.exit('Cannot create sliver %s: No slice credential'
                     % (urn))

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
        
        # Perform the allocations
        aggregate_urls = self._listaggregates().values()
        for (url, rspec) in rspecs.items():
                
            # Is this AM listed in the CH or our list of aggregates?
            # If not we won't be able to check its status and delete it later
            if not url in aggregate_urls:
                self.logger.warning("""You're creating a sliver in an AM (%s) that is either not listed by
                your Clearinghouse or it is not in the optionally provided list of aggregates in
                your configuration file.  By creating this sliver, you will be unable to check its
                status or delete it.""" % (url))
                
                res = raw_input("Would you like to continue? (y/N) ")
                if not res.lower().startswith('y'):
                    return
                
            if not self.opts.native:
                try:
                    import xml.dom.minidom as md
                    newl = ''
                    if '\n' not in rspec:
                        newl = '\n'
                    self.logger.debug("Native RSpec for %s is:\n%s", url, md.parseString(rspec).toprettyxml(indent=' '*2, newl=newl))
                except:
                    self.logger.debug("Native RSpec for %s is:\n%s", url, rspec)

            # Okay, send a message to the AM this resource came from
            result = None
            client = make_client(url, self.frame_config['key'], self.frame_config['cert'])
            try:
                result = self._do_ssl(("Create Sliver %s at %s" % (urn, url)), client.CreateSliver, urn, [slice_cred], rspec, slice_users)
            except InvalidSSLPasswordException, exc:
                self.logger.error("FAILed to create sliver for %s on %s", urn, url)
            except xmlrpclib.Fault, fault:
                # FIXME: string replace literal \n with actual \n
                self.logger.error('FAILed to create sliver %s at %s: %s',
                                  urn, url, str(fault))
            except Exception, exc:
                self.logger.error("FAILed to create sliver for %s on %s: %s", urn, url, exc)
                if not self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.error('    ..... Run with --debug for more information')
                self.logger.debug(traceback.format_exc())

            if result != None and isinstance(result, str) and (result.startswith('<rspec') or result.startswith('<resv_rspec')):
                try:
                    import xml.dom.minidom as md
                    newl = ''
                    if '\n' not in result:
                        newl = '\n'
                    print 'Asked %s to reserve resources. Result:\n%s' % (url, md.parseString(result).toprettyxml(indent=' '*2, newl=newl))
                except:
                    print 'Asked %s to reserve resources. Result: %s' % (url, result)
            else:
                print 'Asked %s to reserve resources. Result: %s' % (url, result)

            if '<RSpec type="SFA">' in rspec:
                # Figure out the login name
                hrn = urn.split('+')[1].replace('.','').replace(':','.').split('.')[-1]
                name = urn.split('+')[3]
                self.logger.info("Your login name for PL resources will be %s_%s" % (hrn,name))


    def deletesliver(self, args):
        if len(args) == 0:
            sys.exit('deletesliver requires arg of slice name')

        name = args[0]
        if name is None or name.strip() == "":
            sys.exit('deletesliver got empty slicename')

        # FIXME: Validate the slice name starts with
        # PREFIX+slice+

        urn = self.framework.slice_name_to_urn(name)
        slice_cred = self._get_slice_cred(urn)
        if slice_cred is None:
            sys.exit('Cannot delete sliver %s: No slice credential'
                     % (urn))

        # Connect to each available GENI AM 
        for client in self._getclients():
            try:
                if self._do_ssl(("Delete Sliver %s on %s" % (urn, client.url)), client.DeleteSliver, urn, [slice_cred]):
                    print "Deleted sliver %s on %s at %s" % (urn, client.urn, client.url)
                else:
                    print "FAILed to delete sliver %s on %s at %s" % (urn, client.urn, client.url)
            except InvalidSSLPasswordException, exc:
                self.logger.error("FAILed to delete sliver %s on %s (%s)", urn, client.urn, client.url)
            except xmlrpclib.Fault, fault:
                # FIXME: string replace literal \n with actual \n
                self.logger.error('Failed to delete sliver %s at %s: %s',
                                  urn, client.url, str(fault))
            except Exception, exc:
                self.logger.error("FAILed to delete sliver %s on %s (%s): %s", urn, client.urn, client.url, exc)
                if not self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.error('    ..... Run with --debug for more information')
                self.logger.debug(traceback.format_exc())
            
    def renewsliver(self, args):
        if len(args) < 2:
            sys.exit('renewsliver requires arg of slice name and new expiration time in UTC')

        name = args[0]
        if name is None or name.strip() == "":
            sys.exit('renewsliver got empty slicename')

        # FIXME: Validate the slice name starts with
        # PREFIX+slice+

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

        print 'Renewing Sliver %s until %r' % (urn, time)

        for client in self._getclients():
            try:
                # Note that the time arg includes UTC offset as needed
                res = self._do_ssl(("Renew Sliver %s on %s" % (urn, client.url)), client.RenewSliver, urn, [slice_cred], time.isoformat())
                if not res:
                    print "FAILed to renew sliver %s on %s (%s)" % (urn, client.urn, client.url)
                else:
                    print "Renewed sliver %s at %s (%s) until %s" % (urn, client.urn, client.url, time.isoformat())
            except InvalidSSLPasswordException, exc:
                self.logger.error("FAILed to renew sliver for %s on %s (%s)", urn, client.urn, client.url)
            except xmlrpclib.Fault, fault:
                # FIXME: string replace literal \n with actual \n
                self.logger.error('FAILed to renew sliver %s at %s: %s',
                                  urn, client.url, str(fault))
            except Exception, exc:
                self.logger.error("FAILed to renew sliver for %s on %s (%s): %s", urn, client.urn, client.url, exc)
                if not self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.error('    ..... Run with --debug for more information')
                self.logger.debug(traceback.format_exc())
    
    def sliverstatus(self, args):
        if len(args) == 0:
            sys.exit('sliverstatus requires arg of slice name')

        name = args[0]
        if name is None or name.strip() == "":
            sys.exit('sliverstatus got empty slicename')

        # FIXME: Validate the slice name starts with
        # PREFIX+slice+

        urn = self.framework.slice_name_to_urn(name)
        slice_cred = self._get_slice_cred(urn)
        if slice_cred is None:
            sys.exit('Cannot get sliver status for %s: No slice credential'
                     % (urn))

        print 'Status of Slice %s:' % urn
        for client in self._getclients():
            try:
                status = self._do_ssl("Sliver status of %s at %s" % (urn, client.url), client.SliverStatus, urn, [slice_cred])
                print "Sliver at %s:" % (client.url)
                pprint.pprint(status)
            except InvalidSSLPasswordException, exc:
                self.logger.error("Failed to retrieve status of %s at %s.",
                                  urn, client.url)
            except xmlrpclib.Fault, fault:
                # FIXME: string replace literal \n with actual \n
                self.logger.error('Failed to retrieve status of %s at %s: %s',
                                  urn, client.url, str(fault))
            except Exception, exc:
                self.logger.error('Failed to retrieve status of %s at %s: %s.', urn, client.url, exc)
                if not self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.error('    ..... Run with --debug for more information')
                self.logger.debug(traceback.format_exc())
                
    def shutdown(self, args):
        if len(args) == 0:
            sys.exit('shutdown requires arg of slice name')

        name = args[0]
        if name is None or name.strip() == "":
            sys.exit('shutdown got empty slicename')

        # FIXME: Validate the slice name starts with
        # PREFIX+slice+

        urn = self.framework.slice_name_to_urn(name)
        slice_cred = self._get_slice_cred(urn)
        if slice_cred is None:
            sys.exit('Cannot shutdown slice %s: No slice credential'
                     % (urn))

        for client in self._getclients():
            try:
                if self._do_ssl("Shutdown %s on %s" % (urn, client.url), client.Shutdown, urn, [slice_cred]):
                    print "Shutdown Sliver %s at %s on %s" % (urn, client.urn, client.url)
                else:
                    print "FAILed to shutdown sliver %s on AM %s at %s" % (urn, client.urn, client.url)
            except InvalidSSLPasswordException, exc:
                self.logger.error("FAILed to shutdown sliver %s on %s (%s)", urn, client.urn, client.url)
            except xmlrpclib.Fault, fault:
                # FIXME: string replace literal \n with actual \n
                self.logger.error('FAILed to shutdown sliver %s at %s: %s',
                                  urn, client.url, str(fault))
            except Exception, exc:
                self.logger.error("FAILed to shutdown sliver %s on %s (%s): %s", urn, client.urn, client.url, exc)
                if not self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.error('    ..... Run with --debug for more information')
                self.logger.debug(traceback.format_exc())
    
    def _do_ssl(self, reason, fn, *args):
        # Change exception name?
        max_attempts = 2
        attempt = 0
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
                        raise InvalidSSLPasswordException('Wrong pass phrase after %d tries' % max_attempts)
                else:
                    raise

    def getversion(self, args):
        for client in self._getclients():
            try:
                version = self._do_ssl("GetVersion at %s" % (client.url), client.GetVersion)
                print "%s (%s) %s" % (client.urn, client.url, version)
            except InvalidSSLPasswordException, exc:
                msg = "Failed to get version information for %s at (%s)."
                self.logger.error(msg, client.urn, client.url)
            except xmlrpclib.Fault, fault:
                # FIXME: string replace literal \n with actual \n
                self.logger.error('Failed to get version of %s: %s',
                                  client.url, str(fault))
            except Exception, exc:
                msg = "Failed to get version information for %s at (%s): %s."
                self.logger.error(msg, client.urn, client.url, exc)
                if not self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.error('    ..... Run with --debug for more information')
                self.logger.debug(traceback.format_exc())

    def createslice(self, args):
        if len(args) == 0:
            sys.exit('createslice requires arg of slice name')

        name = args[0]

        # FIXME: Validate the slice name starts with
        # PREFIX+slice+

        urn = self.framework.slice_name_to_urn(name)
        
        slice_cred = None
        try:
            slice_cred = self._do_ssl("Create Slice %s" % urn, self.framework.create_slice, urn)
            if slice_cred:
                print "Created slice with Name %s, URN %s" % (name, urn)
            else:
                print "Create Slice FAILed for slice name %s." % (name)
                if not self.logger.isEnabledFor(logging.DEBUG):
                    print "   Try re-running with --debug for more information."
        except InvalidSSLPasswordException, exc:
            self.logger.error("FAILed to create slice %s", urn)
        except Exception, exc:
            self.logger.error("FAILed to create slice %s: %s", urn, exc)
            if not self.logger.isEnabledFor(logging.DEBUG):
                self.logger.error('    ..... Run with --debug for more information')
            self.logger.debug(traceback.format_exc())

        
    def deleteslice(self, args):
        if len(args) == 0:
            sys.exit('deleteslice requires arg of slice name')

        name = args[0]

        # FIXME: Validate the slice name starts with
        # PREFIX+slice+

        urn = self.framework.slice_name_to_urn(name)

        res = None
        try:
            res = self._do_ssl("Delete Slice %s" % urn, self.framework.delete_slice, urn)
            print "Delete Slice %s result: %r" % (name, res)
        except InvalidSSLPasswordException, exc:
            self.logger.error("FAILed to delete slice %s", urn)
        except Exception, exc:
            self.logger.error("FAILed to delete slice %s: %s", urn, exc)
            if not self.logger.isEnabledFor(logging.DEBUG):
                self.logger.error('    ..... Run with --debug for more information')
            self.logger.debug(traceback.format_exc())


    def getslicecred(self, args):
        if len(args) == 0:
            sys.exit('getslicecred requires arg of slice name')

        name = args[0]

        # FIXME: Validate the slice name starts with
        # PREFIX+slice+

        urn = self.framework.slice_name_to_urn(name)
        cred = self._get_slice_cred(urn)
        print "Slice cred for %s: %s" % (urn, cred)
        
    def _get_slice_cred(self, urn):
        '''Try a couple times to get the given slice credential.
        Retry on wrong pass phrase.'''

        try:
            return self._do_ssl("Get Slice Cred %s" % urn, self.framework.get_slice_cred, urn)
        except InvalidSSLPasswordException, exc:
            self.logger.error("FAILed to get slice credential for %s", urn)
        except Exception, exc:
            self.logger.error("FAILed to get slice credential for %s: %s", urn, exc)
            if not self.logger.isEnabledFor(logging.DEBUG):
                self.logger.error('    ..... Run with --debug for more information')
            self.logger.debug(traceback.format_exc())

        return None

    def listaggregates(self, args):
        """Print the aggregates federated with the control framework."""
        for (urn, url) in self._listaggregates().items():
            print "%s: %s" % (urn, url)

    def renewslice(self, args):
        """Renew the slice at the clearinghouse so that the slivers can be
        renewed.
        """
        if len(args) != 2:
            sys.exit('renewslice <slice name> <expiration date>')
        name = args[0]
        expire_str = args[1]
        # convert the slice name to a framework urn
        urn = self.framework.slice_name_to_urn(name)
        # convert the desired expiration to a python datetime
        try:
            in_expiration = dateutil.parser.parse(expire_str)
        except:
            msg = 'Unable to parse date "%s".\nTry "YYYYMMDDTHH:MM:SSZ" format'
            msg = msg % (expire_str)
            sys.exit(msg)

        # Try to renew the slice
        out_expiration = None
        try:
            out_expiration = self._do_ssl("Renew Slice %s" % urn, self.framework.renew_slice, urn, in_expiration)
        except InvalidSSLPasswordException, exc:
            self.logger.error("FAILed to renew slice %s", urn)
        except Exception, exc:
            self.logger.error("FAILed to renew slice %s: %s", urn, exc)
            if not self.logger.isEnabledFor(logging.DEBUG):
                self.logger.error('    ..... Run with --debug for more information')
            self.logger.debug(traceback.format_exc())

        if out_expiration:
            print "Slice %s now expires at %s" % (name, out_expiration)
        else:
            print "FAILed to renew slice %s" % (name)


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
    return parser.parse_args()

def configure_logging(opts):
    level = logging.INFO
    logging.basicConfig(level=level)
    if opts.debug:
        level = logging.DEBUG
    logger = logging.getLogger("omni")
    logger.setLevel(level)
    return logger

def main(argv=None):
    if argv is None:
        argv = sys.argv
    opts, args = parse_args(argv)
    logger = configure_logging(opts)

    # Load up the config file
    configfiles = ['omni_config','~/.gcf/omni_config']

    if opts.configfile:
        configfiles.insert(0, opts.configfile)

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
        
    cf_type = config['selected_framework']['type']

    framework_mod = __import__('omnilib.frameworks.framework_%s' % cf_type, fromlist=['omnilib.frameworks'])
    framework = framework_mod.Framework(config['selected_framework'])
        
    # Process the user's call
    handler = CallHandler(framework, config, opts)    
    handler._handle(args)
        
        
if __name__ == "__main__":
    sys.exit(main())
