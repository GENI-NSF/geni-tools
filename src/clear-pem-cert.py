#!/usr/bin/python

#----------------------------------------------------------------------
# Copyright (c) 2011 Raytheon BBN Technologies
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

""" The clear-pem-cert.py script.
    This script is meant to help users to remove the passphrase from their 
    protogeni certificate.
"""

import string
import sys, os, shutil
from subprocess import Popen, PIPE
import optparse
import logging

logger = None

def parseArgs(argv):
    """Construct an Options Parser for parsing omni-configure command line
    arguments, and parse them.
    """

    parser = optparse.OptionParser()
    parser.add_option("-p", "--cert", default="~/.ssl/geni_cert.pem",
                      help="User certificate file location [DEFAULT: %default]", metavar="FILE")
    parser.add_option("-v", "--verbose", default=False, action="store_true",
                      help="Turn on verbose command summary for omni-configure script")

    if argv is None:
        # prints to stderr
        parser.print_help()
        return

    (opts, args) = parser.parse_args(argv)
    return opts

def configLogging(opts) :
    global logger
    level = logging.INFO
    if opts.verbose :
        level = logging.DEBUG

    logging.basicConfig(level=level)
    logger = logging.getLogger("clearcert")


def clearCert(certFile):
    global logger
    # Copy cert file to a new location
    certdir = os.path.dirname(certFile)
    certname = os.path.splitext(os.path.basename(certFile))[0]
    bakcertfile = os.path.join(certdir, certname + '_enc.pem')
    logger.info("Backup encrypted certificate file at: %s", bakcertfile)

    tmpcertfile = "%s.tmp" % certFile
    logger.debug("Using tmpcertfile: %s", tmpcertfile)
    shutil.copyfile(certFile, bakcertfile)

    logger.info("Removing passphrase from cert...")
    command = ['openssl', 'rsa']
    command.append('-in')
    command.append(certFile)
    command.append("-out")
    command.append(tmpcertfile)
    logger.debug("Run commnand: %s", command)
    p = Popen(command, stdout=PIPE)
    p.communicate()[0]
    if p.returncode != 0:
        shutil.move(bakcertfile, certFile)
        if os.path.exists(tmpcertfile):
            os.remove(tmpcertfile)
        raise Exception("Error removing passphrase from certificate")
    
    command = ['openssl', 'x509']
    command.append('-in')
    command.append(certFile)
    logger.debug("Run commnand: %s", command)
    p = Popen(command, stdout=PIPE)
    tmpcert = p.communicate()[0]
    if p.returncode != 0:
        shutil.move(bakcertfile, certFile)
        if os.path.exists(tmpcertfile):
            os.remove(tmpcertfile)
        raise Exception("Error removing passphrase from certificate")
    f = open(tmpcertfile,'a')
    f.write("%s" % tmpcert)
    f.close()
    logger.debug("Move tmpcertfile to certfile")
    shutil.move(tmpcertfile, certFile)
    logger.info("Change permissions of %s to 0400", certFile)
    os.chmod(certFile, 0400)

def main():
    global logger
    argv = sys.argv[1:]
    opts = parseArgs(argv)
    configLogging(opts)
    # Expand the cert file to a full path
    logger.debug("Running %s with options %s" %(sys.argv[0], opts))
    opts.cert= os.path.expanduser(opts.cert)
    if not os.path.exists(opts.cert):
        raise Exception("Certificate file %s does not exist" % opts.cert)
    clearCert(opts.cert)


if __name__ == "__main__":
    sys.exit(main())
 

