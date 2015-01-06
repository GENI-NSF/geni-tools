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
Simple test client for testing the GENI proxy AM that talks to the GENI Clearinghouse
(gch) and then to an aggregate manager (eg gcf-am).
Uses the proxy_aggregate_manager section of the gcf_config file.

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
import time
import uuid
import xml.dom.minidom as minidom
import xmlrpclib
import zlib

from gcf.geni.config import read_config
from gcf.omnilib.xmlrpc.client import make_client
import gcf.sfa.trust.credential as cred
import gcf.sfa.trust.gid as gid

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

def verify_rspec(rspec):
    # It should be parseable XML
    # The top level node should be named 'rspec'
    # The children of the top level node should all be named 'resource'
    dom = minidom.parseString(rspec)
    top = dom.documentElement
    if top.tagName.lower() != 'rspec':
        return None
    return dom

def test_create_sliver(server, slice_urn, slice_credential, dom):
#    print("SERVER = " + str(server));
#    print("URN = " + str(slice_urn));
#    print("SC = " + str(slice_credential));
#    print("DOM = " + str(dom));
    print 'Testing CreateSliver...',
    nodes = dom.getElementsByTagName('node')
#    print("NODES = " + str(nodes));
    some_available = False;
    # If there aren't any nodes that are available, error
    if (nodes.length == 0):
        # *** Should check if they are available
        print "No nodes available"
        return

    # Otherwise make an unbounded request
    # from src/gcf/geni/am/amapi2-request.xml
    request_rspec = \
'<?xml version="1.0" encoding="UTF-8"?>' + \
'<rspec xmlns="http://www.geni.net/resources/rspec/3"' + \
'       xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"' + \
'       xsi:schemaLocation="http://www.geni.net/resources/rspec/3 http://www.geni.net/resources/rspec/3/request.xsd"' + \
'       type="request">' + \
'  <node client_id="foo"/>' + \
'</rspec>'
#    print("REQUEST_RSPEC = " + str(request_rspec));
#    users = [{'key':''}]
    users = [];
    options = dict();
    result = server.CreateSliver(slice_urn, slice_credential,
                                         request_rspec, users, options)
#    print "MANIFEST_RSPEC = " + str(result);
    error_code = result['code']['geni_code']
    if (error_code != 0):
        print "CreateSliver failed " + str(result);
    else:
        print 'passed'

def test_delete_sliver(server, slice_urn, slice_credential):
    print 'Testing DeleteSliver...',
    options = dict()
    try:
        result = server.DeleteSliver(slice_urn, slice_credential, options)
#        print("DS.result = " + str(result))
        error_code = result['code']['geni_code'];
        if error_code != 0:
            print 'Delete Sliver failed';
        else:
            print 'passed'
    except xmlrpclib.Error, v:
        print 'ERROR', v

def test_sliver_status(server, slice_urn, credentials):
    should_retry = True;
    num_retries = 0;
    while (should_retry):
        result  = test_sliver_status_internal(server, slice_urn, credentials);
        should_retry = result['retry'];
        success = result['success'];
        if(should_retry == False):
            break;
        print "Busy ...", 
        time.sleep(10);
        num_retries = num_retries + 1;
        if (num_retries > 10):
            break;
    return success;

def test_sliver_status_internal(server, slice_urn, credentials):
    print 'Testing SliverStatus...',
    options = dict()
    result = server.SliverStatus(slice_urn, credentials, options)
    print "SS.RESULT = " + str(result)
    error_code = result['code']['geni_code']
    error_message = result['output'];
    if (error_code != 0):
        if ("resource is busy" in error_message):
            return {'retry':True, 'success':False};
        else:
            print "Sliver Status failed " + str(result);
            return {'retry':False, 'success':False};
    
    result = result['value']
#    import pprint
#    pprint.pprint(result)
    sliver_keys = frozenset(('geni_urn', 'geni_status', 'geni_resources'))
    resource_keys = frozenset(('geni_urn', 'geni_status', 'geni_error'))
    errors = list()
    missing = sliver_keys;
    if (type(result).__name__ == "dict"):
        missing = sliver_keys - set(result.keys())
    if missing:
        errors.append('missing keys %r' % (missing))
    if 'geni_resources' in result:
        for resource in result['geni_resources']:
            missing = resource_keys - set(resource.keys())
            if missing:
                errors.append('missing resource keys %r' % (missing))
    success=True;
    if errors:
        print 'failed'
        for x in errors:
            print '\t', x
        success=False;
    else:
        print 'passed'

    return {'retry': False, 'success': success }
        
    # Note expiration_time is in UTC
def test_renew_sliver(server, slice_urn, credentials, expiration_time):
    print 'Testing RenewSliver...',
    options = dict();
    result = server.RenewSliver(slice_urn, credentials, expiration_time, options)
#    print "RenewSliver.RESULT = " + str(result);
    if (result['code']['geni_code'] != 0):
        print "Renew Sliver failed " + str(result);

    result = result['value'];

    if result is True or result is False:
        print 'passed. (Result: %r)' % (result)
    else:
        print 'failed'
        print 'returned %r instead of boolean value' % (result)

def test_shutdown(server, slice_urn, credentials):
    print 'Testing Shutdown...',
    options = dict()
    result = server.Shutdown(slice_urn, credentials, options)
    if (result['code']['geni_code'] != 0):
        print "Shutdown failed " + str(result);
        return;

    result = result['value']
    if result is True or result is False:
        print 'passed'
    else:
        print 'failed'
        print 'returned %r instead of boolean value' % (result)

def test_get_version(server):
    print 'Testing GetVersion...',
    # This next throws exceptions on errors
    vdict = server.GetVersion()
    if vdict['geni_api'] == 2:
        print 'passed'
    else:
        print 'failed'

def test_list_resources(server, credentials, compressed=False, available=True,
                        slice_urn=None):
    print 'Testing ListResources...',
    options = dict(geni_compressed=compressed, geni_available=available)
    if slice_urn:
        options['geni_slice_urn'] = slice_urn
    rspec = server.ListResources(credentials, options)
#    print("TLR.rspec = " + str(rspec))
    if compressed:
        rspec = zlib.decompress(base64.b64decode(rspec))
    logging.getLogger('gcf-test').debug(rspec)
    dom = verify_rspec(rspec)
    if dom:
        print 'passed'
    else:
        print 'failed'
    return dom

def exercise_am(ch_server, am_server, certfile):

    # Get UUID out of certfile
    user_certstr = file(certfile, 'r').read()
    user_gid = gid.GID(string=user_certstr)
    user_uuid = str(uuid.UUID(int=user_gid.get_uuid()));

    # Create a project at the clearinghouse
    project_name = "Proj-" + str(uuid.uuid4());
    lead_id = user_uuid; 
    project_purpose = "DUMMY";
    project_result = ch_server.CreateProject(project_name, 
                                             lead_id, project_purpose);
    if(project_result['code'] != 0):
        print "Failed to create project " + str(project_result);
        return

    project_id = project_result['value'];
    print("PROJECT_RESULT = " + str(project_id));

    # Create a slice at the clearinghouse
    slice_name = "Slice-" + str(uuid.uuid4());
    slice_name = slice_name[:15]; # Can't have slice names too big
    slice_result = ch_server.CreateSlice(slice_name, project_id, user_uuid)
    if (slice_result['code'] != 0):
        print "Failed to create slice " + str(slice_result);
        return;
    slice_info = slice_result['value']
    slice_id = slice_info['slice_id']

    slice_credential_result = ch_server.GetSliceCredential(slice_id, user_certstr)
    if(slice_credential_result['code'] != 0):
        print "Failed to get slice credential " + str(slice_credential_result);
        return

    slice_cred_string = slice_credential_result['value']['slice_credential']
    slice_credential = cred.Credential(string=slice_cred_string)
    slice_gid = slice_credential.get_gid_object()
    slice_urn = slice_gid.get_urn()
    print 'Slice Creation SUCCESS: URN = %s' % (slice_urn)
    
    # Set up the array of credentials as just the slice credential
    credentials = [slice_cred_string]

    test_get_version(am_server)
    dom = test_list_resources(am_server, credentials)
    test_create_sliver(am_server, slice_urn, credentials, dom)
    test_sliver_status(am_server, slice_urn, credentials)
    test_list_resources(am_server, credentials, slice_urn=slice_urn)
    
    expiration = datetime.datetime.utcnow() + datetime.timedelta(days=1)
    test_renew_sliver(am_server, slice_urn, credentials, expiration)
    
    test_delete_sliver(am_server, slice_urn, credentials)
    
    # Test compression on list resources
    dom = test_list_resources(am_server, credentials, compressed=True,
                              available=False)

    # Now create a slice and shut it down instead of deleting it.
    slice_name = "Slice-" + str(uuid.uuid4());
    slice_name = slice_name[:15]; # Can't have slice names too big
    slice_result = ch_server.CreateSlice(slice_name, project_id, user_uuid)
    if(slice_result['code'] != 0):
        print "Failed to create slice " + str(slice_result);
        return

    slice_info = slice_result['value'];
    sllice_id = slice_info['slice_id']
    slice_credential_result = ch_server.GetSliceCredential(slice_id, user_certstr)
    if(slice_credential_result['code'] != 0):
        print "Failed to get slice credential " + str(slice_credential_result)
        return

    slice_cred_string = slice_credential_result['value']['slice_credential']
    slice_credential = cred.Credential(string=slice_cred_string)
    slice_gid = slice_credential.get_gid_object()
    slice_urn = slice_gid.get_urn()
    print 'Second Slice URN = %s' % (slice_urn)
    credentials = [slice_cred_string]
    dom = test_list_resources(am_server, credentials)
    test_create_sliver(am_server, slice_urn, credentials, dom)
    test_shutdown(am_server, slice_urn, credentials)

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
        host = config['geni clearinghouse']['host']
        port = config['geni clearinghouse']['port']
        if not host.startswith('http'):
            host = 'https://%s' % host.strip('/')
        url = "%s:%s/" % (host,port)
        setattr(opts,'ch',url)
        
    if getattr(opts,'am') is None:
        host = config['proxy aggregate_manager']['host']
        port = config['proxy aggregate_manager']['port']
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
        sys.exit("Proxy certfile %s doesn't exist" % certf)
    if not os.path.getsize(certf) > 0:
        sys.exit("Proxy certfile %s is empty" % certf)

    if not os.path.exists(keyf):
        sys.exit("Proxy keyfile %s doesn't exist" % keyf)
    if not os.path.getsize(keyf) > 0:
        sys.exit("Proxy keyfile %s is empty" % keyf)

    logger.info('CH Server is %s. Using keyfile %s, certfile %s', opts.ch, keyf, certf)
    logger.info('AM Server is %s. Using keyfile %s, certfile %s', opts.am, keyf, certf)
    ch_server = make_client(opts.ch, keyf, certf, opts.debug_rpc)
    am_server = make_client(opts.am, keyf, certf, opts.debug_rpc)
    exercise_am(ch_server, am_server, certf)

    return 0

if __name__ == "__main__":
    sys.exit(main())
