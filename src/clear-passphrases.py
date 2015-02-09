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

""" The clear-passphrases.py script.
    This script is meant to help users to remove the passphrase from their 
    the private key of SSL certs or of SSH keys.
"""

import string, re
import sys, os, shutil, platform
from subprocess import Popen, PIPE
import ConfigParser
import optparse
import logging
from gcf.sfa.trust.certificate import Certificate, Keypair
from gcf.oscript import load_config
from gcf.omnilib.util import OmniError

logger = None

def loadKeyFromFile(key_file):
    """ This function loads a private key from a file 
        giving the user three chances to get the passphrase right
    """
    k = Keypair()
    logger.debug("Loading current private key from: %s", key_file)
    # Keep track if the effort was successful
    succ = False
    for i in range(0,3) :
        try :
            k.load_from_file(key_file)
        except Exception, e:
            logger.info("Unable to load private key, maybe you misstyped the passphrase. Try again.")
            logger.debug("Error loading from '%s': %s", key_file, e)
            continue
        succ = True
        break
    # If the key was not loaded properly return None
    if not succ:
        k = None
    return k

def getYNAns(question):
    valid_ans=['','y', 'n']
    answer = raw_input("%s [Y,n]?" % question).lower()
    while answer not in valid_ans:
        answer = raw_input("Your input has to be 'y' or <ENTER> for yes, 'n' for no:").lower()
    if answer == 'n':
        return False
    return True


def getFileName(filename):
    """ This function takes as input a filename and if it already 
        exists it will ask the user whether to replace it or not 
        and if the file shouldn't be replaced it comes up with a
        unique name
    """
    # If the file exists ask the # user to replace it or not
    filename = os.path.expanduser(filename)
    if os.path.exists(filename):
        (basename, extension) = os.path.splitext(filename)
        question = "File " + filename + " exists, do you want to replace it "
        if not getYNAns(question):
            i = 1
            if platform.system().lower().find('darwin') != -1 :
                tmp_pk_file = basename + '(' + str(i) + ')' + extension
            else :
                tmp_pk_file = basename + '-' + str(i) + extension
            
            while os.path.exists(tmp_pk_file):
                i = i+1
                if platform.system().lower().find('darwin'):
                    tmp_pk_file = basename + '(' + str(i) + ')' + extension
                else :
                    tmp_pk_file = basename + '-' + str(i) + extension
            filename = tmp_pk_file
    return filename

def parseArgs(argv):
    """Construct an Options Parser for parsing omni-configure command line
    arguments, and parse them.
    """

    parser = optparse.OptionParser()
    parser.add_option("-c", "--configfile", 
                      help="Config file location", metavar="FILE")
    parser.add_option("-f", "--framework",
                      help="Control framework to use for creation/deletion of slices")
    parser.add_option("-k", "--prcertkey", 
                      help="Private key for SSL certificate file location ", metavar="FILE")
    parser.add_option("-e", "--prkey",
                      help="Private SSH key file location", metavar="FILE")
    parser.add_option("-v", "--verbose", default=False, action="store_true",
                      help="Turn on verbose command summary for clear-passphrases script")

    if argv is None:
        # prints to stderr
        parser.print_help()
        return

    (opts, args) = parser.parse_args(argv)
    return opts

def configLogging(opts) :
    global logger
    level = logging.INFO
    if opts.verbose :
        level = logging.DEBUG

    logging.basicConfig(level=level)
    logger = logging.getLogger("clearcert")

def clearCert(prcertkeyFile):
    global logger
    #Check if the certificate has key that is encrypted
    text = ""
    try:
        with open(prcertkeyFile, 'r') as f:
            text = f.read()
    except Exception, e:
        logger.error("Failed to read SSL certificate from '%s': %s", prcertkeyFile, e)
        sys.exit(-1)

    index = text.find("ENCRYPTED")
    if index == -1 :
        logger.info("Private key for SSL certificate does not have a passphrase. Skip.")
        return 

    k = None
    try:
        k = loadKeyFromFile(prcertkeyFile)
    except Exception, e:
        logger.error("Failed to read key from '%s': %s", prcertkeyFile, e)
        sys.exit(-1)
    if not k:
        logger.warning("Failed to load key from file. Unable to remove passphrase. Exit!")
        sys.exit(-1)

    logger.debug("Loaded key from %s" % prcertkeyFile)

    # Copy key file to a new location
    question = "Do you want to make a backup of your encrypted cert (%s)" % prcertkeyFile
    if getYNAns(question):
      backupEncFile(prcertkeyFile)

    kpem = k.as_pem()

    cert = None
    try:
        cert = Certificate(filename=prcertkeyFile)
    except Exception, e:
        logger.warning("Failed to load cert from '%s': %s", prcertkeyFile, e)
        sys.exit(-1)

    logger.debug("Read certificate: %s", cert.dump_string())

    cpem = cert.save_to_string()

    try:
        with open(prcertkeyFile, 'w') as cfile:
            cfile.write(kpem)
            cfile.write('\n')
            cfile.write(cpem)
    except Exception, e:
        logger.error("Failed to write decrypted cert/key to '%s': %s", prcertkeyFile, e)
        sys.exit(-1)

    logger.info("... Cleared password from SSL cert/key '%s'", prcertkeyFile)

def clearSSHKey(keyFile):

    text = ""
    #Check if the key is encrypted
    try:
        with open(keyFile, 'r') as f:
            text = f.read()
    except Exception, e:
        logger.error("Failed to read SSH key from '%s': %s", keyFile, e)
        return

    index = text.find("ENCRYPTED")
    if index == -1 :
        logger.info("SSH Key does not have a passphrase. Skip.")
        return 

    k = loadKeyFromFile(keyFile)
    if not k:
        logger.warning("Failed to load key from file. Unable to remove passphrase. Exit!")
        sys.exit()
    logger.debug("Loaded key from %s" %keyFile)

    question = "Do you want to make a backup of your encrypted key (%s)" % keyFile
    if getYNAns(question):
      backupEncFile(keyFile)

    k.save_to_file(keyFile)
    logger.debug("Saved key to %s" %keyFile)
    logger.info("... Cleared passphrase from SSH key '%s'", keyFile)

def backupEncFile(fullname):
    # Make a backup copy of the key
    filedir = os.path.dirname(fullname)
    filename = os.path.splitext(os.path.basename(fullname))[0]
    extension = os.path.splitext(os.path.basename(fullname))[1]
    bakfile = os.path.join(filedir, filename + '_enc' + extension)
    bakfile = getFileName(bakfile)
    try:
        shutil.copyfile(fullname, bakfile)
        logger.info("Made back up of encrypted key to '%s'" %bakfile)
    except Exception, e:
        logger.error("Failed to copy '%s' to backup '%s': %s", fullname, bakfile, e)

def findSSHPrivKeys( config ):
    """Look in omni_config for user and key information of the public keys that
    are installed in the nodes. It uses the global variable config and returns
    keyList which is a dictionary of keyLists per user"""

    keyList = [] 
    if not config.has_key('users'):
      logger.warn("Your omni_config is missing the 'users' attribute.")
      return keyList

    for user in config['users']:
        # convert strings containing public keys (foo.pub) into
        # private keys (foo)
        privuserkeys = string.replace(user['keys'].replace(" ",""), ".pub","")
        privuserkeys = privuserkeys.split(",")
        for key in privuserkeys:
            key = os.path.expanduser(key)
            if os.path.exists(key):
              keyList.append(key)
    return keyList

def removeSSHPassphrase(key):
  question = "Do you want to remove the passphrase from your ssh-key (%s, key used to login to compute resources)" % key
  if getYNAns(question):
    if not os.path.exists(key):
        raise Exception("SSH Key file '%s' does not exist" % key)
    logger.info("\n\tTHIS SCRIPT WILL REMOVE THE PASSPHRASE FROM YOUR SSH KEY.")

    # Check if this is a cert file
    if fileIsSSLCert(key) :
      logger.debug("File appears to be a cert and key despite what user said")
      clearCert(key)
    else :
     clearSSHKey(key)


def removeSSLPassphrase(prcertkey):
  question = "Do you want to remove the passphrase from the private key of your SSL cert (%s)" % prcertkey
  if getYNAns(question):
    if not os.path.exists(prcertkey):
        raise Exception("SSL Key file '%s' does not exist" % prcertkey)
    logger.info("\n\tTHIS SCRIPT WILL REPLACE '%s' WITH AN UNENCRYPTED CERT KEY. A BACKUP OF THE ORIGINAL CERT WILL BE CREATED.\n" % prcertkey)
    # Check if this is a cert file
    if fileIsSSLCert(prcertkey) :
      clearCert(prcertkey)
    else :
      clearSSHKey(prcertkey)
       
def fileIsSSLCert(filename):
    text = ""
    try:
        with open(filename, 'r') as f:
            text = f.read()
    except Exception, e:
        logger.error("Failed to read cert/key from '%s': %s", filename, e)
        sys.exit(-1)

    pkey_match = re.findall("^-+BEGIN CERTIFICATE-+$.*?^-+END CERTIFICATE-+$", text, re.MULTILINE|re.S)
    if len(pkey_match) == 0:
      return False
    return True

def main():
    global logger
    argv = sys.argv[1:]
    opts = parseArgs(argv)
    configLogging(opts)

    logger.debug("Running %s with options %s" %(sys.argv[0], opts))

    # The script will either run with a config file or with the -p or -k option
    # The -c option takes precedent so start with that
    checkForConfig = True

    if opts.configfile : 
      # If you have specified the configfile then -p and -k will be ignored
      if opts.prkey or opts.prcertkey : 
        logger.warn("You have specified an omni config file location; the -p"+\
                    " and -k options are going to be ignored.")
        opts.prkey = None
        opts.prcertkey = None

    # If the user provided the location of a private key for the cert start from
    # remove the passphrase
    if opts.prcertkey : 
      opts.prcertkey= os.path.expanduser(opts.prcertkey)
      removeSSLPassphrase(opts.prcertkey)
      checkForConfig = False
        
    if opts.prkey :
      opts.prkey= os.path.expanduser(opts.prkey)
      removeSSHPassphrase(opts.prkey)
      checkForConfig = False
    
    if checkForConfig : 
      try:
          config = load_config(opts, logger)
      except OmniError, oe:
          sys.exit(-1)

      # Form config find the private key for the SSL cert
      prcertkey = config["selected_framework"]["key"]
      prcertkey= os.path.expanduser(prcertkey)
      removeSSLPassphrase(prcertkey)

      # Form config find all the private SSH keys stored in the user computer
      keylist = findSSHPrivKeys(config)
      logger.debug("List of private ssh keys: %s" %(str(keylist)))
      for key in keylist : 
        key = os.path.expanduser(key)
        removeSSHPassphrase(key)

if __name__ == "__main__":
    sys.exit(main())
 

