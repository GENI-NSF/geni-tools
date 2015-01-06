#!/usr/bin/env python

#----------------------------------------------------------------------
# Copyright (c) 2011-2015 Raytheon BBN Technologies
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
Framework to run a GENI Aggregate Manager that is actually a thin proxy
to the 'real' GENI AM, using the GENI Clearinghouse to get the experimenter's
"inside" cert and key.
Configured with a new proxy aggregate_manager section of the gcf_config.
Uses only AM API v2

Run with "-h" flag to see usage and command line options.
"""

# NOTE: Treat this file as sample code. It is incomplete.

import sys

# Check python version. Requires 2.6 or greater, but less than 3.
if sys.version_info < (2, 6):
    raise Exception('Must use python 2.6 or greater.')
elif sys.version_info >= (3,):
    raise Exception('Not python 3 ready')

import logging
import optparse
import os

from gcf import geni
import gcf.geni.am
import gcf.geni.am.am2
import gcf.geni.am.proxyam
from gcf.geni.config import read_config

def parse_args(argv):
    parser = optparse.OptionParser()
    parser.add_option("-k", "--keyfile",
                      help="AM key file name", metavar="FILE")
    parser.add_option("-g", "--certfile",
                      help="AM certificate file name (PEM format)", metavar="FILE")
    parser.add_option("-c", "--configfile",  help="config file path", metavar="FILE")
    # Note: The trusted CH certificates are _not_ enough here.
    # It needs self signed certificates. EG CA certificates.
    parser.add_option("-r", "--rootcadir",
                      help="Trusted Root certificates directory (files in PEM format)", metavar="FILE")
    # Could try to determine the real IP Address instead of the loopback
    # using socket.gethostbyname(socket.gethostname())
    parser.add_option("-H", "--host", 
                      help="server ip", metavar="HOST")
    parser.add_option("-p", "--port", type=int, 
                      help="server port", metavar="PORT")
    parser.add_option("--debug", action="store_true", default=False,
                       help="enable debugging output")
    parser.add_option("-V", "--api-version", type=int,
                      help="AM API Version", default=2)
    return parser.parse_args()

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

def main(argv=None):
    if argv is None:
        argv = sys.argv
    opts = parse_args(argv)[0]
    level = logging.INFO
    if opts.debug:
        level = logging.DEBUG
    logging.basicConfig(level=level)

    # Read in config file options, command line gets priority
    optspath = None
    if not opts.configfile is None:
        optspath = os.path.expanduser(opts.configfile)

    config = read_config(optspath)   
        
    for (key,val) in config['proxy aggregate_manager'].items():                  
        if hasattr(opts,key) and getattr(opts,key) is None:
            setattr(opts,key,val)
        if not hasattr(opts,key):
            setattr(opts,key,val)
    if getattr(opts,'rootcadir') is None:
        setattr(opts,'rootcadir',config['global']['rootcadir'])        

#    print("CONFIG = " + str(config))
#    print("OPTS = " + str(opts))

    if opts.rootcadir is None:
        sys.exit('Missing path to trusted root certificate directory (-r argument)')
    
    # rootcadir is  dir of multiple certificates
    delegate = geni.ReferenceAggregateManager(getAbsPath(opts.rootcadir))

    # here rootcadir is supposed to be a single file with multiple
    # certs possibly concatenated together
    comboCertsFile = geni.CredentialVerifier.getCAsFileFromDir(getAbsPath(opts.rootcadir))

    am_host = getattr(opts,'am_host');
    am_port = getattr(opts,'am_port');
    am_url = "http://" + am_host + ":" + am_port + "/";
    if (hasattr(opts, 'am_url')):
        am_url = getattr(opts, 'am_url');

    certfile = getAbsPath(opts.certfile)
    keyfile = getAbsPath(opts.keyfile)
    if not os.path.exists(certfile):
        sys.exit("Proxy AM certfile %s doesn't exist" % certfile)
    if not os.path.getsize(certfile) > 0:
        sys.exit("Proxy AM certfile %s is empty" % certfile)

    if not os.path.exists(keyfile):
        sys.exit("Proxy AM keyfile %s doesn't exist" % keyfile)
    if not os.path.getsize(keyfile) > 0:
        sys.exit("Proxy AM keyfile %s is empty" % keyfile)

    logger = logging.getLogger('gcf-am');
    logger.info('Talking to AM ' + am_url);
    pams = gcf.geni.am.proxyam.ProxyAggregateManagerServer((opts.host, int(opts.port)),
                                                       am_url,
                                             keyfile=keyfile,
                                             certfile=certfile,
                                             trust_roots_dir=getAbsPath(opts.rootcadir),
                                             ca_certs=comboCertsFile,
                                             base_name=config['global']['base_name'])

    logger.info('GENI AM Listening on port %s...' % (opts.port))
    pams.serve_forever()

if __name__ == "__main__":
    sys.exit(main())
