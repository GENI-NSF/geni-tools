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

from __future__ import absolute_import


import json
import logging
import optparse
import os
import sys
import xmlrpclib

from gcf.omnilib.util.dossl import _do_ssl
from gcf.omnilib.frameworks.framework_base import Framework_Base

# Dummy client of authorizer server to show what the arguments passed
# and return structures are

# For talking to CH SA to get credentials
# CH SA uses SSL XMLRPC
class ClientFramework(Framework_Base):
    def __init__(self, config, opts):
        Framework_Base.__init__(self, config)
        self.config = config
        self.logger = logging.getLogger('client')
        self.fwtype = "Ciient"
        self.opts = opts

# Get slice credential for user on given slice from CH SA
def get_credentials(opts):
    config = {'cert' : opts.cert, 'key' : opts.key}
    framework = ClientFramework(config, {})
    suppress_errors = None
    reason = "Testing"
    ch_client = framework.make_client(opts.ch_url, opts.key, opts.cert, 
                                   allow_none=True,
                                   verbose=False)
    (result, msg) = _do_ssl(framework, suppress_errors, reason, 
                            ch_client.get_credentials, opts.slice_urn, [], {})
    cred = result['value'][0]['geni_value']
    creds = [cred]
    return creds

# Parse command line arguments
def parse_args(argv):
    parser = optparse.OptionParser()
    parser.add_option("--url", help="Authorizer Server URL", default=None)
    parser.add_option("--ch_url", help="CH SA URL", default=None)
    parser.add_option("--cert", help="User SSL cert filename", default=None)
    parser.add_option("--key", help="User SSL key filename", default=None)
    parser.add_option("--slice_urn", help="URN of slice against which to allocate", default=None)

    [opts, args] = parser.parse_args(argv)

    if opts.url == None or opts.ch_url == None or opts.cert == None \
            or opts.key == None or opts.slice_urn == None:
            parser.print_help()
            sys.exit()

    return opts

# Run a simple client against the authorization server
def main():

    opts = parse_args(sys.argv)

    cert = open(opts.cert, 'r').read()

    creds = get_credentials(opts)

    client = xmlrpclib.Server(opts.url)
    
    # I'm hard-coding a call for createsliver. There are also issues around renew to consider.
    method = "CreateSliver_V2"
    args = {'slice_urn' : opts.slice_urn }
    opts = {'geni_am_urn' : 'https://foo.example.com'}

    # This is the TOTAL (current + requested) allocation state per user/slice
    # Returned by resource_manager.get_requested_allocation_state
    requested_allocation_state = [
        {'sliver_urn' : '',
         'slice_urn' : 'urn:publicid:IDN+ch-mb.gpolab.bbn.com:COUNT+slice+THREE',
         'user_urn' : 'urn:publicid:IDN+ch-mb.gpolab.bbn.com+user+mbrinn',
         'start_time' : '5/29/2015 01:00',
         'end_time' : '5/31/2015 23:00',
         'measurements' : {'NODE' : 3}
         },
        {'sliver_urn' : '',
         'slice_urn' : 'urn:publicid:IDN+ch-mb.gpolab.bbn.com:COUNT+slice+FOUR',
         'user_urn' : 'urn:publicid:IDN+ch-mb.gpolab.bbn.com+user+ahelsing',
         'start_time' : '5/29/2015 01:00',
         'end_time' : '5/31/2015 23:00',
         'measurements' : {'NODE' : 4}
         }
    ]

    result = client.validate_arguments(method, args, opts)
    print "VALIDATE_ARGUMENTS.RESULT = %s" % result 
    result = client.authorize(method, cert, creds, args, opts,
                            requested_allocation_state)
    # Should print NONE if authorized. Raises exception if not
    print "AUTHORIZE.RESULT = %s" % result 

    
    

if __name__ == "__main__":
    sys.exit(main())
