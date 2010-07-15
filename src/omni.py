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
import base64
import json
import logging
import optparse
import os
import pprint
import sys
import zlib

import dateutil.parser

from geni.omni.xmlrpc.client import make_client
from geni.omni.omnispec.translation import rspec_to_omnispec, omnispec_to_rspec
from geni.omni.omnispec.omnispec import OmniSpec

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

    def __init__(self, framework, frame_config, omni_config):
        self.framework = framework    
        self.frame_config = frame_config
        self.omni_config = omni_config
        frame_config['cert'] = getAbsPath(frame_config['cert'])
        if not os.path.exists(frame_config['cert']):
            sys.exit('Frameworks certfile %s doesnt exist' % frame_config['cert'])

        frame_config['key'] = getAbsPath(frame_config['key'])
        if not os.path.exists(frame_config['key']):
            sys.exit('Frameworks keyfile %s doesnt exist' % frame_config['key'])

    def _handle(self, args):
        if len(args) == 0:
            sys.exit('Insufficient number of arguments - Missing command to run')
        
        call = args[0].lower()
        if call.startswith('_'):
            return
        if not hasattr(self,call):
            sys.exit('Unknown function: %s' % call)
        getattr(self,call)(args[1:])

    def _getclients(self):
        ''' Ask FW CH for known aggregates (_listaggregates) and construct 
        an XMLRPC client for each.'''
        clients = []
        for (urn, url) in self._listaggregates([]).items():
            client = make_client(url, self.frame_config['key'], self.frame_config['cert'])
            client.urn = urn
            client.url = url
            clients.append(client)
        return clients    
        
    def _listaggregates(self, args):
        '''Ask Framework CH for known aggregates'''
        aggs = self.framework.list_aggregates()
        return aggs

    def listresources(self, args):
        '''Optional arg is a slice name limiting results. Call ListResources
        on all AMs known by the FW CH, and return the omnispecs found.'''
        rspecs = {}
        options = {}
        logger = logging.getLogger('omni')

        options['geni_compressed'] = True;

        # Get the credential for this query
        if len(args) == 0:
            cred = self.framework.get_user_cred()
        else:
            name = args[0]
            urn = self.framework.slice_name_to_urn(name)
            cred = self.framework.get_slice_cred(urn)
            options['geni_slice_urn'] = urn

        
        # Connect to each available GENI AM to list their resources
        for client in self._getclients():
            try:
                if cred is None:
                    logger.debug("Have null credentials in call to ListResources!")
                rspec = client.ListResources([cred], options)
                rspecs[(client.urn, client.url)] = rspec
            except Exception, exc:
                logger.error("Failed to List Resources from %s (%s): %s" % (client.urn, client.url, exc))
            
        # Convert the rspecs to omnispecs
        omnispecs = {}
        for ((urn,url), rspec) in rspecs.items():                        
            logger.debug("Getting RSpec items for urn %s", urn)
            if 'geni_compressed' in options and options['geni_compressed']:
                # Yuck. Apparently PG ignores the compressed flag? At least sometimes?
                try:
                    rspec = zlib.decompress(base64.b64decode(rspec))
                except:
                    logger.debug("Failed to decompress resource list. In PG framework this is ok.")
                    pass
            omnispecs[url] = rspec_to_omnispec(urn,rspec)

        if omnispecs and omnispecs != {}:
            jspecs = json.dumps(omnispecs, indent=4)
            print jspecs
        return omnispecs
    
    
    def createsliver(self, args):
        if len(args) < 2:
            sys.exit('createsliver requires 2 args: slicename and rspec filename')

        name = args[0]

        # FIXME: Validate the slice name starts with
        # PREFIX+slice+

        urn = self.framework.slice_name_to_urn(name)
        slice_cred = self.framework.get_slice_cred(urn)

        # Load up the user's edited omnispec
        specfile = args[1]
        if not os.path.isfile(specfile):
            sys.exit('omnispec file of resources to request missing: %s' % specfile)

        jspecs = json.loads(file(specfile,'r').read())
        omnispecs = {}
        for url, spec_dict in jspecs.items():
            omnispecs[url] = OmniSpec('','',dictionary=spec_dict)
        
        
        # Copy the user config and read the keys from the files into the structure
        slice_users = copy(self.omni_config['slice_users'])
        for user in slice_users:
            newkeys = []
            required = ['name', 'urn', 'keys']
            for req in required:
                if not req in user:
                    raise Exception("%s in omni_config is not specified for user %s" % (req,user))

            for f in user['keys']:
                try:
                    newkeys.append(file(os.path.expanduser(f)).read())
                except Exception, exc:
                    logger = logging.getLogger('omni')
                    logger.debug("Failed to read user key from %s: %s", f, exc)
            user['keys'] = newkeys
        
        # Anything we need to allocate?
        for (url, ospec) in omnispecs.items():
            allocate = False
            for (_, r) in ospec.get_resources().items():
                if r.get_allocate():
                    allocate = True
                    break
                
            # Okay, send a message to the AM this resource came from
            if allocate:
                try:
                    client = make_client(url, self.frame_config['key'], self.frame_config['cert'])
                    rspec = omnispec_to_rspec(ospec, True)
                    result = client.CreateSliver(urn, [slice_cred], rspec, slice_users)
                    print result
                except Exception, exc:
                    print "Unable to allocate from: %s" % (url)
                    logger = logging.getLogger('omni')
                    logger.debug(str(exc))
            else:
                logger = logging.getLogger('omni')
                logger.debug('Nothing to allocate at %r', url)

    def deletesliver(self, args):
        if len(args) == 0:
            sys.exit('deletesliver requires arg of slice name')

        name = args[0]

        # FIXME: Validate the slice name starts with
        # PREFIX+slice+

        urn = self.framework.slice_name_to_urn(name)
        slice_cred = self.framework.get_slice_cred(urn)
        # Connect to each available GENI AM 
        for client in self._getclients():
            try:
                client.DeleteSliver(urn, [slice_cred])
            except Exception, exc:
                print "Failed to delete sliver %s on %s (%s)" %(urn, client.urn, client.url)
                logger = logging.getLogger('omni')
                logger.debug(str(exc))
            
    def renewsliver(self, args):
        if len(args) == 0:
            sys.exit('renewsliver requires arg of slice name')

        name = args[0]

        # FIXME: Validate the slice name starts with
        # PREFIX+slice+

        urn = self.framework.slice_name_to_urn(name)
        slice_cred = self.framework.get_slice_cred(urn)
        time = dateutil.parser.parse(args[1])
        print time        

        for client in self._getclients():
            try:
                client.RenewSliver(urn, [slice_cred], time.isoformat())
            except:
                print "Failed to renew sliver %s on %s" % (urn, client.urn)
    
    def sliverstatus(self, args):
        if len(args) == 0:
            sys.exit('sliverstatus requires arg of slice name')

        name = args[0]

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
                print "Failed to retrieve status of %s at %s" % (urn, client.urn)
                logger = logging.getLogger('omni')
                logger.debug(str(exc))
                
    def shutdown(self, args):
        if len(args) == 0:
            sys.exit('shutdown requires arg of slice name')

        name = args[0]

        # FIXME: Validate the slice name starts with
        # PREFIX+slice+

        urn = self.framework.slice_name_to_urn(name)
        slice_cred = self.framework.get_slice_cred(urn)
        for client in self._getclients():
            try:
                client.Shutdown(urn, [slice_cred])
            except:
                print "Failed to shutdown %s: %s at %s" % (urn, client.urn, client.url)
    
    def getversion(self, args):
        for client in self._getclients():
            try:
                print "%s (%s) %s" % (client.urn, client.url, client.GetVersion())
            except:
                print "Failed to get version information for %s at (%s)" % (client.urn, client.url)
                                
    def createslice(self, args):
        if len(args) == 0:
            sys.exit('createslice requires arg of slice name')

        name = args[0]

        # FIXME: Validate the slice name starts with
        # PREFIX+slice+

        urn = self.framework.slice_name_to_urn(name)
        self.framework.create_slice(urn)
        
    def deleteslice(self, args):
        if len(args) == 0:
            sys.exit('deleteslice requires arg of slice name')

        name = args[0]

        # FIXME: Validate the slice name starts with
        # PREFIX+slice+

        urn = self.framework.slice_name_to_urn(name)
        self.framework.delete_slice(urn)

    def getslicecred(self, args):
        if len(args) == 0:
            sys.exit('getslicecred requires arg of slice name')

        name = args[0]

        # FIXME: Validate the slice name starts with
        # PREFIX+slice+

        urn = self.framework.slice_name_to_urn(name)
        cred = self.framework.get_slice_cred(urn)
        print cred


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
    # Load up the JSON formatted config file
    filename = os.path.expanduser(opts.configfile)

    if not os.path.exists(filename):
        sys.exit('Missing omni config file %s' % filename)

    logger.debug("Loading config file %s", filename)
    config = json.loads(file(filename, 'r').read())
        
    if not opts.framework:
        opts.framework = config['omni']['default_cf']

    logger.info( 'Using control framework %s' % opts.framework)
        
    # Dynamically load the selected control framework
    cf = opts.framework.lower()
    if config[cf] is None:
        sys.exit('Missing config for CF %s' % cf)

    framework_mod = __import__('geni.omni.frameworks.framework_%s' % cf, fromlist=['geni.omni.frameworks'])
    framework = framework_mod.Framework(config[cf])
        
    # Process the user's call
    handler = CallHandler(framework, config[cf], config['omni'])    
    handler._handle(args)
        
        
if __name__ == "__main__":
    sys.exit(main())
