#----------------------------------------------------------------------
# Copyright (c) 2013 Raytheon BBN Technologies
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

import xmlrpclib

from utils import StitchingError, StitchingServiceFailedError

# Tags used in the options to the SCS
HOP_EXCLUSION_TAG = 'hop_exclusion_list'
GENI_PROFILE_TAG = 'geni_routing_profile'

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

# FIXME: Support authentication by the service at some point
class Service(object):
    def __init__(self, url):
        self.url = url

    def ComputePath(self, slice_urn, request_rspec, options):
        """Invoke the XML-RPC service with the request rspec.
        Create an SCS PathInfo from the result.
        """
        server = xmlrpclib.ServerProxy(self.url)
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
