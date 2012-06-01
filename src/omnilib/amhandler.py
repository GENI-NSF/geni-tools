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
import xml.dom.minidom as md
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

# FIXME: Use this frequently in experimenter mode, for all API calls
def _check_valid_return_struct(client, thisVersion, message, call):
    '''Basic check that any API method returned code/value/output struct,
    producing a message with a proper error message'''
    if thisVersion is None:
        # error
        message = "AM %s failed %s (empty): %s" % (client.url, call, message)
        return (None, message)
    elif not isinstance(thisVersion, dict):
        # error
        message = "AM %s failed %s (returned %s): %s" % (client.url, call, thisVersion, message)
        return (None, message)
    elif not thisVersion.has_key('value'):
        message = "AM %s failed %s (no value: %s): %s" % (client.url, call, thisVersion, message)
        return (None, message)
    elif not thisVersion.has_key('code'):
        message = "AM %s failed %s (no code: %s): %s" % (client.url, call, thisVersion, message)
        return (None, message)
    elif not thisVersion['code'].has_key('geni_code'):
        message = "AM %s failed %s (no geni_code: %s): %s" % (client.url, call, thisVersion, message)
        # error
        return (None, message)
    elif thisVersion['code']['geni_code'] != 0:
        # error
        # This next line is experimenter-only maybe?
        message = "AM %s failed %s: %s" % (client.url, call, _append_geni_error_output(thisVersion, message))
        return (None, message)
    else:
        return (thisVersion, message)

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

# ----- Utility methods follow

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
            server = self._filename_part_from_am_url(client.url)
            filename = "getversion-"+server+".xml"
            if self.opts.prefix and self.opts.prefix.strip() != "":
                filename  = self.opts.prefix.strip() + "-" + filename
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
        if not os.path.exists(os.path.dirname(self.opts.getversionCacheName)):
            os.makedirs(os.path.dirname(self.opts.getversionCacheName))
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

    def _get_advertised_rspecs(self, client):
        '''Get the supported advertisement rspec versions for this client (from GetVersion)'''
        (ads, message) = self._get_getversion_key(client, 'ad_rspec_versions')
        if ads is None:
            if message and "has no key" in message:
                (ads, message) = self._get_getversion_key(client, 'geni_ad_rspec_versions')

        if ads is None:
            self.logger.warning("Couldnt get Advertised supported RSpec versions from GetVersion so can't do ListResources: %s" % message)

        return (ads, message)

    def _get_request_rspecs(self, client):
        '''Get the supported request rspec versions for this client (from GetVersion)'''
        (ads, message) = self._get_getversion_key(client, 'request_rspec_versions')
        if ads is None:
            if message and "has no key" in message:
                (ads, message) = self._get_getversion_key(client, 'geni_request_rspec_versions')

        if ads is None:
            self.logger.warning("Couldnt get Request supported RSpec versions from GetVersion: %s" % message)

        return (ads, message)

    def _get_cred_versions(self, client):
        '''Get the supported credential types for this client (from GetVersion)'''
        (res, message) = self._get_getversion_key(client, 'geni_credential_types')
        if res is None:
            self.logger.warning("Couldnt get credential types supported from GetVersion: %s" % message)
        return (res, message)

    def _get_singlealloc_style(self, client):
        '''Get the supported single_allocation for this client (from GetVersion)'''
        (res, message) = self._get_getversion_key(client, 'geni_single_allocation')
        if res is None:
            self.logger.debug("Couldnt get single_allocation mode supported from GetVersion; will use default of False: %s" % message)
            res = False
        return (res, message)

    def _get_alloc_style(self, client):
        '''Get the supported geni_allocate allocation style for this client (from GetVersion)'''
        (res, message) = self._get_getversion_key(client, 'geni_allocate')
        if res is None:
            self.logger.debug("Couldnt get allocate style supported from GetVersion; will use default of 'geni_single': %s" % message)
            res = 'geni_single'
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
        retVal = ""
        version = {}
        (clients, message) = self._getclients()
        successCnt = 0

        # Ensure GetVersion skips the cache, unless commandline option forces the cache
        if not self.opts.useGetVersionCache:
            self.opts.noGetVersionCache = True

        for client in clients:
            # Pulls from cache or caches latest, error checks return
            #FIXME: This makes the getversion output be only the value
            # But for developers, I want the whole thing I think
            (thisVersion, message) = self._get_getversion_value(client)

            version[ client.url ] = thisVersion

            if version[client.url] is None:
                self.logger.warn( "URN: %s (url:%s) call failed: %s\n" % (client.urn, client.url, message) )
                retVal += "Cannot GetVersion at %s: %s\n" % (client.url, message)
            else:
                successCnt += 1
                retVal += self._do_getversion_output(thisVersion, client, message)

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
                return (None, "Could not get user credential: %s" % message)
        else:
            urn = self.framework.slice_name_to_urn(slicename)
            (cred, message) = _get_slice_cred(self, urn)
            if cred is None:
                prstr = "Cannot list resources for slice %s: Could not get slice credential. " % urn
                if message != "":
                    prstr += message
                self.logger.error(prstr)
#--- Dev mode allow doing the call anyhow?
                return (None, prstr)

            self.logger.info('Gathering resources reserved for slice %s.' % slicename)

            options['geni_slice_urn'] = urn

        # We now have a credential
#----

        # Query each aggregate for resources
        successCnt = 0
        mymessage = ""
        (clientList, message) = self._getclients()
        if len(clientList) == 0 and message != "":
            mymessage = "No aggregates available to query: %s" % message
        # FIXME: What if got a message and still got some aggs?

        # Connect to each available GENI AM to list their resources
        for client in clientList:
            if cred is None:
                self.logger.debug("Have null credential in call to ListResources!")
            self.logger.debug("Connecting to AM: %s at %s", client.urn, client.url)
            rspec = None


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
                (ad_rspec_version, message) = self._get_advertised_rspecs(client)
                if ad_rspec_version is None:
                    if mymessage != "":
                        mymessage += ". "
                    mymessage = mymessage + message
                    continue

                self.logger.debug("Got %d supported ad_rspec_versions", len(ad_rspec_version))
                # foreach item in the list that is the val
                match = False
                for availversion in ad_rspec_version:
                    if not availversion.has_key('type') and availversion.has_key('version'):
                        self.logger.warning("AM getversion ad_rspec_version entry malformed: no type or version")
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
                    #   return error showing ad_rspec_versions
                    pp = pprint.PrettyPrinter(indent=4)
                    self.logger.warning("AM cannot provide Ad Rspec in requested version (%s %s) at AM %s [%s]. This AM only supports: \n%s", rtype, rver, client.urn, client.url, pp.pformat(ad_rspec_version))
                    if mymessage != "":
                        mymessage += ". "
                    mymessage = mymessage + "Skipped AM %s that didnt support required RSpec format %s %s" % (client.url, rtype, rver)
                    continue
#--- API version differences:
                if self.opts.api_version == 1:
                    options['rspec_version'] = dict(type=rtype, version=rver)
                else:
                    options['geni_rspec_version'] = dict(type=rtype, version=rver)
#--- Dev mode should not force supplying this option maybe?
            elif self.opts.api_version >= 2:
                # User did not specify an rspec type but did request version 2.
                # Make an attempt to do the right thing, otherwise bail and tell the user.
                (ad_rspec_version, message) = self._get_advertised_rspecs(client)
                if ad_rspec_version is None:
                    if mymessage != "":
                        mymessage += ". "
                    mymessage = mymessage + message
                    continue
                if len(ad_rspec_version) == 1:
                    # there is only one advertisement, so use it.
                    options['geni_rspec_version'] = dict(type=ad_rspec_version[0]['type'],
                                                         version=ad_rspec_version[0]['version'])
                else:
                    # Inform the user that they have to pick.
                    ad_versions = [(x['type'], x['version']) for x in ad_rspec_version]
                    self.logger.warning("Please use the -t option to specify the desired RSpec type for AM %s as one of %r", client.url, ad_versions)
                    if mymessage != "":
                        mymessage += ". "
                    mymessage = mymessage + "AM %s supports multiple RSpec versions: %r" % (client.url, ad_versions)
                    continue
#-----

            self.logger.debug("Doing listresources with options %r", options)
            # If ABAC then creds are ABAC creds. Else Creds are the user cred or slice cred
            # as retrieved above, as normal
            if is_ABAC_framework(self.framework):
                creds = get_abac_creds(self.framework.abac_dir)
                creds.append(cred)
            else:
                creds = [cred]

            (resp, message) = _do_ssl(self.framework, None, ("List Resources at %s" % (client.url)), client.ListResources, creds, options)

            # If ABAC return is a dict with proof and the regular return
            if isinstance(resp, dict):
                if is_ABAC_framework(self.framework):
                    if 'proof' in resp:
                        save_proof(self.framework.abac_log, resp['proof'])
                if 'manifest' in resp:
                    rspec = resp['manifest']
#--- AM API version specific
                elif 'code' in resp:
                    # AM API v2
                    if resp['code']['geni_code'] == 0:
                        rspec = resp['value']
                    else:
                        message = resp['output']
                        resp = None
            else:
                rspec = resp

            if not rspec is None:
                successCnt += 1
                if options.get('geni_compressed', False):
                    try:
                        rspec = zlib.decompress(rspec.decode('base64'))
                    except Exception, e:
                        self.logger.error("Failed to decompress RSpec: %s", e);
                # FIXME: In experimenter mode, maybe notice if the rspec appears compressed anyhow and try to decompress?
                rspecs[(client.urn, client.url)] = rspec
            else:
                if mymessage != "":
                    mymessage += ". "
                mymessage += "No resources from AM %s: %s" % (client.url, message)

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
            self.logger.debug("Getting RSpec items for AM urn %s (%s)", urn, url)

            # Create HEADER
#--- AM API specific
            if slicename is not None:
                header = "Resources for:\n\tSlice: %s\n\tat AM:\n\tURN: %s\n\tURL: %s\n" % (slicename, urn, url)
#---
            else:
                header = "Resources at AM:\n\tURN: %s\n\tURL: %s\n" % (urn, url)
            header = "<!-- "+header+" -->"

            # Create BODY
            returnedRspecs[(urn,url)] = rspec
            try:
                newl = ''
                if '\n' not in rspec:
                    newl = '\n'
                content = md.parseString(rspec).toprettyxml(indent=' '*2, newl=newl)
            except:
                content = rspec

            filename=None
            # Create FILENAME
            if self.opts.output:
                fileCtr += 1 
                # Instead of fileCtr: if have a urn, then use that to produce an HRN. Else
                # remove all punctuation and use URL
                server = str(fileCtr)
                if urn and urn is not "unspecified_AM_URN" and (not urn.startswith("http")):
                    # construct hrn
                    # strip off any leading urn:publicid:IDN
                    if urn.find("IDN+") > -1:
                        urn = urn[(urn.find("IDN+") + 4):]
                    urnParts = urn.split("+")
                    server = urnParts.pop(0)
                    server = server.translate(string.maketrans(' .:', '---'))
                else:
                    # remove all punctuation and use url
                    server = self._filename_part_from_am_url(url)
                filename = "rspec-" + server+".xml"
#--- AM API specific
                if slicename:
                    filename = slicename+"-" + filename
#--- 

                if self.opts.prefix and self.opts.prefix.strip() != "":
                    filename  = self.opts.prefix.strip() + "-" + filename

            # Create FILE
            # This prints or logs results, depending on filename None
            self._printResults( header, content, filename)
            if filename:
                savedFileDesc += "Saved listresources RSpec at '%s' to file %s; " % (urn, filename)
        # End of loop over rspecs

        # Create RETURNS
        # FIXME: If numAggs is 1 then retVal should just be the rspec?
#--- AM API specific:
        if slicename:
            retVal = "Retrieved resources for slice %s from %d aggregates."%(slicename, numAggs)
#---
        else:
            retVal = "Retrieved resources from %d aggregates."%(numAggs)
        if numAggs > 0:
            retVal +="\n"
            if len(returnedRspecs.keys()) > 0:
                retVal += "Wrote rspecs from %d aggregates" % numAggs
                if self.opts.output:
                    retVal +=" to %d files"% fileCtr
                    retVal += "\n" + savedFileDesc
            else:
                retVal +="No Rspecs succesfully parsed from %d aggregates" % numAggs
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

        retVal=''
#--- Should dev mode allow wrong arg count?
        if len(args) < 2 or args[0] == None or args[0].strip() == "":
            self._raise_omni_error('createsliver requires 2 args: slicename and an rspec filename')

        # check command line args
        if not self.opts.aggregate:
            # the user must supply an aggregate.
            msg = 'Missing -a argument: specify an aggregate where you want the reservation.'
            # FIXME: parse the AM to reserve at from a comment in the RSpec
            # Calling exit here is a bit of a hammer.
            # Maybe there's a gentler way.
            self._raise_omni_error(msg)

        name = args[0]
        # FIXME: catch errors getting slice URN to give prettier error msg?
        urn = self.framework.slice_name_to_urn(name.strip())
        (slice_cred, message) = _get_slice_cred(self, urn)
        if slice_cred is None:
#--- Dev mode allow missing slice cred
            self._raise_omni_error('Cannot create sliver %s: Could not get slice credential: %s' % (urn, message), NoSliceCredError)

#--- Dev vs Exp diffs here:
        expd, slice_exp = self._has_slice_expired(slice_cred)
        if expd:
            self._raise_omni_error('Cannot create sliver for slice %s: Slice has expired at %s' % (urn, slice_exp.isoformat()))

        retVal += _print_slice_expiration(self, urn, slice_cred)+"\n"
#---

        # Load up the user's request rspec
        specfile = args[1]
        if specfile is None or not os.path.isfile(specfile):
#--- Dev mode should allow missing RSpec
            self._raise_omni_error('File of resources to request missing: %s' % specfile)

        rspecs = None
        # read the rspec into a string, and add it to the rspecs dict
        rspecs = {}
        try:
            rspec = file(specfile).read()
            rspecs[_derefAggNick(self, self.opts.aggregate)[0]] = rspec
        except Exception, exc:
#--- Should dev mode allow this?
            self._raise_omni_error('Unable to read rspec file %s: %s'
                                   % (specfile, str(exc)))

        result = None
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
                    self._raise_omni_error("%s in omni_config is not specified for user %s" % (req,user))
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
        
        # Perform the allocations
        (aggs, message) = _listaggregates(self)
        if aggs == {} and message != "":
            retVal += "No aggregates to reserve on: %s" % message

        aggregate_urls = aggs.values()
        for (url, rspec) in rspecs.items():
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
            self.logger.info("Creating sliver(s) from rspec file %s for slice %s", specfile, urn)

            # If ABAC then creds are ABAC creds, else creds are slice_cred
            if is_ABAC_framework(self.framework):
                creds = get_abac_creds(self.framework.abac_dir)
                creds.append(slice_cred)
            else:
                creds = [slice_cred]

            args = [urn, creds, rspec, slice_users]
#--- API version diff:
            if self.opts.api_version >= 2:
                # Add the options dict
                args.append(dict())
#---

            (result, message) = _do_ssl(self.framework,
                                        None,
                                        ("Create Sliver %s at %s" % (urn, url)),
                                        client.CreateSliver,
                                        *args)

            # If ABAC then return is a dict with abac_credentials, proof, and normal return
            if isinstance(result, dict):
                if is_ABAC_framework(self.framework):
                    if 'abac_credentials' in result:
                        save_abac_creds(result['abac_credentials'],
                                self.framework.abac_dir)
                    if 'proof' in result:
                        save_proof(self.framework.abac_log, result['proof'])
                if 'manifest' in result:
                    result = result['manifest']
#--- AM API version specific
                elif 'code' in result:
                    # Probably V2 API
                    if result['code']['geni_code'] == 0:
                        result = result['value']
                    elif result['code']['geni_code'] == 7: # REFUSED
                        self._raise_omni_error( result['output'], RefusedError)
                    else:
                        message = result['output']
                        result = None

            prettyresult = result

#--- Dev vs Exp diff?:            
            if rspec_util.is_rspec_string( result, self.logger ):
                try:
                    newl = ''
                    if '\n' not in result:
                        newl = '\n'
                    prettyresult = md.parseString(result).toprettyxml(indent=' '*2, newl=newl)
                except:
                    pass
                # summary
                retVal += 'Reserved resources on %s. ' % (url)

            else:
                # summary
                retVal += 'Asked %s to reserve resources. No manifest Rspec returned. ' % (url)
                if result is None and message != "":
                    retVal += message

            # FIXME: When Tony revises the rspec, fix this test
            if '<RSpec' in rspec and 'type="SFA"' in rspec:
                # Figure out the login name
                # We could of course do this for the user.
                prstr = "Please run the omni sliverstatus call on your slice %s to determine your login name to PL resources." % name
                self.logger.info(prstr)
                retVal += ". " + prstr

            # If the user specified -o then we save the return from
            # each AM as though it is a manifest RSpec in a
            # separate file
            # Create HEADER
            header = "<!-- Reserved resources for:\n\tSlice: %s\n\tAt AM:\n\tURL: %s\n -->" % (name, url)
            filename = None
            if self.opts.output:
                # create filename
                # remove all punctuation and use url
                server = self._filename_part_from_am_url(url)
                filename = name+"-manifest-rspec-"+server+".xml"
                if self.opts.prefix and self.opts.prefix.strip() != "":
                    filename  = self.opts.prefix.strip() + "-" + filename
                        
                self.logger.info("Writing result of createsliver for slice: %s at AM: %s to file %s", name, url, filename)
                retVal += '\n   Saved createsliver results to %s. ' % (filename)
            else:
                self.logger.info('Asked %s to reserve resources. Result:' % (url))

            # Print or log results, putting header first
            self._printResults( header, prettyresult, filename)

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

#--- Dev mode allow passing too few args?
        if len(args) < 2 or args[0] == None or args[0].strip() == "":
            self._raise_omni_error('renewsliver requires arg of slice name and new expiration time in UTC')

        name = args[0]

        # FIXME: catch errors getting slice URN to give prettier error msg?
        urn = self.framework.slice_name_to_urn(name)
        (slice_cred, message) = _get_slice_cred(self, urn)
        if slice_cred is None:
#--- Dev mode allow passing no slice cred?
            self._raise_omni_error('Cannot renew sliver %s: Could not get slice credential: %s' % (urn, message), NoSliceCredError)

#--- Dev mode skip this:
        expd, slice_exp = self._has_slice_expired(slice_cred)
        if expd:
            self._raise_omni_error('Cannot get renewsliver for slice %s: Slice has expired at %s' % (urn, slice_exp.isoformat()))

#--- Should dev mode allow passing time as is?
        time = None
        try:
            time = dateutil.parser.parse(args[1])
        except Exception, exc:
            self._raise_omni_error('renewsliver couldnt parse new expiration time from %s: %r' % (args[1], exc))

        # Convert to naive UTC time if necessary for ease of comparison
        time = naiveUTC(time)

        retVal = ''

        # Compare requested time with slice expiration time
        retVal += _print_slice_expiration(self, urn, slice_cred) +"\n"
        if time > slice_exp:
#--- Dev mode allow this
            self._raise_omni_error('Cannot renew sliver %s until %s UTC because it is after the slice expiration time %s UTC' % (urn, time, slice_exp))
        elif time <= datetime.datetime.utcnow():
            self.logger.info('Sliver %s will be set to expire now' % urn)
#--- Dev mode allow earlier time
            time = datetime.datetime.utcnow()
        else:
            self.logger.debug('Slice expires at %s UTC after requested time %s UTC' % (slice_exp, time))

        # Add UTC TZ, to have an RFC3339 compliant datetime, per the AM API
        time_with_tz = time.replace(tzinfo=dateutil.tz.tzutc())

        self.logger.info('Renewing Sliver %s until %s (UTC)' % (urn, time_with_tz))

        if self.opts.orca_slice_id:
            self.logger.info('Using ORCA slice id %r', self.opts.orca_slice_id)
            urn = self.opts.orca_slice_id

        successCnt = 0
        successList = []
        failList = []
        (clientList, message) = self._getclients()
        for client in clientList:
            # Add ABAC Creds if necessary, else it is just the slice_cred
            if is_ABAC_framework(self.framework):
                creds = get_abac_creds(self.framework.abac_dir)
                creds.append(slice_cred)
            else:
                creds = [slice_cred]
            # Note that the time arg includes UTC offset as needed
            time_string = time_with_tz.isoformat()
            if self.opts.no_tz:
                # The timezone causes an error in older sfa
                # implementations as deployed in mesoscale GENI. Strip
                # off the timezone if the user specfies --no-tz
                self.logger.info('Removing timezone at user request (--no-tz)')
                time_string = time_with_tz.replace(tzinfo=None).isoformat()

            args = [urn, creds, time_string]
#--- AM API version specific
            if self.opts.api_version >= 2:
                # Add the options dict
                args.append(dict())
            (res, message) = _do_ssl(self.framework,
                                     None,
                                     ("Renew Sliver %s on %s" % (urn, client.url)),
                                     client.RenewSliver,
                                     *args)
            # Unpack ABAC results: A dict with abac_credentials, proof, and the normal return
            if isinstance(res, dict):
                if is_ABAC_framework(self.framework):
                    if 'abac_credentials' in res:
                        save_abac_creds(res['abac_credentials'],
                                self.framework.abac_dir)
                    if 'proof' in res:
                        save_proof(self.framework.abac_log, res['proof'])
                if 'success' in res:
                    res = res['success']
#--- AM API version specific
                if 'code' in res:
                    # AM API v2
                    if res['code']['geni_code'] == 0:
                        res = res['value']
                    else:
                        message = res['output']
                        res = None

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
        if len(args) == 0 or args[0] == None or args[0].strip() == "":
            self._raise_omni_error('sliverstatus requires arg of slice name')

        name = args[0]

        # FIXME: catch errors getting slice URN to give prettier error msg?
        urn = self.framework.slice_name_to_urn(name)
        (slice_cred, message) = _get_slice_cred(self, urn)
        if slice_cred is None:
            self._raise_omni_error('Cannot get sliver status for %s: Could not get slice credential: %s' % (urn, message), NoSliceCredError)

        expd, slice_exp = self._has_slice_expired(slice_cred)
        if expd:
            self._raise_omni_error('Cannot get sliverstatus for slice %s: Slice has expired at %s' % (urn, slice_exp.isoformat()))

        retVal = _print_slice_expiration(self, urn, slice_cred) + "\n"

        if self.opts.orca_slice_id:
            self.logger.info('Using ORCA slice id %r', self.opts.orca_slice_id)
            urn = self.opts.orca_slice_id

        successCnt = 0
        retItem = {}
        # Query status at each client
        (clientList, message) = self._getclients()
        if len(clientList) > 0:
            self.logger.info('Status of Slice %s:' % urn)
        else:
            prstr = "No aggregates available to get slice status at: %s" % message
            retVal += prstr + "\n"
            self.logger.warn(prstr)

        for client in clientList:
            # Add ABAC Creds if necessary to the normal slice_cred
            if is_ABAC_framework(self.framework):
                creds = get_abac_creds(self.framework.abac_dir)
                creds.append(slice_cred)
            else:
                creds = [slice_cred]

            args = [urn, creds]
            if self.opts.api_version >= 2:
                # Add the options dict
                args.append(dict())
            (status, message) = _do_ssl(self.framework,
                                        None,
                                        "Sliver status of %s at %s" % (urn, client.url),
                                        client.SliverStatus, *args)
            # Unpack ABAC results from a dict that includes proof
            if status and 'proof' in status:
                if is_ABAC_framework(self.framework):
                    save_proof(self.framework.abac_log, status['proof'])
                    # XXX: may not need to do delete the proof dict entry
                    del status['proof']
            if status and 'code' in status:
                # AM API v2
                if status['code']['geni_code'] == 0:
                    status = status['value']
                else:
                    message = status['output']
                    status = None
            if status:
                prettyResult = pprint.pformat(status)
                if not isinstance(status, dict):
                    # malformed sliverstatus return
                    self.logger.warn('Malformed sliver status from AM %s. Expected struct, got type %s.' % (client.url, status.__class__.__name__))
                    if isinstance(status, str):
                        prettyResult = str(status)
                header="Sliver status for Slice %s at AM URL %s" % (urn, client.url)
                filename = None
                if self.opts.output:
                    # better filename
                    # remove all punctuation and use url
                    server = self._filename_part_from_am_url(client.url)
                    filename = name+"-sliverstatus-"+server+".json"
                    if self.opts.prefix and self.opts.prefix.strip() != "":
                        filename  = self.opts.prefix.strip() + "-" + filename
                        
                    #self.logger.info("Writing result of sliverstatus for slice: %s at AM: %s to file %s", name, client.url, filename)
                    
                self._printResults(header, prettyResult, filename)
                if filename:
                    retVal += "Saved sliverstatus on %s at AM %s to file %s. \n" % (name, client.url, filename)
                retItem[ client.url ] = status
                successCnt+=1
            else:
                # FIXME: Put the message error in retVal?
                retItem[ client.url ] = False
                retVal += "\nFailed to get SliverStatus on %s at AM %s: %s\n" % (name, client.url, message)

        # FIXME: Return the status if there was only 1 client?
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
        if len(args) == 0 or args[0] == None or args[0].strip() == "":
            self._raise_omni_error('deletesliver requires arg of slice name')

        name = args[0]

        # FIXME: catch errors getting slice URN to give prettier error msg?
        urn = self.framework.slice_name_to_urn(name)
        (slice_cred, message) = _get_slice_cred(self, urn)
        if slice_cred is None:
            self._raise_omni_error('Cannot delete sliver %s: Could not get slice credential: %s' % (urn, message), NoSliceCredError)

        # Here we would abort if the slice has expired
        # But perhaps we should keep going so if there are resources
        # at the aggregate, it can use this cue to free them?
        expd, slice_exp = self._has_slice_expired(slice_cred)
        if expd:
            self._raise_omni_error('Cannot delete sliver for slice %s: Slice has expired at %s' % (urn, slice_exp.isoformat()))

        if self.opts.orca_slice_id:
            self.logger.info('Using ORCA slice id %r', self.opts.orca_slice_id)
            urn = self.opts.orca_slice_id

        retVal = ""
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
            #Gather ABAC certs if we need them to add to the slice_cred
            if is_ABAC_framework(self.framework):
                creds = get_abac_creds(self.framework.abac_dir)
                creds.append(slice_cred)
            else:
                creds = [slice_cred]

            args = [urn, creds]
            if self.opts.api_version >= 2:
                # Add the options dict
                args.append(dict())
            (res, message) = _do_ssl(self.framework,
                                     None,
                                     ("Delete Sliver %s on %s" % (urn, client.url)),
                                     client.DeleteSliver,
                                     *args)
            # Unpack ABAC results from a dict with proof and normal result
            if isinstance(res, dict):
                if is_ABAC_framework(self.framework):
                    if 'proof' in res:
                        save_proof(self.framework.abac_log, res['proof'])
                if 'success' in res:
                    res = res['success']
                if 'code' in res:
                    # AM API v2
                    if res['code']['geni_code'] == 0:
                        res = res['value']
                    else:
                        message = res['output']
                        res = None

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
        if len(args) == 0 or args[0] == None or args[0].strip() == "":
            self._raise_omni_error('shutdown requires arg of slice name')

        name = args[0]

        # FIXME: catch errors getting slice URN to give prettier error msg?
        urn = self.framework.slice_name_to_urn(name)
        (slice_cred, message) = _get_slice_cred(self, urn)
        if slice_cred is None:
            self._raise_omni_error('Cannot shutdown slice %s: Could not get slice credential: %s' % (urn, message), NoSliceCredError)

        expd, slice_exp = self._has_slice_expired(slice_cred)
        if expd:
            self._raise_omni_error('Cannot shutdown slice %s: Slice has expired at %s' % (urn, slice_exp.isoformat()))

        if self.opts.orca_slice_id:
            self.logger.info('Using ORCA slice id %r', self.opts.orca_slice_id)
            urn = self.opts.orca_slice_id

        #Call shutdown on each AM
        retVal = ""
        successCnt = 0
        successList = []
        failList = []
        (clientList, message) = self._getclients()
        for client in clientList:
            # Add ABAC Creds if necessary to the slice_cred
            if is_ABAC_framework(self.framework):
                creds = get_abac_creds(self.framework.abac_dir)
                creds.append(slice_cred)
            else:
                creds = [slice_cred]

            args = [urn, creds]
            if self.opts.api_version >= 2:
                # Add the options dict
                args.append(dict())
            (res, message) = _do_ssl(self.framework,
                                     None,
                                     "Shutdown %s on %s" % (urn, client.url),
                                     client.Shutdown,
                                     *args)
            # Unpack ABAC results from a dict with proof, normal result
            if isinstance(res, dict):
                if is_ABAC_framework(self.framework):
                    if 'proof' in res:
                        save_proof(self.abac_log, res['proof'])
                if 'success' in res:
                    res = res['success']
                if 'code' in res:
                    # AM API v2
                    if res['code']['geni_code'] == 0:
                        res = res['value']
                    else:
                        message = res['output']
                        res = None
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
            client.url = url
            clients.append(client)

        return (clients, message)

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
        return omnilib.xmlrpc.client.make_client(url, framework.key, framework.cert)
    else:
        return omnilib.xmlrpc.client.make_client(url, None, None)

