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
"""
   Utilities to parse credentials
"""

import datetime
import dateutil.parser
import logging
import traceback
import xml.dom.minidom as md

def is_valid_v3(logger, credString):
    '''Is the given credential a valid sfa style v3 credential?'''
# 1) Call:
#    sfa.trust.credential.cred.verify(trusted_certs=None, schema=FIXME, trusted_certs_required=False)
    # Will have to check in the xsd I think

# 2)
    # also for each cert:
    #   retrieve gid from cred
    #   check not expired
    #   check version is 3
    #   get email, urn, uuid - all not empty
    #   more? CA:TRUE/FALSE? real serialNum? Has a DN?
    #    if type is slice or user, CA:FALSE. It type is authority, CA:TRUE
    #   Should this be in gid.py? or in geni.util.cert_util?
    #

    return True

def get_cred_target_urn(logger, cred):
    '''Parse the given credential to get is target URN'''
    credString = get_cred_xml(cred)
    urn = ""

    if credString is None:
        return urn

    # If credString is not a string then complain and return
    if type(credString) != type('abc'):
        if logger is None:
            level = logging.INFO
            logging.basicConfig(level=level)
            logger = logging.getLogger("omni.credparsing")
            logger.setLevel(level)
        logger.error("Cannot parse target URN: Credential is not a string: %s", str(credString))
        return credexp

    try:
        doc = md.parseString(credString)
        signed_cred = doc.getElementsByTagName("signed-credential")

        # Is this a signed-cred or just a cred?
        if len(signed_cred) > 0:
            cred = signed_cred[0].getElementsByTagName("credential")[0]
        else:
            cred = doc.getElementsByTagName("credential")[0]

        targetnode = cred.getElementsByTagName("target_urn")[0]
        if len(targetnode.childNodes) > 0:
            urn = str(targetnode.childNodes[0].nodeValue)
    except Exception, exc:
        if logger is None:
            level = logging.INFO
            logging.basicConfig(level=level)
            logger = logging.getLogger("omni.credparsing")
            logger.setLevel(level)
        logger.error("Failed to parse credential for target URN: %s", exc)
        logger.info("Unparsable credential: %s", credString)
        logger.debug(traceback.format_exc())

    return urn

def get_cred_exp(logger, cred):
    '''Parse the given credential in GENI AM API XML format to get its expiration time and return that'''

    # Don't fully parse credential: grab the expiration from the string directly
    credexp = datetime.datetime.fromordinal(1)

    credString = get_cred_xml(cred)

    if credString is None:
        # failed to get a credential string. Can't check
        return credexp

    # If credString is not a string then complain and return
    if type(credString) != type('abc'):
        if logger is None:
            level = logging.INFO
            logging.basicConfig(level=level)
            logger = logging.getLogger("omni.credparsing")
            logger.setLevel(level)
        logger.error("Cannot parse expiration date: Credential is not a string: %s", str(credString))
        return credexp

    try:
        doc = md.parseString(credString)
        signed_cred = doc.getElementsByTagName("signed-credential")

        # Is this a signed-cred or just a cred?
        if len(signed_cred) > 0:
            cred = signed_cred[0].getElementsByTagName("credential")[0]
        else:
            cred = doc.getElementsByTagName("credential")[0]
        expirnode = cred.getElementsByTagName("expires")[0]
        if len(expirnode.childNodes) > 0:
            credexp = dateutil.parser.parse(expirnode.childNodes[0].nodeValue)
    except Exception, exc:
        if logger is None:
            level = logging.INFO
            logging.basicConfig(level=level)
            logger = logging.getLogger("omni.credparsing")
            logger.setLevel(level)
        logger.error("Failed to parse credential for expiration time: %s", exc)
        logger.info("Unparsable credential: %s", credString)
        logger.debug(traceback.format_exc())

    return credexp

def is_cred_xml(cred):
    '''Is this a cred in XML format, or a struct? Return true if XML'''
    if cred is None:
        return False
    if not isinstance(cred, str):
        return False
    # Anything else? Starts with <?
    return True

def get_cred_xml(cred):
    '''Return the cred XML, from the struct if any, else None'''
    if is_cred_xml(cred):
        return cred
    # Make sure the cred is the right struct?
    # extract the real cred
#        {
#           geni_type: <string>,
#           geni_version: <string>,
#           geni_value: <the credential as a string>
#        }

    if isinstance(cred, dict) and cred.has_key("geni_value"):
        return cred["geni_value"]

    return None

