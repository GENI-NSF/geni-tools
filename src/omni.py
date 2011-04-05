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
import xmlrpclib
import zlib
import ConfigParser

import dateutil.parser
from omnilib.omnispec.translation import rspec_to_omnispec, omnispec_to_rspec
from omnilib.omnispec.omnispec import OmniSpec
from omnilib.util.faultPrinting import cln_xmlrpclib_fault
import omnilib.xmlrpc.client

import sfa.trust.credential as cred

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
        getattr(self,call)(args[1:])

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

        self._print_slice_expiration(urn)

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
                    import xml.dom.minidom as md
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
                self.logger.info("Please run the omni sliverstatus call on your slice to determine your login name to PL resources")


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
                print "Deleted sliver %s on %s at %s" % (urn, client.urn, client.url)
            else:
                print "Failed to delete sliver %s on %s at %s" % (urn, client.urn, client.url)
            
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

        slicecred_obj = cred.Credential(string=slice_cred)
        self._print_slice_expiration(urn, slice_cred)
        if time > slicecred_obj.expiration:
            sys.exit('Cannot renew sliver %s until %s which is after slice expiration time %s' % (urn, time, slicecred_obj.expiration))
        elif time <= datetime.datetime.utcnow():
            self.logger.info('Sliver %s will be set to expire now' % urn)
        else:
            self.logger.debug('Slice expires at %s after requested time %s' % (slicecred_obj.expiration, time))

        print 'Renewing Sliver %s until %s' % (urn, time)

        if self.opts.orca_slice_id:
            self.logger.info('Using ORCA slice id %r', self.opts.orca_slice_id)
            urn = self.opts.orca_slice_id
        for client in self._getclients():
            # Note that the time arg includes UTC offset as needed
            res = self._do_ssl(("Renew Sliver %s on %s" % (urn, client.url)), client.RenewSliver, urn, [slice_cred], time.isoformat())
            if not res:
                print "Failed to renew sliver %s on %s (%s)" % (urn, client.urn, client.url)
            else:
                print "Renewed sliver %s at %s (%s) until %s" % (urn, client.urn, client.url, time.isoformat())
    
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
        for client in self._getclients():
            status = self._do_ssl("Sliver status of %s at %s" % (urn, client.url), client.SliverStatus, urn, [slice_cred])
            if status:
                print "Sliver at %s:" % (client.url)
                pprint.pprint(status)

                
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
        for client in self._getclients():
            if self._do_ssl("Shutdown %s on %s" % (urn, client.url), client.Shutdown, urn, [slice_cred]):
                print "Shutdown Sliver %s at %s on %s" % (urn, client.urn, client.url)
            else:
                print "Failed to shutdown sliver %s on AM %s at %s" % (urn, client.urn, client.url)
    
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
                else:
                    self.logger.error("%s: Unknown SSL error %s" % (failMsg, exc))
                    if not self.logger.isEnabledFor(logging.DEBUG):
                        self.logger.error('    ..... Run with --debug for more information')
                    self.logger.debug(traceback.format_exc())

                    return None
            except xmlrpclib.Fault, fault:
                self.logger.error("%s Server says: %s" % (failMsg, cln_xmlrpclib_fault(fault)))
                return None
            except Exception, exc:
                self.logger.error("%s: %s" % (failMsg, exc))
                if not self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.error('    ..... Run with --debug for more information')
                self.logger.debug(traceback.format_exc())
                return None

    def getversion(self, args):
        for client in self._getclients():
            version = self._do_ssl("GetVersion at %s" % (str(client.url)), client.GetVersion)
            if not version is None:
                print "%s (%s) %s" % (client.urn, client.url, version)
            

    def createslice(self, args):
        if len(args) == 0 or args[0] == None or args[0].strip() == "":
            sys.exit('createslice requires arg of slice name')

        name = args[0]

        # FIXME: catch errors getting slice URN to give prettier error msg?
        urn = self.framework.slice_name_to_urn(name)
        
        slice_cred = self._do_ssl("Create Slice %s" % urn, self.framework.create_slice, urn)
        if slice_cred:
            print "Created slice with Name %s, URN %s" % (name, urn)
        else:
            print "Create Slice Failed for slice name %s." % (name)
            if not self.logger.isEnabledFor(logging.DEBUG):
                print "   Try re-running with --debug for more information."

        
    def deleteslice(self, args):
        if len(args) == 0 or args[0] == None or args[0].strip() == "":
            sys.exit('deleteslice requires arg of slice name')

        name = args[0]

        # FIXME: catch errors getting slice URN to give prettier error msg?
        urn = self.framework.slice_name_to_urn(name)

        res = self._do_ssl("Delete Slice %s" % urn, self.framework.delete_slice, urn)
        print "Delete Slice %s result: %r" % (name, res)


    def getslicecred(self, args):
        if len(args) == 0 or args[0] == None or args[0].strip() == "":
            sys.exit('getslicecred requires arg of slice name')

        name = args[0]

        # FIXME: catch errors getting slice URN to give prettier error msg?
        urn = self.framework.slice_name_to_urn(name)
        cred = self._get_slice_cred(urn)

        self._print_slice_expiration(urn)

        # FIXME: Print the non slice cred bit to STDERR so
        # capturing just stdout givs just the cred?
        print "Slice cred for %s: %s" % (urn, cred)
        
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
            print 'Slice %s has expired at %s' % (urn, sliceexp)
        elif sliceexp - datetime.timedelta(hours=shorthours) <= now:
            print 'Slice %s expires in <= %d hours' % (urn, shorthours)
            self.logger.debug('Slice %s expires on %s' % (urn, sliceexp))
            self.logger.debug('It is now %s' % (datetime.datetime.now()))
        elif sliceexp - datetime.timedelta(days=middays) <= now:
            print 'Slice %s expires within %d day' % (urn, middays)
        else:
            self.logger.debug('Slice %s expires on %s' % (urn, sliceexp))

    def _get_slice_cred(self, urn):
        '''Try a couple times to get the given slice credential.
        Retry on wrong pass phrase.'''

        return self._do_ssl("Get Slice Cred %s" % urn, self.framework.get_slice_cred, urn)

    def listaggregates(self, args):
        """Print the aggregates federated with the control framework."""
        for (urn, url) in self._listaggregates().items():
            print "%s: %s" % (urn, url)

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
            print "Slice %s now expires at %s" % (name, out_expiration)
        else:
            print "Failed to renew slice %s" % (name)
        self._print_slice_expiration(urn)


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
            sys.exit("Config file '%s' does not exist"
                     % (opts.configfile))

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

def main(argv=None):
    opts, args = parse_args(sys.argv[1:])    
    logger = configure_logging(opts)
    config = load_config(opts, logger)        
    framework = load_framework(config)
        
    # Process the user's call
    handler = CallHandler(framework, config, opts)    
    handler._handle(args)
        
        
if __name__ == "__main__":
    sys.exit(main())
