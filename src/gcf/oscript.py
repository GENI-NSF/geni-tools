#!/usr/bin/env python

#----------------------------------------------------------------------
# Copyright (c) 2011-2015 Raytheon BBN Technologies
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

from __future__ import absolute_import

""" The OMNI client
    This client is a GENI API client that is capable of connecting
    to multiple slice authorities (clearinghouses) for slice creation and deletion.
    See README-omni.txt

    Be sure to create an omni config file (typically ~/.gcf/omni_config)
    and supply valid paths to your per control framework user certs and keys.
    See gcf/omni_config.sample for an example, and src/omni-configure.py
    for a script to configure omni for you.

    Typical usage:
    omni.py sfa listresources
    
    The currently supported control frameworks (clearinghouse implementations)
    are SFA (i.e. PlanetLab), PG and GCF.

    Extending Omni to support additional frameworks with their own
    clearinghouse APIs requires adding a new Framework extension class.

    Return Values and Arguments of various omni commands:
      Aggregate functions:
       Most aggregate functions return 2 items: A string describing the result, and an object for tool use.
       In AM APIV3+ functions, that object is a dictionary by aggregate URL containing the full AM API v3+ return struct
       (code, value, output).
       [string dictionary] = omni.py getversion # dict is keyed by AM url
       [string dictionary] = omni.py listresources # dict is keyed by AM url,urn
       [string dictionary] = omni.py listresources SLICENAME # AM API V1&2 only; dict is keyed by AM url,urn
       [string dictionary] = omni.py describe SLICENAME # AM API V3+ only
       [string rspec] = omni.py createsliver SLICENAME RSPEC_FILENAME # AM API V1&2 only
       [string dictionary] = omni.py allocate SLICENAME RSPEC_FILENAME # AM API V3+ only
       [string dictionary] = omni.py provision SLICENAME # AM API V3+ only
       [string dictionary] = omni.py performoperationalaction SLICENAME ACTION # AM API V3+ only
       [string dictionary] = omni.py poa SLICENAME ACTION # AM API V3+ only; alias for performoperationalaction
       [string dictionary] = omni .py sliverstatus SLICENAME # AM API V1&2 only
       [string dictionary] = omni .py status SLICENAME # AM API V3+ only
       [string (successList of AM URLs, failList)] = omni.py renewsliver SLICENAME # AM API V1&2 only
       [string dictionary] = omni.py renew SLICENAME # AM API V3+ only
       [string (successList of AM URLs, failList)] = omni.py deletesliver SLICENAME # AM API V1&2 only
       [string dictionary] = omni.py delete SLICENAME # AM API V3+ only
       In AM API v1&2:
       [string (successList, failList)] = omni.py shutdown SLICENAME
       In AM API v3:
       [string dictionary] = omni.py shutdown SLICENAME
       [string dictionary] = omni.py update SLICENAME RSPEC_FILENAME # Some AM API V3+ AMs only
       [string dictionary] = omni.py cancel SLICENAME # Some AM API V3+ AMs only

       Non-AM API functions exported by aggregates, supported by Omni:
       From ProtoGENI/InstaGENI:
       [string dictionary] = omni.py createimage SLICENAME IMAGENAME [false] -u <SLIVER URN>
       [string dictionary] = omni.py snapshotimage SLICENAME IMAGENAME [false] -u <SLIVER URN> ; alias for createimage
       [string dictionary] = omni.py deleteimage IMAGEURN [CREATORURN]
       [string dictionary] = omni.py listimages [CREATORURN]

      Clearinghouse functions:
       [string dictionary] = omni.py get_ch_version # dict of CH specific version information
       [string dictionary urn->url] = omni.py listaggregates
       On success: [string sliceurnstring] = omni.py createslice SLICENAME
       On fail: [string None] = omni.py createslice SLICENAME
       [stringCred stringCred] = omni.py getslicecred SLICENAME
       On success: [string dateTimeRenewedTo] = omni.py renewslice SLICENAME
       On fail: [string None] = omni.py renewslice SLICENAME
       [string Boolean] = omni.py deleteslice SLICENAME
       [string listOfSliceURNs] = omni.py listslices USER
       [string listOfSliceURNs] = omni.py listmyslices USER
       [string listOfProjectDictionaries (PROJECT_URN, PROJECT_UID, PROJECT_ROLE, EXPIRED)] = omni.py listprojects USER
       [string listOfProjectDictionaries (PROJECT_URN, PROJECT_UID, PROJECT_ROLE, EXPIRED)] = omni.py listmyprojects USER
       [string listOfSSHKeyPairs] = omni.py listmykeys
       [string listOfSSHKeyPairs] = omni.py listkeys USER
       [string stringCred] = omni.py getusercred
       [string string] = omni.py print_slice_expiration SLICENAME
       [string dictionary AM URN->dict by sliver URN of silver info] = omni.py listslivers SLICENAME
       [string listOfMemberDictionaries (PROJECT_MEMBER (URN), EMAIL, PROJECT_ROLE, PROJECT_MEMBER_UID)] = omni.py listprojectmembers PROJECTNAME
       [string listOfMemberDictionaries (KEYS, URN, EMAIL, ROLE)] = omni.py listslicemembers SLICENAME
       [string Boolean] = omni.py addslicemember SLICENAME USER [ROLE]
       [string Boolean] = omni.py removeslicemember SLICENAME USER 

      Other functions:
       [string dictionary] = omni.py nicknames # List aggregate and rspec nicknames    
       [string dictionary] = omni.py print_sliver_expirations SLICENAME
"""

import ConfigParser
from copy import deepcopy
import datetime
import inspect
import logging.config
import optparse
import os
import shutil
import sys
import urllib2

from .omnilib.util import OmniError, AMAPIError
from .omnilib.handler import CallHandler
from .omnilib.util.handler_utils import validate_url, printNicknames

# Explicitly import framework files so py2exe is happy
from .omnilib.frameworks import framework_apg
from .omnilib.frameworks import framework_base
from .omnilib.frameworks import framework_gcf
from .omnilib.frameworks import framework_gch
from .omnilib.frameworks import framework_gib
from .omnilib.frameworks import framework_of
from .omnilib.frameworks import framework_pg
from .omnilib.frameworks import framework_pgch
from .omnilib.frameworks import framework_sfa
from .omnilib.frameworks import framework_chapi
from .gcf_version import GCF_VERSION

#DEFAULT_RSPEC_LOCATION = "http://www.gpolab.bbn.com/experiment-support"               
#DEFAULT_RSPEC_EXTENSION = "xml"                

def countSuccess( successList, failList ):
    """Intended to be used with 'renewsliver', 'deletesliver', and
    'shutdown' which return a two item tuple as their second
    argument.  The first item is a list of urns/urls for which it
    successfully performed the operation.  The second item is a
    list of the urns/urls for which it did not successfully
    perform the operation.  Failure could be due to an actual
    error or just simply that there were no such resources
    allocated to this sliver at that aggregates.  In this context
    this method returns a tuple containing the number of items
    which succeeded and the number of items attempted.
    """
    succNum = len( successList )
    return (succNum, succNum + len( failList ) )

def load_agg_nick_config(opts, logger):
    """Load the agg_nick_cache file.
    Search path:
    - filename from commandline
    """
    if opts.noCacheFiles:
        logger.debug("Not loading agg_nick_config per option noCacheFiles")
        config = {}
        if not config.has_key('aggregate_nicknames'):
            config['aggregate_nicknames'] = {}
        if not config.has_key('omni_defaults'):
            config['omni_defaults'] = {}
        return config

    # the directory of this file
    curr_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
    parent_dir = curr_dir.rsplit(os.sep,2)[0]

    # Load up the config file
    configfiles = [os.path.join(parent_dir, 'agg_nick_cache.base')]
    
    aggNickCacheExists = False
    # if aggNickCacheName defined on commandline exists, check it first
    if os.path.exists( opts.aggNickCacheName ):
        configfiles.insert(0, opts.aggNickCacheName)
        aggNickCacheExists = True

    # get date of current file
    if aggNickCacheExists:
        aggNickCacheDate = os.path.getmtime(opts.aggNickCacheName)
        aggNickCacheTimestamp = datetime.datetime.fromtimestamp(aggNickCacheDate)
    else:
        aggNickCacheTimestamp = None

    # update the file if necessary
    if opts.noAggNickCache or (not aggNickCacheTimestamp and not opts.useAggNickCache) or (aggNickCacheTimestamp and aggNickCacheTimestamp < opts.AggNickCacheOldestDate and not opts.useAggNickCache):
        update_agg_nick_cache( opts, logger )

    # aggNickCacheName may now exist. If so, add it to the front of the list.
    if not aggNickCacheExists and os.path.exists( opts.aggNickCacheName ):
        configfiles.insert(0, opts.aggNickCacheName)

    readConfigFile = False
    # Find the first valid config file
    for cf in configfiles:         
        filename = os.path.expanduser(cf)
        if os.path.exists(filename):
            config = {}       

            # Did we find a valid config file?
            if not os.path.exists(filename):
                prtStr = "Could not find agg_nick_cache file: %s"%filename
                logger.info( prtStr )
                continue
#                return config

            logger.info("Loading agg_nick_cache file '%s'", filename)

            confparser = ConfigParser.RawConfigParser()
            try:
                confparser.read(filename)
                readConfigFile = True
                break
            except ConfigParser.Error as exc:
                logger.error("agg_nick_cache file %s could not be parsed: %s"% (filename, str(exc)))
    if not readConfigFile:
        logger.error("Failed to read any possible agg_nick_cache file; Check your network connection and/or permissions to read/write '%s'.", opts.aggNickCacheName)
        return {}

    config = load_aggregate_nicknames( config, confparser, filename, logger, opts )
    config = load_omni_defaults( config, confparser, filename, logger, opts )
    return config

def locate_config( opts, logger, config={}):
    """Locate the omni config file.
    Search path:
    - filename from commandline
      - in current directory
      - in ~/.gcf
    - omni_config in current directory
    - omni_config in ~/.gcf
    """

    # Load up the config file
    configfiles = ['omni_config','~/.gcf/omni_config']

    if opts.configfile:
        # if configfile defined on commandline does not exist, fail
        if os.path.exists( opts.configfile ):
            configfiles.insert(0, opts.configfile)
        else:
            # Check maybe the default directory for the file
            configfile = os.path.join( os.path.join('~','.gcf'), opts.configfile )
            configfile = os.path.normpath(os.path.expanduser( configfile ))
            if os.path.exists( configfile ):
                configfiles.insert(0, configfile)
            else:
                logger.error("Config file '%s' or '%s' does not exist"
                     % (opts.configfile, configfile))
                raise (OmniError, "Config file '%s' or '%s' does not exist"
                     % (opts.configfile, configfile))

    # Find the first valid config file
    for cf in configfiles:
        filename = os.path.normpath(os.path.expanduser(cf))
        if os.path.exists(filename):
            break

    # Did we find a valid config file?
    if not os.path.exists(filename):
        prtStr = """ Could not find an omni configuration file in local directory or in ~/.gcf/omni_config
     An example config file can be found in the source tarball or on the wiki"""
        logger.error( prtStr )
        raise OmniError, prtStr

    return filename
def load_config(opts, logger, config={}, filename=None):
    """Load the omni_config file specified by the `filename` option.
    """
    if filename is None:
        filename = locate_config(opts, logger, config)

    logger.info("Loading config file '%s'", filename)
    
    confparser = ConfigParser.RawConfigParser()
    try:
        confparser.read(filename)
    except ConfigParser.Error as exc:
        logger.error("Config file '%s' could not be parsed: %s"% (filename, str(exc)))
        raise OmniError, "Config file '%s' could not be parsed: %s"% (filename, str(exc))

    # Load up the omni options
    config['logger'] = logger
    config['omni'] = {}
    for (key,val) in confparser.items('omni'):
        config['omni'][key] = val
        
    # Load up the users the user wants us to see        
    config['users'] = []
    if 'users' in config['omni']:
        if config['omni']['users'].strip() is not '' :
            for user in config['omni']['users'].split(','):
                if user.strip() is not '' : 
                    d = {}
                    for (key,val) in confparser.items(user.strip()):
                        d[key] = val
                    config['users'].append(d)

    config = load_aggregate_nicknames( config, confparser, filename, logger, opts )
    config = load_omni_defaults( config, confparser, filename, logger, opts )

    # Find rspec nicknames
    config['rspec_nicknames'] = {}
#    config['default_rspec_location'] = DEFAULT_RSPEC_LOCATION
#    config['default_rspec_extension'] = DEFAULT_RSPEC_EXTENSION
    if confparser.has_section('rspec_nicknames'):
        for (key,val) in confparser.items('rspec_nicknames'):
            key = key.strip()
            temp = val.strip()
            if temp == "":
                continue
            if key == "default_rspec_location":
                config['default_rspec_location'] = temp      
            elif key == "default_rspec_extension":
                config['default_rspec_extension'] = temp                
            else:
                config['rspec_nicknames'][key] = temp

    # Load up the framework section
    if not opts.framework:
        if config['omni'].has_key('default_cf'):
            opts.framework = config['omni']['default_cf']
        else:
            logger.info("No 'default_cf' defined in omni_config. Using 'portal'")
            opts.framework = "portal"

    # Fill in the project if it is configured
    if hasattr(opts,'project') and not opts.project:
        if config['omni'].has_key('default_project'):
            opts.project = config['omni']['default_project']

    # Config of useslicemembers some value of true or false sets the option
    if hasattr(opts,'useSliceMembers') and config['omni'].has_key('useslicemembers'):
        usm = config['omni']['useslicemembers'].strip().lower()
        if usm in ('t', 'true', 'y', 'yes', '1', 'on'):
            usm = True
            if not opts.useSliceMembers:
                logger.info("Setting option 'useSliceMembers' True based on omni_config setting")
                opts.useSliceMembers = True
        elif usm in ('f', 'false', 'n', 'no', '0', 'off'):
            usm = False
            if opts.useSliceMembers:
                logger.info("Un-Setting option 'useSliceMembers' (set False) based on omni_config setting")
                opts.useSliceMembers = False

    # Config of ignoreconfigusers some value of true sets the option
    if hasattr(opts,'ignoreConfigUsers') and config['omni'].has_key('ignoreconfigusers'):
        usm = config['omni']['ignoreconfigusers'].strip().lower()
        if usm in ('t', 'true', 'y', 'yes', '1', 'on'):
            usm = True
            if not opts.ignoreConfigUsers:
                logger.info("Setting option 'ignoreConfigUsers' based on omni_config setting")
                opts.ignoreConfigUsers = True

    logger.info("Using control framework %s" % opts.framework)

    # Find the control framework
    cf = opts.framework.strip()
    if not confparser.has_section(cf):
        logger.error("Missing framework '%s' in configuration file" % cf )
        raise OmniError, "Missing framework '%s' in configuration file" % cf
    
    # Copy the control framework into a dictionary
    config['selected_framework'] = {}
    for (key,val) in confparser.items(cf):
        config['selected_framework'][key] = val

    # This portion of the config is only of interest for `omni-configure`
    # but is included here for completeness
    if confparser.has_section('omni_configure'):
        for (key,val) in confparser.items('omni_configure'):
            key = key.strip()
            temp = val.strip()
            if key == "version":
                config['omni_configure_version'] = temp
            elif key == "date":
                config['omni_configure_date'] = temp
            elif key == "files":
                files1 = temp.split("\n")
                files2 = []
                for item in files1:
                    fdesc,fname,oktodelete = item.split(",")
                    files2.append((fdesc.strip(),fname.strip(),oktodelete.strip()))
                config['omni_configure_files'] = files2

    return config

def load_aggregate_nicknames( config, confparser, filename, logger, opts ):
    # Find aggregate nicknames
    if not config.has_key('aggregate_nicknames'):
        config['aggregate_nicknames'] = {}
    if confparser.has_section('aggregate_nicknames'):
        for (key,val) in confparser.items('aggregate_nicknames'):
            temp = val.split(',')
            for i in range(len(temp)):
                temp[i] = temp[i].strip()
            if len(temp) != 2:
                logger.warn("Malformed definition of aggregate nickname '%s'. Should be <URN>,<URL> where URN may be empty. Got: %s", key, val)
            if len(temp) == 0:
                continue
            if len(temp) == 1:
                # Got 1 entry - if its a valid URL, use it
                res = validate_url(temp[0])
                if res is None or res.startswith("WARN:"):
                    t = temp[0]
                    temp = ["",t]
                else:
                    # not a valid URL. Skip it
                    logger.warn("Skipping aggregate nickname '%s': '%s' doesn't look like a URL", key, temp[0])
                    continue

            # If temp len > 2: try to use it as is
            if config['aggregate_nicknames'].has_key(key):
                if config['aggregate_nicknames'][key] == temp:
                    #logger.debug("AM nickname %s from %s defined identically already", key, filename)
                    continue
                elif temp[0] == "" and config['aggregate_nicknames'][key][1] == temp[1]:
                    #logger.debug("AM nickname %s from %s already defined and with a URN", key, filename)
                    continue
                else:
                    logger.debug("Aggregate nickname '%s' being redefined using value from '%s'", key, filename)
                    logger.debug("     Old: %s=%s. New: %s=%s", config['aggregate_nicknames'][key][0], config['aggregate_nicknames'][key][1], temp[0], temp[1])
#            else:
#                logger.debug("Loaded aggregate nickname '%s' from file '%s'." % (key, filename))
            config['aggregate_nicknames'][key] = temp
    return config

def load_omni_defaults( config, confparser, filename, logger, opts ):
    # Find Omni defaults in the omni_config
    # These are values that should over-ride any hard coded defaults
    # But if the incoming config already has a value for this, don't replace that.
    # In practice this should mean that values in the agg_nick_cache
    # over-ride values in a user's custom omni_config.
    # So this should only be used for setup values
    # That can be over-ridden with other omni_config settings
    # or commandline options.
    if not config.has_key('omni_defaults'):
        config['omni_defaults'] = {}
    if confparser.has_section('omni_defaults'):
        for (key,val) in confparser.items('omni_defaults'):
            val = val.strip()
            key = key.strip()
            if config['omni_defaults'].has_key(key):
                if config['omni_defaults'][key] == val:
 #                   logger.debug("Ignoring omni_default '%s' from '%s': using earlier identical config setting", key, filename)
                    continue
                else:
                    logger.debug("Ignoring omni_default '%s' from '%s': using earlier different config setting", key, filename)
                    logger.debug("     Current: %s=%s. Ignored: %s", key, config['omni_defaults'][key], val)
                    continue
#            else:
#                logger.debug("Loaded omni default '%s' from file '%s'." % (key, filename))
            config['omni_defaults'][key] = val
    return config

def load_framework(config, opts):
    """Select the Control Framework to use from the config, and instantiate the proper class."""

    cf_type = config['selected_framework']['type']
    config['logger'].debug('Using framework type %s', cf_type)

    # Compute the module path leading up to where we will find frameworks, so that we can live
    # inside the standard omni/gcf distribution, or deeper inside a larger package
    prefix = ".".join(__name__.split(".")[:-1])

    framework_mod = __import__('%s.omnilib.frameworks.framework_%s' % (prefix, cf_type), fromlist=['%s.omnilib.frameworks' % (prefix)])
    config['selected_framework']['logger'] = config['logger']
    framework = framework_mod.Framework(config['selected_framework'], opts)
    return framework    

def update_agg_nick_cache( opts, logger ):
    """Try to download the definitive version of `agg_nick_cache` and
    store in the specified place."""
    tmpcache = None
    try:
        import tempfile
        handle, tmpcache = tempfile.mkstemp()
        os.close(handle)
        # make sure the directory containing --aggNickCacheName exists
        # wget `agg_nick_cache`
        # cp `agg_nick_cache` opts.aggNickCacheName
        directory = os.path.dirname(opts.aggNickCacheName)
        if not os.path.exists( directory ):
            os.makedirs( directory )
        logger.debug("Attempting to refresh agg_nick_cache from %s...", opts.aggNickDefinitiveLocation)
        # Do not use urllib here, because urllib interacts badly with M2Crypto
        # which overrites the URLopener.open_https method in a way that makes opening https
        # connections take 60 seconds where they should take 5.
        # (we've imported M2Crypto here indirectly via sfa.trust.gid)
        # See http://nostacktrace.com/dev/2011/2/4/no-love-for-the-monkey-patch.html
        # urllib.urlretrieve( opts.aggNickDefinitiveLocation, tmpcache )
        handle = urllib2.urlopen(opts.aggNickDefinitiveLocation)
        with open (tmpcache, "w") as f:
            f.write(handle.read())
        good = False
        if os.path.exists(tmpcache) and os.path.getsize(tmpcache) > 0:
            if os.path.exists(opts.aggNickCacheName) and os.path.getsize(opts.aggNickCacheName) > 0:
                tmpsize = os.path.getsize(tmpcache)
                oldsize = os.path.getsize(opts.aggNickCacheName)
                if tmpsize / oldsize > 10 or oldsize / tmpsize > 10:
                    # If the size changed dramatically, then assume the new one is broken.
                    # Of course, it could be that the old one is broken...
                    logger.info("Download of latest `agg_nick_cache` from '%s' seems broken (size is wrong). Keeping old cache.", opts.aggNickDefinitiveLocation)
                    logger.debug("Old cache '%s' size: %d. New temp '%s' size: %d", opts.aggNickCacheName, oldsize, tmpcache, tmpsize)
                else:
                    # Size didn't change dramatically
                    good = True
            else:
                # No previous cache - use the new one
                good = True
        else:
            logger.info("Download of latest `agg_nick_cache` from '%s' seems broken (no or empty file). Keeping old cache.", opts.aggNickDefinitiveLocation)
            logger.debug("Temp file: '%s'. Exists? %s", tmpcache, os.path.exists(tmpcache))
        if good:
            # On Windows, rename doesn't delete any existing file, so explicitly delete the old one first
            # And shutil.move also wants the destination to be gone
            try:
                os.unlink(opts.aggNickCacheName)
            except:
                pass
            shutil.move(tmpcache, opts.aggNickCacheName)
            logger.info("Downloaded latest `agg_nick_cache` from '%s' and copied to '%s'." % (opts.aggNickDefinitiveLocation, opts.aggNickCacheName))
    except Exception, e:
        logger.info("Attempted to download latest `agg_nick_cache` from '%s' but could not." % opts.aggNickDefinitiveLocation )
        logger.debug(e)
    finally:
        try:
            os.unlink(tmpcache)
        except:
            pass

# Check if there is a newer version of Omni available.
# Look for an entry "latest_omni_version" under "omni_defaults" in the omni_config (or really, agg_nick_cache).
# Expected format is "#,Message" EG: "2.8,Omni 2.8 was release 2/1/2015". No commas in the message.
# If a newer version is available, log a message at INFO level.
def checkForUpdates(config, logger):
    if not config or not config.has_key('omni_defaults') or not config['omni_defaults'].has_key('latest_omni_version') or config['omni_defaults']['latest_omni_version'] is None:
        logger.debug("No latest Omni version found in config")
        return False
    latestStr = str(config['omni_defaults']['latest_omni_version']).strip()
    latestVals = latestStr.split(',')
    if len(latestVals) == 0:
        logger.debug("Failed to find any values in latest_omni_version: %s", latestStr)
        return False

    if latestVals[0].strip() == GCF_VERSION.strip():
        logger.debug("Already running latest GCF: %s", GCF_VERSION)
        return False
    import re
    def natSort(s, _nsre=re.compile('([0-9]+)')):
        return [int(text) if text.isdigit() else text.lower()
                for text in re.split(_nsre, s)]
    latest = max(latestVals[0].strip(), GCF_VERSION, key=natSort)
    if latest == GCF_VERSION.strip():
        logger.debug("Running a newer version of Omni than the last release. Running %s > %s", GCF_VERSION, latestVals[0])
        return False

    logger.debug("New Omni version available: %s > %s", latestVals[0], GCF_VERSION)
    if len(latestVals) > 1:
        logger.info(latestVals[1])
    else:
        logger.info("A new version of Omni is available: Version %s", latestVals[0])
    return True

def initialize(argv, options=None, dictLoggingConfig=None ):
    """Parse argv (list) into the given optional optparse.Values object options.
    (Supplying an existing options object allows pre-setting certain values not in argv.)
    Then configure logging per those options.
    Then load the omni_config file
    Then initialize the control framework.
    Return the framework, config, args list, and optparse.Values struct."""

    opts, args = parse_args(argv, options)
    logger = configure_logging(opts, dictLoggingConfig)
    if "--useSliceMembers" in argv:
        logger.info("Option --useSliceMembers is no longer necessary and is now deprecated, as that behavior is now the default. This option will be removed in a future release.")
    config = load_agg_nick_config(opts, logger)
    # Load custom config _after_ system agg_nick_cache,
    # which also sets omni_defaults
    config = load_config(opts, logger, config)
    checkForUpdates(config, logger)
    framework = load_framework(config, opts)
    logger.debug('User Cert File: %s', framework.cert)
    return framework, config, args, opts


####
def call(argv, options=None, verbose=False, dictLoggingConfig=None):
    """Method to use when calling omni as a library

    argv is a list ala sys.argv
    options is an optional optparse.Values structure like you get from parser.parse_args
      Use this to pre-set certain values, or allow your caller to get omni options from its commandline

    Verbose option allows printing the command and summary, or suppressing it.
    dictLoggingConfig is a Python logging configuration dictionary for configuring logging. If
    not supplied, any logging config filename provided using the option --logconfig will be applied.
    Callers can control omni logs (suppressing console printing for example) using python logging.

    Return is a list of 2 items: a human readable string summarizing the result 
    (possibly an error message), and the result object (may be None on error). The result 
    object type varies by underlying command called.

    Can call functions like this:
     User does:    myscript.py -f my_sfa --myScriptPrivateOption describe ahtest-describe-emulab-net.json

     Your myscript.py code does:
import os
import pprint
import re
import sys

import gcf.oscript as omni
from .omnilib.util.files import *
from .omnilib.util.omnierror import OmniError

################################################################################
# Requires that you have omni installed or the path to gcf/src in your
# PYTHONPATH.
#
# For example put the following in your bashrc:
#     export PYTHONPATH=${PYTHONPATH}:path/to/gcf/src
#
################################################################################

def main(argv=None):
  ##############################################################################
  # Get a parser from omni that understands omni options
  ##############################################################################
  parser = omni.getParser()
  # update usage for help message
  omni_usage = parser.get_usage()
  parser.set_usage(omni_usage+"\nmyscript.py supports additional commands.\n\n\tCommands and their arguments are:\n\t\t\t[add stuff here]")

  ##############################################################################
  # Add additional optparse.OptionParser style options for your
  # script as needed.
  # Be sure not to re-use options already in use by omni for
  # different meanings, otherwise you'll raise an OptionConflictError
  ##############################################################################
  parser.add_option("--myScriptPrivateOption",
                    help="A non-omni option added by %s"%sys.argv[0],
                    action="store_true", default=False)
  # options is an optparse.Values object, and args is a list
  options, args = omni.parse_args(sys.argv[1:], parser=parser)
  if options.myScriptPrivateOption:
    # do something special for your private script's options
    print "Got myScriptOption"



  ##############################################################################
  # Try to read 2nd argument as an RSpec filename. Pull the AM URL and
  # and maybe slice name from that file.
  # Then construct omni args appropriately: command, slicename, action or rspecfile or datetime
  ##############################################################################
  omniargs = []
  if args and len(args)>1:
    sliceurn = None
    # Try to read args[1] as an RSpec filename to read
    rspecfile = args[1]
    rspec = None
    if rspecfile:
      print "Looking for slice name and AM URL in RSpec file %s" % rspecfile
      try:
        rspec = readFile(rspecfile)
      except:
        print "Failed to read rspec from %s" % rspecfile

    if rspec:
    # Now parse the comments, whch look like this:
#<!-- Resources at AM:
#	URN: unspecified_AM_URN
#	URL: https://localhost:8001
# -->
# Reserved resources for:\n\tSlice: %s
# at AM:\n\tURN: %s\n\tURL: %s

      if not ("Resources at AM" in rspec or "Reserved resources for" in rspec):
        sys.exit("Could not find slice name or AM URL in RSpec %s" % rspec)
      amurn = None
      amurl = None
      # Pull out the AM URN and URL
      match = re.search(r"at AM:\n\tURN: (\S+)\n\tURL: (\S+)\n", rspec)
      if match:
        amurn = match.group(1)
        amurl = match.group(2)
        print "  Found AM %s (%s)" % (amurn, amurl)
        omniargs.append("-a")
        omniargs.append(amurl)

      # Pull out the slice name or URN if any
      if "Reserved resources for" in rspec:
        match = re.search(r"Reserved resources for:\n\tSlice: (\S+)\n\t", rspec)
        if match:
          sliceurn = match.group(1)
          print "  Found slice %s" % sliceurn

    command = args[0]
    rest = []
    if len(args) > 2:
      rest = args[2:]

    # If the command requires a slice and we didn't get a readable rspec from the rspecfile,
    # Then treat that as the slice
    if not sliceurn and rspecfile and not rspec:
      sliceurn = rspecfile
      rspecfile = None

    # construct the args in order
    omniargs.append(command)
    if sliceurn:
      omniargs.append(sliceurn)
    if rspecfile and command.lower() in ('createsliver', 'allocate'):
      omniargs.append(rspecfile)
    for arg in rest:
      omniargs.append(arg)
  elif len(args) == 1:
    omniargs = args
  else:
    print "Got no command or rspecfile. Run '%s -h' for more information."%sys.argv[0]
    return

  ##############################################################################
  # And now call omni, and omni sees your parsed options and arguments
  ##############################################################################
  print "Call Omni with args %s:\n" % omniargs
  try:
    text, retItem = omni.call(omniargs, options)
  except OmniError, oe:
    sys.exit("\nOmni call failed: %s" % oe)

  print "\nGot Result from Omni:\n"

  # Process the dictionary returned in some way
  if isinstance(retItem, dict):
    import json
    print json.dumps(retItem, ensure_ascii=True, indent=2)
  else:
    print pprint.pformat(retItem)

  # Give the text back to the user
  print text

  if type(retItem) == type({}):
    numItems = len(retItem.keys())
  elif type(retItem) == type([]):
    numItems = len(retItem)
  elif retItem is None:
    numItems = 0
  else:
    numItems = 1
  if numItems:
    print "\nThere were %d item(s) returned." % numItems

if __name__ == "__main__":
  sys.exit(main())


    This is equivalent to: ./omni.py -a <AM URL> describe <slicename>
    """

    if options is not None and not options.__class__==optparse.Values:
        raise OmniError("Invalid options argument to call: must be an optparse.Values object")

    if argv is None or not type(argv) == list:
        raise OmniError("Invalid argv argument to call: must be a list")

    framework, config, args, opts = initialize(argv, options, dictLoggingConfig)
    # process the user's call
    return API_call( framework, config, args, opts, verbose=verbose )

def getOptsUsed(parser, opts, logger=None):
    '''Get string to print out the options supplied'''
    #sys.argv when called as a library is
    # uninteresting/misleading. So args is better, but this misses
    # the options.
    # We print here all non-default options
    nondef = ""
    for attr in dir(opts):
        import types
        if attr.startswith("_"):
            continue
        if isinstance(getattr(opts, attr), types.MethodType):
            continue
        # if the parser has no option with a dest==attr,
        # then continue
        # This means that the user supplied an option the parser didn't
        # handle, and typically there would have been an error,
        # but lets not complain here
        has = False
        for opt in parser.option_list:
            if opt.dest == attr:
                has=True
                break

        if has == False:
            for group in parser.option_groups:
                for opt in group.option_list:
                    if opt.dest == attr:
                        has = True
                        break
                if has:
                    break
            if not has:
                continue
        if (not parser.defaults.has_key(attr)) or (parser.defaults[attr] != getattr(opts, attr)):
            # If default is a relative path we expanded,
            # then it looks like it changed here. So try expanding
            # any defaults to see if that makes it match
            try:
                defVal = parser.defaults[attr]
                defVal = os.path.normcase(os.path.expanduser(defVal))
                if defVal == getattr(opts, attr):
                    continue
            except:
                pass
            # non-default value
            nondef += "\n\t\t" + attr + ": " + str(getattr(opts, attr))

    if nondef != "":
        nondef = "\n  Options as run:" + nondef + "\n\n  "
    return nondef

def API_call( framework, config, args, opts, verbose=False ):
    """Call the function from the given args list. 
    Apply the options from the given optparse.Values opts argument
    If verbose, print the command and the summary.
    Return is a list of 2 items: a human readable string summarizing the result 
    (possibly an error message), and the result object (may be None on error). The result 
    object type varies by underlying command called.
    """

    logger = config['logger']

    if opts.debug:
        logger.info(getSystemInfo() + "\nOmni: " + getOmniVersion())

    if len(args) > 0 and args[0].lower() == "nicknames":
        result = printNicknames(config, opts)
    else:
        # Process the user's call
        handler = CallHandler(framework, config, opts)
    #    Returns string, item
        result = handler._handle(args)
    if result is None:
        retVal = None
        retItem = None
    elif len(result)==2:
        retVal, retItem = result
    else:
        retVal = result
        retItem = None

    # Print the summary of the command result
    if verbose:
        nondef = getOptsUsed(getParser(), opts, logger)
        cmd = None
        if len(args) > 0:
            cmd = args[0]
        s = "Completed " + cmd + ":\n" + nondef + "Args: "+" ".join(args)+"\n\n  Result Summary: " + str(retVal)
        headerLen = (70 - (len(s) + 2)) / 4
        header = "- "*headerLen+" "+s+" "+"- "*headerLen

        logger.info( " " + "-"*54 )
        logger.info( header )
        # printed not logged so can redirect output to a file
        #logger.info(retVal)
#        logger.info( " " + "="*54 )
#        print retItem
        logger.info( " " + "="*54 )
    # end of if verbose
    
    return retVal, retItem

def configure_logging(opts, dictConfig=None):
    """Configure logging. If a logging config dictionary is supplied, configuring Logging using that.
    Else, if a log config filename is supplied with the -l option,
    and the file is non-empty, configure logging from that file. For details on this,
    see the applyLogConfig documentation.

    Otherwise, use a basic config, with INFO level by default,
    DEBUG level if opts.debug, INFO if opts.info, etc.

    Return a logger for 'omni'."""

    # Warning: If Omni is used as a library, and the caller did some logging configuration,
    # then the call here to logging.basicConfig(level) will do nothing. In particular, it will not reset
    # the log level based on the options supplied to Omni. The caller should supply a separate logging config
    # file, or use e.g. logging.disable(logging.INFO) before calling omni. and logging.disable(logging.NOTSET) after

    level = logging.INFO
    optlevel = 'INFO'
    # If log level was specified in options, use it. Most verbose
    # level is used. Note that at ERROR and WARN levels, command
    # outputs (like manifests) are not printed: use -o.
    if opts.error:
        level = logging.ERROR
        optlevel = 'ERROR'
    if opts.warn:
        level = logging.WARN
        optlevel = 'WARNING'
    if opts.info:
        level = logging.INFO
        optlevel = 'INFO'
    if opts.debug:
        level = logging.DEBUG
        optlevel = 'DEBUG'
    
    deft = {}

    # Add the ability to use %(logfilename)s in the logging config
    # file
    deft['logfilename'] = opts.logoutput

    error = None # error raised configuring from given dictionary
    if not opts.noLoggingConfiguration:
        if dictConfig is not None:
            # Try to configure logging from the given object
            # Note this raises an exception if it fails (a ValueError, TypeError, AttributeError or ImportError)
            # Also note this only works in python2.7+
            logging.config.dictConfig(dictConfig)
        elif opts.logconfig:
            deft['optlevel'] = optlevel
            applyLogConfig(opts.logconfig, defaults=deft)
        else:
            # Ticket 296: Add timestamps to log messages
#        fmt = '%(asctime)s %(levelname)-8s %(name)s: %(message)s'
            fmt = '%(asctime)s %(levelname)-8s: %(message)s'
            logging.basicConfig(level=level,format=fmt,datefmt='%H:%M:%S')

    logger = logging.getLogger("omni")

    if dictConfig is not None and not opts.noLoggingConfiguration:
        logger.debug("Configured logging from dictionary")

    return logger

def applyLogConfig(logConfigFilename, defaults={'optlevel': 'INFO'}):
    """Change the logging configuration to that in the specified file, if found.
    Effects all uses of python logging in this process.

    Existing loggers are not modified, unless they are explicitly named
    in the logging config file (they or their ancestor, not 'root').

    Tries hard to find the file, and does nothing if not found.

    'defaults' is a dictionary in ConfigParser format, that sets variables
    for use in the config files. Specifically,
    use this to set 'optlevel' to the basic logging level desired: INFO is the default.

    For help creating a logging config file,
    see http://docs.python.org/library/logging.config.html#configuration-file-format
    and see the sample 'omni_log_conf_sample.conf'

    From a script, you can over-ride the -l argument to change the log level.
    Alternatively, you can call this function during omni operations.
    Sample usage from a script:
      # Configure logging based on command line options, using any -l specified file
      framework, config, args, opts = omni.initialize(omniargs, options)
      text, retItem = omni.API_call( framework, config, args, opts )

      # Without changing commandline args, reset the logging config
      omni.applyLogConfig("examples/myLogConfig.conf")

      # <Here your script resets 'args' to give a different command>

      # Then make the call for the new command, using the new log level
      text, retItem = omni.API_call( framework, config, args, opts )
"""

    fns = [logConfigFilename, os.path.join('src', logConfigFilename), os.path.expanduser(logConfigFilename), os.path.join('.', logConfigFilename), os.path.abspath(logConfigFilename)]
    found = False
    for fn in fns:
        if os.path.exists(fn) and os.path.getsize(fn) > 0:
            # Only new loggers get the parameters in the config file.
            # If disable_existing is True(default), then existing loggers are disabled,
            # unless they (or ancestors, not 'root') are explicitly listed in the config file.
            logging.config.fileConfig(fn, defaults=defaults, disable_existing_loggers=False)
            logging.info("Configured logging from file %s", fn)
            found = True
            break

    if not found:
        logging.warn("Failed to find log config file %s", logConfigFilename)

def getSystemInfo():
    import platform
    pver = platform.python_implementation() + " " + platform.python_version()
    osinfo = platform.platform()
    return "Python: " + pver + "\nOS: " + osinfo

def getOmniVersion():
    version ="GENI Omni Command Line Aggregate Manager Tool Version %s" % GCF_VERSION
    version +="\nCopyright (c) 2011-2015 Raytheon BBN Technologies"
    return version

def getParser():
    """Construct an Options Parser for parsing omni arguments.
    Do not actually parse anything"""

    usage = "\n" + getOmniVersion() + "\n\n%prog [options] [--project <proj_name>] <command and arguments> \n\
\n \t Commands and their arguments are: \n\
 \t\tAM API functions: \n\
 \t\t\t getversion \n\
 \t\t\t listresources [In AM API V1 and V2 optional: slicename] \n\
 \t\t\t describe slicename [AM API V3 only] \n\
 \t\t\t createsliver <slicename> <rspec URL, filename, or nickname> [AM API V1&2 only] \n\
 \t\t\t allocate <slicename> <rspec URL, filename, or nickname> [AM API V3 only] \n\
 \t\t\t provision <slicename> [AM API V3 only] \n\
 \t\t\t performoperationalaction <slicename> <action> [AM API V3 only] \n\
 \t\t\t poa <slicename> <action> \n\
 \t\t\t\t [alias for 'performoperationalaction'; AM API V3 only] \n\
 \t\t\t sliverstatus <slicename> [AMAPI V1&2 only]\n\
 \t\t\t status <slicename> [AMAPI V3 only]\n\
 \t\t\t renewsliver <slicename> <new expiration time in UTC> [AM API V1&2 only] \n\
 \t\t\t renew <slicename> <new expiration time in UTC> [AM API V3 only] \n\
 \t\t\t deletesliver <slicename> [AM API V1&2 only] \n\
 \t\t\t delete <slicename> [AM API V3 only] \n\
 \t\t\t shutdown <slicename> \n\
 \t\t\t update <slicename> <rspec URL, filename, or nickname> [Some AM API V3 AMs only] \n\
 \t\t\t cancel <slicename> [Some AM API V3 AMs only] \n\
 \t\tNon AM API aggregate functions (supported by some aggregates): \n\
 \t\t\t createimage <slicename> <imagename> [optional: false (keep image private)] -u <sliver urn> [ProtoGENI/InstaGENI only] \n\
 \t\t\t snapshotimage <slicename> <imagename> [optional: false (keep image private)] -u <sliver urn> [ProtoGENI/InstaGENI only] \n\
 \t\t\t\t [alias for 'createimage'] \n\
 \t\t\t deleteimage <imageurn> [optional: creatorurn] [ProtoGENI/InstaGENI only] \n\
 \t\t\t listimages [optional: creatorurn] [ProtoGENI/InstaGENI only] \n\
 \t\tClearinghouse / Slice Authority functions: \n\
 \t\t\t get_ch_version \n\
 \t\t\t listaggregates \n\
 \t\t\t createslice <slicename> \n\
 \t\t\t getslicecred <slicename> \n\
 \t\t\t renewslice <slicename> <new expiration time in UTC> \n\
 \t\t\t deleteslice <slicename> \n\
 \t\t\t listslices [optional: username] [Alias for listmyslices]\n\
 \t\t\t listmyslices [optional: username] \n\
 \t\t\t listprojects [optional: username] [Alias for listmyprojects]\n\
 \t\t\t listmyprojects [optional: username] \n\
 \t\t\t listmykeys [optional: username] [Alias for listkeys]\n\
 \t\t\t listkeys [optional: username]\n\
 \t\t\t getusercred \n\
 \t\t\t print_slice_expiration <slicename> \n\
 \t\t\t listslivers <slicename> \n\
 \t\t\t listprojectmembers <projectname> \n\
 \t\t\t listslicemembers <slicename> \n\
 \t\t\t addslicemember <slicename> <username> [optional: role] \n\
 \t\t\t removeslicemember <slicename> <username>  \n\
 \t\tOther functions: \n\
 \t\t\t nicknames \n\
 \t\t\t print_sliver_expirations <slicename> \n\
\n\t See README-omni.txt for details.\n\
\t And see the Omni website at https://github.com/GENI-NSF/geni-tools/wiki."

    parser = optparse.OptionParser(usage=usage, version="%prog: " + getOmniVersion())

    # Basics
    basicgroup = optparse.OptionGroup( parser, "Basic and Most Used Options")
    basicgroup.add_option("-a", "--aggregate", metavar="AGGREGATE_URL", action="append",
                      help="Communicate with a specific aggregate")
    basicgroup.add_option("--available", dest='geni_available',
                      default=False, action="store_true",
                      help="Only return available resources")
    basicgroup.add_option("-c", "--configfile",
                      help="Config file name (aka `omni_config`)", metavar="FILE")
    basicgroup.add_option("-f", "--framework", default=os.getenv("GENI_FRAMEWORK", ""),
                      help="Control framework to use for creation/deletion of slices")
    basicgroup.add_option("-r", "--project", 
                      help="Name of project. (For use with pgch framework.)")
    basicgroup.add_option("--alap", action="store_true", default=False,
                          help="Request slivers be renewed as close to the requested time as possible, instead of failing if the requested time is not possible. Default is False.")
    # Note that type and version are case in-sensitive strings.
    # This causes settiong options.explicitRSpecVersion as well
    basicgroup.add_option("-t", "--rspectype", nargs=2, default=["GENI", '3'], metavar="RSPEC-TYPE RSPEC-VERSION",
                      help="RSpec type and version to return, default: '%default'")
    # This goes in options.api_version. Also causes setting options.explicitAPIVersion
    basicgroup.add_option("-V", "--api-version", type="int", default=2,
                      help="Specify version of AM API to use (default v%default)")
    basicgroup.add_option("--useSliceAggregates", default=False, action="store_true",
                          help="Perform the slice action at all aggregates the given slice is known to use according to clearinghouse records. Default is %default.")
    parser.add_option_group( basicgroup )

    # AM API v3 specific
    v3group = optparse.OptionGroup( parser, "AM API v3+",
                          "Options used in AM API v3 or later" )
    v3group.add_option("--best-effort", dest='geni_best_effort',
                      default=False, action="store_true",
                      help="Should AMs attempt to complete the operation on only some slivers, if others fail")
    v3group.add_option("--cred", action='append', metavar="CRED_FILENAME",
                      help="Send credential in given filename with any call that takes a list of credentials")
    v3group.add_option("--end-time", dest='geni_end_time',
                      help="Requested end time for any newly allocated or provisioned slivers - may be ignored by the AM")
    v3group.add_option("--start-time", dest='geni_start_time',
                      help="Requested start time for any allocated slivers - NOW if not provided, could be for future reservations")
# Sample options file content:
#{
# "option_name_1": "value",
# "option_name_2": {"complicated_dict" : 37},
# "option_name_3": 67
#}
    v3group.add_option("--optionsfile", metavar="JSON_OPTIONS_FILENAME",
                      help="Send all options defined in named JSON format file to methods that take options")
    v3group.add_option("--speaksfor", metavar="USER_URN",
                      help="Supply given URN as user we are speaking for in Speaks For option")
    v3group.add_option("-u", "--sliver-urn", dest="slivers", action="append",
                      help="Sliver URN (not name) on which to act. Supply this option multiple times for multiple slivers, or not at all to apply to the entire slice")
    # For Update. See http://groups.geni.net/geni/wiki/GAPI_AM_API_DRAFT/Adopted#ChangestoDescribe
    v3group.add_option("--cancelled", action="store_true", default=False,
                       help="Should Describe show sliver state of only geni_provisioned slivers, ignoring any geni_updating and geni_allocated slivers (default %default)")
    parser.add_option_group( v3group )

    # logging levels
    loggroup = optparse.OptionGroup( parser, "Logging and Verboseness",
                          "Control the amount of output to the screen and/or to a log" )
    loggroup.add_option("-q", "--quiet", default=True, action="store_false", dest="verbose",
                      help="Turn off verbose command summary for omni commandline tool")
    loggroup.add_option("-v", "--verbose", default=True, action="store_true",
                      help="Turn on verbose command summary for omni commandline tool")
    loggroup.add_option("--debug", action="store_true", default=False,
                       help="Enable debugging output. If multiple loglevel are set from commandline (e.g. --debug, --info) the more verbose one will be preferred.")
    loggroup.add_option("--info", action="store_true", default=False,
                       help="Set logging to INFO.If multiple loglevel are set from commandline (e.g. --debug, --info) the more verbose one will be preferred.")
    loggroup.add_option("--warn", action="store_true", default=False,
                       help="Set log level to WARN. This won't print the command outputs, e.g. manifest rspec, so use the -o or the --outputfile options to save it to a file. If multiple loglevel are set from commandline (e.g. --debug, --info) the more verbose one will be preferred.")
    loggroup.add_option("--error", action="store_true", default=False,
                       help="Set log level to ERROR. This won't print the command outputs, e.g. manifest rspec, so use the -o or the --outputfile options to save it to a file.If multiple loglevel are set from commandline (e.g. --debug, --info) the more verbose one will be preferred.")
    loggroup.add_option("--verbosessl", default=False, action="store_true",
                      help="Turn on verbose SSL / XMLRPC logging")
    loggroup.add_option("-l", "--logconfig", default=None,
                      help="Python logging config file. Default: '%default'")
    loggroup.add_option("--logoutput", default='omni.log',
                      help="Python logging output file [use %(logfilename)s in logging config file]. Default: '%default'")
    loggroup.add_option("--tostdout", default=False, action="store_true",
                      help="Print results like rspecs to STDOUT instead of to log stream")
    loggroup.add_option("--noLoggingConfiguration", default=False, action="store_true",
                        help="Do not configure python logging; for use by other tools.")
    parser.add_option_group( loggroup )

    # output to files
    filegroup = optparse.OptionGroup( parser, "File Output",
                          "Control name of output file and whether to output to a file" )
    filegroup.add_option("-o", "--output",  default=False, action="store_true",
                      help="Write output of many functions (getversion, listresources, allocate, status, getslicecred,...) , to a file (Omni picks the name)")
    filegroup.add_option("-p", "--prefix", default=None, metavar="FILENAME_PREFIX",
                      help="Filename prefix when saving results (used with -o, not --usercredfile, --slicecredfile, or --outputfile)")
    # If this next is set, then options.output is also set
    filegroup.add_option("--outputfile",  default=None, metavar="OUTPUT_FILENAME",
                      help="Name of file to write output to (instead of Omni picked name). '%a' will be replaced by servername, '%s' by slicename if any. Implies -o. Note that for multiple aggregates, without a '%a' in the name, only the last aggregate output will remain in the file. Will ignore -p.")
    filegroup.add_option("--usercredfile", default=os.getenv("GENI_USERCRED", None), metavar="USER_CRED_FILENAME",
                      help="Name of user credential file to read from if it exists, or save to when running like '--usercredfile " + 
                         "myUserCred.xml -o getusercred'. Defaults to value of 'GENI_USERCRED' environment variable if defined.")
    filegroup.add_option("--slicecredfile", default=os.getenv("GENI_SLICECRED", None), metavar="SLICE_CRED_FILENAME",
                      help="Name of slice credential file to read from if it exists, or save to when running like '--slicecredfile " + 
                         "mySliceCred.xml -o getslicecred mySliceName'. Defaults to value of 'GENI_SLICECRED' environment variable if defined.")
    parser.add_option_group( filegroup )

    # GetVersion
    gvgroup = optparse.OptionGroup( parser, "GetVersion Cache",
                          "Control GetVersion Cache" )
    gvgroup.add_option("--NoGetVersionCache", dest='noGetVersionCache',
                      default=False, action="store_true",
                      help="Disable using cached GetVersion results (forces refresh of cache)")
    gvgroup.add_option("--ForceUseGetVersionCache", dest='useGetVersionCache',
                      default=False, action="store_true",
                      help="Require using the GetVersion cache if possible (default false)")
    # This causes setting options.GetVersionCacheOldestDate
    gvgroup.add_option("--GetVersionCacheAge", dest='GetVersionCacheAge',
                      default=7,
                      help="Age in days of GetVersion cache info before refreshing (default is %default)")
    gvgroup.add_option("--GetVersionCacheName", dest='getversionCacheName',
                      default="~/.gcf/get_version_cache.json",
                      help="File where GetVersion info will be cached, default is %default")
    gvgroup.add_option("--noCacheFiles", default=False, action="store_true",
                       help="Disable both GetVersion and Aggregate Nickname cache functionality completely; no files are downloaded, saved, or loaded.")
    parser.add_option_group( gvgroup )

    # AggNick
    angroup = optparse.OptionGroup( parser, "Aggregate Nickname Cache",
                          "Control Aggregate Nickname Cache" )
    angroup.add_option("--NoAggNickCache", dest='noAggNickCache',
                      default=False, action="store_true",
                      help="Disable using cached AggNick results and force refresh of cache (default is %default)")
    angroup.add_option("--ForceUseAggNickCache", dest='useAggNickCache',
                      default=False, action="store_true",
                      help="Require using the AggNick cache if possible (default %default)")
    # This causes setting options.AggNickCacheOldestDate
    angroup.add_option("--AggNickCacheAge", dest='AggNickCacheAge',
                      default=1,
                      help="Age in days of AggNick cache info before refreshing (default is %default)")
    angroup.add_option("--AggNickCacheName", dest='aggNickCacheName',
                      default="~/.gcf/agg_nick_cache",
                      help="File where AggNick info will be cached, default is %default")
    angroup.add_option("--AggNickDefinitiveLocation", dest='aggNickDefinitiveLocation',
                      default="https://raw.githubusercontent.com/GENI-NSF/geni-tools/master/agg_nick_cache.base",
                      help="Website with latest agg_nick_cache, default is %default. To force Omni to read this cache, delete your local AggNickCache or use --NoAggNickCache.")
    parser.add_option_group( angroup )

    # Development / Advanced
    devgroup = optparse.OptionGroup( parser, "For Developers / Advanced Users",
                          "Features only needed by developers or advanced users" )
    devgroup.add_option("--useSliceMembers", default=True, action="store_true",
                          help="DEPRECATED - this option no longer has any effect. The option is always true, unless you specify --noSliceMembers.")
    devgroup.add_option("--noSliceMembers", default=False, action="store_true",
                          help="Reverse of --useSliceMembers. Do NOT create accounts or install slice members' SSH keys on reserved resources in createsliver, provision or performoperationalaction. Default is %default. " + \
                              "When specified, only users from your omni_config are used (unless --ignoreConfigUsers).")
    devgroup.add_option("--ignoreConfigUsers", default=False, action="store_true",
                          help="Ignore users and SSH keys listed in your omni_config when installing SSH keys on resources in createsliver or provision or " + \
                              "performoperationalaction. Default is false - your omni_config users are read and used.")
    devgroup.add_option("--ssltimeout", default=360, action="store", type="float",
                        help="Seconds to wait before timing out AM and CH calls. Default is %default seconds.")
    devgroup.add_option("--noExtraCHCalls", default=False, action="store_true",
                        help="Disable extra Clearinghouse calls like reporting slivers. Default is %default.")
    devgroup.add_option("--devmode", default=False, action="store_true",
                      help="Run in developer mode: more verbose, less error checking of inputs")
    devgroup.add_option("--raise-error-on-v2-amapi-error", dest='raiseErrorOnV2AMAPIError',
                      default=False, action="store_true",
                      help="In AM API v2, if an AM returns a non-0 (failure) result code, raise an AMAPIError. Default is %default. For use by scripts.")
    devgroup.add_option("--maxBusyRetries", default=4, action="store", type="int",
                      help="Max times to retry AM or CH calls on getting a 'busy' error. Default: %default")
    devgroup.add_option("--no-compress", dest='geni_compressed', 
                      default=True, action="store_false",
                      help="Do not compress returned values")
    devgroup.add_option("--abac", default=False, action="store_true",
                      help="Use ABAC authorization")
    devgroup.add_option("--arbitrary-option", dest='arbitrary_option',
                      default=False, action="store_true",
                      help="Add an arbitrary option to ListResources (for testing purposes)")
    devgroup.add_option("--no-ssl", dest="ssl", action="store_false",
                      default=True, help="do not use ssl")
    devgroup.add_option("--no-tz", default=False, action="store_true",
                      help="Do not send timezone on RenewSliver")
    devgroup.add_option("--orca-slice-id", dest="orca_slice_id",
                      help="Use the given Orca slice id")
    parser.add_option_group( devgroup )
    return parser

def parse_args(argv, options=None, parser=None):
    """Parse the given argv list using the Omni optparse.OptionParser, or the parser supplied if given.
    Fill options into the given option optparse.Values object if supplied.
    """
    if options is not None and not options.__class__==optparse.Values:
        raise OmniError("Invalid options argument to parse_args: must be an optparse.Values object")
    elif options is not None:
        # The caller, presumably a script, gave us an optparse.Values storage object.
        # Passing this object to parser.parse_args replaces the storage - it is pass
        # by reference. Callers may not expect that. In particular, multiple calls in
        # separate threads will conflict.
        # Make a deep copy
        options = deepcopy(options)

    if parser is not None and not isinstance(parser, optparse.OptionParser):
        raise OmniError("parse_args got invalid parser: %s." % parser)
    if parser is None:
        parser = getParser()
    if argv is None:
        # prints to stderr
        parser.print_help()
        return None, []

    (options, args) = parser.parse_args(argv, options)

    # Set an option indicating if the user explicitly requested the RSpec version
    options.ensure_value('explicitRSpecVersion', False)
    options.explicitRSpecVersion = ('-t' in argv or '--rspectype' in argv)

    # Set an option indicating if the user explicitly requested the API version
    options.ensure_value('explicitAPIVersion', False)
    # FIXME: Do something more extensible...
    options.explicitAPIVersion = ('-V' in argv or '--api-version' in argv or '-V1' in argv or '-V2' in argv or '-V3' in argv or '-V4' in argv or '-V5' in argv)

    # Validate options here if we want to be careful that options are of the right types...
    # particularly if the user passed in an options argument

    # Validate the API version. The parser has already converted the argument to
    # an integer, so check against a list of valid versions.
    supported_versions = [1, 2, 3]
    if options.api_version not in supported_versions:
        parser.error('API version "%s" is not a supported version. Valid versions are: %r.'
                     % (options.api_version, supported_versions))

    # From GetVersionCacheAge (int days) produce options.GetVersionCacheOldestDate as a datetime.datetime
    indays = -1
    try:
        indays = int(options.GetVersionCacheAge)
    except Exception, e:
        raise OmniError, "Failed to parse GetVersionCacheAge: %s" % e 
    options.GetVersionCacheOldestDate = datetime.datetime.utcnow() - datetime.timedelta(days=indays)

    options.getversionCacheName = os.path.normcase(os.path.expanduser(options.getversionCacheName))

    if options.noGetVersionCache and options.useGetVersionCache:
        parser.error("Cannot both force not using the GetVersion cache and force TO use it.")

    # From AggNickCacheAge (int days) produce options.AggNickCacheOldestDate as a datetime.datetime
    indays = -1
    try:
        indays = int(options.AggNickCacheAge)
    except Exception, e:
        raise OmniError, "Failed to parse AggNickCacheAge: %s" % e 
    options.AggNickCacheOldestDate = datetime.datetime.utcnow() - datetime.timedelta(days=indays)

    options.aggNickCacheName = os.path.normcase(os.path.expanduser(options.aggNickCacheName))

    if options.noAggNickCache and options.useAggNickCache:
        parser.error("Cannot both force not using the AggNick cache and force TO use it.")

    if options.outputfile:
        options.output = True

    if options.usercredfile:
        options.usercredfile = os.path.normpath(os.path.normcase(os.path.expanduser(options.usercredfile)))
    if options.slicecredfile:
        options.slicecredfile = os.path.normpath(os.path.normcase(os.path.expanduser(options.slicecredfile)))

    # noSliceMembers forces useSliceMembers to be false
    # Note you can also force it false with an omni_config setting of useslicemembers=False in the omni section
    if options.noSliceMembers:
        options.useSliceMembers = False

    return options, args

def main(argv=None):
    # do initial setup & process the user's call
    if argv is None:
        argv = sys.argv[1:]
    try:
        framework, config, args, opts = initialize(argv)
        API_call(framework, config, args, opts, verbose=opts.verbose)
    except AMAPIError, ae:
        if ae.returnstruct and isinstance(ae.returnstruct, dict) and ae.returnstruct.has_key('code'):
            if isinstance(ae.returnstruct['code'], int) or isinstance(ae.returnstruct['code'], str):
                sys.exit(int(ae.returnstruct['code']))
            if isinstance(ae.returnstruct['code'], dict) and ae.returnstruct['code'].has_key('geni_code'):
                sys.exit(int(ae.returnstruct['code']['geni_code']))
        sys.exit(ae)

    except OmniError, oe:
        sys.exit(oe)
