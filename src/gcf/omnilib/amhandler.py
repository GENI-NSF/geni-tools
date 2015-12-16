#!/usr/bin/env python

from __future__ import absolute_import

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

"""
Omni AM API Call Handler
Handle calls to AM API functions
"""

from copy import copy
import datetime
import dateutil.parser
import json
import logging
import os
import pprint
import re
import string
import zlib

from .util import OmniError, NoSliceCredError, RefusedError, naiveUTC, AMAPIError
from .util.dossl import _do_ssl
from .util.abac import get_abac_creds, save_abac_creds, save_proof, is_ABAC_framework
from .util import credparsing as credutils
from .util.handler_utils import _listaggregates, validate_url, _get_slice_cred, _derefAggNick, \
    _derefRSpecNick, _get_user_urn, \
    _print_slice_expiration, _construct_output_filename, \
    _getRSpecOutput, _writeRSpec, _printResults, _load_cred, _lookupAggNick, \
    expires_from_rspec, expires_from_status
from .util.json_encoding import DateTimeAwareJSONEncoder, DateTimeAwareJSONDecoder
from .xmlrpc import client as xmlrpcclient
from .util.files import *
from .util.credparsing import *

from ..geni.util.tz_util import tzd
from ..geni.util import rspec_util, urn_util


class BadClientException(Exception):
    ''' Internal only exception thrown if AM speaks wrong AM API version'''
    def __init__(self, client, msg):
        self.client = client
        self.validMsg = msg

class AMCallHandler(object):
    '''Dispatch AM API calls to aggregates'''
    def __init__(self, framework, config, opts):
        self.framework = framework
        self.logger = config['logger']
        self.omni_config = config['omni']
        self.config = config
        self.opts = opts # command line options as parsed
        self.GetVersionCache = None # The cache of GetVersion info in memory
        self.clients = None # XMLRPC clients for talking to AMs
        if self.opts.abac:
            aconf = self.config['selected_framework']
            if 'abac' in aconf and 'abac_log' in aconf:
                self.abac_dir = aconf['abac']
                self.abac_log = aconf['abac_log']
            else:
                self.logger.error("ABAC requested (--abac) and no abac= or abac_log= in omni_config: disabling ABAC")
                self.opts.abac= False
                self.abac_dir = None
                self.abac_log = None

    def _handle(self, args):
        ''' Actually dispatch calls - only those that don't start with an underscore'''
        if len(args) == 0:
            self._raise_omni_error('Insufficient number of arguments - Missing command to run')
        
        call = args[0].lower()
        # disallow calling private methods
        if call.startswith('_'):
            return
        if not hasattr(self,call):
            self._raise_omni_error('Unknown function: %s' % call)

        # Extract the slice name arg and put it in an option
        self.opts.sliceName = self._extractSliceArg(args)

        # Try to auto-correct API version
        msg = self._correctAPIVersion(args)
        if msg is None:
            msg = ""

        (message, val) = getattr(self,call)(args[1:])
        if message is None:
            message = ""
        return (msg+message, val)

    # Pull any slice name arg out of the args and return it, else None
    # Ignore it for createsliver or allocate as no slice exists yet in these cases
    def _extractSliceArg(self, args):
        if args is None or len(args) == 0:
            return None
        call = args[0].lower().strip()
        # Skip createsliver and allocate and provision because the whole idea is to add a new AM here - so the CH doesn't know
        if call in ('getversion', 'listimages', 'deleteimage', 'createsliver', 'allocate', 'provision'): # createimage?
            return None
        elif len(args) > 1:
            ret = args[1].strip()
            if ret == "":
                return None
            self.logger.debug("Found slice name %s", ret)
            return ret

    def _correctAPIVersion(self, args):
        '''Switch AM API versions if the AMs all or mostly speak something else. But be conservative.'''

        cmd = None
        if len(args) > 0:
            cmd = args[0].strip().lower()

        # FIXME: Keep this check in sync with createsliver
        if cmd is not None and cmd == 'createsliver' and (not self.opts.aggregate or len(self.opts.aggregate) == 0):
            # the user must supply an aggregate.
            msg = 'Missing -a argument: specify an aggregate where you want the reservation.'
            self._raise_omni_error(msg)

        configVer = str(self.opts.api_version) # turn int into a string
        (clients, message) = self._getclients()
        numClients = len(clients)

        # If we know the method we are calling takes exactly 1 AM and we have more
        # than one here, bail. Note that later we remove bad AMs, so this is an imperfect check.

        # createimage takes exactly 1 client
        # FIXME: Keep this check in sync with createimage
        if cmd is not None and cmd == 'createimage' and numClients > 1:
            self._raise_omni_error("CreateImage snapshots a particular machine: specify exactly 1 AM URL with '-a'")

        liveVers = {}
        versions = {}
        retmsg = "" # Message to put at start of result summary
        i = -1 # Index of client in clients list
        badcIs = [] # Indices of bad clients to remove from list later
        for client in clients:
            i = i + 1
            (thisVer, message) = self._get_this_api_version(client)
            if thisVer is None:
                # Not a valid client
                numClients = numClients - 1
                badcIs.append(i) # Mark this client to be removed from the list later

                if message and message.strip() != '':
                    # Extract out of the message the real error
                    # raise that as an omni error
                    # FIXME: If messages change in dossl this won't work
                    if "Operation timed out" in message:
                        message = "Aggregate %s unreachable: %s" % (client.str, message[message.find("Operation timed out"):])
                    elif "Unknown socket error" in message:
                        message = "Aggregate %s unreachable: %s" % (client.str, message[message.find("Unknown socket error"):])
                    elif "Server does not trust" in message:
                        message = "Aggregate %s does not trust your certificate: %s" % (client.str, message[message.find("Server does not trust"):])
                    elif "Your user certificate" in message:
                        message = "Cannot contact aggregates: %s" % (message[message.find("Your user certificate"):])
                else:
                    message = 'Unknown error'
                if self.numOrigClients == 1:
                    self._raise_omni_error(message)
                msg = "Removing %s from list of aggregates to contact. %s " % (client.str, message)
                self.logger.warn(msg)
                retmsg += msg
                if retmsg.endswith(' ') or retmsg.endswith('.'):
                    retmsg += "\n"
                elif not retmsg.endswith('\n'):
                    retmsg += ".\n"
                continue
            thisVer = str(thisVer) # turn int into a string
            liveVers[thisVer]  = liveVers.get(thisVer, 0) + 1 # hash is by strings
            (thisVersions, message) = self._get_api_versions(client)
            # Ticket 242: be robust to malformed geni_api_versions
            if thisVersions and isinstance(thisVersions, dict):
                for version in thisVersions.keys(): # version is a string
#                    self.logger.debug("%s supports %d at %s", client.url, int(version), thisVersions[version])
                    versions[version] = versions.get(version, 0) + 1 # hash by strings
#                    self.logger.debug("%d spoken by %d", int(version), versions[version])
            else:
                #self.logger.debug("Incrementing counter of clients that speak %r somewhere", thisVer)
                versions[thisVer] = versions.get(thisVer, 0) + 1
        # End of loop over clients

        # Remove the bad clients now (not while looping over this same list)
        i = -1
        newcs = []
        for i in range(len(self.clients)):
            if i in badcIs:
#                self.logger.debug("Skipping client %s" % self.clients[i].url)
                continue
#            self.logger.debug("Saving client %s" % self.clients[i].url)
            newcs.append(self.clients[i])
        self.clients = newcs

        if len(self.clients) == 0:
            self._raise_omni_error(retmsg + "\nNo Aggregates left to operate on.")

        # If we didn't get any AMs, bail early
        if len(liveVers.keys()) == 0:
            return retmsg

        # If all the AMs talk the desired version here, great
        if liveVers.has_key(configVer) and liveVers[configVer] == numClients:
            self.logger.debug("Config version spoken here by all AMs")
            return retmsg

        # If all the AMs talk the desired version somewhere, fine. We'll switch URLs later.
        if versions.has_key(configVer) and versions[configVer] == numClients:
            self.logger.debug("Config version spoken somewhere by all AMs")
            return retmsg

        # Some AM does not talk the desired version
        self.logger.warn("You asked to use AM API %s, but the AM(s) you are contacting do not all speak that version.", configVer)

        # If all AMs speak the same (different) version at the current URL, use that
        if len(liveVers.keys()) == 1:
            newVer = int(liveVers.keys()[0])
            msg = "At the URLs you are contacting, all your AMs speak AM API v%d. " % newVer
            self.logger.warn(msg)
            if self.opts.devmode:
                self.logger.warn("Would switch AM API versions, but in dev mode, so continuing...")
            elif self.opts.explicitAPIVersion:
                retmsg = ("Your AMs do not all speak requested API v%s. " % configVer) + msg
                msg = "Continuing with your requested API version %s, but consider next time calling Omni with '-V%d'." % (configVer, newVer)
                retmsg += msg + "\n"
                self.logger.warn(msg)
            else:
                retmsg = ("Your AMs do not all speak requested API v%s. " % configVer) + msg
                msg = "Switching to AM API v%d. Next time call Omni with '-V%d'." % (newVer, newVer)
                retmsg += msg + "\n"
                self.logger.warn(msg)
                self.opts.api_version = newVer
            return retmsg

        # If the configured version is spoken somewhere by a majority of AMs, use it
        if versions.has_key(configVer) and float(versions[configVer]) >= float(numClients)/float(2):
            self.logger.debug("Config version spoken somewhere by a majority of AMs")
            #self.logger.debug("numClients/2 = %r", float(numClients)/float(2))
            self.logger.info("Sticking with API version %s, even though only %d of %d AMs support it", configVer, versions[configVer], numClients)
            return retmsg

        self.logger.warn("Configured API version %s is not supported by most of your AMs", configVer)

        # We could now prefer the version that the most AMs talk at the current URL - particularly if that
        # is the configVer
        # Or a version that the most AMs talk at another URL (could be all) - particularly if that is the
        # configVer again

        # So we need to find the version that the most AMs support.
        # Sort my versions array by value
        from operator import itemgetter
        sortedVersions = sorted(versions.iteritems(), key=itemgetter(1), reverse=True)
        sortedLiveVersions = sorted(liveVers.iteritems(), key=itemgetter(1), reverse=True)
        mostLive = sortedLiveVersions[0][0]
        mostAnywhere = sortedVersions[0][0]

        if mostLive == configVer or (liveVers.has_key(configVer) and liveVers[configVer] == liveVers[mostLive]):
            # The configured API version is what is spoken at the most AMs at the current URL
            self.logger.debug("Config version is the most common live version")
            configSup = versions.get(configVer, 0)
            self.logger.info("Sticking with API version %d, even though only %d of %d AMs support it", configVer, configSup, numClients)
            return retmsg

        if liveVers[mostLive] == numClients:
            newVer = int(mostLive)
            msg = "At the URLs you are contacting, all your AMs speak AM API v%d. " % newVer
            self.logger.warn(msg)
            if self.opts.devmode:
                self.logger.warn("Would switch AM API version, but continuing...")
            elif self.opts.explicitAPIVersion:
                retmsg = "Most of your AMs do not support requested API version %d. " + msg
                msg = "Continuing with your requested API version %s, but consider next time calling Omni with '-V%d'." % (configVer, newVer)
                retmsg += msg + "\n"
                self.logger.warn(msg)
            else:
                msg = "Switching to AM API v%d. Next time call Omni with '-V%d'." % (newVer, newVer)
                retmsg += msg + "\n"
                self.logger.warn(msg)
                self.opts.api_version = newVer
            return retmsg

        if mostAnywhere == configVer or (versions.has_key(configVer) and versions[configVer] == versions[mostAnywhere]):
            # The configured API version is what is spoken at the most AMs at _some_ URL
            self.logger.debug("Config version is the most common anywhere version")
            self.logger.info("Sticking with API version %s, even though only %d of %d AMs support it", configVer, versions[configVer], numClients)
            return retmsg

        # If we get here, the configured version is not the most popular, nor supported by most AMs
        # IE, something else is more popular

        if versions[mostAnywhere] == numClients:
            # The most popular anywhere API version is spoken by all AMs
            newVer = int(mostAnywhere)
            if self.opts.devmode:
                self.logger.warn("Would switch AM API version to %d, which is supported by all your AMs, but continuing...")
            elif self.opts.explicitAPIVersion:
                msg = "Continuing with your requested API version %s (even though it is not well supported by your AMs), but consider next time calling Omni with '-V%d' (which all your AMs support). " % (configVer, newVer)
                self.logger.warn(msg)
                retmsg = msg + "\n"
            else:
                retmsg = "Your requested AM API version is not well supported by your AMs. "
                msg = "Switching to AM API v%d, which is supported by all your AMs. Next time call Omni with '-V%d'." % (newVer, newVer)
                retmsg += msg + "\n"
                self.logger.warn(msg)
                self.opts.api_version = newVer
            return retmsg

        if float(liveVers[mostLive]) >= float(numClients)/float(2):
            # The most popular live API version is spoken by a majority of AMs
            newVer = int(mostLive)
            if self.opts.devmode:
                self.logger.warn("Would switch AM API version to %d, which is running at a majority of your AMs, but continuing...", newVer)
            elif self.opts.explicitAPIVersion:
                msg = "Continuing with your requested API version %s (which is not well supported by your AMs), but consider next time calling Omni with '-V%d' (which most of your AMs are running). " % (configVer, newVer)
                self.logger.warn(msg)
                retmsg = msg + "\n"
            else:
                msg = "Switching to AM API v%d, which is running at a majority of your AMs. Next time call Omni with '-V%d'." % (newVer, newVer)
                retmsg = msg + "\n"
                self.logger.warn(msg)
                self.opts.api_version = newVer
            return retmsg

        if float(versions[mostAnywhere]) >= float(numClients)/float(2):
            # The most popular anywhere API version is spoken by a majority of AMs
            newVer = int(mostAnywhere)
            if self.opts.devmode:
                self.logger.warn("Would switch AM API version to %d, which is supported by a majority of your AMs, but continuing...", newVer)
            elif self.opts.explicitAPIVersion:
                msg = "Continuing with your requested API version %s, but consider next time calling Omni with '-V%d' (which is supported by most of your AMs). " % (configVer, newVer)
                retmsg = msg + "\n"
                self.logger.warn(msg)
            else:
                msg = "Switching to AM API v%d, which is supported by a majority of your AMs. Next time call Omni with '-V%d'." % (newVer, newVer)
                retmsg = msg + "\n"
                self.logger.warn(msg)
                self.opts.api_version = newVer
            return retmsg

        # No API version is supported by a majority of AMs

        if versions.has_key(configVer) and versions[configVer] > 0:
            # Somebody speaks the desired version. Use that
            self.logger.debug("Config ver is supported _somewhere_ at least")
            return retmsg

        # No AM speaks the desired API version. No version is supported by a majority of AMs
        # Go with the most popular live version? The most popular anywhere version?

        newVer = int(mostAnywhere)
        if self.opts.devmode:
            self.logger.warn("Would switch AM API version to %d, the most commonly supported version, but continuing...", newVer)
        elif self.opts.explicitAPIVersion:
            msg = "Continuing with your requested API version %s, but consider next time calling Omni with '-V%d' (which is the most common version your AMs support). " % (configVer, newVer)
            retmsg = msg + "\n"
            self.logger.warn(msg)
        else:
            msg = "Switching to AM API v%d, the most commonly supported version. Next time call Omni with '-V%d'." % (newVer, newVer)
            retmsg = msg + "\n"
            self.logger.warn(msg)
            self.opts.api_version = newVer
        return retmsg


    # ------- AM API methods and direct support methods follow

    # FIXME: This method manipulates the message. Need to separate Dev/Exp
    # Also, it marks whether it used the cache through the message. Is there a better way?
    # Helper indicates a function to get one of the getversion return attributes called this, 
    # So make messages indicate not 'getversion' but that we were trying to get an attribute
    def _do_getversion(self, client, helper=False):
        '''Pull GetVersion for this AM from cache; otherwise actually call GetVersion if this
        AM wasn't in the cache, the options say not to use the cache, or the cache is too old.

        If we actually called GetVersion:
        Construct full error message including string version of code/output slots.
        Then cache the result.
        If we got the result from the cache, set the message to say so.
        '''
        cachedVersion = None
        if not self.opts.noGetVersionCache:
            cachedVersion = self._get_cached_getversion(client)
        # FIXME: What if cached entry had an error? Should I retry then?
        if self.opts.noGetVersionCache or cachedVersion is None or (self.opts.GetVersionCacheOldestDate and cachedVersion['timestamp'] < self.opts.GetVersionCacheOldestDate):
            self.logger.debug("Actually calling GetVersion")
            if self.opts.noGetVersionCache:
                self.logger.debug(" ... opts.noGetVersionCache set")
            elif cachedVersion is None:
                self.logger.debug(" ... cachedVersion was None")
            failMsg = "GetVersion at %s" % (str(client.str))
            if helper:
                failMsg = "Check AM properties at %s" % (str(client.str))
            if self.opts.api_version >= 2:
                options = self._build_options("GetVersion", None, None)
                if len(options.keys()) == 0:
                    (thisVersion, message) = _do_ssl(self.framework, None, failMsg, client.GetVersion)
                else:
                    (thisVersion, message) = _do_ssl(self.framework, None, failMsg, client.GetVersion, options)
            else:
                (thisVersion, message) = _do_ssl(self.framework, None, failMsg, client.GetVersion)

            # This next line is experimenter-only maybe?
            message = _append_geni_error_output(thisVersion, message)

            # Cache result, even on error (when we note the error message)
            self._cache_getversion(client, thisVersion, message)
        else:
            self.logger.debug("Pulling GetVersion from cache")
            thisVersion = cachedVersion['version']
            message = "From cached result from %s" % cachedVersion['timestamp']
        return (thisVersion, message)

    def _do_getversion_output(self, thisVersion, client, message):
        '''Write GetVersion output to a file or log depending on options.
        Return a string to print that we saved it to a file, if that's what we did.
        '''
        # FIXME only print 'peers' on verbose? (Or is peers gone now?)
        # FIXME: Elsewhere we use json.dumps - should we do so here too?
        #     This is more concise and looks OK - leave it for now
        pp = pprint.PrettyPrinter(indent=4)
        prettyVersion = pp.pformat(thisVersion)
        if client.nick:
            header = "AM %s URN: %s (url: %s) has version:" % (client.nick, client.urn, client.url)
            if self.opts.devmode:
                amstr = "%s (%s, %s)" % (client.nick, client.urn, client.url)
            else:
                amstr = client.nick
        else:
            header = "AM URN: %s (url: %s) has version:" % (client.urn, client.url)
            amstr = "%s (%s)" % (client.urn, client.url)
        if message:
            header += " (" + message + ")"
        filename = None
        if self.opts.output:
            # Create filename
            filename = _construct_output_filename(self.opts, None, client.url, client.urn, "getversion", ".json", 1)
            self.logger.info("Writing result of getversion at AM %s to file '%s'", amstr, filename)
        # Create File
        # This logs or prints, depending on whether filename is None
        _printResults(self.opts, self.logger, header, prettyVersion, filename)

        # FIXME: include filename in summary: always? only if 1 aggregate?
        if filename:
            return "Saved getversion at AM %s to file '%s'.\n" % (amstr, filename)
        else:
            return ""

    def _save_getversion_cache(self):
        '''Write GetVersionCache object to file as JSON (creating it and directories if needed)'''
        #client url->
        #      timestamp (a datetime.datetime)
        #      version struct, including code/value/etc as appropriate
        #      urn
        #      url
        #      lasterror
        if self.opts.noCacheFiles:
            self.logger.debug("Per option noCacheFiles, not saving GetVersion cache")
            return
        fdir = os.path.dirname(self.opts.getversionCacheName)
        if fdir and fdir != "":
            if not os.path.exists(fdir):
                os.makedirs(fdir)
        try:
            with open(self.opts.getversionCacheName, 'w') as f:
                json.dump(self.GetVersionCache, f, cls=DateTimeAwareJSONEncoder)
            self.logger.debug("Wrote GetVersionCache to %s", self.opts.getversionCacheName)
        except Exception, e:
            self.logger.error("Failed to write GetVersion cache: %s", e)

    def _load_getversion_cache(self):
        '''Load GetVersion cache from JSON encoded file, if any'''
        self.GetVersionCache = {}
        if self.opts.noCacheFiles:
            self.logger.debug("Per option noCacheFiles, not loading get version cache")
            return
        #client url->
        #      timestamp (a datetime.datetime)
        #      version struct, including code/value/etc as appropriate
        #      urn
        #      url
        #      lasterror
        if not os.path.exists(self.opts.getversionCacheName) or os.path.getsize(self.opts.getversionCacheName) < 1:
            return
        try:
            with open(self.opts.getversionCacheName, 'r') as f:
                self.GetVersionCache = json.load(f, encoding='ascii', cls=DateTimeAwareJSONDecoder)
            self.logger.debug("Read GetVersionCache from %s", self.opts.getversionCacheName)
        except Exception, e:
            self.logger.error("Failed to read GetVersion cache: %s", e)

    # FIXME: This saves every time we add to the cache. Is that right?
    def _cache_getversion(self, client, thisVersion, error=None):
        '''Add to Cache the GetVersion output for this AM.
        If this was an error, don't over-write any existing good result, but record the error message

        This methods both loads and saves the cache from file.
        '''
        # url, urn, timestamp, apiversion, rspecversions (type version, type version, ..), credtypes (type version, ..), single_alloc, allocate, last error and message
        res = {}
        if error and error.startswith(" (PG log ur"):
            # If the only error string is the pointer to the PG log url, treat this as no error
            error = None
        if error:
            # On error, pretend this is old, to force refetch
            res['timestamp'] = datetime.datetime.min
        else:
            res['timestamp'] = datetime.datetime.utcnow()
        res['version'] = thisVersion
        if client is not None and client.urn is not None and str(client.urn).strip() != "":
            res['urn'] = client.urn
        elif client is not None and client.url is not None:
            res['urn'] = client.url
        else:
            res['urn'] = "unspecified_AM_URN"
        if client is not None and client.url is not None:
            res['url'] = client.url
        else:
            res['url'] = "unspecified_AM_URL"
        res['error'] = error
        if self.GetVersionCache is None:
            # Read the file as serialized JSON
            self._load_getversion_cache()
        if error:
            # On error, leave existing data alone - just record the last error
            if self.GetVersionCache.has_key(client.url):
                self.GetVersionCache[client.url]['lasterror'] = error
            self.logger.debug("Added GetVersion error output to cache for %s: %s", client.url, error)
        else:
            self.GetVersionCache[client.url] = res
            self.logger.debug("Added GetVersion success output to cache for %s", client.url)

        # Write the file as serialized JSON
        self._save_getversion_cache()

    def _get_cached_getversion(self, client):
        '''Get GetVersion from cache or this AM, if any.'''
        if self.GetVersionCache is None:
            self._load_getversion_cache()
        if self.GetVersionCache is None:
            return None
        self.logger.debug("Checking cache for %s", client.url)
        if isinstance(self.GetVersionCache, dict) and self.GetVersionCache.has_key(client.url):
            # FIXME: Could check that the cached URN is same as the client urn?
            return self.GetVersionCache[client.url]

    # FIXME: Is this too much checking/etc for developers?
    # See _check_valid_return_struct: lots of overlap, but this checks the top-level geni_api
    # FIXME: The return from the cache doesn't really need to be rechecked, does it? Or will that not happen?
    # Helper indicates a function to get one of the getversion return attributes called this, 
    # So make messages indicate not 'getversion' but that we were trying to get an attribute
    def _do_and_check_getversion(self, client, helper=False):
        '''Do GetVersion (possibly from cache), then check return for errors,
        constructing a good message. 
        Basically, add return checks to _do_getversion'''
        op = "getversion"
#        if helper:
#            op = "check AM properties"
        message = None
        (thisVersion, message) = self._do_getversion(client, helper)
        if thisVersion is None:
            # error
            message = "AM %s failed %s (empty): %s" % (client.str, op, message)
            return (None, message)
        elif not isinstance(thisVersion, dict):
            # error
            message = "AM %s failed %s (returned %s): %s" % (client.str, op, thisVersion, message)
            return (None, message)
        elif not thisVersion.has_key('geni_api'):
            # error
            message = "AM %s failed %s (no geni_api at top: %s): %s" % (client.str, op, thisVersion, message)
            return (None, message)
        elif thisVersion['geni_api'] == 1:
            # No more checking to do - return it as is
            return (thisVersion, message)
        elif not thisVersion.has_key('value'):
            message = "AM %s failed %s (no value: %s): %s" % (client.str, op, thisVersion, message)
            return (None, message)
        elif not thisVersion.has_key('code'):
            message = "AM %s failed %s (no code: %s): %s" % (client.str, op, thisVersion, message)
            return (None, message)
        elif not thisVersion['code'].has_key('geni_code'):
            message = "AM %s failed %s (no geni_code: %s): %s" % (client.str, op, thisVersion, message)
            # error
            return (None, message)
        elif thisVersion['code']['geni_code'] != 0:
            # error
            # This next line is experimenter-only maybe?
            message = "AM %s failed %s: %s" % (client.str, op, _append_geni_error_output(thisVersion, message))
            return (None, message)
        elif not isinstance(thisVersion['value'], dict):
            message = "AM %s failed %s (non dict value %s): %s" % (client.str, op, thisVersion['value'], message)
            return (None, message)
        # OK, we have a good result
        return (thisVersion, message)

    # This is the real place that ends up calling GetVersion
    # FIXME: As above: this loses the code/output slots and any other top-level slots.
    #  Maybe only for experimenters?

    # Helper indicates a function to get one of the getversion return attributes called this, 
    # So make messages indicate not 'getversion' but that we were trying to get an attribute
    def _get_getversion_value(self, client, helper=False):
        '''Do GetVersion (possibly from cache), check error returns to produce a message,
        pull out the value slot (dropping any code/output).'''
        message = None

        # We cache results by URL
        if not hasattr(self, 'gvValueCache'):
            self.gvValueCache = dict()
        if self.gvValueCache.has_key(client.url):
            return self.gvValueCache[client.url]

        (thisVersion, message) = self._do_and_check_getversion(client, helper)
        if thisVersion is None:
            # error - return what the error check had
            return (thisVersion, message)
        elif thisVersion['geni_api'] == 1:
            versionSpot = thisVersion
        else:
            versionSpot = thisVersion['value']
        self.gvValueCache[client.url] = (versionSpot, message)
        return (versionSpot, message)

    # Helper indicates a function to get one of the getversion return attributes called this, 
    # So make messages indicate not 'getversion' but that we were trying to get an attribute
    def _get_getversion_key(self, client, key, helper=False):
        '''Pull the given key from the GetVersion value object'''
        if key is None or key.strip() == '':
            return (None, "no key specified")
        (versionSpot, message) = self._get_getversion_value(client, helper)
        if versionSpot is None:
            return (None, message)
        elif not versionSpot.has_key(key):
            message2 = "AM %s getversion has no key %s" % (client.str, key)
            if message:
                message = message2 + "; " + message
            else:
                message = message2
            return (None, message)
        else:
            return (versionSpot[key], message)

    def _get_this_api_version(self, client):
        '''Get the supported API version for this AM (from GetVersion)'''
        (res, message) = self._get_getversion_key(client, 'geni_api', helper=True)
        if res is None:
            self.logger.debug("Couldn't get api version supported from GetVersion: %s" % message)
        # Return is an int API version
        return (res, message)

    def _get_api_versions(self, client):
        '''Get the supported API versions and URLs for this AM (from GetVersion)'''
        (res, message) = self._get_getversion_key(client, 'geni_api_versions', helper=True)
        if res is None:
            msg = "Couldnt get api versions supported from GetVersion: %s" % message
            (thisVer, msg2) = self._get_getversion_key(client, 'geni_api', helper=True)
            if thisVer and thisVer < 2:
                self.logger.debug(msg)
            else:
                self.logger.warning(msg)
        # Return is a dict: Int API version -> string URL of AM
        return (res, message)

    def _get_advertised_rspecs(self, client):
        '''Get the supported advertisement rspec versions for this AM (from GetVersion)'''
        (ads, message) = self._get_getversion_key(client, 'ad_rspec_versions', helper=True)
        if ads is None:
            if message and "has no key" in message:
                (ads, message) = self._get_getversion_key(client, 'geni_ad_rspec_versions', helper=True)

        if ads is None:
            self.logger.warning("Couldnt get Advertised supported RSpec versions from GetVersion so can't do ListResources: %s" % message)

        # Return is array of dicts with type, version, schema, namespace, array of extensions 
        return (ads, message)

    def _get_request_rspecs(self, client):
        '''Get the supported request rspec versions for this AM (from GetVersion)'''
        (ads, message) = self._get_getversion_key(client, 'request_rspec_versions', helper=True)
        if ads is None:
            if message and "has no key" in message:
                (ads, message) = self._get_getversion_key(client, 'geni_request_rspec_versions', helper=True)

        if ads is None:
            self.logger.warning("Couldnt get Request supported RSpec versions from GetVersion: %s" % message)

        # Return is array of dicts with type, version, schema, namespace, array of extensions 
        return (ads, message)

    def _get_cred_versions(self, client):
        '''Get the supported credential types for this AM (from GetVersion)'''
        (res, message) = self._get_getversion_key(client, 'geni_credential_types', helper=True)
        if res is None:
            self.logger.warning("Couldnt get credential types supported from GetVersion: %s" % message)
        # Return is array of dicts: geni_type, geni_version
        return (res, message)

    def _get_singlealloc_style(self, client):
        '''Get the supported single_allocation for this AM (from GetVersion)'''
        (res, message) = self._get_getversion_key(client, 'geni_single_allocation', helper=True)
        if res is None:
            self.logger.debug("Couldnt get single_allocation mode supported from GetVersion; will use default of False: %s" % message)
            res = False
        # return is boolean
        return (res, message)

    def _get_alloc_style(self, client):
        '''Get the supported geni_allocate allocation style for this AM (from GetVersion)'''
        (res, message) = self._get_getversion_key(client, 'geni_allocate', helper=True)
        if res is None:
            self.logger.debug("Couldnt get allocate style supported from GetVersion; will use default of 'geni_single': %s" % message)
            res = 'geni_single'
        # Return is string: geni_single, geni_disjoint, or geni_many
        return (res, message)

    def _api_call(self, client, msg, op, args):
        '''Make the AM API Call, after first checking that the AM we are talking
        to is of the right API version.'''
        (ver, newc, validMsg) = self._checkValidClient(client)
        if newc is None:
            # if the error reason is just that the client is not
            # reachable then clean up the error message
            if "Operation timed out" in validMsg:
                validMsg = "Aggregate %s unreachable: %s" % (client.str, validMsg[validMsg.find("Operation timed out"):])
            elif "Unknown socket error" in validMsg:
                validMsg = "Aggregate %s unreachable: %s" % (client.str, validMsg[validMsg.find("Unknown socket error"):])
            elif "Server does not trust" in validMsg:
                validMsg = "Aggregate %s does not trust your certificate: %s" % (client.str, validMsg[validMsg.find("Server does not trust"):])
            elif "Your user certificate" in validMsg:
                validMsg = "Cannot contact aggregates: %s" % (validMsg[validMsg.find("Your user certificate"):])

            # Theoretically could remove bad client here. But nothing uses the clients list after an _api_call
            # And removing it here is dangerous if we're inside a loop over the clients
            raise BadClientException(client, validMsg)
        elif newc.url != client.url:
            if ver != self.opts.api_version:
                self.logger.error("AM %s doesn't speak API version %d. Try the AM at %s and tell Omni to use API version %d, using the option '-V%d'.", client.str, self.opts.api_version, newc.url, ver, ver)
                raise BadClientException(client, validMsg)
#                self.logger.warn("Changing API version to %d. Is this going to work?", ver)
#                # FIXME: changing the api_version is not a great idea if
#                # there are multiple clients. Push this into _checkValidClient
#                # and only do it if there is one client.
#
#                # FIXME: changing API versions means unwrap or wrap cred, maybe change the op name, ...
#                # This may work for getversion, but likely not for other methods!
#                self.opts.api_version = ver
            else:
                pass

            # Theoretically could remove bad client here and add the correct one. But nothing uses the clients list after an _api_call
            # And removing it here is dangerous if we're inside a loop over the clients

            client = newc
        elif ver != self.opts.api_version:
            self.logger.error("AM %s doesn't speak API version %d. Tell Omni to use API version %d, using the option '-V%d'.", client.str, self.opts.api_version, ver, ver)
            raise BadClientException(client, validMsg)

        self.logger.debug("Doing SSL/XMLRPC call to %s invoking %s", client.url, op)
        #self.logger.debug("Doing SSL/XMLRPC call to %s invoking %s with args %r", client.url, op, args)
        return _do_ssl(self.framework, None, msg, getattr(client, op), *args), client

    # FIXME: Must still factor dev vs exp
    # For experimenters: If exactly 1 AM, then show only the value slot, formatted nicely, printed to STDOUT.
    # If it fails, show only why
    # If saving to file, print out 'saved to file <foo>', or the error if it failed
    # If querying multiple, then print a header for each before printing to STDOUT, otherwise like above.

    # For developers, maybe leave it like this? Print whole struct not just the value?
    def getversion(self, args):
        """AM API GetVersion
        Get basic information about the aggregate and how to talk to it.

        Aggregates queried:
        - Each URL given in an -a argument or URL listed under that given
        nickname in omni_config, if provided, ELSE
        - List of URLs given in omni_config aggregates option, if provided, ELSE
        - List of URNs and URLs provided by the selected clearinghouse
        - Note that --useSliceAggregates is not honored as no slice name is provided.

        Output directing options:
        -o Save result (JSON format) in per-Aggregate files
        -p (used with -o) Prefix for resulting version information filenames
        --outputfile If supplied, use this output file name: substitute the AM for any %a
        If not saving results to a file, they are logged.
        If --tostdout option, then instead of logging, print to STDOUT.

        Omni caches getversion results for use elsewhere. This method skips the local cache.
        --ForceUseGetVersionCache will force it to look at the cache if possible
        --GetVersionCacheAge <#> specifies the # of days old a cache entry can be, before Omni re-queries the AM, default is 7
        --GetVersionCacheName <path> is the path to the GetVersion cache, default is ~/.gcf/get_version_cache.json

        --devmode causes Omni to continue on bad input, if possible
        -V# specifies the AM API version to attempt to speak
        -l to specify a logging config file
        --logoutput <filename> to specify a logging output filename

        Sample usage:
        omni.py -a http://myaggregate/url -V2 getversion
        """

        ### Method specific arg handling

        # Ensure GetVersion skips the cache, unless commandline option forces the cache
        if not self.opts.useGetVersionCache:
            self.opts.noGetVersionCache = True

        # Start basic loop over clients
        retVal = ""
        version = {}
        (clients, message) = self._getclients()
        numClients = len(clients)
        successCnt = 0
        for client in clients:
            # Pulls from cache or caches latest, error checks return
            # getversion output should be the whole triple
            (thisVersion, message) = self._do_and_check_getversion(client)
            if self.opts.devmode:
                pp = pprint.PrettyPrinter(indent=4)
                prettyVersion = pp.pformat(thisVersion)
                self.logger.debug("AM %s raw getversion:\n%s", client.url, prettyVersion)
            thisVersionValue, message = self._retrieve_value(thisVersion, message, self.framework)

            # Method specific result handling
            version[ client.url ] = thisVersion
            
            # Per client result outputs:
            if version[client.url] is None:
                # FIXME: SliverStatus sets these to False. Should this for consistency?
                self.logger.warn("URN: %s (url:%s) GetVersion call failed: %s\n" % (client.urn, client.url, message) )
                retVal += "Cannot GetVersion at %s: %s\n" % (client.str, message)
            else:
                successCnt += 1
                retVal += self._do_getversion_output(thisVersionValue, client, message)
        # End of loop over clients

        ### Method specific all-results handling, printing
        if numClients==0:
            retVal += "No aggregates to query. %s\n\n" % message
        else:
            if self.numOrigClients>1:
                # FIXME: If I have a message from getclients, want it here?
                if "From Cache" in message:
                    retVal += "\nGot version for %d out of %d aggregates using GetVersion cache\n" % (successCnt,self.numOrigClients)
                else:
                    retVal += "\nGot version for %d out of %d aggregates\n" % (successCnt,self.numOrigClients)
            else:
                if successCnt == 1:
                    retVal += "\nGot version for %s\n" % clients[0].str
                else:
                    retVal += "\nFailed to get version for %s\n" % clients[0].str
                if "From Cache" in message:
                    retVal += message + "\n"
        return (retVal, version)

    # ------- End of GetVersion stuff

    def _selectRSpecVersion(self, slicename, client, mymessage, options):
        '''Helper for Describe and ListResources and Provision to set the rspec_version option, based on a single AMs capabilities.
        Uses -t argument: If user specified an RSpec type and version, then only
        use AMs that support that type/version (default is GENI 3).
        Return dict with API version appropriate key specifying RSpec type/version
        to request, plus a message describing results.
        Raise a BadClientException if the AM cannot support the given RSpect type
        or didn't advertise what it supports.'''

        # If the user specified a specific rspec type and version,
        # then we ONLY get rspecs from each AM that is capable
        # of talking that type&version.
        # Note an alternative would have been to let the AM just
        # do whatever it likes to do if
        # you ask it to give you something it doesn't understand.
        if self.opts.rspectype:
            rtype = self.opts.rspectype[0]
            rver = self.opts.rspectype[1]
            self.logger.debug("Will request RSpecs only of type %s and version %s", rtype, rver)

            # Note this call uses the GetVersion cache, if available
            # If got a slicename, use request rspecs to better match manifest support
            if not slicename:
                (ad_rspec_version, message) = self._get_advertised_rspecs(client)
            else:
                (ad_rspec_version, message) = self._get_request_rspecs(client)
            if ad_rspec_version is None:
                if message:
                    if mymessage != "":
                        mymessage += ". "
                    mymessage = mymessage + message
                self.logger.debug("AM %s failed to advertise supported RSpecs", client.str)
                # Allow developers to call an AM that fails to advertise
                if not self.opts.devmode:
                    # Skip this AM/client
                    raise BadClientException(client, mymessage)
                else:
                    self.logger.debug("... but continuing")
                    ad_rspec_version = ()

            self.logger.debug("Got %d supported RSpec versions", len(ad_rspec_version))
            # foreach item in the list that is the val
            match = False
            hasGENI3 = False
            hasPG2 = False
            for availversion in ad_rspec_version:
                if not (availversion.has_key('type') and availversion.has_key('version')):
                    self.logger.warning("AM getversion rspec_version entry malformed: no type or no version")
                    continue

                # version is also a string
                if str(availversion['type']).lower().strip() == rtype.lower().strip() and str(availversion['version']).lower().strip() == str(rver).lower().strip():
                    # success
                    self.logger.debug("Found a matching supported type/ver: %s/%s", availversion['type'], availversion['version'])
                    match = True
                    rtype=availversion['type']
                    rver=availversion['version']
                    break
                if str(availversion['type']).lower().strip() == 'geni' and str(availversion['version']).lower().strip() == '3':
                    hasGENI3 = True
                elif str(availversion['type']).lower().strip() == 'protogeni' and str(availversion['version']).lower().strip() == '2':
                    hasPG2 = True

            # if no success
            if match == False:
                # if user did not explicitly specify this version, then maybe try to get the RSpec with another format
                if not self.opts.explicitRSpecVersion:
                    # if only 1 version is supported, use it
                    if len(ad_rspec_version) == 1:
                        ver = ad_rspec_version[0]
                        if ver.has_key('type') and ver.has_key('version'):
                            self.logger.warning("AM doesn't support default RSpec version %s %s. Returning RSpec in only supported format. Next time at this AM, call Omni with '-t %s %s'.", rtype, rver, ver['type'], ver['version'])
                            rtype=ver['type']
                            rver=ver['version']
                    # if this is an ad, and default_ad_rspec is set, use that
                    # FIXME: Maybe do this even for manifests?
                    elif not slicename:
                        (default_ad, message) = self._get_getversion_key(client, 'default_ad_rspec')
                        if default_ad and default_ad.has_key('type') and default_ad.has_key('version'):
                            self.logger.warning("AM doesn't support default RSpec version %s %s. Returning RSpec in AM specified default Ad format. Next time at this AM, call Omni with '-t %s %s'.", rtype, rver, default_ad['type'], default_ad['version'])
                            rtype=default_ad['type']
                            rver=default_ad['version']
                    # more than 1 format advertised but no default.
                else:
                    # User explicitly picked this version that is not supported
                    # FIXME: Could or should we pick PGv2 if GENIv3 not there, and vice versa?

                    #   return error showing ad_rspec_versions
                    pp = pprint.PrettyPrinter(indent=4)
                    self.logger.warning("AM cannot provide Rspec in requested version (%s %s) at AM %s. This AM only supports: \n%s", rtype, rver, client.str, pp.pformat(ad_rspec_version))
                    tryOthersMsg = "";
                    if hasGENI3:
                        tryOthersMsg = ". Try calling Omni with '-t GENI 3' for GENI v3 RSpecs."
                    elif hasPG2:
                        tryOthersMsg = ". Try calling Omni with '-t ProtoGENI 2' for ProtoGENI v2 RSpecs."
                    else:
                        tryOthersMsg = ". Try calling Omni with '-t <another supported RSpec format>'."
                    if mymessage != "" and not mymessage.endswith('.'):
                        mymessage += ". "

                    if not self.opts.devmode:
                        mymessage = mymessage + "Skipped AM %s that didnt support required RSpec format %s %s" % (client.str, rtype, rver)
                        mymessage = mymessage + tryOthersMsg
                        # Skip this AM/client
                        raise BadClientException(client, mymessage)
                    else:
                        mymessage = mymessage + "AM %s didnt support required RSpec format %s %s, but continuing" % (client.str, rtype, rver)

#--- API version differences:
            if self.opts.api_version == 1:
                options['rspec_version'] = dict(type=rtype, version=rver)
            else:
                options['geni_rspec_version'] = dict(type=rtype, version=rver)

#--- Dev mode should not force supplying this option maybe?
        # This elif is only if no rspec type option was supplied - which you can't really do at this point
        elif self.opts.api_version >= 2:
            # User did not specify an rspec type but did request version 2.
            # Make an attempt to do the right thing, otherwise bail and tell the user.
            if not slicename:
                (ad_rspec_version, message) = self._get_advertised_rspecs(client)
            else:
                (ad_rspec_version, message) = self._get_request_rspecs(client)
            if ad_rspec_version is None:
                if message:
                    if mymessage != "" and not mymessage.endswith('.'):
                        mymessage += ". "
                    mymessage = mymessage + message
                self.logger.debug("AM %s failed to advertise supported RSpecs", client.str)
                # Allow developers to call an AM that fails to advertise
                if not self.opts.devmode:
                    # Skip this AM/client
                    raise BadClientException(client, mymessage)

            if len(ad_rspec_version) == 1:
                # there is only one advertisement, so use it.
                options['geni_rspec_version'] = dict(type=ad_rspec_version[0]['type'],
                                                     version=ad_rspec_version[0]['version'])
            # FIXME: if there is a default_ad_rspec and this is for ads, use that?
            else:
                # FIXME: Could we pick GENI v3 if there, else PG v2?

                # Inform the user that they have to pick.
                ad_versions = [(x['type'], x['version']) for x in ad_rspec_version]
                self.logger.warning("Please use the -t option to specify the desired RSpec type for AM %s as one of %r", client.str, ad_versions)
                if mymessage != "" and not mymessage.endswith('.'):
                    mymessage += ". "
                mymessage = mymessage + "AM %s supports multiple RSpec versions: %r" % (client.str, ad_versions)
                if not self.opts.devmode:
                    # Skip this AM/client
                    raise BadClientException(client, mymessage)
        return (options, mymessage)
    # End of _selectRSpecVersion

    def _maybeDecompressRSpec(self, options, rspec):
        '''Helper to decompress an RSpec string if necessary'''
        if rspec is None or rspec.strip() == "":
            return rspec

        if options.get('geni_compressed', False):
            try:
                rspec = zlib.decompress(rspec.decode('base64'))
            except Exception, e:
                if rspec and rspec_util.is_rspec_string(rspec, None, None, logger=self.logger):
                    self.logger.debug("AM returned uncompressed RSpec when compressed was requested")
                else:
                    self.logger.error("Failed to decompress RSpec: %s", e);
                self.logger.debug("RSpec begins: '%s'", rspec[:min(40, len(rspec))])
        # In experimenter mode, maybe notice if the rspec appears compressed anyhow and try to decompress?
        elif not self.opts.devmode and rspec and not rspec_util.is_rspec_string(rspec, None, None, logger=self.logger):
            try:
                rspec2 = zlib.decompress(rspec.decode('base64'))
                if rspec2 and rspec_util.is_rspec_string(rspec2, None, None, logger=self.logger):
                    rspec = rspec2
            except Exception, e:
                pass
        return rspec

    def _listresources(self, args):
        """Support method for doing AM API ListResources. Queries resources on various aggregates.
        
        Takes an optional slicename.

        Aggregates queried:
        - If `--useSliceAggregates`, each aggregate recorded at the clearinghouse as having resources for the given slice,
          '''and''' any aggregates specified with the `-a` option.
         - Only supported at some clearinghouses, and the list of aggregates is only advisory
        - Each URL given in an -a argument or URL listed under that given
        nickname in omni_config, if provided, ELSE
        - List of URLs given in omni_config aggregates option, if provided, ELSE
        - List of URNs and URLs provided by the selected clearinghouse

        If you specify a required Ad RSpec type and version (both strings. Use the -t option)
        then it skips any AM that doesn't advertise (in GetVersion) that it supports that format.
        Note that -t GENI 3 is the default.

        Returns a dictionary of rspecs with the following format:
           rspecs[(urn, url)] = return struct, containing a decompressed rspec
           AND a string describing the result.
        On error the dictionary is None and the message explains.

        Decompress the returned RSpec if necessary

        --arbitrary-option: supply arbitrary thing for testing
        -V# API Version #
        --devmode: Continue on error if possible
        --no-compress: Request the returned RSpec not be compressed (default is to compress)
        --available: Return Ad of only available resources
        """

        # rspecs[(urn, url)] = decompressed rspec
        rspecs = {}
        options = {}
        
        # Pass in a dummy option for testing that is actually ok
        # FIXME: Omni should have a standard way for supplying additional options. Something like extra args
        # of the form Name=Value
        # Then a standard helper function could be used here to split them apart
        if self.opts.arbitrary_option:
            options['arbitrary_option'] = self.opts.arbitrary_option

#--- Maybe dev mode gets both user and slice creds? Somehow let caller decide?
#-- AM API v2-3 differences here:
        # An optional slice name might be specified.
        # FIXME: This should be done by caller so this method takes slicename that may be null
        slicename = None
        if len(args) > 0:
            slicename = args[0].strip()

        if self.opts.api_version >= 3 and slicename is not None and slicename != "":
            if not self.opts.devmode:
                self._raise_omni_error("In AM API version 3, use 'describe' to list contents of a slice, not 'listresources'. Otherwise specify the -V2 argument to use AM API v2, if the AM supports it.")
            else:
                self.logger.warn("Got a slice name to v3+ ListResources, but continuing...")

        options['geni_compressed'] = self.opts.geni_compressed

        # Get the credential for this query
        if slicename is None or slicename == "":
            options['geni_available'] = self.opts.geni_available
            slicename = None
            cred = None
            if self.opts.api_version >= 3:
                (cred, message) = self.framework.get_user_cred_struct()
            else:
                (cred, message) = self.framework.get_user_cred()
            if cred is None:
                # Per AM API Change Proposal AD, allow no user cred to get an ad
                self.logger.debug("No user credential, but this is now allowed for getting Ads....")
        else:
            (slicename, urn, cred, retVal, slice_exp) = self._args_to_slicecred(args, 1, "listresources")
            if cred is None or cred == "":
                # Dev mode allow doing the call anyhow
                if not self.opts.devmode:
                    return (None, prstr)

            self.logger.info('Gathering resources reserved for slice %s.' % slicename)

            options['geni_slice_urn'] = urn

        # We now have a credential
#----

        # Query each aggregate for resources
        successCnt = 0
        mymessage = ""
        (clientList, message) = self._getclients()
        numClients = len(clientList)
        if numClients == 0:
            if message != "":
                mymessage = "No aggregates available to query: %s" % message
        else:
            # FIXME: What if got a message and still got some aggs?
            if message != "":
                self.logger.debug("Got %d AMs but also got an error message: %s", numClients, message)
            creds = _maybe_add_abac_creds(self.framework, cred)
            creds = self._maybe_add_creds_from_files(creds)

        # Connect to each available GENI AM to list their resources
        for client in clientList:
            if creds is None or len(creds) == 0:
                self.logger.debug("Have null or empty credential list in call to ListResources!")
            rspec = None

            (ver, newc, validMsg) = self._checkValidClient(client)
            if newc is None:
                if validMsg and validMsg != '':
                    if not mymessage:
                        mymessage = ""
                    else:
                        if not mymessage.endswith('.'):
                            mymessage += ".\n"
                        else:
                            mymyessage += "\n"
                    if "Operation timed out" in validMsg:
                        validMsg = validMsg[validMsg.find("Operation timed out"):]
                    elif "Unknown socket error" in validMsg:
                        validMsg = validMsg[validMsg.find("Unknown socket error"):]
                    elif "Server does not trust" in validMsg:
                        validMsg = validMsg[validMsg.find("Server does not trust"):]
                    elif "Your user certificate" in validMsg:
                        validMsg = validMsg[validMsg.find("Your user certificate"):]
                    mymessage += "Skipped AM %s: %s" % (client.str, validMsg)

                # Theoretically could remove this client from clients list, but currently 
                # nothing uses client list after this, so no need.
                # Plus, editing the client list inside the loop is bad
                continue
            elif newc.url != client.url:
                if ver != self.opts.api_version:
                    if numClients == 1:
                        self._raise_omni_error("Can't do ListResources: AM %s speaks only AM API v%d, not %d. Try calling Omni with the -V%d option." % (client.str, ver, self.opts.api_version, ver))
                    self.logger.warn("AM %s doesn't speak API version %d. Try the AM at %s and tell Omni to use API version %d, using the option '-V%d'.", client.str, self.opts.api_version, newc.url, ver, ver)

                    if not mymessage:
                        mymessage = ""
                    else:
                        if not mymessage.endswith('.'):
                            mymessage += ".\n"
                        else:
                            mymyessage += "\n"
                    mymessage += "Skipped AM %s: speaks only API v%d, not %d. Try -V%d option." % (client.str, ver, self.opts.api_version, ver)
                    # Theoretically could remove this client from clients list, but currently 
                    # nothing uses client list after this, so no need.
                    # Plus, editing the client list inside the loop is bad

                    continue
#                    raise BadClientException(client, mymessage)
#                    self.logger.warn("Changing API version to %d. Is this going to work?", ver)
#                    # FIXME: changing the api_version is not a great idea if
#                    # there are multiple clients. Push this into _checkValidClient
#                    # and only do it if there is one client.
#1                    self.opts.api_version = ver
                else:
                    self.logger.debug("Using new AM url %s but same API version %d", newc.url, ver)

                # Theoretically could remove this client from clients list, but currently 
                # nothing uses client list after this, so no need.
                # Plus, editing the client list inside the loop is bad
                # Also note I'm not adding the new corrected client here

                client = newc
            elif ver != self.opts.api_version:
                if numClients == 1:
                    self._raise_omni_error("Can't do ListResources: AM %s speaks only AM API v%d, not %d. Try calling Omni with the -V%d option." % (client.str, ver, self.opts.api_version, ver))
                self.logger.warn("AM %s speaks API version %d, not %d. Rerun with option '-V%d'.", client.str, ver, self.opts.api_version, ver)

                if not mymessage:
                    mymessage = ""
                else:
                    if not mymessage.endswith('.'):
                        mymessage += ".\n"
                    else:
                        mymessage += "\n"
                mymessage += "Skipped AM %s: speaks only API v%d, not %d. Try -V%d option." % (client.str, ver, self.opts.api_version, ver)

                # Theoretically could remove this client from clients list, but currently 
                # nothing uses client list after this, so no need.
                # Plus, editing the client list inside the loop is bad
                continue

            self.logger.debug("Connecting to AM: %s at %s", client.urn, client.url)

#---
# In Dev mode, just use the requested type/version - don't check what is supported
            try:
                (options, mymessage) = self._selectRSpecVersion(slicename, client, mymessage, options)
            except BadClientException, bce:
                if not mymessage:
                    mymessage = ""
                else:
                    if not mymessage.endswith('.'):
                        mymessage += ".\n"
                    else:
                        mymessage += "\n"
                if bce.validMsg and bce.validMsg != '':
                    mymessage += bce.validMsg
                    if not mymessage.endswith('.'):
                        mymessage += ". "
                # mymessage += "AM %s doesn't advertise matching RSpec versions" % client.url
                self.logger.warn(message + "... continuing with next AM")

                # Theoretically could remove this client from clients list, but currently 
                # nothing uses client list after this, so no need.
                # Plus, editing the client list inside the loop is bad
                continue

            options = self._build_options("ListResources", slicename, options)

            # Done constructing options to ListResources
#-----

            self.logger.debug("Doing listresources with %d creds, options %r", len(creds), options)
            (resp, message) = _do_ssl(self.framework, None, ("List Resources at %s" % (client.url)), client.ListResources, creds, options)

            # Decompress the RSpec before sticking it in retItem
            if resp and (self.opts.api_version == 1 or (self.opts.api_version > 1 and isinstance(resp, dict) and resp.has_key('value') and isinstance(resp['value'], str))):
                if self.opts.api_version > 1:
                    origRSpec = resp['value']
                else:
                    origRSpec = resp
                rspec = self._maybeDecompressRSpec(options, origRSpec)
                if rspec and rspec != origRSpec:
                    self.logger.debug("Decompressed RSpec")
                if rspec and rspec_util.is_rspec_string( rspec, None, None, logger=self.logger ):
                    successCnt += 1
                    doPretty = (slicename is not None) # True on Manifests
                    if doPretty and rspec.count('\n') > 10:
                        # Are there newlines in the manifest already? Then set it false. Good enough.
                        doPretty = False
                    elif not doPretty and rspec.count('\n') <= 10:
                        # Are there no newlines in the Ad? Then set it true to make the ad prettier,
                        # but usually don't bother. FOAM ads are messy otherwise.
                        doPretty = True
                    rspec = rspec_util.getPrettyRSpec(rspec, doPretty)
                else:
                    self.logger.warn("Didn't get a valid RSpec!")
                    if mymessage != "":
                        if mymessage.endswith('.'):
                            mymessage += ' '
                        else:
                            mymessage += ". "
                    mymessage += "No resources from AM %s: %s" % (client.str, message)
                if self.opts.api_version > 1:
                    resp['value']=rspec
                else:
                    resp = rspec
            else:
                self.logger.warn("No resource listing returned!")
                self.logger.debug("Return struct missing proper rspec in value element!")
                if mymessage != "":
                    if mymessage.endswith('.'):
                        mymessage += ' '
                    else:
                        mymessage += ". "
                mymessage += "No resources from AM %s: %s" % (client.str, message)

            # Return for tools is the full code/value/output triple
            rspecs[(client.urn, client.url)] = resp
        # End of loop over clients

        if self.numOrigClients > 0:
            if slicename:
                self.logger.info( "Listed reserved resources on %d out of %d possible aggregates." % (successCnt, self.numOrigClients))
            else:
                self.logger.info( "Listed advertised resources at %d out of %d possible aggregates." % (successCnt, self.numOrigClients))
        return (rspecs, mymessage)
    # End of _listresources

    def listresources(self, args):
        """GENI AM API ListResources
        Call ListResources on 1+ aggregates and prints the rspec to stdout or to a file.
        Optional argument for API v1&2 is a slice name, making the request for a manifest RSpec.
        Note that the slice name argument is only supported in AM API v1 or v2.
        For listing contents of a slice in APIv3+, use describe().
        
        Aggregates queried:
        - If `--useSliceAggregates`, each aggregate recorded at the clearinghouse as having resources for the given slice,
          '''and''' any aggregates specified with the `-a` option.
         - Only supported at some clearinghouses, and the list of aggregates is only advisory
        - Each URL given in an -a argument or URL listed under that given
        nickname in omni_config, if provided, ELSE
        - List of URLs given in omni_config aggregates option, if provided, ELSE
        - List of URNs and URLs provided by the selected clearinghouse

        -t <type version>: Default "GENI 3". Specify a required RSpec type and version to return.
        It skips any AM that doesn't advertise (in GetVersion) that it supports that format.

        Returns a dictionary of rspecs with the following format:
         API V1&2:
           rspecs[(urn, url)] = decompressed rspec
         API V3+:
           rspecs[url] = return struct containing a decompressed rspec

        Output directing options:
        -o Save result RSpec (XML format) in per-Aggregate files
        -p (used with -o) Prefix for resulting rspec filenames
        --outputfile If supplied, use this output file name: substitute the AM for any %a,
        and %s for any slicename
        If not saving results to a file, they are logged.
        If --tostdout option, then instead of logging, print to STDOUT.

        File names will indicate the slice name, file format, and 
        which aggregate is represented.
        e.g.: myprefix-myslice-rspec-localhost-8001.xml

        --slicecredfile says to use the given slicecredfile if it exists.

        If a slice name is supplied, then resources for that slice only 
        will be displayed.  In this case, the slice credential is usually
        retrieved from the Slice Authority. But
        with the --slicecredfile option it is read from that file, if it exists.

        --arbitrary-option: supply arbitrary thing for testing
        -V# API Version #
        --devmode: Continue on error if possible
        --no-compress: Request the returned RSpec not be compressed (default is to compress)
        --available: Return Ad of only available resources

        -l to specify a logging config file
        --logoutput <filename> to specify a logging output filename

        Sample usage:
        Call AM API v2 ListResources at 1 Aggregate for 1 slice, getting the manifest RSpec
        omni.py -a http://myaggregate/url -V2 listresources myslice

        Call AM API v3 ListResources at 1 Aggregate, getting the Ad RSpec
        omni.py -a http://myaggregate/url -V3 listresources

        Do AM API v3 ListResources from 1 aggregate saving the results in a specific file,
        with the aggregate name (constructed from the URL) inserted into the filename:
        omni.py -a http://myaggregate/url -V3 -o --outputfile AdRSpecAt%a.xml listresources
        """
#--- API version specific
        # An optional slice name might be specified.
        slicename = None
        if len(args) > 0:
            slicename = args[0].strip()
            if self.opts.api_version >= 3 and slicename is not None and slicename != "":
                if not self.opts.devmode:
                    self._raise_omni_error("In AM API version 3, use 'describe' to list contents of a slice, not 'listresources'. Otherwise specify the -V2 argument to use AM API v2, if the AM supports it.")
                else:
                    self.logger.warn("Got a slice name to v3+ ListResources, but continuing...")
#---

        # check command line args
        if self.opts.output:
            self.logger.info("Saving output to a file.")

        # Query the various aggregates for resources
        # rspecs[(urn, url)] = decompressed rspec
        (rspecs, message) = self._listresources( args )
        numAggs = self.numOrigClients
        
        # handle empty case
        if not rspecs or rspecs == {}:
            if slicename:
                prtStr = "Got no resources on slice %s"%slicename 
            else:
                prtStr = "Got no resources" 
            if message is not None:
                prtStr = prtStr + ". " + message
            else:
                prtStr += " (no reason given)"
            self.logger.info( prtStr )
            return prtStr, {}

        # Loop over RSpecs and print them
        returnedRspecs = {}
        rspecCtr = 0
        savedFileDesc = ""
        for ((urn,url), rspecStruct) in rspecs.items():
            amNick = _lookupAggNick(self, urn)
            if amNick is None:
                amNick = urn
            self.logger.debug("Getting RSpec items for AM urn %s (%s)", urn, url)
            rspecOnly, message = self._retrieve_value( rspecStruct, message, self.framework)
            if self.opts.api_version < 2:
                returnedRspecs[(urn,url)] = rspecOnly
            else:
                returnedRspecs[url] = rspecStruct

            retVal, filename = _writeRSpec(self.opts, self.logger, rspecOnly, slicename, urn, url, None, len(rspecs))
            if filename:
                if not savedFileDesc.endswith(' ') and savedFileDesc != "" and not savedFileDesc.endswith('\n'):
                    savedFileDesc += " "
                savedFileDesc += "Saved listresources RSpec from '%s' (url '%s') to file %s; " % (amNick, url, filename)

            if rspecOnly and rspecOnly != "":
                rspecCtr += 1
                if slicename:
                    # Try to parse the new sliver expiration from the rspec and print it in the result summary.
                    # Use a helper function in handler_utils that can be used elsewhere.
                    manExpires = expires_from_rspec(rspecOnly, self.logger)
                    if manExpires is not None:
                        prstr = "Reservation at %s in slice %s expires at %s (UTC)." % (amNick, slicename, manExpires)
                        self.logger.info(prstr)
                        if not savedFileDesc.endswith('.') and savedFileDesc != "" and not savedFileDesc.endswith('; '):
                            savedFileDesc += '.'
                        if not savedFileDesc.endswith(' ') and savedFileDesc != '':
                            savedFileDesc += " "
                        savedFileDesc += prstr
                    else:
                        self.logger.debug("Got None sliver expiration from manifest")

        # End of loop over rspecs
        self.logger.debug("rspecCtr %d", rspecCtr)

        # Create RETURNS
        # FIXME: If numAggs is 1 then retVal should just be the rspec?
#--- AM API specific:
        if slicename:
            retVal = "Queried resources for slice %s from %d of %d aggregate(s)."%(slicename, rspecCtr, numAggs)
#---
        else:
            retVal = "Queried resources from %d of %d aggregate(s)." % (rspecCtr, numAggs)

        if numAggs > 0:
            retVal +="\n"
            if len(returnedRspecs.keys()) > 0:
                if self.opts.output:
                    retVal += "Wrote rspecs from %d aggregate(s)" % numAggs
                    retVal +=" to %d file(s)"% len(rspecs)
                if savedFileDesc != "":
                    if not retVal.endswith("\n"):
                        retVal += "\n"
                    retVal += savedFileDesc
            else:
                retVal +="No Rspecs succesfully parsed from %d aggregate(s)." % numAggs
            if message:
                retVal += message

        retItem = returnedRspecs

        return retVal, retItem
    # End of listresources

    def describe(self, args):
        """GENI AM API v3 Describe()
        Retrieve a manifest RSpec describing the resources contained by the named entities,
        e.g. a single slice or a set of the slivers in a slice. This listing and description
        should be sufficiently descriptive to allow experimenters to use the resources.
        For listing contents of a slice in APIv1 or 2, or to get the Ad
        of available resources at an AM, use ListResources().

        Argument is a slice name, naming the slice whose contents will be described.
        Lists contents and state on 1+ aggregates and prints the result to stdout or to a file.

        --sliver-urn / -u option: each specifies a sliver URN to describe. If specified,
        only the listed slivers will be described. Otherwise, all slivers in the slice will be described.

        Return is (1) A string describing the result to print, and (2) a dictionary by AM URL of the full
        code/value/output return struct from the AM.

        Aggregates queried:
        - If `--useSliceAggregates`, each aggregate recorded at the clearinghouse as having resources for the given slice,
          '''and''' any aggregates specified with the `-a` option.
         - Only supported at some clearinghouses, and the list of aggregates is only advisory
        - Each URL given in an -a argument or URL listed under that given
        nickname in omni_config, if provided, ELSE
        - List of URLs given in omni_config aggregates option, if provided, ELSE
        - List of URNs and URLs provided by the selected clearinghouse

        Output directing options:
        -o writes output to file instead of stdout; single file per aggregate.
        -p gives filename prefix for each output file
        --outputfile If supplied, use this output file name: substitute the AM for any %a,
        and %s for any slicename
        If not saving results to a file, they are logged.
        If --tostdout option, then instead of logging, print to STDOUT.

        File names will indicate the slice name, file format, and
        which aggregate is represented.
        e.g.: myprefix-myslice-rspec-localhost-8001.json

        -t <type version>: Specify a required manifest RSpec type and version to return.
        It skips any AM that doesn't advertise (in GetVersion)
        that it supports that format. Default is "GENI 3".

        --slicecredfile says to use the given slicecredfile if it exists.

        --arbitrary-option: supply arbitrary thing for testing
        -V# API Version #
        --devmode: Continue on error if possible
        --no-compress: Request the returned RSpec not be compressed (default is to compress)

        -l to specify a logging config file
        --logoutput <filename> to specify a logging output filename

        Sample usage:
        Describe at 1 Aggregate, getting the Manifest RSpec
        in GENI v3 RSpec format
        omni.py -a http://myaggregate/url -V3 describe myslice

        Describe from 2 aggregates, saving the results in a specific file,
        with the aggregate name (constructed from the URL) inserted into the filename:
        omni.py -a http://myaggregate/url -a http://another/aggregate -V3 -o --outputfile AdRSpecAt%a.xml describe myslice

        Describe 2 slivers from a particular aggregate
        omni.py -a http://myaggregate/url -V3 describe myslice -u urn:publicid:IDN:myam+sliver+sliver1 -u urn:publicid:IDN:myam+sliver+sliver2
      """
        if self.opts.api_version < 3:
            if self.opts.devmode:
                self.logger.warn("Trying Describe with AM API v%d...", self.opts.api_version)
            else:
                self._raise_omni_error("Describe is only available in AM API v3+. Use ListResources with AM API v%d, or specify -V3 to use AM API v3." % self.opts.api_version)

        # get the slice name and URN or raise an error
        (name, urn, slice_cred,
         retVal, slice_exp) = self._args_to_slicecred(args, 1, "Describe")

        options = {}
        options['geni_compressed'] = self.opts.geni_compressed

        # Pass in a dummy option for testing that is actually ok
        # FIXME: Omni should have a standard way for supplying additional options. Something like extra args
        # of the form Name=Value
        # Then a standard helper function could be used here to split them apart
        if self.opts.arbitrary_option:
            options['arbitrary_option'] = self.opts.arbitrary_option

        successCnt = 0
        retItem = {}
        args = []
        creds = []
        slivers = []
        urnsarg = []
        # Query status at each client
        (clientList, message) = self._getclients()
        numClients = len(clientList)
        if numClients > 0:
            self.logger.info('Describe Slice %s:' % urn)

            creds = _maybe_add_abac_creds(self.framework, slice_cred)
            creds = self._maybe_add_creds_from_files(creds)

            urnsarg, slivers = self._build_urns(urn)

            # Add the options dict
            options = self._build_options('Describe', name, options)
        else:
            prstr = "No aggregates available to describe slice at: %s" % message
            retVal += prstr + "\n"
            self.logger.warn(prstr)

        descripMsg = "slice %s" % urn
        if len(slivers) > 0:
            descripMsg = "%d slivers in slice %s" % (len(slivers), urn)
        op = 'Describe'
        msg = "Describe %s at " % (descripMsg)
        for client in clientList:
            args = [urnsarg, creds]
            try:
                # Do per client check for rspec version to use and properly fill in geni_rspec_version
                mymessage = ""
                (options, mymessage) = self._selectRSpecVersion(name, client, mymessage, options)
                args.append(options)
                self.logger.debug("Doing describe of %s, %d creds, options %r", descripMsg, len(creds), options)
                ((status, message), client) = self._api_call(client,
                                                   msg + str(client.url),
                                                   op, args)
                if mymessage.strip() != "":
                    if message is None or message.strip() == "":
                        message = ""
                    message = mymessage + ". " + message
            except BadClientException as bce:
                if bce.validMsg and bce.validMsg != '':
                    retVal += bce.validMsg + ". "
                else:
                    retVal += "Describe skipping AM %s. No matching RSpec version or wrong AM API version - check logs" % (client.str)
                if numClients == 1:
                    self._raise_omni_error("\nDescribe failed: " + retVal)
                continue

# FIXME: Factor this next chunk into helper method?
            # Decompress the RSpec before sticking it in retItem
            rspec = None
            if status and isinstance(status, dict) and status.has_key('value') and isinstance(status['value'], dict) and status['value'].has_key('geni_rspec'):
                rspec = self._maybeDecompressRSpec(options, status['value']['geni_rspec'])
                if rspec and rspec != status['value']['geni_rspec']:
                    self.logger.debug("Decompressed RSpec")
                if rspec and rspec_util.is_rspec_string( rspec, None, None, logger=self.logger ):
                    rspec = rspec_util.getPrettyRSpec(rspec)
                else:
                    self.logger.warn("Didn't get a valid RSpec!")
                status['value']['geni_rspec'] = rspec
            else:
                self.logger.warn("Got no resource listing from AM %s", client.str)
                self.logger.debug("Return struct missing geni_rspec element!")

            # Return for tools is the full code/value/output triple
            retItem[client.url] = status

            # Get the dict describe result out of the result (accounting for API version diffs, ABAC)
            (status, message) = self._retrieve_value(status, message, self.framework)
            if not status:
                fmt = "\nFailed to Describe %s at AM %s: %s\n"
                if message is None or message.strip() == "":
                    message = "(no reason given)"
                retVal += fmt % (descripMsg, client.str, message)
                continue # go to next AM

            missingSlivers = self._findMissingSlivers(status, slivers)
            if len(missingSlivers) > 0:
                self.logger.warn("%d slivers from request missing in result?!", len(missingSlivers))
                self.logger.debug("%s", missingSlivers)

            sliverFails = self._didSliversFail(status)
            for sliver in sliverFails.keys():
                self.logger.warn("Sliver %s reported error: %s", sliver, sliverFails[sliver])

            (header, rspeccontent, rVal) = _getRSpecOutput(self.logger, rspec, name, client.urn, client.url, message, slivers)
            self.logger.debug(rVal)
            if status and isinstance(status, dict) and status.has_key('geni_rspec') and rspec and rspeccontent:
                status['geni_rspec'] = rspeccontent

            if not isinstance(status, dict):
                # malformed describe return
                self.logger.warn('Malformed describe result from AM %s. Expected struct, got type %s.' % (client.str, status.__class__.__name__))
                # FIXME: Add something to retVal that the result was malformed?
                if isinstance(status, str):
                    prettyResult = str(status)
                else:
                    prettyResult = pprint.pformat(status)
            else:
                prettyResult = json.dumps(status, ensure_ascii=True, indent=2)

            #header="<!-- Describe %s at AM URL %s -->" % (descripMsg, client.url)
            filename = None

            if self.opts.output:
                filename = _construct_output_filename(self.opts, name, client.url, client.urn, "describe", ".json", numClients)
                #self.logger.info("Writing result of describe for slice: %s at AM: %s to file %s", name, client.url, filename)
            _printResults(self.opts, self.logger, header, prettyResult, filename)
            if filename:
                retVal += "Saved description of %s at AM %s to file %s. \n" % (descripMsg, client.str, filename)
            # Only count it as success if no slivers were missing
            if len(missingSlivers) == 0 and len(sliverFails.keys()) == 0:
                successCnt+=1
            else:
                retVal += " - with %d slivers missing and %d slivers with errors. \n" % (len(missingSlivers), len(sliverFails.keys()))

        # FIXME: Return the status if there was only 1 client?
        if numClients > 0:
            retVal += "Found description of slivers on %d of %d possible aggregates." % (successCnt, self.numOrigClients)
        self.logger.debug("Describe return: \n" + json.dumps(retItem, indent=2))
        return retVal, retItem
    # End of describe

    def createsliver(self, args):
        """AM API CreateSliver call
        CreateSliver <slicename> <rspec file>
        Return on success the manifest RSpec
        For use in AM API v1+2 only. For AM API v3+, use allocate(), provision, and performoperationalaction().

        Slice name could be a full URN, but is usually just the slice name portion.
        Note that PLC Web UI lists slices as <site name>_<slice name>
        (e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

        -a Contact only the aggregate at the given URL, or with the given
         nickname that translates to a URL in your omni_config

          - Note that `--useSliceAggregates` is not honored, as the desired
            aggregate usually has no resources in this slice yet.

        Output directing options:
        -o writes output to file instead of stdout; single file per aggregate.
        -p gives filename prefix for each output file
        --outputfile If supplied, use this output file name: substitute the AM for any %a,
        and %s for any slicename
        If not saving results to a file, they are logged.
        If --tostdout option, then instead of logging, print to STDOUT.

        File names will indicate the slice name, file format, and
        which aggregate is represented.
        e.g.: myprefix-myslice-manifest-localhost-8001.xml

        --devmode: Continue on error if possible

        -l to specify a logging config file
        --logoutput <filename> to specify a logging output filename

        --slicecredfile Read slice credential from given file, if it exists
        Slice credential is usually retrieved from the Slice Authority. But
        with the --slicecredfile option it is read from that file, if it exists.

        omni_config users section is used to get a set of SSH keys that
        should be loaded onto the remote node to allow SSH login, if the
        remote resource and aggregate support this.

        Note you likely want to check SliverStatus to ensure your resource
        comes up.
        And check the sliver expiration time: you may want to call RenewSliver.
        """

        if self.opts.api_version >= 3:
            if self.opts.devmode:
                self.logger.warn("Trying CreateSliver with AM API v%d...", self.opts.api_version)
            else:
                self._raise_omni_error("CreateSliver is only available in AM API v1 or v2. Use Allocate, then Provision, then PerformOperationalAction in AM API v3+, or use the -V2 option to use AM API v2 if the AM supports it.")

        # check command line args
        if not self.opts.aggregate or len(self.opts.aggregate) == 0:
            # the user must supply an aggregate.

            # FIXME: Note this check is now duplicated in _correctAPIVersion

            msg = 'Missing -a argument: specify an aggregate where you want the reservation.'
            # FIXME: parse the AM to reserve at from a comment in the RSpec
            # Calling exit here is a bit of a hammer.
            # Maybe there's a gentler way.
            self._raise_omni_error(msg)
        elif self.clients and len(self.clients) > 1:
            self.logger.warn("Multiple clients supplied - only the first will be used. ('%s')" % self.clients[0].str)
        elif not self.clients and len(self.opts.aggregate) > 1:
            self.logger.warn("Multiple -a arguments received - only the first will be used. ('%s')" % self.opts.aggregate[0])
            self.opts.aggregate = [self.opts.aggregate[0]]

        # prints slice expiration. Warns or raises an Omni error on problems
        (slicename, urn, slice_cred, retVal, slice_exp) = self._args_to_slicecred(args, 2, "CreateSliver", "and a request rspec filename")

        # Load up the user's request rspec
        rspecfile = None
        if not (self.opts.devmode and len(args) < 2):
            rspecfile = args[1]
        if rspecfile is None: # FIXME: If file type arg, check the file exists: os.path.isfile(rspecfile) 
#--- Dev mode should allow missing RSpec
            msg = 'File of resources to request missing: %s' % rspecfile
            if self.opts.devmode:
                self.logger.warn(msg)
            else:
                self._raise_omni_error(msg)

        try:
            # read the rspec into a string, and add it to the rspecs dict
            rspec = _derefRSpecNick(self, rspecfile)
        except Exception, exc:
#--- Should dev mode allow this?
            msg = "Unable to read rspec file '%s': %s" % (rspecfile, str(exc))
            if self.opts.devmode:
                rspec = ""
                self.logger.warn(msg)
            else:
                self._raise_omni_error(msg)

        # Test if the rspec is really json containing an RSpec, and pull out the right thing
        rspec = self._maybeGetRSpecFromStruct(rspec)

        # FIXME: We could try to parse the RSpec right here, and get the AM URL or nickname
        # out of the RSpec

        (clientList, message) = self._getclients()
        if (clientList is None or len(clientList) == 0):
            retVal += "CreateSliver failed: No aggregates at which to make reservation"
            if message != '':
                retVal += ": %" % message
            self._raise_omni_error(retVal)
        client = clientList[0]
        url = client.url
        clienturn = client.urn

        result = None
        self.logger.info("Creating sliver(s) from rspec file %s for slice %s", rspecfile, urn)

        creds = _maybe_add_abac_creds(self.framework, slice_cred)
        creds = self._maybe_add_creds_from_files(creds)

        # Copy the user config and read the keys from the files into the structure
        slice_users = self._get_users_arg(slicename)
        if not slice_users or len(slice_users) == 0:
            self.logger.warn("No users or SSH keys supplied; you will not be able to SSH in to any compute resources")

        op = "CreateSliver"
        options = self._build_options(op, slicename, None)
        args = [urn, creds, rspec, slice_users]
#--- API version diff:
        if self.opts.api_version >= 2:
            # Add the options dict
            args.append(options)
#---

        msg = "Create Sliver %s at %s" % (urn, client.str)
        self.logger.debug("Doing createsliver with urn %s, %d creds, rspec of length %d starting '%s...', users struct %s..., options %r", urn, len(creds), len(rspec), rspec[:min(100, len(rspec))], str(slice_users)[:min(180, len(str(slice_users)))], options)
        try:
            ((result, message), client) = self._api_call(client, msg, op,
                                                args)
            url = client.url
            client.urn = clienturn
        except BadClientException as bce:
            self._raise_omni_error("Cannot CreateSliver at %s: The AM speaks the wrong API version, not %d. %s" % (client.str, self.opts.api_version, bce.validMsg))

        # Get the manifest RSpec out of the result (accounting for API version diffs, ABAC)
        (result, message) = self._retrieve_value(result, message, self.framework)
        if result:
            self.logger.info("Got return from CreateSliver for slice %s at %s:", slicename, client.str)

            if rspec_util.is_rspec_string( result, None, None, logger=self.logger ):
                result = rspec_util.getPrettyRSpec(result)
            (retVal, filename) = _writeRSpec(self.opts, self.logger, result, slicename, clienturn, url, message)
            if filename:
                self.logger.info("Wrote result of createsliver for slice: %s at AM: %s to file %s", slicename, client.str, filename)
                retVal += '\n   Saved createsliver results to %s. ' % (filename)

            manExpires = None
            if result and "<rspec" in result and "expires" in result:
                # Try to parse the new sliver expiration from the rspec and print it in the result summary.
                # Use a helper function in handler_utils that can be used elsewhere.
                manExpires = expires_from_rspec(result, self.logger)
                if manExpires is not None:
                    prstr = "Reservation at %s in slice %s expires at %s (UTC)." % (client.str, slicename, manExpires)
                    self.logger.info(prstr)
                    if not (retVal.endswith('.') or retVal.endswith('. ')):
                        retVal += '.'
                    retVal += " " + prstr
                else:
                    self.logger.debug("Got None sliver expiration from manifest")

            # record new slivers in the SA database if able to do so
            try:
                if not self.opts.noExtraCHCalls:
                    agg_urn = self._getURNForClient(client)
                    exp = slice_exp
                    if manExpires:
                        exp = manExpires
                    self.framework.create_sliver_info(result, urn, 
                                                      url, exp, None, agg_urn)
                else:
                    self.logger.debug("Per commandline option, not reporting new sliver to clearinghouse")
            except NotImplementedError, nie:
                self.logger.debug('Framework %s doesnt support recording slivers in SA database', self.config['selected_framework']['type'])
            except Exception, e:
                # FIXME: Info only?
                self.logger.warn('Error recording new slivers in SA database')
                self.logger.debug(e)
#                import traceback
#                self.logger.debug(traceback.format_exc())
#                raise e

            # FIXME: When Tony revises the rspec, fix this test
            if result and '<RSpec' in result and 'type="SFA"' in result:
                # Figure out the login name
                # We could of course do this for the user.
                prstr = "Please run the omni sliverstatus call on your slice %s to determine your login name to PL resources." % slicename
                self.logger.info(prstr)
                if not retVal.endswith('.'):
                    retVal += '.'
                retVal += " " + prstr

        else:
            prStr = "Failed CreateSliver for slice %s at %s." % (slicename, client.str)
            if message is None or message.strip() == "":
                message = "(no reason given)"
            if message:
                prStr += "  %s" % message
            self.logger.warn(prStr)
            retVal = prStr

        return retVal, result
    # End of createsliver

    def allocate(self, args):
        """
        GENI AM API Allocate <slice name> <rspec file name>
        For use with AM API v3+ only. Otherwise, use CreateSliver.
        Allocate resources as described in a request RSpec argument to a slice with 
        the named URN. On success, one or more slivers are allocated, containing 
        resources satisfying the request, and assigned to the given slice.

        Clients must Renew or Provision slivers before the expiration time
        (given in the return struct), or the aggregate will automatically Delete them.

        Slice name could be a full URN, but is usually just the slice name portion.
        Note that PLC Web UI lists slices as <site name>_<slice name>
        (e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

        Slice credential is usually retrieved from the Slice Authority. But
        with the --slicecredfile option it is read from that file, if it exists.

        Aggregates queried:
        - Each URL given in an -a argument or URL listed under that given
        nickname in omni_config, if provided, ELSE
        - List of URLs given in omni_config aggregates option, if provided, ELSE
        - List of URNs and URLs provided by the selected clearinghouse
        - Note that `--useSliceAggregates` is not honored, as the desired
          aggregate usually has no resources in this slice yet.
        Note that if multiple aggregates are supplied, the same RSpec will be submitted to each.
        Aggregates should ignore parts of the Rspec requesting specific non-local resources (bound requests), but each 
        aggregate should attempt to satisfy all unbound requests. Note also that allocate() calls
        are always all-or-nothing: if the aggregate cannot give everything requested, it gives nothing.

        --end-time: Request that new slivers expire at the given time.
        The aggregates may allocate the resources, but not be able to grant the requested
        expiration time.
        Note that per the AM API expiration times will be timezone aware.
        Unqualified times are assumed to be in UTC.
        Note that the expiration time cannot be past your slice expiration
        time (see renewslice).

        Output directing options:
        -o Save result in per-Aggregate files
        -p (used with -o) Prefix for resulting files
        --outputfile If supplied, use this output file name: substitute the AM for any %a,
        and %s for any slicename
        If not saving results to a file, they are logged.
        If --tostdout option, then instead of logging, print to STDOUT.

        File names will indicate the slice name, file format, and
        which aggregate is represented.
        e.g.: myprefix-myslice-allocate-localhost-8001.json

        -V# API Version #
        --devmode: Continue on error if possible
        -l to specify a logging config file
        --logoutput <filename> to specify a logging output filename

        Sample usage:
        Basic allocation of resources at 1 AM into myslice
        omni.py -V3 -a http://myaggregate/url allocate myslice my-request-rspec.xml

        Allocate resources into 2 AMs, requesting a specific sliver end time, save results into specificly named files that include an AM name calculated from the AM URL,
        using the slice credential saved in the given file
        omni.py -V3 -a http://myaggregate/url -a http://myother/aggregate --end-time 20120909 -o --outputfile myslice-manifest-%a.json --slicecredfile mysaved-myslice-slicecred.xml allocate myslice my-request-rspec.xml
        """
        if self.opts.api_version < 3:
            if self.opts.devmode:
                self.logger.warn("Trying Allocation with AM API v%d...", self.opts.api_version)
            else:
                self._raise_omni_error("Allocate is only available in AM API v3+. Use CreateSliver with AM API v%d, or specify -V3 to use AM API v3." % self.opts.api_version)

        (slicename, urn, slice_cred, retVal, slice_exp) = self._args_to_slicecred(args, 2,
                                                      "Allocate",
                                                      "and a request rspec filename")
        # Load up the user's request rspec
        rspecfile = None
        if not (self.opts.devmode and len(args) < 2):
            rspecfile = args[1]
        if rspecfile is None: # FIXME: If file type arg, check the file exists: os.path.isfile(rspecfile) 
            # Dev mode should allow missing RSpec
            msg = 'File of resources to request missing: %s' % rspecfile
            if self.opts.devmode:
                self.logger.warn(msg)
            else:
                self._raise_omni_error(msg)

        try:
            # read the rspec into a string, and add it to the rspecs dict
            rspec = _derefRSpecNick(self, rspecfile)
        except Exception, exc:
            msg = "Unable to read rspec file '%s': %s" % (rspecfile, str(exc))
            if self.opts.devmode:
                rspec = ""
                self.logger.warn(msg)
            else:
                self._raise_omni_error(msg)

        # Test if the rspec is really json containing an RSpec, and
        # pull out the right thing
        rspec = self._maybeGetRSpecFromStruct(rspec)

        # Build args
        options = self._build_options('Allocate', slicename, None)
        creds = _maybe_add_abac_creds(self.framework, slice_cred)
        creds = self._maybe_add_creds_from_files(creds)
        args = [urn, creds, rspec, options]
        descripMsg = "slivers in slice %s" % urn
        op = 'Allocate'
        self.logger.debug("Doing Allocate with urn %s, %d creds, rspec starting: \'%s...\', and options %s", urn, len(creds), rspec[:min(40, len(rspec))], options)

        successCnt = 0
        retItem = dict()
        (clientList, message) = self._getclients()
        numClients = len(clientList)
        if numClients == 0:
            msg = "No aggregate specified to submit allocate request to. Use the -a argument."
            if self.opts.devmode:
                #  warn
                self.logger.warn(msg)
            else:
                self._raise_omni_error(msg)
        elif numClients > 1:
            #  info - mention unbound bits will be repeated
            self.logger.info("Multiple aggregates will get the same request RSpec; unbound requests will be attempted at multiple aggregates.")

        # Do the command for each client
        for client in clientList:
            self.logger.info("Allocate %s at %s:", descripMsg, client.str)
            try:
                ((result, message), client) = self._api_call(client,
                                    ("Allocate %s at %s" % (descripMsg, client.url)),
                                    op,
                                    args)
            except BadClientException, bce:
                if bce.validMsg and bce.validMsg != '':
                    retVal += bce.validMsg + ". "
                else:
                    retVal += "Skipped aggregate %s. (Unreachable? Doesn't speak AM API v%d? Check the log messages, and try calling 'getversion' to check AM status and API versions supported.).\n" % (client.str, self.opts.api_version)
                if numClients == 1:
                    self._raise_omni_error("\nAllocate failed: " + retVal)
                continue

            # Make the RSpec more pretty-printed
            rspec = None
            if result and isinstance(result, dict) and result.has_key('value') and isinstance(result['value'], dict) and result['value'].has_key('geni_rspec'):
                rspec = result['value']['geni_rspec']
                if rspec and rspec_util.is_rspec_string( rspec, None, None, logger=self.logger ):
                    rspec = rspec_util.getPrettyRSpec(rspec)
                    result['value']['geni_rspec'] = rspec
                else:
                    self.logger.debug("No valid RSpec returned!")
            else:
                self.logger.debug("Return struct missing geni_rspec element!")

            # Pull out the result and check it
            retItem[ client.url ] = result
            (realresult, message) = self._retrieve_value(result, message, self.framework)
            badSlivers = self._getSliverAllocStates(realresult, 'geni_allocated')
            for sliver in badSlivers.keys():
                self.logger.warn("Sliver %s in wrong state! Expected %s, got %s?!", sliver, 'geni_allocated', badSlivers[sliver])
                # FIXME: Is the alloc reported here as a failure if some slivers in wrong state?

            if realresult:
                # Success (maybe partial?)
                (header, rspeccontent, rVal) = _getRSpecOutput(self.logger, rspec, slicename, client.urn, client.url, message)
                self.logger.debug(rVal)
                if realresult and isinstance(realresult, dict) and realresult.has_key('geni_rspec') and rspec and rspeccontent:
                    realresult['geni_rspec'] = rspeccontent
                if isinstance(realresult, dict):
                    # Hmm. The rspec content looks OK here. But the
                    # json.dumps seems to screw it up? Quotes get
                    # double escaped.
                    prettyResult = json.dumps(realresult, ensure_ascii=True, indent=2)
                else:
                    prettyResult = pprint.pformat(realresult)

                # Save out the result
#                header="<!-- Allocate %s at AM URL %s -->" % (descripMsg, client.url)
                filename = None

                if self.opts.output:
                    filename = _construct_output_filename(self.opts, slicename, client.url, client.urn, "allocate", ".json", numClients)
                    #self.logger.info("Writing result of allocate for slice: %s at AM: %s to file %s", slicename, client.url, filename)
                _printResults(self.opts, self.logger, header, prettyResult, filename)
                if filename:
                    retVal += "Saved allocation of %s at AM %s to file %s. \n" % (descripMsg, client.str, filename)
                else:
                    retVal += "Allocated %s at %s. \n" % (descripMsg, client.str)

                # Check the new sliver expirations
                (orderedDates, sliverExps) = self._getSliverExpirations(realresult)
                # None case
                if len(orderedDates) == 1:
                    self.logger.info("All slivers expire on %r", orderedDates[0].isoformat())
                elif len(orderedDates) == 2:
                    self.logger.info("%d slivers expire on %r, the rest (%d) on %r", len(sliverExps[orderedDates[0]]), orderedDates[0].isoformat(), len(sliverExps[orderedDates[0]]), orderedDates[1].isoformat())
                elif len(orderedDates) == 0:
                    msg = " 0 Slivers reported allocated!"
                    self.logger.warn(msg)
                    retVal += msg
                else:
                    self.logger.info("%d slivers expire on %r, %d on %r, and others later", len(sliverExps[orderedDates[0]]), orderedDates[0].isoformat(), len(sliverExps[orderedDates[0]]), orderedDates[1].isoformat())
                if len(orderedDates) > 0:
                    if len(orderedDates) == 1:
                        retVal += " All slivers expire on: %s" % orderedDates[0].isoformat()
                    else:
                        retVal += " First sliver expiration: %s" % orderedDates[0].isoformat()

                self.logger.debug("Allocate %s result: %s" %  (descripMsg, prettyResult))
                successCnt += 1
            else:
                # Failure
                if message is None or message.strip() == "":
                    message = "(no reason given)"
                retVal += "Allocation of %s at %s failed: %s.\n" % (descripMsg, client.str, message)
                self.logger.warn(retVal)
                # FIXME: Better message?
        # Done with allocate call loop over clients

        if numClients == 0:
            retVal += "No aggregates at which to allocate %s. %s\n" % (descripMsg, message)
        elif numClients > 1:
            retVal += "Allocated %s at %d out of %d aggregates.\n" % (descripMsg, successCnt, self.numOrigClients)
        elif successCnt == 0:
            retVal += "Allocate %s failed at %s" % (descripMsg, clientList[0].url)
        self.logger.debug("Allocate Return: \n%s", json.dumps(retItem, indent=2))
        return retVal, retItem
    # end of allocate

    def provision(self, args):
        """
        GENI AM API Provision <slice name>
        For use with AM API v3+ only. Otherwise, use CreateSliver.
        Request that the named geni_allocated slivers be made geni_provisioned, 
        instantiating or otherwise realizing the resources, such that they have a 
        valid geni_operational_status and may possibly be made geni_ready for 
        experimenter use. This operation is synchronous, but may start a longer process, 
        such as creating and imaging a virtual machine.

        Clients must Renew or use slivers before the expiration time
        (given in the return struct), or the aggregate will automatically Delete them.

        Slice name could be a full URN, but is usually just the slice name portion.
        Note that PLC Web UI lists slices as <site name>_<slice name>
        (e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

        Slice credential is usually retrieved from the Slice Authority. But
        with the --slicecredfile option it is read from that file, if it exists.

        Aggregates queried:
        - Each URL given in an -a argument or URL listed under that given
        nickname in omni_config, if provided, ELSE
        - List of URLs given in omni_config aggregates option, if provided, ELSE
        - List of URNs and URLs provided by the selected clearinghouse
        - Note that `--useSliceAggregates` is not honored, as the desired
          aggregate usually has no resources in this slice yet.

        -t <type version>: Specify a required manifest RSpec type and version to return.
        It skips any AM that doesn't advertise (in GetVersion)
        that it supports that format. Default is "GENI 3".

        --end-time: Request that new slivers expire at the given time.
        The aggregates may provision the resources, but not be able to grant the requested
        expiration time.
        Note that per the AM API expiration times will be timezone aware.
        Unqualified times are assumed to be in UTC.
        Note that the expiration time cannot be past your slice expiration
        time (see renewslice).

        --sliver-urn / -u option: each specifies a sliver URN to provision. If specified, 
        only the listed slivers will be provisioned. Otherwise, all slivers in the slice will be provisioned.
        --best-effort: If supplied, slivers that can be provisioned, will be; some slivers 
        may not be provisioned, in which case check the geni_error return for that sliver.
        If not supplied, then if any slivers cannot be provisioned, the whole call fails
        and sliver allocation states do not change.

        Note that some aggregates may require provisioning all slivers in the same state at the same 
        time, per the geni_single_allocation GetVersion return.

        Output directing options:
        -o Save result in per-Aggregate files
        -p (used with -o) Prefix for resulting files
        --outputfile If supplied, use this output file name: substitute the AM for any %a,
        and %s for any slicename
        If not saving results to a file, they are logged.
        If --tostdout option, then instead of logging, print to STDOUT.

        File names will indicate the slice name, file format, and
        which aggregate is represented.
        e.g.: myprefix-myslice-provision-localhost-8001.json

        -V# API Version #
        --devmode: Continue on error if possible
        -l to specify a logging config file
        --logoutput <filename> to specify a logging output filename

        omni_config users section is used to get a set of SSH keys that
        should be loaded onto the remote node to allow SSH login, if the
        remote resource and aggregate support this.

        Sample usage:
        Basic provision of allocated resources at 1 AM into myslice
        omni.py -V3 -a http://myaggregate/url provision myslice

        Provision resources in 2 AMs, requesting a specific sliver end time, save results into specificly named files that include an AM name calculated from the AM URL,
        and slice name, using the slice credential saved in the given file. Provision in best effort mode: provision as much as possible
        omni.py -V3 -a http://myaggregate/url -a http://myother/aggregate --end-time 20120909 -o --outputfile %s-provision-%a.json --slicecredfile mysaved-myslice-slicecred.xml --best-effort provision myslice

        Provision allocated resources in specific slivers
        omni.py -V3 -a http://myaggregate/url -u urn:publicid:IDN+myam+sliver+1 -u urn:publicid:IDN+myam+sliver+2 provision myslice
        """

        if self.opts.api_version < 3:
            if self.opts.devmode:
                self.logger.warn("Trying Provision with AM API v%d...", self.opts.api_version)
            else:
                self._raise_omni_error("Provision is only available in AM API v3+. Use CreateSliver with AM API v%d, or specify -V3 to use AM API v3." % self.opts.api_version)

        # Build up args, options
        op = "Provision"
        (slicename, urn, slice_cred, retVal, slice_exp) = self._args_to_slicecred(args, 1,
                                                      op)

        # Copy the user config and read the keys from the files into the structure
        slice_users = self._get_users_arg(slicename)

        # If there are slice_users, include that option
        options = {}
        if slice_users and len(slice_users) > 0:
            options['geni_users'] = slice_users
        else:
            self.logger.warn("No users or SSH keys supplied; you will not be able to SSH in to any compute resources")

        options = self._build_options(op, slicename, options)
        urnsarg, slivers = self._build_urns(urn)

        descripMsg = "slivers in slice %s" % urn
        if len(slivers) > 0:
            descripMsg = "%d slivers in slice %s" % (len(slivers), urn)

        creds = _maybe_add_abac_creds(self.framework, slice_cred)
        creds = self._maybe_add_creds_from_files(creds)

        # Get Clients
        successCnt = 0
        retItem = dict()
        (clientList, message) = self._getclients()
        numClients = len(clientList)
        if numClients == 0:
            msg = "No aggregate specified to submit provision request to. Use the -a argument."
            if message and message.strip() != "":
                msg += " " + message
            if self.opts.devmode:
                #  warn
                self.logger.warn(msg)
            else:
                self._raise_omni_error(msg)
        elif numClients > 1 and len(slivers) > 0:
            # All slivers will go to all AMs. If not best effort, AM may fail the request if its
            # not a local sliver.
            #  # FIXME: Could partition slivers by AM URN?
            msg = "Will do %s %s at all %d AMs - some aggregates may fail the request if given slivers not from that aggregate." % (op, descripMsg, numClients)
            if self.opts.geni_best_effort:
                self.logger.info(msg)
            else:
                self.logger.warn(msg + " Consider running with --best-effort in future.")

        # Loop over clients doing operation
        for client in clientList:
            args = [urnsarg, creds]
            self.logger.info("%s %s at %s", op, descripMsg, client.str)
            try:
                mymessage = ""
                (options, mymessage) = self._selectRSpecVersion(slicename, client, mymessage, options)
                args.append(options)
                self.logger.debug("Doing Provision at %s with urns %s, %d creds, options %s", client.str, urnsarg, len(creds), options)
                ((result, message), client) = self._api_call(client,
                                                  ("Provision %s at %s" % (descripMsg, client.url)),
                                                  op,
                                                  args)
                if mymessage.strip() != "":
                    if message is None or message.strip() == "":
                        message = ""
                    message = mymessage + ". " + message
            except BadClientException, bce:
                if bce.validMsg and bce.validMsg != '':
                    retVal += bce.validMsg + ". "
                else:
                    retVal += "Skipped aggregate %s. (Unreachable? Doesn't speak AM API v%d? Check the log messages, and try calling 'getversion' to check AM status and API versions supported.).\n" % (client.str, self.opts.api_version)
                if numClients == 1:
                    self._raise_omni_error("\nProvision failed: " + retVal)
                continue

            # Make the RSpec more pretty-printed
            if result and isinstance(result, dict) and result.has_key('value') and isinstance(result['value'], dict) and result['value'].has_key('geni_rspec'):
                rspec = result['value']['geni_rspec']
                if rspec and rspec_util.is_rspec_string( rspec, None, None, logger=self.logger ):
                    rspec = rspec_util.getPrettyRSpec(rspec)
                    result['value']['geni_rspec'] = rspec
                else:
                    self.logger.debug("No valid RSpec returned!")
            else:
                self.logger.debug("Return struct missing geni_rspec element!")

            # Pull out the result
            retItem[ client.url ] = result
            (realresult, message) = self._retrieve_value(result, message, self.framework)

            badSlivers = self._getSliverAllocStates(realresult, 'geni_provisioned')
            for sliver in badSlivers.keys():
                self.logger.warn("Sliver %s in wrong state! Expected %s, got %s?!", sliver, 'geni_provisioned', badSlivers[sliver])
                # FIXME: Is the alloc reported here as a failure if some slivers in wrong state?

            if realresult:
                # Success
                missingSlivers = self._findMissingSlivers(realresult, slivers)
                if len(missingSlivers) > 0:
                    self.logger.warn("%d slivers from request missing in result?!", len(missingSlivers))
                    self.logger.debug("Slivers requested missing in result: %s", missingSlivers)

                sliverFails = self._didSliversFail(realresult)
                for sliver in sliverFails.keys():
                    self.logger.warn("Sliver %s reported error: %s", sliver, sliverFails[sliver])

                # record new slivers in SA database if possible
                try:
                    if not self.opts.noExtraCHCalls:
                        agg_urn = self._getURNForClient(client)
                        # Get the slivers actually returned
                        ret_slivers = self._getSliverResultList(realresult)
                        self.framework.create_sliver_info(None, urn, 
                                                          client.url,
                                                          slice_exp,
                                                          ret_slivers, agg_urn)
                    else:
                        self.logger.debug("Per commandline option, not reporting new sliver(s) to clearinghouse")
                except NotImplementedError, nie:
                    self.logger.debug('Framework %s doesnt support recording slivers in SA database', self.config['selected_framework']['type'])
                except Exception, e:
                    # FIXME: Info only?
                    self.logger.warn('Error recording new slivers in SA database')
                    self.logger.debug(e)

                # Print out the result
                if isinstance(realresult, dict):
                    prettyResult = json.dumps(realresult, ensure_ascii=True, indent=2)
                else:
                    prettyResult = pprint.pformat(realresult)

                header="<!-- Provision %s at AM %s -->" % (descripMsg, client.str)
                filename = None

                if self.opts.output:
                    filename = _construct_output_filename(self.opts, slicename, client.url, client.urn, "provision", ".json", numClients)
                    #self.logger.info("Writing result of provision for slice: %s at AM: %s to file %s", name, client.url, filename)
                _printResults(self.opts, self.logger, header, prettyResult, filename)
                if filename:
                    retVal += "Saved provision of %s at AM %s to file %s. \n" % (descripMsg, client.str, filename)
                else:
                    retVal += "Provisioned %s at %s. \n" % (descripMsg, client.str)
                if len(missingSlivers) > 0:
                    retVal += " - but with %d slivers from request missing in result?! \n" % len(missingSlivers)
                if len(sliverFails.keys()) > 0:
                    retVal += " = but with %d slivers reporting errors. \n" % len(sliverFails.keys())

                # Check sliver expiration
                (orderedDates, sliverExps) = self._getSliverExpirations(realresult)
                # None case
                if len(orderedDates) == 1:
                    self.logger.info("All slivers expire on %r", orderedDates[0].isoformat())
                elif len(orderedDates) == 2:
                    self.logger.info("%d slivers expire on %r, the rest (%d) on %r", len(sliverExps[orderedDates[0]]), orderedDates[0].isoformat(), len(sliverExps[orderedDates[0]]), orderedDates[1].isoformat())
                elif len(orderedDates) == 0:
                    msg = " 0 Slivers reported results!"
                    self.logger.warn(msg)
                    retVal += msg
                else:
                    self.logger.info("%d slivers expire on %r, %d on %r, and others later", len(sliverExps[orderedDates[0]]), orderedDates[0].isoformat(), len(sliverExps[orderedDates[0]]), orderedDates[1].isoformat())
                if len(orderedDates) > 0:
                    if len(orderedDates) == 1:
                        retVal += " All slivers expire on: %s" % orderedDates[0].isoformat()
                    else:
                        retVal += " First sliver expiration: %s" % orderedDates[0].isoformat()

                self.logger.debug("Provision %s result: %s" %  (descripMsg, prettyResult))
                if len(missingSlivers) == 0 and len(sliverFails.keys()) == 0:
                    successCnt += 1
            else:
                # Failure
                if message is None or message.strip() == "":
                    message = "(no reason given)"
                retVal = "Provision of %s at %s failed: %s" % (descripMsg, client.str, message)
                self.logger.warn(retVal)
                retVal += "\n"
        # Done loop over clients

        if numClients == 0:
            retVal += "No aggregates at which to provision %s. %s\n" % (descripMsg, message)
        elif numClients > 1:
            retVal += "Provisioned %s at %d out of %d aggregates.\n" % (descripMsg, successCnt, self.numOrigClients)
        elif successCnt == 0:
            retVal += "Provision %s failed at %s" % (descripMsg, clientList[0].url)
        self.logger.debug("Provision Return: \n%s", json.dumps(retItem, indent=2))
        return retVal, retItem
    # end of provision

    def performoperationalaction(self, args):
        """ Alias of "poa" which is an implementation of v3 PerformOperationalAction.
        """
        return self.poa( args )

    def poa(self, args):
        """
        GENI AM API PerformOperationalAction <slice name> <action name>
        For use with AM API v3+ only. Otherwise, use CreateSliver.

        Perform the named operational action on the named slivers or slice, possibly changing
        the geni_operational_status of the named slivers. E.G. 'start' a VM. For valid 
        operations and expected states, consult the state diagram advertised in the 
        aggregate's advertisement RSpec.

        Common `poa` Actions:
        Some actions are well known and supported at many aggregates and
        resource types. Always check the Ad RSpec for an aggregate to verify
        what is supported.
        - `geni_start`: Make the resources ready for use (like booting
        machines). No options needed
        - `geni_restart`: For example, reboot a machine. No options required.
        - `geni_stop`: Stop a resource (e.g. shut it down). No options
        needed.
        - `geni_update_users`: Refresh the set of user accounts and installed
        SSH keys on the resource. Takes the option `geni_users`. This action
        creates any users specified that do not already exist, and sets the
        SSH keys for all users per the list of keys specified - including
        removing keys not explicitly listed. The `geni_users` option can be
        supplied using the `--optionsfile` argument. If not supplied that
        way, then users are read from the omni_config or clearinghouse slice
        members, as documented under `createsliver`.

        Clients must Renew or use slivers before the expiration time
        (given in the return struct), or the aggregate will automatically Delete them.

        --sliver-urn / -u option: each specifies a sliver URN on which to perform the given action. If specified, 
        only the listed slivers will be acted on. Otherwise, all slivers in the slice will be acted on.
        Note though that actions are state and resource type specific, so the action may not apply everywhere.

        Slice name could be a full URN, but is usually just the slice name portion.
        Note that PLC Web UI lists slices as <site name>_<slice name>
        (e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

        Aggregates queried:
        - If `--useSliceAggregates`, each aggregate recorded at the clearinghouse as having resources for the given slice,
          '''and''' any aggregates specified with the `-a` option.
         - Only supported at some clearinghouses, and the list of aggregates is only advisory
        - Each URL given in an -a argument or URL listed under that given
        nickname in omni_config, if provided, ELSE
        - List of URLs given in omni_config aggregates option, if provided, ELSE
        - List of URNs and URLs provided by the selected clearinghouse

        --slicecredfile Read slice credential from given file, if it exists
        Slice credential is usually retrieved from the Slice Authority. But
        with the --slicecredfile option it is read from that file, if it exists.

        --best-effort: If supplied, slivers that can be acted on, will be; some slivers 
        may not be acted on successfully, in which case check the geni_error return for that sliver.
        If not supplied, then if any slivers cannot be changed, the whole call fails
        and sliver states do not change.

        Output directing options:
        -o Save result in per-Aggregate files
        -p (used with -o) Prefix for resulting files
        --outputfile If supplied, use this output file name: substitute the AM for any %a,
        and %s for any slicename
        If not saving results to a file, they are logged.
        If --tostdout option, then instead of logging, print to STDOUT.

        File names will indicate the slice name, file format, and
        which aggregate is represented.
        e.g.: myprefix-myslice-poa-geni_start-localhost-8001.json

        -V# API Version #
        --devmode: Continue on error if possible
        -l to specify a logging config file
        --logoutput <filename> to specify a logging output filename

        Sample usage:
        Do geni_start on slivers in myslice
        omni.py -V3 -a http://myaggregate poa myslice geni_start

        Do geni_start on 2 slivers in myslice, but continue if 1 fails, and save results to the named file
        omni.py -V3 -a http://myaggregate poa --best-effort -o --outputfile %s-start-%a.json -u urn:publicid:IDN+myam+sliver+1 -u urn:publicid:IDN+myam+sliver+2 myslice geni_start
        """
        if self.opts.api_version < 3:
            if self.opts.api_version == 2:
                self.logger.info("Running PerformOperationalAction even though you are using AM API v2 - will fail at most AMs.")
            elif self.opts.devmode:
                self.logger.warn("Trying PerformOperationalAction with AM API v%d...", self.opts.api_version)
            else:
                self._raise_omni_error("PerformOperationalAction is only available in AM API v3+. Use CreateSliver with AM API v%d, or specify -V3 to use AM API v3." % self.opts.api_version)

        # Build up args, options
        op = "PerformOperationalAction"
        (slicename, urn, slice_cred, retVal, slice_exp) = self._args_to_slicecred(args, 2,
                                                      op,
                                                      "and an action to perform")
        action = args[1]
        if action is None or action.strip() == "":
            if self.opts.devmode:
                action = ""
                self.logger.warn("poa: No action specified....")
            else:
                self._raise_omni_error("PerformOperationalAction requires an arg of the name of the action to perform")

        # check common action typos
        # FIXME: Auto correct?
        if not self.opts.devmode:
            if action.lower() == "start":
                self.logger.warn("Action: '%s'. Did you mean 'geni_start'?" % action)
            elif action.lower() == "stop":
                self.logger.warn("Action: '%s'. Did you mean 'geni_stop'?" % action)
            elif action.lower() == "restart":
                self.logger.warn("Action: '%s'. Did you mean 'geni_restart'?" % action)

        options = self._build_options(op, slicename, None)

        # If the action is geni_update_users and we got no geni_users option yet, then call _get_users_arg.
        # If we did get a geni_users, then we use that.
        # _get_users_arg will check slice members and the omni config (per options)
        if action.lower() == 'geni_update_users':
            if options and options.has_key('geni_users'):
                self.logger.debug("Got geni_users option from optionsfile")
            else:
                if not options:
                    options = {}
                users = self._get_users_arg(slicename)
                if users and len(users) > 0:
                    options['geni_users'] = users
                else:
                    self.logger.info("No users or keys supplied for geni_update_users")

        urnsarg, slivers = self._build_urns(urn)

        descripMsg = "%s on slivers in slice %s" % (action, urn)
        if len(slivers) > 0:
            descripMsg = "%s on %d slivers in slice %s" % (action, len(slivers), urn)

        creds = _maybe_add_abac_creds(self.framework, slice_cred)
        creds = self._maybe_add_creds_from_files(creds)
        args = [urnsarg, creds, action, options]
        self.logger.debug("Doing POA with urns %s, action %s, %d creds, and options %s", urnsarg, action, len(creds), options)

        # Get clients
        successCnt = 0
        retItem = dict()
        (clientList, message) = self._getclients()
        numClients = len(clientList)
        if numClients == 0:
            msg = "No aggregate specified to submit %s request to. Use the -a argument." % op
            if self.opts.devmode:
                #  warn
                self.logger.warn(msg)
            else:
                self._raise_omni_error(msg)
        elif numClients > 1 and len(slivers) > 0:
            # All slivers will go to all AMs. If not best effort, AM may fail the request if its
            # not a local sliver.
            #  # FIXME: Could partition slivers by AM URN?
            msg = "Will do %s %s at all %d AMs - some aggregates may fail the request if given slivers not from that aggregate." % (op, descripMsg, numClients)
            if self.opts.geni_best_effort:
                self.logger.info(msg)
            else:
                self.logger.warn(msg + " Consider running with --best-effort in future.")

        # Do poa action on each client
        for client in clientList:
            self.logger.info("%s %s at %s", op, descripMsg, client.str)
            try:
                ((result, message), client) = self._api_call(client,
                                                  ("PerformOperationalAction %s at %s" % (descripMsg, client.url)),
                                                  op,
                                                  args)
            except BadClientException, bce:
                if bce.validMsg and bce.validMsg != '':
                    retVal += bce.validMsg + ". "
                else:
                    retVal += "Skipped aggregate %s. (Unreachable? Doesn't speak AM API v%d? Check the log messages, and try calling 'getversion' to check AM status and API versions supported.).\n" % (client.str, self.opts.api_version)
                if numClients == 1:
                    self._raise_omni_error("\nPerformOperationalAction failed: " + retVal)
                continue

            retItem[ client.url ] = result
            (realresult, message) = self._retrieve_value(result, message, self.framework)

            if realresult is None:
                # Failure
                if message is None or message.strip() == "":
                    message = "(no reason given)"
                msg = "PerformOperationalAction %s at %s failed: %s \n" % (descripMsg, client.str, message)
                retVal += msg
                self.logger.warn(msg)
            else:
                # Success
                missingSlivers = self._findMissingSlivers(realresult, slivers)
                if len(missingSlivers) > 0:
                    self.logger.warn("%d slivers from request missing in result?!", len(missingSlivers))
                    self.logger.debug("%s", missingSlivers)

                sliverFails = self._didSliversFail(realresult)
                for sliver in sliverFails.keys():
                    self.logger.warn("Sliver %s reported error: %s", sliver, sliverFails[sliver])

                # Save result
                ftype = ".json"
                if isinstance(realresult, dict):
                    prettyResult = json.dumps(realresult, ensure_ascii=True, indent=2)
                    # Some POAs return a top level geni_credential
                    # Save it off separately for convenience
                    if realresult.has_key('geni_credential'):
                        cred = realresult['geni_credential'].replace("\\n", "\n")
                        fname = _maybe_save_slicecred(self, slicename + '-sharedlan', cred)
                        if fname is not None:
                            prstr = "Saved shared LAN credential to file '%s'" % fname
                            retVal += prstr + "\n"
                            self.logger.info(prstr)
                else:
                    ftype = ".txt"
                    prettyResult = pprint.pformat(realresult)
                    # Some POAs return a credential per sliver
                    # Save those as separate files for readability
                    if isinstance(realresult, list):
                        for sliver in realresult:
                            sliverurn = ''
                            cred = None
                            if isinstance(sliver, dict):
                                if sliver.has_key('geni_sliver_urn'):
                                    sliverurn = sliver['geni_sliver_urn']
                                if sliver.has_key('geni_credential'):
                                    cred = sliver['geni_credential'].replace("\\n", "\n")
                            if cred is not None:
                                fname = _maybe_save_slicecred(self, slicename + '-' + sliverurn + '-sharedlan', cred)
                                if fname is not None:
                                    prstr = "Saved shared LAN %s credential to file '%s'" % (sliverurn, fname)
                                    retVal += prstr + "\n"
                                    self.logger.info(prstr)

                header="PerformOperationalAction result for %s at AM %s:" % (descripMsg, client.str)
                filename = None
                if self.opts.output:
                    filename = _construct_output_filename(self.opts, slicename, client.url, client.urn, "poa-" + action, ftype, numClients)
                    #self.logger.info("Writing result of poa %s at AM: %s to file %s", descripMsg, client.url, filename)

                _printResults(self.opts, self.logger, header, prettyResult, filename)

                retVal += "PerformOperationalAction %s was successful." % descripMsg
                if len(missingSlivers) > 0:
                    retVal += " - with %d missing slivers?!" % len(missingSlivers)
                if len(sliverFails.keys()) > 0:
                    retVal += " - with %d slivers reporting errors!" % len(sliverFails.keys())
                if filename:
                    retVal += " Saved results at AM %s to file %s. \n" % (client.str, filename)
                elif len(prettyResult) < 120:
                    retVal += ' ' + prettyResult + '\n'
                else:
                    retVal += ' \n'
                if len(missingSlivers) == 0 and len(sliverFails.keys()) == 0:
                    successCnt += 1
        # Done loop over clients

        self.logger.debug("POA %s result: %s", descripMsg, json.dumps(retItem, indent=2))

        if numClients == 0:
            retVal += "No aggregates at which to PerformOperationalAction %s. %s\n" % (descripMsg, message)
        elif numClients > 1:
            retVal += "Performed Operational Action %s at %d out of %d aggregates.\n" % (descripMsg, successCnt, self.numOrigClients)
        elif successCnt == 0:
            retVal += "PerformOperationalAction %s failed at %s" % (descripMsg, clientList[0].url)

        return retVal, retItem
    # end of poa

    def renewsliver(self, args):
        """AM API RenewSliver <slicename> <new expiration time in UTC
        or with a timezone>
        For use in AM API v1&2. Use renew() in AM API v3+.
        Slice name could be a full URN, but is usually just the slice name portion.
        Note that PLC Web UI lists slices as <site name>_<slice name>
        (e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

        Slice credential is usually retrieved from the Slice Authority. But
        with the --slicecredfile option it is read from that file, if it exists.

        Aggregates queried:
        - If `--useSliceAggregates`, each aggregate recorded at the clearinghouse as having resources for the given slice,
          '''and''' any aggregates specified with the `-a` option.
         - Only supported at some clearinghouses, and the list of aggregates is only advisory
        - Each URL given in an -a argument or URL listed under that given
        nickname in omni_config, if provided, ELSE
        - List of URLs given in omni_config aggregates option, if provided, ELSE
        - List of URNs and URLs provided by the selected clearinghouse

        Note that per the AM API expiration times will be timezone aware.
        Unqualified times are assumed to be in UTC.
        Note that the expiration time cannot be past your slice expiration
        time (see renewslice). Some aggregates will
        not allow you to _shorten_ your sliver expiration time.
        Times are in UTC or supply an explicit timezone, and 
        should be quoted if they contain spaces or forward slashes.

        -V# API Version #
        --devmode: Continue on error if possible
        -l to specify a logging config file
        --logoutput <filename> to specify a logging output filename
        --alap: Renew slivers as long as possible (up to the slice
        expiration / time requested). Default is False - either renew
        to the requested time, or fail.
        """

        if self.opts.api_version >= 3:
            if self.opts.devmode:
                self.logger.warn("Trying RenewSliver with AM API v%d...", self.opts.api_version)
            else:
                self._raise_omni_error("RenewSliver is only available in AM API v1 or v2. Use Renew, or specify the -V2 option to use AM API v2, if the AM supports it.")

        # Gather arguments, options

        # prints slice expiration. Warns or raises an Omni error on problems
        (name, urn, slice_cred, retVal, slice_exp) = self._args_to_slicecred(args, 2, "RenewSliver", "and new expiration time in UTC")

        if len(args) >= 2:
            ds = args[1]
        else:
            ds = None
        # noSec=True so that fractional seconds are dropped
        (time, time_with_tz, time_string) = self._datetimeFromString(ds, slice_exp, name, noSec=True)

        self.logger.info('Renewing Sliver %s until %s (UTC)' % (name, time_with_tz))

        creds = _maybe_add_abac_creds(self.framework, slice_cred)
        creds = self._maybe_add_creds_from_files(creds)

        op = "RenewSliver"
        options = self._build_options(op, name, None)
        args = [urn, creds, time_string]
#--- AM API version specific
        if self.opts.api_version >= 2:
            # Add the options dict
            args.append(options)

        self.logger.debug("Doing renewsliver with urn %s, %d creds, time %s, options %r", urn, len(creds), time_string, options)

        # Run renew at each client
        successCnt = 0
        successList = []
        failList = []
        (clientList, message) = self._getclients()
        numClients = len(clientList)
        msg = "Renew Sliver %s on " % (urn)
        for client in clientList:
            try:
                ((res, message), client) = self._api_call(client,
                                                   msg + str(client.url),
                                                   op, args)
            except BadClientException, bce:
                if bce.validMsg and bce.validMsg != '':
                    retVal += bce.validMsg + ". "
                else:
                    retVal += "Skipped aggregate %s. (Unreachable? Doesn't speak AM API v%d? Check the log messages, and try calling 'getversion' to check AM status and API versions supported.).\n" % (client.str, self.opts.api_version)
                if numClients == 1:
                    self._raise_omni_error("\nRenewSliver failed: " + retVal)
                continue

            outputstr = None
            if self.opts.alap:
                # Get the output from the res - it will have the new
                # sliver expiration
                if isinstance(res, dict) and res.has_key('output') and res['output'] is not None and str(res['output']).strip() != "":
                    outputstr = str(res['output']).strip()

            # Get the boolean result out of the result (accounting for API version diffs, ABAC)
            (res, message) = self._retrieve_value(res, message, self.framework)

            if not res:
                prStr = "Failed to renew sliver %s at %s (got result '%s')" % (urn, (client.str if client.nick else client.urn), res)
                if message != "":
                    if not prStr.endswith('.'):
                        prStr += '.'
                    prStr += " " + message
                else:
                    prStr += " (no reason given)"
                if numClients == 1:
                    retVal += prStr + "\n"
                self.logger.warn(prStr)
                failList.append( client.url )
            else:
                newExp = time_with_tz.isoformat()
                gotALAP = False
                if self.opts.alap:
                    if not outputstr or outputstr.strip() == "":
                        self.logger.info("Querying AM for actual sliver expiration...")
                        # Call sliverstatus
                        # If result haskey 'pg_expires' then make that
                        # outputstr
                        # elif haskey geni_resources and that haskey
                        # orca_expires then make that outputstr
                        # use same creds but diff args & options
                        try:
                            args2 = [urn, creds]
                            options2 = self._build_options('SliverStatus', name, None)
                            # API version specific
                            if self.opts.api_version >= 2:
                                # Add the options dict
                                args2.append(options2)
                            message2 = ""
                            status = None

                            ((status, message2), client2) = self._api_call(client,
                                                                         'SliverStatus of %s at %s' % (urn, str(client.url)),
                                                                         'SliverStatus', args2)
                            # Get the dict status out of the result (accounting for API version diffs, ABAC)
                            (status, message1) = self._retrieve_value(status, message2, self.framework)
                            exps = expires_from_status(status, self.logger)
                            if len(exps) > 1:
                                # More than 1 distinct sliver expiration found
                                # FIXME: Sort and take first?
                                exps = exps.sort()
                                self.logger.debug("Found %d different expiration times. Using first", len(exps))
                                outputstr = exps[0].isoformat()
                            elif len(exps) == 0:
                                self.logger.debug("Failed to parse a sliver expiration from status")
                            else:
                                outputstr = exps[0].isoformat()
                        except Exception, e:
                            self.logger.debug("Failed SliverStatus to get real expiration: %s", e)
                    if outputstr:
                        try:
                            newExpO = dateutil.parser.parse(str(outputstr), tzinfos=tzd)
                            newExpO = naiveUTC(newExpO)
                            newExpO_tz = newExpO.replace(tzinfo=dateutil.tz.tzutc())
                            newExp = newExpO_tz.isoformat()
                            if abs(time - newExpO) > datetime.timedelta.resolution:
                                gotALAP = True
                                self.logger.debug("Got new sliver expiration from output field. Orig %s != new %s", time, newExpO)
                        except:
                            self.logger.debug("Failed to parse a time from the RenewSliver output - assume got requested time. Output: '%s'", outputstr)
                    else:
                        self.logger.debug("Could not determine actual sliver expiration after renew alap")

                prStr = "Renewed sliver %s at %s until %s (UTC)" % (urn, (client.str if client.nick else client.urn), newExp)
                if gotALAP:
                    prStr = prStr + " (not requested %s UTC), which was as long as possible for this AM" % time_with_tz.isoformat()
                elif self.opts.alap and not outputstr:
                    prStr = prStr + " (or as long as possible at this AM)"
                self.logger.info(prStr)

                if not self.opts.noExtraCHCalls:
                    try:
                        agg_urn = self._getURNForClient(client)
                        if urn_util.is_valid_urn(agg_urn):
                            sliver_urns = self.framework.list_sliverinfo_urns(urn, agg_urn)
                            # We only get here if the framework implements list_sliverinfo_urns
                            if not sliver_urns:
                                sliver_urns = []

                            # Use sliverstatus to augment the list of slivers in this slice at this AM
                            # This way we catch slivers that were never recorded.
                            # Only do this if we have 0 slivers, to limit times we incur the expense of
                            # an extra AM API call.
                            if len(sliver_urns) == 0:
                                st = None
                                streal = None
                                try:
                                    args2 = [urn, creds]
                                    ops = self._build_options('SliverStatus', name, None)
                                    args2.append(ops)
                                    ((st, m), c) = self._api_call(client,
                                                                  "Sliverstatus of %s at %s" % (urn, agg_urn),
                                                                  'SliverStatus', args2)
                                    (streal, m2) = self._retrieve_value(st, m, self.framework)
                                    #self.logger.debug("Got st %s", streal)
                                except Exception, e:
                                    self.logger.debug("Failed Sliverstatus to list slivers after renew of %s at %s: %s", urn, agg_urn, e)
                                if streal and isinstance(streal, dict) and streal.has_key('geni_resources'):
                                    for s in streal['geni_resources']:
                                        #self.logger.debug("Got s %s", s)
                                        if s.has_key('geni_urn') and urn_util.is_valid_urn_bytype(s['geni_urn'], 'sliver'):
                                            slice_auth = slice_urn[0 : slice_urn.find('slice+')]
                                            surn = s['geni_urn']
                                            if not surn in sliver_urns:
                                                sliver_urns.append(surn)
                                        elif s.has_key('geni_urn'):
                                            surn = s['geni_urn']
                                            if surn is None:
                                                surn = ""
                                            surn = surn.strip()
                                            if surn.startswith(urn) and agg_urn is not None and agg_urn != "" and ("foam" in agg_urn or "al2s" in agg_urn):
                                                # Work around a FOAM/AL2S bug producing bad sliver URNs
                                                # See http://groups.geni.net/geni/ticket/1294
                                                if not surn in sliver_urns:
                                                    sliver_urns.append(surn)
                                                    self.logger.debug("Malformed sliver URN '%s'. Assuming this is OK anyhow at this FOAM based am: %s. See http://groups.geni.net/geni/ticket/1294", surn, agg_urn)
                                    # End of loop over status return elems

                            for sliver_urn in sliver_urns:
                                self.framework.update_sliver_info(agg_urn, urn, sliver_urn,
                                                                  newExp)
                        else:
                            self.logger.info("Not updating recorded sliver expirations - no valid AM URN known")
                    except NotImplementedError, nie:
                        self.logger.debug('Framework %s doesnt support recording slivers in SA database', self.config['selected_framework']['type'])
                    except Exception, e:
                        # FIXME: Only info?
                        self.logger.warn('Error updating sliver record in SA database')
                        self.logger.debug(e)
                        import traceback
                        self.logger.debug(traceback.format_exc())
                else:
                    self.logger.debug("Per commandline option, not updating sliver info record at clearinghouse")

                if numClients == 1:
                    retVal += prStr + "\n"
                successCnt += 1
                successList.append( client.url )
        if numClients == 0:
            retVal += "No aggregates on which to renew slivers for slice %s. %s\n" % (urn, message)
        elif numClients > 1:
            if self.opts.alap:
                # FIXME: Say more about where / how long it was renewed?
                retVal += "Renewed slivers on %d out of %d aggregates for slice %s until %s (UTC) or as long as possible\n" % (successCnt, self.numOrigClients, urn, time_with_tz)
            else:
                retVal += "Renewed slivers on %d out of %d aggregates for slice %s until %s (UTC)\n" % (successCnt, self.numOrigClients, urn, time_with_tz)
        return retVal, (successList, failList)
    # End of renewsliver

    def renew(self, args):
        """AM API Renew <slicename> <new expiration time in UTC
        or with a timezone>
        For use with AM API v3+. Use RenewSliver() in AM API v1&2.

        This command will renew your resources at each aggregate up to the
        specified time.  This time must be less than or equal to the time
        available to the slice (see `print_slice_expiration` and
        `renewslice`).  Times are in UTC or supply an explicit timezone, and
        should be quoted if they contain spaces or forward slashes.

        Slice name could be a full URN, but is usually just the slice name portion.
        Note that PLC Web UI lists slices as <site name>_<slice name>
        (e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

        Slice credential is usually retrieved from the Slice Authority. But
        with the --slicecredfile option it is read from that file, if it exists.

        Aggregates queried:
        - If `--useSliceAggregates`, each aggregate recorded at the clearinghouse as having resources for the given slice,
          '''and''' any aggregates specified with the `-a` option.
         - Only supported at some clearinghouses, and the list of aggregates is only advisory
        - Each URL given in an -a argument or URL listed under that given
        nickname in omni_config, if provided, ELSE
        - List of URLs given in omni_config aggregates option, if provided, ELSE
        - List of URNs and URLs provided by the selected clearinghouse

        Note that per the AM API expiration times will be timezone aware.
        Unqualified times are assumed to be in UTC.
        Note that the expiration time cannot be past your slice expiration
        time (see renewslice). Some aggregates will
        not allow you to _shorten_ your sliver expiration time.

        --sliver-urn / -u option: each specifies a sliver URN to renew. If specified, 
        only the listed slivers will be renewed. Otherwise, all slivers in the slice will be renewed.
        --best-effort: If supplied, slivers that can be renewed, will be; some slivers 
        may not be renewed, in which case check the geni_error return for that sliver.
        If not supplied, then if any slivers cannot be renewed, the whole call fails
        and sliver expiration times do not change.

        When renewing multiple slivers, note that slivers in the geni_allocated state are treated
        differently than slivers in the geni_provisioned state, and typically are restricted
        to shorter expiration times. Users are recommended to supply the geni_best_effort option, 
        and to consider operating on only slivers in the same state.

        Note that some aggregates may require renewing all slivers in the same state at the same 
        time, per the geni_single_allocation GetVersion return.

        Output directing options:
        -o Save result in per-Aggregate files
        -p (used with -o) Prefix for resulting files
        --outputfile If supplied, use this output file name: substitute the AM for any %a,
        and %s for any slicename
        If not saving results to a file, they are logged.
        If --tostdout option, then instead of logging, print to STDOUT.

        File names will indicate the slice name, file format, and
        which aggregate is represented.
        e.g.: myprefix-myslice-renew-localhost-8001.json

        -V# API Version #
        --devmode: Continue on error if possible
        -l to specify a logging config file
        --logoutput <filename> to specify a logging output filename
        --alap: Renew slivers as long as possible (up to the slice
        expiration / time requested). Default is False - either renew
        to the requested time, or fail.

        Sample usage:
        Renew slivers in slice myslice to the given time; fail the call if all slivers cannot be renewed to this time
        omni.py -V3 -a http://myaggregate/url renew myslice 20120909

        Renew slivers in slice myslice to the given time; any slivers that cannot be renewed to this time, stay as they were, while others are renewed
        omni.py -V3 -a http://myaggregate/url --best-effort renew myslice "2012/09/09 12:00"

        Renew the given sliver in myslice at this AM to the given time and write the result struct to the given file
        omni.py -V3 -a http://myaggregate/url -o --outputfile %s-renew-%a.json -u urn:publicid:IDN+myam+sliver+1 renew myslice 20120909
        """

        if self.opts.api_version < 3:
            if self.opts.devmode:
                self.logger.warn("Trying Renew with AM API v%d...", self.opts.api_version)
            else:
                self._raise_omni_error("Renew is only available in AM API v3+. Use RenewSliver with AM API v%d, or specify -V3 to use AM API v3." % self.opts.api_version)

        # Gather options,args

        # prints slice expiration. Warns or raises an Omni error on problems
        (name, urn, slice_cred,
         retVal, slice_exp) = self._args_to_slicecred(args, 2,
                                                      "Renew",
                                                      "and new expiration time in UTC")

        time = datetime.datetime.max
        if len(args) >= 2:
            ds = args[1]
        else:
            ds = None
        # noSec=True so that fractional seconds are dropped
        (time, time_with_tz, time_string) = self._datetimeFromString(ds, slice_exp, name, noSec=True)

        self.logger.info('Renewing Slivers in slice %s until %s (UTC)' % (name, time_with_tz))

        creds = _maybe_add_abac_creds(self.framework, slice_cred)
        creds = self._maybe_add_creds_from_files(creds)

        urnsarg, slivers = self._build_urns(urn)

        descripMsg = "slivers in slice %s" % urn
        if len(slivers) > 0:
            descripMsg = "%d slivers in slice %s" % (len(slivers), urn)

        op = 'Renew'
        args = [urnsarg, creds, time_string]
        # Add the options dict
        options = self._build_options(op, name, None)
        args.append(options)

        self.logger.debug("Doing renew with urns %s, %d creds, time %s, options %r", urnsarg, len(creds), time_string, options)

        # Call renew at each client
        successCnt = 0
        (clientList, message) = self._getclients()
        numClients = len(clientList)
        retItem = dict()
        msg = "Renew %s at " % (descripMsg)
        for client in clientList:
            try:
                ((res, message), client) = self._api_call(client, msg + client.url, op,
                                                args)
            except BadClientException, bce:
                if bce.validMsg and bce.validMsg != '':
                    retVal += bce.validMsg + ". "
                else:
                    retVal += "Skipped aggregate %s. (Unreachable? Doesn't speak AM API v%d? Check the log messages, and try calling 'getversion' to check AM status and API versions supported.).\n" % (client.str, self.opts.api_version)
                if numClients == 1:
                    self._raise_omni_error("\nRenew failed: " + retVal)
                continue
            retItem[client.url] = res

            # Get the boolean result out of the result (accounting for API version diffs, ABAC)
            (res, message) = self._retrieve_value(res, message, self.framework)

            if res is None:
                prStr = "Failed to renew %s at %s" % (descripMsg, (client.str if client.nick else client.urn))
                if message != "":
                    prStr += ": " + message
                else:
                    prStr += " (no reason given)"
                if numClients == 1:
                    retVal += prStr + "\n"
                self.logger.warn(prStr)
            else:
                prStr = "Renewed %s at %s until %s (UTC)" % (descripMsg, (client.str if client.nick else client.urn), time_with_tz.isoformat())
                self.logger.info(prStr)

                # Look inside return. Did all slivers we asked about report results?
                # For each that did, did any fail?
                missingSlivers = self._findMissingSlivers(res, slivers)
                if len(missingSlivers) > 0:
                    msg = " - but %d slivers from request missing in result?!" % len(missingSlivers)
                    self.logger.warn(msg)
                    self.logger.debug("%s", missingSlivers)
                    prStr += msg

                sliverFails = self._didSliversFail(res)
                for sliver in sliverFails.keys():
                    self.logger.warn("Sliver %s reported error: %s", sliver, sliverFails[sliver])
                if len(sliverFails.keys()) > 0:
                    prStr += " - with %d slivers reporting errors!" % len(sliverFails.key())

                (orderedDates, sliverExps) = self._getSliverExpirations(res, time)
                if len(orderedDates) == 1 and orderedDates[0] == time:
                    self.logger.info("All slivers expire as requested on %r", time_with_tz.isoformat())
                elif len(orderedDates) == 1:
                    self.logger.warn("Slivers expire on %r, not as requested %r", orderedDates[0].isoformat(), time_with_tz.isoformat())
#                    self.logger.warn("timedelta: %r", time - orderedDates[0])
                elif len(orderedDates) == 0:
                    msg = " 0 Slivers reported results!"
                    self.logger.warn(msg)
                    retVal += msg
                else:
                    firstTime = None
                    firstCount = 0
                    if sliverExps.has_key(time):
                        expectedCount = sliverExps[time]
                    else:
                        expectedCount = 0
                    for time in orderedDates:
                        if time == requestedExpiration or time - requestedExpiration < datetime.timedelta.resolution:
                            continue
                        firstTime = time
                        firstCount = len(sliverExps[time])
                        break
                    self.logger.warn("Slivers do not all expire as requested: %d as requested (%r), but %d expire on %r, and others at %d other times", expectedCount, time_with_tz.isoformat(), firstCount, firstTime.isoformat(), len(orderedDates) - 2)

                if not self.opts.noExtraCHCalls:
                    # record results in SA database
                    try:
                        agg_urn = self._getURNForClient(client)
                        slivers = self._getSliverResultList(res)
                        for sliver in slivers:
                            if isinstance(sliver, dict) and \
                                    sliver.has_key('geni_sliver_urn') and \
                                    sliver.has_key('geni_expires'):
                                # Exclude slivers with
                                # geni_allocation_status of geni_allocated - they
                                # are not yet in the DB
                                if sliver.has_key('geni_allocation_status') and \
                                        sliver['geni_allocation_status'] == 'geni_allocated':
                                    self.logger.debug("Not recording updated sliver that is only allocated: %s", sliver)
                                    continue

                                # FIXME: Exclude slivers in sliverFails (had errors)?
                                if sliver['geni_sliver_urn'] in sliverFails.keys():
                                    self.logger.debug("Not recording sliver that had renew error: %s", sliver)
                                    continue

                                self.framework.update_sliver_info \
                                    (agg_urn, urn, sliver['geni_sliver_urn'], sliver['geni_expires'])
                    except NotImplementedError, nie:
                        self.logger.debug('Framework %s doesnt support recording slivers in SA database', self.config['selected_framework']['type'])
                    except Exception, e:
                        # FIXME: Info only?
                        self.logger.warn('Error updating sliver record in SA database')
                        self.logger.debug(e)
                else:
                    self.logger.debug("Per commandline option, not updating sliver record at clearinghouse")

                # Save results
                if isinstance(res, dict):
                    prettyResult = json.dumps(res, ensure_ascii=True, indent=2)
                else:
                    prettyResult = pprint.pformat(res)
                header="Renewed %s at AM %s" % (descripMsg, client.str)
                filename = None
                if self.opts.output:
                    filename = _construct_output_filename(self.opts, name, client.url, client.urn, "renewal", ".json", numClients)
                #self.logger.info("Writing result of renew for slice: %s at AM: %s to file %s", name, client.url, filename)
                _printResults(self.opts, self.logger, header, prettyResult, filename)
                if filename:
                    retVal += "Saved renewal on %s at AM %s to file %s. \n" % (descripMsg, client.str, filename)
                if numClients == 1:
                    retVal += prStr + "\n"
                if len(sliverFails.keys()) == 0 and len(missingSlivers) == 0:
                    successCnt += 1
        # End of loop over clients

        if numClients == 0:
            retVal += "No aggregates on which to renew slivers for slice %s. %s\n" % (urn, message)
        elif numClients > 1:
            retVal += "Renewed slivers on %d out of %d aggregates for slice %s until %s (UTC)\n" % (successCnt, self.numOrigClients, urn, time_with_tz)
        self.logger.debug("Renew Return: \n%s", json.dumps(retItem, indent=2))
        return retVal, retItem
    # End of renew

    def sliverstatus(self, args):
        """AM API SliverStatus  <slice name>
        For use in AM API v1&2; use status() in API v3+.
        Slice name could be a full URN, but is usually just the slice name portion.
        Note that PLC Web UI lists slices as <site name>_<slice name>
        (e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

        Slice credential is usually retrieved from the Slice Authority. But
        with the --slicecredfile option it is read from that file, if it exists.

        Aggregates queried:
        - If `--useSliceAggregates`, each aggregate recorded at the clearinghouse as having resources for the given slice,
          '''and''' any aggregates specified with the `-a` option.
         - Only supported at some clearinghouses, and the list of aggregates is only advisory
        - Each URL given in an -a argument or URL listed under that given
        nickname in omni_config, if provided, ELSE
        - List of URLs given in omni_config aggregates option, if provided, ELSE
        - List of URNs and URLs provided by the selected clearinghouse

        Output directing options:
        -o Save result in per-Aggregate files
        -p (used with -o) Prefix for resulting files
        --outputfile If supplied, use this output file name: substitute the AM for any %a,
        and %s for any slicename
        If not saving results to a file, they are logged.
        If --tostdout option, then instead of logging, print to STDOUT.

        File names will indicate the slice name, file format, and
        which aggregate is represented.
        e.g.: myprefix-myslice-status-localhost-8001.json

        -V# API Version #
        --devmode: Continue on error if possible
        -l to specify a logging config file
        --logoutput <filename> to specify a logging output filename
        """

        if self.opts.api_version >= 3:
            if self.opts.devmode:
                self.logger.warn("Trying SliverStatus with AM API v%d...", self.opts.api_version)
            else:
                self._raise_omni_error("SliverStatus is only available in AM API v1 or v2. Use Status, or specify the -V2 option to use AM API v2, if the AM supports it.")

        # Build up args, options

        # prints slice expiration. Warns or raises an Omni error on problems
        (name, urn, slice_cred, retVal, slice_exp) = self._args_to_slicecred(args, 1, "SliverStatus")

        successCnt = 0
        retItem = {}
        args = []
        creds = []
        op = 'SliverStatus'
        # Query status at each client
        (clientList, message) = self._getclients()
        numClients = len(clientList)
        if numClients > 0:
            self.logger.info('Status of Slice %s:' % urn)

            creds = _maybe_add_abac_creds(self.framework, slice_cred)
            creds = self._maybe_add_creds_from_files(creds)

            args = [urn, creds]
            options = self._build_options(op, name, None)
            # API version specific
            if self.opts.api_version >= 2:
                # Add the options dict
                args.append(options)
            self.logger.debug("Doing sliverstatus with urn %s, %d creds, options %r", urn, len(creds), options)
        else:
            prstr = "No aggregates available to get slice status at: %s" % message
            retVal += prstr + "\n"
            self.logger.warn(prstr)

        msg = "%s of %s at " % (op, urn)

        # Call SliverStatus on each client
        for client in clientList:
            try:
                ((rawstatus, message), client) = self._api_call(client,
                                                   msg + str(client.url),
                                                   op, args)
            except BadClientException, bce:
                if bce.validMsg and bce.validMsg != '':
                    retVal += bce.validMsg + ". "
                else:
                    retVal += "Skipped aggregate %s. (Unreachable? Doesn't speak AM API v%d? Check the log messages, and try calling 'getversion' to check AM status and API versions supported.).\n" % (client.str, self.opts.api_version)
                if numClients == 1:
                    self._raise_omni_error("\nSliverStatus failed: " + retVal)
                continue

            rawResult = rawstatus
            amapiError = None
            status = None
            try:
                # Get the dict status out of the result (accounting for API version diffs, ABAC)
                (status, message) = self._retrieve_value(rawstatus, message, self.framework)
            except AMAPIError, amapiError:
                # Would raise an AMAPIError.
                # But that loses the side-effect of deleting any sliverinfo records.
                # So if we're doing those, hold odd on raising the error
                if self.opts.noExtraCHCalls:
                    raise amapiError
                else:
                    self.logger.debug("Got AMAPIError retrieving value from sliverstatus. Hold it until we do any sliver info processing")

            if status:
                if not isinstance(status, dict):
                    # malformed sliverstatus return
                    self.logger.warn('Malformed sliver status from AM %s. Expected struct, got type %s.' % (client.str, status.__class__.__name__))
                    # FIXME: Add something to retVal that the result was malformed?
                    if isinstance(status, str):
                        prettyResult = str(status)
                    else:
                        prettyResult = pprint.pformat(status)
                else:
                    try:
                        prettyResult = json.dumps(status, ensure_ascii=True, indent=2)
                    except Exception, jde:
                        self.logger.debug("Failed to parse status as JSON: %s", jde)
                        prettyResult = pprint.pformat(status)

                    if status.has_key('geni_status'):
                        msg = "Slice %s at AM %s has overall SliverStatus: %s"% (name, client.str, status['geni_status'])
                        self.logger.info(msg)
                        retVal += msg + ".\n "
                        # FIXME: Do this even if many AMs?

                    exps = expires_from_status(status, self.logger)
                    if len(exps) > 1:
                        # More than 1 distinct sliver expiration found
                        # FIXME: Sort and take first?
                        exps = exps.sort()
                        outputstr = exps[0].isoformat()
                        msg = "Resources in slice %s at AM %s expire at %d different times. First expiration is %s UTC" % (name, client.str, len(exps), outputstr)
                    elif len(exps) == 0:
                        self.logger.debug("Failed to parse a sliver expiration from status")
                        msg = None
                    else:
                        outputstr = exps[0].isoformat()
                        msg = "Resources in slice %s at AM %s expire at %s UTC" % (name, client.str, outputstr)
                    if msg:
                        self.logger.info(msg)
                        retVal += msg + ".\n "

                    # #634: Get the sliverinfo
                    # Then sync these up: create an entry if there isn't one, or update it with the correct expiration
                    if not self.opts.noExtraCHCalls:
                        try:
                            # Get the Agg URN for this client
                            agg_urn = self._getURNForClient(client)
                            self.logger.debug("Syncing sliver_info records with CH....")
                            if urn_util.is_valid_urn(agg_urn):
                                # Extract sliver_urn / expiration pairs from sliverstatus
                                # But this is messy. An AM might report a sliver in the top level geni_urn.
                                # Or it might report multiple geni_resources, and the URN in each geni_urn might be the slivers.
                                # For PG and GRAM and EG, look for geni_urn under geni_resources
                                # At DCN, the geni_urn under geni_resources is what I want, although the URN type says 'slice'
                                poss_slivers = []
                                if status.has_key('geni_resources'):
                                    for resource in status['geni_resources']:
                                        if resource and isinstance(resource, dict) and resource.has_key('geni_urn'):
                                            gurn = resource['geni_urn']
                                            if urn_util.is_valid_urn(gurn):
                                                poss_slivers.append(gurn.strip())
#                                self.logger.debug("AM poss_slivers: %s", str(poss_slivers))

                                # Grab the first expiration. In APIv2 that's the only real one.
                                if isinstance(exps, list):
                                    if len(exps) > 0:
                                        expI = exps[0]
                                    else:
                                        expI = None
                                else:
                                    expI = exps

                                # I'd like to be able to tell the SA to delete all slivers registered for
                                # this slice/AM, but the API says sliver_urn is required
                                slivers_by_am = self.framework.list_sliver_infos_for_slice(urn)
                                if slivers_by_am is None or not slivers_by_am.has_key(agg_urn):
                                    # CH has no slivers. So all slivers the AM reported must be sent to the CH

                                    # FIXME: status should be a list of structs which each has a geni_urn or geni_sliver_urn
                                    # So it could be status['geni_resources']. Mostly I think that works.
                                    s_es = []
                                    if status.has_key('geni_resources'):
                                        s_es = status['geni_resources']
                                        self.logger.debug("CH listed 0 sliver_info records, so creating them all from status info")
                                        # Create an entry
                                        self.framework.create_sliver_info(None, urn, 
                                                                          client.url,
                                                                          expI,
                                                                          s_es, agg_urn)
                                    else:
                                        # No struct of slivers to report
                                        pass
                                else:
                                    # Need to reconcile the CH list and the AM list
                                    ch_slivers = slivers_by_am[agg_urn]
                                    self.logger.debug("Reconciling %d CH sliver infos against %d AM reported slivers", len(ch_slivers.keys()), len(poss_slivers))
                                    # For each CH sliver, if not in poss_slivers, then remove it
                                    # Else if expirations differ, update it
                                    for sliver in ch_slivers.keys():
                                        chexpo = None
                                        if ch_slivers[sliver].has_key('SLIVER_INFO_EXPIRATION'):
                                            chexp = ch_slivers[sliver]['SLIVER_INFO_EXPIRATION']
                                            chexpo = naiveUTC(dateutil.parser.parse(chexp, tzinfos=tzd))
                                        if sliver not in poss_slivers:
                                            self.logger.debug("CH lists sliver '%s' that is not in AM list; delete", sliver)
                                            # CH reported a sliver not reported by the AM. Delete it
                                            self.framework.delete_sliver_info(sliver)
                                        else:
                                            if chexpo is None or (expI is not None and abs(chexpo - expI) > datetime.timedelta.resolution):
                                                self.logger.debug("CH sliver %s expiration %s != AM exp %s; update at CH", sliver, str(chexpo), str(expI))
                                                # update the recorded expiration time to be accurate
                                                self.framework.update_sliver_info(agg_urn, urn, sliver,
                                                                                  expI)
                                            else:
                                                # CH has what we have
#                                                self.logger.debug("CH agrees about expiration of %s: %s", sliver, expI)
                                                pass

                                    # Then for each AM sliver, if not in ch_slivers, add it
                                    sliver_statusstruct = []
                                    for amsliver in poss_slivers:
                                        if amsliver not in ch_slivers.keys():
                                            self.logger.debug("AM lists sliver %s not reported by CH", amsliver)
                                            # AM reported a sliver not reported by the CH
                                            if status.has_key('geni_resources'):
                                                s_es = status['geni_resources']
                                                for resource in status['geni_resources']:
                                                    if resource and isinstance(resource, dict) and resource.has_key('geni_urn'):
                                                        gurn = resource['geni_urn']
                                                        if gurn.strip() == amsliver:
                                                            sliver_statusstruct.append(resource)
                                                            break
                                    if len(sliver_statusstruct) > 0:
                                        self.logger.debug("Creating %s sliver records at CH", len(sliver_statusstruct))
                                        # Create an entry for each sliver that was missing
                                        self.framework.create_sliver_info(None, urn, 
                                                                          client.url,
                                                                          expI,
                                                                          sliver_statusstruct, agg_urn)
                                # End of else block to reconcile CH vs AM sliver lists
                            else:
                                self.logger.debug("Not syncing slivers with CH - no valid AM URN known")
                        except NotImplementedError, nie:
                            self.logger.debug('Framework %s doesnt support recording slivers in SA database', self.config['selected_framework']['type'])
                        except Exception, e:
                            # FIXME: info only?
                            self.logger.warn('Error syncing slivers with SA database')
                            self.logger.debug(e)
                    else:
                        self.logger.debug("Per commandline option, not syncing slivers with clearinghouse")
                    # End of block to sync sliver_info with CH
                # End of block to handle status is a dict

                # Save/print out result
                header="Sliver status for Slice %s at AM %s" % (urn, client.str)
                filename = None
                if self.opts.output:
                    filename = _construct_output_filename(self.opts, name, client.url, client.urn, "sliverstatus", ".json", numClients)
                    #self.logger.info("Writing result of sliverstatus for slice: %s at AM: %s to file %s", name, client.url, filename)

                _printResults(self.opts, self.logger, header, prettyResult, filename)
                if filename:
                    retVal += "Saved sliverstatus on %s at AM %s to file %s. \n" % (name, client.str, filename)
                retItem[ client.url ] = status
                successCnt+=1
            else:
                # #634:
                # delete any sliver_infos for this am/slice
                # However, not all errors mean there are no slivers here.
                # Based on testing 8/2014, all AMs return code 2 or code 12 if there are no slivers here
                # so that it's safe to delete any sliver_info records. 
                # Use code 15 too as that seems reasonable.
                # SEARCHFAILED (12), EXPIRED (15)
                # EG uses ERROR (2), but that's too general so avoid that one
                doDelete = False
                code = -1
                if rawResult is not None and isinstance(rawResult, dict) and rawResult.has_key('code') and isinstance(rawResult['code'], dict) and 'geni_code' in rawResult['code']:
                    code = rawResult['code']['geni_code']
                if code==12 or code==15:
                    doDelete=True
                if doDelete and not self.opts.noExtraCHCalls:
                    self.logger.debug("SliverStatus failed with an error that suggests no slice at this AM - delete all sliverinfo records: %s", message)
                    # delete sliver info from SA database
                    try:
                        # Get the Agg URN for this client
                        agg_urn = self._getURNForClient(client)
                        if urn_util.is_valid_urn(agg_urn):
                            # I'd like to be able to tell the SA to delete all slivers registered for
                            # this slice/AM, but the API says sliver_urn is required
                            sliver_urns = self.framework.list_sliverinfo_urns(urn, agg_urn)
                            for sliver_urn in sliver_urns:
                                self.framework.delete_sliver_info(sliver_urn)
                        else:
                            self.logger.debug("Not ensuring with CH that AM %s slice %s has no slivers - no valid AM URN known")
                    except NotImplementedError, nie:
                        self.logger.debug('Framework %s doesnt support recording slivers in SA database', self.config['selected_framework']['type'])
                    except Exception, e:
                        self.logger.info('Error ensuring slice has no slivers recorded in SA database at this AM')
                        self.logger.debug(e)
                else:
                    if self.opts.noExtraCHCalls:
                        self.logger.debug("Per commandline option, not ensuring clearinghouse lists no slivers for this slice.")
                    else:
                        self.logger.debug("Based on return error code, (%d), not deleting any slivers here.", code)

                if amapiError is not None:
                    self.logger.debug("Having processed the sliverstatus return, now raise the AMAPI Error")
                    raise amapiError

                # FIXME: Put the message error in retVal?
                # FIXME: getVersion uses None as the value in this case. Be consistent
                retItem[ client.url ] = False
                if message is None or message.strip() == "":
                    if status is None:
                        message = "(no reason given, missing result)"
                    elif status == False:
                        message = "(no reason given, False result)"
                    elif status == 0:
                        message = "(no reason given, 0 result)"
                    else:
                        message = "(no reason given, empty result)"
                retVal += "\nFailed to get SliverStatus on %s at AM %s: %s\n" % (name, client.str, message)
        # End of loop over clients

        # FIXME: Return the status if there was only 1 client?
        if numClients > 0:
            retVal += "Returned status of slivers on %d of %d possible aggregates." % (successCnt, self.numOrigClients)
        return retVal, retItem
    # End of sliverstatus

    def status(self, args):
        """AM API Status <slice name>

        For use in AM API v3+. See sliverstatus for the v1 and v2 equivalent.

        Slice name could be a full URN, but is usually just the slice name portion.
        Note that PLC Web UI lists slices as <site name>_<slice name>
        (e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

        Slice credential is usually retrieved from the Slice Authority. But
        with the --slicecredfile option it is read from that file, if it exists.

        --sliver-urn / -u option: each specifies a sliver URN to get status on. If specified, 
        only the listed slivers will be queried. Otherwise, all slivers in the slice will be queried.

        Aggregates queried:
        - If `--useSliceAggregates`, each aggregate recorded at the clearinghouse as having resources for the given slice,
          '''and''' any aggregates specified with the `-a` option.
         - Only supported at some clearinghouses, and the list of aggregates is only advisory
        - Each URL given in an -a argument or URL listed under that given
        nickname in omni_config, if provided, ELSE
        - List of URLs given in omni_config aggregates option, if provided, ELSE
        - List of URNs and URLs provided by the selected clearinghouse

        Output directing options:
        -o Save result in per-Aggregate files
        -p (used with -o) Prefix for resulting files
        --outputfile If supplied, use this output file name: substitute the AM for any %a,
        and %s for any slicename
        If not saving results to a file, they are logged.
        If --tostdout option, then instead of logging, print to STDOUT.

        File names will indicate the slice name, file format, and
        which aggregate is represented.
        e.g.: myprefix-myslice-poa-geni_start-localhost-8001.json

        -V# API Version #
        --devmode: Continue on error if possible
        -l to specify a logging config file
        --logoutput <filename> to specify a logging output filename

        Sample usage:
        Get status on the slice at given aggregate
        omni.py -V3 -a http://aggregate/url status myslice

        Get status on specific slivers and save the result to a file
        omni.py -V3 -a http://aggregate/url -o --outputfile %s-status-%a.json -u urn:publicid:IDN+myam+sliver+1 -u urn:publicid:IDN+myam+sliver+2 status myslice
        """

        if self.opts.api_version < 3:
            if self.opts.devmode:
                self.logger.warn("Trying Status with AM API v%d...", self.opts.api_version)
            else:
                self._raise_omni_error("Status is only available in AM API v3+. Use SliverStatus with AM API v%d, or specify -V3 to use AM API v3." % self.opts.api_version)

        # Build up args, options

        # prints slice expiration. Warns or raises an Omni error on problems
        (name, urn, slice_cred,
         retVal, slice_exp) = self._args_to_slicecred(args, 1, "Status")

        successCnt = 0
        retItem = {}
        args = []
        creds = []
        # Get clients
        (clientList, message) = self._getclients()
        numClients = len(clientList)
        if numClients > 0:
            self.logger.info('Status of Slice %s:' % urn)

            creds = _maybe_add_abac_creds(self.framework, slice_cred)
            creds = self._maybe_add_creds_from_files(creds)

            urnsarg, slivers = self._build_urns(urn)
            args = [urnsarg, creds]
            # Add the options dict
            options = self._build_options('Status', name, None)
            args.append(options)
            self.logger.debug("Doing status with urns %s, %d creds, options %r", urnsarg, len(creds), options)
        else:
            prstr = "No aggregates available to get slice status at: %s" % message
            retVal += prstr + "\n"
            self.logger.warn(prstr)

        descripMsg = "slivers in slice %s" % urn
        if len(slivers) > 0:
            descripMsg = "%d slivers in slice %s" % (len(slivers), urn)

        # Do Status at all clients
        op = 'Status'
        msg = "Status of %s at " % (descripMsg)
        for client in clientList:
            try:
                ((status, message), client) = self._api_call(client,
                                                   msg + str(client.url),
                                                   op, args)
            except BadClientException, bce:
                if bce.validMsg and bce.validMsg != '':
                    retVal += bce.validMsg + ". "
                else:
                    retVal += "Skipped aggregate %s. (Unreachable? Doesn't speak AM API v%d? Check the log messages, and try calling 'getversion' to check AM status and API versions supported.).\n" % (client.str, self.opts.api_version)
                if numClients == 1:
                    self._raise_omni_error("\nStatus failed: " + retVal)
                continue

            retItem[client.url] = status
            # Get the dict status out of the result (accounting for API version diffs, ABAC)
            (status, message) = self._retrieve_value(status, message, self.framework)

            if not status:
                # #634:
                # delete any sliver_infos for this am/slice
                # However, not all errors mean there are no slivers here.
                # Based on testing 8/2014, all AMs return code 2 or code 12 if there are no slivers here
                # so that it's safe to delete any sliver_info records. 
                # Use code 15 too as that seems reasonable.
                # Use SEARCHFAILED (12), EXPIRED (15)
                # EG uses ERROR (2), but that will show up in other places. So avoid that one.
                # Also note that if not geni_best_effort
                # that a failure may mean only part failed
                doDelete = False
                raw = retItem[client.url]
                code = -1
                if raw is not None and isinstance(raw, dict) and raw.has_key('code') and isinstance(raw['code'], dict) and 'geni_code' in raw['code']:
                    code = raw['code']['geni_code']
                # Technically if geni_best_effort and got this failure, then all slivers are bad
                # But that's only true if the AM honors geni_best_effort, which it may not
                # So only assume they're all bad if we didn't request any specific slivers.
                if len(slivers) == 0:
                    if code==12 or code==15:
                        doDelete=True
                if not self.opts.noExtraCHCalls:
                    if doDelete:
                        self.logger.debug("Status failed with an error that suggests no slice at this AM or requested slivers not at this AM - delete all/requested sliverinfo records: %s", message)
                        # delete sliver info from SA database
                        try:
                            if len(slivers) > 0:
                                self.logger.debug("Status failed - assuming all %d sliver URNs asked about are invalid and not at this AM - delete from CH", len(slivers))
                                for sliver in slivers:
                                    self.framework.delete_sliver_info(sliver)
                            else:
                                self.logger.debug("Status failed: assuming this slice has 0 slivers at this AM. Ensure CH lists none.")
                                # Get the Agg URN for this client
                                agg_urn = self._getURNForClient(client)
                                if urn_util.is_valid_urn(agg_urn):
                                    # I'd like to be able to tell the SA to delete all slivers registered for
                                    # this slice/AM, but the API says sliver_urn is required
                                    sliver_urns = self.framework.list_sliverinfo_urns(urn, agg_urn)
                                    for sliver_urn in sliver_urns:
                                        self.framework.delete_sliver_info(sliver_urn)
                                else:
                                    self.logger.debug("Not ensuring with CH that AM %s slice %s has no slivers - no valid AM URN known")
                        except NotImplementedError, nie:
                            self.logger.debug('Framework %s doesnt support recording slivers in SA database', self.config['selected_framework']['type'])
                        except Exception, e:
                            self.logger.info('Error ensuring slice has no slivers recorded in SA database at this AM')
                            self.logger.debug(e)
                    else:
                        self.logger.debug("Given AM return code (%d) and # requested slivers (%d), not telling CH to not list these slivers.", code, len(slivers))
                else:
                    self.logger.debug("Per commandline option, not ensuring clearinghouse lists no slivers for this slice.")

                # FIXME: Put the message error in retVal?
                # FIXME: getVersion uses None as the value in this case. Be consistent
                fmt = "\nFailed to get Status on %s at AM %s: %s\n"
                if message is None or message.strip() == "":
                    message = "(no reason given)"
                retVal += fmt % (descripMsg, client.str, message)
                continue
            # End of block to handle got no good status (got an error)

            missingSlivers = self._findMissingSlivers(status, slivers)
            if len(missingSlivers) > 0:
                self.logger.warn("%d slivers from request missing in result?!", len(missingSlivers))
                self.logger.debug("%s", missingSlivers)

            # Summarize result
            retcnt = len(slivers) # Num slivers reporting results
            if retcnt > 0:
                retcnt = retcnt - len(missingSlivers)
            else:
                retcnt = len(self._getSliverResultList(status))
            retVal += "Retrieved Status on %d slivers in slice %s at %s:\n" % (retcnt, urn, client.str)

            sliverFails = self._didSliversFail(status)
            for sliver in sliverFails.keys():
                self.logger.warn("Sliver %s reported error: %s", sliver, sliverFails[sliver])

            # Summarize sliver expiration
            (orderedDates, sliverExps) = self._getSliverExpirations(status, None)
            if len(orderedDates) == 1:
                msg = "All slivers expire on %r." % orderedDates[0].isoformat()
                self.logger.info(msg)
            elif len(orderedDates) == 0:
                msg = "0 Slivers reported results!"
                self.logger.warn(msg)
            else:
                firstTime = orderedDates[0]
                firstCount = len(sliverExps[firstTime])
                msg = "Slivers expire on %d times, next is %d at %r, and others at %d other times." % (len(orderedDates), firstCount, firstTime.isoformat(), len(orderedDates) - 1)
                self.logger.info(msg)
            retVal += "  " + msg + "\n"

            # Summarize overall status
            # Get all statuses in a hash (value is count)
            alloc_statuses, op_statuses = self._getSliverStatuses(status)
            # If only 1 sliver, get its allocation and operational status
            # if alloc or operational status same for all slivers, say so
            # Else say '%d slivers have %d different statuses
            # if op state includes geni_failed or geni_pending_allocation, say so
            # If alloc state includes geni_unallocated, say so
            statusMsg = '  '
            if len(alloc_statuses) == 1:
                if retcnt == 1:
                    statusMsg += "Sliver is "
                else:
                    statusMsg += "All slivers are "
                statusMsg += "in allocation state %s.\n" % alloc_statuses.keys()[0]
            else:
                statusMsg += "  %d slivers have %d different allocation statuses" % (retcnt, len(alloc_statuses.keys()))
                if 'geni_unallocated' in alloc_statuses:
                    statusMsg += "; some are geni_unallocated.\n"
                else:
                    if not statusMsg.endswith('.'):
                        statusMsg += '.'
                    statusMsg += "\n"
            if len(op_statuses) == 1:
                if retcnt == 1:
                    statusMsg += "  Sliver is "
                else:
                    statusMsg += "  All slivers are "
                statusMsg += "in operational state %s.\n" % op_statuses.keys()[0]
            else:
                statusMsg = "  %d slivers have %d different operational statuses" % (retcnt, len(op_statuses.keys()))
                if 'geni_failed' in op_statuses:
                    statusMsg += "; some are geni_failed"
                if 'geni_pending_allocation' in op_statuses:
                    statusMsg += "; some are geni_pending_allocation"
                else:
                    if not statusMsg.endswith('.'):
                        statusMsg += '.'
                    statusMsg += "\n"
            statusMsg += "\n"
            # Resulting text added to retVal (below). But do this even if lots AMs? Or only if limited # of AMs?

            # Print or save out result
            if not isinstance(status, dict):
                # malformed status return
                self.logger.warn('Malformed status from AM %s. Expected struct, got type %s.' % (client.str, status.__class__.__name__))
                # FIXME: Add something to retVal that the result was malformed?
                if isinstance(status, str):
                    prettyResult = str(status)
                else:
                    prettyResult = pprint.pformat(status)
            else:
                prettyResult = json.dumps(status, ensure_ascii=True, indent=2)

            header="Status for %s at AM %s" % (descripMsg, client.str)
            filename = None
            if self.opts.output:
                filename = _construct_output_filename(self.opts, name, client.url, client.urn, "status", ".json", numClients)
                #self.logger.info("Writing result of status for slice: %s at AM: %s to file %s", name, client.url, filename)
            _printResults(self.opts, self.logger, header, prettyResult, filename)
            if filename:
                retVal += "Saved status on %s at AM %s to file %s. \n" % (descripMsg, client.str, filename)
            if len(missingSlivers) > 0:
                retVal += " - %d slivers missing from result!? \n" % len(missingSlivers)
            if len(sliverFails.keys()) > 0:
                retVal += " - %d slivers failed?! \n" % len(sliverFails.keys())
            retVal += statusMsg
            if len(missingSlivers) == 0 and len(sliverFails.keys()) == 0:
                successCnt+=1

            # Now sync up slivers with CH
            if not self.opts.noExtraCHCalls:
                # ensure have agg_urn
                agg_urn = self._getURNForClient(client)
                if urn_util.is_valid_urn(agg_urn):
                    slivers_by_am = None # Slivers in this slice by AM CH reports
                    try:
                        slivers_by_am = self.framework.list_sliver_infos_for_slice(urn)

                        # Gather info on what the AM reported
                        resultValue = self._getSliverResultList(status)
                        status_structs = {} # dict by URN of sliver status structs
                        expirations = {} # dict by URN of sliver expiration string
                        if len(resultValue) == 0:
                            self.logger.debug("Result value not a list or empty")
                        else:
                            for sliver in resultValue:
                                if not isinstance(sliver, dict):
                                    self.logger.debug("entry in result list was not a dict")
                                    continue
                                if not sliver.has_key('geni_sliver_urn') or str(sliver['geni_sliver_urn']).strip() == "":
                                    self.logger.debug("entry in result had no 'geni_sliver_urn'")
                                else:
                                    slivurn = sliver['geni_sliver_urn']
                                    status_structs[slivurn] = sliver
                                    if not sliver.has_key('geni_expires'):
                                        self.logger.debug("Sliver %s missing 'geni_expires'", slivurn)
                                        expirations[slivurn] = slice_exp # Assume sliver expires at slice expiration if not specified
                                        continue
                                    expirations[slivurn] = sliver['geni_expires']
                        # Finished building status_structs and expirations

                        statuses = self._getSliverAllocStates(status) # Dict by URN of sliver alloc state
                        resultSlivers = statuses.keys()

                        if slivers_by_am is None or not slivers_by_am.has_key(agg_urn):
                            # CH has no slivers. So all
                            # slivers the AM reported must be sent
                            # to the CH
                            if len(resultSlivers) > 0:
                                self.logger.debug("CH missing %d slivers at AM - report those that are provisioned", len(resultSlivers))
                            for sliver in resultSlivers:
                                if not statuses.has_key(sliver):
                                    self.logger.debug("No %s key in statuses? %s", sliver, statuses)
                                elif statuses[sliver] == 'geni_provisioned':
                                    if not expirations.has_key(sliver):
                                        self.logger.debug("No %s key in expirations? %s", sliver, expirations)
                                        expO = None
                                    else:
                                        expO = self._datetimeFromString(expirations[sliver])[1]
                                    if not status_structs.has_key(sliver):
                                        self.logger.debug("status_structs missing %s: %s", sliver, status_structs)
                                    else:
                                    # self.logger.debug("Will create sliver. slice: %s, AMURL: %s, expiration: %s, status_struct: %s, AMURN: %s", urn, client.url, expO, status_structs[sliver], agg_urn)
                                        self.framework.create_sliver_info(None, urn, 
                                                                          client.url,
                                                                          expO,
                                                                          [status_structs[sliver]], agg_urn)
                                # else this sliver should not (yet) be recorded at the CH
                        else:
                            # Need to reconcile the CH list and the AM list
                            ch_slivers = slivers_by_am[agg_urn]

                            # missingSlivers: delete CH record for each
                            # FIXME: If self.opts.geni_best_effort could an AM not return an entry for a sliver
                            # you don't have permission to see or something? I don't think I'll
                            # worry about this now.
                            if len(missingSlivers) > 0:
                                self.logger.debug("Ensure %d missing slivers not reported by CH", len(missingSlivers))
                            for missing in missingSlivers:
                                if missing in ch_slivers.keys():
                                    self.framework.delete_sliver_info(missing)
                                # Else AM didn't list it and neither did CH

                            # sliverFails: If the failed sliver says it is provisioned, it should be at the CH
                            # If the failed sliver is not provisioned, then it should not be at the CH (yet)
                            for fail in sliverFails:
                                if statuses[fail] == 'geni_provisioned' and fail not in ch_slivers.keys():
                                    expO = self._datetimeFromString(expirations[fail])[1]
                                    self.logger.debug("Recording failed but provisioned sliver %s at CH (error: %s)", fail, sliverFails[fail])
                                    self.framework.create_sliver_info(None, urn, 
                                                                      client.url,
                                                                      expO,
                                                                      [status_structs[fail]], agg_urn)
                                elif statuses[fail] != 'geni_provisioned' and fail in ch_slivers.keys():
                                    # The AM says the sliver is gone or not yet provisioned: Delete
                                    self.logger.debug("Deleting CH record of failed and not provisioned sliver %s (error: %s, expiration: %s)", fail, sliverFails[fail], expirations[fail])
                                    self.framework.delete_sliver_info(fail)
                                else:
                                    # Do nothing with this failed sliver - just note it
                                    if fail in ch_slivers.keys():
                                        self.logger.debug("Not changing existing CH record of sliver %s that failed: %s", fail, sliverFails[fail])
                                    else:
                                        self.logger.debug("Not adding new CH record of sliver %s that failed: %s", fail, sliverFails[fail])
                            # End of block to handle failed slivers (had a geni_error)

                            # Any in CH not in result (and if we asked for slivers, also in list
                            # we asked for) - Delete
                            # Plus any in CH and result that are not geni_provisioned, delete
                            for ch_sliver in ch_slivers.keys():
                                if ch_sliver not in resultSlivers:
                                    if len(slivers) == 0 or ch_sliver in slivers:
                                        self.logger.debug("Deleting CH record of sliver not at AM: %s", ch_sliver)
                                        self.framework.delete_sliver_info(ch_sliver)
                                elif statuses[ch_sliver] != 'geni_provisioned':
                                    self.logger.debug("Deleting CH record of not provisioned sliver %s (expiration: %s)", ch_sliver, expirations[ch_sliver])
                                    self.framework.delete_sliver_info(ch_sliver)

                            # All other slivers in result (not in sliverFails):
                            for sliver in resultSlivers:
                                if statuses[sliver] == 'geni_provisioned' and sliver not in sliverFails.keys():
                                    if sliver not in ch_slivers.keys():
                                        expO = self._datetimeFromString(expirations[sliver])[1]
                                        self.logger.debug("Recording AM reported sliver %s at CH", sliver)
                                        self.framework.create_sliver_info(None, urn, 
                                                                          client.url,
                                                                          expO,
                                                                          [status_structs[sliver]], agg_urn)
                                    else:
                                        # Now dealing with slivers listed by AM and CH, and provisioned at AM, and not failed
                                        chexpo = None
                                        if ch_slivers[sliver].has_key('SLIVER_INFO_EXPIRATION'):
                                            chexp = ch_slivers[sliver]['SLIVER_INFO_EXPIRATION']
                                            chexpo = naiveUTC(dateutil.parser.parse(chexp, tzinfos=tzd))

                                        expO, expT, _ = self._datetimeFromString(expirations[sliver])
                                        if chexpo is None or (expO is not None and abs(chexpo - expO) > datetime.timedelta.resolution):
                                            self.logger.debug("CH sliver %s expiration %s != AM exp %s; update at CH", sliver, str(chexpo), str(expO))
                                            # update the recorded expiration time to be accurate
                                            self.framework.update_sliver_info(agg_urn, urn, sliver,
                                                                              expT)
                                        # else CH/AM agree on the time. Nothing to do
                                # Else the sliver is not yet provisioned or failed. Should already have been handled
                            # End of loop over slivers in result
                        # End of block where CH lists slivers in the slice for this AM
                    except NotImplementedError, nie:
                        self.logger.debug('Framework %s doesnt support recording slivers in SA database', self.config['selected_framework']['type'])
                    except Exception, e:
                        self.logger.info('Error ensuring CH lists same slivers as at this AM')
                        self.logger.debug(e)
                else:
                    self.logger.debug("Not syncing slivers with CH - no valid AM URN known")
            else:
                self.logger.debug("Per commandline option, not syncing slivers with clearinghouse.")

        # End of loop over clients

        # FIXME: Return the status if there was only 1 client?
        if numClients > 0:
            retVal += "Returned status of slivers on %d of %d possible aggregates." % (successCnt, self.numOrigClients)
        self.logger.debug("Status result: " + json.dumps(retItem, indent=2))
        return retVal, retItem
    # End of status

    def deletesliver(self, args):
        """AM API DeleteSliver <slicename>
        For use in AM API v1&2; Use Delete() for v3+
        Slice name could be a full URN, but is usually just the slice name portion.
        Note that PLC Web UI lists slices as <site name>_<slice name>
        (e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

        Slice credential is usually retrieved from the Slice Authority. But
        with the --slicecredfile option it is read from that file, if it exists.

        Aggregates queried:
        - If `--useSliceAggregates`, each aggregate recorded at the clearinghouse as having resources for the given slice,
          '''and''' any aggregates specified with the `-a` option.
         - Only supported at some clearinghouses, and the list of aggregates is only advisory
        - Each URL given in an -a argument or URL listed under that given
        nickname in omni_config, if provided, ELSE
        - List of URLs given in omni_config aggregates option, if provided, ELSE
        - List of URNs and URLs provided by the selected clearinghouse

        -V# API Version #
        --devmode: Continue on error if possible
        -l to specify a logging config file
        --logoutput <filename> to specify a logging output filename
        """
        if self.opts.api_version >= 3:
            if self.opts.devmode:
                self.logger.warn("Trying DeleteSliver with AM API v%d...", self.opts.api_version)
            else:
                self._raise_omni_error("DeleteSliver is only available in AM API v1 or v2. Use Delete, or specify the -V2 option to use AM API v2, if the AM supports it.")

        # prints slice expiration. Warns or raises an Omni error on problems
        (name, urn, slice_cred, retVal, slice_exp) = self._args_to_slicecred(args, 1, "DeleteSliver")

        creds = _maybe_add_abac_creds(self.framework, slice_cred)
        creds = self._maybe_add_creds_from_files(creds)

        args = [urn, creds]
        op = 'DeleteSliver'
        options = self._build_options(op, name, None)
#--- API version specific
        if self.opts.api_version >= 2:
            # Add the options dict
            args.append(options)

        self.logger.debug("Doing deletesliver with urn %s, %d creds, options %r", urn, len(creds), options)

        successList = []
        failList = []
        successCnt = 0
        (clientList, message) = self._getclients()
        numClients = len(clientList)
        msg = "%s %s at " % (op, urn)

        # Connect to each available GENI AM
        ## The AM API does not cleanly state how to deal with
        ## aggregates which do not have a sliver in this slice.  We
        ## know at least one aggregate (PG) returns an Exception in
        ## this case.
        ## FIX ME: May need to look at handling of this more in the future.
        ## Also, if the user supplied the aggregate list, a failure is
        ## more interesting.  We can figure out what the error strings
        ## are at the various aggregates if they don't know about the
        ## slice and make those more quiet.  Finally, we can try
        ## sliverstatus at places where it fails to indicate places
        ## where you still have resources.
        for client in clientList:
            try:
                ((rawres, message), client) = self._api_call(client,
                                                   msg + str(client.url),
                                                   op, args)
            except BadClientException, bce:
                if bce.validMsg and bce.validMsg != '':
                    retVal += bce.validMsg + ". "
                else:
                    retVal += "Skipped aggregate %s. (Unreachable? Doesn't speak AM API v%d? Check the log messages, and try calling 'getversion' to check AM status and API versions supported.).\n" % (client.str, self.opts.api_version)
                if numClients == 1:
                    self._raise_omni_error("\nDeleteSliver failed: " + retVal)
                continue

            amapiError = None
            res = None
            try:
                # Get the boolean result out of the result (accounting for API version diffs, ABAC)
                (res, message) = self._retrieve_value(rawres, message, self.framework)
            except AMAPIError, amapiError:
                # Would raise an AMAPIError.
                # But that loses the side-effect of deleting any sliverinfo records.
                # So if we're doing those, hold odd on raising the error
                if self.opts.noExtraCHCalls:
                    raise amapiError
                else:
                    self.logger.debug("Got AMAPIError retrieving value from deletesliver. Hold it until we do any sliver info processing")

            if res:
                prStr = "Deleted sliver %s at %s" % (urn,
                                                     (client.str if client.nick else client.urn))

                if not self.opts.noExtraCHCalls:
                    # delete sliver info from SA database
                    try:
                        # Get the Agg URN for this client
                        agg_urn = self._getURNForClient(client)
                        if urn_util.is_valid_urn(agg_urn):
                            # I'd like to be able to tell the SA to delete all slivers registered for
                            # this slice/AM, but the API says sliver_urn is required
                            sliver_urns = self.framework.list_sliverinfo_urns(urn, agg_urn)
                            for sliver_urn in sliver_urns:
                                self.framework.delete_sliver_info(sliver_urn)
                        else:
                            self.logger.debug("Not reporting to CH that slivers were deleted - no valid AM URN known")
                    except NotImplementedError, nie:
                        self.logger.debug('Framework %s doesnt support recording slivers in SA database', self.config['selected_framework']['type'])
                    except Exception, e:
                        # FIXME: info only?
                        self.logger.warn('Error noting sliver deleted in SA database')
                        self.logger.debug(e)
                else:
                    self.logger.debug("Per commandline option, not reporting sliver deleted to clearinghouse")

                if numClients == 1:
                    retVal = prStr
                self.logger.info(prStr)
                successCnt += 1
                successList.append( client.url )
            else:
                doDelete = False
                code = -1
                if rawres is not None and isinstance(rawres, dict) and rawres.has_key('code') and isinstance(rawres['code'], dict) and 'geni_code' in rawres['code']:
                    code = rawres['code']['geni_code']
                if code==12 or code==15:
                    doDelete=True
                if doDelete and not self.opts.noExtraCHCalls:
                    self.logger.debug("DeleteSliver failed with an error that suggests no slice at this AM - delete all sliverinfo records: %s", message)
                    # delete sliver info from SA database
                    try:
                        # Get the Agg URN for this client
                        agg_urn = self._getURNForClient(client)
                        if urn_util.is_valid_urn(agg_urn):
                            # I'd like to be able to tell the SA to delete all slivers registered for
                            # this slice/AM, but the API says sliver_urn is required
                            sliver_urns = self.framework.list_sliverinfo_urns(urn, agg_urn)
                            for sliver_urn in sliver_urns:
                                self.framework.delete_sliver_info(sliver_urn)
                        else:
                            self.logger.debug("Not ensuring with CH that AM %s slice %s has no slivers - no valid AM URN known")
                    except NotImplementedError, nie:
                        self.logger.debug('Framework %s doesnt support recording slivers in SA database', self.config['selected_framework']['type'])
                    except Exception, e:
                        self.logger.info('Error ensuring slice has no slivers recorded in SA database at this AM')
                        self.logger.debug(e)
                else:
                    if self.opts.noExtraCHCalls:
                        self.logger.debug("Per commandline option, not ensuring clearinghouse lists no slivers for this slice.")
                    else:
                        self.logger.debug("Based on return error code, (%d), not deleting any sliver infos here.", code)

                if amapiError is not None:
                    self.logger.debug("Having processed the deletesliver return, now raise the AMAPI Error")
                    raise amapiError

                prStr = "Failed to delete sliver %s at %s (got result '%s')" % (urn, (client.str if client.nick else client.urn), res)
                if message is None or message.strip() == "":
                    message = "(no reason given)"
                if not prStr.endswith('.'):
                    prStr += '.'
                prStr += " " + message
                self.logger.warn(prStr)
                if numClients == 1:
                    retVal = prStr
                failList.append( client.url )
        if numClients == 0:
            retVal = "No aggregates specified on which to delete slivers. %s" % message
        elif numClients > 1:
            retVal = "Deleted slivers on %d out of a possible %d aggregates" % (successCnt, self.numOrigClients)
        return retVal, (successList, failList)
    # End of deletesliver

    def delete(self, args):
        """AM API Delete <slicename>
        For use in AM API v3+. Use DeleteSliver for API v1&2.
        Delete the named slivers, making them geni_unallocated. Resources are stopped
        if necessary, and both de-provisioned and de-allocated. No further AM API
        operations may be performed on slivers that have been deleted.
        See deletesliver.

        Slice name could be a full URN, but is usually just the slice name portion.
        Note that PLC Web UI lists slices as <site name>_<slice name>
        (e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

        Slice credential is usually retrieved from the Slice Authority. But
        with the --slicecredfile option it is read from that file, if it exists.

        --sliver-urn / -u option: each specifies a sliver URN to delete. If specified,
        only the listed slivers will be deleted. Otherwise, all slivers in the slice will be deleted.
        --best-effort: If supplied, slivers that can be deleted, will be; some slivers
        may not be deleted, in which case check the geni_error return for that sliver.
        If not supplied, then if any slivers cannot be deleted, the whole call fails
        and slivers do not change.

        Aggregates queried:
        - If `--useSliceAggregates`, each aggregate recorded at the clearinghouse as having resources for the given slice,
          '''and''' any aggregates specified with the `-a` option.
         - Only supported at some clearinghouses, and the list of aggregates is only advisory
        - Each URL given in an -a argument or URL listed under that given
        nickname in omni_config, if provided, ELSE
        - List of URLs given in omni_config aggregates option, if provided, ELSE
        - List of URNs and URLs provided by the selected clearinghouse

        Output directing options:
        -o Save result in per-Aggregate files
        -p (used with -o) Prefix for resulting files
        --outputfile If supplied, use this output file name: substitute the AM for any %a,
        and %s for any slicename
        If not saving results to a file, they are logged.
        If --tostdout option, then instead of logging, print to STDOUT.

        File names will indicate the slice name, file format, and
        which aggregate is represented.
        e.g.: myprefix-myslice-delete-localhost-8001.json

        -V# API Version #
        --devmode: Continue on error if possible
        -l to specify a logging config file
        --logoutput <filename> to specify a logging output filename

        Sample usage:
        Delete all slivers in the slice at specific aggregates
        omni.py -V3 -a http://aggregate/url -a http://another/url delete myslice

        Delete slivers in slice myslice; any slivers that cannot be deleted, stay as they were, while others are deleted
        omni.py -V3 -a http://myaggregate/url --best-effort delete myslice

        Delete the given sliver in myslice at this AM and write the result struct to the given file
        omni.py -V3 -a http://myaggregate/url -o --outputfile %s-delete-%a.json -u urn:publicid:IDN+myam+sliver+1 delete myslice
        """

        if self.opts.api_version < 3:
            if self.opts.devmode:
                self.logger.warn("Trying Delete with AM API v%d...", self.opts.api_version)
            else:
                self._raise_omni_error("Delete is only available in AM API v3+. Use DeleteSliver with AM API v%d, or specify -V3 to use AM API v3." % self.opts.api_version)

        # Gather options, args

        # prints slice expiration. Warns or raises an Omni error on problems
        (name, urn, slice_cred,
         retVal, slice_exp) = self._args_to_slicecred(args, 1, "Delete")

        creds = _maybe_add_abac_creds(self.framework, slice_cred)
        creds = self._maybe_add_creds_from_files(creds)

        urnsarg, slivers = self._build_urns(urn)

        descripMsg = "slivers in slice %s" % urn
        if len(slivers) > 0:
            descripMsg = "%d slivers in slice %s" % (len(slivers), urn)

        args = [urnsarg, creds]
        # Add the options dict
        options = self._build_options('Delete', name, None)
        args.append(options)

        self.logger.debug("Doing delete with urns %s, %d creds, options %r",
                          urnsarg, len(creds), options)

        successCnt = 0
        (clientList, message) = self._getclients()
        numClients = len(clientList)

        # Connect to each available GENI AM
        ## The AM API does not cleanly state how to deal with
        ## aggregates which do not have a sliver in this slice.  We
        ## know at least one aggregate (PG) returns an Exception in
        ## this case.
        ## FIX ME: May need to look at handling of this more in the future.
        ## Also, if the user supplied the aggregate list, a failure is
        ## more interesting.  We can figure out what the error strings
        ## are at the various aggregates if they don't know about the
        ## slice and make those more quiet.  Finally, we can try
        ## to call status at places where it fails to indicate places
        ## where you still have resources.
        op = 'Delete'
        msg = "Delete of %s at " % (descripMsg)
        retItem = {}
        for client in clientList:
            try:
                ((result, message), client) = self._api_call(client,
                                                   msg + str(client.url),
                                                   op, args)
            except BadClientException, bce:
                if bce.validMsg and bce.validMsg != '':
                    retVal += bce.validMsg + ". "
                else:
                    retVal += "Skipped aggregate %s. (Unreachable? Doesn't speak AM API v%d? Check the log messages, and try calling 'getversion' to check AM status and API versions supported.).\n" % (client.str, self.opts.api_version)
                if numClients == 1:
                    self._raise_omni_error("\nDelete failed: " + retVal)
                continue

            retItem[client.url] = result

            (realres, message) = self._retrieve_value(result, message, self.framework)
            someSliversFailed = False
            badSlivers = self._getSliverAllocStates(realres, 'geni_unallocated')
            for sliver in badSlivers.keys():
                self.logger.warn("Sliver %s in wrong state! Expected %s, got %s?!", sliver, 'geni_unallocated', badSlivers[sliver])
                # FIXME: This really might be a case where sliver in wrong state means the call failed?!
                someSliversFailed = True

            missingSlivers = self._findMissingSlivers(realres, slivers)
            if len(missingSlivers) > 0:
                self.logger.debug("Slivers from request missing in result: %s", missingSlivers)

            sliverFails = self._didSliversFail(realres)
            for sliver in sliverFails.keys():
                self.logger.warn("Sliver %s reported error: %s", sliver, sliverFails[sliver])

            if realres is not None:

                if not self.opts.noExtraCHCalls:
                    # record results in SA database
                    try:
                        sliversDict = self._getSliverResultList(realres)
                        for sliver in sliversDict:
                            if isinstance(sliver, dict) and \
                                    sliver.has_key('geni_sliver_urn'):
                                # Note that the sliver may not be in the DB if you delete after allocate

                                # FIXME: Exclude any slivers that are not geni_unallocated?
                                # That is, what happens if you call delete only with specific slivers, 
                                # and do not delete all the slivers. Will the others be returned?
                                # I think the others are not _supposed to be returned....

                                # FIXME: If the user asked to delete everything in this slice
                                # at this AM, should I use list_slivers to delete everything
                                # the CH knows in this slice at this AM, in case something got missed?

                                # FIXME: Exclude slivers in sliverFails (had errors)?
                                if sliver['geni_sliver_urn'] in sliverFails.keys():
                                    self.logger.debug("Skipping noting delete of failed sliver %s", sliver)
                                    continue
                                self.logger.debug("Recording sliver %s deleted", sliver)
                                self.framework.delete_sliver_info \
                                    (sliver['geni_sliver_urn'])
                            else:
                                self.logger.debug("Skipping noting delete of malformed sliver %s", sliver)
                    except NotImplementedError, nie:
                        self.logger.debug('Framework %s doesnt support recording slivers in SA database', self.config['selected_framework']['type'])
                    except Exception, e:
                        # FIXME Info?
                        self.logger.warn('Error noting sliver deleted in SA database')
                        self.logger.debug(e)
                else:
                    self.logger.debug("Per commandline option, not reporting sliver deleted to clearinghouse")

                prStr = "Deleted %s at %s" % (descripMsg,
                                              (client.str if client.nick else client.urn))
                if someSliversFailed:
                    prStr += " - but %d slivers are not fully de-allocated; check the return! " % len(badSlivers.keys())
                if len(missingSlivers) > 0:
                    prStr += " - but %d slivers from request missing in result!? " % len(missingSlivers)
                if len(sliverFails.keys()) > 0:
                    prStr += " = but %d slivers failed! " % len(sliverFails.keys())
                if numClients == 1:
                    retVal = prStr + "\n"
                self.logger.info(prStr)

                # Construct print / save out result

                if not isinstance(realres, list):
                    # malformed describe return
                    self.logger.warn('Malformed delete result from AM %s. Expected list, got type %s.' % (client.str, realres.__class__.__name__))
                    # FIXME: Add something to retVal saying that the result was malformed?
                    if isinstance(realres, str):
                        prettyResult = str(realres)
                    else:
                        prettyResult = pprint.pformat(realres)
                else:
                    prettyResult = json.dumps(realres, ensure_ascii=True, indent=2)

                header="Deletion of %s at AM %s" % (descripMsg, client.str)
                filename = None
                if self.opts.output:
                    filename = _construct_output_filename(self.opts, name, client.url, client.urn, "delete", ".json", numClients)
                #self.logger.info("Writing result of delete for slice: %s at AM: %s to file %s", name, client.url, filename)
                _printResults(self.opts, self.logger, header, prettyResult, filename)
                if filename:
                    retVal += "Saved deletion of %s at AM %s to file %s. \n" % (descripMsg, client.str, filename)

                if len(sliverFails.keys()) == 0:
                    successCnt += 1
            else:
                doDelete = False
                raw = retItem[client.url]
                code = -1
                if raw is not None and isinstance(raw, dict) and raw.has_key('code') and isinstance(raw['code'], dict) and 'geni_code' in raw['code']:
                    code = raw['code']['geni_code']
                # Technically if geni_best_effort and got this failure, then all slivers are bad
                # But that's only true if the AM honors geni_best_effort, which it may not
                # So only assume they're all bad if we didn't request any specific slivers.
                if len(slivers) == 0:
                    if code==12 or code==15:
                        doDelete=True
                if not self.opts.noExtraCHCalls:
                    if doDelete:
                        self.logger.debug("Delete failed with an error that suggests no slice at this AM or requested slivers not at this AM - delete all/requested sliverinfo records: %s", message)
                        # delete sliver info from SA database
                        try:
                            if len(slivers) > 0:
                                self.logger.debug("Delete failed - assuming all %d sliver URNs asked about are invalid and not at this AM - delete from CH", len(slivers))
                                for sliver in slivers:
                                    self.framework.delete_sliver_info(sliver)
                            else:
                                self.logger.debug("Delete failed: assuming this slice has 0 slivers at this AM. Ensure CH lists none.")
                                # Get the Agg URN for this client
                                agg_urn = self._getURNForClient(client)
                                if urn_util.is_valid_urn(agg_urn):
                                    # I'd like to be able to tell the SA to delete all slivers registered for
                                    # this slice/AM, but the API says sliver_urn is required
                                    sliver_urns = self.framework.list_sliverinfo_urns(urn, agg_urn)
                                    for sliver_urn in sliver_urns:
                                        self.framework.delete_sliver_info(sliver_urn)
                                else:
                                    self.logger.debug("Not ensuring with CH that AM %s slice %s has no slivers - no valid AM URN known")
                        except NotImplementedError, nie:
                            self.logger.debug('Framework %s doesnt support recording slivers in SA database', self.config['selected_framework']['type'])
                        except Exception, e:
                            self.logger.info('Error ensuring slice has no slivers recorded in SA database at this AM')
                            self.logger.debug(e)
                    else:
                        self.logger.debug("Given AM return code (%d) and # requested slivers (%d), not telling CH to not list these slivers.", code, len(slivers))
                else:
                    self.logger.debug("Per commandline option, not ensuring clearinghouse lists no slivers for this slice.")

                if message is None or message.strip() == "":
                    message = "(no reason given)"
                prStr = "Failed to delete %s at %s: %s" % (descripMsg, (client.str if client.nick else client.urn), message)
                self.logger.warn(prStr)
                if numClients == 1:
                    retVal = prStr
        # loop over all clients

        if numClients == 0:
            retVal = "No aggregates specified on which to delete slivers. %s" % message
        elif numClients > 1:
            retVal = "Deleted slivers on %d out of a possible %d aggregates" % (successCnt, self.numOrigClients)
        self.logger.debug("Delete result: " + json.dumps(retItem, indent=2))
        return retVal, retItem
    # End of delete

    def shutdown(self, args):
        """AM API Shutdown <slicename>
        Slice name could be a full URN, but is usually just the slice name portion.
        Note that PLC Web UI lists slices as <site name>_<slice name>
        (e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

        Slice credential is usually retrieved from the Slice Authority. But
        with the --slicecredfile option it is read from that file, if it exists.

        Aggregates queried:
        - If `--useSliceAggregates`, each aggregate recorded at the clearinghouse as having resources for the given slice,
          '''and''' any aggregates specified with the `-a` option.
         - Only supported at some clearinghouses, and the list of aggregates is only advisory
        - Each URL given in an -a argument or URL listed under that given
        nickname in omni_config, if provided, ELSE
        - List of URLs given in omni_config aggregates option, if provided, ELSE
        - List of URNs and URLs provided by the selected clearinghouse

        -V# API Version #
        --devmode: Continue on error if possible
        -l to specify a logging config file
        --logoutput <filename> to specify a logging output filename
        """

        # prints slice expiration. Warns or raises an Omni error on problems
        (name, urn, slice_cred, retVal, slice_exp) = self._args_to_slicecred(args, 1, "Shutdown")

        creds = _maybe_add_abac_creds(self.framework, slice_cred)
        creds = self._maybe_add_creds_from_files(creds)

        args = [urn, creds]
        op = "Shutdown"
        options = self._build_options(op, name, None)
        if self.opts.api_version >= 2:
            # Add the options dict
            args.append(options)

        self.logger.debug("Doing shutdown with urn %s, %d creds, options %r", urn, len(creds), options)

        #Call shutdown on each AM
        successCnt = 0
        successList = []
        failList = []
        retItem = dict()
        (clientList, message) = self._getclients()
        numClients = len(clientList)
        msg = "Shutdown %s on " % (urn)
        for client in clientList:
            try:
                ((res, message), client) = self._api_call(client, msg + client.url, op, args)
            except BadClientException, bce:
                if bce.validMsg and bce.validMsg != '':
                    retVal += bce.validMsg + ". "
                else:
                    retVal += "Skipped aggregate %s. (Unreachable? Doesn't speak AM API v%d? Check the log messages, and try calling 'getversion' to check AM status and API versions supported.).\n" % (client.str, self.opts.api_version)
                if numClients == 1:
                    self._raise_omni_error("\nShutdown Failed: " + retVal)
                continue

            retItem[client.url] = res
            # Get the boolean result out of the result (accounting for API version diffs, ABAC)
            (res, message) = self._retrieve_value(res, message, self.framework)

            if res:
                prStr = "Shutdown Sliver %s at AM %s" % (urn, (client.str if client.nick else client.urn))
                self.logger.info(prStr)
                if numClients == 1:
                    retVal = prStr
                successCnt+=1
                successList.append( client.url )
            else:
                prStr = "Failed to shutdown sliver %s at AM %s" % (urn, (client.str if client.nick else client.urn)) 
                if message is None or message.strip() == "":
                    message = "(no reason given)"
                if not prStr.endswith('.'):
                    prStr += '.'
                prStr += " " + message
                self.logger.warn(prStr)
                if numClients == 1:
                    retVal = prStr
                failList.append( client.url )
        if numClients == 0:
            retVal = "No aggregates specified on which to shutdown slice %s. %s" % (urn, message)
        elif numClients > 1:
            retVal = "Shutdown slivers of slice %s on %d of %d possible aggregates" % (urn, successCnt, self.numOrigClients)
        if self.opts.api_version < 3:
            return retVal, (successList, failList)
        else:
            return retVal, retItem
    # End of shutdown

    def update(self, args):
        """
        GENI AM API Update <slice name> <rspec file name>
        For use with AM API v3+ only, and only at some AMs. 
        Technically adopted for AM API v4, but may be implemented by v3 AMs. See http://groups.geni.net/geni/wiki/GAPI_AM_API_DRAFT/Adopted#ChangeSetC:Update

        Update resources as described in a request RSpec argument in a slice with 
        the named URN. Update the named slivers if specified, or all slivers in the slice at the aggregate.
        On success, new resources in the RSpec will be allocated in new slivers, existing resources in the RSpec will
        be updated, and slivers requested but missing in the RSpec will be deleted.

        Return a string summarizing results, and a dictionary by AM URL of the return value from the AM.

        After update, slivers that were geni_allocated remain geni_allocated (unless they were left
        out of the RSpec, indicating they should be deleted, which is then immediate). Slivers that were 
        geni_provisioned or geni_updating will be geni_updating.
        Clients must Renew or Provision any new (geni_updating) slivers before the expiration time
        (given in the return struct), or the aggregate will automatically revert the changes 
        (delete new slivers or revert changed slivers to their original state). 
        Slivers that were geni_provisioned that you do not include in the RSpec will be deleted, 
        but only after calling Provision.
        Slivers that were geni_allocated or geni_updating are immediately changed.

        Slice name could be a full URN, but is usually just the slice name portion.
        Note that PLC Web UI lists slices as <site name>_<slice name>
        (e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

        Slice credential is usually retrieved from the Slice Authority. But
        with the --slicecredfile option it is read from that file, if it exists.

        Aggregates queried:
        - If `--useSliceAggregates`, each aggregate recorded at the clearinghouse as having resources for the given slice,
          '''and''' any aggregates specified with the `-a` option.
         - Only supported at some clearinghouses, and the list of aggregates is only advisory
        - Each URL given in an -a argument or URL listed under that given
        nickname in omni_config, if provided, ELSE
        - List of URLs given in omni_config aggregates option, if provided, ELSE
        - List of URNs and URLs provided by the selected clearinghouse
        Note that if multiple aggregates are supplied, the same RSpec will be submitted to each.
        Aggregates should ignore parts of the Rspec requesting specific non-local resources (bound requests), but each 
        aggregate should attempt to satisfy all unbound requests. 

        --sliver-urn / -u option: each specifies a sliver URN to update. If specified, 
        only the listed slivers will be updated. Otherwise, all slivers in the slice will be updated.
        --best-effort: If supplied, slivers that can be updated, will be; some slivers 
        may not be updated, in which case check the geni_error return for that sliver.
        If not supplied, then if any slivers cannot be updated, the whole call fails
        and sliver states do not change.

        Note that some aggregates may require updating all slivers in the same state at the same 
        time, per the geni_single_allocation GetVersion return.

        --end-time: Request that new slivers expire at the given time.
        The aggregates may update the resources, but not be able to grant the requested
        expiration time.
        Note that per the AM API expiration times will be timezone aware.
        Unqualified times are assumed to be in UTC.
        Note that the expiration time cannot be past your slice expiration
        time (see renewslice).

        Output directing options:
        -o Save result in per-Aggregate files
        -p (used with -o) Prefix for resulting files
        --outputfile If supplied, use this output file name: substitute the AM for any %a,
        and %s for any slicename
        If not saving results to a file, they are logged.
        If --tostdout option, then instead of logging, print to STDOUT.

        File names will indicate the slice name, file format, and
        which aggregate is represented.
        e.g.: myprefix-myslice-update-localhost-8001.json

        -V# API Version #
        --devmode: Continue on error if possible
        -l to specify a logging config file
        --logoutput <filename> to specify a logging output filename

        Sample usage:
        Basic update of resources at 1 AM into myslice
        omni.py -V3 -a http://myaggregate/url update myslice my-request-rspec.xml

        Update resources in 2 AMs, requesting a specific sliver end time, save results into specificly named files that include an AM name calculated from the AM URL,
        using the slice credential saved in the given file
        omni.py -V3 -a http://myaggregate/url -a http://myother/aggregate --end-time 20120909 -o --outputfile myslice-manifest-%a.json --slicecredfile mysaved-myslice-slicecred.xml update myslice my-update-rspec.xml
        """
        if self.opts.api_version < 3:
            if self.opts.devmode:
                self.logger.warn("Trying Update with AM API v%d...", self.opts.api_version)
            else:
                self._raise_omni_error("Update is only available in AM API v3+. Specify -V3 to use AM API v3.")

        (slicename, urn, slice_cred, retVal, slice_exp) = self._args_to_slicecred(args, 2,
                                                      "Update",
                                                      "and a request rspec filename")
        # Load up the user's request rspec
        rspecfile = None
        if not (self.opts.devmode and len(args) < 2):
            rspecfile = args[1]
        if rspecfile is None: # FIXME: If file type arg, check the file exists: os.path.isfile(rspecfile) 
            # Dev mode should allow missing RSpec
            msg = 'File of resources to request missing: %s' % rspecfile
            if self.opts.devmode:
                self.logger.warn(msg)
            else:
                self._raise_omni_error(msg)

        try:
            # read the rspec into a string, and add it to the rspecs dict
            rspec = _derefRSpecNick(self, rspecfile)
        except Exception, exc:
            msg = "Unable to read rspec file '%s': %s" % (rspecfile, str(exc))
            if self.opts.devmode:
                rspec = ""
                self.logger.warn(msg)
            else:
                self._raise_omni_error(msg)

        # Test if the rspec is really json containing an RSpec, and
        # pull out the right thing
        rspec = self._maybeGetRSpecFromStruct(rspec)

        # Build args
        op = 'Update'
        options = self._build_options(op, slicename, None)
        urnsarg, slivers = self._build_urns(urn)
        creds = _maybe_add_abac_creds(self.framework, slice_cred)
        creds = self._maybe_add_creds_from_files(creds)
        args = [urnsarg, creds, rspec, options]
        descripMsg = "slivers in slice %s" % urn
        if len(slivers) > 0:
            descripMsg = "%d slivers in slice %s" % (len(slivers), urn)
        self.logger.debug("Doing Update with urns %s, %d creds, rspec starting: \'%s...\', and options %s", urnsarg, len(creds), rspec[:min(40, len(rspec))], options)

        successCnt = 0
        retItem = dict()
        (clientList, message) = self._getclients()
        numClients = len(clientList)
        if numClients == 0:
            msg = "No aggregate specified to submit update request to. Use the -a argument."
            if self.opts.devmode:
                #  warn
                self.logger.warn(msg)
            else:
                self._raise_omni_error(msg)
        elif numClients > 1:
            #  info - mention unbound bits will be repeated
            self.logger.info("Multiple aggregates will get the same request RSpec; unbound requests will be attempted at multiple aggregates.")
            if len(slivers) > 0:
                # All slivers will go to all AMs. If not best effort, AM may fail the request if its
                # not a local sliver.
                #  # FIXME: Could partition slivers by AM URN?
                msg = "Will do %s %s at all %d AMs - some aggregates may fail the request if given slivers not from that aggregate." % (op, descripMsg, numClients)
                if self.opts.geni_best_effort:
                    self.logger.info(msg)
                else:
                    self.logger.warn(msg + " Consider running with --best-effort in future.")

        # Do the command for each client
        for client in clientList:
            self.logger.info("%s %s at %s:", op, descripMsg, client.str)
            try:
                ((result, message), client) = self._api_call(client,
                                    ("%s %s at %s" % (op, descripMsg, client.url)),
                                    op,
                                    args)
            except BadClientException, bce:
                if bce.validMsg and bce.validMsg != '':
                    retVal += bce.validMsg + ". "
                else:
                    retVal += "Skipped aggregate %s. (Unreachable? Doesn't speak AM API v%d? Check the log messages, and try calling 'getversion' to check AM status and API versions supported.).\n" % (client.str, self.opts.api_version)
                if numClients == 1:
                    self._raise_omni_error("\nUpdate failed: " + retVal)
                continue

            # Make the RSpec more pretty-printed
            rspec = None
            if result and isinstance(result, dict) and result.has_key('value') and isinstance(result['value'], dict) and result['value'].has_key('geni_rspec'):
                rspec = result['value']['geni_rspec']
                if rspec and rspec_util.is_rspec_string( rspec, None, None, logger=self.logger ):
                    rspec = rspec_util.getPrettyRSpec(rspec)
                    result['value']['geni_rspec'] = rspec
                else:
                    self.logger.debug("No valid RSpec returned!")
            else:
                self.logger.debug("Return struct missing geni_rspec element!")

            # Pull out the result and check it
            retItem[ client.url ] = result
            (realresult, message) = self._retrieve_value(result, message, self.framework)

            if realresult:
                # Success (maybe partial?)

                missingSlivers = self._findMissingSlivers(realresult, slivers)
                if len(missingSlivers) > 0:
                    self.logger.warn("%d slivers from request missing in result?!", len(missingSlivers))
                    self.logger.debug("Slivers requested missing in result: %s", missingSlivers)

                sliverFails = self._didSliversFail(realresult)
                for sliver in sliverFails.keys():
                    self.logger.warn("Sliver %s reported error: %s", sliver, sliverFails[sliver])

                (header, rspeccontent, rVal) = _getRSpecOutput(self.logger, rspec, slicename, client.urn, client.url, message)
                self.logger.debug(rVal)
                if realresult and isinstance(realresult, dict) and realresult.has_key('geni_rspec') and rspec and rspeccontent:
                    realresult['geni_rspec'] = rspeccontent
                if isinstance(realresult, dict):
                    # Hmm. The rspec content looks OK here. But the
                    # json.dumps seems to screw it up? Quotes get
                    # double escaped.
                    prettyResult = json.dumps(realresult, ensure_ascii=True, indent=2)
                else:
                    prettyResult = pprint.pformat(realresult)

                # Save out the result
#                header="<!-- Update %s at AM URL %s -->" % (descripMsg, client.url)
                filename = None

                if self.opts.output:
                    filename = _construct_output_filename(self.opts, slicename, client.url, client.urn, "update", ".json", numClients)
                    #self.logger.info("Writing result of update for slice: %s at AM: %s to file %s", slicename, client.url, filename)
                _printResults(self.opts, self.logger, header, prettyResult, filename)
                if filename:
                    retVal += "Saved update of %s at AM %s to file %s. \n" % (descripMsg, client.str, filename)
                else:
                    retVal += "Updated %s at %s. \n" % (descripMsg, client.str)

                if len(missingSlivers) > 0:
                    retVal += " - but with %d slivers from request missing in result?! \n" % len(missingSlivers)
                if len(sliverFails.keys()) > 0:
                    retVal += " = but with %d slivers reporting errors. \n" % len(sliverFails.keys())

                # Check the new sliver expirations
                (orderedDates, sliverExps) = self._getSliverExpirations(realresult)
                # None case
                if len(orderedDates) == 1:
                    self.logger.info("All slivers expire on %r", orderedDates[0].isoformat())
                elif len(orderedDates) == 2:
                    self.logger.info("%d slivers expire on %r, the rest (%d) on %r", len(sliverExps[orderedDates[0]]), orderedDates[0].isoformat(), len(sliverExps[orderedDates[0]]), orderedDates[1].isoformat())
                elif len(orderedDates) == 0:
                    msg = " 0 Slivers reported updated!"
                    self.logger.warn(msg)
                    retVal += msg
                else:
                    self.logger.info("%d slivers expire on %r, %d on %r, and others later", len(sliverExps[orderedDates[0]]), orderedDates[0].isoformat(), len(sliverExps[orderedDates[0]]), orderedDates[1].isoformat())
                if len(orderedDates) > 0:
                    if len(orderedDates) == 1:
                        retVal += " All slivers expire on: %s" % orderedDates[0].isoformat()
                    else:
                        retVal += " First sliver expiration: %s" % orderedDates[0].isoformat()

                self.logger.debug("Update %s result: %s" %  (descripMsg, prettyResult))
                if len(missingSlivers) == 0 and len(sliverFails.keys()) == 0:
                    successCnt += 1
            else:
                # Failure
                if message is None or message.strip() == "":
                    message = "(no reason given)"
                retVal += "Update of %s at %s failed: %s.\n" % (descripMsg, client.str, message)
                self.logger.warn(retVal)
                # FIXME: Better message?
        # Done with update call loop over clients

        if numClients == 0:
            retVal += "No aggregates at which to update %s. %s\n" % (descripMsg, message)
        elif numClients > 1:
            retVal += "Updated %s at %d out of %d aggregates.\n" % (descripMsg, successCnt, self.numOrigClients)
        elif successCnt == 0:
            retVal += "Update %s failed at %s" % (descripMsg, clientList[0].url)
        self.logger.debug("Update Return: \n%s", json.dumps(retItem, indent=2))
        return retVal, retItem
    # end of update

# Cancel(urns, creds, options)
# return (like for Describe - see how that is handled):
#   rspec
#   slice urn
#   slivers list
#     urn
#     expires
#     alloc status
#     op status
#     error
# options may include geni_best_effort
    def cancel(self, args):
        """
        GENI AM API Cancel <slice name>
        For use with AM API v3+ only, and only at some AMs. 
        Technically adopted for AM API v4, but may be implemented by v3 AMs. See http://groups.geni.net/geni/wiki/GAPI_AM_API_DRAFT/Adopted#ChangeSetC:Update

        Cancel an Update or Allocate of what is reserved in this slice. For geni_allocated slivers,
        this method acts like Delete. For geni_updating slivers, returns the slivers to the geni_provisioned state and
        the operational state and properties from before the call to Update.

        Return a string summarizing results, and a dictionary by AM URL of the return value from the AM.

        Slice name could be a full URN, but is usually just the slice name portion.
        Note that PLC Web UI lists slices as <site name>_<slice name>
        (e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

        Slice credential is usually retrieved from the Slice Authority. But
        with the --slicecredfile option it is read from that file, if it exists.

        Aggregates queried:
        - If `--useSliceAggregates`, each aggregate recorded at the clearinghouse as having resources for the given slice,
          '''and''' any aggregates specified with the `-a` option.
         - Only supported at some clearinghouses, and the list of aggregates is only advisory
        - Each URL given in an -a argument or URL listed under that given
        nickname in omni_config, if provided, ELSE
        - List of URLs given in omni_config aggregates option, if provided, ELSE
        - List of URNs and URLs provided by the selected clearinghouse

        --sliver-urn / -u option: each specifies a sliver URN whose update or allocate to cancel. If specified, 
        only the listed slivers will be cancelled. Otherwise, all slivers in the slice will be cancelled.
        --best-effort: If supplied, slivers whose update or allocation can be cancelled, will be; some sliver 
        changes may not be cancelled, in which case check the geni_error return for that sliver.
        If not supplied, then if any slivers cannot be cancelled, the whole call fails
        and sliver states do not change.

        Note that some aggregates may require updating all slivers in the same state at the same 
        time, per the geni_single_allocation GetVersion return.

        Output directing options:
        -o Save result in per-Aggregate files
        -p (used with -o) Prefix for resulting files
        --outputfile If supplied, use this output file name: substitute the AM for any %a,
        and %s for any slicename
        If not saving results to a file, they are logged.
        If --tostdout option, then instead of logging, print to STDOUT.

        File names will indicate the slice name, file format, and
        which aggregate is represented.
        e.g.: myprefix-myslice-update-localhost-8001.json

        -V# API Version #
        --devmode: Continue on error if possible
        -l to specify a logging config file
        --logoutput <filename> to specify a logging output filename

        Sample usage:
        Basic cancel of changes at 1 AM in myslice
        omni.py -V3 -a http://myaggregate/url cancel myslice

        Cancel changes in 2 AMs, save results into specificly named files that include an AM name calculated from the AM URL,
        using the slice credential saved in the given file
        omni.py -V3 -a http://myaggregate/url -a http://myother/aggregate -o --outputfile myslice-status-%a.json --slicecredfile mysaved-myslice-slicecred.xml cancel myslice
        """
        if self.opts.api_version < 3:
            if self.opts.devmode:
                self.logger.warn("Trying Cancel with AM API v%d...", self.opts.api_version)
            else:
                self._raise_omni_error("Cancel is only available in AM API v3+. Specify -V3 to use AM API v3.")

        (slicename, urn, slice_cred, retVal, slice_exp) = self._args_to_slicecred(args, 1,
                                                                                  "Cancel")

        creds = _maybe_add_abac_creds(self.framework, slice_cred)
        creds = self._maybe_add_creds_from_files(creds)

        urnsarg, slivers = self._build_urns(urn)

        descripMsg = "changes in slice %s" % urn
        if len(slivers) > 0:
            descripMsg = "changes in %d slivers in slice %s" % (len(slivers), urn)

        args = [urnsarg, creds]
        # Add the options dict
        options = self._build_options('Delete', slicename, None)
        args.append(options)

        self.logger.debug("Doing cancel with urns %s, %d creds, options %r",
                          urnsarg, len(creds), options)

        successCnt = 0
        (clientList, message) = self._getclients()
        numClients = len(clientList)

        # Connect to each available GENI AM
        ## The AM API does not cleanly state how to deal with
        ## aggregates which do not have a sliver in this slice.  We
        ## know at least one aggregate (PG) returns an Exception in
        ## this case.
        ## FIX ME: May need to look at handling of this more in the future.
        ## Also, if the user supplied the aggregate list, a failure is
        ## more interesting.  We can figure out what the error strings
        ## are at the various aggregates if they don't know about the
        ## slice and make those more quiet.  Finally, we can try
        ## to call status at places where it fails to indicate places
        ## where you still have resources.
        op = 'Cancel'
        msg = "Cancel of %s at " % (descripMsg)
        retItem = {}
        for client in clientList:
            try:
                ((result, message), client) = self._api_call(client,
                                                   msg + str(client.url),
                                                   op, args)
            except BadClientException, bce:
                if bce.validMsg and bce.validMsg != '':
                    retVal += bce.validMsg + ". "
                else:
                    retVal += "Skipped aggregate %s. (Unreachable? Doesn't speak AM API v%d? Check the log messages, and try calling 'getversion' to check AM status and API versions supported.).\n" % (client.str, self.opts.api_version)
                if numClients == 1:
                    self._raise_omni_error("\nCancel failed: " + retVal)
                continue

# FIXME: Factor this next chunk into helper method?
            # Decompress the RSpec before sticking it in retItem
            rspec = None
            if result and isinstance(result, dict) and result.has_key('value') and isinstance(result['value'], dict) and result['value'].has_key('geni_rspec'):
                rspec = self._maybeDecompressRSpec(options, result['value']['geni_rspec'])
                if rspec and rspec != result['value']['geni_rspec']:
                    self.logger.debug("Decompressed RSpec")
                if rspec and rspec_util.is_rspec_string( rspec, None, None, logger=self.logger ):
                    rspec = rspec_util.getPrettyRSpec(rspec)
                else:
                    self.logger.warn("Didn't get a valid RSpec!")
                result['value']['geni_rspec'] = rspec
            else:
                self.logger.warn("Got no results from AM %s", client.str)
                self.logger.debug("Return struct missing geni_rspec element!")

            # Return for tools is the full code/value/output triple
            retItem[client.url] = result

            # Get the dict cancel result out of the result (accounting for API version diffs, ABAC)
            (result, message) = self._retrieve_value(result, message, self.framework)
            if not result:
                fmt = "\nFailed to Cancel %s at AM %s: %s\n"
                if message is None or message.strip() == "":
                    message = "(no reason given)"
                retVal += fmt % (descripMsg, client.str, message)
                continue # go to next AM
            else:
                retVal += "\nCancelled %s at AM %s" % (descripMsg, client.str)

            sliverStateErrors = 0
            # FIXME: geni_unallocated or geni_provisioned are both possible new alloc states
            # So querying sliver alloc states would have to get all states and then complain if any are not
            # either of those states.
            sliverStates = self._getSliverAllocStates(result)
            for sliver in sliverStates.keys():
#                self.logger.debug("Sliver %s state: %s", sliver, sliverStates[sliver])
                if sliverStates[sliver] not in ['geni_unallocated', 'geni_provisioned']:
                    self.logger.warn("Sliver %s in wrong state! Expected %s, got %s?!", sliver, 'geni_unallocated ir geni_provisioned', sliverStates[sliver])
                    # FIXME: This really might be a case where sliver in wrong state means the call failed?!
                    sliverStateErrors += 1

            missingSlivers = self._findMissingSlivers(result, slivers)
            if len(missingSlivers) > 0:
                self.logger.warn("%d slivers from request missing in result", len(missingSlivers))
                self.logger.debug("%s", missingSlivers)

            sliverFails = self._didSliversFail(result)
            for sliver in sliverFails.keys():
                self.logger.warn("Sliver %s reported error: %s", sliver, sliverFails[sliver])

            (header, rspeccontent, rVal) = _getRSpecOutput(self.logger, rspec, slicename, client.urn, client.url, message, slivers)
            self.logger.debug(rVal)
            if result and isinstance(result, dict) and result.has_key('geni_rspec') and rspec and rspeccontent:
                result['geni_rspec'] = rspeccontent

            if not isinstance(result, dict):
                # malformed cancel return
                self.logger.warn('Malformed cancel result from AM %s. Expected struct, got type %s.' % (client.str, result.__class__.__name__))
                # FIXME: Add something to retVal that the result was malformed?
                if isinstance(result, str):
                    prettyResult = str(result)
                else:
                    prettyResult = pprint.pformat(result)
            else:
                prettyResult = json.dumps(result, ensure_ascii=True, indent=2)

            #header="<!-- Cancel %s at AM URL %s -->" % (descripMsg, client.url)
            filename = None

            if self.opts.output:
                filename = _construct_output_filename(self.opts, slicename, client.url, client.urn, "cancel", ".json", numClients)
                #self.logger.info("Writing result of cancel for slice: %s at AM: %s to file %s", slicename, client.url, filename)
            else:
                self.logger.info("Result of Cancel: ")
            _printResults(self.opts, self.logger, header, prettyResult, filename)
            if filename:
                retVal += "Saved result of cancel %s at AM %s to file %s. \n" % (descripMsg, client.str, filename)
            # Only count it as success if no slivers were missing
            if len(missingSlivers) == 0 and len(sliverFails.keys()) == 0 and sliverStateErrors == 0:
                successCnt+=1
            else:
                retVal += " - with %d sliver(s) missing and %d sliver(s) with errors and %d sliver(s) in wrong state. \n" % (len(missingSlivers), len(sliverFails.keys()), sliverStateErrors)

        # loop over all clients

        if numClients == 0:
            retVal = "No aggregates specified at which to cancel changes. %s" % message
        elif numClients > 1:
            retVal = "Cancelled changes at %d out of a possible %d aggregates" % (successCnt, self.numOrigClients)
        self.logger.debug("Cancel result: " + json.dumps(retItem, indent=2))
        return retVal, retItem
    # End of cancel

    # End of AM API operations
    #######

    # Non AM API operations at aggregates

    def snapshotimage(self, args):
        '''Call createimage'''
        return self.createimage(args)

    def createimage(self, args):
        '''ProtoGENI's createimage function: snapshot the disk for a
        single sliver (node), giving it the given image name.
        See http://www.protogeni.net/trac/protogeni/wiki/ImageHowTo'''
        # args: sliceURNOrName, sliverURN, imageName, makePublic=True
        # Plus the AM(s) to invoke this at
        # sliver urn from the -U argument
        # So really we just need slice name, imageName, and makePublic
        # This is a PG function, and only expected to work at recent
        # PG AMs

#        # imagename is alphanumeric
#        # note this method returns quick; the experimenter gets an
#        # email later when it is done. In the interval, don't change
#        # anything
#        # Note that if you re-use the name, you replace earlier
#        # content
#        # makePublic is whether the image is available to others;
#        # default is True
#        # sliverURN is the urn of the sliver from the manifest RSpec
#        # whose disk image you are snapshotting

        # prints slice expiration. Warns or raises an Omni error on problems
        (name, sliceURN, slice_cred, retVal, slice_exp) = self._args_to_slicecred(args, 2, "snapshotImage", 
                                "and an image name and optionally makePublic")

        # Extract the single sliver URN. More than one, complain
        urnsarg, slivers = self._build_urns(sliceURN)
        if len(slivers) != 1:
            self._raise_omni_error("CreateImage requires exactly one sliver URN: the sliver containing the node to snapshot.")

        sliverURN = slivers[0]
        if sliverURN:
            sliverURN = sliverURN.strip()
        if not urn_util.is_valid_urn_bytype(sliverURN, 'sliver', self.logger):
            if not self.opts.devmode:
                self._raise_omni_error("Sliver URN invalid: %s" % sliverURN)
            else:
                self.logger.warn("Sliver URN invalid but continuing: %s", sliverURN)

        # Extract the imageName from args
        if len(args) >= 2:
            imageName = args[1]
        else:
            imageName = None
        if not imageName:
            self._raise_omni_error("CreateImage requires a name for the image (alphanumeric)")

        # FIXME: Check that image name is alphanumeric?
        import re
        if not re.match("^[a-zA-Z0-9]+$", imageName):
            if not self.opts.devmode:
                self._raise_omni_error("Image name must be alphanumeric: %s" % imageName)
            else:
                self.logger.warning("Image name must be alphanumeric, but continuing: %s" % imageName)

        # Extract makePublic from args, if present
        makePublic = True
        if len(args) >= 3:
            makePublicString = args[2]
            # 0 or f or false or no, case insensitive, means False
            makePublic = makePublicString.lower() not in ('0', 'f', 'false', 'no')
        if makePublic:
            publicString = "public"
        else:
            publicString = "private"

        creds = _maybe_add_abac_creds(self.framework, slice_cred)
        creds = self._maybe_add_creds_from_files(creds)
        op = "CreateImage"
        options = self._build_options(op, name, None)
        options['global'] = makePublic
        args = (sliceURN, imageName, sliverURN, creds, options)

        retItem = None
        retVal = ""

        (clientList, message) = self._getclients()
        numClients = len(clientList)
        if numClients != 1:
            self._raise_omni_error("CreateImage snapshots a particular machine: specify exactly 1 AM URL with '-a'")
            # FIXME: Note this is already checked in _correctAPIVersion

        client = clientList[0]
        msg = "Create %s Image %s of sliver %s on " % (publicString, imageName, sliverURN)

        self.logger.debug("Doing createimage with slice %s, image %s, sliver %s, %d creds, options %r", sliceURN, imageName, sliverURN, len(creds), options)
        # FIXME: Confirm that AM is PG, complain if not?
        # pgeni gives an error 500 (Protocol Error). PLC gives error
        # 13 (invalid method)
        try:
            ((res, message), client) = self._api_call(client, msg + client.url, op, args)
        except BadClientException, bce:
            if bce.validMsg and bce.validMsg != '':
                retVal += bce.validMsg + ". "
            else:
                retVal += "Skipped aggregate %s. (Unreachable? Doesn't speak AM API v%d? Check the log messages, and try calling 'getversion' to check AM status and API versions supported.).\n" % (client.str, self.opts.api_version)
            self._raise_omni_error("\nCreateImage Failed: " + retVal)

#        self.logger.debug("Doing SSL/XMLRPC call to %s invoking %s with args %r", client.url, op, args)
#        (res, message) = _do_ssl(self.framework, None, msg + client.url, getattr(client, op), *args)

        self.logger.debug("raw result: %r" % res)

        retItem = res
        (realres, message) = self._retrieve_value(res, message, self.framework)

        if not realres:
            # fail
            prStr = "Failed to %s%s" % (msg, client.str)
            if message is None or message.strip() == "":
                message = "(no reason given)"
            if not prStr.endswith('.'):
                prStr += '.'
            prStr += " " + message
            self.logger.warn(prStr)
            retVal += prStr + "\n"
        else:
            # success
            prStr = "Snapshotting disk on %s at %s, creating %s image %s" % (sliverURN, client.str, publicString, res['value'])
            self.logger.info(prStr)
            retVal += prStr

        return retVal, retItem

    def deleteimage(self, args):
        '''ProtoGENI's deleteimage function: Delete the named disk image. 
        Takes an image urn. Optionally supply the URN of the image creator, if that is not you,
        as a second argument.
        Note that you should invoke this at the AM where you created the image - other AMs will return
        a SEARCHFAILED error.
        See http://www.protogeni.net/trac/protogeni/wiki/ImageHowTo'''

        image_urn = None
        creator_urn = None

        # Ensure we got a disk image URN
        if len(args) < 1:
            if not self.opts.devmode:
                self._raise_omni_error("Missing image URN argument to deleteimage")
            else:
                self.logger.warn("Missing image URN argument to deleteimage but continuing")

        if len(args) >= 1:
            image_urn = args[0]
        self.logger.info("DeleteImage using image_urn %r", image_urn)

        # Validate that this looks like an image URN
        if image_urn and not urn_util.is_valid_urn_bytype(image_urn, 'image', self.logger):
            if not self.opts.devmode:
                self._raise_omni_error("Image URN invalid: %s" % image_urn)
            else:
                self.logger.warn("Image URN invalid but continuing: %s", image_urn)

        if len(args) > 1:
            creator_urn = args[1]
            if creator_urn:
                creator_urn = creator_urn.strip()
            if creator_urn == "":
                creator_urn = None
        if creator_urn:
            self.logger.info("Deleteimage using creator_urn %s", creator_urn)
            # If we got a creator urn option
            # Validate it looks like a user urn
            if not urn_util.is_valid_urn_bytype(creator_urn, 'user', self.logger):
                if not self.opts.devmode:
                    self._raise_omni_error("Creator URN invalid: %s" % creator_urn)
                else:
                    self.logger.warn("Creator URN invalid but continuing: %s", image_urn)

        # get the user credential
        cred = None
        message = "(no reason given)"
        if self.opts.api_version >= 3:
            (cred, message) = self.framework.get_user_cred_struct()
        else:
            (cred, message) = self.framework.get_user_cred()
        if cred is None:
            # Dev mode allow doing the call anyhow
            self.logger.error('Cannot deleteimage: Could not get user credential: %s', message)
            if not self.opts.devmode:
                return ("Could not get user credential: %s" % message, dict())
            else:
                self.logger.info('... but continuing')
                cred = ""

        creds = _maybe_add_abac_creds(self.framework, cred)
        creds = self._maybe_add_creds_from_files(creds)

        op = "DeleteImage"
        options = self._build_options(op, None, None)

        # put creator_urn in the options list if we got one
        if creator_urn:
            options['creator_urn'] = creator_urn

        args = (image_urn, creds, options)

        retItem = dict()
        retVal = ""

        # Return value is an XML-RPC boolean 1 (True) on success. Else it uses the AM API to return an error code.
        # EG a SEARCHFAILED "No such image" if the local AM does not have this image.

        (clientList, message) = self._getclients()
        numClients = len(clientList)
        # FIXME: Insist on only 1 AM (user has to know which AM has this image)? Or let user try a bunch of AMs 
        # and just see where it works?
        msg = "Delete Image %s" % (image_urn)
        if creator_urn:
            msg += " created by %s" % (creator_urn)
        msg += " on "

        self.logger.debug("Doing deleteimage with image_urn %s, %d creds, options %r",
                          image_urn, len(creds), options)
        prStr = None
        success = False
        for client in clientList:
            # FIXME: Confirm that AM is PG, complain if not?
            # pgeni gives an error 500 (Protocol Error). PLC gives error
            # 13 (invalid method)
            try:
                ((res, message), client) = self._api_call(client, msg + client.url, op, args)
            except BadClientException, bce:
                if bce.validMsg and bce.validMsg != '':
                    retVal += bce.validMsg + ". "
                else:
                    retVal += "Skipped aggregate %s. (Unreachable? Doesn't speak AM API v%d? Check the log messages, and try calling 'getversion' to check AM status and API versions supported.).\n" % (client.str, self.opts.api_version)
                if numClients == 1:
                    self._raise_omni_error("\nDeleteImage Failed: " + retVal)
                continue

            self.logger.debug("deleteimage raw result: %r" % res)

            retItem[client.url] = res
            (realres, message) = self._retrieve_value(res, message, self.framework)

            if not realres:
                # fail
                prStr = "Failed to %s%s" % (msg, client.str)
                if message is None or message.strip() == "":
                    message = "(no reason given)"
                if not prStr.endswith('.'):
                    prStr += '.'
                prStr += " " + message
                self.logger.warn(prStr)
                #retVal += prStr + "\n"
            else:
                # success
                success = True
                prStr = "Deleted image %s at %s" % (image_urn, client.str)
                self.logger.info(prStr)
                retVal += prStr
                if not self.opts.devmode:
                    # Only expect 1 AM to have this, so quit once we find it
                    break

        if numClients == 0:
            retVal = "Specify at least one aggregate at which to try to delete image %s. %s" % (image_urn, message)
        elif not success:
            retVal = "Failed to delete image %s at any of %d aggregates. Last error: %s" % (image_urn, self.numOrigClients, prStr)
        return retVal, retItem

    def listimages(self, args):
        '''ProtoGENI's ListImages function: List the disk images created by the given user. 
        Takes a user urn or name. If no user is supplied, uses the caller's urn. 
        Gives a list of all images created by that user, including the URN 
        for deleting the image. Return is a list of structs containing the url and urn of the image.
        Note that you should invoke this at the AM where the images were created.
        See http://www.protogeni.net/trac/protogeni/wiki/ImageHowTo

        Output directing options:
        -o Save result in per-Aggregate files
        -p (used with -o) Prefix for resulting files
        --outputfile If supplied, use this output file name: substitute the AM for any %a

        If not saving results to a file, they are logged.
        If --tostdout option is supplied (not -o), then instead of logging, print to STDOUT.

        File names will indicate the user and which aggregate is represented.
        e.g.: myprefix-imageowner-listimages-localhost-8001.json
        '''

        creator_urn = None

        # If we got a creator argument, use it
        if len(args) >= 1:
            creator_urn = args[0]
            self.logger.debug("ListImages got creator_urn %r", creator_urn)

        # get the user credential
        cred = None
        message = "(no reason given by SA)"
        if self.opts.api_version >= 3:
            (cred, message) = self.framework.get_user_cred_struct()
        else:
            (cred, message) = self.framework.get_user_cred()
        if cred is None:
            # Dev mode allow doing the call anyhow
            self.logger.error('Cannot listimages: Could not get user credential: %s', message)
            if not self.opts.devmode:
                return ("Could not get user credential: %s" % message, dict())
            else:
                self.logger.info('... but continuing')
                cred = ""

        creds = _maybe_add_abac_creds(self.framework, cred)
        creds = self._maybe_add_creds_from_files(creds)

        invoker_authority = None
        if cred:
            invoker_urn = credutils.get_cred_owner_urn(self.logger, cred)
            if urn_util.is_valid_urn(invoker_urn):
                iURN = urn_util.URN(None, None, None, invoker_urn)
                invoker_authority = urn_util.string_to_urn_format(iURN.getAuthority())
                self.logger.debug("Got invoker %s with authority %s", invoker_urn, invoker_authority)

        if not creator_urn:
            creator_urn = invoker_urn

        # Validate that this looks like an user URN
        if creator_urn and not urn_util.is_valid_urn_bytype(creator_urn, 'user', self.logger):
            self.logger.debug("Creator_urn %s not valid", creator_urn)
            if invoker_authority:
                test_urn = urn_util.URN(invoker_authority, "user", creator_urn, None)
                if urn_util.is_valid_urn_bytype(test_urn.urn, 'user', self.logger):
                    self.logger.info("Inferred creator urn %s from name %s", test_urn, creator_urn)
                    creator_urn = test_urn.urn
                else:
                    self.logger.debug("test urn using invoker_authority was invalid")
                    if not self.opts.devmode:
                        self._raise_omni_error("Creator URN invalid: %s" % creator_urn)
                    else:
                        self.logger.warn("Creator URN invalid but continuing: %s", creator_urn)
            else:
                self.logger.debug("Had no invoker authority")
                if not self.opts.devmode:
                    self._raise_omni_error("Creator URN invalid: %s" % creator_urn)
                else:
                    self.logger.warn("Creator URN invalid but continuing: %s", creator_urn)

        if urn_util.is_valid_urn(creator_urn) and cred:
            urn = urn_util.URN(None, None, None, creator_urn)
            # Compare creator_urn with invoker urn: must be same SA
            creator_authority = urn_util.string_to_urn_format(urn.getAuthority())
            if creator_authority != invoker_authority:
                if not self.opts.devmode:
                    return ("Cannot listimages: Given creator %s not from same SA as you (%s)" % (creator_urn, invoker_authority), dict())
                else:
                    self.logger.warn("Cannot listimages but continuing: Given creator %s not from same SA as you (%s)" % (creator_urn, invoker_authority))

        self.logger.info("ListImages using creator_urn %r", creator_urn)

        op = "ListImages"
        options = self._build_options(op, None, None)

        args = (creator_urn, creds, options)

        retItem = dict()
        retVal = ""

        # Return value is a list of structs on success. Else it uses the AM API to return an error code.
        # EG a SEARCHFAILED "No such image" if the local AM does not have this image.

        (clientList, message) = self._getclients()
        numClients = len(clientList)
        msg = "List Images created by %s on " % (creator_urn)

        self.logger.debug("Doing listimages with creator_urn %s, %d creds, options %r",
                          creator_urn, len(creds), options)
        prStr = None
        success = False
        for client in clientList:
            # FIXME: Confirm that AM is PG, complain if not?
            # pgeni gives an error 500 (Protocol Error). PLC gives error
            # 13 (invalid method)
            try:
                ((res, message), client) = self._api_call(client, msg + client.url, op, args)
            except BadClientException, bce:
                if bce.validMsg and bce.validMsg != '':
                    retVal += bce.validMsg + ". "
                else:
                    retVal += "Skipped aggregate %s. (Unreachable? Doesn't speak AM API v%d? Check the log messages, and try calling 'getversion' to check AM status and API versions supported.).\n" % (client.str, self.opts.api_version)
                if numClients == 1:
                    self._raise_omni_error("\nListImages Failed: " + retVal)
                continue

            self.logger.debug("listimages raw result: %r" % res)

            retItem[client.url] = res
            (realres, message) = self._retrieve_value(res, message, self.framework)

            if realres is None or realres == 0:
                # fail
                prStr = "Failed to %s%s" % (msg, client.str)
                if message is None or message.strip() == "":
                    message = "(no reason given)"
                if not prStr.endswith('.'):
                    prStr += '.'
                prStr += " " + message
                self.logger.warn(prStr)
                #retVal += prStr + "\n"
            else:
                # success
                success = True
                prettyResult = json.dumps(realres, ensure_ascii=True, indent=2)

                # Save/print out result
                imgCnt = len(realres)
                header="Found %d images created by %s at %s" % (imgCnt, creator_urn, client.str)
                filename = None
                if self.opts.output:
                    creator_name = urn_util.nameFromURN(creator_urn)
                    filename = _construct_output_filename(self.opts, creator_name, client.url, client.urn, "listimages", ".json", numClients)

                _printResults(self.opts, self.logger, header, prettyResult, filename)
                if filename:
                    prStr = "Saved list of images created by %s at AM %s to file %s. \n" % (creator_urn, client.str, filename)
                elif numClients == 1:
                    prStr = "Images created by %s at %s:\n%s" % (creator_urn, client.str, prettyResult)
                else:
                    imgCnt = len(realres)
                    prStr = "Found %d images created by %s at %s. \n" % (imgCnt, creator_urn, client.str)

                retVal += prStr

        if numClients == 0:
            retVal = "Specify at least one valid aggregate at which to try to list images created by %s. %s" % (creator_urn, message)
        elif not success:
            retVal = "Failed to list images created by %s at any of %d aggregates. Last error: %s" % (creator_urn, self.numOrigClients, prStr)
        return retVal, retItem

    def print_sliver_expirations(self, args):
        '''Print the expiration of any slivers in the given slice.
        Return is a string, and a struct by AM URL of the list of sliver expirations.

        Slice name could be a full URN, but is usually just the slice name portion.
        Note that PLC Web UI lists slices as <site name>_<slice name>
        (e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

        Slice credential is usually retrieved from the Slice Authority. But
        with the --slicecredfile option it is read from that file, if it exists.

        --sliver-urn / -u option: each specifies a sliver URN to get status on. If specified, 
        only the listed slivers will be queried. Otherwise, all slivers in the slice will be queried.

        Aggregates queried:
        - If `--useSliceAggregates`, each aggregate recorded at the clearinghouse as having resources for the given slice,
          '''and''' any aggregates specified with the `-a` option.
         - Only supported at some clearinghouses, and the list of aggregates is only advisory
        - Each URL given in an -a argument or URL listed under that given
        nickname in omni_config, if provided, ELSE
        - List of URLs given in omni_config aggregates option, if provided, ELSE
        - List of URNs and URLs provided by the selected clearinghouse

        -V# API Version #
        --devmode: Continue on error if possible
        -l to specify a logging config file
        --logoutput <filename> to specify a logging output filename
        '''
        # for each AM,
        # do sliverstatus or listresources as appropriate and get the sliver expiration,
        # and print that
        # prints slice expiration. Warns or raises an Omni error on problems
        (name, urn, slice_cred, retVal, slice_exp) = self._args_to_slicecred(args, 1, "print_sliver_expirations")

        creds = _maybe_add_abac_creds(self.framework, slice_cred)
        creds = self._maybe_add_creds_from_files(creds)
        (clientList, message) = self._getclients()
        numClients = len(clientList)
        retItem = {}
        for client in clientList:
            # What kind of AM is this? Which function do I call?
            # For now, always use status or sliverstatus
            # Known AMs all do something in status.
            # Of known AMs, FOAM and GRAM do not do manifest, and ION not yet
            sliverstatus = True
            (ver, msg) = self._get_this_api_version(client)
            if not ver:
                self.logger.debug("Error getting API version. Assume 2. Msg: %s", msg)
            else:
                self.logger.debug("%s does API v%d", client.str, ver)
                if ver >= 3:
                    sliverstatus = False
            # Call the function
            if sliverstatus:
                args = [urn, creds]
                options = self._build_options('SliverStatus', name, None)
                if self.opts.api_version >= 2:
                    # Add the options dict
                    args.append(options)
                self.logger.debug("Doing sliverstatus with urn %s, %d creds, options %r", urn, len(creds), options)
                msg = None
                status = None
                try:
                    ((status, message), client) = self._api_call(client,
                                                                 "SliverStatus of %s at %s" % (urn, str(client.url)),
                                                                 'SliverStatus', args)
                    # Get the dict status out of the result (accounting for API version diffs, ABAC)
                    (status, message) = self._retrieve_value(status, message, self.framework)
                except Exception, e:
                    self.logger.debug("Failed to get sliverstatus to get sliver expiration from %s: %s", client.str, e)
                    retItem[client.url] = None

                # Parse the expiration and print / add to retVal
                if status and isinstance(status, dict):
                    exps = expires_from_status(status, self.logger)
                    if len(exps) > 1:
                        # More than 1 distinct sliver expiration found
                        # Sort and take first
                        exps = exps.sort()
                        outputstr = exps[0].isoformat()
                        msg = "Resources in slice %s at AM %s expire at %d different times. First expiration is %s UTC" % (name, client.str, len(exps), outputstr)
                    elif len(exps) == 0:
                        msg = "Failed to get sliver expiration from %s" % client.str
                        self.logger.debug("Failed to parse a sliver expiration from status")
                    else:
                        outputstr = exps[0].isoformat()
                        msg = "Resources in slice %s at AM %s expire at %s UTC" % (name, client.str, outputstr)
                    retItem[client.url] = exps
                else:
                    retItem[client.url] = None
                    msg = "Malformed or failed to get status from %s, cannot find sliver expiration" % client.str
                    if message is None or message.strip() == "":
                        if status is None:
                            message = "(no reason given, missing result)"
                        elif status == False:
                            message = "(no reason given, False result)"
                        elif status == 0:
                            message = "(no reason given, 0 result)"
                        else:
                            message = "(no reason given, empty result)"
                        # FIXME: If this is PG and code 12, then be nicer here.
                    if message:
                        msg += " %s" % message
                    if message and "protogeni AM code: 12: No slice or aggregate here" in message:
                        # PG says this AM has no resources here
                        msg = "No resources at %s in slice %s" % (client.str, name)
                        self.logger.debug("AM %s says: %s", client.str, message)
                if msg:
                    self.logger.info(msg)
                    retVal += msg + ".\n "
            else:
                # Doing APIv3
                urnsarg, slivers = self._build_urns(urn)
                args = [urnsarg, creds]
                # Add the options dict
                options = self._build_options('Status', name, None)
                args.append(options)
                self.logger.debug("Doing status with urns %s, %d creds, options %r", urnsarg, len(creds), options)
                descripMsg = "slivers in slice %s" % urn
                if len(slivers) > 0:
                    descripMsg = "%d slivers in slice %s" % (len(slivers), urn)

                msg = None
                status = None
                try:
                    ((status, message), client) = self._api_call(client,
                                                                 "Status of %s at %s" % (urn, str(client.url)),
                                                                 'Status', args)
                    # Get the dict status out of the result (accounting for API version diffs, ABAC)
                    (status, message) = self._retrieve_value(status, message, self.framework)
                except Exception, e:
                    self.logger.debug("Failed to get status to get sliver expiration from %s: %s", client.str, e)
                    retItem[client.url] = None

                if not status:
                    retItem[client.url] = None

                    if message and "protogeni AM code: 12: No such slice here" in message:
                        # PG says this AM has no resources here
                        msg = "No resources at %s in slice %s" % (client.str, name)
                        self.logger.debug("AM %s says: %s", client.str, message)
                        self.logger.info(msg)
                        retVal += msg + ".\n "
                    else:
                        # FIXME: Put the message error in retVal?
                        # FIXME: getVersion uses None as the value in this case. Be consistent
                        fmt = "\nFailed to get Status on %s at AM %s: %s\n"
                        if message is None or message.strip() == "":
                            message = "(no reason given)"
                        retVal += fmt % (descripMsg, client.str, message)
                    continue

                # Summarize sliver expiration
                (orderedDates, sliverExps) = self._getSliverExpirations(status, None)
                retItem[client.url] = orderedDates
                if len(orderedDates) == 1:
                    msg = "Resources in slice %s at AM %s expire at %s UTC" % (name, client.str, orderedDates[0])
                elif len(orderedDates) == 0:
                    msg = "0 Slivers reported results!"
                else:
                    firstTime = orderedDates[0]
                    firstCount = len(sliverExps[firstTime])
                    msg = "Resources in slice %s at AM %s expire at %d different times. First expiration is %s UTC (%d slivers), and other slivers at %d different times." % (name, client.str, len(orderedDates), firstTime, firstCount, len(orderedDates) - 1)
                if msg:
                    self.logger.info(msg)
                    retVal += msg + ".\n "
            # End of block to handle APIv3 AM
        # End of loop over AMs

        if numClients == 0:
            retVal = "No aggregates specified on which to get sliver expirations in slice %s. %s" % (name, message)
        elif numClients > 1:
            soonest = None
            for client in clientList:
                thisAM = retItem[client.url]
                if thisAM and len(thisAM) > 0:
                    nextTime = thisAM[0]
                    if nextTime:
                        if soonest is None or nextTime < soonest[0]:
                            soonest = (nextTime, client.str)
            if soonest:
                retVal += "First resources expire at %s (UTC) at AM %s.\n" % (soonest[0], soonest[1])
        return retVal, retItem
    # End of print_sliver_expirations

    #######

    # Helper functions follow

    def _checkValidClient(self, client):
        '''Confirm this AM speaks the right AM API version. 
        Return the API version spoken by this AM, and a client object to talk to it.
        In particular, the returned client may be different, if the AM you asked about advertised
        a different URL as supporting your desired API Version.
        Check for None client to indicate an error, so you can bail.'''

        # Use the GetVersion cache
        # Make sure the client we are talking to speaks the expected AM API (or claims to)
        # What else would this do? See if it is reachable? We'll do that elsewhere

        cver, message = self._get_this_api_version(client)
        if isinstance(cver, str):
            self.logger.warn("AM %s reported a string API version %s", client.url, cver)
            cver = int(cver)
        configver = self.opts.api_version
        if cver and cver == configver:
            return (cver, client, None)
        elif not cver:
            self.logger.debug("_checkValidClient got message %s", message)
            if "Operation timed out" in message:
                message = message[message.find("Operation timed out"):]
            elif "Unknown socket error" in message:
                message = message[message.find("Unknown socket error"):]
            elif "Server does not trust" in message:
                message = message[message.find("Server does not trust"):]
            elif "Your user certificate" in message:
                message = message[message.find("Your user certificate"):]
            self.logger.debug("Got no api_version from getversion at %s? %s" % (client.url, message))
            msg = "Error contacting %s: %s" % (client.url, message)
            self.logger.warn(msg)
            if not self.opts.devmode:
                self.logger.warn("... skipping this aggregate")
                return (0, None, msg + " ... skipped this aggregate")
            else:
                self.logger.warn("... but continuing with requested version and client")
                return (configver, client, msg + " ... but continued with requested version and client")

        # This AM doesn't speak the desired API version - see if there's an alternate
        svers, message = self._get_api_versions(client)
        if svers:
            if svers.has_key(str(configver)):
                msg = "Requested API version %d, but AM %s uses version %d. Same aggregate talks API v%d at a different URL: %s" % (configver, client.url, cver, configver, svers[str(configver)])
                self.logger.warn(msg)
                # do a makeclient with the corrected URL and return that client?
                if not self.opts.devmode:
                    try:
                        newclient = make_client(svers[str(configver)], self.framework, self.opts)
                    except Exception, e:
                        self.logger.debug(" - but that URL appears invalid: '%s'" % e)
                        self.logger.warn(" -- Cannot connect to that URL, skipping this aggregate")
                        retmsg = "Skipped AM %s: it claims to speak API v%d at a broken URL (%s)." % (client.url, configver, svers[str(configver)])
                        return (configver, None, retmsg)
                    newclient.urn = client.urn # Wrong urn?
                    newclient.nick = _lookupAggNick(self, newclient.url)
                    if newclient.nick:
                        if self.opts.devmode:
                            newclient.str = "%s (%s)" % (newclient.nick, newclient.url)
                        else:
                            newclient.str = newclient.nick
                    else:
                        newclient.str = newclient.url
                    (ver, c, msg2) = self._checkValidClient(newclient)
                    if ver == configver and c.url == newclient.url and c is not None:
                        self.logger.info("Switching AM URL to match requested version")
                        return (ver, c, "Switched AM URL from %s to %s to speak AM API v%d as requested" % (client.url, c.url, configver))
                    else:
                        self.logger.warn("... skipping this aggregate - failed to get a connection to the AM URL with the right version")
                        return (configver, None, "Skipped AM %s: failed to get a connection to %s which supports APIv%d as requested" % (client.url, newclient.url, configver))
                else:
                    self.logger.warn("... but continuing with requested version and client")
                    return (configver, client, msg + ", but continued with URL and version as requested")
            else:
                if len(svers.keys()) == 1:
                    msg = "Requested API version %d, but AM %s only speaks version %d. Try running Omni with -V%d." % (configver, client.url, cver, cver)
                    retmsg = msg
                else:
                    msg = "Requested API version %d, but AM %s uses version %d. This aggregate does not talk your requested version. It advertises: %s. Try running Omni with -V<one of the advertised versions>." % (configver, client.url, cver, pprint.pformat(svers.keys()))
                    retmsg = "Requested API version %d, but AM %s uses version %d. Try running Omni with -V%s" % (configver, client.url, cver, pprint.pformat(svers.keys()))
                self.logger.warn(msg)
                # FIXME: If we're continuing, change api_version to be correct, or we will get errors
                if not self.opts.devmode:
#                    self.logger.warn("Changing to use API version %d", cver)
                    self.logger.warn("... skipping this aggregate")
                    retmsg += " Skipped this aggregate"
                    return (cver, None, retmsg)
                else:
                    # FIXME: Pick out the max API version supported at this client, and use that?
                    self.logger.warn("... but continuing with requested version and client")
                    return (configver, client, retmsg + " Continued with URL as requested.")
        else:
            msg = "Requested API version %d, but AM %s advertises only version %d. Try running Omni with -V%d." % (configver, client.url, cver, cver)
            self.logger.warn(msg)
            # FIXME: If we're continuing, change api_version to be correct, or we will get errors
            if not self.opts.devmode:
#                self.logger.warn("Changing to use API version %d", cver)
                self.logger.warn("... skipping this aggregate")
                return (cver, None, msg + " ... skipped this Aggregate")
            else:
                self.logger.warn("... but continuing with requested version and client")
                return (configver, client, msg + " ... but continued with URL as requested")
                #self.logger.warn("... skipping this aggregate")
                #return (cver, None, msg)
        # Shouldn't get here...
        self.logger.warn("Cannot validate client ... skipping this aggregate")
        return (cver, None, ("Could not validate AM %s .. skipped" % client.str))
    # End of _checkValidClient

    def _maybeGetRSpecFromStruct(self, rspec):
        '''RSpec might be string of JSON, in which case extract the
        XML out of the struct.'''
        if rspec is None:
            self._raise_omni_error("RSpec is empty")

        if "'geni_rspec'" in rspec or "\"geni_rspec\"" in rspec or '"geni_rspec"' in rspec:
            try:
                rspecStruct = json.loads(rspec, encoding='ascii', cls=DateTimeAwareJSONDecoder, strict=False)
                if rspecStruct and isinstance(rspecStruct, dict) and rspecStruct.has_key('geni_rspec'):
                    rspec = rspecStruct['geni_rspec']
                    if rspec is None:
                        self._raise_omni_error("Malformed RSpec: 'geni_rspec' empty in JSON struct")
            except Exception, e:
                import traceback
                msg = "Failed to read RSpec from JSON text %s: %s" % (rspec[:min(60, len(rspec))], e)
                self.logger.debug(traceback.format_exc())
                if self.opts.devmode:
                    self.logger.warn(msg)
                else:
                    self._raise_omni_error(msg)

        # If \" in rspec then make that "
        rspec = string.replace(rspec, "\"", '"')
        # If \n in rspec then remove that
        rspec = string.replace(rspec, "\\n", " ")
#        rspec = string.replace(rspec, '\n', ' ')
        return rspec

    def _get_users_arg(self, sliceName):
        '''Get the users argument for SSH public keys to install.
        These keys are used in createsliver, provision, and poa geni_update_users.
        Keys may come from the clearinghouse list of slice members, and from the omni_config 'users' section.
        Commandline options enable/disable each source. The set of users and keys is unioned.'''

        # Return is a list of dicts
        # Each dict has 2 keys: 'urn' and 'keys'
        # 'keys' is a list of strings - the value of the keys
        slice_users = []


        # First get slice members & keys from the CH
        if self.opts.useSliceMembers and not self.opts.noExtraCHCalls:
            self.logger.debug("Getting users and SSH keys from the Clearinghouse list of slice members")
            sliceMembers = []
            mess = None
            try:
                # Return is a list of dicts with 'URN', 'EMAIL', and 'KEYS' (which is a list of keys or None)
                (sliceMembers, mess) = self.framework.get_members_of_slice(sliceName)
                if not sliceMembers:
                    self.logger.debug("Got empty sliceMembers list for slice %s: %s", sliceName, mess)
            except Exception, e:
                self.logger.debug("Failed to get list of slice members for slice %s: %s", sliceName, e)

            if sliceMembers:
                for member in sliceMembers:
                    if not (member.has_key('URN') and member.has_key('KEYS')):
                        self.logger.debug("Skipping malformed member %s", member)
                        continue
                    found = False
                    for user in slice_users:
                        if user['urn'] == member['URN']:
                            found = True
                            if member['KEYS'] is None:
                                self.logger.debug("CH had no keys for member %s", member['URN'])
                                break
                            for mkey in member['KEYS']:
                                if mkey.strip() in user['keys']:
                                    continue
                                else:
                                    user['keys'].append(mkey.strip())
                                    self.logger.debug("Adding a CH key for member %s", member['URN'])
                            # Done unioning keys for existing user
                            break
                    # Done searching for existing user
                    if not found:
                        nmember = dict()
                        nmember['urn'] = member['URN']
                        nmember['keys'] = []
                        if member['KEYS'] is not None:
                            for key in member['KEYS']:
                                nmember['keys'].append(key.strip())
                        slice_users.append(nmember)
                # Done looping of slice members
            # Done if got sliceMembers
            self.logger.debug("From Clearinghouse got %d users whose SSH keys will be set", len(slice_users))
        # Done block to fetch users from CH
        else:
            if self.opts.useSliceMembers and self.opts.noExtraCHCalls:
                self.logger.debug("Per config not doing extra Clearinghouse calls, including looking up slice members")
            elif not self.opts.useSliceMembers:
                self.logger.debug("Did not request to get slice members' SSH keys")

        if not self.opts.ignoreConfigUsers:
            self.logger.debug("Reading users and keys to install from your omni_config")
            # Copy the user config and read the keys from the files into the structure
            slice_users2 = copy(self.config['users'])
            if len(slice_users) == 0 and len(slice_users2) == 0:
                self.logger.warn("No users defined. No keys will be uploaded to support SSH access.")
                return slice_users

            for user in slice_users2:
                newkeys = []
                required = ['urn', 'keys']
                for req in required:
#--- Dev vs Exp: allow this in dev mode:
                    if not req in user:
                        msg = "%s in omni_config is not specified for user %s" % (req,user)
                        if self.opts.devmode:
                            self.logger.warn(msg)
                        else:
                            self._raise_omni_error(msg)
#---
                if user.has_key('keys'):
                    for key in user['keys'].split(','):
                        try:
                            newkeys.append(file(os.path.expanduser(key.strip())).read().strip())
                        except Exception, exc:
                            self.logger.error("Failed to read user key from %s: %s" %(user['keys'], exc))
                    user['keys'] = newkeys
                if len(newkeys) == 0:
                    uStr = ""
                    if user.has_key('urn'):
                        uStr = user['urn']
                    self.logger.warn("Empty keys for user %s", uStr)
                else:
                    uStr = ""
                    if user.has_key('urn'):
                        uStr = "User %s " % user['urn']
                    self.logger.debug("%sNewkeys: %r...", uStr, str(newkeys)[:min(160, len(str(newkeys)))])

                # Now merge this into the list from above
                found = False
                for member in slice_users:
                    if not user.has_key('urn'):
                        if not member.has_key('urn'):
                            found = True
                    elif member.has_key('urn') and user['urn'] == member['urn']:
                        found = True
                    if found:
                        if user.has_key('keys'):
                            if not member.has_key('keys'):
                                member['keys'] = []
                            for key in user['keys']:
                                if key.strip() not in member['keys']:
                                    member['keys'].append(key.strip())
                        break
                if not found:
                    slice_users.append(user)
            # Done looping over users defined in the omni_config
            self.logger.debug("After reading omni_config, %d users will have SSH keys set", len(slice_users))
        else:
            self.logger.debug("Requested to ignore omni_config users and SSH keys")

#        if len(slice_users) < 1:
#            self.logger.warn("No user keys found to be uploaded")
        return slice_users
    # End of _get_users_arg

    def _retrieve_value(self, result, message, framework):
        '''Extract ABAC proof and creds from the result if any.
        Then pull the actual value out, checking for errors.
        Returned message includes a string representation of any error code/output.
        '''
        # Existing code is inconsistent on whether it is if code or elif code.
        # IE is the whole code struct shoved inside the success thing maybe?
        if not result:
            self.logger.debug("Raw result from AM API call was %s?!", result)
            if not message or message.strip() == "":
                message = "(no reason given)"
            if result is None:
                message += " (missing result)"
            elif result == False:
                message += " ('False' result)"
            elif result == 0:
                message += " ('0' result)"
            else:
                message += " (empty result)"
            return (result, message)

        value = result
        # If ABAC return is a dict with proof and the regular return
        if isinstance(result, dict):
            if is_ABAC_framework(framework):
                if 'proof' in result:
                    save_proof(framework.abac_log, result['proof'])
                    # XXX: may not need to do delete the proof dict entry
                    # This was only there for SliverStatus, where the return is already a dict
                    del result['proof']
                if 'abac_credentials' in result:
                    save_abac_creds(result['abac_credentials'],
                                    framework.abac_dir)
                # For ListR and CreateS
                if 'manifest' in result:
                    value = result['manifest']
                # For Renew, Delete, Shutdown
                elif 'success' in result:
                    value = result['success']

            # FIXME Should that be if 'code' or elif 'code'?
            # FIXME: See _check_valid_return_struct
            if 'code' in result and isinstance(result['code'], dict) and 'geni_code' in result['code']:
                # AM API v2+
                if result['code']['geni_code'] == 0:
                    value = result['value']
                    if value is None:
                        self.logger.warn("Result claimed success but value is empty!")
                        if result['code'].has_key('am_code'):
                            if not message or message.strip() == "":
                                message = "(no reason given)"
                            amtype = ""
                            if result['code'].has_key('am_type'):
                                amtype = result['code']['am_type']
                            message += " (AM return code %s:%d)" % (amtype, result['code']['am_code'])

                    # If this is pg then include the pg log urn/url in
                    # the message even on success when in debug mode
                    # But problem: callers swallow the message if it
                    # looks like success. So log this at info.
                    # The result here is that this is logged only on
                    # success, not on error.
                    msg = _get_pg_log(result)
                    if not message and msg != "":
                        message = ""
                    if msg != "":
#                        # Force this log URL to be logged even if we're at WARN log level? That's noisy
#                        if not self.logger.isEnabledFor(logging.INFO):
#                            self.logger.warn(msg)
#                        else:
                        self.logger.info(msg)
                        # FIXME: This may cause pg_log to be included in result summary even in success
#                        message += msg

                # FIXME: More complete error code handling!
                elif self.opts.raiseErrorOnV2AMAPIError and result['code']['geni_code'] != 0 and self.opts.api_version == 2:
                    # Allow scripts to get an Error raised if any
                    # single AM returns a failure error code.
                    # note it means any other AMs do not get processed
                    # FIXME: AMAPIError needs a nice printable string
                    self._raise_omni_error(message, AMAPIError, result)
                else:
                    message = _append_geni_error_output(result, message)
                    value = None
            else:
                # No code in result
                if self.opts.api_version > 1:
                    # This happens doing getversion at a v1 AM.
                    if isinstance(result, dict) and result.has_key('geni_api') and result['geni_api'] == 1:
                        pass
                    else:
                        self.logger.warn("Result had no code!")
        else:
            # Not a dict response. Value is result in itself
            if self.opts.api_version > 1:
                self.logger.warn("Result was not a dict!")
        return (value, message)
    # End of _retrieve_value

    def _args_to_slicecred(self, args, num_args, methodname, otherargstring=""):
        '''Confirm got the specified number of arguments. First arg is taken as slice name.
        Try to get the slice credential. Check it for expiration and print the expiration date.
        Raise an OmniError on error, unless in devmode, when we just log a warning.
        '''
#- pull slice name
#- get urn
#- get slice_cred
#- check expiration
#- get printout of expiration
#- if orca_id reset urn
#- return name, urn, slice_cred, retVal, slice_exp
#users: SliverStatus, CreateSliver, Describe, renewSliver, DeleteSliver,

        if num_args < 1:
            return ("", "", "", "", datetime.datetime.max)

        # If we had no args or not enough
        if len(args) == 0 or len(args) < num_args or (len(args) >=1 and (args[0] == None or args[0].strip() == "")):
            msg = '%s requires arg of slice name %s' % (methodname, otherargstring)
            if self.opts.devmode:
                self.logger.warn(msg + ", but continuing...")
                if len(args) == 0 or (len(args) >=1 and (args[0] == None or args[0].strip() == "")):
                    return ("", "", "", "", datetime.datetime.max)
            else:
                self._raise_omni_error(msg)

        name = args[0]

        # FIXME: catch errors getting slice URN to give prettier error msg?
        urn = self.framework.slice_name_to_urn(name)

        # Get a slice cred, handle it being None
        (slice_cred, message) = _get_slice_cred(self, urn)

        # Unwrap the slice cred if it is wrapped and this is an API < 3
        if self.opts.api_version < 3 and slice_cred is not None:
            slice_cred = get_cred_xml(slice_cred)
            if slice_cred is None:
                message = "No valid SFA slice credential returned"

        if slice_cred is None:
            msg = 'Cannot do %s for %s: Could not get slice credential: %s' % (methodname, urn, message)
            if self.opts.devmode:
                slice_cred = ""
                self.logger.warn(msg + ", but continuing....")
            else:
                self._raise_omni_error(msg, NoSliceCredError)

        # FIXME: Check that the returned slice_cred is actually for the given URN?
        # Or maybe do that in _get_slice_cred?

        # Check for an expired slice
        slice_exp = None
        expd = True
        if not self.opts.devmode or slice_cred != "":
            expd, slice_exp = self._has_slice_expired(slice_cred)
        if slice_exp is None:
            slice_exp = datetime.datetime.min
        if expd:
            msg = 'Cannot do %s for slice %s: Slice has expired at %s' % (methodname, urn, slice_exp.isoformat())
            if self.opts.devmode:
                self.logger.warn(msg + ", but continuing...")
            else:
                self._raise_omni_error(msg)

        retVal = ""
        if not self.opts.devmode or slice_cred != "":
            retVal = _print_slice_expiration(self, urn, slice_cred) + "\n"

        if self.opts.orca_slice_id:
            self.logger.info('Using ORCA slice id %r', self.opts.orca_slice_id)
            urn = self.opts.orca_slice_id
        return name, urn, slice_cred, retVal, slice_exp
    # End of _args_to_slicecred

    def _raise_omni_error( self, msg, err=OmniError, triple=None ):
        msg2 = msg
        if triple is not None:
            msg2 += " "
            msg2 += str(triple)
        self.logger.error( msg2 )
        if triple is None:
            raise err, msg
        else: 
            raise err, (msg, triple)

    def _has_slice_expired(self, sliceCred):
        """Return (boolean, expiration datetime) whether given slicecred (string) has expired)"""
        if sliceCred is None:
            return (True, None)
        sliceexp = credutils.get_cred_exp(self.logger, sliceCred)
        sliceexp = naiveUTC(sliceexp)
        now = datetime.datetime.utcnow()
        if sliceexp <= now:
            return (True, sliceexp)
        return (False, sliceexp)

    def _getclients(self):
        """Create XML-RPC clients for each aggregate (from commandline,
        else from config file, else from framework)
        Return them as a sequence.
        Each client has a urn and url. See handler_utils._listaggregates for details.
        """
        if self.clients is not None:
            return (self.clients, "")

        self.clients = []
        self.numOrigClients = 0
        (aggs, message) = _listaggregates(self)
        if aggs == {} and message != "":
            self.logger.warn('No aggregates found: %s', message)
            return (self.clients, message)
        if message == "From CH":
            self.logger.info("Acting on all aggregates from the clearinghouse - this may take time")
        for (urn, url) in aggs.items():
            client = make_client(url, self.framework, self.opts)
            client.urn = urn
            client.nick = _lookupAggNick(self, url)
            clstr = client.url
            if client.nick:
                if self.opts.devmode:
                    clstr = "%s (%s)" % (client.nick, client.url)
                else:
                    clstr = client.nick
            client.str = clstr
            self.clients.append(client)
        self.numOrigClients = len(self.clients)
        return (self.clients, message)

    def _build_urns(self, slice_urn):
        '''Build up the URNs argument, using given slice URN and the option sliver-urn, if present.
        Only gather sliver URNs if they are valid.
        If no sliver URNs supplied, list is the slice URN.
        If sliver URNs were supplied but all invalid, raise an error.
        Return the urns list for the arg, plus a separate list of the valid slivers.'''
        urns = list()
        slivers = list()

        # FIXME: Check that all URNs are for same AM?
        if self.opts.slivers and len(self.opts.slivers) > 0:
            for sliver in self.opts.slivers:
                if not urn_util.is_valid_urn_bytype(sliver, 'sliver', self.logger):
                    self.logger.warn("Supplied sliver URN %s - not a valid sliver URN.", sliver)
                    if self.opts.devmode:
                        urns.append(sliver)
                        slivers.append(sliver)
                    else:
                        self.logger.warn("... skipping")
                else:
#                    self.logger.debug("Adding sliver URN %s", sliver)
                    urns.append(sliver)
                    slivers.append(sliver)
            if len(urns) == 0:
                # Error - got no slivers to operate on
                msg = "No valid sliver URNs found, from %d supplied." % len(self.opts.slivers)
                if self.opts.devmode:
                    self.logger.warn(msg)
                else:
                    self._raise_omni_error(msg)
        elif len(urns) == 0:
            urns.append(slice_urn)
        return urns, slivers

    # slicename included just to pass on to datetimeFromString
    def _build_options(self, op, slicename, options):
        '''Add geni_best_effort and geni_end_time and geni_start_time to options if supplied, applicable'''
        if self.opts.api_version == 1 and op != 'ListResources':
            return None
        if not options or options is None:
            options = {}

        if self.opts.api_version >= 3 and self.opts.geni_end_time:
            if op in ('Allocate', 'Provision', 'Update') or self.opts.devmode:
                if self.opts.devmode and not op in ('Allocate', 'Provision', 'Update'):
                    self.logger.warn("Got geni_end_time for method %s but using anyhow", op)
                time = datetime.datetime.max
                try:
                    # noSec=True so that fractional seconds are dropped (which can break at PG AMs, or could)
                    (time, time_with_tz, time_string) = self._datetimeFromString(self.opts.geni_end_time, name=slicename, noSec=True)
                    options["geni_end_time"] = time_string
                except Exception, exc:
                    msg = 'Couldnt parse geni_end_time from %s: %r' % (self.opts.geni_end_time, exc)
                    self.logger.warn(msg)
                    if self.opts.devmode:
                        self.logger.info(" ... passing raw geni_end_time")
                        options["geni_end_time"] = self.opts.geni_end_time

        if self.opts.api_version >= 3 and self.opts.geni_start_time:
            if op in ('Allocate') or self.opts.devmode:
                if self.opts.devmode and not op in ('Allocate'):
                    self.logger.warn("Got geni_start_time for method %s but using anyhow", op)
                time = datetime.datetime.min
                try:
                    # noSec=True so that fractional seconds are dropped
                    (time, time_with_tz, time_string) = self._datetimeFromString(self.opts.geni_start_time, name=slicename, noSec=True)
                    options['geni_start_time'] = time_string
                except Exception, exc:
                    msg = 'Couldnt parse geni_start_time from %s: %r' % (self.opts.geni_start_time, exc)
                    self.logger.warn(msg)
                    if self.opts.devmode:
                        self.logger.info(" ... passing raw geni_start_time")
                        options["geni_start_time"] = self.opts.geni_start_time

        if self.opts.api_version >= 3 and self.opts.geni_best_effort:
            # FIXME: What about Describe? Status?
            if op in ('Provision', 'Renew', 'Delete', 'PerformOperationalAction', 'Cancel'):
                options["geni_best_effort"] = self.opts.geni_best_effort
            elif self.opts.devmode:
                self.logger.warn("Got geni_best_effort for method %s but using anyhow", op)
                options["geni_best_effort"] = self.opts.geni_best_effort

        # For Update. See http://groups.geni.net/geni/wiki/GAPI_AM_API_DRAFT/Adopted#ChangestoDescribe
        if self.opts.api_version >= 3 and self.opts.cancelled and op == 'Describe':
            options["geni_cancelled"] = self.opts.cancelled
        elif self.opts.devmode and self.opts.cancelled:
            self.logger.warn("Got cancelled option for method %s but using anhow", op)
            options["geni_cancelled"] = self.opts.cancelled

        # To support Speaks For, allow specifying the URN of the user
        # the tool is speaking for. 
        if self.opts.speaksfor:
            options["geni_speaking_for"] = self.opts.speaksfor

        if self.opts.api_version > 1 and self.opts.alap:
            if op in ('Renew', 'RenewSliver'):
                options["geni_extend_alap"] = self.opts.alap
            elif self.opts.devmode:
                self.logger.warn("Got geni_extend_alap option for method %s that doesn't take it, but using anyhow", op)
                options["geni_extend_alap"] = self.opts.alap

        # To support all the methods that take arbitrary options,
        # allow specifying a JSON format file that specifies
        # name/value pairs, with values of various types.
        # Note that options here may over-ride other options.
        # Sample options file content:
#{
# "option_name_1": "value",
# "option_name_2": {"complicated_dict" : 37},
# "option_name_3": 67
#}
        if self.opts.optionsfile:
            if not (os.path.exists(self.opts.optionsfile) and os.path.getsize(self.opts.optionsfile) > 0):
                msg = "Options file %s doesn't exist or is not readable" % self.opts.optionsfile
                if self.opts.devmode:
                    self.logger.warn(msg)
                else:
                    self._raise_omni_error(msg)

            try:
                optionsStruct = None
                with open(self.opts.optionsfile, 'r') as optsfp:
                    # , encoding='ascii', cls=DateTimeAwareJSONDecoder, strict=False)
                    optionsStruct = json.load(optsfp)
                self.logger.debug("options read from file: %s", optionsStruct)
                if optionsStruct and isinstance(optionsStruct, dict) and len(optionsStruct.keys()) > 0:
                    for name, value in optionsStruct.iteritems():
                        self.logger.debug("Adding option %s=%s", name, value)
                        options[name] = value
            except Exception, e:
                import traceback
                msg = "Failed to read options from JSON-format file %s: %s" % (self.opts.optionsfile, e)
                self.logger.debug(traceback.format_exc())
                if self.opts.devmode:
                    self.logger.warn(msg)
                else:
                    self._raise_omni_error(msg)

        return options

    def _getSliverResultList(self, resultValue):
        '''Pull the list of sliver-specific results from the input'''
        # resultValue could be a list of dicts with keys geni_sliver_urn and geni_error (Delete, poa, Renew)
        # OR dict containing the key geni_slivers, which is then the above list (Status, Provision, Describe
        # Note allocate does not return the geni_error key - otherwise it is like status/provision)
        if not resultValue:
            self.logger.debug("Result value empty")
            return list()
        if isinstance(resultValue, dict):
            if resultValue.has_key('geni_slivers'):
                resultValue = resultValue['geni_slivers']
            else:
                self.logger.debug("Result value had no 'geni_slivers' key")
                return list()
        if not isinstance(resultValue, list) or len(resultValue) == 0:
            self.logger.debug("Result value not a list or empty")
            return list()
        return resultValue

    def _getSliverStatuses(self, resultValue):
        '''Summarize the allocation and operational statuses in a list of 2 hashes by state name'''
        op_statuses = dict()
        alloc_statuses = dict()

        resultValue = self._getSliverResultList(resultValue)
        if len(resultValue) == 0:
            self.logger.debug("Result value not a list or empty")

        for sliver in resultValue:
            sliverUrn = ''
            if not isinstance(sliver, dict):
                self.logger.debug("entry in result list was not a dict")
                continue
            if not sliver.has_key('geni_sliver_urn') or str(sliver['geni_sliver_urn']).strip() == "":
                self.logger.debug("entry in result had no 'geni_sliver_urn'")
            else:
                sliverUrn = sliver['geni_sliver_urn']
            if not sliver.has_key('geni_allocation_status') or str(sliver['geni_allocation_status']).strip() == "":
                self.logger.debug("Sliver %s had no allocation status", sliverUrn)
            else:
                aStat = sliver['geni_allocation_status']
                if aStat in alloc_statuses:
                    alloc_statuses[aStat] += 1
                else:
                    alloc_statuses[aStat] = 1
            if not sliver.has_key('geni_operational_status') or str(sliver['geni_operational_status']).strip() == "":
                self.logger.debug("Sliver %s had no operational status", sliverUrn)
            else:
                oStat = sliver['geni_operational_status']
                if oStat in op_statuses:
                    op_statuses[oStat] += 1
                else:
                    op_statuses[oStat] = 1
        return (alloc_statuses, op_statuses)

    def _didSliversFail(self, resultValue):
        '''Take a result value, and return a dict of slivers that had a geni_error: URN->geni_error'''
        # Used by Describe, Renew, Provision, Status, PerformOperationalAction, Delete
#        sliverFails = self._didSliversFail(realresult)
#        for sliver in sliverFails.keys():
#            self.logger.warn("Sliver %s reported error: %s", sliver, sliverFails[sliver])
#            # FIXME: Add to retVal?
#        # Then add fact that sliverFails is not empty to test on whether the call succeded overall or not

        result = dict()
        resultValue = self._getSliverResultList(resultValue)
        if len(resultValue) == 0:
            self.logger.debug("Result value not a list or empty")
            return result

        for sliver in resultValue:
            if not isinstance(sliver, dict):
                self.logger.debug("entry in result list was not a dict")
                continue
            if not sliver.has_key('geni_sliver_urn') or str(sliver['geni_sliver_urn']).strip() == "":
                self.logger.debug("entry in result had no 'geni_sliver_urn'")
                continue
#            sliver['geni_error'] = 'testing' # TESTING CODE
            if sliver.has_key('geni_error') and sliver['geni_error'] is not None and str(sliver['geni_error']).strip() != "":
                self.logger.debug("Sliver %s had error %s", sliver['geni_sliver_urn'], sliver['geni_error'])
                result[sliver['geni_sliver_urn']] = sliver['geni_error']
        return result

    def _findMissingSlivers(self, resultValue, requestedSlivers):
        '''Return list of sliver URNs in requested list but with no entry in resultValue'''
        # Used by Describe, Renew, Provision, Status, PerformOperationalAction, Delete
#        missingSlivers = self._findMissingSlivers(realresult, slivers)
#        if len(missingSlivers) > 0:
#            self.logger.warn("%d slivers from request missing in result!?", len(missingSlivers))
#            self.logger.debug("%s", missingSlivers)
#        # Then add missingSlivers being non-empty to test for overall success
        result = list()
        if not requestedSlivers or len(requestedSlivers) == 0:
            return result

        resultValue = self._getSliverResultList(resultValue)
        if len(resultValue) == 0:
            self.logger.debug("Result value not a list or empty")
            return result

        retSlivers = list()
        # get URNs from resultValue
        for sliver in resultValue:
            if not isinstance(sliver, dict):
                self.logger.debug("entry in result list was not a dict")
                continue
            if not sliver.has_key('geni_sliver_urn') or str(sliver['geni_sliver_urn']).strip() == "":
                self.logger.debug("entry in result had no 'geni_sliver_urn'")
                continue
            retSlivers.append(sliver['geni_sliver_urn'])

        for request in requestedSlivers:
            if not request or str(request).strip() == "":
                continue
            # if request not in resultValue, then add it to the return
            if request not in retSlivers:
                result.append(request)
        return result

    def _getSliverExpirations(self, resultValue, requestedExpiration=None):
        '''Get any slivers with a listed expiration different than the supplied date.
        If supplied is None, then gets all sliver expirationtimes.
        Return is a dict(sliverURN)->expiration'''

        # Called by Renew, Allocate(requested=None), Provision(requested=None)
        # (orderedDates, sliverExps) = self._getSliverExpirations(realresult, requestedExpiration/None)
        # None case
        # if len(orderedDates) == 1:
        #    self.logger.info("All slivers expire on %s", orderedDates[0])
        # elif len(orderedDates) == 2:
        #    self.logger.info("%d slivers expire on %s, the rest (%d) on %s", len(sliverExps[orderedDates[0]]), orderedDates[0], len(sliverExps[orderedDates[0]]), orderedDates[1])
        # else:
        #    self.logger.info("%d slivers expire on %s, %d on %s, and others later", len(sliverExps[orderedDates[0]]), orderedDates[0], len(sliverExps[orderedDates[0]]), orderedDates[1])
        # retVal += " First sliver expiration: %s" % orderedDates[0]

        # Renew/specific time case
        # (orderedDates, sliverExps) = self._getSliverExpirations(realresult, requestedExpiration/None)
#        if len(orderedDates) == 1 and orderedDates[0] == requestedExpiration:
#            self.logger.info("All slivers expire as requested on %s", requestedExpiration)
#        elif len(orderedDates) == 1:
#            self.logger.warn("Slivers expire on %s, not as requested %s", orderedDates[0], requestedExpiration)
#        else:
#            firstTime = None
#            firstCount = 0
#            if sliverExps.has_key(requestedExpiration):
#                expectedCount = sliverExps[requestedExpiration]
#            else:
#                expectedCount = 0
#            for time in orderedDates:
#                if time == requestedExpiration:
#                    continue
#                firstTime = time
#                firstCount = len(sliverExps[time])
#                break
#            self.logger.warn("Slivers do not all expire as requested: %d as requested (%s), but %d expire on %s, and others at %d other times", expectedCount, requestedExpiration, firstCount, firstTime, len(orderedDates) - 2)

        if requestedExpiration is None:
            requestedExpiration = datetime.datetime.max

        result = dict()

        resultValue = self._getSliverResultList(resultValue)
        if len(resultValue) == 0:
            self.logger.debug("Result value not a list or empty")
            return [], result

        for sliver in resultValue:
            if not isinstance(sliver, dict):
                self.logger.debug("entry in result list was not a dict")
                continue
            if not sliver.has_key('geni_sliver_urn') or str(sliver['geni_sliver_urn']).strip() == "":
                self.logger.debug("entry in result had no 'geni_sliver_urn'")
                continue
            if not sliver.has_key('geni_expires'):
                self.logger.debug("Sliver %s missing 'geni_expires'", sliver['geni_sliver_urn'])
                continue
            sliver_expires = sliver['geni_expires']
            if isinstance(sliver_expires, str):
                (sliver_expires, sliver_expires_with_tz, timestring) = self._datetimeFromString(sliver_expires)
            if requestedExpiration != datetime.datetime.max and sliver_expires != requestedExpiration:
                self.logger.warn("Sliver %s doesn't expire when requested! Expires at %r, not at %r", sliver['geni_sliver_urn'], sliver['geni_expires'], requestedExpiration.isoformat())
            if sliver_expires not in result.keys():
                thisTime = list()
                result[sliver_expires] = thisTime
            result[sliver_expires].append(sliver['geni_sliver_urn'])
        orderedDates = result.keys()
        orderedDates.sort()
        return (orderedDates, result)

    def _getSliverAllocStates(self, resultValue, expectedState=None):
        '''Get the Allocation state of slivers if the state is not the expected one, or all
        states if the expected arg is omitted.
        Return is a dict of sliverURN->actual allocation state.'''

        # Called by Allocate, Provision, Delete:
        # badSlivers = self._getSliverAllocStates(realresult, 'geni_allocated'/'geni_provisioned')
        # for sliver in badSlivers.keys():
        #   self.logger.warn("Sliver %s in wrong state! Expected %s, got %s", sliver, 'geni_allocated'/'geni_provisioned', badSlivers[sliver])
        # FIXME: Put that in return value?

        result = dict()
        if not resultValue:
            return result

        resultValue = self._getSliverResultList(resultValue)
        if len(resultValue) == 0:
            self.logger.debug("Result value not a list or empty")
            return result

        for sliver in resultValue:
            if not isinstance(sliver, dict):
                self.logger.debug("entry in result list was not a dict")
                continue
            if not sliver.has_key('geni_sliver_urn') or str(sliver['geni_sliver_urn']).strip() == "":
                self.logger.debug("entry in result had no 'geni_sliver_urn'")
                continue
            if not sliver.has_key('geni_allocation_status'):
                self.logger.debug("Sliver %s missing 'geni_allocation_status'", sliver['geni_sliver_urn'])
                result[sliver['geni_sliver_urn']] = ""
            if sliver['geni_allocation_status'] != expectedState:
                result[sliver['geni_sliver_urn']] = sliver['geni_allocation_status']

        return result

    # name arg: if present then we assume you are trying to
    # renew/create slivers with the given time - so raise an error if
    # the time is invalid
    # When noSec is true, fractional seconds are trimmed from the parsed time. Avoid problems at PG servers.
    def _datetimeFromString(self, dateString, slice_exp = None, name=None, noSec=False):
        '''Get time, time_with_tz, time_string from the given string. Log/etc appropriately
        if given a slice expiration to limit by.
        If given a slice name or slice expiration, insist that the given time is a valid
        time for requesting sliver expirations.
        Generally, use time_with_tz for comparisons and time_string to print or send in API Call.'''
        time = datetime.datetime.max
        try:
            if dateString is not None or self.opts.devmode:
                time = dateutil.parser.parse(dateString, tzinfos=tzd)
                if noSec:
                    time2 = time.replace(microsecond=0)
                    if (time2 != time):
                        self.logger.debug("Trimmed fractional seconds from %s to get %s", dateString, time2)
                        time = time2
        except Exception, exc:
            msg = "Couldn't parse time from '%s': %s" % (dateString, exc)
            if self.opts.devmode:
                self.logger.warn(msg)
            else:
                self._raise_omni_error(msg)

        # Convert to naive UTC time if necessary for ease of comparison
        try:
            time = naiveUTC(time)
        except Exception, exc:
            if self.opts.devmode:
                pass
            else:
                self.logger.warn("Failed to convert '%s' to naive UTC: %r", dateString, exc)
                raise

        if slice_exp:
            # Compare requested time with slice expiration time
            if not name:
                name = "<unspecified>"
            if time > slice_exp:
                msg = 'Cannot request or renew sliver(s) in %s until %s UTC because it is after the slice expiration time %s UTC' % (name, time, slice_exp)
                if self.opts.devmode:
                    self.logger.warn(msg + ", but continuing...")
                else:
                    self._raise_omni_error(msg)
            else:
                self.logger.debug('Slice expires at %s UTC, at or after requested time %s UTC' % (slice_exp, time))

        if time <= datetime.datetime.utcnow():
            if name is not None and not self.opts.devmode:
                # Syseng ticket 3011: User typo means their sliver expires.
                # Instead raise an error
                self._raise_omni_error("Cannot request or renew sliver(s) in %s to now or the past (%s UTC <= %s UTC)" % (name, time, datetime.datetime.utcnow()))
#                    self.logger.info('Sliver(s) in %s will be set to expire now' % name)
#                    time = datetime.datetime.utcnow()
            elif name is not None and self.opts.devmode:
                self.logger.warn("Will request or renew sliver(s) in %s to now or the past (%s UTC <= %s UTC)" % (name, time, datetime.datetime.utcnow()))

        # Add UTC TZ, to have an RFC3339 compliant datetime, per the AM API
        time_with_tz = time.replace(tzinfo=dateutil.tz.tzutc())
        # Note that the time arg includes UTC offset as needed
        time_string = time_with_tz.isoformat()

        if self.opts.no_tz:
            # The timezone causes an error in older sfa
            # implementations as deployed in mesoscale GENI. Strip
            # off the timezone if the user specfies --no-tz
            self.logger.info('Removing timezone at user request (--no-tz)')
            time_string = time_with_tz.replace(tzinfo=None).isoformat()

        return time, time_with_tz, time_string
    # end of datetimeFromString

    def _maybe_add_creds_from_files(self, creds):
        if creds is None:
            creds = []
        # Load and pass along also any 'credentials' specified with the
        # --cred argument
        if self.opts.cred and len(self.opts.cred) > 0:
            for credfile in self.opts.cred:
                # load it (comes out wrapped as needed)
                # FIXME: Wrapping code needs updates to mark speaksfor?
                cred = _load_cred(self, credfile)
                # append it
                if cred:
                    self.logger.info("Adding credential %s to arguments", credfile)
                    creds.append(cred)
        return creds


    def _getURNForClient(self, client):
        if client is None or client.url is None:
            return None
        agg_urn = client.urn
        if not urn_util.is_valid_urn(agg_urn):
            # Check if get_version has a geni_urn and use that?
            (gvurn, gvmess) = self._get_getversion_key(client, 'geni_urn', helper=True)
            (gvuurn, gvmess) = self._get_getversion_key(client, 'urn', helper=True) # For SFA AMs
            if urn_util.is_valid_urn(gvurn):
                agg_urn = gvurn
            elif urn_util.is_valid_urn(gvuurn):
                agg_urn = gvuurn
            elif not self.opts.noExtraCHCalls:
                # Else, ask the CH
                try:
                    turn = self.framework.lookup_agg_urn_by_url(client.url)
                    if urn_util.is_valid_urn(turn):
                        return turn
                except Exception, e:
                    self.logger.debug("Error asking CH for URN to match URL %s: %s", client.url, e)
            else:
                self.logger.debug("Didn't look up AM urn at CH per commandline option")
        return agg_urn

# End of AMHandler

def make_client(url, framework, opts):
    """ Create an xmlrpc client, skipping the client cert if not opts.ssl"""

    warnprefix = "WARN: "
    err = validate_url(url)
    if err is not None:
        if hasattr(framework, 'logger'):
            logger = framework.logger
        else:
            logger = logging.getLogger("omni")
        if err.find(warnprefix) == 0:
            err = err[len(warnprefix):]
            logger.warn(err)
        else:
            logger.error(err)
            raise OmniError(err)

    if opts.ssl:
        tmp_client =  xmlrpcclient.make_client(url, framework.key, framework.cert, opts.verbosessl, opts.ssltimeout)
    else:
        tmp_client = xmlrpcclient.make_client(url, None, None)
    tmp_client.url = str(url)
    tmp_client.urn = ""
    tmp_client.nick = None
    return tmp_client
        

def _maybe_add_abac_creds(framework, cred):
    '''Construct creds list. If using ABAC then creds are ABAC creds. Else creds are the user cred or slice cred
    as supplied, as normal.'''
    if is_ABAC_framework(framework):
        creds = get_abac_creds(framework.abac_dir)
    else:
        creds = []
    if cred:
        creds.append(cred)
    return creds

# FIXME: Use this frequently in experimenter mode, for all API calls
def _check_valid_return_struct(client, resultObj, message, call):
    '''Basic check that any API method returned code/value/output struct,
    producing a message with a proper error message'''
    if resultObj is None:
        # error
        message = "AM %s failed %s (empty): %s" % (client.str, call, message)
        return (None, message)
    elif not isinstance(resultObj, dict):
        # error
        message = "AM %s failed %s (returned %s): %s" % (client.str, call, resultObj, message)
        return (None, message)
    elif not resultObj.has_key('value'):
        message = "AM %s failed %s (no value: %s): %s" % (client.str, call, resultObj, message)
        return (None, message)
    elif not resultObj.has_key('code'):
        message = "AM %s failed %s (no code: %s): %s" % (client.str, call, resultObj, message)
        return (None, message)
    elif not resultObj['code'].has_key('geni_code'):
        message = "AM %s failed %s (no geni_code: %s): %s" % (client.str, call, resultObj, message)
        # error
        return (None, message)
    elif resultObj['code']['geni_code'] != 0:
        # error
        # This next line is experimenter-only maybe?
        message = "AM %s failed %s: %s" % (client.str, call, _append_geni_error_output(resultObj, message))
        return (None, message)
    else:
        return (resultObj, message)

# FIXMEFIXME: Use this lots places
# FIXME: How factor this for Dev/Exp?
def _append_geni_error_output(retStruct, message):
    '''Add to given error message the code and output if code != 0'''
    # If return is a dict
    if isinstance(retStruct, dict) and retStruct.has_key('code'):
        message2 = ""
        if isinstance(retStruct['code'], int):
            if retStruct['code'] != 0:
                message2 = "Malformed error from Aggregate: code " + str(retStruct['code'])
        elif isinstance(retStruct['code'], dict):
            if retStruct['code'].has_key('geni_code') and retStruct['code']['geni_code'] != 0:
                message2 = "Error from Aggregate: code " + str(retStruct['code']['geni_code'])
            amType = ""
            if retStruct['code'].has_key('am_type'):
                amType = retStruct['code']['am_type']
            if retStruct['code'].has_key('am_code') and retStruct['code']['am_code'] != 0 and retStruct['code']['am_code'] is not None and str(retStruct['code']['am_code']).strip() != "":
                if message2 != "":
                    if not message2.endswith('.'):
                        message2 += '.'
                    message2 += " "
                message2 += "%s AM code: %s" % (amType, str(retStruct['code']['am_code']))
        if retStruct.has_key('output') and retStruct['output'] is not None and str(retStruct['output']).strip() != "":
            message2 += ": %s" % retStruct['output']

        # Append any PG log urn/url - this shows up in Result Summary
        # on errors
        message2 += _get_pg_log(retStruct)

        if message2 != "":
            if not message2.endswith('.'):
                message2 += '.'
        if message is not None and message.strip() != "" and message2 != "":
            if not message2.endswith('.'):
                message2 += '.'
            message += " (%s)" % message2
        else:
            message = message2
    return message

def _get_pg_log(retStruct):
    '''Pull out the PG log URN and URL, if present'''
    msg = ""
    if retStruct.has_key('code') and isinstance(retStruct['code'], dict) and retStruct['code'].has_key('am_type') and retStruct['code']['am_type'] == 'protogeni':
        if retStruct['code'].has_key('protogeni_error_url'):
            msg += " (PG log url - look here for details on any failures: %s)" % retStruct['code']['protogeni_error_url']
        elif retStruct['code'].has_key('protogeni_error_log'):
            msg = " (PG log urn: %s)" % retStruct['code']['protogeni_error_log']
    return msg
