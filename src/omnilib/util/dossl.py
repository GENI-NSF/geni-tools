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
"""
   Utility function wrapping SSL calls to catch SSL/OpenSSL/XMLRPC errors.
   Takes a framework which should have a logger and a cert filename.
   2nd args is a string in an error which should be at debug level not error.
"""

import logging
import OpenSSL
import ssl
import traceback
import xmlrpclib

from omnilib.util.faultPrinting import cln_xmlrpclib_fault


def _do_ssl(framework, suppresserror, reason, fn, *args):
    """ Attempts to make an xmlrpc call, and will repeat the attempt
    if it failed due to a bad passphrase for the ssl key.  Also does some
    exception handling.  Returns the xmlrpc return if everything went okay, 
    otherwise returns None."""
    
    # Change exception name?
    max_attempts = 2
    attempt = 0
        
    failMsg = "Call for %s failed." % reason
    while(attempt < max_attempts):
        attempt += 1
        try:
            result = fn(*args)
            return result
        except OpenSSL.crypto.Error, err:
            if str(err).find('bad decrypt') > -1:
                framework.logger.debug("Doing %s got %s", reason, err)
                framework.logger.error('Wrong pass phrase for private key.')
                if attempt < max_attempts:
                    framework.logger.info('.... please retry.')
                else:
                    framework.logger.error("Wrong pass phrase after %d tries" % max_attempts)
            else:
                framework.logger.error("%s: Unknown OpenSSL error %s" % (failMsg, err))
                if not framework.logger.isEnabledFor(logging.DEBUG):
                    framework.logger.error('    ..... Run with --debug for more information')
                framework.logger.debug(traceback.format_exc())

                return None
        except ssl.SSLError, exc:
            if exc.errno == 336265225:
                framework.logger.debug("Doing %s got %s", reason, exc)
                framework.logger.error('Wrong pass phrase for private key.')
                if attempt < max_attempts:
                    framework.logger.info('.... please retry.')
                else:
                    framework.logger.error("Wrong pass phrase after %d tries. Cannot do %s." % (max_attempts, reason))
                    return None
            elif exc.errno == 1 and exc.strerror.find("error:14094418") > -1:
                # Handle SSLError: [Errno 1] _ssl.c:480: error:14094418:SSL routines:SSL3_READ_BYTES:tlsv1 alert unknown ca
                import sfa.trust.gid as gid
                certiss = 'unknown'
                certsubj = 'unknown'
                try:
                    certObj = gid.GID(filename=framework.cert)
                    certiss = certObj.get_issuer()
                    certsubj = certObj.get_urn()
                except:
                    pass
                framework.logger.error("Can't do %s. Server does not trust the CA (%s) that signed your (%s) user certificate! Use an account at another clearinghouse or find another server.", reason, certiss, certsubj)
                if not framework.logger.isEnabledFor(logging.DEBUG):
                    framework.logger.error('    ..... Run with --debug for more information')
                framework.logger.debug(traceback.format_exc())
                return None
            else:
                framework.logger.error("%s: Unknown SSL error %s" % (failMsg, exc))
                if not framework.logger.isEnabledFor(logging.DEBUG):
                    framework.logger.error('    ..... Run with --debug for more information')
                framework.logger.debug(traceback.format_exc())

                return None
        except xmlrpclib.Fault, fault:
            framework.logger.error("%s Server says: %s" % (failMsg, cln_xmlrpclib_fault(fault)))
            return None
        except Exception, exc:
            if suppresserror and str(exc).find(suppresserror) > -1:
                # Suppress this error
                framework.logger.debug("Suppressing error doing %s: %s" % (failMsg, exc))
                framework.logger.debug(traceback.format_exc())
                return None
            framework.logger.error("%s: %s" % (failMsg, exc))
            if not framework.logger.isEnabledFor(logging.DEBUG):
                framework.logger.error('    ..... Run with --debug for more information')
            framework.logger.debug(traceback.format_exc())
            return None

