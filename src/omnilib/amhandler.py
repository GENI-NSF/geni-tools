#!/usr/bin/python

#----------------------------------------------------------------------
# Copyright (c) 2012 Raytheon BBN Technologies
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
import os
import pprint
import re
import string
import zlib

from omnilib.util import OmniError, NoSliceCredError, RefusedError, naiveUTC, AMAPIError
from omnilib.util.dossl import _do_ssl
from omnilib.util.abac import get_abac_creds, save_abac_creds, save_proof, \
        is_ABAC_framework
import omnilib.util.credparsing as credutils
from omnilib.util.handler_utils import _listaggregates, validate_url, _get_slice_cred, _derefAggNick, \
    _print_slice_expiration
from omnilib.util.json_encoding import DateTimeAwareJSONEncoder, DateTimeAwareJSONDecoder
import omnilib.xmlrpc.client
from omnilib.util.files import *

from geni.util import rspec_util, urn_util

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

        # Try to auto-correct API version
        msg = self._correctAPIVersion(args)

        (message, val) = getattr(self,call)(args[1:])
        return (msg+message, val)

    def _correctAPIVersion(self, args):
        '''Switch AM API versions if the AMs all or mostly speak something else. But be conservative.'''

        configVer = str(self.opts.api_version) # turn int into a string
        (clients, message) = self._getclients()
        clientCount = len(clients)
        liveVers = {}
        versions = {}
        retmsg = "" # Message to put at start of result summary
        for client in clients:
            (thisVer, message) = self._get_this_api_version(client)
            thisVer = str(thisVer) # turn int into a string
            liveVers[thisVer]  = liveVers.get(thisVer, 0) + 1 # hash is by strings
            (thisVersions, message) = self._get_api_versions(client)
            if thisVersions:
                for version in thisVersions.keys(): # version is a string
#                    self.logger.debug("%s supports %d at %s", client.url, int(version), thisVersions[version])
                    versions[version] = versions.get(version, 0) + 1 # hash by strings
#                    self.logger.debug("%d spoken by %d", int(version), versions[version])
            else:
                #self.logger.debug("Incrementing counter of clients that speak %r somewhere", thisVer)
                versions[thisVer] = versions.get(thisVer, 0) + 1

        # If all the AMs talk the desired version here, great
        if liveVers.has_key(configVer) and liveVers[configVer] == clientCount:
            self.logger.debug("Config version spoken here by all AMs")
            return retmsg

        # If all the AMs talk the desired version somewhere, fine. We'll switch URLs later.
        if versions.has_key(configVer) and versions[configVer] == clientCount:
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
                retmsg = "Your AMs do not all speak requested API v%d. " + msg
                msg = "Switching to AM API v%d. Next time call Omni with '-V%d'." % (newVer, newVer)
                retmsg += msg + "\n"
                self.logger.warn(msg)
                self.opts.api_version = newVer
            return retmsg

        # If the configured version is spoken somewhere by a majority of AMs, use it
        if versions.has_key(configVer) and float(versions[configVer]) >= float(clientCount)/float(2):
            self.logger.debug("Config version spoken somewhere by a majority of AMs")
            #self.logger.debug("clientCount/2 = %r", float(clientCount)/float(2))
            self.logger.info("Sticking with API version %s, even though only %d of %d AMs support it", configVer, versions[configVer], clientCount)
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
            self.logger.info("Sticking with API version %d, even though only %d of %d AMs support it", configVer, configSup, clientCount)
            return retmsg

        if liveVers[mostLive] == clientCount:
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
            self.logger.info("Sticking with API version %s, even though only %d of %d AMs support it", configVer, versions[configVer], clientCount)
            return retmsg

        # If we get here, the configured version is not the most popular, nor supported by most AMs
        # IE, something else is more popular

        if versions[mostAnywhere] == clientCount:
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

        if float(liveVers[mostLive]) >= float(clientCount)/float(2):
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

        if float(versions[mostAnywhere]) >= float(clientCount)/float(2):
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
    def _do_getversion(self, client):
        '''Pull GetVersion for this AM from cache; otherwise actually call GetVersion if this
        AM wasn't in the cache, the options say not to use the cache, or the cache is too old.

        If we actually called GetVersion:
        Construct full error message including string version of code/output slots.
        Then cache the result.
        If we got the result from the cache, set the message to say so.
        '''
        cachedVersion = self._get_cached_getversion(client)
        # FIXME: What if cached entry had an error? Should I retry then?
        if self.opts.noGetVersionCache or cachedVersion is None or (self.opts.GetVersionCacheOldestDate and cachedVersion['timestamp'] < self.opts.GetVersionCacheOldestDate):
            self.logger.debug("Actually calling GetVersion")
            (thisVersion, message) = _do_ssl(self.framework, None, "GetVersion at %s" % (str(client.url)), client.GetVersion)

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
        header = "AM URN: %s (url: %s) has version:" % (client.urn, client.url)
        if message:
            header += " (" + message + ")"
        filename = None
        if self.opts.output:
            # Create filename
            filename = self._construct_output_filename(None, client.url, client.urn, "getversion", ".json", 1)
            self.logger.info("Writing result of getversion at AM %s (%s) to file '%s'", client.urn, client.url, filename)
        # Create File
        # This logs or prints, depending on whether filename is None
        self._printResults( header, prettyVersion, filename)

        # FIXME: include filename in summary: always? only if 1 aggregate?
        if filename:
            return "Saved getversion at AM %s (%s) to file '%s'.\n" % (client.urn, client.url, filename)
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

    # FIXME: This pulls only the value slot out - losing the code&output, the top-level geni_api,
    # and any extra slots. Is that what we want?
    # FIXME: Unused
    def _get_client_version(self, client):
        '''Get the actual GetVersion value - not the full struct - for this AM.
        Get this from the cache or the AM, depending on the options.
        For APIv1, the actual version is the full struct; else it is the value'''
        (thisVersion, message) = self._do_getversion(client)
        if thisVersion is None:
            # error
            self.logger.warning("AM %s failed getversion (empty): %s", client.url, message)
            return None
        elif not isinstance(thisVersion, dict):
            # error
            self.logger.warning("AM %s failed getversion (returned %s): %s", client.url, thisVersion, message)
            return None
        elif not thisVersion.has_key('geni_api'):
            # error
            self.logger.warning("AM %s failed getversion (malformed return %s): %s", client.url, thisVersion, message)
            return None
        topVer = thisVersion['geni_api']
        innerVer = None
        if thisVersion.has_key['value'] and thisVersion['value'].has_key('geni_api'):
            innerVer = thiVersion['value']['geni_api']
        if topVer > 1 and topVer != innerVer:
            # error
            self.logger.warning("AM %s corrupt getversion top %d != inner %d", client.url, topVer, innerVer)
        # This will indicate it came from the cache
        if message:
            self.logger.info("Got AM version: %s", message)
        return topVer

    # FIXME: Is this too much checking/etc for developers?
    # See _check_valid_return_struct: lots of overlap, but this checks the top-level geni_api
    # FIXME: The return from the cache doesn't really need to be rechecked, does it? Or will that not happen?
    def _do_and_check_getversion(self, client):
        '''Do GetVersion (possibly from cache), then check return for errors,
        constructing a good message. 
        Basically, add return checks to _do_getversion'''
        message = None
        (thisVersion, message) = self._do_getversion(client)
        if thisVersion is None:
            # error
            message = "AM %s failed getversion (empty): %s" % (client.url, message)
            return (None, message)
        elif not isinstance(thisVersion, dict):
            # error
            message = "AM %s failed getversion (returned %s): %s" % (client.url, thisVersion, message)
            return (None, message)
        elif not thisVersion.has_key('geni_api'):
            # error
            message = "AM %s failed getversion (no geni_api at top: %s): %s" % (client.url, thisVersion, message)
            return (None, message)
        elif thisVersion['geni_api'] == 1:
            # No more checking to do - return it as is
            return (thisVersion, message)
        elif not thisVersion.has_key('value'):
            message = "AM %s failed getversion (no value: %s): %s" % (client.url, thisVersion, message)
            return (None, message)
        elif not thisVersion.has_key('code'):
            message = "AM %s failed getversion (no code: %s): %s" % (client.url, thisVersion, message)
            return (None, message)
        elif not thisVersion['code'].has_key('geni_code'):
            message = "AM %s failed getversion (no geni_code: %s): %s" % (client.url, thisVersion, message)
            # error
            return (None, message)
        elif thisVersion['code']['geni_code'] != 0:
            # error
            # This next line is experimenter-only maybe?
            message = "AM %s failed getversion: %s" % (client.url, _append_geni_error_output(thisVersion, message))
            return (None, message)
        elif not isinstance(thisVersion['value'], dict):
            message = "AM %s failed getversion (non dict value %s): %s" % (client.url, thisVersion['value'], message)
            return (None, message)
        # OK, we have a good result
        return (thisVersion, message)

    # This is the real place that ends up calling GetVersion
    # FIXME: As above: this loses the code/output slots and any other top-level slots.
    #  Maybe only for experimenters?

    def _get_getversion_value(self, client):
        '''Do GetVersion (possibly from cache), check error returns to produce a message,
        pull out the value slot (dropping any code/output).'''
        message = None

        # We cache results by URL
        if not hasattr(self, 'gvValueCache'):
            self.gvValueCache = dict()
        if self.gvValueCache.has_key(client.url):
            return self.gvValueCache[client.url]

        (thisVersion, message) = self._do_and_check_getversion(client)
        if thisVersion is None:
            # error - return what the error check had
            return (thisVersion, message)
        elif thisVersion['geni_api'] == 1:
            versionSpot = thisVersion
        else:
            versionSpot = thisVersion['value']
        self.gvValueCache[client.url] = (versionSpot, message)
        return (versionSpot, message)

    def _get_getversion_key(self, client, key):
        '''Pull the given key from the GetVersion value object'''
        if key is None or key.strip() == '':
            return (None, "no key specified")
        (versionSpot, message) = self._get_getversion_value(client)
        if versionSpot is None:
            return (None, message)
        elif not versionSpot.has_key(key):
            message2 = "AM %s getversion has no key %s" % (client.url, key)
            if message:
                message = message2 + "; " + message
            else:
                message = message2
            return (None, message)
        else:
            return (versionSpot[key], message)

    def _get_this_api_version(self, client):
        '''Get the supported API version for this AM (from GetVersion)'''
        (res, message) = self._get_getversion_key(client, 'geni_api')
        if res is None:
            self.logger.warning("Couldnt get api version supported from GetVersion: %s" % message)
        # Return is an int API version
        return (res, message)

    def _get_api_versions(self, client):
        '''Get the supported API versions and URLs for this AM (from GetVersion)'''
        (res, message) = self._get_getversion_key(client, 'geni_api_versions')
        if res is None:
            msg = "Couldnt get api versions supported from GetVersion: %s" % message
            (thisVer, msg2) = self._get_getversion_key(client, 'geni_api')
            if thisVer and thisVer < 2:
                self.logger.debug(msg)
            else:
                self.logger.warning(msg)
        # Return is a dict: Int API version -> string URL of AM
        return (res, message)

    def _get_advertised_rspecs(self, client):
        '''Get the supported advertisement rspec versions for this AM (from GetVersion)'''
        (ads, message) = self._get_getversion_key(client, 'ad_rspec_versions')
        if ads is None:
            if message and "has no key" in message:
                (ads, message) = self._get_getversion_key(client, 'geni_ad_rspec_versions')

        if ads is None:
            self.logger.warning("Couldnt get Advertised supported RSpec versions from GetVersion so can't do ListResources: %s" % message)

        # Return is array of dicts with type, version, schema, namespace, array of extensions 
        return (ads, message)

    def _get_request_rspecs(self, client):
        '''Get the supported request rspec versions for this AM (from GetVersion)'''
        (ads, message) = self._get_getversion_key(client, 'request_rspec_versions')
        if ads is None:
            if message and "has no key" in message:
                (ads, message) = self._get_getversion_key(client, 'geni_request_rspec_versions')

        if ads is None:
            self.logger.warning("Couldnt get Request supported RSpec versions from GetVersion: %s" % message)

        # Return is array of dicts with type, version, schema, namespace, array of extensions 
        return (ads, message)

    def _get_cred_versions(self, client):
        '''Get the supported credential types for this AM (from GetVersion)'''
        (res, message) = self._get_getversion_key(client, 'geni_credential_types')
        if res is None:
            self.logger.warning("Couldnt get credential types supported from GetVersion: %s" % message)
        # Return is array of dicts: geni_type, geni_version
        return (res, message)

    def _get_singlealloc_style(self, client):
        '''Get the supported single_allocation for this AM (from GetVersion)'''
        (res, message) = self._get_getversion_key(client, 'geni_single_allocation')
        if res is None:
            self.logger.debug("Couldnt get single_allocation mode supported from GetVersion; will use default of False: %s" % message)
            res = False
        # return is boolean
        return (res, message)

    def _get_alloc_style(self, client):
        '''Get the supported geni_allocate allocation style for this AM (from GetVersion)'''
        (res, message) = self._get_getversion_key(client, 'geni_allocate')
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
            raise BadClientException(client, validMsg)
        elif newc.url != client.url:
            if ver != self.opts.api_version:
                self.logger.error("AM %s doesn't speak API version %d. Try the AM at %s and tell Omni to use API version %d, using the option '-V%d'.", client.url, self.opts.api_version, newc.url, ver, ver)
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
            client = newc
        elif ver != self.opts.api_version:
            self.logger.error("AM %s doesn't speak API version %d. Tell Omni to use API version %d, using the option '-V%d'.", client.url, self.opts.api_version, ver, ver)
            raise BadClientException(client, validMsg)

        self.logger.debug("Doing SSL/XMLRPC call to %s invoking %s", client.url, op)
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
                self.logger.warn( "URN: %s (url:%s) call failed: %s\n" % (client.urn, client.url, message) )
                retVal += "Cannot GetVersion at %s: %s\n" % (client.url, message)
            else:
                successCnt += 1
                retVal += self._do_getversion_output(thisVersionValue, client, message)
        # End of loop over clients

        ### Method specific all-results handling, printing
        if len(clients)==0:
            retVal += "No aggregates to query. %s\n\n" % message
        else:
            if len(clients)>1:
                # FIXME: If I have a message from getclients, want it here?
                if "From Cache" in message:
                    retVal += "\nGot version for %d out of %d aggregates using GetVersion cache\n" % (successCnt,len(clients))
                else:
                    retVal += "\nGot version for %d out of %d aggregates\n" % (successCnt,len(clients))
            else:
                if successCnt == 1:
                    retVal += "\nGot version for %s\n" % clients[0].url
                else:
                    retVal += "\nFailed to get version for %s\n" % clients[0].url
                if "From Cache" in message:
                    retVal += message + "\n"
        return (retVal, version)

    # ------- End of GetVersion stuff

    def _selectRSpecVersion(self, slicename, client, mymessage, options):
        '''Helper for Describe and ListResources to set the rspec_version option, based on a single AMs capabilities.
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
                self.logger.debug("AM %s failed to advertise supported RSpecs", client.url)
                # Allow developers to call an AM that fails to advertise
                if not self.opts.devmode:
                    # Skip this AM/client
                    raise BadClientException(client, mymessage)

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
                    self.logger.warning("AM cannot provide Rspec in requested version (%s %s) at AM %s [%s]. This AM only supports: \n%s", rtype, rver, client.urn, client.url, pp.pformat(ad_rspec_version))
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
                        mymessage = mymessage + "Skipped AM %s that didnt support required RSpec format %s %s" % (client.url, rtype, rver)
                        mymessage = mymessage + tryOthersMsg
                        # Skip this AM/client
                        raise BadClientException(client, mymessage)
                    else:
                        mymessage = mymessage + "AM %s didnt support required RSpec format %s %s, but continuing" % (client.url, rtype, rver)

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
                self.logger.debug("AM %s failed to advertise supported RSpecs", client.url)
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
                self.logger.warning("Please use the -t option to specify the desired RSpec type for AM %s as one of %r", client.url, ad_versions)
                if mymessage != "" and not mymessage.endswith('.'):
                    mymessage += ". "
                mymessage = mymessage + "AM %s supports multiple RSpec versions: %r" % (client.url, ad_versions)
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
                if rspec and rspec_util.is_rspec_string(rspec, self.logger):
                    self.logger.debug("AM returned uncompressed RSpec when compressed was requested")
                else:
                    self.logger.error("Failed to decompress RSpec: %s", e);
                self.logger.debug("RSpec begins: '%s'", rspec[:min(40, len(rspec))])
        # In experimenter mode, maybe notice if the rspec appears compressed anyhow and try to decompress?
        elif not self.opts.devmode and rspec and not rspec_util.is_rspec_string(rspec, self.logger):
            try:
                rspec2 = zlib.decompress(rspec.decode('base64'))
                if rspec2 and rspec_util.is_rspec_string(rspec2, self.logger):
                    rspec = rspec2
            except Exception, e:
                pass
        return rspec

    def _listresources(self, args):
        """Support method for doing AM API ListResources. Queries resources on various aggregates.
        
        Takes an optional slicename.

        Aggregates queried:
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
                # Dev mode allow doing the call anyhow
                self.logger.error('Cannot list resources: Could not get user credential')
                if not self.opts.devmode:
                    return (None, "Could not get user credential: %s" % message)
                else:
                    self.logger.info('... but continuing')
                    cred = ""
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
        if len(clientList) == 0:
            if message != "":
                mymessage = "No aggregates available to query: %s" % message
        else:
            # FIXME: What if got a message and still got some aggs?
            if message != "":
                self.logger.debug("Got %d AMs but also got an error message: %s", len(clientList), message)
            creds = _maybe_add_abac_creds(self.framework, cred)

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
                    mymessage += validMsg
                continue
            elif newc.url != client.url:
                if ver != self.opts.api_version:
                    self.logger.error("AM %s doesn't speak API version %d. Try the AM at %s and tell Omni to use API version %d, using the option '-V%d'.", client.url, self.opts.api_version, newc.url, ver, ver)
                    if len(clientList) == 1:
                        self._raise_omni_error("Can't do ListResources: AM %s speaks only AM API v%d, not %d. Try calling Omni with the -V%d option." % (client.url, ver, self.opts.api_version, ver))

                    if not mymessage:
                        mymessage = ""
                    else:
                        if not mymessage.endswith('.'):
                            mymessage += ".\n"
                        else:
                            mymyessage += "\n"
                    mymessage += "Skipped AM %s: speaks only API v%d, not %d. Try -V%d option." % (client.url, ver, self.opts.api_version, ver)
                    continue
#                    raise BadClientException(client, mymessage)
#                    self.logger.warn("Changing API version to %d. Is this going to work?", ver)
#                    # FIXME: changing the api_version is not a great idea if
#                    # there are multiple clients. Push this into _checkValidClient
#                    # and only do it if there is one client.
#1                    self.opts.api_version = ver
                else:
                    self.logger.debug("Using new AM url %s but same API version %d", newc.url, ver)
                client = newc
            elif ver != self.opts.api_version:
                self.logger.error("AM %s speaks API version %d, not %d. Rerun with option '-V%d'.", client.url, ver, self.opts.api_version, ver)
                if len(clientList) == 1:
                    self._raise_omni_error("Can't do ListResources: AM %s speaks only AM API v%d, not %d. Try calling Omni with the -V%d option." % (client.url, ver, self.opts.api_version, ver))

                if not mymessage:
                    mymessage = ""
                else:
                    if not mymessage.endswith('.'):
                        mymessage += ".\n"
                    else:
                        mymessage += "\n"
                mymessage += "Skipped AM %s: speaks only API v%d, not %d. Try -V%d option." % (client.url, ver, self.opts.api_version, ver)
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
                continue

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
                if rspec and rspec_util.is_rspec_string( rspec, self.logger ):
                    successCnt += 1
                    rspec = rspec_util.getPrettyRSpec(rspec)
                else:
                    self.logger.warn("Didn't get a valid RSpec!")
                    if mymessage != "":
                        if mymessage.endswith('.'):
                            mymessage += ' '
                        else:
                            mymessage += ". "
                    mymessage += "No resources from AM %s: %s" % (client.url, message)
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
                mymessage += "No resources from AM %s: %s" % (client.url, message)

            # Return for tools is the full code/value/output triple
            rspecs[(client.urn, client.url)] = resp

        if len(clientList) > 0:
            if slicename:
                self.logger.info( "Listed reserved resources on %d out of %d possible aggregates." % (successCnt, len(clientList)))
            else:
                self.logger.info( "Listed advertised resources at %d out of %d possible aggregates." % (successCnt, len(clientList)))
        return (rspecs, mymessage)
    # End of _listresources

    def listresources(self, args):
        """GENI AM API ListResources
        Call ListResources on 1+ aggregates and prints the rspec to stdout or to a file.
        Optional argument for API v1&2 is a slice name, making the request for a manifest RSpec.
        Note that the slice name argument is only supported in AM API v1 or v2.
        For listing contents of a slice in APIv3+, use describe().
        
        Aggregates queried:
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
#        numAggs = 0
#        if rspecs is not None:
#            numAggs = len(rspecs.keys())
        (aggs, mla) = _listaggregates(self)
        numAggs = len(aggs)
        
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
            self.logger.debug("Getting RSpec items for AM urn %s (%s)", urn, url)
            rspecOnly, message = self._retrieve_value( rspecStruct, message, self.framework)
            if self.opts.api_version < 2:
                returnedRspecs[(urn,url)] = rspecOnly
            else:
                returnedRspecs[url] = rspecStruct
            if rspecOnly and rspecOnly != "":
                rspecCtr += 1

            retVal, filename = self._writeRSpec(rspecOnly, slicename, urn, url, None, len(rspecs))
            if filename:
                savedFileDesc += "Saved listresources RSpec at '%s' (url '%s') to file %s; " % (urn, url, filename)
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
                    retVal += "\n" + savedFileDesc
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
        if len(clientList) > 0:
            self.logger.info('Describe Slice %s:' % urn)

            creds = _maybe_add_abac_creds(self.framework, slice_cred)

            urnsarg, slivers = self._build_urns(urn)

            # Add the options dict
            options = self._build_options('Describe', options)
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
                if mymessage != "":
                    if message is None or message.strip() == "":
                        message = ""
                    message = mymessage + ". " + message
            except BadClientException as bce:
                if bce.validMsg and bce.validMsg != '':
                    retVal += bce.validMsg + ". "
                else:
                    retVal += "Describe skipping AM %s. No matching RSpec version or wrong AM API version - check logs" % (client.url)
                if len(clientList) == 1:
                    self._raise_omni_error("\nDescribe failed: " + retVal)
                continue

# FIXME: Factor this next chunk into helper method?
            # Decompress the RSpec before sticking it in retItem
            rspec = None
            if status and isinstance(status, dict) and status.has_key('value') and isinstance(status['value'], dict) and status['value'].has_key('geni_rspec'):
                rspec = self._maybeDecompressRSpec(options, status['value']['geni_rspec'])
                if rspec and rspec != status['value']['geni_rspec']:
                    self.logger.debug("Decompressed RSpec")
                if rspec and rspec_util.is_rspec_string( rspec, self.logger ):
                    rspec = rspec_util.getPrettyRSpec(rspec)
                else:
                    self.logger.warn("Didn't get a valid RSpec!")
                status['value']['geni_rspec'] = rspec
            else:
                self.logger.warn("Got no resource listing from AM %s", client.url)
                self.logger.debug("Return struct missing geni_rspec element!")

            # Return for tools is the full code/value/output triple
            retItem[client.url] = status

            # Get the dict describe result out of the result (accounting for API version diffs, ABAC)
            (status, message) = self._retrieve_value(status, message, self.framework)
            if not status:
                fmt = "\nFailed to Describe %s at AM %s: %s\n"
                if message is None or message.strip() == "":
                    message = "(no reason given)"
                retVal += fmt % (descripMsg, client.url, message)
                continue # go to next AM

            missingSlivers = self._findMissingSlivers(status, slivers)
            if len(missingSlivers) > 0:
                self.logger.warn("%d slivers from request missing in result?!", len(missingSlivers))
                self.logger.debug("%s", missingSlivers)

            sliverFails = self._didSliversFail(status)
            for sliver in sliverFails.keys():
                self.logger.warn("Sliver %s reported error: %s", sliver, sliverFails[sliver])

            (header, rspeccontent, rVal) = self._getRSpecOutput(rspec, name, client.urn, client.url, message, slivers)
            self.logger.debug(rVal)
            if status and isinstance(status, dict) and status.has_key('geni_rspec') and rspec and rspeccontent:
                status['geni_rspec'] = rspeccontent

            if not isinstance(status, dict):
                # malformed describe return
                self.logger.warn('Malformed describe result from AM %s. Expected struct, got type %s.' % (client.url, status.__class__.__name__))
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
                filename = self._construct_output_filename(name, client.url, client.urn, "describe", ".json", len(clientList))
                #self.logger.info("Writing result of describe for slice: %s at AM: %s to file %s", name, client.url, filename)
            self._printResults(header, prettyResult, filename)
            if filename:
                retVal += "Saved description of %s at AM %s to file %s. \n" % (descripMsg, client.url, filename)
            # Only count it as success if no slivers were missing
            if len(missingSlivers) == 0 and len(sliverFails.keys()) == 0:
                successCnt+=1
            else:
                retVal += " - with %d slivers missing and %d slivers with errors. \n" % (len(missingSlivers), len(sliverFails.keys()))

        # FIXME: Return the status if there was only 1 client?
        if len(clientList) > 0:
            retVal += "Found description of slivers on %d of %d possible aggregates." % (successCnt, len(clientList))
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
            msg = 'Missing -a argument: specify an aggregate where you want the reservation.'
            # FIXME: parse the AM to reserve at from a comment in the RSpec
            # Calling exit here is a bit of a hammer.
            # Maybe there's a gentler way.
            self._raise_omni_error(msg)
        elif len(self.opts.aggregate) > 1:
            self.logger.warn("Multiple -a arguments received - only the first will be used.")

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
          rspec = readFile(rspecfile)
        except Exception, exc:
#--- Should dev mode allow this?
            msg = 'Unable to read rspec file %s: %s' % (rspecfile, str(exc))
            if self.opts.devmode:
                rspec = ""
                self.logger.warn(msg)
            else:
                self._raise_omni_error(msg)

        # Test if the rspec is really json containing an RSpec, and pull out the right thing
        rspec = self._maybeGetRSpecFromStruct(rspec)

        # FIXME: We could try to parse the RSpec right here, and get the AM URL or nickname
        # out of the RSpec

        url, clienturn = _derefAggNick(self, self.opts.aggregate[0])

        # Perform the allocations
        (aggs, message) = _listaggregates(self)
        if aggs == {} and message != "":
            retVal += "No aggregates to reserve on: %s" % message

        aggregate_urls = aggs.values()
        # Is this AM listed in the CH or our list of aggregates?
        # If not we won't be able to check its status and delete it later
        if not url in aggregate_urls:
            self.logger.info("""Be sure to remember (write down) AM URL:
             %s. 
             You are reserving resources there, and your clearinghouse
             and config file won't remind you to check that sliver later. 
             Future listresources/sliverstatus/deletesliver calls need to 
             include the 
                   '-a %s'
             arguments again to act on this sliver.""" % (url, url))

        # Okay, send a message to the AM this resource came from
        result = None
        client = make_client(url, self.framework, self.opts)
        client.urn = clienturn
        self.logger.info("Creating sliver(s) from rspec file %s for slice %s", rspecfile, urn)

        creds = _maybe_add_abac_creds(self.framework, slice_cred)

        # Copy the user config and read the keys from the files into the structure
        slice_users = self._get_users_arg()

        options = None
        args = [urn, creds, rspec, slice_users]
#--- API version diff:
        if self.opts.api_version >= 2:
            options = dict()
            # Add the options dict
            args.append(options)
#---

        op = "CreateSliver"
        msg = "Create Sliver %s at %s" % (urn, url)
        self.logger.debug("Doing createsliver with urn %s, %d creds, rspec of length %d starting '%s...', users struct %s, options %r", urn, len(creds), len(rspec), rspec[:min(100, len(rspec))], slice_users, options)
        try:
            ((result, message), client) = self._api_call(client, msg, op,
                                                args)
            url = client.url
            client.urn = clienturn
        except BadClientException as bce:
            self._raise_omni_error("Cannot CreateSliver at %s: The AM speaks the wrong API version, not %d. %s" % (client.url, self.opts.api_version, bce.validMsg))

        # Get the manifest RSpec out of the result (accounting for API version diffs, ABAC)
        (result, message) = self._retrieve_value(result, message, self.framework)
        if result:
            self.logger.info("Got return from CreateSliver for slice %s at %s:", slicename, url)

            (retVal, filename) = self._writeRSpec(result, slicename, clienturn, url, message)
            if filename:
                self.logger.info("Wrote result of createsliver for slice: %s at AM: %s to file %s", slicename, url, filename)
                retVal += '\n   Saved createsliver results to %s. ' % (filename)

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
            prStr = "Failed CreateSliver for slice %s at %s." % (slicename, url)
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
        if rspecfile is None or not os.path.isfile(rspecfile):
            # Dev mode should allow missing RSpec
            msg = 'File of resources to request missing: %s' % rspecfile
            if self.opts.devmode:
                self.logger.warn(msg)
            else:
                self._raise_omni_error(msg)

        # read the rspec into a string, and add it to the rspecs dict
        try:
            rspec = file(rspecfile).read()
        except Exception, exc:
            msg = 'Unable to read rspec file %s: %s' % (rspecfile, str(exc))
            if self.opts.devmode:
                rspec = ""
                self.logger.warn(msg)
            else:
                self._raise_omni_error(msg)

        # Test if the rspec is really json containing an RSpec, and
        # pull out the right thing
        rspec = self._maybeGetRSpecFromStruct(rspec)

        # Build args
        options = self._build_options('Allocate', None)
        creds = _maybe_add_abac_creds(self.framework, slice_cred)
        args = [urn, creds, rspec, options]
        descripMsg = "slivers in slice %s" % urn
        op = 'Allocate'
        self.logger.debug("Doing Allocate with urn %s, %d creds, rspec starting: \'%s...\', and options %s", urn, len(creds), rspec[:min(40, len(rspec))], options)

        successCnt = 0
        retItem = dict()
        (clientList, message) = self._getclients()
        if len(clientList) == 0:
            msg = "No aggregate specified to submit allocate request to. Use the -a argument."
            if self.opts.devmode:
                #  warn
                self.logger.warn(msg)
            else:
                self._raise_omni_error(msg)
        elif len(clientList) > 1:
            #  info - mention unbound bits will be repeated
            self.logger.info("Multiple aggregates will get the same request RSpec; unbound requests will be attempted at multiple aggregates.")

        # Do the command for each client
        for client in clientList:
            self.logger.info("Allocate %s at %s:", descripMsg, client.url)
            try:
                ((result, message), client) = self._api_call(client,
                                    ("Allocate %s at %s" % (descripMsg, client.url)),
                                    op,
                                    args)
            except BadClientException, bce:
                if bce.validMsg and bce.validMsg != '':
                    retVal += bce.validMsg + ". "
                else:
                    retVal += "Skipped aggregate %s. (Unreachable? Doesn't speak AM API v%d? Check the log messages, and try calling 'getversion' to check AM status and API versions supported.).\n" % (client.url, self.opts.api_version)
                if len(clientList) == 1:
                    self._raise_omni_error("\nAllocate failed: " + retVal)
                continue

            # Make the RSpec more pretty-printed
            rspec = None
            if result and isinstance(result, dict) and result.has_key('value') and isinstance(result['value'], dict) and result['value'].has_key('geni_rspec'):
                rspec = result['value']['geni_rspec']
                if rspec and rspec_util.is_rspec_string( rspec, self.logger ):
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
                (header, rspeccontent, rVal) = self._getRSpecOutput(rspec, slicename, client.urn, client.url, message)
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
                    filename = self._construct_output_filename(slicename, client.url, client.urn, "allocate", ".json", len(clientList))
                    #self.logger.info("Writing result of allocate for slice: %s at AM: %s to file %s", slicename, client.url, filename)
                self._printResults(header, prettyResult, filename)
                if filename:
                    retVal += "Saved allocation of %s at AM %s to file %s. \n" % (descripMsg, client.url, filename)
                else:
                    retVal += "Allocated %s at %s. \n" % (descripMsg, client.url)

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
                    retVal += " Next sliver expiration: %s" % orderedDates[0].isoformat()

                self.logger.debug("Allocate %s result: %s" %  (descripMsg, prettyResult))
                successCnt += 1
            else:
                # Failure
                if message is None or message.strip() == "":
                    message = "(no reason given)"
                retVal += "Allocation of %s at %s failed: %s.\n" % (descripMsg, client.url, message)
                self.logger.warn(retVal)
                # FIXME: Better message?
        # Done with allocate call loop over clients

        if len(clientList) == 0:
            retVal += "No aggregates at which to allocate %s. %s\n" % (descripMsg, message)
        elif len(clientList) > 1:
            retVal += "Allocated %s at %d out of %d aggregates.\n" % (descripMsg, successCnt, len(clientList))
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
        slice_users = self._get_users_arg()

        # If there are slice_users, include that option
        options = {}
        if slice_users and len(slice_users) > 0:
            options['geni_users'] = slice_users

        options = self._build_options(op, options)
        urnsarg, slivers = self._build_urns(urn)

        descripMsg = "slivers in slice %s" % urn
        if len(slivers) > 0:
            descripMsg = "%d slivers in slice %s" % (len(slivers), urn)

        creds = _maybe_add_abac_creds(self.framework, slice_cred)
        args = [urnsarg, creds, options]
        self.logger.debug("Doing Provision with urns %s, %d creds, options %s", urnsarg, len(creds), options)

        # Get Clients
        successCnt = 0
        retItem = dict()
        (clientList, message) = self._getclients()
        if len(clientList) == 0:
            msg = "No aggregate specified to submit provision request to. Use the -a argument."
            if self.opts.devmode:
                #  warn
                self.logger.warn(msg)
            else:
                self._raise_omni_error(msg)
        elif len(clientList) > 1 and len(slivers) > 0:
            # All slivers will go to all AMs. If not best effort, AM may fail the request if its
            # not a local sliver.
            #  # FIXME: Could partition slivers by AM URN?
            msg = "Will do %s %s at all %d AMs - some aggregates may fail the request if given slivers not from that aggregate." % (op, descripMsg, len(clientList))
            if self.opts.geni_best_effort:
                self.logger.info(msg)
            else:
                self.logger.warn(msg + " Consider running with --best-effort in future.")

        # Loop over clients doing operation
        for client in clientList:
            self.logger.info("%s %s at %s", op, descripMsg, client.url)
            try:
                ((result, message), client) = self._api_call(client,
                                                  ("Provision %s at %s" % (descripMsg, client.url)),
                                                  op,
                                                  args)
            except BadClientException, bce:
                if bce.validMsg and bce.validMsg != '':
                    retVal += bce.validMsg + ". "
                else:
                    retVal += "Skipped aggregate %s. (Unreachable? Doesn't speak AM API v%d? Check the log messages, and try calling 'getversion' to check AM status and API versions supported.).\n" % (client.url, self.opts.api_version)
                if len(clientList) == 1:
                    self._raise_omni_error("\nProvision failed: " + retVal)
                continue

            # Make the RSpec more pretty-printed
            if result and isinstance(result, dict) and result.has_key('value') and isinstance(result['value'], dict) and result['value'].has_key('geni_rspec'):
                rspec = result['value']['geni_rspec']
                if rspec and rspec_util.is_rspec_string( rspec, self.logger ):
                    rspec = rspec_util.getPrettyRSpec(rspec)
                    result['value']['geni_rspec'] = rspec

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

                # Print out the result
                if isinstance(realresult, dict):
                    prettyResult = json.dumps(realresult, ensure_ascii=True, indent=2)
                else:
                    prettyResult = pprint.pformat(realresult)

                header="<!-- Provision %s at AM URL %s -->" % (descripMsg, client.url)
                filename = None

                if self.opts.output:
                    filename = self._construct_output_filename(slicename, client.url, client.urn, "provision", ".json", len(clientList))
                    #self.logger.info("Writing result of provision for slice: %s at AM: %s to file %s", name, client.url, filename)
                self._printResults(header, prettyResult, filename)
                if filename:
                    retVal += "Saved provision of %s at AM %s to file %s. \n" % (descripMsg, client.url, filename)
                else:
                    retVal += "Provisioned %s at %s. \n" % (descripMsg, client.url)
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
                retVal += " Next sliver expiration: %s" % orderedDates[0].isoformat()

                self.logger.debug("Provision %s result: %s" %  (descripMsg, prettyResult))
                if len(missingSlivers) == 0 and len(sliverFails.keys()) == 0:
                    successCnt += 1
            else:
                # Failure
                if message is None or message.strip() == "":
                    message = "(no reason given)"
                retVal = "Provision of %s at %s failed: %s" % (descripMsg, client.url, message)
                self.logger.warn(retVal)
        # Done loop over clients

        if len(clientList) == 0:
            retVal += "No aggregates at which to provision %s. %s\n" % (descripMsg, message)
        elif len(clientList) > 1:
            retVal += "Provisioned %s at %d out of %d aggregates.\n" % (descripMsg, successCnt, len(clientList))
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

        Clients must Renew or use slivers before the expiration time
        (given in the return struct), or the aggregate will automatically Delete them.

        --sliver-urn / -u option: each specifies a sliver URN on which to perform the given action. If specified, 
        only the listed slivers will be acted on. Otherwise, all slivers in the slice will be acted on.
        Note though that actions are state and resource type specific, so the action may not apply everywhere.

        Slice name could be a full URN, but is usually just the slice name portion.
        Note that PLC Web UI lists slices as <site name>_<slice name>
        (e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

        Aggregates queried:
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
            if self.opts.devmode:
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

        options = self._build_options(op, None)
        urnsarg, slivers = self._build_urns(urn)

        descripMsg = "%s on slivers in slice %s" % (action, urn)
        if len(slivers) > 0:
            descripMsg = "%s on %d slivers in slice %s" % (action, len(slivers), urn)

        creds = _maybe_add_abac_creds(self.framework, slice_cred)
        args = [urnsarg, creds, action, options]
        self.logger.debug("Doing POA with urns %s, action %s, %d creds, and options %s", urnsarg, action, len(creds), options)

        # Get clients
        successCnt = 0
        retItem = dict()
        (clientList, message) = self._getclients()
        if len(clientList) == 0:
            msg = "No aggregate specified to submit %s request to. Use the -a argument." % op
            if self.opts.devmode:
                #  warn
                self.logger.warn(msg)
            else:
                self._raise_omni_error(msg)
        elif len(clientList) > 1 and len(slivers) > 0:
            # All slivers will go to all AMs. If not best effort, AM may fail the request if its
            # not a local sliver.
            #  # FIXME: Could partition slivers by AM URN?
            msg = "Will do %s %s at all %d AMs - some aggregates may fail the request if given slivers not from that aggregate." % (op, descripMsg, len(clientList))
            if self.opts.geni_best_effort:
                self.logger.info(msg)
            else:
                self.logger.warn(msg + " Consider running with --best-effort in future.")

        # Do poa action on each client
        for client in clientList:
            self.logger.info("%s %s at %s", op, descripMsg, client.url)
            try:
                ((result, message), client) = self._api_call(client,
                                                  ("PerformOperationalAction %s at %s" % (descripMsg, client.url)),
                                                  op,
                                                  args)
            except BadClientException, bce:
                if bce.validMsg and bce.validMsg != '':
                    retVal += bce.validMsg + ". "
                else:
                    retVal += "Skipped aggregate %s. (Unreachable? Doesn't speak AM API v%d? Check the log messages, and try calling 'getversion' to check AM status and API versions supported.).\n" % (client.url, self.opts.api_version)
                if len(clientList) == 1:
                    self._raise_omni_error("\nPerformOperationalAction failed: " + retVal)
                continue

            retItem[ client.url ] = result
            (realresult, message) = self._retrieve_value(result, message, self.framework)

            if realresult is None:
                # Failure
                if message is None or message.strip() == "":
                    message = "(no reason given)"
                msg = "PerformOperationalAction %s at %s failed: %s \n" % (descripMsg, client.url, message)
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
                if isinstance(realresult, dict):
                    prettyResult = json.dumps(realresult, ensure_ascii=True, indent=2)
                else:
                    prettyResult = pprint.pformat(realresult)
                header="PerformOperationalAction result for %s at AM URL %s" % (descripMsg, client.url)
                filename = None
                if self.opts.output:
                    filename = self._construct_output_filename(slicename, client.url, client.urn, "poa-" + action, ".json", len(clientList))
                    #self.logger.info("Writing result of poa %s at AM: %s to file %s", descripMsg, client.url, filename)
                self._printResults(header, prettyResult, filename)
                retVal += "PerformOperationalAction %s was successful." % descripMsg
                if len(missingSlivers) > 0:
                    retVal += " - with %d missing slivers?!" % len(missingSlivers)
                if len(sliverFails.keys()) > 0:
                    retVal += " - with %d slivers reporting errors!" % len(sliverFails.keys())
                if filename:
                    retVal += " Saved results at AM %s to file %s. \n" % (client.url, filename)
                else:
                    retVal += ' \n'
                if len(missingSlivers) == 0 and len(sliverFails.keys()) == 0:
                    successCnt += 1
        # Done loop over clients

        self.logger.debug("POA %s result: %s", descripMsg, json.dumps(retItem, indent=2))

        if len(clientList) == 0:
            retVal += "No aggregates at which to PerformOperationalAction %s. %s\n" % (descripMsg, message)
        elif len(clientList) > 1:
            retVal += "Performed Operational Action %s at %d out of %d aggregates.\n" % (descripMsg, successCnt, len(clientList))
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
        - Each URL given in an -a argument or URL listed under that given
        nickname in omni_config, if provided, ELSE
        - List of URLs given in omni_config aggregates option, if provided, ELSE
        - List of URNs and URLs provided by the selected clearinghouse

        Note that per the AM API expiration times will be timezone aware.
        Unqualified times are assumed to be in UTC.
        Note that the expiration time cannot be past your slice expiration
        time (see renewslice). Some aggregates will
        not allow you to _shorten_ your sliver expiration time.

        -V# API Version #
        --devmode: Continue on error if possible
        -l to specify a logging config file
        --logoutput <filename> to specify a logging output filename
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
        (time, time_with_tz, time_string) = self._datetimeFromString(ds, slice_exp, name)

        self.logger.info('Renewing Sliver %s until %s (UTC)' % (name, time_with_tz))

        creds = _maybe_add_abac_creds(self.framework, slice_cred)

        options = None
        args = [urn, creds, time_string]
#--- AM API version specific
        if self.opts.api_version >= 2:
            # Add the options dict
            options = dict()
            args.append(options)

        self.logger.debug("Doing renewsliver with urn %s, %d creds, time %s, options %r", urn, len(creds), time_string, options)

        # Run renew at each client
        successCnt = 0
        successList = []
        failList = []
        (clientList, message) = self._getclients()
        op = "RenewSliver"
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
                    retVal += "Skipped aggregate %s. (Unreachable? Doesn't speak AM API v%d? Check the log messages, and try calling 'getversion' to check AM status and API versions supported.).\n" % (client.url, self.opts.api_version)
                if len(clientList) == 1:
                    self._raise_omni_error("\nRenewSliver failed: " + retVal)
                continue

            # Get the boolean result out of the result (accounting for API version diffs, ABAC)
            (res, message) = self._retrieve_value(res, message, self.framework)

            if not res:
                prStr = "Failed to renew sliver %s on %s (%s) (got result '%s')" % (urn, client.urn, client.url, res)
                if message != "":
                    if not prStr.endswith('.'):
                        prStr += '.'
                    prStr += " " + message
                else:
                    prStr += " (no reason given)"
                if len(clientList) == 1:
                    retVal += prStr + "\n"
                self.logger.warn(prStr)
                failList.append( client.url )
            else:
                prStr = "Renewed sliver %s at %s (%s) until %s (UTC)" % (urn, client.urn, client.url, time_with_tz.isoformat())
                self.logger.info(prStr)
                if len(clientList) == 1:
                    retVal += prStr + "\n"
                successCnt += 1
                successList.append( client.url )
        if len(clientList) == 0:
            retVal += "No aggregates on which to renew slivers for slice %s. %s\n" % (urn, message)
        elif len(clientList) > 1:
            retVal += "Renewed slivers on %d out of %d aggregates for slice %s until %s (UTC)\n" % (successCnt, len(clientList), urn, time_with_tz)
        return retVal, (successList, failList)
    # End of renewsliver

    def renew(self, args):
        """AM API Renew <slicename> <new expiration time in UTC
        or with a timezone>
        For use with AM API v3+. Use RenewSliver() in AM API v1&2.
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

        Sample usage:
        Renew slivers in slice myslice to the given time; fail the call if all slivers cannot be renewed to this time
        omni.py -V3 -a http://myaggregate/url renew myslice 20120909

        Renew slivers in slice myslice to the given time; any slivers that cannot be renewed to this time, stay as they were, while others are renewed
        omni.py -V3 -a http://myaggregate/url --best-effort renew myslice 20120909

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
        (time, time_with_tz, time_string) = self._datetimeFromString(ds, slice_exp, name)

        self.logger.info('Renewing Slivers in slice %s until %s (UTC)' % (name, time_with_tz))

        creds = _maybe_add_abac_creds(self.framework, slice_cred)

        urnsarg, slivers = self._build_urns(urn)

        descripMsg = "slivers in slice %s" % urn
        if len(slivers) > 0:
            descripMsg = "%d slivers in slice %s" % (len(slivers), urn)

        op = 'Renew'
        args = [urnsarg, creds, time_string]
        # Add the options dict
        options = self._build_options(op, None)
        args.append(options)

        self.logger.debug("Doing renew with urns %s, %d creds, time %s, options %r", urnsarg, len(creds), time_string, options)

        # Call renew at each client
        successCnt = 0
        (clientList, message) = self._getclients()
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
                    retVal += "Skipped aggregate %s. (Unreachable? Doesn't speak AM API v%d? Check the log messages, and try calling 'getversion' to check AM status and API versions supported.).\n" % (client.url, self.opts.api_version)
                if len(clientList) == 1:
                    self._raise_omni_error("\nRenew failed: " + retVal)
                continue
            retItem[client.url] = res

            # Get the boolean result out of the result (accounting for API version diffs, ABAC)
            (res, message) = self._retrieve_value(res, message, self.framework)

            if res is None:
                prStr = "Failed to renew %s on %s (%s)" % (descripMsg, client.urn, client.url)
                if message != "":
                    prStr += ": " + message
                else:
                    prStr += " (no reason given)"
                if len(clientList) == 1:
                    retVal += prStr + "\n"
                self.logger.warn(prStr)
            else:
                prStr = "Renewed %s at %s (%s) until %s (UTC)" % (descripMsg, client.urn, client.url, time_with_tz.isoformat())
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
                        if time == requestedExpiration or time - requestedExpiration < timedelta.resolution:
                            continue
                        firstTime = time
                        firstCount = len(sliverExps[time])
                        break
                    self.logger.warn("Slivers do not all expire as requested: %d as requested (%r), but %d expire on %r, and others at %d other times", expectedCount, time_with_tz.isoformat(), firstCount, firstTime.isoformat(), len(orderedDates) - 2)

                # Save results
                if isinstance(res, dict):
                    prettyResult = json.dumps(res, ensure_ascii=True, indent=2)
                else:
                    prettyResult = pprint.pformat(res)
                header="Renewed %s at AM URL %s" % (descripMsg, client.url)
                filename = None
                if self.opts.output:
                    filename = self._construct_output_filename(name, client.url, client.urn, "renewal", ".json", len(clientList))
                #self.logger.info("Writing result of renew for slice: %s at AM: %s to file %s", name, client.url, filename)
                self._printResults(header, prettyResult, filename)
                if filename:
                    retVal += "Saved renewal on %s at AM %s to file %s. \n" % (descripMsg, client.url, filename)
                if len(clientList) == 1:
                    retVal += prStr + "\n"
                if len(sliverFails.keys()) == 0 and len(missingSlivers) == 0:
                    successCnt += 1
        # End of loop over clients

        if len(clientList) == 0:
            retVal += "No aggregates on which to renew slivers for slice %s. %s\n" % (urn, message)
        elif len(clientList) > 1:
            retVal += "Renewed slivers on %d out of %d aggregates for slice %s until %s (UTC)\n" % (successCnt, len(clientList), urn, time_with_tz)
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
        # Query status at each client
        (clientList, message) = self._getclients()
        if len(clientList) > 0:
            self.logger.info('Status of Slice %s:' % urn)

            creds = _maybe_add_abac_creds(self.framework, slice_cred)

            args = [urn, creds]
            options = None
            # API version specific
            if self.opts.api_version >= 2:
                # Add the options dict
                options = dict()
                args.append(options)
            self.logger.debug("Doing sliverstatus with urn %s, %d creds, options %r", urn, len(creds), options)
        else:
            prstr = "No aggregates available to get slice status at: %s" % message
            retVal += prstr + "\n"
            self.logger.warn(prstr)

        op = 'SliverStatus'
        msg = "%s of %s at " % (op, urn)

        # Call SliverStatus on each client
        for client in clientList:
            try:
                ((status, message), client) = self._api_call(client,
                                                   msg + str(client.url),
                                                   op, args)
            except BadClientException, bce:
                if bce.validMsg and bce.validMsg != '':
                    retVal += bce.validMsg + ". "
                else:
                    retVal += "Skipped aggregate %s. (Unreachable? Doesn't speak AM API v%d? Check the log messages, and try calling 'getversion' to check AM status and API versions supported.).\n" % (client.url, self.opts.api_version)
                if len(clientList) == 1:
                    self._raise_omni_error("\nSliverStatus failed: " + retVal)
                continue

            # Get the dict status out of the result (accounting for API version diffs, ABAC)
            (status, message) = self._retrieve_value(status, message, self.framework)

            if status:
                if not isinstance(status, dict):
                    # malformed sliverstatus return
                    self.logger.warn('Malformed sliver status from AM %s. Expected struct, got type %s.' % (client.url, status.__class__.__name__))
                    # FIXME: Add something to retVal that the result was malformed?
                    if isinstance(status, str):
                        prettyResult = str(status)
                    else:
                        prettyResult = pprint.pformat(status)
                else:
                    prettyResult = json.dumps(status, ensure_ascii=True, indent=2)
                    if status.has_key('geni_status'):
                        msg = "Slice %s at AM %s has overall SliverStatus: %s"% (urn, client.url, status['geni_status'])
                        self.logger.info(msg)
                        retVal += msg + ".\n "
                        # FIXME: Do this even if many AMs?

                # Save/print out result
                header="Sliver status for Slice %s at AM URL %s" % (urn, client.url)
                filename = None
                if self.opts.output:
                    filename = self._construct_output_filename(name, client.url, client.urn, "sliverstatus", ".json", len(clientList))
                    #self.logger.info("Writing result of sliverstatus for slice: %s at AM: %s to file %s", name, client.url, filename)

                self._printResults(header, prettyResult, filename)
                if filename:
                    retVal += "Saved sliverstatus on %s at AM %s to file %s. \n" % (name, client.url, filename)
                retItem[ client.url ] = status
                successCnt+=1
            else:
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
                retVal += "\nFailed to get SliverStatus on %s at AM %s: %s\n" % (name, client.url, message)
        # End of loop over clients

        # FIXME: Return the status if there was only 1 client?
        if len(clientList) > 0:
            retVal += "Returned status of slivers on %d of %d possible aggregates." % (successCnt, len(clientList))
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
        if len(clientList) > 0:
            self.logger.info('Status of Slice %s:' % urn)

            creds = _maybe_add_abac_creds(self.framework, slice_cred)

            urnsarg, slivers = self._build_urns(urn)
            args = [urnsarg, creds]
            # Add the options dict
            options = self._build_options('Status', None)
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
                    retVal += "Skipped aggregate %s. (Unreachable? Doesn't speak AM API v%d? Check the log messages, and try calling 'getversion' to check AM status and API versions supported.).\n" % (client.url, self.opts.api_version)
                if len(clientList) == 1:
                    self._raise_omni_error("\nStatus failed: " + retVal)
                continue

            retItem[client.url] = status
            # Get the dict status out of the result (accounting for API version diffs, ABAC)
            (status, message) = self._retrieve_value(status, message, self.framework)
            if not status:
                # FIXME: Put the message error in retVal?
                # FIXME: getVersion uses None as the value in this case. Be consistent
                fmt = "\nFailed to get Status on %s at AM %s: %s\n"
                if message is None or message.strip() == "":
                    message = "(no reason given)"
                retVal += fmt % (descripMsg, client.url, message)
                continue

            missingSlivers = self._findMissingSlivers(status, slivers)
            if len(missingSlivers) > 0:
                self.logger.warn("%d slivers from request missing in result?!", len(missingSlivers))
                self.logger.debug("%s", missingSlivers)

            # Summarize result
            if len(slivers) > 0:
                retct = str(len(slivers) - len(missingSlivers))
            else:
                retct = str(len(self._getSliverResultList(status)))
            retVal += "Retrieved Status on %s slivers in slice %s at %s:\n" % (retct, urn, client.url)

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
                firstCount = len(sliverExps[time])
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
                if len(slivers) == 1:
                    statusMsg += "Sliver is "
                else:
                    statusMsg += "All slivers are "
                statusMsg += "in allocation state %s.\n" % alloc_statuses.keys()[0]
            else:
                statusMsg += "  %d slivers have %d different allocation statuses" % (len(slivers), len(alloc_statuses.keys()))
                if 'geni_unallocated' in alloc_statuses:
                    statusMsg += "; some are geni_unallocated.\n"
                else:
                    if not statusMsg.endswith('.'):
                        statusMsg += '.'
                    statusMsg += "\n"
            if len(op_statuses) == 1:
                if len(slivers) == 1:
                    statusMsg += "  Sliver is "
                else:
                    statusMsg += "  All slivers are "
                statusMsg += "in operational state %s.\n" % op_statuses.keys()[0]
            else:
                statusMsg = "  %d slivers have %d different operational statuses" % (len(slivers), len(op_statuses.keys()))
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
                self.logger.warn('Malformed status from AM %s. Expected struct, got type %s.' % (client.url, status.__class__.__name__))
                # FIXME: Add something to retVal that the result was malformed?
                if isinstance(status, str):
                    prettyResult = str(status)
                else:
                    prettyResult = pprint.pformat(status)
            else:
                prettyResult = json.dumps(status, ensure_ascii=True, indent=2)

            header="Status for %s at AM URL %s" % (descripMsg, client.url)
            filename = None
            if self.opts.output:
                filename = self._construct_output_filename(name, client.url, client.urn, "status", ".json", len(clientList))
                #self.logger.info("Writing result of status for slice: %s at AM: %s to file %s", name, client.url, filename)
            self._printResults(header, prettyResult, filename)
            if filename:
                retVal += "Saved status on %s at AM %s to file %s. \n" % (descripMsg, client.url, filename)
            if len(missingSlivers) > 0:
                retVal += " - %d slivers missing from result!? \n" % len(missingSlivers)
            if len(sliverFails.keys()) > 0:
                retVal += " - %d slivers failed?! \n" % len(sliverFails.keys())
            retVal += statusMsg
            if len(missingSlivers) == 0 and len(sliverFails.keys()) == 0:
                successCnt+=1
        # End of loop over clients

        # FIXME: Return the status if there was only 1 client?
        if len(clientList) > 0:
            retVal += "Returned status of slivers on %d of %d possible aggregates." % (successCnt, len(clientList))
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

        args = [urn, creds]
        options = None
#--- API version specific
        if self.opts.api_version >= 2:
            # Add the options dict
            options = dict()
            args.append(options)

        self.logger.debug("Doing deletesliver with urn %s, %d creds, options %r", urn, len(creds), options)

        successList = []
        failList = []
        successCnt = 0
        (clientList, message) = self._getclients()
        op = 'DeleteSliver'
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
                ((res, message), client) = self._api_call(client,
                                                   msg + str(client.url),
                                                   op, args)
            except BadClientException, bce:
                if bce.validMsg and bce.validMsg != '':
                    retVal += bce.validMsg + ". "
                else:
                    retVal += "Skipped aggregate %s. (Unreachable? Doesn't speak AM API v%d? Check the log messages, and try calling 'getversion' to check AM status and API versions supported.).\n" % (client.url, self.opts.api_version)
                if len(clientList) == 1:
                    self._raise_omni_error("\nDeleteSliver failed: " + retVal)
                continue

            # Get the boolean result out of the result (accounting for API version diffs, ABAC)
            (res, message) = self._retrieve_value(res, message, self.framework)

            if res:
                prStr = "Deleted sliver %s on %s at %s" % (urn,
                                                           client.urn,
                                                           client.url)
                if len(clientList) == 1:
                    retVal = prStr
                self.logger.info(prStr)
                successCnt += 1
                successList.append( client.url )
            else:
                prStr = "Failed to delete sliver %s on %s at %s (got result '%s')" % (urn, client.urn, client.url, res)
                if message is None or message.strip() == "":
                    message = "(no reason given)"
                if not prStr.endswith('.'):
                    prStr += '.'
                prStr += " " + message
                self.logger.warn(prStr)
                if len(clientList) == 1:
                    retVal = prStr
                failList.append( client.url )
        if len(clientList) == 0:
            retVal = "No aggregates specified on which to delete slivers. %s" % message
        elif len(clientList) > 1:
            retVal = "Deleted slivers on %d out of a possible %d aggregates" % (successCnt, len(clientList))
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

        urnsarg, slivers = self._build_urns(urn)

        descripMsg = "slivers in slice %s" % urn
        if len(slivers) > 0:
            descripMsg = "%d slivers in slice %s" % (len(slivers), urn)

        args = [urnsarg, creds]
        # Add the options dict
        options = self._build_options('Delete', None)
        args.append(options)

        self.logger.debug("Doing delete with urns %s, %d creds, options %r",
                          urnsarg, len(creds), options)

        successCnt = 0
        (clientList, message) = self._getclients()

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
                    retVal += "Skipped aggregate %s. (Unreachable? Doesn't speak AM API v%d? Check the log messages, and try calling 'getversion' to check AM status and API versions supported.).\n" % (client.url, self.opts.api_version)
                if len(clientList) == 1:
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
                prStr = "Deleted %s on %s at %s" % (descripMsg,
                                                           client.urn,
                                                           client.url)
                if someSliversFailed:
                    prStr += " - but %d slivers are not fully de-allocated; check the return! " % len(badSlivers.keys())
                if len(missingSlivers) > 0:
                    prStr += " - but %d slivers from request missing in result!? " % len(missingSlivers)
                if len(sliverFails.keys()) > 0:
                    prStr += " = but %d slivers failed! " % len(sliverFails.keys())
                if len(clientList) == 1:
                    retVal = prStr + "\n"
                self.logger.info(prStr)

                # Construct print / save out result

                if not isinstance(realres, list):
                    # malformed describe return
                    self.logger.warn('Malformed delete result from AM %s. Expected list, got type %s.' % (client.url, realres.__class__.__name__))
                    # FIXME: Add something to retVal that the result was malformed?
                    if isinstance(realres, str):
                        prettyResult = str(realres)
                    else:
                        prettyResult = pprint.pformat(realres)
                else:
                    prettyResult = json.dumps(realres, ensure_ascii=True, indent=2)

                header="Deletion of %s at AM URL %s" % (descripMsg, client.url)
                filename = None
                if self.opts.output:
                    filename = self._construct_output_filename(name, client.url, client.urn, "delete", ".json", len(clientList))
                #self.logger.info("Writing result of delete for slice: %s at AM: %s to file %s", name, client.url, filename)
                self._printResults(header, prettyResult, filename)
                if filename:
                    retVal += "Saved deletion of %s at AM %s to file %s. \n" % (descripMsg, client.url, filename)

                if len(sliverFails.keys()) == 0:
                    successCnt += 1
            else:
                if message is None or message.strip() == "":
                    message = "(no reason given)"
                prStr = "Failed to delete %s on %s at %s: %s" % (descripMsg, client.urn, client.url, message)
                self.logger.warn(prStr)
                if len(clientList) == 1:
                    retVal = prStr
        # loop over all clients

        if len(clientList) == 0:
            retVal = "No aggregates specified on which to delete slivers. %s" % message
        elif len(clientList) > 1:
            retVal = "Deleted slivers on %d out of a possible %d aggregates" % (successCnt, len(clientList))
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

        args = [urn, creds]
        options = dict()
        if self.opts.api_version >= 2:
            # Add the options dict
            options = dict()
            args.append(options)

        self.logger.debug("Doing shutdown with urn %s, %d creds, options %r", urn, len(creds), options)

        #Call shutdown on each AM
        successCnt = 0
        successList = []
        failList = []
        retItem = dict()
        (clientList, message) = self._getclients()
        msg = "Shutdown %s on " % (urn)
        op = "Shutdown"
        for client in clientList:
            try:
                ((res, message), client) = self._api_call(client, msg + client.url, op, args)
            except BadClientException, bce:
                if bce.validMsg and bce.validMsg != '':
                    retVal += bce.validMsg + ". "
                else:
                    retVal += "Skipped aggregate %s. (Unreachable? Doesn't speak AM API v%d? Check the log messages, and try calling 'getversion' to check AM status and API versions supported.).\n" % (client.url, self.opts.api_version)
                if len(clientList) == 1:
                    self._raise_omni_error("\nShutdown Failed: " + retVal)
                continue

            retItem[client.url] = res
            # Get the boolean result out of the result (accounting for API version diffs, ABAC)
            (res, message) = self._retrieve_value(res, message, self.framework)

            if res:
                prStr = "Shutdown Sliver %s on AM %s at %s" % (urn, client.urn, client.url)
                self.logger.info(prStr)
                if len(clientList) == 1:
                    retVal = prStr
                successCnt+=1
                successList.append( client.url )
            else:
                prStr = "Failed to shutdown sliver %s on AM %s at %s" % (urn, client.urn, client.url) 
                if message is None or message.strip() == "":
                    message = "(no reason given)"
                if not prStr.endswith('.'):
                    prStr += '.'
                prStr += " " + message
                self.logger.warn(prStr)
                if len(clientList) == 1:
                    retVal = prStr
                failList.append( client.url )
        if len(clientList) == 0:
            retVal = "No aggregates specified on which to shutdown slice %s. %s" % (urn, message)
        elif len(clientList) > 1:
            retVal = "Shutdown slivers of slice %s on %d of %d possible aggregates" % (urn, successCnt, len(clientList))
        if self.opts.api_version < 3:
            return retVal, (successList, failList)
        else:
            return retVal, retItem
    # End of shutdown

    # End of AM API operations
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
            msg = "Got no api_version from getversion at %s? %s" % (client.url, message)
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
                        msg2 = " - but that URL appears invalid: '%s'" % e
                        self.logger.warn(" -- Cannot connect to that URL, skipping this aggregate")
                        retmsg = "Skipped AM %s: it claims to speak API v%d at a broken URL (%s)." % (client.url, configver, svers[str(configver)])
                        return (configver, None, retmsg)
                    newclient.urn = client.urn # Wrong urn?
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
        return (cver, None, ("Could not validate AM %s .. skipped" % client.url))
    # End of _checkValidClient

    def _maybeGetRSpecFromStruct(self, rspec):
        '''RSpec might be string of JSON, in which case extract the
        XML out of the struct.'''
        if "'geni_rspec'" in rspec or "\"geni_rspec\"" in rspec or '"geni_rspec"' in rspec:
            try:
                rspecStruct = json.loads(rspec, encoding='ascii', cls=DateTimeAwareJSONDecoder, strict=False)
                if rspecStruct and isinstance(rspecStruct, dict) and rspecStruct.has_key('geni_rspec'):
                    rspec = rspecStruct['geni_rspec']
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

    def _getRSpecOutput(self, rspec, slicename, urn, url, message, slivers=None):
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

        server = self._get_server_name(url, urn)

        # Create BODY
        if rspec and rspec_util.is_rspec_string( rspec, self.logger ):
            # This line seems to insert extra \ns - GCF ticket #202
#            content = rspec_util.getPrettyRSpec(rspec)
            content = string.replace(rspec, "\\n", '\n')
#            content = rspec
            if slicename:
                retVal = "Got Reserved resources RSpec from %s" % server
            else:
                retVal = "Got RSpec from %s" % server
        else:
            content = "<!-- No valid RSpec returned. -->"
            if rspec is not None:
                # FIXME: Diff for dev here?
                self.logger.warn("No valid RSpec returned: Invalid RSpec? Starts: %s...", str(rspec)[:min(40, len(rspec))])
                content += "\n<!-- \n" + rspec + "\n -->"
                if slicename:
                    retVal = "Invalid RSpec returned for slice %s from %s that starts: %s..." % (slicename, server, str(rspec)[:min(40, len(rspec))])
                else:
                    retVal = "Invalid RSpec returned from %s that starts: %s..." % (server, str(rspec)[:min(40, len(rspec))])
                if message:
                    self.logger.warn("Server said: %s", message)
                    retVal += "; Server said: %s" % message

            else:
                forslice = ""
                if slicename:
                    forslice = "for slice %s " % slicename
                serversaid = ""
                if message:
                    serversaid = ": %s" % message

                retVal = "No RSpec returned %sfrom %s%s" % (forslice, server, serversaid)
                self.logger.warn(retVal)
        return header, content, retVal

    def _writeRSpec(self, rspec, slicename, urn, url, message=None, clientcount=1):
        '''Write the given RSpec using _printResults.
        If given a slicename, label the output as a manifest.
        Use rspec_util to check if this is a valid RSpec, and to format the RSpec nicely if so.
        Do much of this using _getRSpecOutput
        Use _construct_output_filename to build the output filename.
        '''
        # return just filename? retVal?
        # Does this do logging? Or return what it would log? I think it logs, but....

        (header, content, retVal) = self._getRSpecOutput(rspec, slicename, urn, url, message)

        filename=None
        # Create FILENAME
        if self.opts.output:
            mname = "rspec"
            if slicename:
                mname = "manifest-rspec"
            filename = self._construct_output_filename(slicename, url, urn, mname, ".xml", clientcount)
            # FIXME: Could add note to retVal here about file it was saved to? For now, caller does that.

        # Create FILE
        # This prints or logs results, depending on whether filename is None
        self._printResults( header, content, filename)
        return retVal, filename
    # End of _writeRSpec

    def _get_users_arg(self):
        '''Get the users argument for SSH public keys to install from omni_config 'users' section.'''
        # Copy the user config and read the keys from the files into the structure
        slice_users = copy(self.config['users'])
        if len(slice_users) == 0:
            self.logger.warn("No users defined. No keys will be uploaded to support SSH access.")

        #slice_users = copy(self.omni_config['slice_users'])
        for user in slice_users:
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

            for key in user['keys'].split(','):
                try:
                    newkeys.append(file(os.path.expanduser(key.strip())).read())
                except Exception, exc:
                    self.logger.error("Failed to read user key from %s: %s" %(user['keys'], exc))
            user['keys'] = newkeys
            if len(newkeys) == 0:
                self.logger.warn("Empty keys for user %s", user['urn'])
            else:
                self.logger.debug("Newkeys: %r", newkeys)

#            # Now error check the URN. It has to match that in the cert
#            # for AMs of type pg with tag < Tag v4.240? or stable-20110420?
#            # FIXME: Complain if NO urn is that in the cert?
#            # Only do the complaint if there is a PG AM that is old?
#            # Or somehow hold of complaining until per AM we have an issue?
#            certurn = ''
#            try:
#                certurn = gid.GID(filename=self.framework.cert).get_urn()
#            except Exception, exc:
#                self.logger.warn("Failed to get URN from cert %s: %s", self.framework.cert, exc)
#            if certurn != user['urn']:
#                self.logger.warn("Keys MAY not be installed for user %s. In PG prior to stable-20110420, the user URN must match that in your certificate. Your cert has urn %s but you specified that user %s has URN %s. Try making your omni_config user have a matching URN.", user, certurn, user, user['urn'])
#                # FIXME: if len(slice_users) == 1 then use the certurn?

#        if len(slice_users) < 1:
#            self.logger.warn("No user keys found to be uploaded")
        return slice_users
    # End of _get_users_arg

    def _get_server_name(self, clienturl, clienturn):
        '''Construct a short server name from the AM URL and URN'''
        if clienturn and not clienturn.startswith("unspecified_AM_URN") and (not clienturn.startswith("http")):
            # construct hrn
            # strip off any leading urn:publicid:IDN
            if clienturn.find("IDN+") > -1:
                clienturn = clienturn[(clienturn.find("IDN+") + 4):]
            urnParts = clienturn.split("+")
            server = urnParts.pop(0)
            server = server.translate(string.maketrans(' .:', '---'))
        else:
            # remove all punctuation and use url
            server = self._filename_part_from_am_url(clienturl)
        return server

    def _construct_output_filename(self, slicename, clienturl, clienturn, methodname, filetype, clientcount):
        '''Construct a file name for omni command outputs; return that name.
        If --outputfile specified, use that.
        Else, overall form is [prefix-][slicename-]methodname-server.filetype
        filetype should be .xml or .json'''

        # Construct server bit. Get HRN from URN, else use url
        # FIXME: Use sfa.util.xrn.get_authority or urn_to_hrn?
        server = self._get_server_name(clienturl, clienturn)
        if self.opts.outputfile:
            filename = self.opts.outputfile
            if "%a" in self.opts.outputfile:
                # replace %a with server
                filename = string.replace(filename, "%a", server)
            elif clientcount > 1:
                # FIXME: How do we distinguish? Let's just prefix server
                filename = server + "-" + filename
            if "%s" in self.opts.outputfile:
                # replace %s with slicename
                if not slicename:
                    slicename = 'noslice'
                filename = string.replace(filename, "%s", slicename)
            return filename

        filename = methodname + "-" + server + filetype
#--- AM API specific
        if slicename:
            filename = slicename+"-" + filename
#--- 
        if self.opts.prefix and self.opts.prefix.strip() != "":
            filename  = self.opts.prefix.strip() + "-" + filename
        return filename

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

    def _printResults(self, header, content, filename=None):
        """Print header string and content string to file of given
        name. If filename is none, then log to info.
        If --tostdout option, then instead of logging, print to STDOUT.
        """
        cstart = 0
        # if content starts with <?xml ..... ?> then put the header after that bit
        if content is not None and content.find("<?xml") > -1:
            cstart = content.find("?>", content.find("<?xml") + len("<?xml"))+2
            # push past any trailing \n
            if content[cstart:cstart+2] == "\\n":
                cstart += 2
        # used by listresources
        if filename is None:
            if header is not None:
                if cstart > 0:
                    if not self.opts.tostdout:
                        self.logger.info(content[:cstart])
                    else:
                        print content[:cstart] + "\n"
                if not self.opts.tostdout:
                    # indent header a bit if there was something first
                    pre = ""
                    if cstart > 0:
                        pre = "  "
                    self.logger.info(pre + header)
                else:
                    # If cstart is 0 maybe still log the header so it
                    # isn't written to STDOUT and non-machine-parsable
                    if cstart == 0:
                        self.logger.info(header)
                    else:
                        print header + "\n"
            elif content is not None:
                if not self.opts.tostdout:
                    self.logger.info(content[:cstart])
                else:
                    print content[:cstart] + "\n"
            if content is not None:
                if not self.opts.tostdout:
                    # indent a bit if there was something first
                    pre = ""
                    if cstart > 0:
                        pre += "  "
                    self.logger.info(pre + content[cstart:])
                else:
                    print content[cstart:] + "\n"
        else:
            fdir = os.path.dirname(filename)
            if fdir and fdir != "":
                if not os.path.exists(fdir):
                    os.makedirs(fdir)
            with open(filename,'w') as file:
                self.logger.info( "Writing to '%s'"%(filename))
                if header is not None:
                    if cstart > 0:
                        file.write (content[:cstart] + '\n')
                    # this will fail for JSON output. 
                    # only write header to file if have xml like
                    # above, else do log thing per above
                    if cstart > 0:
                        file.write("  " + header )
                        file.write( "\n" )
                    else:
                        self.logger.info(header)
                elif cstart > 0:
                    file.write(content[:cstart] + '\n')
                if content is not None:
                    pre = ""
                    if cstart > 0:
                        pre += "  "
                    file.write( pre + content[cstart:] )
                    file.write( "\n" )
    # End of _printResults

    def _filename_part_from_am_url(self, url):
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
        elif server.endswith("/gapi"):
            server = server[:(server.index("/gapi"))]
        elif server.endswith(":12346"):
            server = server[:(server.index(":12346"))]

        # remove punctuation. Handle both unicode and ascii gracefully
        bad = u'!"#%\'()*+,-./:;<=>?@[\]^_`{|}~'
        if isinstance(server, unicode):
            table = dict((ord(char), unicode('-')) for char in bad)
        else:
            assert isinstance(server, str)
            table = string.maketrans(bad, '-' * len(bad))
        server = server.translate(table)
        if server.endswith('-'):
            server = server[:-1]
        return server

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

    def _getclients(self, ams=None):
        """Create XML-RPC clients for each aggregate (from commandline,
        else from config file, else from framework)
        Return them as a sequence.
        Each client has a urn and url. See _listaggregates for details.
        """
        clients = []
        (aggs, message) = _listaggregates(self)
        if aggs == {} and message != "":
            self.logger.warn('No aggregates found: %s', message)
            return (clients, message)

        for (urn, url) in aggs.items():
            client = make_client(url, self.framework, self.opts)
            client.urn = urn
            clients.append(client)

        return (clients, message)

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

    def _build_options(self, op, options):
        '''Add geni_best_effort and geni_end_time to options if supplied, applicable'''
        if not options or options is None:
            options = {}

        if self.opts.api_version >= 3 and self.opts.geni_end_time:
            if op in ('Allocate', 'Provision') or self.opts.devmode:
                if self.opts.devmode and not op in ('Allocate', 'Provision'):
                    self.logger.warn("Got geni_end_time for method %s but using anyhow", op)
                time = datetime.datetime.max
                try:
                    (time, time_with_tz, time_string) = self._datetimeFromString(self.opts.geni_end_time)
                    options["geni_end_time"] = time_string
                except Exception, exc:
                    msg = 'Couldnt parse geni_end_time from %s: %r' % (self.opts.geni_end_time, exc)
                    self.logger.warn(msg)
                    if self.opts.devmode:
                        self.logger.info(" ... passing raw geni_end_time")
                        options["geni_end_time"] = self.opts.geni_end_time


        if self.opts.api_version >= 3 and self.opts.geni_best_effort:
            # FIXME: What about Describe? Status?
            if op in ('Provision', 'Renew', 'Delete', 'PerformOperationalAction'):
                options["geni_best_effort"] = self.opts.geni_best_effort
            elif self.opts.devmode:
                self.logger.warn("Got geni_best_effort for method %s but using anyhow", op)
                options["geni_best_effort"] = self.opts.geni_best_effort

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
                self.logger.debug("entry in result had no 'geni_sliver'urn'")
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
                self.logger.debug("entry in result had no 'geni_sliver'urn'")
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
                self.logger.debug("entry in result had no 'geni_sliver'urn'")
                continue
            retSlivers.append(sliver['geni_sliver_urn'])

        for request in requestedSlivers:
            if not request or request.strip() == "":
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
        # retVal += " Next sliver expiration: %s" % orderedDates[0]

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
                self.logger.debug("entry in result had no 'geni_sliver'urn'")
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
                self.logger.debug("entry in result had no 'geni_sliver'urn'")
                continue
            if not sliver.has_key('geni_allocation_status'):
                self.logger.debug("Sliver %s missing 'geni_allocation_status'", sliver['geni_sliver_urn'])
                result[sliver['geni_sliver_urn']] = ""
            if sliver['geni_allocation_status'] != expectedState:
                result[sliver['geni_sliver_urn']] = sliver['geni_allocation_status']

        return result

    def _datetimeFromString(self, dateString, slice_exp = None, name=None):
        '''Get time, time_with_tz, time_string from the given string. Log/etc appropriately
        if given a slice expiration to limit by.
        Generally, use time_with_tz for comparisons and time_string to print or send in API Call.'''
        time = datetime.datetime.max
        try:
            if dateString is not None or self.opts.devmode:
                time = dateutil.parser.parse(dateString)
        except Exception, exc:
            msg = "Renew couldn't parse time from %s: %s" % (dateString, exc)
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
                self.logger.warn("Failed to convert %s to naive UTC: %r", dateString, exc)
                raise

        if slice_exp:
            # Compare requested time with slice expiration time
            if not name:
                name = "<unspecified>"
            if time > slice_exp:
                msg = 'Cannot renew sliver(s) in %s until %s UTC because it is after the slice expiration time %s UTC' % (name, time, slice_exp)
                if self.opts.devmode:
                    self.logger.warn(msg + ", but continuing...")
                else:
                    self._raise_omni_error(msg)
            elif time <= datetime.datetime.utcnow():
                if not self.opts.devmode:
                    # Syseng ticket 3011: User typo means their sliver expires.
                    # Instead either (a) raise an error, or (b) substitute something a
                    # few minutes in the future
                    self.logger.info('Sliver(s) in %s will be set to expire now' % name)
                    time = datetime.datetime.utcnow()
            else:
                self.logger.debug('Slice expires at %s UTC, at or after requested time %s UTC' % (slice_exp, time))

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
        tmp_client =  omnilib.xmlrpc.client.make_client(url, framework.key, framework.cert, opts.verbosessl)
    else:
        tmp_client = omnilib.xmlrpc.client.make_client(url, None, None)
    tmp_client.url = str(url)
    tmp_client.urn = ""
    return tmp_client
        

def _maybe_add_abac_creds(framework, cred):
    '''Construct creds list. If using ABAC then creds are ABAC creds. Else creds are the user cred or slice cred
    as supplied, as normal.'''
    if is_ABAC_framework(framework):
        creds = get_abac_creds(framework.abac_dir)
        creds.append(cred)
    else:
        creds = [cred]
    return creds

# FIXME: Use this frequently in experimenter mode, for all API calls
def _check_valid_return_struct(client, resultObj, message, call):
    '''Basic check that any API method returned code/value/output struct,
    producing a message with a proper error message'''
    if resultObj is None:
        # error
        message = "AM %s failed %s (empty): %s" % (client.url, call, message)
        return (None, message)
    elif not isinstance(resultObj, dict):
        # error
        message = "AM %s failed %s (returned %s): %s" % (client.url, call, resultObj, message)
        return (None, message)
    elif not resultObj.has_key('value'):
        message = "AM %s failed %s (no value: %s): %s" % (client.url, call, resultObj, message)
        return (None, message)
    elif not resultObj.has_key('code'):
        message = "AM %s failed %s (no code: %s): %s" % (client.url, call, resultObj, message)
        return (None, message)
    elif not resultObj['code'].has_key('geni_code'):
        message = "AM %s failed %s (no geni_code: %s): %s" % (client.url, call, resultObj, message)
        # error
        return (None, message)
    elif resultObj['code']['geni_code'] != 0:
        # error
        # This next line is experimenter-only maybe?
        message = "AM %s failed %s: %s" % (client.url, call, _append_geni_error_output(resultObj, message))
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
        if retStruct['code'].has_key('geni_code') and retStruct['code']['geni_code'] != 0:
            message2 = "Error from Aggregate: code " + str(retStruct['code']['geni_code'])
        amType = ""
        if retStruct['code'].has_key('am_type'):
            amType = retStruct['code']['am_type']
        if retStruct['code'].has_key('am_code') and retStruct['code']['am_code'] != 0:
            if message2 != "":
                if not message2.endswith('.'):
                    message2 += '.'
                message2 += " "
            message2 += "%s AM code: %s" % (amType, str(retStruct['code']['am_code']))
        if retStruct.has_key('output') and retStruct['output'] is not None and str(retStruct['output']).strip() != "":
            message2 += ": %s" % retStruct['output']
        if amType == 'protogeni' and retStruct['code'].has_key('protogeni_error_log'):
            message2 += " (PG error log: %s)" % retStruct['code']['protogeni_error_log']
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

