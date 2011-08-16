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

"""
   Utility function wrapping SSL calls to catch SSL/OpenSSL/XMLRPC errors.
   Takes a framework which should have a logger and a cert filename.
   2nd arg is a list of strings in an error which should be at debug level not error.
"""

import logging
import OpenSSL
import socket
import ssl
import traceback
import xmlrpclib
import sfa.trust.gid as gid

from omnilib.util.omnierror import OmniError

from omnilib.util.faultPrinting import cln_xmlrpclib_fault


def _do_ssl(framework, suppresserrors, reason, fn, *args):
    """ Attempts to make an xmlrpc call, and will repeat the attempt
    if it failed due to a bad passphrase for the ssl key.  Also does some
    exception handling.  Returns: (1) the xmlrpc return if everything went okay,
    otherwise returns None. And (2) A message explaining any errors."""

    # Change exception name?
    max_attempts = 2
    attempt = 0

    failMsg = "Call for %s failed." % reason
    while(attempt <= max_attempts):
        attempt += 1
        try:
            result = fn(*args)
            return (result, "")
        except OpenSSL.crypto.Error, err:
            if str(err).find('bad decrypt') > -1:
                framework.logger.debug("Doing %s got %s", reason, err)
                framework.logger.error('Wrong pass phrase for private key.')
                if attempt <= max_attempts:
                    framework.logger.info('.... please retry.')
                else:
                    framework.logger.error("Wrong pass phrase after %d tries" % max_attempts)
#                    return (None, "Wrong pass phrase after %d tries." % max_attempts)
                    raise OmniError, "Wrong pass phrase after %d tries." % max_attempts
            else:
                framework.logger.error("%s: Unknown OpenSSL error %s" % (failMsg, err))
                if not framework.logger.isEnabledFor(logging.DEBUG):
                    framework.logger.error('    ..... Run with --debug for more information')
                framework.logger.debug(traceback.format_exc())

                return (None, "Unknown OpenSSL error %s" % err)
        except ssl.SSLError, exc:
            if exc.errno == 336265225:
                framework.logger.debug("Doing %s got %s", reason, exc)
                framework.logger.error('Wrong pass phrase for private key.')
                if attempt <= max_attempts:
                    framework.logger.info('.... please retry.')
                else:
                    framework.logger.error("Wrong pass phrase after %d tries. Cannot do %s." % (max_attempts, reason))
#                    return (None, "Wrong pass phrase after %d tries." % max_attempts)
                    raise OmniError, "Wrong pass phrase after %d tries." % max_attempts
            elif exc.errno == 1 and exc.strerror.find("error:14094418") > -1:
                # Handle SSLError: [Errno 1] _ssl.c:480: error:14094418:SSL routines:SSL3_READ_BYTES:tlsv1 alert unknown ca
                certiss = 'unknown'
                certsubj = 'unknown'
                try:
                    certObj = gid.GID(filename=framework.cert)
                    certiss = certObj.get_issuer()
                    certsubj = certObj.get_urn()
                except:
                    pass
                msg = "Server does not trust the CA (%s) that signed your (%s) user certificate! Use an account at another clearinghouse or find another server." % (certiss, certsubj)
                framework.logger.error("Can't do %s. %s", reason, msg)
                if not framework.logger.isEnabledFor(logging.DEBUG):
                    framework.logger.error('    ..... Run with --debug for more information')
                framework.logger.debug(traceback.format_exc())
                return (None, msg)
            elif exc.errno == 1 and exc.strerror.find("error:14094415") > -1:
                # user certificate expired
                expiredAt = None
                userURN = ""
                issuer = ""
                try:
                    certObj = gid.GID(filename=framework.cert)
                    userURN = certObj.get_urn()
                    issuer = str(certObj.get_issuer())
                    expiredAt = certObj.cert.get_notAfter()
                except:
                    pass
                msg = "Your user certificate %s has expired" % userURN
                if expiredAt:
                    msg += " at %s" % expiredAt
                msg += ". "
                if issuer.find("boss") == 0:
                    msg += "ProtoGENI users should log in to their account at the ProtoGENI website at http://%s and create and download a new certificate. " % issuer
                elif issuer.find("plc.") == 0:
                    msg += "PlanetLab users should email PlanetLab support (support@planet-lab.org) to get a new user certificate."
                else:
                    msg += "Contact your certificate issuer: %s. " % issuer
                    msg += "ProtoGENI users should log in to their SA website and create and download a new certificate. "
                    msg += "PlanetLab users should email PlanetLab support (support@planet-lab.org) to get a new user certificate."
                framework.logger.error("Can't do %s. %s", reason, msg)
                if not framework.logger.isEnabledFor(logging.DEBUG):
                    framework.logger.error('    ..... Run with --debug for more information')
                framework.logger.debug(traceback.format_exc())
                return (None, msg)
            else:
                msg = "Uknown SSL error %s" % exc
                framework.logger.error("%s: %s" % (failMsg, msg))
                if not framework.logger.isEnabledFor(logging.DEBUG):
                    framework.logger.error('    ..... Run with --debug for more information')
                framework.logger.debug(traceback.format_exc())
                return (None, msg)
        except xmlrpclib.Fault, fault:
            if suppresserrors:
                for suppresserror in suppresserrors:
                    if suppresserror and str(fault).find(suppresserror) > -1:
                        # Suppress this error
                        framework.logger.debug("Suppressing error doing %s: %s" % (failMsg, cln_xmlrpclib_fault(fault)))
                        framework.logger.debug(traceback.format_exc())
                        return (None, suppresserror)
            clnfault = cln_xmlrpclib_fault(fault)
            framework.logger.error("%s Server says: %s" % (failMsg, clnfault))
            if str(fault).find("try again later") > -1 and attempt <= max_attempts:
                import time
                pause = 10
                framework.logger.info(" ... pausing %d seconds and retrying ...." % pause)
                time.sleep(pause)
                continue
            else:
                return (None, clnfault)
        except socket.error, sock_err:
            if suppresserrors:
                for suppresserror in suppresserrors:
                    if suppresserror and str(sock_err).find(suppresserror) > -1:
                        # Suppress this error
                        framework.logger.debug("Suppressing error doing %s: %s" % (failMsg, sock_err))
                        framework.logger.debug(traceback.format_exc())
                        return (None, suppresserror)
            # Check for an M2Crypto timeout case, which manifests as socket error 115, 'Operation now in progress'
            if sock_err.errno == 115:
                framework.logger.debug("%s Operation timed out.", failMsg)
                return (None, "Operation timed out")
            else:
                framework.logger.error("%s: Unknown socket error: %s" % (failMsg, sock_err))
                if not framework.logger.isEnabledFor(logging.DEBUG):
                    framework.logger.error('    ..... Run with --debug for more information')
                framework.logger.debug(traceback.format_exc())
                return (None, str(sock_err))
        except Exception, exc:
            if suppresserrors:
                for suppresserror in suppresserrors:
                    if suppresserror and str(exc).find(suppresserror) > -1:
                        # Suppress this error
                        framework.logger.debug("Suppressing error doing %s: %s" % (failMsg, exc))
                        framework.logger.debug(traceback.format_exc())
                        return (None, suppresserror)
            msg = "%s: %s" % (exc.__class__.__name__, exc)
            framework.logger.error("%s: %s" % (failMsg, msg))
            if not framework.logger.isEnabledFor(logging.DEBUG):
                framework.logger.error('    ..... Run with --debug for more information')
            framework.logger.debug(traceback.format_exc())
            return (None, msg)
    return (None, "Unknown error")
