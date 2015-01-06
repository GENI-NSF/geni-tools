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
Framework to run a GENI Clearinghouse. See geni/ch.py for the 
Reference Clearinghouse that this runs.

Run with "-h" flag to see usage and command line options.
"""

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
from gcf.geni.config import read_config
from gcf.geni.pgch import PGClearinghouse

config = None

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

class CommandHandler(object):
    
    # TODO: Implement a register handler to register aggregate managers
    # (persistently) so that a client could ask for the list of
    # aggregate managers.

    def runserver_handler(self, opts):
        """Run the clearinghouse server."""
        # Verify that opts.keyfile exists
        # Verify that opts.directory exists
        certfile = getAbsPath(opts.certfile)
        keyfile = getAbsPath(opts.keyfile)
        if not os.path.exists(certfile):
            sys.exit("Clearinghouse certfile %s doesn't exist" % certfile)
        if not os.path.getsize(certfile) > 0:
            sys.exit("Clearinghouse certfile %s is empty" % certfile)

        if not os.path.exists(keyfile):
            sys.exit("Clearinghouse keyfile %s doesn't exist" % keyfile)
        if not os.path.getsize(keyfile) > 0:
            sys.exit("Clearinghouse keyfile %s is empty" % keyfile)

        ch = PGClearinghouse((not opts.use_gpo_ch))
        # address is a tuple in python socket servers
        addr = (opts.host, int(opts.port))
        # rootcafile is turned into a concatenated file for Python SSL use inside ch.py
        ch.runserver(addr, keyfile, certfile,
                     getAbsPath(opts.rootcadir), config['global']['base_name'],
                     opts.user_cred_duration, opts.slice_duration, config)

def parse_args(argv):
    parser = optparse.OptionParser()
    parser.add_option("-k", "--keyfile", 
                      help="CH key file name", metavar="FILE")
    parser.add_option("-g", "--certfile",
                      help="CH certificate file name (PEM format)", metavar="FILE")
    parser.add_option("-c", "--configfile", default="gcf_config", help="config file path", metavar="FILE")
    # Note: A CH that only wants to talk to its own users doesn't need
    # this argument. It works if it just trusts its own cert.
    # Supplying this arg allows users of other frameworks to create slices on this CH.
    parser.add_option("-r", "--rootcadir", 
                      help="Root certificate directory name (files in PEM format)", metavar="FILE")
    # Could try to determine the real IP Address instead of the loopback
    # using socket.gethostbyname(socket.gethostname())
    parser.add_option("-H", "--host", 
                      help="server ip", metavar="HOST")
    parser.add_option("-p", "--port", type=int, 
                      help="server port", metavar="PORT")
    parser.add_option("--debug", action="store_true", default=False,
                       help="enable debugging output")
    parser.add_option("--user_cred_duration", default=geni.pgch.USER_CRED_LIFE, metavar="SECONDS",
                      help="User credential lifetime in seconds (default %d)" % geni.pgch.USER_CRED_LIFE)
    parser.add_option("--slice_duration", default=geni.pgch.SLICE_CRED_LIFE, metavar="SECONDS",
                      help="Slice lifetime in seconds (default %d)" % geni.pgch.SLICE_CRED_LIFE)
    parser.add_option("--use-gpo-ch", default=False, action="store_true",
                      help="Use remote GPO Clearinghouse (default False) or the local GCF Clearinghouse")
    return parser.parse_args()

def main(argv=None): 
    if argv is None:
        argv = sys.argv
    opts, args = parse_args(argv)

    level = logging.INFO
    if opts.debug:
        level = logging.DEBUG
    logging.basicConfig(level=level)
    if not args:
        args = ('runserver',)

    handler = '_'.join((args[0], 'handler'))

    # Read in config file options, command line gets priority
    global config
    optspath = None
    if not opts.configfile is None:
        optspath = os.path.expanduser(opts.configfile)

    config = read_config(optspath)   

    for (key,val) in config['clearinghouse'].items():
        if hasattr(opts,key) and getattr(opts,key) is None:
            setattr(opts,key,val)
        if not hasattr(opts,key):
            setattr(opts,key,val)
    if getattr(opts,'rootcadir') is None:
        setattr(opts,'rootcadir',config['global']['rootcadir'])
    config['debug'] = opts.debug

    ch = CommandHandler()        
    if hasattr(ch, handler):
        return getattr(ch, handler)(opts)
    else:
        print >> sys.stderr, 'Unknown command ', args[0]

if __name__ == "__main__":
    sys.exit(main())
