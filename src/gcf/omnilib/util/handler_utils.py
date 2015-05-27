#----------------------------------------------------------------------
# Copyright (c) 2012-2015 Raytheon BBN Technologies
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
'''Misc utilities for use by chhandler and amhandler'''

from __future__ import absolute_import

import datetime
import dateutil
import json
import logging
import os
import re
import string

from . import json_encoding
from . import credparsing as credutils
from .dossl import _do_ssl
from .dates import naiveUTC
from .files import *
from ...geni.util import rspec_util
from ...geni.util.tz_util import tzd
from ...sfa.trust.gid import GID
from ...sfa.trust.credential import Credential

def _derefAggNick(handler, aggregateNickname):
    """Check if the given aggregate string is a nickname defined
    in omni_config. If so, return the dereferenced URL,URN.
    Else return the input as the URL, and 'unspecified_AM_URN' as the URN."""

    if not aggregateNickname:
        return (None, None)
    aggregateNickname = aggregateNickname.strip()
    urn = "unspecified_AM_URN"
    url = aggregateNickname

    # ConfigParser.optionxform by default lowercases keys. So aggregate nicknames
    # are lowercased. Here we lowercase any -a argument before
    # checking the defined nicknames, to make sure
    # you can find your nickname
    amNick = aggregateNickname.lower()

    if handler.config['aggregate_nicknames'].has_key(amNick):
        url = handler.config['aggregate_nicknames'][amNick][1]
        tempurn = handler.config['aggregate_nicknames'][amNick][0]
        if tempurn.strip() != "":
            urn = tempurn
        handler.logger.info("Substituting AM nickname %s with URL %s, URN %s", aggregateNickname, url, urn)
    else:
        # if we got here, we are assuming amNick is actually a URL
        # Print a warning now if amNick (url) doesn't look like a URL
        # validate_url returns None if it appears to be a valid URL
        if validate_url( url ):
            handler.logger.info("Failed to find an AM nickname '%s'.  If you think this is an error, try using --NoAggNickCache to force the AM nickname cache to update." % aggregateNickname)
        else:
            # See if we can find the correct URN by finding the supplied URL in the aggregate nicknames
            turn = _lookupAggURNFromURLInNicknames(handler.logger, handler.config, url)
            if turn and turn != "":
                urn = turn
#            else:
#                handler.logger.debug("Didn't find %s in nicknames", url)

    return url,urn

def _extractURL(logger, url):
    if url:
#        orig = url
        if url.startswith("https://"):
            url = url[len("https://"):]
        elif url.startswith("http://"):
            url = url[len("http://"):]
        if url.startswith("www."):
            url = url[len("www."):]
        if url.startswith("boss."):
            url = url[len("boss."):]
#        logger.debug("Extracted %s from %s", url, orig)
    return url

# Is nick better than retNick? Prefer non-empty and site-type and shorter nicknames
def _isBetterNick(retNick, nick, logger=None):
    if not nick:
        return False
    if retNick and retNick == nick:
        return False
    if not retNick or len(nick) < len(retNick) or \
            (retNick.startswith('ig-') and nick.endswith('-ig')) or \
            (retNick.startswith('og-') and nick.endswith('-og')) or \
            (retNick.startswith('pg-') and nick.endswith('-pg')) or \
            (retNick.startswith('clab-') and nick.endswith('-clab')) or \
            (retNick.startswith('apt-') and nick.endswith('-apt')) or \
            (retNick.startswith('eg-') and nick.endswith('-eg')):
        # Don't flip back to type-site to get something shorter
        if retNick and retNick.split('-')[-1] in ['ig', 'pg', 'eg', 'og', 'clab', 'apt'] and \
                nick.split('-')[-1] not in ['ig', 'pg', 'eg', 'og', 'clab', 'apt']:
#            if logger:
#                logger.debug(" .. but this nickname flips site/type")
            return False
#        if logger:
#            logger.debug(" ... that nickname is better than what I had (%s)", retNick)
        return True
    return False

# Lookup aggregate nickname by aggregate_urn or aggregate_url
def _lookupAggNick(handler, aggregate_urn_or_url):
    retNick = None
    for nick, (urn, url) in handler.config['aggregate_nicknames'].items():
        # Case 1
        if aggregate_urn_or_url == urn or aggregate_urn_or_url == url:
#            handler.logger.debug("For urn/url %s found match: %s=%s,%s", aggregate_urn_or_url, nick, urn, url)
            if _isBetterNick(retNick, nick, handler.logger):
                retNick = nick
    if retNick is not None:
        return retNick
    for nick, (urn, url) in handler.config['aggregate_nicknames'].items():
        # Case 2
        if aggregate_urn_or_url.startswith(url):
#            handler.logger.debug("Queried %s startswith url for nick %s", aggregate_urn_or_url, nick)
            if _isBetterNick(retNick, nick, handler.logger):
                retNick = nick
    if retNick is not None:
        return retNick
    aggregate_urn_or_url = _extractURL(handler.logger, aggregate_urn_or_url)
    for nick, (urn, url) in handler.config['aggregate_nicknames'].items():
        # Case 3
        if _extractURL(handler.logger,url) == aggregate_urn_or_url:
#            handler.logger.debug("Queried & trimmed %s is end of url %s for nick %s", aggregate_urn_or_url, url, nick)
            if _isBetterNick(retNick, nick, handler.logger):
                retNick = nick
    if retNick is not None:
        return retNick
    for nick, (urn, url) in handler.config['aggregate_nicknames'].items():
        # Case 4
        if aggregate_urn_or_url in urn:
#            handler.logger.debug("Trimmed %s is in urn for %s=%s,%s", aggregate_urn_or_url, nick, urn, url)
            if _isBetterNick(retNick, nick, handler.logger):
                retNick = nick
        elif _extractURL(handler.logger, url).startswith(aggregate_urn_or_url):
            # Case 5
#            handler.logger.debug("Trimmed %s is in url for %s=%s,%s", aggregate_urn_or_url, nick, urn, url)
            if _isBetterNick(retNick, nick, handler.logger):
                retNick = nick
#    if retNick is None:
#        handler.logger.debug("Found no match for %s", aggregate_urn_or_url)
#    else:
#        handler.logger.debug("Returning %s", retNick)
    return retNick

def _lookupAggURNFromURLInNicknames(logger, config, agg_url):
    urn = ""
    retNick = None
    # Take exact match else take row where agg_url startswith url in cache else
    # take row where extractURL exact match extractURL in cache
    nagg_url = _extractURL(logger, agg_url)
    if agg_url:
        for nick, (amURN, amURL) in config['aggregate_nicknames'].items():
            if agg_url.strip() == amURL.strip() and amURN.strip() != '':
                if _isBetterNick(retNick, nick, logger):
                    urn = amURN.strip()
#                    logger.debug("Supplied AM URL %s is URN %s according to configured aggregate nicknames (matches URL %s, nick %s T1)", agg_url, urn, amURL, nick)
                    retNick = nick
        if retNick is not None:
            logger.debug("Supplied AM URL %s is URN %s according to configured aggregate nicknames (nick %s T1)", agg_url, urn, retNick)
            return urn

        for nick, (amURN, amURL) in config['aggregate_nicknames'].items():
            if agg_url.strip().startswith(amURL.strip()) and amURN.strip() != '':
                if _isBetterNick(retNick, nick, logger):
                    urn = amURN.strip()
#                    logger.debug("Supplied AM URL %s is URN %s according to configured aggregate nicknames (matches %s T2)", agg_url, urn, amURL)
                    retNick = nick
        if retNick is not None:
            logger.debug("Supplied AM URL %s is URN %s according to configured aggregate nicknames (nick %s T2)", agg_url, urn, retNick)
            return urn

        for nick, (amURN, amURL) in config['aggregate_nicknames'].items():
            if nagg_url == amURL.strip() and amURN.strip() != '':
                if _isBetterNick(retNick, nick, logger):
                    urn = amURN.strip()
#                    logger.debug("Supplied AM URL %s is URN %s according to configured aggregate nicknames (matches %s T3)", agg_url, urn, amURL)
                    retNick = nick
        if retNick is not None:
            logger.debug("Supplied AM URL %s is URN %s according to configured aggregate nicknames (nick %s T3)", agg_url, urn, retNick)
            return urn

        for nick, (amURN, amURL) in config['aggregate_nicknames'].items():
            extr_nick_url = _extractURL(logger, amURL)
            if nagg_url == extr_nick_url and amURN.strip() != '':
                if _isBetterNick(retNick, nick, logger):
                    urn = amURN.strip()
#                    logger.debug("Supplied AM URL %s is URN %s according to configured aggregate nicknames (matches %s T4)", agg_url, urn, amURL)
                    retNick = nick
        if retNick is not None:
            logger.debug("Supplied AM URL %s is URN %s according to configured aggregate nicknames (nick %s T4)", agg_url, urn, retNick)
            return urn

        for nick, (amURN, amURL) in config['aggregate_nicknames'].items():
            extr_nick_url = _extractURL(logger, amURL)
            if extr_nick_url.startswith(nagg_url) and amURN.strip() != '':
                if _isBetterNick(retNick, nick, logger):
                    urn = amURN.strip()
#                    logger.debug("Supplied AM URL %s is URN %s according to configured aggregate nicknames (matches %s T5)", agg_url, urn, amURL)
                    retNick = nick
        if retNick is not None:
            logger.debug("Supplied AM URL %s is URN %s according to configured aggregate nicknames (nick %s T5)", agg_url, urn, retNick)
            return urn

        for nick, (amURN, amURL) in config['aggregate_nicknames'].items():
            if nagg_url in amURL and amURN.strip() != '':
                if _isBetterNick(retNick, nick, logger):
                    urn = amURN.strip()
#                    logger.debug("Supplied AM URL %s is URN %s according to configured aggregate nicknames (matches %s T6)", agg_url, urn, amURL)
                    retNick = nick
        if retNick is not None:
            logger.debug("Supplied AM URL %s is URN %s according to configured aggregate nicknames (nick %s T6)", agg_url, urn, retNick)
            return urn
    return urn

def _lookupAggNickURLFromURNInNicknames(logger, config, agg_urn):
    url = ""
    nick = ""
    if agg_urn:
        # Ignore any +cm / +am difference
        if agg_urn.endswith('+cm') or agg_urn.endswith('+am'):
            agg_urn = agg_urn[:-3]
            logger.debug("Trimmed URN for lookup to %s", agg_urn)
        for amNick in config['aggregate_nicknames'].keys():
            (amURN, amURL) = config['aggregate_nicknames'][amNick]
            # Pick the shortest URL / nickname for this URN - stripping of any version diff for the URL
            if agg_urn in amURN and amURL.strip() != '':
                if (url == "" or nick == "") or \
                        (len(amURL) < len(url)) or \
                        (len(amNick) < len(nick)) or \
                        (nick.startswith('ig-') and amNick.endswith('-ig')) or \
                        (nick.startswith('pg-') and amNick.endswith('-pg')) or \
                        (nick.startswith('og-') and amNick.endswith('-og')) or \
                        (nick.startswith('clab-') and amNick.endswith('-clab')) or \
                        (nick.startswith('apt-') and amNick.endswith('-apt')) or \
                        (nick.startswith('eg-') and amNick.endswith('-eg')):
                    url = amURL.strip()
                    nick = amNick.strip()
                    logger.debug("Supplied AM URN %s is nickname %s, URL %s according to configured aggregate nicknames (matches %s)", agg_urn, nick, url, amURN)
    return nick, url

def _derefRSpecNick( handler, rspecNickname ):
    contentstr = None
    try:
        contentstr = readFile( rspecNickname )
    except:
        pass
    if contentstr is None:
        handler.logger.debug("RSpec '%s' is not a filename or a url" % (rspecNickname))
        if handler.config['rspec_nicknames'].has_key(rspecNickname):
            handler.logger.info("Substituting RSpec nickname '%s' with '%s'" % (rspecNickname, handler.config['rspec_nicknames'][rspecNickname]))
            try:
                contentstr = readFile( handler.config['rspec_nicknames'][rspecNickname] )
            except:
                raise ValueError, "Could not read RSpec '%s' (from nickname '%s')" % (handler.config['rspec_nicknames'][rspecNickname], rspecNickname)
        elif handler.config.has_key('default_rspec_location') and handler.config.has_key('default_rspec_extension'):
            handler.logger.info("Looking for RSpec '%s' in the default rspec location" % (rspecNickname))
            try:
                URL_PREFIXES = ("http://", "https://", "ftp://")
                if handler.config['default_rspec_location'].startswith(URL_PREFIXES):
                    location = handler.config['default_rspec_location']+"/"+rspecNickname+"."+handler.config['default_rspec_extension']
                else:
                    location = os.path.join(handler.config['default_rspec_location'], rspecNickname+"."+handler.config['default_rspec_extension'])
                handler.logger.info("... which is '%s'" % (location))
                contentstr = readFile( location )            
            except:
                raise ValueError, "Unable to interpret RSpec '%s' as any of url, file, nickname, or in a default location" % (rspecNickname)
        else:
            raise ValueError, "Unable to interpret RSpec '%s' as any of url, file, nickname, or in a default location" % (rspecNickname)            
    return contentstr

def _listaggregates(handler):
    """List the aggregates that can be used for the current operation.
    If the user specified --useSliceAggregates and the framework
    supports it, then use the aggregates for which
    there are recorded slivers at the CH.
    If 1+ aggregates were specified on the command line, use only those.
    Else if aggregates are specified in the config file, use that set.
    Else ask the framework for the list of aggregates.
    Returns the aggregates as a dict of urn => url pairs.
    If URLs were given on the commandline, AM URN is 'unspecified_AM_URN', with '+'s tacked on for 2nd+ such.
    If multiple URLs were given in the omni config, URN is really the URL
    """
    # used by _getclients (above), createsliver, listaggregates
    ret = {}
    if handler.opts.useSliceAggregates and not handler.opts.noExtraCHCalls and hasattr(handler.opts,'sliceName') and handler.opts.sliceName is not None:
        handler.logger.debug("Looking for slivers recorded at CH for slice %s", handler.opts.sliceName)
        sliverAggs = []
        try:
            sliverAggs = handler.framework.list_sliver_infos_for_slice(handler.opts.sliceName).keys()
        except Exception, e:
            handler.logger.warn("Error looking up aggregates for slice %s at CH: %s", handler.opts.sliceName, e)
        for aggURN in sliverAggs:
            handler.logger.debug("Look up CH recorded URN %s", aggURN)
            nick, url = _lookupAggNickURLFromURNInNicknames(handler.logger, handler.config, aggURN)
            aggURNAlt = None
            if aggURN.endswith('+cm'):
                aggURNAlt = aggURN[:-2] + 'am'
            elif aggURN.endswith('+am'):
                aggURNAlt = aggURN[:-2] + 'cm'
            if url != '':
                # Avoid duplicate aggregate entries
                if url in ret.values():
                    if (ret.has_key(aggURN) and ret[aggURN]==url) or \
                            (aggURNAlt is not None and ret.has_key(aggURNAlt) and ret[aggURNAlt] == url):
                        handler.logger.debug("Not adding duplicate agg %s", nick)
                        continue
                while aggURN in ret:
                    aggURN += "+"
                ret[aggURN] = url
                handler.logger.info("Adding aggregate %s to query list", nick)
            else:
                handler.logger.info("Aggregate %s unknown", aggURN)
        if not handler.opts.aggregate:
            return (ret, "%d aggregates known to have resources for slice %s" % (len(sliverAggs), handler.opts.sliceName))
    if handler.opts.aggregate:
        for agg in handler.opts.aggregate:
            # Try treating that as a nickname
            # otherwise it is the url directly
            # Either way, if we have no URN, we fill in 'unspecified_AM_URN'
            url, urn = _derefAggNick(handler, agg)
            if url is None or urn is None:
                handler.logger.info("Aggregate '%s' unknown", agg)
                continue
            url = url.strip()
            urn = urn.strip()
            aggURNAlt = None
            if urn.endswith('+cm'):
                aggURNAlt = urn[:-2] + 'am'
            elif urn.endswith('+am'):
                aggURNAlt = urn[:-2] + 'cm'
            if url != '':
                # Avoid duplicate aggregate entries
                if url in ret.values():
                    if (ret.has_key(urn) and ret[urn]==url) or \
                            (aggURNAlt is not None and ret.has_key(aggURNAlt) and ret[aggURNAlt] == url) or \
                            urn == "unspecified_AM_URN":
                        handler.logger.debug("Not adding duplicate agg %s=%s", agg, urn)
                        continue
                elif urn in ret.keys() and urn != "unspecified_AM_URN":
                    if _extractURL(handler.logger, ret[urn]).startswith(_extractURL(handler.logger, url)) or \
                            _extractURL(handler.logger, url).startswith(_extractURL(handler.logger, ret[urn])):
                        handler.logger.debug("Not adding duplicate agg %s=%s", agg, urn)
                        continue
                while urn in ret:
                    urn += "+"
                handler.logger.debug("Adding aggregate %s (%s) to query list", agg, urn)
                ret[urn] = url
            else:
                handler.logger.info("Aggregate '%s' unknown", agg)
        return (ret, "")
    elif not handler.omni_config.get('aggregates', '').strip() == '':
        aggs = {}
        for url in handler.omni_config['aggregates'].strip().split(','):
            if url is None:
                continue
            url = url.strip()
            if url != '':
                # Try treating that as a nickname
                # otherwise it is the url directly
                # Either way, if we have no URN, we fill in 'unspecified_AM_URN'
                nurl, urn = _derefAggNick(handler, url)
                nurl = nurl.strip()
                urn = urn.strip()
                if nurl != '':
                    # Avoid duplicate aggregate entries
                    if nurl in aggs.values() and ((aggs.has_key(urn) and aggs[urn]==nurl) or urn == "unspecified_AM_URN"):
                        continue
                    while urn in aggs:
                        urn += "+"
                    aggs[urn] = nurl
                else:
                    aggs[url] = url
        return (aggs, "")
    elif not handler.opts.noExtraCHCalls:
        handler.logger.debug("Querying clearinghouse for all aggregates")
        (aggs, message) =  _do_ssl(handler.framework, None, "List Aggregates from control framework", handler.framework.list_aggregates)
        if aggs is None:
            # FIXME: Return the message?
            return ({}, message)
        # FIXME: Check that each agg has both a urn and url key?
        return (aggs, "From CH")
    else:
        handler.logger.debug("Per commandline option, not looking up aggregates at the clearinghouse")
        return ({}, "Per noExtraCHCalls, not looking up aggregates at clearinghouse")

def _load_cred(handler, filename):
    '''
    Load a credential from the given filename. Return None on error.
    Based on AM API version, returned cred will be a struct or raw XML.
    In dev mode, file contents are returned as is.
    '''
    if not filename:
        handler.logger.debug("No filename provided for credential")
        return None
    if not os.path.exists(filename) or not os.path.isfile(filename) or os.path.getsize(filename) <= 0:
        handler.logger.warn("Credential file %s missing or empty", filename)
        return None

    handler.logger.info("Getting credential from file %s", filename)
    cred = None
    isStruct = False
    with open(filename, 'r') as f:
        cred = f.read()

    try:
        cred = json.loads(cred, encoding='ascii', cls=json_encoding.DateTimeAwareJSONDecoder)
        isStruct = True
    except Exception, e:
        handler.logger.debug("Failed to get a JSON struct from cred in file %s. Treat as a string.", filename)
        #handler.logger.debug(e)

    if not handler.opts.devmode:
        if handler.opts.api_version >= 3 and credutils.is_cred_xml(cred) and not isStruct:
            handler.logger.debug("Using APIv3+ and got XML cred. Wrapping it.")
            cred = handler.framework.wrap_cred(cred)
        elif handler.opts.api_version < 3 and not credutils.is_cred_xml(cred) and isStruct:
            handler.logger.debug("Using APIv2 or 1 and got a struct cred. Unwrapping it.")
            cred = credutils.get_cred_xml(cred)
        else:
            handler.logger.debug("Using APIv%d and got cred seemingly in right form, return it", handler.opts.api_version)
    return cred

def _get_slice_cred(handler, urn):
    """Get a cred for the slice with the given urn.
    Try a couple times to get the given slice credential.
    Retry on wrong pass phrase.
    Return the slice credential, and a string message of any error.
    Returned credential will be a struct in AM API v3+.
    """

    cred = _load_cred(handler, handler.opts.slicecredfile)
    if cred is not None:
        msg = "Read slice cred from %s" % handler.opts.slicecredfile
        # We support reading cred from file without supplying a URN
        if not urn or urn.strip() == "":
            handler.logger.info("Got slice credential from file %s", handler.opts.slicecredfile)
        else:
            target_urn = credutils.get_cred_target_urn(handler.logger, cred)
            if target_urn != urn:
                msg += " - BUT it is for slice %s, not expected %s!" % (target_urn, urn)
                handler.logger.warn(msg)
                cred = None
            else:
                msg += " for slice %s" % urn
                handler.logger.info(msg)
        return (cred, msg)
    elif handler.opts.slicecredfile and urn:
            handler.logger.warn("Since supplied slicecred file not readable, falling back to re-downloading slice credential for slice %s", urn)

    # We support reading cred from file without supplying a URN
    if not urn or urn.strip() == "":
        msg = "No slice URN supplied and no credential read from a file"
        handler.logger.warn(msg)
        return (None, msg)

    # Check that the return is either None or a valid slice cred
    # Callers handle None - usually by raising an error
    if handler.opts.api_version < 3:
        (cred, message) = _do_ssl(handler.framework, None, "Get Slice Cred for slice %s" % urn, handler.framework.get_slice_cred, urn)
    else:
        (cred, message) = _do_ssl(handler.framework, None, "Get Slice Cred for slice %s" % urn, handler.framework.get_slice_cred_struct, urn)
    if type(cred) is dict:
        # Validate the cred inside the struct
        if not cred.has_key('geni_type') \
                and cred['geni_type'] == Credential.SFA_CREDENTIAL_TYPE:
            handler.logger.error("Non SFA slice credential returned for slice %s: %s" % (urn, cred))
            cred = None
            message = "Invalid slice credential returned"
        elif not cred.has_key('geni_value'):
            handler.logger.error("Malformed slice credential struct returned for slice %s: %s" % (urn, cred))
            cred = None
            message = "Invalid slice credential returned"
        if cred is not None:
            icred = cred['geni_value']
            if icred is not None and (not (type(icred) is str and icred.startswith("<"))):
                handler.logger.error("Got invalid SFA slice credential for slice %s: %s" % (urn, icred))
                cred = None
                message = "Invalid slice credential returned"

        # FIXME: If this is API v2, unwrap the cred? I _think_ all callers handle this appropriately without doing so

        return (cred, message)
    if cred is not None and (not (type(cred) is str and cred.startswith("<"))):
        #elif slice_cred is not XML that looks like a credential, assume
        # assume it's an error message, and raise an omni_error
        handler.logger.error("Got invalid slice credential for slice %s: %s" % (urn, cred))
        cred = None
        message = "Invalid slice credential returned"
    if cred and handler.opts.api_version >= 3:
        cred = handler.framework.wrap_cred(cred)
    return (cred, message)

def _print_slice_expiration(handler, urn, sliceCred=None):
    """Check when the slice expires. Print varying warning notices
    and the expiration date"""
    # FIXME: push this to config?
    shorthours = 3
    middays = 1

# This could be used to print user credential expiration info too...

    if sliceCred is None:
        (sliceCred, _) = _get_slice_cred(handler, urn)
    if sliceCred is None:
        # failed to get a slice string. Can't check
        return ""

    sliceexp = credutils.get_cred_exp(handler.logger, sliceCred)
    sliceexp = naiveUTC(sliceexp)
    now = datetime.datetime.utcnow()
    if sliceexp <= now:
        retVal = 'Slice %s has expired at %s UTC' % (urn, sliceexp)
        handler.logger.warn('Slice %s has expired at %s UTC' % (urn, sliceexp))
    elif sliceexp - datetime.timedelta(hours=shorthours) <= now:
        retVal = 'Slice %s expires in <= %d hours on %s UTC' % (urn, shorthours, sliceexp)
        handler.logger.warn('Slice %s expires in <= %d hours' % (urn, shorthours))
        handler.logger.info('Slice %s expires on %s UTC' % (urn, sliceexp))
        handler.logger.debug('It is now %s UTC' % (datetime.datetime.utcnow()))
    elif sliceexp - datetime.timedelta(days=middays) <= now:
        retVal = 'Slice %s expires within %d day(s) on %s UTC' % (urn, middays, sliceexp)
        handler.logger.info('Slice %s expires within %d day on %s UTC' % (urn, middays, sliceexp))
    else:
        retVal = 'Slice %s expires on %s UTC' % (urn, sliceexp)
        handler.logger.info('Slice %s expires on %s UTC' % (urn, sliceexp))
    return retVal

def validate_url(url):
    """Basic sanity checks on URLs before trying to use them.
    Return None on success, error string if there is a problem.
    If return starts with WARN: then just log a warning - not fatal."""

    import urlparse
    pieces = urlparse.urlparse(url)
    if not all([pieces.scheme, pieces.netloc]):
        return "Invalid URL: %s" % url
    if not pieces.scheme in ["http", "https"]:
        return "Invalid URL. URL should be http or https protocol: %s" % url
    if not set(pieces.netloc) <= set(string.letters+string.digits+'-.:'):
        return "Invalid URL. Host/port has invalid characters in url %s" % url

    # Look for common errors in contructing the urls

    # FIXME: check cache to find common URL typos?

# GCF Ticket #66: This check is just causing confusion. And will be OBE with FOAM.
#    # if the urn part of the urn is openflow/gapi (no trailing slash)
#    # then warn it needs a trailing slash for Expedient
#    if pieces.path.lower().find('/openflow/gapi') == 0 and pieces.path != '/openflow/gapi/':
#        return "WARN: Likely invalid Expedient URL %s. Expedient AM runs at /openflow/gapi/ - try url https://%s/openflow/gapi/" % (url, pieces.netloc)

# GCF ticket #66: Not sure these checks are helping either.
# Right thing may be to test the URL and see if an AM is running there, rather
# than this approach.

#    # If the url has no path part but a port that is 123?? and not 12346
#    # then warn and suggest SFA AMs typically run on 12346
#    if (pieces.path is None or pieces.path.strip() == "" or pieces.path.strip() == '/') and pieces.port >= 12300 and pieces.port < 12400 and pieces.port != 12346:
#        return "WARN: Likely invalid SFA URL %s. SFA AM typically runs on port 12346. Try AM URL https://%s:12346/" % (url, pieces.hostname)

#    # if the non host part has 'protogeni' and is not protogeni/xmlrpc/am
#    # then warn that PG AM interface is at protogeni/xmlrpc/am
#    if pieces.path.lower().find('/protogeni') == 0 and pieces.path != '/protogeni/xmlrpc/am' and pieces.path != '/protogeni/xmlrpc/am/':
#        return "WARN: Likely invalid PG URL %s: PG AMs typically run at /protogeni/xmlrpc/am - try url https://%s/protogeni/xmlrpc/am" % (url, pieces.netloc)

    return None

def _filename_part_from_am_url(url):
    """Strip uninteresting parts from an AM URL 
    to help construct part of a filename.
    """
    # see listresources and createsliver

    if url is None or url.strip() == "":
        return url

    # remove all punctuation and use url
    server = url
    # strip leading protocol bit
    if url.find('://') > -1:
        server = url[(url.find('://') + 3):]

    # protogeni often runs on port 12369 - pull that out if possible
    if ":12369/protogeni/" in server:
        server = server[:(server.index(":12369/"))] + server[(server.index(":12369/")+6):]

    if server.startswith("boss."):
        server = server[server.index("boss.")+len("boss."):]

    # strip standard url endings that dont tell us anything
    if server.endswith("/xmlrpc/am"):
        server = server[:(server.index("/xmlrpc/am"))]
    elif server.endswith("/xmlrpc"):
        server = server[:(server.index("/xmlrpc"))]
    elif server.endswith("/xmlrpc/am/1.0"):
        server = server[:(server.index("/xmlrpc/am/1.0"))] + "v1"
    elif server.endswith("/xmlrpc/am/2.0"):
        server = server[:(server.index("/xmlrpc/am/2.0"))] + "v2"
    elif server.endswith("/xmlrpc/am/3.0"):
        server = server[:(server.index("/xmlrpc/am/3.0"))] + "v3"
    elif server.endswith("/openflow/gapi/"):
        server = server[:(server.index("/openflow/gapi/"))]
    elif server.endswith(":3626/foam/gapi/1"):
        server = server[:(server.index(":3626/foam/gapi/1"))]
    elif server.endswith(":3626/foam/gapi/2"):
        server = server[:(server.index(":3626/foam/gapi/2"))]
    elif server.endswith("/gapi"):
        server = server[:(server.index("/gapi"))]
    elif server.endswith(":12346"):
        server = server[:(server.index(":12346"))]
    server = remove_bad_characters( server )
    return server

def remove_bad_characters( input ):
    # remove punctuation. Handle both unicode and ascii gracefully
    bad = u'!"#%\'()*+,./:;<=>?@[\]^`{|}~'
    if isinstance(input, unicode):
        table = dict((ord(char), unicode('-')) for char in bad)
    else:
        assert isinstance(input, str)
        table = string.maketrans(bad, '-' * len(bad))
    input = input.translate(table)
    if input.endswith('-'):
        input = input[:-1]
    input = re.sub("--", "-", input)
    return input

def _get_server_name(clienturl, clienturn):
    '''Construct a short server name from the AM URL and URN'''
    if clienturn and not clienturn.startswith("unspecified_AM_URN") and (not clienturn.startswith("http")):
        # construct hrn
        # strip off any leading urn:publicid:IDN
        if clienturn.find("IDN+") > -1:
            clienturn = clienturn[(clienturn.find("IDN+") + 4):]
        urnParts = clienturn.split("+")
        server = urnParts.pop(0)
        if isinstance(server, unicode):
            table = dict((ord(char), unicode('-')) for char in ' .:')
        else:
            table = string.maketrans(' .:', '---')
        server = server.translate(table)
    else:
        # remove all punctuation and use url
        server = _filename_part_from_am_url(clienturl)
    return server

def _construct_output_filename(opts, slicename, clienturl, clienturn, methodname, filetype, clientcount):
    '''Construct a file name for omni command outputs; return that name.
    If --outputfile specified, use that.
    Else, overall form is [prefix-][slicename-]methodname-server.filetype
    filetype should be .xml or .json'''

    # Construct server bit. Get HRN from URN, else use url
    # FIXME: Use sfa.util.xrn.get_authority or urn_to_hrn?
    server = _get_server_name(clienturl, clienturn)
    if opts and opts.outputfile:
        filename = opts.outputfile
        if "%a" in opts.outputfile:
            if server is not None:
                # replace %a with server
                filename = string.replace(filename, "%a", server)
        elif clientcount > 1 and server is not None:
            # FIXME: How do we distinguish? Let's just prefix server
            filename = server + "-" + filename
        if "%s" in opts.outputfile:
            # replace %s with slicename
            if not slicename:
                slicename = 'noslice'
            filename = string.replace(filename, "%s", slicename)
        return filename

    if server is None or server.strip() == '':
        filename = methodname + filetype
    else:
        filename = methodname + "-" + server + filetype
#--- AM API specific
    if slicename:
        filename = slicename+"-" + filename
#--- 
    if opts and opts.prefix and opts.prefix.strip() != "":
        if not opts.prefix.strip().endswith(os.sep):
            filename  = opts.prefix.strip() + "-" + filename
        else:
            filename  = opts.prefix.strip() + filename
    return filename

def _getRSpecOutput(logger, rspec, slicename, urn, url, message, slivers=None):
    '''Get the header, rspec content, and retVal for writing the given RSpec to a file'''
    # Create HEADER
    if slicename:
        if slivers and len(slivers) > 0:
            header = "Reserved resources for:\n\tSlice: %s\n\tSlivers: %s\n\tat AM:\n\tURN: %s\n\tURL: %s\n" % (slicename, slivers, urn, url)
        else:
            header = "Reserved resources for:\n\tSlice: %s\n\tat AM:\n\tURN: %s\n\tURL: %s\n" % (slicename, urn, url)
    else:
        header = "Resources at AM:\n\tURN: %s\n\tURL: %s\n" % (urn, url)
    header = "<!-- "+header+" -->"

    server = _get_server_name(url, urn)

    # Create BODY
    if rspec and rspec_util.is_rspec_string( rspec, None, None, logger=logger ):
        # This line seems to insert extra \ns - GCF ticket #202
#        content = rspec_util.getPrettyRSpec(rspec)
        content = string.replace(rspec, "\\n", '\n')
#        content = rspec
        if slicename:
            retVal = "Got Reserved resources RSpec from %s" % server
        else:
            retVal = "Got RSpec from %s" % server
    else:
        content = "<!-- No valid RSpec returned. -->"
        if rspec is not None:
            # FIXME: Diff for dev here?
            logger.warn("No valid RSpec returned: Invalid RSpec? Starts: %s...", str(rspec)[:min(40, len(rspec))])
            content += "\n<!-- \n" + str(rspec) + "\n -->"
            if slicename:
                retVal = "Invalid RSpec returned for slice %s from %s that starts: %s..." % (slicename, server, str(rspec)[:min(40, len(rspec))])
            else:
                retVal = "Invalid RSpec returned from %s that starts: %s..." % (server, str(rspec)[:min(40, len(rspec))])
            if message:
                logger.warn("Server said: %s", message)
                retVal += "; Server said: %s" % message

        else:
            forslice = ""
            if slicename:
                forslice = "for slice %s " % slicename
            serversaid = ""
            if message:
                serversaid = ": %s" % message

            retVal = "No RSpec returned %sfrom %s%s" % (forslice, server, serversaid)
            logger.warn(retVal)
    return header, content, retVal

def _writeRSpec(opts, logger, rspec, slicename, urn, url, message=None, clientcount=1):
    '''Write the given RSpec using _printResults.
    If given a slicename, label the output as a manifest.
    Use rspec_util to check if this is a valid RSpec, and to format the RSpec nicely if so.
    Do much of this using _getRSpecOutput
    Use _construct_output_filename to build the output filename.
    '''
    # return just filename? retVal?
    # Does this do logging? Or return what it would log? I think it logs, but....

    (header, content, retVal) = _getRSpecOutput(logger, rspec, slicename, urn, url, message)

    filename=None
    # Create FILENAME
    if opts.output:
        mname = "rspec"
        if slicename:
            mname = "manifest-rspec"
        filename = _construct_output_filename(opts, slicename, url, urn, mname, ".xml", clientcount)
        # FIXME: Could add note to retVal here about file it was saved to? For now, caller does that.

    if filename or (rspec is not None and str(rspec).strip() != ''):
        # Create FILE
        # This prints or logs results, depending on whether filename is None
        _printResults(opts, logger, header, content, filename)
    return retVal, filename
# End of _writeRSpec

def _printResults(opts, logger, header, content, filename=None):
    """Print header string and content string to file of given
    name. If filename is none, then log to info.
    If --tostdout option, then instead of logging, print to STDOUT.
    """
    cstart = 0
    # If the content is a single quote quoted XML doc then just drop those single quotes
    if content is not None and content.startswith("'<?xml") and content.endswith("'"):
        content = content[1:-1]
        if content.find(">\n"):
            content = content.replace("\\n", "\n")
    # if content starts with <?xml ..... ?> then put the header after that bit
    elif content is not None and content.find("<?xml") > -1 and content.find("'<?xml") < 0:
        cstart = content.find("?>", content.find("<?xml") + len("<?xml"))+2
        # push past any trailing \n
        if content[cstart:cstart+2] == "\\n":
            cstart += 2
    # used by listresources
    if filename is None:
        if header is not None:
            if cstart > 0:
                if not opts.tostdout:
                    logger.info(content[:cstart])
                else:
                    print content[:cstart] + "\n"
            if not opts.tostdout:
                # indent header a bit if there was something first
                pre = ""
                if cstart > 0:
                    pre = "  "
                logger.info(pre + header)
            else:
                # If cstart is 0 maybe still log the header so it
                # isn't written to STDOUT and non-machine-parsable
                if cstart == 0:
                    logger.info(header)
                else:
                    print header + "\n"
        elif content is not None:
            if not opts.tostdout:
                if cstart > 0 and content[:cstart].strip() != "":
                    logger.info(content[:cstart])
            else:
                print content[:cstart] + "\n"
        if content is not None:
            if not opts.tostdout:
                # indent a bit if there was something first
                pre = ""
                if cstart > 0:
                    pre += "  "
                logger.info(pre + content[cstart:])
            else:
                print content[cstart:] + "\n"
    else:
        fdir = os.path.dirname(filename)
        if fdir and fdir != "":
            if not os.path.exists(fdir):
                os.makedirs(fdir)
        with open(filename,'w') as file:
            logger.info( "Writing to '%s'"%(filename))
            if header is not None:
                if cstart > 0:
                    file.write (content[:cstart] + '\n')
                # this will fail for JSON output. 
                # only write header to file if have xml like
                # above, else do log thing per above
                # FIXME: XML file without the <?xml also ends up logging the header this way
                if cstart > 0:
                    file.write("  " + header )
                    file.write( "\n" )
                else:
                    logger.info(header)
            elif cstart > 0:
                file.write(content[:cstart] + '\n')
            if content is not None:
                pre = ""
                if cstart > 0:
                    pre += "  "
                file.write( pre + content[cstart:] )
                file.write( "\n" )
# End of _printResults

def _maybe_save_slicecred(handler, name, slicecred):
    """Save slice credential to a file, returning the filename or
    None on error or config not specifying -o
    
    Only saves if handler.opts.output and non-empty credential
    
    If you didn't specify -o but do specify --tostdout, then write
    the slice credential to STDOUT
    
    Filename is:
    --slicecredfile if supplied
    else [<--p value>-]-<slicename>-cred.[xml or json, depending on credential format]
    """
    if name is None or name.strip() == "" or slicecred is None or (credutils.is_cred_xml(slicecred) and slicecred.strip() is None):
        return None

    filename = None
    if handler.opts.output:
        if handler.opts.slicecredfile:
            filename = handler.opts.slicecredfile
        else:
            filename = name + "-cred"
            if handler.opts.prefix and handler.opts.prefix.strip() != "":
                filename = handler.opts.prefix.strip() + "-" + filename
        filename = _save_cred(handler, filename, slicecred)
    elif handler.opts.tostdout:
        handler.logger.info("Writing slice %s cred to STDOUT per options", name)
        # pprint does bad on XML, but OK on JSON
        print slicecred
    return filename

def _save_cred(handler, name, cred):
    '''
    Save the given credential to a file of the given name.
    Infer an appropriate file extension from the file type.
    If we are using APIv3+ and the credential is not a struct, wrap it before saving.
    '''
    ftype = ".xml"
    # FIXME: Do this?
    if credutils.is_cred_xml(cred) and handler.opts.api_version >= 3:
        handler.logger.debug("V3 requested, got unwrapped cred. Wrapping before saving")
        cred = handler.framework.wrap_cred(cred)

    if not credutils.is_cred_xml(cred):
        ftype = ".json"
        credout = json.dumps(cred, cls=json_encoding.DateTimeAwareJSONEncoder)
        # then read:                 cred = json.load(f, encoding='ascii', cls=DateTimeAwareJSONDecoder)
    else:
        credout = cred

    if not name.endswith(ftype):
        filename = name + ftype
    else:
        filename = name

    filedir = os.path.dirname(filename)
    if filedir and filedir != "" and not os.path.exists(filedir):
        os.makedirs(filedir)

# usercred did this:
#        with open(fname, "wb") as file:
#            file.write(cred)
    with open(filename, 'w') as file:
        file.write(credout + "\n")

    return filename

def _is_user_cert_expired(handler):
    # create a gid
    usergid = None
    try:
        usergid = GID(filename=handler.framework.config['cert'])
    except Exception, e:
        handler.logger.debug("Failed to create GID from %s: %s",
                             handler.framework.config['cert'], e)
    if usergid and usergid.cert.has_expired():
        return True
    return False

def _get_user_urn(logger, config):
    # create a gid
    usergid = None
    try:
        usergid = GID(filename=config['cert'])
    except Exception, e:
        logger.debug("Failed to create GID from %s: %s",
                             config['cert'], e)
    # do get_urn
    if usergid:
        return usergid.get_urn()
    else:
        return None

def printNicknames(config, opts):
    '''Get the known aggregate and rspec nicknames and return them as a string and a struct.

        Output directing options:
        -o Save result in a file
        -p (used with -o) Prefix for resulting filename
        --outputfile If supplied, use this output file name
        If not saving results to a file, they are logged.
        If intead of -o you specify the --tostdout option, then instead of logging, print to STDOUT.

        File name will be nicknames.txt (plus any requested prefix)
    '''
    retStruct = dict()
    result_string = ""
    retStruct['aggregate_nicknames'] = config['aggregate_nicknames']
    retString = "Omni knows the following Aggregate Nicknames:\n\n"
    retString += "%16s | %s | %s\n" % ("Nickname", string.ljust("URL", 70), "URN")
    retString += "=============================================================================================================\n"
    for nick in sorted(config['aggregate_nicknames'].keys()):
        (urn, url) = config['aggregate_nicknames'][nick]
        retString += "%16s | %s | %s\n" % (nick, string.ljust(url, 70), urn)

    retStruct['rspec_nicknames'] = config['rspec_nicknames']
    if len(config['rspec_nicknames']) > 0:
        retString += "\nOmni knows the following RSpec Nicknames:\n\n"
        retString += "%14s | %s\n" % ("Nickname", "Location")
        retString += "====================================================================================\n"
        for nick in sorted(config['rspec_nicknames'].keys()):
            location = config['rspec_nicknames'][nick]
            retString += "%14s | %s\n" % (nick, location)

    if config.has_key("default_rspec_location"):
        retString += "\n(Default RSpec location: %s )\n" % config["default_rspec_location"]
    if config.has_key("default_rspec_extension"):
        retString += "\n(Default RSpec extension: %s )\n" % config["default_rspec_extension"]

    if opts.aggregate and len(opts.aggregate) > 0:
        result_string += "\nRequested aggregate nicknames:\n"
        for nick in opts.aggregate:
            if nick in config['aggregate_nicknames'].keys():
                (urn, url) = config['aggregate_nicknames'][nick]
                result_string += "\t%s = %s (%s)\n" % (nick, url, urn)
            else:
                result_string += "\t%s = Not a known aggregate nickname\n" % nick
        result_string += "\n"

    header=None
    filename = None
    if opts.output:
        filename = _construct_output_filename(opts, None, None, None, "nicknames", ".txt", 0)

    if filename is not None or opts.tostdout:
        _printResults(opts, config['logger'], header, retString, filename)

    if filename is not None:
        result_string += "Saved list of known nicknames to file %s. \n" % (filename)
    elif opts.tostdout:
        result_string += "Printed list of known nicknames. \n"
    else:
        result_string = retString + result_string

    return result_string, retStruct

def expires_from_rspec(result, logger=None):
    '''Parse the expires attribute off the given rspec and return it as a naive UTC datetime 
    (if found and different from any 'generated' timestamp).
    If that fails, try to parse the ExoGENI sliver info extension.
    If those fail, return None.'''
    # SFA and PG use the expires attribute. MAX too. ION soon, but for now it is wrong.
    # FOAM (and AL2S) and EG and GRAM do not. EG however has a sliver_info extension.
    if result is None or str(result).strip() == "":
        return None
    rspec = str(result)
    match = re.search("<rspec [^>]*expires\s*=\s*[\'\"]([^\'\"]+)[\'\"]", rspec)
    if match:
        expStr = match.group(1).strip()
        if logger:
            logger.debug("Found rspec expires attribute: '%s'", expStr)
        try:
            expObj = _naiveUTCFromString(expStr)

            # Now look for a generated attribute. If there and same, expires is no good
            match2 = re.search("<rspec [^>]*generated\s*=\s*[\'\"]([^\'\"]+)[\'\"]", rspec)
            if match2:
                genStr = match2.group(1).strip()
                #if logger:
                #    logger.debug("Found generated %s", genStr)
                try:
                    genObj = _naiveUTCFromString(genStr)
                    if expObj - genObj > datetime.timedelta.resolution:
                        #if logger:
                        #    logger.debug("Expires diff from gen, use it")
                        return expObj
                    else:
                        if logger:
                            logger.debug("Expires %s same as generated %s, pretend got no expires", expStr, genStr)
                        expObj = None
                except Exception, e2:
                    if logger:
                        logger.debug("Unparsabled generated timestamp %s: %s", genStr, e2)
                    return expObj
            else:
                #if logger:
                #    logger.debug("Found no generated")
                return expObj
        except Exception, e:
            if logger:
                logger.debug("Exception parsing expires attribute %s: %s", expStr, e)
    else:
        if logger:
            logger.debug("RSpec had no expires attribute")

    # Got no good expires so far. Look for the EG geni_sliver_info attribute
    # FIXME: This is really per node, and here we're returning just one.
    match = re.search("<rspec\s+.+\s+<node\s+.+\s+<.*geni_sliver_info\s+[^>]*expiration_time\s*=\s*[\'\"]([^\'\"]+)[\'\"]", rspec, re.DOTALL)
    if match:
        expStr = match.group(1).strip()
        if logger:
            logger.debug("Found EG style geni_sliver_info %s", expStr)
        try:
            expObj = _naiveUTCFromString(expStr)
            return expObj
        except Exception, e:
            if logger:
                logger.debug("Exception parsing EG expiration_time attribute %s: %s", expStr, e)
    else:
        if logger:
            logger.debug("RSpec had no EG geni_sliver_info with an expiration_time attribute")

    # If no expires found, return None
    return None

def _naiveUTCFromString(timeStr):
    if not timeStr:
        return None
    try:
        timeO = dateutil.parser.parse(timeStr, tzinfos=tzd)
        return naiveUTC(timeO)
    except Exception, e:
#        print "Failed to parse time object from string %s: %s" % (timeStr, e)
        return None

def expires_from_status(status, logger):
    # Get the sliver expiration(s) from the status struct
    # Return a list of datetime objects in naiveUTC - may be an empty list if no expiration time found

    # PG: top-level pg_expires
    # DCN: top-level geni_expires
    # GRAM: per resource geni_expires
    # FOAM (and AL2S): top level foam_expires
    # EG: per resource orca_expires
    # SFA: pl_expires (also check sfa_expires to be safe)

    # Caller will likely want to report # expirations and soonest and if they are all same/diff
    # See logic in amhandler._getSliverExpirations and .status() around line 3397
    exps = []
    if status and isinstance(status, dict):
        if status.has_key('pg_expires'):
            exp = status['pg_expires']
            tO = _naiveUTCFromString(exp)
            if tO:
                exps.append(tO)
            if logger:
                logger.debug("Got real sliver expiration using sliverstatus at PG AM")
        elif status.has_key('geni_expires'):
            exp = status['geni_expires']
            tO = _naiveUTCFromString(exp)
            if tO:
                exps.append(tO)
            if logger:
                logger.debug("Got real sliver expiration using sliverstatus at DCN or similar AM")
        elif status.has_key('foam_expires'):
            exp = status['foam_expires']
            tO = _naiveUTCFromString(exp)
            if tO:
                exps.append(tO)
            if logger:
                logger.debug("Got real sliver expiration using sliverstatus at FOAM AM")
        elif status.has_key('pl_expires'):
            exp = status['pl_expires']
            tO = _naiveUTCFromString(exp)
            if tO:
                exps.append(tO)
            if logger:
                logger.debug("Got real sliver expiration using sliverstatus (pl_expires) at SFA AM")
        elif status.has_key('sfa_expires'):
            exp = status['sfa_expires']
            tO = _naiveUTCFromString(exp)
            if tO:
                exps.append(tO)
            if logger:
                logger.debug("Got real sliver expiration using sliverstatus (sfa_expires) at SFA AM")
        elif status.has_key('geni_resources') and \
                isinstance(status['geni_resources'], list) and \
                len(status['geni_resources']) > -1:
            for resource in status['geni_resources']:
                if isinstance(resource, dict):
                    if resource.has_key('orca_expires'):
                        exp = resource['orca_expires']
                        tO = _naiveUTCFromString(exp)
                        if tO and tO not in exps:
                            exps.append(tO)
                        if logger:
                            logger.debug("Got real sliver expiration using sliverstatus at Orca AM")
                    elif resource.has_key('geni_expires'):
                        exp = resource['geni_expires']
                        tO = _naiveUTCFromString(exp)
                        if tO and tO not in exps:
                            exps.append(tO)
                        if logger:
                            logger.debug("Got real sliver expiration using sliverstatus at GRAM AM")
                    else:
                        if logger:
                            logger.debug("No expiration in this geni_resource")
                else:
                    if logger:
                        logger.debug("Malformed non dict geni_resource")
        else:
            if logger:
                logger.debug("No top level expires or geni_resources list")
    else:
        if logger:
            logger.debug("Invalid status object")
    return exps
