#!/usr/bin/env python

#----------------------------------------------------------------------
# Copyright (c) 2013-2015 Raytheon BBN Technologies
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
"Tools and utilities for talking to the stitching computation service."

from __future__ import absolute_import

import json
import os.path
import pprint
import sys
import urllib
import xmlrpclib

try:
    from .utils import StitchingError, StitchingServiceFailedError
    from ..xmlrpc.client import make_client

    from ..util.json_encoding import DateTimeAwareJSONDecoder
except:
    from gcf.omnilib.stitch.utils import StitchingError, StitchingServiceFailedError
    from gcf.omnilib.xmlrpc.client import make_client

    from gcf.omnilib.util.json_encoding import DateTimeAwareJSONDecoder

# Tags used in the options to the SCS
HOP_EXCLUSION_TAG = 'hop_exclusion_list'
HOP_INCLUSION_TAG = 'hop_inclusion_list'
GENI_PROFILE_TAG = 'geni_routing_profile'
GENI_PATHS_MERGED_TAG = 'geni_workflow_paths_merged'
ATTEMPT_PATH_FINDING_TAG = 'attempt_path_finding'

class Result(object):
    '''Hold and parse the raw result from the SCS'''
    CODE = 'code'
    VALUE = 'value'
    GENI_CODE = 'geni_code'
    OUTPUT = 'output'

    def __init__(self, xmlrpc_result):
        self.result = xmlrpc_result
    def isSuccess(self):
        return (self.CODE in self.result
                and self.GENI_CODE in self.result[self.CODE]
                and int(self.result[self.CODE][self.GENI_CODE]) == 0)
    def value(self):
        if self.VALUE in self.result:
            return self.result[self.VALUE]
        else:
            raise StitchingError("No value in result")
    def errorString(self):
        ret = ""
        if self.CODE in self.result:
            ret = str(self.result[self.CODE])
        if self.OUTPUT in self.result:
            ret +=" %s" % self.result[self.OUTPUT]
        return ret

class Service(object):
    def __init__(self, url, key=None, cert=None, timeout=None, verbose=False):
        self.url = url
        self.timeout=timeout
        self.verbose=verbose
        if isinstance(url, unicode):
            url2 = url.encode('ISO-8859-1')
        else:
            url2 = url
        type, uri = urllib.splittype(url2.lower())
        if type == "https":
            self.key=key
            self.cert=cert
        else:
            self.key=None
            self.cert=None

    def GetVersion(self, printResult=True):
        server = make_client(self.url, keyfile=self.key, certfile=self.cert, verbose=self.verbose, timeout=self.timeout)

        # As a sample of how to do make_client specifying the SSL version / ciphers (these are the defaults though):
#        import ssl
#        server = make_client(self.url, keyfile=self.key, certfile=self.cert, verbose=self.verbose, timeout=self.timeout, ssl_version=ssl.PROTOCOL_TLS, ciphers="HIGH:MEDIUM:!ADH:!SSLv2:!MD5:!RC4:@STRENGTH")

        try:
            result = server.GetVersion()
        except xmlrpclib.Error as v:
            if printResult:
                print "ERROR", v
            raise
        except Exception, e:
            if printResult:
                import traceback
                print "ERROR: %s" % traceback.format_exc()
            raise
        if printResult:
            print "GetVersion said:"
            pp = pprint.PrettyPrinter(indent=4)
            print pp.pformat(result)
        return result

    def ListAggregates(self, printResult=True):
        server = make_client(self.url, keyfile=self.key, certfile=self.cert, verbose=self.verbose, timeout=self.timeout)
        try:
            result = server.ListAggregates()
        except xmlrpclib.Error as v:
            if printResult:
                print "ERROR", v
            raise
        if printResult:
            print "ListAggregates said:"
            pp = pprint.PrettyPrinter(indent=4)
            print pp.pformat(result)
        return result

    def ComputePath(self, slice_urn, request_rspec, options, savedFile=None):
        """Invoke the XML-RPC service with the request rspec.
        Create an SCS PathInfo from the result.
        """
        result = None
        if savedFile and os.path.exists(savedFile) and os.path.getsize(savedFile) > 0:
            # read it in
            try:
                savedSCSResults = None
                with open(savedFile, 'r') as sfP:
                    savedStr = str(sfP.read())
                    result = json.loads(savedStr, encoding='ascii', cls=DateTimeAwareJSONDecoder)
            except Exception, e:
                import traceback
                print "ERROR", e, traceback.format_exc()
                raise
        if result is None:
            server = make_client(self.url, keyfile=self.key, certfile=self.cert, verbose=self.verbose, timeout=self.timeout)
            arg = dict(slice_urn=slice_urn, request_rspec=request_rspec,
                       request_options=options)
#        import json
#        print "Calling SCS with arg: %s" % (json.dumps(arg,
#                                                       ensure_ascii=True,
#                                                       indent=2))
            try:
                result = server.ComputePath(arg)
            except xmlrpclib.Error as v:
                print "ERROR", v
                raise

        self.result = result # save the raw result for stitchhandler to print
        geni_result = Result(result) # parse result
        if geni_result.isSuccess():
            return PathInfo(geni_result.value())
        else:
                # when there is no route I seem to get:
#{'geni_code': 3} MxTCE ComputeWorker return error message ' Action_ProcessRequestTopology_MP2P::Finish() Cannot find the set of paths for the RequestTopology. '.
            if self.result:
                raise StitchingServiceFailedError(None, self.result)
            else:
                raise StitchingServiceFailedError("ComputePath invocation failed: %s" % geni_result.errorString(), self.result)

class PathInfo(object):
    '''Hold the SCS expanded RSpec and workflow data'''
    SERVICE_RSPEC = 'service_rspec'
    WORKFLOW_DATA = 'workflow_data'
    DEPS = 'dependencies'
    def __init__(self, raw_result):
        self.raw = raw_result
        self.links = list()
        wd = raw_result[self.WORKFLOW_DATA]
        for link_name in wd:
            link = Link(link_name)
            link.parse_dependencies(wd[link_name][self.DEPS])
            self.links.append(link)
    def rspec(self):
        return self.raw[self.SERVICE_RSPEC]
    def workflow_data(self):
        return self.raw[self.WORKFLOW_DATA]
    def dump_workflow_data(self):
        """Print out the raw workflow data for debugging."""
        wd = self.raw[self.WORKFLOW_DATA]
        for link_name in wd:
            print "Link %r:" % (link_name)
            self.dump_link_data(wd[link_name], "  ")
    def dump_link_data(self, link_data, indent=""):
        print "%sDepends on:" % (indent)
        for d in link_data[self.DEPS]:
            self.dump_dependency(d, indent + "  ")
    def dump_dependency(self, dep_data, indent=""):
        keys = sorted(dep_data.keys())
        deps = []
        if self.DEPS in keys:
            deps = dep_data[self.DEPS]
            keys.remove(self.DEPS)
        for k in keys:
            print "%s%r: %r" % (indent, k, dep_data[k])
        if deps:
            print "%sDepends on:" % (indent)
            for d in deps:
                self.dump_dependency(d, indent + "  ")


class Dependency(object):
    '''A dependency of a stitching path (aka Link) from the workflow_data'''
    AGG_URN = 'aggregate_urn'
    AGG_URL = 'aggregate_url'
    DEPS = 'dependencies'
    IMPORT_VLANS = 'import_vlans'
    HOP_URN = 'hop_urn'
    def __init__(self, data):
        for k in (self.AGG_URN, self.AGG_URL, self.IMPORT_VLANS, self.HOP_URN):
            object.__setattr__(self, k, data[k])
        self.dependencies = list()
        if self.DEPS in data:
            for d in data[self.DEPS]:
                self.dependencies.append(Dependency(d))

class Link(object):
    '''A stitching path's entry in the workflow_data'''
    def __init__(self, name):
        self.name = name
        self.dependencies = list()
    def parse_dependencies(self, data):
        for d in data:
            self.dependencies.append(Dependency(d))

def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    # I2 SSL 
    SCS_URL = "https://geni-scs.net.internet2.edu:8443/geni/xmlrpc"
    # I2 non SSL (deprecated) SCS_URL = "http://geni-scs.net.internet2.edu:8081/geni/xmlrpc"
    # MAX SCS_URL (will go away) = "https://oingo.dragon.maxgigapop.net:8443/geni/xmlrpc"
    # Non SSL MAX SCS_URL (deprecated, will go away) = "http://oingo.dragon.maxgigapop.net:8081/geni/xmlrpc"
    # Test SCS (for untested AMs): https://nutshell.maxgigapop.net:8443/geni/xmlrpc
    # Non SSL Test SCS (deprecated): http://nutshell.maxgigapop.net:8081/geni/xmlrpc
    # Dev (usually down) SCS: http://geni.maxgigapop.net:8081/geni/xmlrpc

    # FIXME: Ideally we'd support loading your omni_config and finding the cert/key that way
    
    ind = -1
    printR = True
    listAMs = False
    keyfile=None
    certfile=None
    verbose = False
    timeout = None
    if "-h" in argv or "-?" in argv:
        print "Usage: scs.py [--scs_url <URL of SCS server if not standard (%s)] [--monitoring to suppress printouts] [--timeout SSL timeout in seconds] --key <path-to-trusted-key> --cert <path-to-trusted-client-cert>" % SCS_URL
        print "    Key and cert are not required for an SCS not running at an https URL."
        print "    Supply --listaggregates to list known AMs at the SCS instead of running GetVersion"
        print "    Supply --verbosessl to turn on detailed SSL logging"
        return 0
    for arg in argv:
        ind = ind + 1
        if ("--scs_url" == arg or "--scsURL" == arg) and (ind+1) < len(argv):
            SCS_URL = argv[ind+1]
        if "--monitoring" == arg:
            printR = False
        if arg.lower() == "--listaggregates":
            listAMs = True
        if ("--key" == arg or "--keyfile" == arg) and (ind+1) < len(argv):
            keyfile = argv[ind+1]
        if ("--cert" == arg or "--certfile" == arg) and (ind+1) < len(argv):
            certfile = argv[ind+1]
        if arg.lower() == "--verbosessl":
            verbose = True
        if arg.lower() == "--timeout" and (ind+1) < len(argv):
            timeout = float(argv[ind+1])

    if SCS_URL.lower().strip().startswith('https') and (keyfile is None or certfile is None):
        print "ERROR: When using an SCS with an https URL, you must supply the --key and --cert arguments to provide the paths to your key file and certificate"
        return 1

    if keyfile is not None:
        # Ensure have a good path for it
        if not os.path.exists(keyfile) or not os.path.getsize(keyfile) > 0:
            print "ERROR: Key file %s doesn't exist or is empty" % keyfile
            return 1
        keyfile = os.path.expanduser(keyfile)
    if certfile is not None:
        # Ensure have a good path for it
        if not os.path.exists(certfile) or not os.path.getsize(certfile) > 0:
            print "ERROR: Cert file %s doesn't exist or is empty" % certfile
            return 1
        certfile = os.path.expanduser(certfile)

    try:
        scsI = Service(SCS_URL, key=keyfile, cert=certfile, timeout=timeout, verbose=verbose)
        if listAMs:
            result = scsI.ListAggregates(printR)
        else:
            result = scsI.GetVersion(printR)
        tag = ""
        try:
            verStruct = result
            if verStruct and verStruct.has_key("value") and verStruct["value"].has_key("code_tag"):
                tag = verStruct["value"]["code_tag"]
        except:
            print "ERROR: SCS return not parsable"
            raise
        print "SUCCESS: SCS at ",SCS_URL, " is running version: ",tag
        return 0
    except Exception, e:
        print "ERROR: SCS at ",SCS_URL, " is down: ",e
        return 1

# To run this main, be sure to do:
# export PYTHONPATH=$PYTHONPATH:/path/to/gcf/src

if __name__ == "__main__":
  sys.exit(main())

