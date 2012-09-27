#!/usr/bin/python

#----------------------------------------------------------------------
# Copyright (c) 2011-12 Raytheon BBN Technologies
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

      Clearinghouse functions:
       [string dictionary urn->url] = omni.py listaggregates
       On success: [string sliceurnstring] = omni.py createslice SLICENAME
       On fail: [string None] = omni.py createslice SLICENAME
       [stringCred stringCred] = omni.py getslicecred SLICENAME
       On success: [string dateTimeRenewedTo] = omni.py renewslice SLICENAME
       On fail: [string None] = omni.py renewslice SLICENAME
       [string Boolean] = omni.py deleteslice SLICENAME
       [string listOfSliceNames] = omni.py listmyslices USER
       [string listOfSSHPublicKeys] = omni.py listmykeys
       [string stringCred] = omni.py getusercred
       [string string] = omni.py print_slice_expiration SLICENAME
    
"""

import ConfigParser
from copy import deepcopy
import datetime
import logging.config
import optparse
import os
import sys

from omnilib.util import OmniError
from omnilib.handler import CallHandler
from omnilib.util.handler_utils import validate_url

OMNI_VERSION="2.1"

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

def load_config(opts, logger):
    """Load the omni config file.
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
            configfile = os.path.join( '~/.gcf', opts.configfile )
            configfile = os.path.expanduser( configfile )
            if os.path.exists( configfile ):
                configfiles.insert(0, configfile)
            else:
                logger.error("Config file '%s' or '%s' does not exist"
                     % (opts.configfile, configfile))
                raise (OmniError, "Config file '%s' or '%s' does not exist"
                     % (opts.configfile, configfile))

    # Find the first valid config file
    for cf in configfiles:         
        filename = os.path.expanduser(cf)
        if os.path.exists(filename):
            break
    
    # Did we find a valid config file?
    if not os.path.exists(filename):
        prtStr = """ Could not find an omni configuration file in local directory or in ~/.gcf/omni_config
     An example config file can be found in the source tarball or on the wiki"""
        logger.error( prtStr )
        raise OmniError, prtStr

    logger.info("Loading config file %s", filename)
    
    confparser = ConfigParser.RawConfigParser()
    try:
        confparser.read(filename)
    except ConfigParser.Error as exc:
        logger.error("Config file %s could not be parsed: %s"% (filename, str(exc)))
        raise OmniError, "Config file %s could not be parsed: %s"% (filename, str(exc))

    # Load up the omni options
    config = {}
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

    # Find aggregate nicknames
    config['aggregate_nicknames'] = {}
    if confparser.has_section('aggregate_nicknames'):
        for (key,val) in confparser.items('aggregate_nicknames'):
            temp = val.split(',')
            for i in range(len(temp)):
                temp[i] = temp[i].strip()
            if len(temp) != 2:
                logger.warn("Malformed definition of aggregate nickname %s. Should be <URN>,<URL> where URN may be empty. Got: %s", key, val)
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
                    logger.warn("Skipping aggregate nickname %s: %s doesn't look like a URL", key, temp[0])
                    continue

            # If temp len > 2: try to use it as is

            config['aggregate_nicknames'][key] = temp

    # Load up the framework section
    if not opts.framework:
        opts.framework = config['omni']['default_cf']

    logger.info("Using control framework %s" % opts.framework)

    # Find the control framework
    cf = opts.framework.strip()
    if not confparser.has_section(cf):
        logger.error( 'Missing framework %s in configuration file' % cf )
        raise OmniError, 'Missing framework %s in configuration file' % cf
    
    # Copy the control framework into a dictionary
    config['selected_framework'] = {}
    for (key,val) in confparser.items(cf):
        config['selected_framework'][key] = val
    
    return config

def load_framework(config, opts):
    """Select the Control Framework to use from the config, and instantiate the proper class."""

    cf_type = config['selected_framework']['type']
    config['logger'].debug('Using framework type %s', cf_type)

    framework_mod = __import__('omnilib.frameworks.framework_%s' % cf_type, fromlist=['omnilib.frameworks'])
    config['selected_framework']['logger'] = config['logger']
    framework = framework_mod.Framework(config['selected_framework'], opts)
    return framework    

def initialize(argv, options=None ):
    """Parse argv (list) into the given optional optparse.Values object options.
    (Supplying an existing options object allows pre-setting certain values not in argv.)
    Then configure logging per those options.
    Then load the omni_config file
    Then initialize the control framework.
    Return the framework, config, args list, and optparse.Values struct."""

    opts, args = parse_args(argv, options)
    logger = configure_logging(opts)
    config = load_config(opts, logger)
    framework = load_framework(config, opts)
    logger.debug('User Cert File: %s', framework.cert)
    return framework, config, args, opts


####
def call(argv, options=None, verbose=False):
    """Method to use when calling omni as a library

    argv is a list ala sys.argv
    options is an optional optparse.Values structure like you get from parser.parse_args
      Use this to pre-set certain values, or allow your caller to get omni options from its commandline

    Verbose option allows printing the command and summary, or suppressing it.
    Callers can control omni logs (suppressing console printing for example) using python logging.

    Can call functions like this:
     User does:    myscript.py -f my_sfa --myScriptPrivateOption describe ahtest-describe-emulab-net.json

     Your myscript.py code does:
import os
import pprint
import re
import sys

import omni
from omnilib.util.omnierror import OmniError

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
  options, args = parser.parse_args(sys.argv[1:])
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
    if rspecfile and os.path.exists(rspecfile) and os.path.getsize(rspecfile) > 0:
      print "Looking for slice name and AM URL in RSpec file %s" % rspecfile
      with open(rspecfile, 'r') as f:
        rspec = f.read()

    # Now parse the comments, whch look like this:
#<!-- Resources at AM:
#	URN: unspecified_AM_URN
#	URL: https://localhost:8001
# -->
# Reserved resources for:\n\tSlice: %s
# at AM:\n\tURN: %s\n\tURL: %s

      if not ("Resources at AM" in rspec or "Reserved resources for" in rspec):
        sys.exit("Could not find slice name or AM URL in RSpec")
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

    framework, config, args, opts = initialize(argv, options)
    # process the user's call
    return API_call( framework, config, args, opts, verbose=verbose )

def API_call( framework, config, args, opts, verbose=False ):
    """Call the function from the given args list. 
    Apply the options from the given optparse.Values opts argument
    If verbose, print the command and the summary.
    Return the summary and the result object.
    """

    logger = config['logger']

    if opts.debug:
        logger.info(getSystemInfo() + "\nOmni: " + getOmniVersion())

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
        #sys.argv when called as a library is
        # uninteresting/misleading. So args is better, but this misses
        # the options.
        # We print here all non-default options
        parser = getParser()
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
            if has == False:
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

        cmd = None
        if len(args) > 0:
            cmd = args[0]
        s = "Completed " + cmd + ":\n" + nondef + "Args: "+" ".join(args)+"\n\n  Result Summary: " + str(retVal)
        headerLen = (70 - (len(s) + 2)) / 4
        header = "- "*headerLen+" "+s+" "+"- "*headerLen

        logger.info( " " + "-"*60 )
        logger.info( header )
        # printed not logged so can redirect output to a file
        #logger.info(retVal)
#        logger.info( " " + "="*60 )
#        print retItem
        logger.info( " " + "="*60 )
    
    return retVal, retItem

def configure_logging(opts):
    """Configure logging. If a log config filename is supplied with the -l option,
    and the file is non-empty, configure logging from that file. For details on this,
    see the applyLogConfig documentation.

    Otherwise, use a basic config, with INFO level by default,
    DEBUG level if opts.debug.

    Return a logger for 'omni'."""

    level = logging.INFO
    optlevel = 'INFO'
    if opts.debug:
        level = logging.DEBUG
        optlevel = 'DEBUG'

    deft = {}

    # Add the ability to use %(logfilename)s in the logging config
    # file
    deft['logfilename'] = opts.logoutput

    if opts.logconfig:
        deft['optlevel'] = optlevel
        applyLogConfig(opts.logconfig, defaults=deft)
    else:
        logging.basicConfig(level=level)

    logger = logging.getLogger("omni")
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
    version ="GENI Omni Command Line Aggregate Manager Tool Version %s" % OMNI_VERSION
    version +="\nCopyright (c) 2012 Raytheon BBN Technologies"
    return version

def getParser():
    """Construct an Options Parser for parsing omni arguments.
    Do not actually parse anything"""

    usage = "\n" + getOmniVersion() + "\n\n%prog [options] <command and arguments> \n\
\n \t Commands and their arguments are: \n\
 \t\tAM API functions: \n\
 \t\t\t getversion \n\
 \t\t\t listresources [In AM API V1 and V2 optional: slicename] \n\
 \t\t\t describe slicename [AM API V3 only] \n\
 \t\t\t createsliver <slicename> <rspec file> [AM API V1&2 only] \n\
 \t\t\t allocate <slicename> <rspec file> [AM API V3 only] \n\
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
 \t\tClearinghouse / Slice Authority functions: \n\
 \t\t\t listaggregates \n\
 \t\t\t createslice <slicename> \n\
 \t\t\t getslicecred <slicename> \n\
 \t\t\t renewslice <slicename> <new expiration time in UTC> \n\
 \t\t\t deleteslice <slicename> \n\
 \t\t\t listmyslices <username> \n\
 \t\t\t listmykeys \n\
 \t\t\t getusercred \n\
 \t\t\t print_slice_expiration <slicename> \n\
\n\t See README-omni.txt for details.\n\
\t And see the Omni website at http://trac.gpolab.bbn.com/gcf"

    parser = optparse.OptionParser(usage=usage, version="%prog: " + getOmniVersion())
    parser.add_option("-c", "--configfile",
                      help="Config file name", metavar="FILE")
    parser.add_option("-f", "--framework", default="",
                      help="Control framework to use for creation/deletion of slices")
    parser.add_option("-V", "--api-version", type="int", default=2,
                      help="Specify version of AM API to use (default 2)")
    parser.add_option("-a", "--aggregate", metavar="AGGREGATE_URL", action="append",
                      help="Communicate with a specific aggregate")
    # Note that type and version are case in-sensitive strings.
    parser.add_option("-t", "--rspectype", nargs=2, default=["GENI", '3'], metavar="AD-RSPEC-TYPE AD-RSPEC-VERSION",
                      help="Ad RSpec type and version to return, default 'GENI 3'")
    parser.add_option("--debug", action="store_true", default=False,
                       help="Enable debugging output")
    parser.add_option("-o", "--output",  default=False, action="store_true",
                      help="Write output of many functions (getversion, listresources, allocate, status, getslicecred,...) , to a file (Omni picks the name)")
    parser.add_option("--outputfile",  default=None, metavar="OUTPUT_FILENAME",
                      help="Name of file to write output to (instead of Omni picked name). '%a' will be replaced by servername, '%s' by slicename if any. Implies -o. Note that for multiple aggregates, without a '%a' in the name, only the last aggregate output will remain in the file. Will ignore -p.")
    parser.add_option("-p", "--prefix", default=None, metavar="FILENAME_PREFIX",
                      help="Filename prefix when saving results (used with -o, not --usercredfile, --slicecredfile, or --outputfile)")
    parser.add_option("--usercredfile", default=None, metavar="USER_CRED_FILENAME",
                      help="Name of user credential file to read from if it exists, or save to when running like '--usercredfile myUserCred.xml -o getusercred'")
    parser.add_option("--slicecredfile", default=None, metavar="SLICE_CRED_FILENAME",
                      help="Name of slice credential file to read from if it exists, or save to when running like '--slicecredfile mySliceCred.xml -o getslicecred mySliceName'")
    parser.add_option("--tostdout", default=False, action="store_true",
                      help="Print results like rspecs to STDOUT instead of to log stream")
    parser.add_option("--no-compress", dest='geni_compressed', 
                      default=True, action="store_false",
                      help="Do not compress returned values")
    parser.add_option("--available", dest='geni_available',
                      default=False, action="store_true",
                      help="Only return available resources")
    parser.add_option("--best-effort", dest='geni_best_effort',
                      default=False, action="store_true",
                      help="Should AMs attempt to complete the operation on only some slivers, if others fail")
    parser.add_option("-u", "--sliver-urn", dest="slivers", action="append",
                      help="Sliver URN (not name) on which to act. Supply this option multiple times for multiple slivers, or not at all to apply to the entire slice")
    parser.add_option("--end-time", dest='geni_end_time',
                      help="Requested end time for any newly allocated or provisioned slivers - may be ignored by the AM")
    parser.add_option("-v", "--verbose", default=True, action="store_true",
                      help="Turn on verbose command summary for omni commandline tool")
    parser.add_option("--verbosessl", default=False, action="store_true",
                      help="Turn on verbose SSL / XMLRPC logging")
    parser.add_option("-q", "--quiet", default=True, action="store_false", dest="verbose",
                      help="Turn off verbose command summary for omni commandline tool")
    parser.add_option("-l", "--logconfig", default=None,
                      help="Python logging config file")
    parser.add_option("--logoutput", default='omni.log',
                      help="Python logging output file [use %(logfilename)s in logging config file]")
    parser.add_option("--NoGetVersionCache", dest='noGetVersionCache',
                      default=False, action="store_true",
                      help="Disable using cached GetVersion results (forces refresh of cache)")
    parser.add_option("--ForceUseGetVersionCache", dest='useGetVersionCache',
                      default=False, action="store_true",
                      help="Require using the GetVersion cache if possible (default false)")
    parser.add_option("--GetVersionCacheAge", dest='GetVersionCacheAge',
                      default=7,
                      help="Age in days of GetVersion cache info before refreshing (default is 7)")
    parser.add_option("--GetVersionCacheName", dest='getversionCacheName',
                      default="~/.gcf/get_version_cache.json",
                      help="File where GetVersion info will be cached, default is ~/.gcf/get_version_cache.json")
    parser.add_option("--devmode", default=False, action="store_true",
                      help="Run in developer mode: more verbose, less error checking of inputs")
    parser.add_option("--arbitrary-option", dest='arbitrary_option',
                      default=False, action="store_true",
                      help="Add an arbitrary option to ListResources (for testing purposes)")
    parser.add_option("--raise-error-on-v2-amapi-error", dest='raiseErrorOnV2AMAPIError',
                      default=False, action="store_true",
                      help="In AM API v2, if an AM returns a non-0 (failure) result code, raise an AMAPIError. Default False. For use by scripts.")
    parser.add_option("--no-tz", default=False, action="store_true",
                      help="Do not send timezone on RenewSliver")
    parser.add_option("--no-ssl", dest="ssl", action="store_false",
                      default=True, help="do not use ssl")
    parser.add_option("--orca-slice-id",
                      help="Use the given Orca slice id")
    parser.add_option("--abac", default=False, action="store_true",
                      help="Use ABAC authorization")
    return parser

def parse_args(argv, options=None):
    """Parse the given argv list using the Omni optparse.OptionParser.
    Fill options into the given option optparse.Values object
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

    parser = getParser()
    if argv is None:
        # prints to stderr
        parser.print_help()
        return

    (options, args) = parser.parse_args(argv, options)

    # Validate options here if we want to be careful that options are of the right types...
    # particularly if the user passed in an options argument

    # Validate the API version. The parser has already converted the argument to
    # an integer, so check against a list of valid versions.
    supported_versions = [1, 2, 3]
    if options.api_version not in supported_versions:
        parser.error('API version "%s" is not a supported version. Valid versions are: %r.'
                     % (options.api_version, supported_versions))

    # From GetVersionCacheAge (int days) produce options.GetVersionCacheOldestDate as a datetime.datetime
    options.GetVersionCacheOldestDate = datetime.datetime.utcnow() - datetime.timedelta(days=options.GetVersionCacheAge)

    options.getversionCacheName = os.path.normcase(os.path.expanduser(options.getversionCacheName))

    if options.noGetVersionCache and options.useGetVersionCache:
        parser.error("Cannot both force not using the GetVersion cache and force TO use it.")

    if options.outputfile:
        options.output = True

    return options, args

def main(argv=None):
    # do initial setup & process the user's call
    if argv is None:
        argv = sys.argv[1:]
    try:
        framework, config, args, opts = initialize(argv)
        API_call(framework, config, args, opts, verbose=opts.verbose)
    except OmniError:
        sys.exit()

        
if __name__ == "__main__":
    sys.exit(main())
