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

    Be sure to create an omni config file (typically ~/.omni/omni_config)
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
import sys
import zlib
import ConfigParser

import dateutil.parser
from omnilib.xmlrpc.client import make_client
from omnilib.omnispec.translation import rspec_to_omnispec, omnispec_to_rspec
from omnilib.omnispec.omnispec import OmniSpec

OMNI_CONFIG_TEMPLATE='/etc/omni/templates/omni_config'

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
    getslicecred, listresouces, createsliver, deletesliver,
    renewsliver, sliverstatus, shutdown
    """

    def __init__(self, framework, config):
        self.framework = framework    
        self.frame_config = config['selected_framework']
        self.omni_config = config['omni']
        self.config = config
        
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
        ''' Ask FW CH for known aggregates (_listaggregates) and construct 
        an XMLRPC client for each.  If 'am' is not none, connect to that URL instead'''
        clients = []
        if ams:
            for am in ams:
                client = make_client(am, self.frame_config['key'], self.frame_config['cert'])
                client.url = am
                client.urn = am
                clients.append(client)
        else:
            for (urn, url) in self._listaggregates([]).items():
                client = make_client(url, self.frame_config['key'], self.frame_config['cert'])
                client.urn = urn
                client.url = url
                clients.append(client)
        return clients    
        
    def _listaggregates(self, args):
        '''Use aggregates listed in config file's aggregates key or, if empty, ask the framework CH for known aggregates'''
        if not self.omni_config.get('aggregates', '').strip() == '':
            aggs = {}
            for url in self.omni_config['aggregates'].strip().split(','):
                aggs[url] = url
            return aggs                
        else:
            aggs = self.framework.list_aggregates()
            return aggs

    def listresources(self, args):
        '''Optional arg is a slice name limiting results. Call ListResources
        on all AMs known by the FW CH, and return the omnispecs found.'''
        rspecs = {}
        options = {}
        logger = logging.getLogger('omni')

        ams = None
        urn_name = None
        if len(args) > 0:
            if args[0].startswith('http'):
                ams = args
            else:
                urn_name = args[0].strip()
                ams = args[1:]

        options['geni_compressed'] = True;

        # Get the credential for this query
        if urn_name is None:
            cred = self.framework.get_user_cred()
        else:
            urn = self.framework.slice_name_to_urn(urn_name)
            cred = self.framework.get_slice_cred(urn)
            options['geni_slice_urn'] = urn

        
        # Connect to each available GENI AM to list their resources
        for client in self._getclients(ams):
            try:
                if cred is None:
                    logger.debug("Have null credentials in call to ListResources!")
                logger.debug("Connecting to AM: %s" % client)
                rspec = client.ListResources([cred], options)
                if options.get('geni_compressed',False):
                    try:
                        rspec = zlib.decompress(rspec.decode('base64'))
                    except:
                        logger.debug("Failed to decompress resources list.  In PG Framework this is okay.")
                        pass
                    
                rspecs[(client.urn, client.url)] = rspec
            except Exception, exc:
                import traceback
                logger.error("Failed to List Resources from %s (%s): %s" % (client.urn, client.url, exc))
                logger.error(traceback.format_exc())
            
        # Convert the rspecs to omnispecs
        omnispecs = {}
        for ((urn,url), rspec) in rspecs.items():                        
            logger.debug("Getting RSpec items for urn %s", urn)
            omnispecs[url] = rspec_to_omnispec(urn,rspec)

        if omnispecs and omnispecs != {}:
            jspecs = json.dumps(omnispecs, indent=4)
            print jspecs
        return omnispecs
    
    
    def createsliver(self, args):
        if len(args) < 2:
            sys.exit('createsliver requires 2 args: slicename and omnispec filename')

        name = args[0]
        if name is None or name.strip() == "":
            sys.exit('createsliver got empty slicename')

        # FIXME: Validate the slice name starts with
        # PREFIX+slice+

        urn = self.framework.slice_name_to_urn(name.strip())
        slice_cred = self.framework.get_slice_cred(urn)

        # Load up the user's edited omnispec
        specfile = args[1]
        if specfile is None or not os.path.isfile(specfile):
            sys.exit('omnispec file of resources to request missing: %s' % specfile)

        jspecs = dict()
        try:
            jspecs = json.loads(file(specfile,'r').read())
        except Exception, exc:
            sys.exit("Parse error reading omnispec %s: %s" % (specfile, exc))

        omnispecs = {}
        for url, spec_dict in jspecs.items():
            omnispecs[url] = OmniSpec('','',dictionary=spec_dict)
        
        
        # Copy the user config and read the keys from the files into the structure
        slice_users = copy(self.config['users'])

        #slice_users = copy(self.omni_config['slice_users'])
        for user in slice_users:
            newkeys = []
            required = ['name', 'urn', 'keys']
            for req in required:
                if not req in user:
                    raise Exception("%s in omni_config is not specified for user %s" % (req,user))

            try:
                for key in user['keys'].split(','):        
                    newkeys.append(file(os.path.expanduser(key.strip())).read())
            except Exception, exc:
                logger = logging.getLogger('omni')
                logger.error("Failed to read user key from %s: %s" %(user['keys'], exc))
            user['keys'] = newkeys
        
        # Anything we need to allocate?
        for (url, ospec) in omnispecs.items():
            if url is None or url.strip() == "":
                print 'omnispec format error: Empty URL'
                continue
            allocate = False
            for (_, r) in ospec.get_resources().items():
                if r.get_allocate():
                    allocate = True
                    break
                
                
            # Is this AM listed in the CH or our list of aggregates?
            # If not we won't be able to check its status and delete it later
            print self._listaggregates(args)
            if not url in self._listaggregates(args).values():
                logger = logging.getLogger('omni')
                logger.warning("""You're creating a sliver in an AM (%s) that is either not listed by
                your Clearinghouse or it is not in the optionally provided list of aggregates in
                your configuration file.  By creating this sliver, you will be unable to check its
                status or delete it.""" % (url))
                
                res = raw_input("Would you like to continue? (y/N) ")
                if not res.lower().startswith('y'):
                    return
                
            # Okay, send a message to the AM this resource came from
            if allocate:
                try:
                    client = make_client(url, self.frame_config['key'], self.frame_config['cert'])
                    rspec = omnispec_to_rspec(ospec, True)
#                    print "Rspec to send to %s:" % url
#                    print rspec
                    result = client.CreateSliver(urn, [slice_cred], rspec, slice_users)
                    print 'Asked %s to reserve resources. Result: %s' % (url, result)
                except Exception, exc:
                    import traceback
                    logger = logging.getLogger('omni')
                    logger.error("Error occurred. Unable to allocate from %s: %s.  Please run --debug to see stack trace." % (url, exc))
                    logger.debug(traceback.format_exc())
            else:
                logger = logging.getLogger('omni')
                logger.debug('Nothing to allocate at %r', url)

    def deletesliver(self, args):
        if len(args) == 0:
            sys.exit('deletesliver requires arg of slice name')

        name = args[0]
        if name is None or name.strip() == "":
            sys.exit('deletesliver got empty slicename')

        # FIXME: Validate the slice name starts with
        # PREFIX+slice+

        urn = self.framework.slice_name_to_urn(name)
        slice_cred = self.framework.get_slice_cred(urn)
        # Connect to each available GENI AM 
        for client in self._getclients():
            try:
                if client.DeleteSliver(urn, [slice_cred]):
                    print "Deleted sliver %s on %s at %s" % (urn, client.urn, client.url)
                else:
                    print "FAILed to delete sliver %s on %s at %s" % (urn, client.urn, client.url)
            except Exception, exc:
                logger = logging.getLogger('omni')
                logger.error("Error occured. Failed to delete sliver %s on %s (%s)." % (urn, client.urn, client.url))
                logger.error(str(exc))
            
    def renewsliver(self, args):
        if len(args) < 2:
            sys.exit('renewsliver requires arg of slice name and new expiration time in UTC')

        name = args[0]
        if name is None or name.strip() == "":
            sys.exit('renewsliver got empty slicename')

        # FIXME: Validate the slice name starts with
        # PREFIX+slice+

        urn = self.framework.slice_name_to_urn(name)
        slice_cred = self.framework.get_slice_cred(urn)
        time = None
        try:
            time = dateutil.parser.parse(args[1])
        except Exception, exc:
            sys.exit('renewsliver couldnt parse new expiration time from %s: %r' % (args[1], exc))

        print 'Renewing Sliver %s until %r' % (urn, time)

        for client in self._getclients():
            try:
                # Note that the time arg includes UTC offset as needed
                res = client.RenewSliver(urn, [slice_cred], time.isoformat())
                if not res:
                    print "FAILed to renew sliver %s on %s" % (urn, client.urn)
                else:
                    print "Renewed sliver %s at %s until %s" % (urn, client.urn, time.isoformat())
            except Exception, exc:
                logger = logging.getLogger('omni')
                logger.error("Failed to renew sliver %s on %s." % (urn, client.urn))
                logger.error(str(exc))
    
    def sliverstatus(self, args):
        if len(args) == 0:
            sys.exit('sliverstatus requires arg of slice name')

        name = args[0]
        if name is None or name.strip() == "":
            sys.exit('sliverstatus got empty slicename')

        # FIXME: Validate the slice name starts with
        # PREFIX+slice+

        urn = self.framework.slice_name_to_urn(name)
        slice_cred = self.framework.get_slice_cred(urn)
        for client in self._getclients():
            try:
                status = client.SliverStatus(urn, [slice_cred])
                print "%s (%s):" % (client.urn, client.url)
                pprint.pprint(status)
            except Exception, exc:
                logger = logging.getLogger('omni')
                logger.error("Failed to retrieve status of %s at %s." % (urn, client.urn))
                logger.error(str(exc))
                
    def shutdown(self, args):
        if len(args) == 0:
            sys.exit('shutdown requires arg of slice name')

        name = args[0]
        if name is None or name.strip() == "":
            sys.exit('shutdown got empty slicename')

        # FIXME: Validate the slice name starts with
        # PREFIX+slice+

        urn = self.framework.slice_name_to_urn(name)
        slice_cred = self.framework.get_slice_cred(urn)
        for client in self._getclients():
            try:
                if client.Shutdown(urn, [slice_cred]):
                    print "Shutdown Sliver %s at %s on %s" % (urn, client.urn, client.url)
                else:
                    print "FAILed to shutdown sliver %s on AM %s at %s" % (urn, client.urn, client.url)
            except Exception, exc:
                logger = logging.getLogger('omni')                
                logger.error("Failed to shutdown %s on AM %s at %s." % (urn, client.urn, client.url))
                logger.error(str(exc))                
    
    def getversion(self, args):
        for client in self._getclients():
            try:
                print "%s (%s) %s" % (client.urn, client.url, client.GetVersion())
            except Exception, exc:
                logger = logging.getLogger('omni')                
                logger.error("Failed to get version information for %s at (%s). " % (client.urn, client.url))
                logger.error(str(exc))                                
                                
    def createslice(self, args):
        if len(args) == 0:
            sys.exit('createslice requires arg of slice name')

        name = args[0]

        # FIXME: Validate the slice name starts with
        # PREFIX+slice+

        urn = self.framework.slice_name_to_urn(name)
        slice_cred = self.framework.create_slice(urn)
        if slice_cred:
            print "Created slice with Name %s, URN %s" % (name, urn)
        else:
            print "Create Slice failed"
        
    def deleteslice(self, args):
        if len(args) == 0:
            sys.exit('deleteslice requires arg of slice name')

        name = args[0]

        # FIXME: Validate the slice name starts with
        # PREFIX+slice+

        urn = self.framework.slice_name_to_urn(name)
        res = self.framework.delete_slice(urn)
        print "Delete Slice %s result: %r" % (name, res)

    def getslicecred(self, args):
        if len(args) == 0:
            sys.exit('getslicecred requires arg of slice name')

        name = args[0]

        # FIXME: Validate the slice name starts with
        # PREFIX+slice+

        urn = self.framework.slice_name_to_urn(name)
        cred = self.framework.get_slice_cred(urn)
        print cred
        
    def listaggregates(self, args):
        """Print the aggregates federated with the control framework."""
        for (urn, url) in self._listaggregates([]).items():
            print "%s: %s" % (urn, url)


def parse_args(argv):
    parser = optparse.OptionParser()
    parser.add_option("-c", "--configfile", default="~/.omni/omni_config",
                      help="config file name", metavar="FILE")
    parser.add_option("-f", "--framework", default="",
                      help="control framework to use for creation/deletion of slices")
    
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
    

def main(argv=None):
    if argv is None:
        argv = sys.argv
    opts, args = parse_args(argv)
    configure_logging(opts)

    logger = logging.getLogger('omni')

    # Load up the config file
    filename = os.path.expanduser(opts.configfile)
    
    if not os.path.exists(filename):

        logger.info('Missing omni config file %s' % filename)
        found = False
        for dst in [OMNI_CONFIG_TEMPLATE, 'omni_config']:
            if os.path.exists(dst):
                from shutil import copyfile
                if '/' in filename:
                    os.mkdir(filename[:filename.rfind('/')])
                    logger.info("Created directory %s" % filename[:filename.rfind('/')])
                copyfile(dst, filename)                
                logger.info("Copied omni_config from %s" % dst)
                found = True
                break
        if not found:
            sys.exit("Could not find a template omni_config to copy to %s" % filename)
            
            

    logger.debug("Loading config file %s", filename)

    confparser = ConfigParser.RawConfigParser()
    try:
        confparser.read(filename)
    except ConfigParser.Error as exc:
        sys.exit("Config file %s could not be parsed: %s"
                 % (filename, str(exc)))

    # Load up the omni options
    config = {}
    config['omni'] = {}
    for (key,val) in confparser.items('omni'):
        config['omni'][key] = val
        
    # Load up the users the user wants us to see        
    config['users'] = []
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
    handler = CallHandler(framework, config)    
    handler._handle(args)
        
        
if __name__ == "__main__":
    sys.exit(main())
