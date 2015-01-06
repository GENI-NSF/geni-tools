#!/usr/bin/env python

#----------------------------------------------------------------------
# Copyright (c) 2010-2015 Raytheon BBN Technologies
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
Simple test client for testing the GENI GCF Clearinghouse and 
AggregateManager.

Run with "-h" flag to see usage and command line options.
"""

import sys

# Check python version. Requires 2.6 or greater, but less than 3.
if sys.version_info < (2, 6):
    raise Exception('Must use python 2.6 or greater.')
elif sys.version_info >= (3,):
    raise Exception('Not python 3 ready')

import base64
import datetime
import logging
import optparse
import os
import random
import xml.dom.minidom as minidom
import xmlrpclib
import zlib
from gcf.geni.config import read_config
from gcf.omnilib.xmlrpc.client import make_client
import gcf.sfa.trust.credential as cred

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

def exercise_ch(host, port, keyfile, certfile):
    url = 'https://%s' % (host)
    if port:
        url = '%s:%s' % (url, port)
    server = make_client(url, keyfile, certfile)
    print server
    try:
        print server.GetVersion()
    except xmlrpclib.Error, v:
        print 'ERROR', v
    try:
        print server.CreateSlice()
    except xmlrpclib.Error, v:
        print 'ERROR', v

def verify_rspec(rspec):
    # It should be parseable XML
    # The top level node should be named 'rspec'
    # The children of the top level node should all be named 'resource'
    dom = minidom.parseString(rspec)
    top = dom.documentElement
    if top.tagName.lower() != 'rspec':
        return None
    return dom

def test_create_sliver(server, slice_urn, slice_credential, dom, api_version=2):
    if api_version < 3:
        print 'Testing CreateSliver...',
    else:
        print 'Testing Allocate...',
    options = None
    if api_version >= 2:
        options = dict()
        # FIXME: Build up a request_rspec for real
        nodes = dom.getElementsByTagName('node')
        dom_impl = minidom.getDOMImplementation()
        request_rspec = dom_impl.createDocument("http://www.geni.net/resources/rspec/3", 'rspec', None)
        top = request_rspec.documentElement
        top.setAttribute("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
        top.setAttribute("xsi:schemaLocation", "http://www.geni.net/resources/rspec/3 http://www.geni.net/resources/rspec/3/request.xsd")
        top.setAttribute("xmlns", "http://www.geni.net/resources/rspec/3")
        top.setAttribute("type", "request")
        if nodes.length == 0:
            print 'failed: no nodes available'
            return
        elif nodes.length == 1:
            top.appendChild(nodes.item(0).cloneNode(True))
        else:
            # pick two at random
            indices = range(nodes.length)
            for _ in range(2):
                index = random.choice(indices)
                indices.remove(index)
                top.appendChild(nodes.item(index).cloneNode(True))
    else:
        resources = dom.getElementsByTagName('resource')
        dom_impl = minidom.getDOMImplementation()
        request_rspec = dom_impl.createDocument(None, 'rspec', None)
        top = request_rspec.documentElement
        if resources.length == 0:
            print 'failed: no resources available'
            return
        elif resources.length == 1:
            top.appendChild(resources.item(0).cloneNode(True))
        else:
            # pick two at random
            indices = range(resources.length)
            for _ in range(2):
                index = random.choice(indices)
                indices.remove(index)
                top.appendChild(resources.item(index).cloneNode(True))
    users = [{'key':''}]
    if options is not None:
        try:
            if api_version < 3:
                result = server.CreateSliver(slice_urn, slice_credential,
                                             request_rspec.toxml(), users, options)
            else:
                result = server.Allocate(slice_urn, slice_credential,
                                             request_rspec.toxml(), options)
        except Exception, e:
            print "failed: %s" % e
            return
    else:
        try:
            result = server.CreateSliver(slice_urn, slice_credential,
                                     request_rspec.toxml(), users)
        except Exception, e:
            print "failed: %s" % e
            return
    if api_version >= 2:
        if not isinstance(result, dict):
            print 'failed'
            print 'didnt get APIV2 dict'
            return
        if not result.has_key('value'):
            print 'failed'
            print 'missing value'
            return
        if api_version > 2:
            if not isinstance(result['value'], dict):
                print 'failed: value not a dict'
                return
            elif not result['value'].has_key('geni_rspec'):
                print 'failed: result value had no geni_rspec'
                return
            manifest_rspec = result['value']['geni_rspec']
        else:
            manifest_rspec = result['value']
    else:
        manifest_rspec = result
    # TODO: verify manifest_rspec
    logging.getLogger('gcf-test').debug(manifest_rspec)
    print 'passed'

def test_delete_sliver(server, slice_urn, slice_credential, api_version=2):
    print 'Testing DeleteSliver...',
    options = None
    if api_version >= 2:
        options = dict()
    try:
        if options is not None:
            if api_version > 2:
                result = server.Delete([slice_urn], slice_credential, options)
            else:
                result = server.DeleteSliver(slice_urn, slice_credential, options)
        else:
            result = server.DeleteSliver(slice_urn, slice_credential)
        if api_version >= 2:
            if not isinstance(result, dict):
                print 'failed'
                print 'didnt get APIV2 dict'
                return
            if not result.has_key('value'):
                print 'failed'
                print 'missing value'
                return
            if api_version > 2:
                if not result.has_key('code') or not result['code'].has_key('geni_code') or not result['code']['geni_code'] == 0:
                    print 'failed: %r' % result
                    return
                else:
                    result = True
            else:
                result = result['value']
        if result is True:
            print 'passed'
        else:
            print 'failed'
    except xmlrpclib.Error, v:
        print 'ERROR', v

def test_sliver_status(server, slice_urn, credentials, api_version=2):
    print 'Testing SliverStatus...',
    options = None
    if api_version >= 2:
        options = dict()
        if api_version == 2:
            result = server.SliverStatus(slice_urn, credentials, options)
        else:
            result = server.Status([slice_urn], credentials, options)
    else:
        result = server.SliverStatus(slice_urn, credentials)

    if api_version >= 2:
        if not isinstance(result, dict):
            print 'failed'
            print 'didnt get APIV2 dict'
            return
        if not result.has_key('value'):
            print 'failed'
            print 'missing value'
            return
        if not result.has_key('code') or not result['code'].has_key('geni_code'):
            print 'failed - no geni_code'
            return
        if not result['code']['geni_code'] == 0:
            print 'failed: %r' % result
            return
        result = result['value']
#    import pprint
#    pprint.pprint(result)
    status_keys = frozenset(('geni_urn', 'geni_status', 'geni_resources'))
    if api_version > 2:
        status_keys = frozenset(('geni_urn', 'geni_slivers'))
    resource_keys = frozenset(('geni_urn', 'geni_status', 'geni_error'))
    sliver_keys = frozenset(('geni_sliver_urn', 'geni_allocation_status', 'geni_operational_status', 'geni_expires', 'geni_error'))
    errors = list()
    missing = status_keys - set(result.keys())
    if missing:
        errors.append('missing top level keys %r' % (missing))
    if 'geni_resources' in result:
        for resource in result['geni_resources']:
            missing = resource_keys - set(resource.keys())
            if missing:
                errors.append('missing resource keys %r' % (missing))
    elif 'geni_slivers' in result:
        for resource in result['geni_slivers']:
            missing = sliver_keys - set(resource.keys())
            if missing:
                errors.append('missing sliver keys %r' % (missing))
    if errors:
        print 'failed'
        for x in errors:
            print '\t', x
    else:
        print 'passed'
        
    # Note expiration_time is in UTC
def test_renew_sliver(server, slice_urn, credentials, expiration_time, api_version=2):
    print 'Testing RenewSliver...',
    options = None
    if api_version >= 2:
        options = dict()
        if api_version == 2:
            result = server.RenewSliver(slice_urn, credentials, expiration_time, options)
        else:
            result = server.Renew([slice_urn], credentials, expiration_time, options)
    else:
        result = server.RenewSliver(slice_urn, credentials, expiration_time)
#    print 'renew returned: %r' % result
    if api_version >= 2:
        if not isinstance(result, dict):
            print 'failed'
            print 'didnt get APIV2 dict'
            return
        if not result.has_key('value'):
            print 'failed'
            print 'missing value'
            return
        if not result.has_key('code'):
            print 'failed'
            print 'missing code'
            return
        if not result['code'].has_key('geni_code'):
            print 'failed'
            print 'missing geni_code'
            return
        if result['code']['geni_code'] == 0 and (api_version > 2 or (result['value'] is True or result['value'] is False)):
            print 'passed'
            return
        elif result['code']['geni_code'] != 0:
            # If you request an expiration too far past the slice cred expiration,
            # this should fail. And that's actually OK for our purposes
            print 'passed. (Result code: %r, output: %s)' % (result['code'], result['output'])
            return
        else:
            print 'failed'
            print 'returned %r instead of boolean value' % (result)
            return
    if result is True or result is False:
        print 'passed. (Result: %r)' % (result)
    else:
        print 'failed'
        print 'returned %r instead of boolean value' % (result)

def test_shutdown(server, slice_urn, credentials, api_version=2):
    print 'Testing Shutdown...',
    options = None
    if api_version >= 2:
        options = dict()
        result = server.Shutdown(slice_urn, credentials, options)
    else:
        result = server.Shutdown(slice_urn, credentials)
    if api_version >= 2:
        if not isinstance(result, dict):
            print 'failed'
            print 'didnt get APIV2 dict'
            return
        if not result.has_key('value'):
            print 'failed'
            print 'missing value'
            return
        result = result['value']
    if result is True or result is False:
        print 'passed'
    else:
        print 'failed'
        print 'returned %r instead of boolean value' % (result)

def test_get_version(server, api_version=2):
    print 'Testing GetVersion...',
    # This next throws exceptions on errors
    options = None
    if api_version >= 2:
        options = dict()
        try:
            vdict = server.GetVersion(options)
        except Exception, e:
            if 'GetVersion() takes exactly 1 argument' in str(e):
                print 'failed: Used API V%d but AM talks v1: %s' % (api_version, e)
            print 'failed: %s' % e
            return
    else:
        try:
            vdict = server.GetVersion()
        except Exception, e:
            print 'failed: %s' % e
            return
    if vdict['geni_api'] == api_version:
        print 'passed'
    else:
        print 'failed: expected API V%d, got V%d' % (api_version, vdict['geni_api'])

def test_list_resources(server, credentials, compressed=False, available=True,
                        slice_urn=None, apiver=2):
    if apiver > 2 and slice_urn:
        print 'Testing Describe...',
    else:
        print 'Testing ListResources...',
    if apiver == 1:
        options = dict(geni_compressed=compressed, geni_available=available)
    else:
        options = dict(geni_compressed=compressed, geni_available=available, geni_rspec_version=(dict(type="geni", version="3")))
    if slice_urn:
        options['geni_slice_urn'] = slice_urn
    if apiver > 2 and slice_urn:
        res = server.Describe([slice_urn], credentials, options)
    else:
        res = server.ListResources(credentials, options)
    if apiver == 1:
        rspec = res
        if not isinstance(rspec, str):
            print 'failed: Result not a string. Got %r' % rspec
            if isinstance(rspec, dict) and rspec.has_key('value') and rspec['value'] is not None and rspec['value'].strip() != '':
                rspec = rspec['value']
                if compressed:
                    rspec = zlib.decompress(base64.b64decode(rspec))
                return verify_rspec(rspec)
            return None
    else:
        if res is None or not isinstance(res, dict) or not res.has_key('value'):
            print 'failed: Result %r' % (res)
            return None
        if not res.has_key('code') or not isinstance(res['code'], dict):
            print 'failed: Result %r' % (res)
            return None
        if res['code'].has_key('geni_code') and res['code']['geni_code'] != 0:
            print 'failed: Result %r' % (res)
            return None
        if apiver == 2 or not slice_urn:
            rspec = res['value']
        else:
            rspec = res['value']['geni_rspec']
    if compressed:
        rspec = zlib.decompress(base64.b64decode(rspec))
    logging.getLogger('gcf-test').debug(rspec)
    try:
        dom = verify_rspec(rspec)
    except Exception, e:
        print "Failed to verify RSpec: %s" % e
        return None
    if dom:
        print 'passed'
    else:
        print 'failed'
    return dom

def exercise_am(ch_server, am_server, api_version=2):
    # Create a slice at the clearinghouse
    slice_cred_string = ch_server.CreateSlice()
    slice_credential = cred.Credential(string=slice_cred_string)
    slice_gid = slice_credential.get_gid_object()
    slice_urn = slice_gid.get_urn()
    print 'Slice Creation SUCCESS: URN = %s' % (slice_urn)
    
    # Set up the array of credentials as just the slice credential
    credentials = [slice_cred_string]
    if api_version > 2:
        # wrap the credential
        credentials = [dict(geni_type=cred.Credential.SFA_CREDENTIAL_TYPE, 
                            geni_version="3", geni_value=slice_cred_string)]

    test_get_version(am_server, api_version)
    dom = test_list_resources(am_server, credentials, apiver=api_version)
    if dom is None:
        print 'No Ad RSpec - cannot create a sliver'
    else:
        test_create_sliver(am_server, slice_urn, credentials, dom, api_version)
        test_sliver_status(am_server, slice_urn, credentials, api_version)
        test_list_resources(am_server, credentials, slice_urn=slice_urn, apiver=api_version)

        expiration = datetime.datetime.utcnow() + datetime.timedelta(seconds=1800)
        test_renew_sliver(am_server, slice_urn, credentials, expiration, api_version)

        test_delete_sliver(am_server, slice_urn, credentials, api_version)
    
    # Test compression on list resources
    dom = test_list_resources(am_server, credentials, compressed=True,
                              available=False, apiver=api_version)

    # Now create a slice and shut it down instead of deleting it.
    slice_cred_string = ch_server.CreateSlice()
    slice_credential = cred.Credential(string=slice_cred_string)
    slice_gid = slice_credential.get_gid_object()
    slice_urn = slice_gid.get_urn()
    print 'Second Slice URN = %s' % (slice_urn)
    credentials = [slice_cred_string]
    if api_version > 2:
        # wrap the credential
        credentials = [dict(geni_type=cred.Credential.SFA_CREDENTIAL_TYPE, 
                            geni_version="3", geni_value=slice_cred_string)]
    dom = test_list_resources(am_server, credentials, apiver=api_version)
    if dom is None:
        print 'No Ad RSpec - cannot create a sliver'
    else:
        test_create_sliver(am_server, slice_urn, credentials, dom, api_version)
        test_shutdown(am_server, slice_urn, credentials, api_version)

def parse_args(argv):
    parser = optparse.OptionParser()
    parser.add_option("-k", "--keyfile",
                      help="experimenter key file name", metavar="FILE")
    parser.add_option("-g", "--certfile",
                      help="experimenter certificate file name", metavar="FILE")
    parser.add_option("-c", "--configfile",  help="config file path", metavar="FILE")
    
    parser.add_option("--ch", 
                      help="clearinghouse URL")
    parser.add_option("--am",
                      help="aggregate manager URL")
    parser.add_option("--debug", action="store_true", default=False,
                       help="enable debugging output")
    parser.add_option("--debug-rpc", action="store_true", default=False,
                      help="enable XML RPC debugging")
    parser.add_option("-V", "--api-version", type=int,
                      help="AM API Version", default=2)
    return parser.parse_args()

def main(argv=None):
    if argv is None:
        argv = sys.argv
    opts = parse_args(argv)[0]
    level = logging.INFO
    if opts.debug:
        level = logging.DEBUG
        
    # Read in config file options, command line gets priority
    global config
    optspath = None
    if not opts.configfile is None:
        optspath = os.path.expanduser(opts.configfile)

    config = read_config(optspath)  
        
    for (key,val) in config['gcf-test'].items():
        if hasattr(opts,key) and getattr(opts,key) is None:
            setattr(opts,key,val)
        if not hasattr(opts,key):
            setattr(opts,key,val)      
    
    # Determine the AM and CH hostnames from the config file
    if getattr(opts,'ch') is None:
        host = config['clearinghouse']['host']
        port = config['clearinghouse']['port']
        if not host.startswith('http'):
            host = 'https://%s' % host.strip('/')
        url = "%s:%s/" % (host,port)
        setattr(opts,'ch',url)
        
    if getattr(opts,'am') is None:
        host = config['aggregate_manager']['host']
        port = config['aggregate_manager']['port']
        if not host.startswith('http'):
            host = 'https://%s' % host.strip('/')
        url = "%s:%s/" % (host,port)
        setattr(opts,'am',url)

            
                    
    logging.basicConfig(level=level)
    logger = logging.getLogger('gcf-test')
    if not opts.keyfile or not opts.certfile:
        sys.exit('Missing required arguments -k for Key file and -c for cert file')

    keyf = getAbsPath(opts.keyfile)
    certf = getAbsPath(opts.certfile)
    if not os.path.exists(certf):
        sys.exit("Client certfile %s doesn't exist" % certf)
    if not os.path.getsize(certf) > 0:
        sys.exit("Client certfile %s is empty" % certf)
    
    if not os.path.exists(keyf):
        sys.exit("Client keyfile %s doesn't exist" % keyf)
    if not os.path.getsize(keyf) > 0:
        sys.exit("Client keyfile %s is empty" % keyf)
#    print 'a_v: %d' % opts.api_version
    logger.info('CH Server is %s. Using keyfile %s, certfile %s', opts.ch, keyf, certf)
    logger.info('AM Server is %s. Using keyfile %s, certfile %s', opts.am, keyf, certf)
    ch_server = make_client(opts.ch, keyf, certf, opts.debug_rpc)
    am_server = make_client(opts.am, keyf, certf, opts.debug_rpc)
    exercise_am(ch_server, am_server, opts.api_version)

    return 0

if __name__ == "__main__":
    sys.exit(main())
