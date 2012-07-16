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
import string
import zlib

from omnilib.util import OmniError, NoSliceCredError, RefusedError, naiveUTC
from omnilib.util.dossl import _do_ssl
from omnilib.util.abac import get_abac_creds, save_abac_creds, save_proof, \
        is_ABAC_framework
import omnilib.util.credparsing as credutils
import omnilib.util.handler_utils
from omnilib.util.handler_utils import _listaggregates, validate_url, _get_slice_cred, _derefAggNick, \
    _print_slice_expiration
from omnilib.util.json_encoding import DateTimeAwareJSONEncoder, DateTimeAwareJSONDecoder
import omnilib.xmlrpc.client

from geni.util import rspec_util 

class AMCallHandler(object):
    def __init__(self, framework, config, opts):
        self.framework = framework
        self.logger = config['logger']
        self.omni_config = config['omni']
        self.config = config
        self.opts = opts
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
        if len(args) == 0:
            self._raise_omni_error('Insufficient number of arguments - Missing command to run')
        
        call = args[0].lower()
        # disallow calling private methods
        if call.startswith('_'):
            return
        if not hasattr(self,call):
            self._raise_omni_error('Unknown function: %s' % call)
        return getattr(self,call)(args[1:])

    # ------- AM API methods and direct support methods follow

    # FIXME: This method manipulates the message. Need to separate Dev/Exp
    # Also, it marks whether it used the cache through the message. Is there a better way?
    def _do_getversion(self, client):
        '''Pull GetVersion for this client from cache; otherwise actually call GetVersion if this
        client wasn't in the cache, the options say not to use the cache, or the cache is too old.

        If we actually called GetVersion:
        Construct full error message including string version of code/output slots.
        Then cache the result.
        If we got the result from the cache, set the message to say so.
        '''
        cachedVersion = self._get_cached_getversion(client)
        if self.opts.noGetVersionCache or cachedVersion is None or (self.opts.GetVersionCacheOldestDate and cachedVersion['timestamp'] < self.opts.GetVersionCacheOldestDate):
            self.logger.debug("Actually calling GetVersion")
            (thisVersion, message) = _do_ssl(self.framework, None, "GetVersion at %s" % (str(client.url)), client.GetVersion)

            # This next line is experimter-only maybe?
            message = _append_geni_error_output(thisVersion, message)

            # Cache result, even on error (when we note the error message)
            self._cache_getversion(client, thisVersion, message)
        else:
            self.logger.debug("Pulling GetVersion from cache")
            thisVersion = cachedVersion['version']
            message = "From Cached result from %s" % cachedVersion['timestamp']
        return (thisVersion, message)

    def _do_getversion_output(self, thisVersion, client, message):
        '''Write GetVersion output to file or log depending on options.
        Return a retVal string to print that we saved it to a file, if that's what we did.
        '''
        # FIXME only print 'peers' on verbose? (Or is peers gone now?)
        pp = pprint.PrettyPrinter(indent=4)
        prettyVersion = pp.pformat(thisVersion)
        header = "AM URN: %s (url: %s) has version:" % (client.urn, client.url)
        if message:
            header += " (" + message + ")"
        filename = None
        if self.opts.output:
            # Create HEADER
            # But JSON cant have any
                    #header = None
            # Create filename
            filename = self._construct_output_filename(None, client.url, client.urn, "getversion", ".xml", 1)
            self.logger.info("Writing result of getversion at AM %s (%s) to file '%s'", client.urn, client.url, filename)
        # Create File
        # This logs or prints, depending on whether filename
        # is None
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

    # FIXME: This saves every time we add to the cache. Is that riht?
    def _cache_getversion(self, client, thisVersion, error=None):
        '''Add to Cache the GetVersion output for this client.
        If this was an error, don't over-write any existing good result, but record the error message

        This methods both loads and saves the cache from file
        '''
        # url, urn, timestamp, apiversion, rspecversions (type version, type version, ..), credtypes (type version, ..), single_alloc, allocate, last error and message
        res = {}
        if error:
            # On error, pretend this is old, to force refetch
            res['timestamp'] = datetime.datetime.min
        else:
            res['timestamp'] = datetime.datetime.utcnow()
        res['version'] = thisVersion
        res['urn'] = client.urn
        res['url'] = client.url
        res['error'] = error
        if self.GetVersionCache is None:
            # Read the file as serialized JSON
            self._load_getversion_cache()
        if error and self.GetVersionCache.has_key(client.url):
            # On error, leave existing data alone - just record the last error
            self.GetVersionCache[client.url]['lasterror'] = error
            self.logger.debug("Added GetVersion error output to cache")
        else:
            self.GetVersionCache[client.url] = res
            self.logger.debug("Added GetVersion success output to cache")

        # Write the file as serialized JSON
        self._save_getversion_cache()

    def _get_cached_getversion(self, client):
        '''Get GetVersion from cache or this client, if any.'''
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
        '''Get the actual GetVersion value - not the full struct - for this client.
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
            self.logger.info("Got client version: %s", message)
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
        (thisVersion, message) = self._do_and_check_getversion(client)
        if thisVersion is None:
            # error - return what the error check had
            return (thisVersion, message)
        elif thisVersion['geni_api'] == 1:
            versionSpot = thisVersion
        else:
            versionSpot = thisVersion['value']
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
        '''Get the supported API version for this client (from GetVersion)'''
        (res, message) = self._get_getversion_key(client, 'geni_api')
        if res is None:
            self.logger.warning("Couldnt get api version supported from GetVersion: %s" % message)
        # Return is an int API version
        return (res, message)

    def _get_api_versions(self, client):
        '''Get the supported API versions and URLs for this client (from GetVersion)'''
        (res, message) = self._get_getversion_key(client, 'geni_api_versions')
        if res is None:
            self.logger.warning("Couldnt get api versions supported from GetVersion: %s" % message)
        # Return is a dict: Int API version -> string URL of AM
        return (res, message)

    def _get_advertised_rspecs(self, client):
        '''Get the supported advertisement rspec versions for this client (from GetVersion)'''
        (ads, message) = self._get_getversion_key(client, 'ad_rspec_versions')
        if ads is None:
            if message and "has no key" in message:
                (ads, message) = self._get_getversion_key(client, 'geni_ad_rspec_versions')

        if ads is None:
            self.logger.warning("Couldnt get Advertised supported RSpec versions from GetVersion so can't do ListResources: %s" % message)

        # Return is array of dicts with type, version, schema, namespace, array of extensions 
        return (ads, message)

    def _get_request_rspecs(self, client):
        '''Get the supported request rspec versions for this client (from GetVersion)'''
        (ads, message) = self._get_getversion_key(client, 'request_rspec_versions')
        if ads is None:
            if message and "has no key" in message:
                (ads, message) = self._get_getversion_key(client, 'geni_request_rspec_versions')

        if ads is None:
            self.logger.warning("Couldnt get Request supported RSpec versions from GetVersion: %s" % message)

        # Return is array of dicts with type, version, schema, namespace, array of extensions 
        return (ads, message)

    def _get_cred_versions(self, client):
        '''Get the supported credential types for this client (from GetVersion)'''
        (res, message) = self._get_getversion_key(client, 'geni_credential_types')
        if res is None:
            self.logger.warning("Couldnt get credential types supported from GetVersion: %s" % message)
        # Return is array of dicts: geni_type, geni_version
        return (res, message)

    def _get_singlealloc_style(self, client):
        '''Get the supported single_allocation for this client (from GetVersion)'''
        (res, message) = self._get_getversion_key(client, 'geni_single_allocation')
        if res is None:
            self.logger.debug("Couldnt get single_allocation mode supported from GetVersion; will use default of False: %s" % message)
            res = False
        # return is boolean
        return (res, message)

    def _get_alloc_style(self, client):
        '''Get the supported geni_allocate allocation style for this client (from GetVersion)'''
        (res, message) = self._get_getversion_key(client, 'geni_allocate')
        if res is None:
            self.logger.debug("Couldnt get allocate style supported from GetVersion; will use default of 'geni_single': %s" % message)
            res = 'geni_single'
        # Return is string: geni_single, geni_disjoint, or geni_many
        return (res, message)

    # FIXME: Must still factor dev vs exp
    # For experimenters: If exactly 1 AM, then show only the value slot, formatted nicely, printed to STDOUT.
    # If it fails, show only why
    # If saving to file, print out 'saved to file <foo>', or the error if it failed
    # If querying multiple, then print a header for each before printing to STDOUT, otherwise like above.

    # For developers, maybe leave it like this? Print whole struct not just the value?
    def getversion(self, args):
        """AM API GetVersion

        Aggregates queried:
        - Single URL given in -a argument or URL listed under that given
        nickname in omni_config, if provided, ELSE
        - List of URLs given in omni_config aggregates option, if provided, ELSE
        - List of URNs and URLs provided by the selected clearinghouse

        -o Save result (JSON format) in per-Aggregate files
        -p (used with -o) Prefix for resulting version information files
        If not saving results to a file, they are logged.
        If --tostdout option, then instead of logging, print to STDOUT.

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
            #FIXME: This makes the getversion output be only the value
            # But for developers, I want the whole thing I think
            (thisVersion, message) = self._get_getversion_value(client)

            # Method specific result handling
            version[ client.url ] = thisVersion

            # Per client result outputs:
            if version[client.url] is None:
                # FIXME: SliverStatus sets these to False. Should this for consistency?
                self.logger.warn( "URN: %s (url:%s) call failed: %s\n" % (client.urn, client.url, message) )
                retVal += "Cannot GetVersion at %s: %s\n" % (client.url, message)
            else:
                successCnt += 1
                retVal += self._do_getversion_output(thisVersion, client, message)
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

    def _listresources(self, args):
        """Queries resources on various aggregates.
        
        Takes an optional slicename.
        Uses optional aggregate option or omni_config aggregate param.
        (See _listaggregates)

        Doesn't care how many aggregates that you query.

        If you specify a required Ad RSpec type and version (both strings. Use the -t option)
        then it skips any AM that doesn't advertise (in GetVersion)
        that it supports that format.

        Returns a dictionary of rspecs with the following format:
           rspecs[(urn, url)] = decompressed rspec
           AND a string describing the result.
        On error the dictionary is None and the message explains.
        """

        # rspecs[(urn, url)] = decompressed rspec
        rspecs = {}
        options = {}
        
        options['geni_compressed'] = self.opts.geni_compressed
        options['geni_available'] = self.opts.geni_available

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

        # Get the credential for this query
        if slicename is None or slicename == "":
            slicename = None
            cred = None
            (cred, message) = self.framework.get_user_cred()
            if cred is None:
#--- Dev mode allow doing the call anyhow?
                self.logger.error('Cannot list resources: Could not get user credential')
                if not self.opts.devmode:
                    return (None, "Could not get user credential: %s" % message)
                else:
                    self.logger.info('... but continuing')
                    cred = ""
        else:
            (slicename, urn, cred, retVal, slice_exp) = self._args_to_slicecred(args, 1, "listresources")
            if cred is None or cred == "":
#--- Dev mode allow doing the call anyhow?
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
        # FIXME: What if got a message and still got some aggs?
        else:
            creds = _maybe_add_abac_creds(self.framework, cred)

        # Connect to each available GENI AM to list their resources
        for client in clientList:
            if cred is None:
                self.logger.debug("Have null credential in call to ListResources!")
            rspec = None

            (ver, newc) = self._checkValidClient(client)
            if newc is None:
                continue
            elif newc.url != client.url:
                client = newc
                if ver != self.opts.api_version:
                    self.logger.warn("Changing API version to %d. Is this going to work?", ver)
                    self.opts.api_version = ver

            self.logger.debug("Connecting to AM: %s at %s", client.urn, client.url)

#---
# In Dev mode, just use the requested type/version - don't check what is supported

            # If the user specified a specific rspec type and version,
            # then we ONLY get rspecs from each AM that is capable
            # of talking that type&version.
            # Note an alternative would have been to let the AM just
            # do whatever it likes to do if
            # you ask it to give you something it doesnt understand.
            if self.opts.rspectype:
                rtype = self.opts.rspectype[0]
                rver = self.opts.rspectype[1]
                self.logger.debug("Will request RSpecs only of type %s and version %s", rtype, rver)

                # Note this call uses the GetVersion cache, if available
                # If got a slicename, should we be using request rspecs to better match manifest support?
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
                        continue

                self.logger.debug("Got %d supported ad_rspec_versions", len(ad_rspec_version))
                # foreach item in the list that is the val
                match = False
                for availversion in ad_rspec_version:
                    if not (availversion.has_key('type') and availversion.has_key('version')):
                        self.logger.warning("AM getversion ad_rspec_version entry malformed: no type or no version")
                        continue

                    # version is also a string
                    if str(availversion['type']).lower().strip() == rtype.lower().strip() and str(availversion['version']).lower().strip() == str(rver).lower().strip():
                        # success
                        self.logger.debug("Found a matching supported type/ver: %s/%s", availversion['type'], availversion['version'])
                        match = True
                        rtype=availversion['type']
                        rver=availversion['version']
                        break
                # if no success
                if match == False:
                    # FIXME: Could or should we pick PGv2 if GENIv3 not there, and vice versa?

                    #   return error showing ad_rspec_versions
                    pp = pprint.PrettyPrinter(indent=4)
                    self.logger.warning("AM cannot provide Ad Rspec in requested version (%s %s) at AM %s [%s]. This AM only supports: \n%s", rtype, rver, client.urn, client.url, pp.pformat(ad_rspec_version))
                    if mymessage != "":
                        mymessage += ". "

                    if not self.opts.devmode:
                        mymessage = mymessage + "Skipped AM %s that didnt support required RSpec format %s %s" % (client.url, rtype, rver)
                        continue
                    else:
                        mymessage = mymessage + "AM %s didnt support required RSpec format %s %s, but continuing" % (client.url, rtype, rver)

#--- API version differences:
                if self.opts.api_version == 1:
                    options['rspec_version'] = dict(type=rtype, version=rver)
                else:
                    options['geni_rspec_version'] = dict(type=rtype, version=rver)

#--- Dev mode should not force supplying this option maybe?
            elif self.opts.api_version >= 2:
                # User did not specify an rspec type but did request version 2.
                # Make an attempt to do the right thing, otherwise bail and tell the user.
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
                        continue

                if len(ad_rspec_version) == 1:
                    # there is only one advertisement, so use it.
                    options['geni_rspec_version'] = dict(type=ad_rspec_version[0]['type'],
                                                         version=ad_rspec_version[0]['version'])
                else:
                    # FIXME: Could we pick GENI v3 if there, else PG v2?

                    # Inform the user that they have to pick.
                    ad_versions = [(x['type'], x['version']) for x in ad_rspec_version]
                    self.logger.warning("Please use the -t option to specify the desired RSpec type for AM %s as one of %r", client.url, ad_versions)
                    if mymessage != "":
                        mymessage += ". "
                    mymessage = mymessage + "AM %s supports multiple RSpec versions: %r" % (client.url, ad_versions)
                    if not self.opts.devmode:
                        continue
            # Done constructing options to ListResources
#-----

            self.logger.debug("Doing listresources with %d creds, options %r", len(creds), options)
            (resp, message) = _do_ssl(self.framework, None, ("List Resources at %s" % (client.url)), client.ListResources, creds, options)

            # Get the RSpec out of the result (accounting for API version diffs, ABAC)
            (rspec, message) = self._retrieve_value(resp, message, self.framework)

            # Per client result saving
            if not rspec is None:
                successCnt += 1
                if options.get('geni_compressed', False):
                    try:
                        rspec = zlib.decompress(rspec.decode('base64'))
                    except Exception, e:
                        self.logger.error("Failed to decompress RSpec: %s", e);
                # In experimenter mode, maybe notice if the rspec appears compressed anyhow and try to decompress?
                elif not self.opts.devmode and rspec and not rspec_util.is_rspec_string(rspec, self.logger):
                    try:
                        rspec2 = zlib.decompress(rspec.decode('base64'))
                        if rspec2 and rspec_util.is_rspec_string(rspec2, self.logger):
                            rspec = rspec2
                    except Exception, e:
                        pass
                rspecs[(client.urn, client.url)] = rspec
            else:
                if mymessage != "":
                    mymessage += ". "
                mymessage += "No resources from AM %s: %s" % (client.url, message)

        if len(clientList) > 0:
            self.logger.info( "Listed resources on %d out of %d possible aggregates." % (successCnt, len(clientList)))
        return (rspecs, mymessage)

    def listresources(self, args):
        """Optional arg is a slice name limiting results. Call ListResources
        on 1+ aggregates and prints the rspec to stdout or to file.
        
        -o writes Ad RSpec to file instead of stdout; single file per aggregate.
        -p gives filename prefix for each output file
        If not saving results to a file, they are logged.
        If --tostdout option, then instead of logging, print to STDOUT.
        -t <type version>: Specify a required A RSpec type and version to return.
        It skips any AM that doesn't advertise (in GetVersion)
        that it supports that format.
        --slicecredfile says to use the given slicecredfile if it exists.

        File names will indicate the slice name, file format, and 
        which aggregate is represented.
        e.g.: myprefix-myslice-rspec-localhost-8001.xml

        If a slice name is supplied, then resources for that slice only 
        will be displayed.  In this case, the slice credential is usually retrieved from the Slice Authority. But
        with the --slicecredfile option it is read from that file, if it exists.

        Aggregates queried:
        - Single URL given in -a argument or URL listed under that given
        nickname in omni_config, if provided, ELSE
        - List of URLs given in omni_config aggregates option, if provided, ELSE
        - List of URNs and URLs provided by the selected clearinghouse
        """
#--- API version specific
        # An optional slice name might be specified.
        slicename = None
        if len(args) > 0:
            slicename = args[0].strip()
#---

        # check command line args
        if self.opts.output:
            self.logger.info("Saving output to a file.")

        # Query the various aggregates for resources
        # rspecs[(urn, url)] = decompressed rspec
        (rspecs, message) = self._listresources( args )
        numAggs = 0
        if rspecs is not None:
            numAggs = len(rspecs.keys())
        
        # handle empty case
        if not rspecs or rspecs == {}:
            if slicename:
                prtStr = "Got no resources on slice %s"%slicename 
            else:
                prtStr = "Got no resources" 
            if message is not None:
                prtStr = prtStr + ". " + message
            self.logger.info( prtStr )
            return prtStr, None

        # Loop over RSpecs and print them
        returnedRspecs = {}
        fileCtr = 0
        savedFileDesc = ""
        for ((urn,url), rspec) in rspecs.items():                        
            returnedRspecs[(urn,url)] = rspec
            self.logger.debug("Getting RSpec items for AM urn %s (%s)", urn, url)

            retVal, filename = self._writeRSpec(rspec, slicename, urn, url, None, len(rspecs))
            if filename:
                savedFileDesc += "Saved listresources RSpec at '%s' to file %s; " % (urn, filename)
        # End of loop over rspecs

        # Create RETURNS
        # FIXME: If numAggs is 1 then retVal should just be the rspec?
#--- AM API specific:
        if slicename:
            retVal = "Retrieved resources for slice %s from %d aggregate(s)."%(slicename, numAggs)
#---
        else:
            retVal = "Retrieved resources from %d aggregate(s)."%(numAggs)

        if numAggs > 0:
            retVal +="\n"
            if len(returnedRspecs.keys()) > 0:
                retVal += "Wrote rspecs from %d aggregate(s)" % numAggs
                if self.opts.output:
                    retVal +=" to %d file(s)"% len(rspecs)
                    retVal += "\n" + savedFileDesc
            else:
                retVal +="No Rspecs succesfully parsed from %d aggregate(s)" % numAggs
            retVal +="."

        retItem = returnedRspecs

        return retVal, retItem

# --- End ListResources, start CreateSliver

    def createsliver(self, args):
        """AM API CreateSliver call
        CreateSliver <slicename> <rspec file>
        Return on success the manifest RSpec(s)

        Slice name could be a full URN, but is usually just the slice name portion.
        Note that PLC Web UI lists slices as <site name>_<slice name>
        (e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

        -a Contact only the aggregate at the given URL, or with the given
         nickname that translates to a URL in your omni_config
        --slicecredfile Read slice credential from given file, if it exists
        -o Save result (manifest rspec) in per-Aggregate files
        -p (used with -o) Prefix for resulting manifest RSpec files
        If not saving results to a file, they are logged.
        If --tostdout option, then instead of logging, print to STDOUT.

        Slice credential is usually retrieved from the Slice Authority. But
        with the --slicecredfile option it is read from that file, if it exists.

        omni_config users section is used to get a set of SSH keys that
        should be loaded onto the remote node to allow SSH login, if the
        remote resource and aggregate support this.

        Note you likely want to check SliverStatus to ensure your resource
        comes up.
        And check the sliver expiration time: you may want to call RenewSliver.
        """

        # check command line args
        if not self.opts.aggregate:
            # the user must supply an aggregate.
            msg = 'Missing -a argument: specify an aggregate where you want the reservation.'
            # FIXME: parse the AM to reserve at from a comment in the RSpec
            # Calling exit here is a bit of a hammer.
            # Maybe there's a gentler way.
            self._raise_omni_error(msg)

        # prints slice expiration. Warns or raises an Omni error on problems
        (slicename, urn, slice_cred, retVal, slice_exp) = self._args_to_slicecred(args, 2, "CreateSliver", "and a request rspec filename")

        # Load up the user's request rspec
        rspecfile = None
        if not (self.opts.devmode and len(args) < 2):
            rspecfile = args[1]
        if rspecfile is None or not os.path.isfile(rspecfile):
#--- Dev mode should allow missing RSpec
            msg = 'File of resources to request missing: %s' % rspecfile
            if self.opts.devmode:
                self.logger.warn(msg)
            else:
                self._raise_omni_error(msg)

        # read the rspec into a string, and add it to the rspecs dict
        try:
            rspec = file(rspecfile).read()
        except Exception, exc:
#--- Should dev mode allow this?
            msg = 'Unable to read rspec file %s: %s' % (rspecfile, str(exc))
            if self.opts.devmode:
                rspec = ""
                self.logger.warn(msg)
            else:
                self._raise_omni_error(msg)

        # FIXME: We could try to parse the RSpec right here, and get the AM URL or nickname
        # out of the RSpec

        url, clienturn = _derefAggNick(self, self.opts.aggregate)

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
             include the arguments 
                   '-a %s'
             arguments again to act on this sliver.""" % (url, url))

        # Okay, send a message to the AM this resource came from
        result = None
        client = make_client(url, self.framework, self.opts)
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

        (ver, newc) = self._checkValidClient(client)
        if newc is None:
            return "Cannot CreateSliver at %s; it uses APIv%d, but you requested v%d" % (ver, self.opts.api_version), None
        elif newc.url != client.url:
            client = newc
            if ver != self.opts.api_version:
                self.logger.warn("Changing API version to %d. Is this going to work?", ver)
                self.opts.api_version = ver

        self.logger.debug("Doing createsliver with urn %s, %d creds, rspec of length %d starting '%s...', users struct %s, options %r", urn, len(creds), len(rspec), rspec[:min(100, len(rspec))], slice_users, options)
        (result, message) = _do_ssl(self.framework,
                                    None,
                                    ("Create Sliver %s at %s" % (urn, url)),
                                    client.CreateSliver,
                                    *args)

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
            retVal += ". " + prstr

        return retVal, result

    def renewsliver(self, args):
        """AM API RenewSliver <slicename> <new expiration time in UTC
        or with a timezone>
        Slice name could be a full URN, but is usually just the slice name portion.
        Note that PLC Web UI lists slices as <site name>_<slice name>
        (e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

        Slice credential is usually retrieved from the Slice Authority. But
        with the --slicecredfile option it is read from that file, if it exists.

        Aggregates queried:
        - Single URL given in -a argument or URL listed under that given
        nickname in omni_config, if provided, ELSE
        - List of URLs given in omni_config aggregates option, if provided, ELSE
        - List of URNs and URLs provided by the selected clearinghouse

        Note that per the AM API expiration times will be timezone aware.
        Unqualified times are assumed to be in UTC.
        Note that the expiration time cannot be past your slice expiration
        time (see renewslice). Some aggregates will
        not allow you to _shorten_ your sliver expiration time.
        """

        # prints slice expiration. Warns or raises an Omni error on problems
        (name, urn, slice_cred, retVal, slice_exp) = self._args_to_slicecred(args, 2, "RenewSliver", "and new expiration time in UTC")

#--- Should dev mode allow passing time as is?
        time = datetime.datetime.max
        try:
            if not (self.opts.devmode and len(args) < 2):
                time = dateutil.parser.parse(args[1])
        except Exception, exc:
            msg = 'renewsliver couldnt parse new expiration time from %s: %r' % (args[1], exc)
            if self.opts.devmode:
                self.logger.warn(msg)
            else:
                self._raise_omni_error(msg)

        # Convert to naive UTC time if necessary for ease of comparison
        try:
            time = naiveUTC(time)
        except:
            if self.opts.devmode:
                pass
            else:
                raise

        # Compare requested time with slice expiration time
        if time > slice_exp:
#--- Dev mode allow this
            msg = 'Cannot renew sliver %s until %s UTC because it is after the slice expiration time %s UTC' % (name, time, slice_exp)
            if self.opts.devmode:
                self.logger.warn(msg + ", but continuing...")
            else:
                self._raise_omni_error(msg)
        elif time <= datetime.datetime.utcnow():
#--- Dev mode allow earlier time
            if not self.opts.devmode:
                self.logger.info('Sliver %s will be set to expire now' % name)
                time = datetime.datetime.utcnow()
        else:
            self.logger.debug('Slice expires at %s UTC after requested time %s UTC' % (slice_exp, time))

        # Add UTC TZ, to have an RFC3339 compliant datetime, per the AM API
        time_with_tz = time.replace(tzinfo=dateutil.tz.tzutc())

        self.logger.info('Renewing Sliver %s until %s (UTC)' % (name, time_with_tz))

        # Note that the time arg includes UTC offset as needed
        time_string = time_with_tz.isoformat()
        if self.opts.no_tz:
            # The timezone causes an error in older sfa
            # implementations as deployed in mesoscale GENI. Strip
            # off the timezone if the user specfies --no-tz
            self.logger.info('Removing timezone at user request (--no-tz)')
            time_string = time_with_tz.replace(tzinfo=None).isoformat()

        creds = _maybe_add_abac_creds(self.framework, slice_cred)

        options = None
        args = [urn, creds, time_string]
#--- AM API version specific
        if self.opts.api_version >= 2:
            # Add the options dict
            options = dict()
            args.append(options)

        self.logger.debug("Doing renewsliver with urn %s, %d creds, time %s, options %r", urn, len(creds), time_string, options)

        successCnt = 0
        successList = []
        failList = []
        (clientList, message) = self._getclients()
        for client in clientList:
            (ver, newc) = self._checkValidClient(client)
            if newc is None:
                continue
            elif newc.url != client.url:
                client = newc
                if ver != self.opts.api_version:
                    self.logger.warn("Changing API version to %d. Is this going to work?", ver)
                    self.opts.api_version = ver

            (res, message) = _do_ssl(self.framework,
                                     None,
                                     ("Renew Sliver %s on %s" % (urn, client.url)),
                                     client.RenewSliver,
                                     *args)

            # Get the boolean result out of the result (accounting for API version diffs, ABAC)
            (res, message) = self._retrieve_value(res, message, self.framework)

            if not res:
                prStr = "Failed to renew sliver %s on %s (%s)" % (urn, client.urn, client.url)
                if message != "":
                    prStr += " " + message
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

    def sliverstatus(self, args):
        """AM API SliverStatus  <slice name>
        Slice name could be a full URN, but is usually just the slice name portion.
        Note that PLC Web UI lists slices as <site name>_<slice name>
        (e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

        Slice credential is usually retrieved from the Slice Authority. But
        with the --slicecredfile option it is read from that file, if it exists.

        Aggregates queried:
        - Single URL given in -a argument or URL listed under that given
        nickname in omni_config, if provided, ELSE
        - List of URLs given in omni_config aggregates option, if provided, ELSE
        - List of URNs and URLs provided by the selected clearinghouse

        -o Save result in per-Aggregate files
        -p (used with -o) Prefix for resulting files
        If not saving results to a file, they are logged.
        If --tostdout option, then instead of logging, print to STDOUT.
        """

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
#--- API version specific
            if self.opts.api_version >= 2:
                # Add the options dict
                options = dict()
                args.append(options)
            self.logger.debug("Doing sliverstatus with urn %s, %d creds, options %r", urn, len(creds), options)
        else:
            prstr = "No aggregates available to get slice status at: %s" % message
            retVal += prstr + "\n"
            self.logger.warn(prstr)

        for client in clientList:
            (ver, newc) = self._checkValidClient(client)
            if newc is None:
                continue
            elif newc.url != client.url:
                client = newc
                if ver != self.opts.api_version:
                    self.logger.warn("Changing API version to %d. Is this going to work?", ver)
                    self.opts.api_version = ver

            (status, message) = _do_ssl(self.framework,
                                        None,
                                        "Sliver status of %s at %s" % (urn, client.url),
                                        client.SliverStatus, *args)

            # Get the dict status out of the result (accounting for API version diffs, ABAC)
            (status, message) = self._retrieve_value(status, message, self.framework)

            if status:
                prettyResult = pprint.pformat(status)
                if not isinstance(status, dict):
                    # malformed sliverstatus return
                    self.logger.warn('Malformed sliver status from AM %s. Expected struct, got type %s.' % (client.url, status.__class__.__name__))
                    # FIXME: Add something to retVal that the result was malformed?
                    if isinstance(status, str):
                        prettyResult = str(status)
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
                retVal += "\nFailed to get SliverStatus on %s at AM %s: %s\n" % (name, client.url, message)

        # FIXME: Return the status if there was only 1 client?
        if len(clientList > 0):
            retVal += "Returned status of slivers on %d of %d possible aggregates." % (successCnt, len(clientList))
        return retVal, retItem
                
    def deletesliver(self, args):
        """AM API DeleteSliver <slicename>
        Slice name could be a full URN, but is usually just the slice name portion.
        Note that PLC Web UI lists slices as <site name>_<slice name>
        (e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

        Slice credential is usually retrieved from the Slice Authority. But
        with the --slicecredfile option it is read from that file, if it exists.

        Aggregates queried:
        - Single URL given in -a argument or URL listed under that given
        nickname in omni_config, if provided, ELSE
        - List of URLs given in omni_config aggregates option, if provided, ELSE
        - List of URNs and URLs provided by the selected clearinghouse
        """
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
            # Confirm this client speaks the right API Version.
            (ver, newc) = self._checkValidClient(client)
            if newc is None:
                continue
            elif newc.url != client.url:
                client = newc
                if ver != self.opts.api_version:
                    self.logger.warn("Changing API version to %d. Is this going to work?", ver)
                    self.opts.api_version = ver

            (res, message) = _do_ssl(self.framework,
                                     None,
                                     ("Delete Sliver %s on %s" % (urn, client.url)),
                                     client.DeleteSliver,
                                     *args)
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
                prStr = "Failed to delete sliver %s on %s at %s" % (urn, client.urn, client.url)
                if message != "":
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

    def shutdown(self, args):
        """AM API Shutdown <slicename>
        Slice name could be a full URN, but is usually just the slice name portion.
        Note that PLC Web UI lists slices as <site name>_<slice name>
        (e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

        Slice credential is usually retrieved from the Slice Authority. But
        with the --slicecredfile option it is read from that file, if it exists.

        Aggregates queried:
        - Single URL given in -a argument or URL listed under that given
        nickname in omni_config, if provided, ELSE
        - List of URLs given in omni_config aggregates option, if provided, ELSE
        - List of URNs and URLs provided by the selected clearinghouse
        """
        # prints slice expiration. Warns or raises an Omni error on problems
        (name, urn, slice_cred, retVal, slice_exp) = self._args_to_slicecred(args, 1, "Shutdown")

        creds = _maybe_add_abac_creds(self.framework, slice_cred)

        args = [urn, creds]
        options = None
        if self.opts.api_version >= 2:
            # Add the options dict
            options = dict()
            args.append(options)

        self.logger.debug("Doing shutdown with urn %s, %d creds, options %r", urn, len(creds), options)

        #Call shutdown on each AM
        successCnt = 0
        successList = []
        failList = []
        (clientList, message) = self._getclients()
        for client in clientList:
            (ver, newc) = self._checkValidClient(client)
            if newc is None:
                continue
            elif newc.url != client.url:
                client = newc
                if ver != self.opts.api_version:
                    self.logger.warn("Changing API version to %d. Is this going to work?", ver)
                    self.opts.api_version = ver

            (res, message) = _do_ssl(self.framework,
                                     None,
                                     "Shutdown %s on %s" % (urn, client.url),
                                     client.Shutdown,
                                     *args)
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
                if message != "":
                    prStr += ". " + message
                self.logger.warn(prStr)
                if len(clientList) == 1:
                    retVal = prStr
                failList.append( client.url )
        if len(clientList) == 0:
            retVal = "No aggregates specified on which to shutdown slice %s. %s" % (urn, message)
        elif len(clientList) > 1:
            retVal = "Shutdown slivers of slice %s on %d of %d possible aggregates" % (urn, successCnt, len(clientList))
        return retVal, (successList, failList)

    # End of AM API operations
    #######
    # Helper functions follow

    def _checkValidClient(self, client):
        '''Confirm this client speaks the right AM API version. 
        Return the API version spoken by this AM, and a client to talk to it.
        In particular, the returned client may be different, if the AM you asked about advertised
        a different URL as supporting your desired API Version.
        Check for None client to indicate an error, so you can bail.'''

        # Use the GetVersion cache
        # Make sure the client we are talking to speaks the expected AM API (or claims to)
        # What else would this do? See if it is reachable? We'll do that elsewhere
        # What should this return?
        # Is this where we could auto-switch client URLs to match the desired AM API version?
        # Return API version, client to use. May be new. If None, bail - error

        cver, message = self._get_this_api_version(client)
        configver = self.opts.api_version
        if cver and cver == configver:
            return (cver, client)
        elif not cver:
            self.logger.warn("Got no api_version from getversion at %s? %s", client.url, message)
            if not self.opts.devmode:
                self.logger.warn("... skipping this client")
                return (0, None)
            else:
                return (configver, client)

        svers, message = self._get_api_versions(client)
        if svers:
            if svers.has_key(configver):
                self.logger.warn("Requested API version %d, but client %s uses version %d. Same client talks API v%d at a different URL: %s", configver, client.url, cver, configver, svers[configver])
                # FIXME: Could do a makeclient with the corrected URL and return that client?
                if not self.opts.devmode:
                    newclient = make_client(svers[configver], self.framework, self.opts)
                    (ver, c) = self._checkValidClient(newclient)
                    if ver == configver and c.url == newclient.url and c is not None:
                        return (ver, c)
                self.logger.warn("... skipping this client")
                return (configver, None)
            else:
                self.logger.warn("Requested API version %d, but client %s uses version %d. This client does not talk that version. It advertises: %s", configver, client.url, cver, pprint.pformat(svers))
                # FIXME: If we're continuing, change api_version to be correct, or we will get errors
                if not self.opts.devmode:
                    self.logger.warn("Changing to use API version %d", cver)
                    return (cver, client)
                else:
                    # FIXME: Pick out the max API version supported at this client, and use that?
                    self.logger.warn("... skipping this client")
                    return (cver, None)
        else:
                self.logger.warn("Requested API version %d, but client %s uses version %d. This client does not advertise other versions.", configver, client.url, cver)
                # FIXME: If we're continuing, change api_version to be correct, or we will get errors
                if not self.opts.devmode:
                    self.logger.warn("Changing to use API version %d", cver)
                    return (cver, client)
                else:
                    self.logger.warn("... skipping this client")
                    return (cver, None)
        self.logger.warn("... skipping this client")
        return (cver, None)

    def _writeRSpec(self, rspec, slicename, urn, url, message=None, clientcount=1):
        '''Write the given RSpec using _printResults.
        If given a slicename, label the output as a manifest.
        Use rspec_util to check if this is a valid RSpec, and to format the RSpec nicely if so.
        Use _construct_output_filename to build the output filename.
        '''
        # return just filename? retVal?
        # Does this do logging? Or return what it would log? I think it logs, but....

        # Create HEADER
        if slicename:
            header = "Reserved resources for:\n\tSlice: %s\n\tat AM:\n\tURN: %s\n\tURL: %s\n" % (slicename, urn, url)
        else:
            header = "Resources at AM:\n\tURN: %s\n\tURL: %s\n" % (urn, url)
        header = "<!-- "+header+" -->"

        server = self._get_server_name(url, urn)

        # Create BODY
        if rspec and rspec_util.is_rspec_string( rspec, self.logger ):
            content = rspec_util.getPrettyRSpec(rspec)
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
                    retVal = "Invalid RSpec returned from %s that starts: %s..." % (slicename, server, str(rspec)[:min(40, len(rspec))])
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

    def _get_users_arg(self):
        '''Get the users argument for SSH public keys to install.'''
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

    def _get_server_name(self, clienturl, clienturn):
        '''Get a short server name from the AM URL and URN'''
        if clienturn and clienturn is not "unspecified_AM_URN" and (not clienturn.startswith("http")):
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
        '''Construct a name for omni command outputs; return that name.
        If outputfile specified, use that.
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
        Then pull the actual value out, checking for errors
        '''
        # Existing code is inconsistent on whether it is if code or elif code.
        # IE is the whole code struct shoved inside the success thing maybe?
        if not result:
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
#--- AM API version specific
            #FIXME Should that be if 'code' or elif 'code'?
            # FIXME: See _check_valid_return_struct
            if 'code' in result and isinstance(result['code'], dict) and 'geni_code' in result['code']:
                # AM API v2
                if result['code']['geni_code'] == 0:
                    value = result['value']
                # FIXME: More complete error code handling!
                elif result['code']['geni_code'] == 7: # REFUSED
                    self._raise_omni_error( result['output'], RefusedError)
                else:
                    if message:
                        message = result['output'] + " (" + message + ")"
                    else:
                        message = result['output']
                    value = None

        return (value, message)

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

#--- Dev mode allow this
        if len(args) == 0 or len(args) < num_args or (len(args) >=1 and (args[0] == None or args[0].strip() == "")):
            msg = '%s requires arg of slice name %s' % (methodname, otherargstring)
            if self.opts.devmode:
                self.logger.warn(msg + ", but continuging...")
                if len(args) == 0 or (len(args) >=1 and (args[0] == None or args[0].strip() == "")):
                    return ("", "", "", "", datetime.datetime.max)
            else:
                self._raise_omni_error(msg)

        name = args[0]

        # FIXME: catch errors getting slice URN to give prettier error msg?
        urn = self.framework.slice_name_to_urn(name)
        (slice_cred, message) = _get_slice_cred(self, urn)
        if slice_cred is None:
#--- Dev mode allow this
            msg = 'Cannot do %s for %s: Could not get slice credential: %s' % (methodname, urn, message)
            if self.opts.devmode:
                slice_cred = ""
                self.logger.warn(msg + ", but continuing....")
            else:
                self._raise_omni_error(msg, NoSliceCredError)

        # FIXME: Check that the returned slice_cred is actually for the given URN?
        # Or mayb do that in _get_slice_cred?

        slice_exp = None
        expd = True
        if not self.opts.devmode or slice_cred != "":
            expd, slice_exp = self._has_slice_expired(slice_cred)
        if slice_exp is None:
            slice_exp = datetime.datetime.min
        if expd:
#--- Dev mode allow this
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

    def _raise_omni_error( self, msg, err=OmniError ):
        self.logger.error( msg )
        raise err, msg

    def _printResults(self, header, content, filename=None):
        """Print header string and content string to file of given
        name. If filename is none, then log to info.
        If --tostdout option, then instead of logging, print to STDOUT.
        """
        cstart = 0
        # if content starts with <?xml ..... ?> then put the header after that bit
        if content is not None and content.find("<?xml") > -1:
            cstart = content.find("?>", content.find("<?xml") + len("<?xml"))+2
        # used by listresources
        if filename is None:
            if header is not None:
                if cstart > 0:
                    if not self.opts.tostdout:
                        self.logger.info(content[:cstart])
                    else:
                        print content[:cstart] + "\n"
                if not self.opts.tostdout:
                    self.logger.info(header)
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
                    self.logger.info(content[cstart:])
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
                        file.write( header )
                        file.write( "\n" )
                    else:
                        self.logger.info(header)
                elif cstart > 0:
                    file.write(content[:cstart] + '\n')
                if content is not None:
                    file.write( content[cstart:] )
                    file.write( "\n" )

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

        # strip standard url endings that dont tell us anything
        if server.endswith("/xmlrpc/am"):
            server = server[:(server.index("/xmlrpc/am"))]
        elif server.endswith("/xmlrpc"):
            server = server[:(server.index("/xmlrpc"))]
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
        tmp_client =  omnilib.xmlrpc.client.make_client(url, framework.key, framework.cert)
    else:
        tmp_client = omnilib.xmlrpc.client.make_client(url, None, None)
    tmp_client.url = str(url)
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
        if retStruct['code']['geni_code'] != 0:
            message2 = "Error: " . str(retStruct['code'])
            if retStruct.has_key('output'):
                message2 += ": %s" % retStruct['output']
            if message is not None:
                message += " (%s)" % message
            else:
                message = message2
    return message

