#!/usr/bin/env python

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

""" The omni-configure.py script.
    This script is meant to help new users setup their omni config in 
    a standard way. Although many of the parameters can be customized using
    command line options, the user should be able to run the script
    with the default configuration and configure Omni. This script should be
    used by new user that want a default configuration of Omni. If advanced
    configuration is needed (multiple users, etc) this should still be done
    manually by editing the omni configuration file. 
"""

import string, re
import sys, os, platform, shutil
import zipfile
from subprocess import Popen, PIPE
import ConfigParser
import optparse
import logging
from sfa.trust.certificate import Certificate, Keypair

logger = None

DEFAULT_PRIVATE_CERT_KEY = {
                            'pg' : "~/.ssh/geni_cert_key_pg",
                            'pl' : "~/.ssh/geni_cert_key_pl",
                            'portal' : "~/.ssl/geni_ssl_portal.key"
                           }

DEFAULT_PRIVATE_KEY = {
                        'pg' : "~/.ssh/geni_key_pg",
                        'pl' : "~/.ssh/geni_key_pl",
                        'portal' : "~/.ssh/geni_key_portal"
                      }

DEFAULT_CERT = {
                 'pg' : "~/.ssl/geni_cert_pg.pem",
                 'pl' : "~/.ssl/geni_cert_pl.gid",
                 'portal' : "~/.ssl/geni_cert_portal.pem"
               }


def getYNAns(question):
    valid_ans=['','y', 'n']
    answer = raw_input("%s [Y,n]?" % question).lower()
    while answer not in valid_ans:
        answer = raw_input("Your input has to be 'y' or <ENTER> for yes, 'n' for no:").lower()
    if answer == 'n':
        return False
    return True

def loadKeyTextFromFile(filename):
    """ This function parses the text in the file 'filename'
        and loads in a string the whole text that corresponds 
        to a private key.
        * Returns a list of strings, each string corresponds to 
          a key. If there are no keys the list is empty
    """
    f = open(filename, 'r')
    text = f.read()
    f.close()
    pkey_match = re.findall("^-+BEGIN RSA PRIVATE KEY-+$.*?^-+END RSA PRIVATE KEY-+$", text, re.MULTILINE|re.S)

    return pkey_match

def setPrivateCertKey(opts):
    ''' This function figures out if there is
        an appropriate ssl key to use for the cert
    '''

    # First check the certificate file. If there is a private
    # key included, then use that
    keyList = loadKeyTextFromFile(opts.cert)
    if len(keyList) > 0 :
       if opts.prcertkey != "" :
         logger.warn("Private key present in the cert file %s. Your option of %s, has been overwritten" % (opts.cert, opts.prcertkey))
          
       opts.prcertkey = opts.cert
    # If the user wants to use the default name
    else :
      if opts.prcertkey == "" :
        opts.prcertkey = DEFAULT_PRIVATE_CERT_KEY[opts.framework]
        opts.prcertkey = os.path.expanduser(opts.prcertkey)
        opts.prcertkey = os.path.abspath(opts.prcertkey)

    logger.debug("Using as private key for the cert file: %s" %opts.prcertkey)

def modifySSHConfigFile(private_key_file):
    """ This function will modify the ssh config file (~/.ssh/config) 
        to include the 'private_key_file' as a default identity
        Also adds the Identity of 'id_rsa' if it exists in the file to ensure
        that it will still be used. 
        The Identities are added only if they are not already there.
    """
    ssh_conf_file = os.path.expanduser('~/.ssh/config')
    logger.debug("Modifying ssh config (%s) file to include generated public key.", ssh_conf_file)
    f = open(ssh_conf_file, 'a+')
    text = f.read()

    # Before adding the private key to the config file 
    # ensure that there is a line about the default id_rsa file

    filename = os.path.expanduser('~/.ssh/id_rsa')
    if os.path.exists(filename):
        linetoadd = "IdentityFile %s\n" % filename 
        # Check to see if there is already this line present
        index = text.find(linetoadd)
        if index == -1 :
            f.write(linetoadd)
            logger.info("Added to %s this line:\n\t'%s'" %(ssh_conf_file, linetoadd))

    # Add the private key to ssh_config to be used without having to specify it
    # with the -i option
    linetoadd = "IdentityFile %s\n" % private_key_file
    index = text.find(linetoadd)
    if index == -1 :
        f.write(linetoadd)
        logger.info("Added to %s this line:\n\t'%s'" %(ssh_conf_file, linetoadd))

    f.close()

def validate_pg(opts):
    """ This function verifies that the we have everything we need
        to run if framework is 'pg'
    """
    # If framework is pgeni, check that the cert file is in the right place
    if not os.path.exists(opts.cert) or os.path.getsize(opts.cert) < 1:
            sys.exit("Geni certificate not in '"+opts.cert+"'. \nMake sure you \
place the .pem file that you downloaded from the Web UI there,\nor \
use the '-p' option to specify a custom location of the certificate.\n")

    logger.info("Using certfile %s", opts.cert)
    
    setPrivateCertKey(opts)

    if not os.path.exists(opts.prcertkey) or os.path.getsize(opts.prcertkey) < 1:
            sys.exit("Private key for the certificate not in '"+opts.prcertkey+"'. \n")

    logger.debug("Using private key for the cert file %s", opts.prcertkey)
    
def validate_pl(opts):
    """ This function verifies that the we have everything we need
        to run if framework is 'pl'
    """

    # If framework is planetlab, check that the key are in the right place
    if not os.path.exists(opts.cert) or os.path.getsize(opts.cert) < 1:
            sys.exit("\nScript currently does not support automatic download of \
PlanetLab cert.\nIf you have a copy place it at '"+opts.cert+"', \nor \
use the '-p' option to specify a custom location of the certificate.\n")

    setPrivateCertKey(opts)

    if not os.path.exists(opts.prcertkey) or \
       os.path.getsize(opts.prcertkey) < 1:
      sys.exit("\nPlanetLab private key not in '"+opts.prcertkey+"'. \n\
      Make sure \
you place the private key registered with PlanetLab there or use\n\
the '-k' option to specify a custom location for the key.\n")

    logger.info("Using certfile %s", opts.cert)
    logger.info("Using PlanteLab private key file %s", opts.prcertkey)

def validate_portal(opts):
    """ This function verifies that the we have everything we need
        to run if framework is 'portal'
    """

    # If framework is portal, check that the bundle file is in the right place
    if not os.path.exists(opts.portal_bundle) or \
           os.path.getsize(opts.portal_bundle) < 1 :
        sys.exit("\nPortal bundle not in '"+opts.portal_bundle+"'.\n\
Make sure you place the bundle downloaded from the portal there,\nor \
use the '-z' option to specify a custom location.\n")

    if not zipfile.is_zipfile(opts.portal_bundle) :
        sys.exit("\nFile '"+opts.portal_bundle+"' not a valid zip file.\n"+\
                 "Exit!")
    validate_bundle(opts.portal_bundle)
    # In the case of the portal there is no cert
    # file yet, extract it
    opts.cert = getFileName(opts.cert)
    extract_cert_from_bundle(opts.portal_bundle, opts.cert)

    setPrivateCertKey(opts)
  
    # If the private key for the cert is not in the cert, check
    # that the file actually exist
    if cmp(opts.prcertkey, opts.cert) : 
      if not os.path.exists(opts.prcertkey) or \
           os.path.getsize(opts.prcertkey) < 1 :
        os.remove(opts.cert)
        sys.exit("\nPrivate SSL key not in '"+opts.prcertkey+"'.\n\
Either place your key in the above file or use\n \
the '-k' option to specify a custom location for the key.\n")

    logger.info("Using portal bundle %s", opts.portal_bundle)

def bundle_extract_keys(omnizip, opts) :
   """ function that will extract any key files in zip bundle
       in the approprate places
         * private key will go to 'opts.prkey' and the corresponding
           public key will go to 'opts.prkey'.pub
         * all public keys except from the one corresponding to the 
           included private key will go under ~/.ssh/
           for any key with no extension we will add .pub
   """
   pubkey_list = []
   filelist = omnizip.namelist()
   # Keep track of the public key name in the bundle
   # that corresponds to the private key, so that we 
   # don't copy it again since it has a special name
   pubkey_of_priv_inbundle = "empty"
   # Make a first pass to extract the private and corresponding
   # public keys
   for x in filelist : 
      if x.startswith('ssh/private') :
        # verify that we have the corresponding public key
        xpub = 'ssh/public/'+os.path.basename(x)+'.pub'
        if xpub not in filelist :
          # Remove the cert before we exit
          os.remove(opts.cert)
          sys.exit("There is no public key that corresponds to the private "+
                   "key in the bundle, please email help@geni.net")

        # Place the private key in the right place
        omnizip.extract(x, '/tmp')
        opts.prkey = copyPrivateKeyFile(os.path.join('/tmp/', x), opts.prkey)

        # Place the public key in the right place
        omnizip.extract(xpub, '/tmp')
        pubname = opts.prkey+'.pub'

        # Try and see if this public key name exist
        tmp = getFileName(pubname)
        # if the file already exists, exit since we can't have a pub key 
        # that does not match the private key
        if cmp(tmp, pubname) :
          # Remove the cert, the private key, and the /tmp/ssh folder before
          # we exit
          os.remove(opts.cert)
          os.remove(opts.prkey)
          shutil.rmtree('/tmp/ssh')
          sys.exit("There is already a key named "+pubname+". Remove it first "+
                   "and then rerun the script")
        
        logger.debug("Place public key %s at %s" \
                     %(pubkey_of_priv_inbundle, pubname))
        shutil.move(os.path.join('/tmp/', xpub), pubname)
        pubkey_list.append(pubname)
        pubkey_of_priv_inbundle = xpub
   
   # Make a second pass to extract all public keys other than the one that 
   # corresponds to the private key
   for x in filelist : 
      if x.startswith('ssh/public') and \
         not x.startswith(pubkey_of_priv_inbundle) :

        omnizip.extract(x, '/tmp')
        xname = os.path.basename(x)
        xbase = os.path.splitext(xname)[0]
        xfullpath = os.path.join('~/.ssh/', xbase + '.pub')
        xfullpath = os.path.abspath(getFileName(xfullpath))

        # Check if the file ~/.ssh exists and create it if not
        dstdir = os.path.dirname(xfullpath)
        if os.path.expanduser(dstdir) :
          if not os.path.exists(dstdir) :
            os.makedirs(dstdir)
          
        logger.debug("Copy public key %s to %s" %(x, xfullpath))
        shutil.move(os.path.join('/tmp/', x), xfullpath)
        pubkey_list.append(xfullpath)

   shutil.rmtree('/tmp/ssh')

   return pubkey_list

def bundle_has_keys(omnizip) :
   """ function that checks if there are any keys
       in the ZipFile omnizip (downloaded from the portal)
   """
   haskeys = False
   filelist = omnizip.namelist()
   for x in filelist : 
      if x.startswith('ssh') :
        haskeys = True
   return haskeys
 
def bundle_has_private_key(omnizip) :
   """ function that checks if there are any keys
       in the ZipFile omnizip (downloaded from the portal)
   """
   hasprkey = False
   filelist = omnizip.namelist()
   for x in filelist : 
      if x.startswith('ssh/private') :
        hasprkey = True
   return hasprkey

def validate_bundle(filename) :
    """ This function ensures that the bundle has all the 
        necessary files
    """
    omnizip = zipfile.ZipFile(filename)
    filelist = omnizip.namelist()
    # Check if it has the absolutely necessary files
    #   * omni_config
    #   * geni_cert.pem

    if 'omni_config' not in filelist : 
      sys.exit("Portal bundle "+filename+" does not contain omni_config "+
               "file. Please email help@geni.net.")
    if 'geni_cert.pem' not in filelist : 
      sys.exit("Portal bundle "+filename+" does not contain geni_cert.pem "+
               "file. Please email help@geni.net.")
    # Check what keys are in the bundle and print warning messages
    # accordingly
    haskeys = False
    haskeys = False
    hasprkey = False
    for x in filelist : 
      if x.startswith('ssh') :
        haskeys = True
      if x.startswith('ssh/private') :
        hasprkey = True
    if haskeys is False : 
      logger.warn("NO SSH KEYS. There are no keys in the bundle you "+
                  "downloaded from the portal. We will create a pair "+
                  "for you based on your geni certificate. This key "+
                  "will only be used for resources you reserve with omni!")

    else :
      if hasprkey is False :
        pub_key_file_list = get_pub_keys_from_bundle(omnizip)
        # XXX BUG: This will probably fail if the public key has an
        # extension other than '.pub'
        key_list =[(x,os.path.splitext(x)[0]) for x in pub_key_file_list]
        warn_message = "\nThere is no PRIVATE KEY in the bundle. In order "+\
                    "for some omni scripts to work (readyToLogin.py, "+\
                    "remote-execute.py) you will need to place a copy "+\
                    "of the corresponding private keys at: "
        for (pub,pr) in key_list :
          warn_message += "\n\t* private key for '"+pub+"' at ~/.ssh/"+pr
        warn_message +="\n"
        logger.warn(warn_message)

    omnizip.close()
   

def get_pub_keys_from_bundle(omnizip) :
    """ This function takes as input a ZipFile that corresponds
        to a bundle dowloaded from the GENI Portal and returns 
        a list of public key filenames
    """
    filelist = omnizip.namelist()
    publist = []
    for f in filelist :
      if f.startswith("ssh/public/") :
        publist.append(os.path.basename(f))  

    return publist


def generatePublicKey(private_key_file):
    """ This function generates a public key using ssh-keygen 
        shell command. The public key is based on the 
        the private key in the 'private_key_file'
        The function returns the name of the public key file
        or None if the creation failed
    """
    args = ['ssh-keygen', '-y', '-f']
    args.append(private_key_file)
    logger.debug("Create public key using ssh-keygen: '%s'", args)

    succ = False
    for i in range(0,3) :
        p = Popen(args, stdout=PIPE)
        public_key = p.communicate()[0]
        if p.returncode != 0:
            logger.warning("Error creating public key, passphrase might be wrong.")
            continue
        succ = True
        break
    # If the key was not loaded properly return None
    if not succ:
        logger.warning("Unable to create public key.")
        return None
    public_key_file = private_key_file + '.pub'
    try :
        f = open(public_key_file,'w')
    except :
        logger.warning("Error opening file %s for writing. Make sure that you have the right permissions." % public_key_file)
        return None
    f.write("%s" % public_key)
    f.close()
    logger.info("Public key stored at: %s", public_key_file)
    return public_key_file

def getFileName(filename):
    """ This function takes as input a filename and if it already 
        exists it will ask the user whether to replace it or not 
        and if the file shouldn't be replaced it comes up with a
        unique name
    """
    # If the file exists ask the # user to replace it or not
    filename = os.path.expanduser(filename)
    filename = os.path.abspath(filename)
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
                if platform.system().lower().find('darwin') != -1 :
                    tmp_pk_file = basename + '(' + str(i) + ')' + extension
                else :
                    tmp_pk_file = basename + '-' + str(i) + extension
            filename = tmp_pk_file
    return filename

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
        except :
            logger.info("Unable to load private key, maybe you misstyped the passphrase. Try again.")
            continue
        succ = True
        break
    # If the key was not loaded properly return None
    if not succ:
        k = None
    return k

def copyPrivateKeyFile(src_file, dst_file):
    """ This function creates a copy of a private key file
        from 'src_file' to 'dst_file'. The src_file might be in .pem format
        so it is not a simple file copy, but we parse the file to only get
        the private key and write it to the destination file
    """

    if os.path.exists(dst_file):
        # Load current and existing keys to see if they are the same
        logger.info("Loading SSH key from %s", src_file)
        k = loadKeyFromFile(src_file)
        if k:
            logger.info("File %s already exists. Loading SSH key from %s", dst_file, dst_file)
            k_exist = loadKeyFromFile(dst_file)
        if not k or not k_exist or not k_exist.is_same(k) : 
            dst_file = getFileName(dst_file)
    else :
      dstdir = os.path.dirname(dst_file)
      if os.path.expanduser(dstdir) :
        if not os.path.exists(dstdir) :
          os.makedirs(dstdir)
        
    # We don't do a blind copy in case the src file is in .pem format but we
    # extract the key from the file
    keyList = loadKeyTextFromFile(src_file)

    if len(keyList) == 0 :
        logger.info("No private key in the file. Exit!")
        sys.exit()

    f = open(dst_file, 'w+')
    # Use only the first key, if multiple are present
    f.write(keyList[0])
    f.close()
    logger.info("Private key stored at: %s", dst_file)
    # Change the permission to something appropriate for keys
    logger.debug("Changing permission on private key to 600")
    os.chmod(dst_file, 0600)
    os.chmod(src_file, 0600)
    return dst_file

def parseArgs(argv, options=None):
    """Construct an Options Parser for parsing omni-configure command line
    arguments, and parse them.
    """

    usage = "\n Script for automatically configuring Omni."

    parser = optparse.OptionParser(usage=usage)
    parser.add_option("-c", "--configfile", default="~/.gcf/omni_config",
                      help="Config file location [DEFAULT: %default]", metavar="FILE")
    parser.add_option("-p", "--cert", default="",
                      help="File location of user SSL certificate. Default is "+\
                      "based on the selected framework (see -f option) [DEFAULT: %s]" % str(DEFAULT_CERT), metavar="FILE")
    parser.add_option("-k", "--prcertkey", default="",
                      help="File location of private key for the user SSL "+\
                      "certificate. Default is based on the selected framework"+\
                      " (see -f option) [DEFAULT: %s]" % str(DEFAULT_PRIVATE_CERT_KEY), metavar="FILE")
    parser.add_option("-e", "--prkey", default="",
                      help="File location of private SSH key for logging "+ \
                      "in to compute resources. Default is based on the "+\
                      "selected framework (see -f option) [DEFAULT: %s]" % str(DEFAULT_PRIVATE_KEY), metavar="FILE")
    parser.add_option("-z", "--portal-bundle", default="~/Downloads/omni-bundle.zip",
                      help="Bundle downloaded from the portal for configuring Omni [DEFAULT: %default]", metavar="FILE")
    parser.add_option("-f", "--framework", default="portal", type='choice',
                      choices=['pg', 'pl', 'portal'],
                      help="Control framework that you have an account with [options: [pg, pl, portal], DEFAULT: %default]")
    parser.add_option("--pick-project", dest="pick_project", 
                      action="store_true",
                      default=False, help="Lets you choose which project to use as default from the projects in the bundle downloaded from the portal")
    parser.add_option("-v", "--verbose", default=False, action="store_true",
                      help="Turn on verbose command summary for omni-configure script")

    if argv is None:
        parser.print_help()
        return

    (opts, args) = parser.parse_args(argv, options)
    return opts, args

def initialize(opts):
    global logger

    #Check if directory for config file exists
    # Expand the configfile to a full path
    opts.configfile= os.path.expanduser(opts.configfile)
    opts.configfile= os.path.abspath(opts.configfile)
    logger.info("Using configfile: %s", opts.configfile)
    configdir = os.path.dirname(opts.configfile)
    if not os.path.exists(configdir):
      # If the directory does not exist but it is the 
      # default directory, create it, if not print an error
      if not cmp(os.path.expanduser('~/.gcf'), configdir):
        logger.info("Creating directory: %s", configdir)
        os.makedirs(configdir)
      else:
        sys.exit('Directory '+ configdir + ' does not exist!')

    # If the value is the default add the appropriate file extention
    # based on the framework

    if opts.cert == "" :
        opts.cert = DEFAULT_CERT[opts.framework]
        logger.debug("Cert is the default. Certfile is %s", opts.cert)
            
    if opts.prkey == "" :
        opts.prkey = DEFAULT_PRIVATE_KEY[opts.framework]
        logger.debug("Private SSH key is the default. File is %s", opts.cert)

    # Expand the cert file to a full path
    opts.cert= os.path.expanduser(opts.cert)
    opts.cert= os.path.abspath(opts.cert)

    # Expand the private file to a full path
    opts.prkey = os.path.expanduser(opts.prkey)
    opts.prkey = os.path.abspath(opts.prkey)

    # Expand the portal bundle file to a full path
    opts.portal_bundle = os.path.expanduser(opts.portal_bundle)
    opts.portal_bundle = os.path.abspath(opts.portal_bundle)

    #validate we have all the information we need per framework
    if not cmp(opts.framework,'pg'): 
        validate_pg(opts)

    if not cmp(opts.framework,'pl'):
        validate_pl(opts)

    if not cmp(opts.framework,'portal'):
        validate_portal(opts)

    # Expand the prcertkey file to a full path
    # In order to properly set the private key for the cert
    #   we need to parse the cert file and look to see if there
    #   is one included, but we can't do this here, so this
    #   happens in each of the validate calls
    opts.prcertkey = os.path.expanduser(opts.prcertkey)
    opts.prcertkey = os.path.abspath(opts.prcertkey)
       
def extract_cert_from_bundle(filename, dest) :
    """ This functions extracts a cert named geni_cert.pem
        out of a bundle downladed from the portal named <filename>
        and saves it at <dest>
    """
    omnizip = zipfile.ZipFile(filename)
    # extract() can only take a directory as argument
    # extract it at /tmp and then move it to the file 
    # we want
    omnizip.extract('geni_cert.pem', '/tmp')
    omnizip.close()
    # If the destination does not exist create it
    destdir = os.path.dirname(dest)
    if os.path.expanduser(destdir) :
      if not os.path.exists(destdir) :
        os.makedirs(destdir)
    shutil.move('/tmp/geni_cert.pem', dest)
    
def configureSSHKeys(opts):
    global logger

    # Use the default place for the geni private key
    private_key_file = opts.prkey

    if not cmp(opts.framework, 'portal') :
      omnizip = zipfile.ZipFile(opts.portal_bundle)
      # If there are no keys in the bundle create a pair
      # the same was as for a PG framework
      if not bundle_has_keys(omnizip) :
        logger.info("Bundle does not have keys, use as Private SSH key the "+
                    "key of the cert "+opts.cert)
        pkey=opts.prcertkey
      else :
      # if there are keys, then extract them in the right place
      # and return the list of pubkey filenames for use in the 
      # omni_config
        pubkey_list = bundle_extract_keys(omnizip, opts)
        return pubkey_list
          
    logger.info("\n\n\tCREATING SSH KEYPAIR")

    # This is the place 
    if not cmp(opts.framework,'pg'):
      logger.debug("Framework is ProtoGENI use as Private SSH key the key in the cert: %s", opts.cert)
      pkey = opts.prcertkey
    else :
      if not cmp(opts.framework,'pl'):
        logger.debug("Framework is PlanetLab use as Private SSH key the pl key: %s", opts.prcertkey)
        pkey = opts.prcertkey

    # Make sure that the .ssh directory exists, if it doesn't create it
    ssh_dir = os.path.expanduser('~/.ssh')
    if not os.path.exists(ssh_dir) :
        logger.info("Creating directory: %s", ssh_dir)
        os.makedirs(ssh_dir)

    private_key_file = copyPrivateKeyFile(pkey, private_key_file)

    public_key_file = generatePublicKey(private_key_file)
    if not public_key_file:
        #we failed at generating a public key, remove the private key and exit
        os.remove(private_key_file)
        sys.exit(-1)

    modifySSHConfigFile(private_key_file)
    
    return [public_key_file]

def getUserInfo(cert) :

    global logger

    # The user URN is in the Alternate Subject Data
    cert_alt_data = cert.get_data()
    data = cert_alt_data.split(',')
    user_urn_list = [o for o in data if o.find('+user+') != -1]
    logger.debug("User URN list in the cert is: %s", user_urn_list)

    # If there is no data that has the string '+user+' this probably means that 
    # the provided cert is not a user cert
    if len(user_urn_list) == 0:
      sys.exit("The certificate is probably not a user cert")

    # XXX If there are more data with the '+user+' string probably more than one
    # user URNs in the cert. For now exit, but maybe the right thing would be to
    # pick one?
    if len(user_urn_list) > 1:
      sys.exit("There are more than one user URNs in the cert. Exit!")

    urn = user_urn_list[0].strip().lstrip('URI:')
    logger.debug("User URN in the cert is: %s", urn)
    user = urn.split('+')[-1]
    logger.debug("User is: %s", user)

    return(user, urn)

def createConfigFile(opts, public_key_list):
    """ This function creates the omni_config file. 
        It will rewrite any existing omni_config file
        and makes a backup of the omni_config file 
        of the form omni_config_<i> 
    """
    global logger

    cert = Certificate(filename=opts.cert)

    if not cmp(opts.framework,'pg'):
      omni_config_str = getPGConfig(opts, public_key_list, cert)
    else :
      if not cmp(opts.framework, 'pl'):
        omni_config_str = getPLConfig(opts, public_key_list, cert)
      else :
        if not cmp(opts.framework, 'portal'):
          omni_config_str = getPortalConfig(opts, public_key_list, cert)
    
    # Write the config to a file
    omni_bak_file = opts.configfile
    omni_bak_file = getFileName(omni_bak_file)
    if omni_bak_file != opts.configfile:
        logger.info("Your old omni configuration file has been backed up at %s" % omni_bak_file)
        shutil.copyfile(opts.configfile, omni_bak_file)
        
    try: 
        f = open(opts.configfile, 'w')
    except:
        logger.warning("Error opening file %s for writing. Make sure that you have the right permissions." % opts.configfile)
        sys.exit(-1)

    print >>f, omni_config_str
    f.close()
    logger.info("Wrote omni configuration file at: %s", opts.configfile)
   
    
def loadProjects(filename) :
    f = open(filename)
    content = f.read()
    f.close()
    proj_re = '^#*\s*default_project\s*=\s*(.*)$'
    return re.findall(proj_re, content, re.MULTILINE)

def fixNicknames(config) :
    config['aggregate_nicknames'] = {}
    # ExoGENI AMs

def getPortalOmniSection(opts, config, user, projects) :

    omni_section = """
[omni]
default_cf=%s
users=%s
default_project=%s
""" %(opts.framework, user, config['omni']['default_project'])

    for p in projects :
      if p != config['omni']['default_project'] :
        omni_section +="#default_project=%s\n" % p

    return omni_section

def getPortalSFSection(opts, config) :

    return """
[portal]
type = pgch
authority = %s
ch = %s
sa = %s
cert = %s
key = %s
""" %(
      config['selected_framework']['authority'], 
      config['selected_framework']['ch'], 
      config['selected_framework']['sa'],
      opts.cert, opts.prcertkey)

def getPortalUserSection(opts, user, user_urn, public_key_list) :
    return """
[%s]
urn=%s
keys=%s
""" %(user, user_urn, ','.join(public_key_list))

def getPortalAMNickSection(opts, config) :

    return """
#------AM nicknames
# Format :
# Nickname=URN, URL
# URN is optional
[aggregate_nicknames]

# ProtoGENI AMs
pg-gpo1=urn:publicid:IDN+pgeni.gpolab.bbn.com+authority+cm,https://pgeni.gpolab.bbn.com:12369/protogeni/xmlrpc/am/1.0
pg-gpo2=urn:publicid:IDN+pgeni.gpolab.bbn.com+authority+cm,https://pgeni.gpolab.bbn.com:12369/protogeni/xmlrpc/am/2.0
pg-gpo=urn:publicid:IDN+pgeni.gpolab.bbn.com+authority+cm,https://pgeni.gpolab.bbn.com:12369/protogeni/xmlrpc/am/2.0
pg-bbn1=urn:publicid:IDN+pgeni.gpolab.bbn.com+authority+cm,https://pgeni.gpolab.bbn.com:12369/protogeni/xmlrpc/am/1.0
pg-bbn2=urn:publicid:IDN+pgeni.gpolab.bbn.com+authority+cm,https://pgeni.gpolab.bbn.com:12369/protogeni/xmlrpc/am/2.0
pg-bbn=urn:publicid:IDN+pgeni.gpolab.bbn.com+authority+cm,https://pgeni.gpolab.bbn.com:12369/protogeni/xmlrpc/am/2.0

pg-utah1=urn:publicid:IDN+emulab.net+authority+cm,https://www.emulab.net:12369/protogeni/xmlrpc/am/1.0
pg-utah2=urn:publicid:IDN+emulab.net+authority+cm,https://www.emulab.net:12369/protogeni/xmlrpc/am/2.0
pg-utah3=urn:publicid:IDN+emulab.net+authority+cm,https://www.emulab.net:12369/protogeni/xmlrpc/am/3.0
pg-utah=urn:publicid:IDN+emulab.net+authority+cm,https://www.emulab.net:12369/protogeni/xmlrpc/am/2.0

pg-ky1=urn:publicid:IDN+uky.emulab.net+authority+cm,https://www.uky.emulab.net:12369/protogeni/xmlrpc/am/1.0
pg-ky2=urn:publicid:IDN+uky.emulab.net+authority+cm,https://www.uky.emulab.net:12369/protogeni/xmlrpc/am/2.0
pg-ky3=urn:publicid:IDN+uky.emulab.net+authority+cm,https://www.uky.emulab.net:12369/protogeni/xmlrpc/am/3.0
pg-ky=urn:publicid:IDN+uky.emulab.net+authority+cm,https://www.uky.emulab.net:12369/protogeni/xmlrpc/am/2.0
pg-uky1=urn:publicid:IDN+uky.emulab.net+authority+cm,https://www.uky.emulab.net:12369/protogeni/xmlrpc/am/1.0
pg-uky2=urn:publicid:IDN+uky.emulab.net+authority+cm,https://www.uky.emulab.net:12369/protogeni/xmlrpc/am/2.0
pg-uky3=urn:publicid:IDN+uky.emulab.net+authority+cm,https://www.uky.emulab.net:12369/protogeni/xmlrpc/am/3.0
pg-uky=urn:publicid:IDN+uky.emulab.net+authority+cm,https://www.uky.emulab.net:12369/protogeni/xmlrpc/am/2.0

# ExoGENI AMs, including OpenFlow ExoGENI AMs
eg-gpo=,https://bbn-hn.exogeni.net:11443/orca/xmlrpc
eg-bbn=,https://bbn-hn.exogeni.net:11443/orca/xmlrpc

eg-renci=,https://rci-hn.exogeni.net:11443/orca/xmlrpc

# ExoSM
eg-sm=,https://geni.renci.org:11443/orca/xmlrpc

# InstaGENI AMs, including OpenFlow InstaGENI AMs
ig-utah1=urn:publicid:IDN+utah.geniracks.net+authority+cm,https://boss.utah.geniracks.net:12369/protogeni/xmlrpc/am/1.0
ig-utah2=urn:publicid:IDN+utah.geniracks.net+authority+cm,https://boss.utah.geniracks.net:12369/protogeni/xmlrpc/am/2.0
ig-utah3=urn:publicid:IDN+utah.geniracks.net+authority+cm,https://boss.utah.geniracks.net:12369/protogeni/xmlrpc/am/3.0
ig-utah=urn:publicid:IDN+utah.geniracks.net+authority+cm,https://boss.utah.geniracks.net:12369/protogeni/xmlrpc/am/2.0

ig-gpo1=urn:publicid:IDN+instageni.gpolab.bbn.com+authority+cm,https://boss.instageni.gpolab.bbn.com:12369/protogeni/xmlrpc/am/1.0
ig-gpo2=urn:publicid:IDN+instageni.gpolab.bbn.com+authority+cm,https://boss.instageni.gpolab.bbn.com:12369/protogeni/xmlrpc/am/2.0
ig-gpo3=urn:publicid:IDN+instageni.gpolab.bbn.com+authority+cm,https://boss.instageni.gpolab.bbn.com:12369/protogeni/xmlrpc/am/3.0
ig-gpo=urn:publicid:IDN+instageni.gpolab.bbn.com+authority+cm,https://boss.instageni.gpolab.bbn.com:12369/protogeni/xmlrpc/am/2.0
ig-bbn1=urn:publicid:IDN+instageni.gpolab.bbn.com+authority+cm,https://boss.instageni.gpolab.bbn.com:12369/protogeni/xmlrpc/am/1.0
ig-bbn2=urn:publicid:IDN+instageni.gpolab.bbn.com+authority+cm,https://boss.instageni.gpolab.bbn.com:12369/protogeni/xmlrpc/am/2.0
ig-bbn3=urn:publicid:IDN+instageni.gpolab.bbn.com+authority+cm,https://boss.instageni.gpolab.bbn.com:12369/protogeni/xmlrpc/am/3.0
ig-bbn=urn:publicid:IDN+instageni.gpolab.bbn.com+authority+cm,https://boss.instageni.gpolab.bbn.com:12369/protogeni/xmlrpc/am/2.0

""" 


def getPortalConfig(opts, public_key_list, cert) :
    # The bundle contains and omni_config
    # extract it and load it
    omnizip = zipfile.ZipFile(opts.portal_bundle)
    omnizip.extract('omni_config', '/tmp')

    config = loadConfigFile('/tmp/omni_config')
    projects = loadProjects('/tmp/omni_config')
    os.remove('/tmp/omni_config')

    if not config['selected_framework'].has_key('authority'):
      sys.exit("\nERROR: Your omni bundle is old, you must get a new version:\n"+
                  "\t 1. Download new omni-bundle.zip from the Portal\n"+
                  "\t 2. Rerun omni-configure.py"+
                  "\nExiting!")

    if len(projects) == 0 :
      logger.warn("\nWARNING: You are not a member of any projects! You will need to:\n"+
                  "\t 1. Join a project in the portal\n"+
                  "\t 2. Use the -r flag with omni.py to specify your project "+
                  "or \n\t    download a new bundle and rerun omni-configure.py")

      defproj = ""
    else : 
      defproj = config['omni']['default_project']
      if len(projects) > 1 and opts.pick_project :
        defproj = selectProject(projects, defproj)

    # Replace default project with the selected one
    config['omni']['default_project'] = defproj

    (user, user_urn) = getUserInfo(cert)

    omni_section = getPortalOmniSection(opts, config, user, projects)
    user_section = getPortalUserSection(opts, user, user_urn, public_key_list)
    cf_section = getPortalSFSection(opts, config)
    amnick_section = getPortalAMNickSection(opts, config)

    return omni_section + user_section + cf_section + amnick_section

def selectProject(projects, defproj) : 
    print("\nChoose one of your projects as your default:")
    i = 1
    for p in projects :
      if p == defproj :
        print("\t*%d. %s" % (i,p))
        defindex = i
      else :
        print("\t %d. %s" % (i,p))
      i+=1
    valid_ans = map(str, range(1, len(projects)+1)) + ['']
    answer = raw_input("Enter your choice[%d]: "%defindex)
    while answer not in valid_ans:
        answer = raw_input("Your input has to be 1 to %d: " % len(projects))

    if answer == '' :
      answer = defindex

    return projects[int(answer)-1]

def loadConfigFile(filename):
    confparser = ConfigParser.RawConfigParser()
    try:
        confparser.read(filename)
    except ConfigParser.Error as exc:
        logger.error("Config file %s could not be parsed."% filename)
        sys.exit(-1)

    # Load up the omni options
    config = {}
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

    # Copy the control framework into a dictionary
    cf = config['omni']['default_cf']
    config['selected_framework'] = {}
    for (key,val) in confparser.items(cf):
        config['selected_framework'][key] = val

    return config

def getPGConfig(opts, public_key_list, cert) :

    (user, user_urn) = getUserInfo(cert)

    if user_urn.find('emulab.net') != -1 :
        sa = 'https://www.emulab.net:12369/protogeni/xmlrpc/sa'
    else :
        if user_urn.find('pgeni.gpolab.bbn.com') != -1 :
            sa = 'https://www.pgeni.gpolab.bbn.com:12369/protogeni/xmlrpc/sa'
        else : 
          if user_urn.find('loni.org') != -1 :
            sa = 'https://cron.loni.org:443/protogeni/xmlrpc/sa'
          else:
            raise Exception("Creation of omni_config for users at %s is not supported. Please contact omni-users@geni.net" % user_urn.split('+')[-2]) 
    logger.debug("Framework is ProtoGENI, use as SA: %s", sa)

    cf_section = """
[%s]
type = pg
ch = https://www.emulab.net:12369/protogeni/xmlrpc/ch
sa = %s
cert = %s
key = %s
""" %(opts.framework, sa, opts.cert, opts.prcertkey)

    return createConfigStr(opts, public_key_list, cert, cf_section)

def getPLConfig(opts, public_key_list, cert) :
    # We need to get the issuer and the subject for SFA frameworks
    # issuer -> authority
    # subject -> user
    issuer = cert.get_issuer()
    logger.debug("Issuer of the cert is: %s", issuer)
    subject = cert.get_subject()
    logger.debug("Subject(user) of the cert is: %s", subject)

    (user, user_urn) = getUserInfo(cert)

    cf_section = """
[%s]
type = sfa
authority=%s
user=%s
cert=%s
key=%s
registry=http://www.planet-lab.org:12345
slicemgr=http://www.planet-lab.org:12347
""" %(opts.framework, issuer, subject, opts.cert, opts.prcertkey)

    return createConfigStr(opts, public_key_list, cert, cf_section)

def createConfigStr(opts, public_key_list, cert, cf_section) :
    
    (user, user_urn) = getUserInfo(cert)

    omni_config_dict = {
                        'cf' : opts.framework,
                        'user' : user, 
                        'urn' : user_urn,
                        'pkey' : ",".join(public_key_list),
                        'cf_section' : cf_section,
                       }
    logger.debug("omni_config_dict is: %s", omni_config_dict)

    omni_config_file="""
[omni]
default_cf = %(cf)s 
users = %(user)s

# ---------- Users ----------
[%(user)s]
urn = %(urn)s
keys = %(pkey)s

# ---------- Frameworks ----------
%(cf_section)s

#------AM nicknames
# Format :
# Nickname=URN, URL
# URN is optional
[aggregate_nicknames]

#ProtoGENI AMs
pg-gpo1=urn:publicid:IDN+pgeni.gpolab.bbn.com+authority+cm,https://pgeni.gpolab.bbn.com:12369/protogeni/xmlrpc/am/1.0
pg-gpo2=urn:publicid:IDN+pgeni.gpolab.bbn.com+authority+cm,https://pgeni.gpolab.bbn.com:12369/protogeni/xmlrpc/am/2.0
pg-gpo=urn:publicid:IDN+pgeni.gpolab.bbn.com+authority+cm,https://pgeni.gpolab.bbn.com:12369/protogeni/xmlrpc/am/2.0
pg-bbn1=urn:publicid:IDN+pgeni.gpolab.bbn.com+authority+cm,https://pgeni.gpolab.bbn.com:12369/protogeni/xmlrpc/am/1.0
pg-bbn2=urn:publicid:IDN+pgeni.gpolab.bbn.com+authority+cm,https://pgeni.gpolab.bbn.com:12369/protogeni/xmlrpc/am/2.0
pg-bbn=urn:publicid:IDN+pgeni.gpolab.bbn.com+authority+cm,https://pgeni.gpolab.bbn.com:12369/protogeni/xmlrpc/am/2.0

pg-utah1=urn:publicid:IDN+emulab.net+authority+cm,https://www.emulab.net:12369/protogeni/xmlrpc/am/1.0
pg-utah2=urn:publicid:IDN+emulab.net+authority+cm,https://www.emulab.net:12369/protogeni/xmlrpc/am/2.0
pg-utah3=urn:publicid:IDN+emulab.net+authority+cm,https://www.emulab.net:12369/protogeni/xmlrpc/am/3.0
pg-utah=urn:publicid:IDN+emulab.net+authority+cm,https://www.emulab.net:12369/protogeni/xmlrpc/am/2.0

pg-ky1=urn:publicid:IDN+uky.emulab.net+authority+cm,https://www.uky.emulab.net:12369/protogeni/xmlrpc/am/1.0
pg-ky2=urn:publicid:IDN+uky.emulab.net+authority+cm,https://www.uky.emulab.net:12369/protogeni/xmlrpc/am/2.0
pg-ky3=urn:publicid:IDN+uky.emulab.net+authority+cm,https://www.uky.emulab.net:12369/protogeni/xmlrpc/am/3.0
pg-ky=urn:publicid:IDN+uky.emulab.net+authority+cm,https://www.uky.emulab.net:12369/protogeni/xmlrpc/am/2.0
pg-uky1=urn:publicid:IDN+uky.emulab.net+authority+cm,https://www.uky.emulab.net:12369/protogeni/xmlrpc/am/1.0
pg-uky2=urn:publicid:IDN+uky.emulab.net+authority+cm,https://www.uky.emulab.net:12369/protogeni/xmlrpc/am/2.0
pg-uky3=urn:publicid:IDN+uky.emulab.net+authority+cm,https://www.uky.emulab.net:12369/protogeni/xmlrpc/am/3.0
pg-uky=urn:publicid:IDN+uky.emulab.net+authority+cm,https://www.uky.emulab.net:12369/protogeni/xmlrpc/am/2.0

# Public PlanetLab AM
plc=,https://www.planet-lab.org:12346/
plcv3=,https://sfav3.planet-lab.org:12346/
plc3=,https://sfav3.planet-lab.org:12346/

# Private myplc installations
pl-gpo=,https://myplc.gpolab.bbn.com:12346/
pl-bbn=,https://myplc.gpolab.bbn.com:12346/
pl-clemson=,https://myplc.clemson.edu:12346/
pl-stanford=,https://myplc.stanford.edu:12346/
pl-indiana=,https://myplc.grnoc.iu.edu:12346/
pl-gatech=,https://myplc.cip.gatech.edu:12346/

# OpenFlow AMs
of-gpo=,https://foam.gpolab.bbn.com:3626/foam/gapi/1
of-bbn=,https://foam.gpolab.bbn.com:3626/foam/gapi/1
of-stanford=,https://openflow4.stanford.edu:3626/foam/gapi/1
of-clemson=,https://foam.clemson.edu:3626/foam/gapi/1
of-rutgers=,https://nox.orbit-lab.org:3626/foam/gapi/1
of-indiana=,https://foam.noc.iu.edu:3626/foam/gapi/1
of-gatech=,https://foam.oflow.cip.gatech.edu:3626/foam/gapi/1
of-nlr=,https://foam.nlr.net:3626/foam/gapi/1
of-i2=,https://foam.net.internet2.edu:3626/foam/gapi/1
of-uen=,https://foamyflow.chpc.utah.edu:3626/foam/gapi/1

# ExoGENI AMs, including OpenFlow ExoGENI AMs
eg-gpo=,https://bbn-hn.exogeni.net:11443/orca/xmlrpc
eg-bbn=,https://bbn-hn.exogeni.net:11443/orca/xmlrpc
eg-of-gpo=,https://bbn-hn.exogeni.net:3626/foam/gapi/1
eg-of-bbn=,https://bbn-hn.exogeni.net:3626/foam/gapi/1

eg-renci=,https://rci-hn.exogeni.net:11443/orca/xmlrpc
eg-of-renci=,https://rci-hn.exogeni.net:3626/foam/gapi/1

# ExoSM
eg-sm=,https://geni.renci.org:11443/orca/xmlrpc

# InstaGENI AMs, including OpenFlow InstaGENI AMs
ig-utah1=urn:publicid:IDN+utah.geniracks.net+authority+cm,https://boss.utah.geniracks.net:12369/protogeni/xmlrpc/am/1.0
ig-utah2=urn:publicid:IDN+utah.geniracks.net+authority+cm,https://boss.utah.geniracks.net:12369/protogeni/xmlrpc/am/2.0
ig-utah3=urn:publicid:IDN+utah.geniracks.net+authority+cm,https://boss.utah.geniracks.net:12369/protogeni/xmlrpc/am/3.0
ig-utah=urn:publicid:IDN+utah.geniracks.net+authority+cm,https://boss.utah.geniracks.net:12369/protogeni/xmlrpc/am/2.0
ig-of-utah=,https://foam.utah.geniracks.net:3626/foam/gapi/1

ig-gpo1=urn:publicid:IDN+instageni.gpolab.bbn.com+authority+cm,https://boss.instageni.gpolab.bbn.com:12369/protogeni/xmlrpc/am/1.0
ig-gpo2=urn:publicid:IDN+instageni.gpolab.bbn.com+authority+cm,https://boss.instageni.gpolab.bbn.com:12369/protogeni/xmlrpc/am/2.0
ig-gpo3=urn:publicid:IDN+instageni.gpolab.bbn.com+authority+cm,https://boss.instageni.gpolab.bbn.com:12369/protogeni/xmlrpc/am/3.0
ig-gpo=urn:publicid:IDN+instageni.gpolab.bbn.com+authority+cm,https://boss.instageni.gpolab.bbn.com:12369/protogeni/xmlrpc/am/2.0
ig-of-gpo=,https://foam.instageni.gpolab.bbn.com:3626/foam/gapi/1 
ig-bbn1=urn:publicid:IDN+instageni.gpolab.bbn.com+authority+cm,https://boss.instageni.gpolab.bbn.com:12369/protogeni/xmlrpc/am/1.0
ig-bbn2=urn:publicid:IDN+instageni.gpolab.bbn.com+authority+cm,https://boss.instageni.gpolab.bbn.com:12369/protogeni/xmlrpc/am/2.0
ig-bbn3=urn:publicid:IDN+instageni.gpolab.bbn.com+authority+cm,https://boss.instageni.gpolab.bbn.com:12369/protogeni/xmlrpc/am/3.0
ig-bbn=urn:publicid:IDN+instageni.gpolab.bbn.com+authority+cm,https://boss.instageni.gpolab.bbn.com:12369/protogeni/xmlrpc/am/2.0
ig-of-bbn=,https://foam.instageni.gpolab.bbn.com:3626/foam/gapi/1 

ig-ky1=urn:publicid:IDN+lan.sdn.uky.edu+authority+cm,https://boss.lan.sdn.uky.edu:12369/protogeni/xmlrpc/am/1.0
ig-ky2=urn:publicid:IDN+lan.sdn.uky.edu+authority+cm,https://boss.lan.sdn.uky.edu:12369/protogeni/xmlrpc/am/2.0
ig-ky3=urn:publicid:IDN+lan.sdn.uky.edu+authority+cm,https://boss.lan.sdn.uky.edu:12369/protogeni/xmlrpc/am/3.0
ig-ky=urn:publicid:IDN+lan.sdn.uky.edu+authority+cm,https://boss.lan.sdn.uky.edu:12369/protogeni/xmlrpc/am/2.0
ig-of-ky=,https://foam.lan.sdn.uky.edu:3626/foam/gapi/1
ig-uky1=urn:publicid:IDN+lan.sdn.uky.edu+authority+cm,https://boss.lan.sdn.uky.edu:12369/protogeni/xmlrpc/am/1.0
ig-uky2=urn:publicid:IDN+lan.sdn.uky.edu+authority+cm,https://boss.lan.sdn.uky.edu:12369/protogeni/xmlrpc/am/2.0
ig-uky3=urn:publicid:IDN+lan.sdn.uky.edu+authority+cm,https://boss.lan.sdn.uky.edu:12369/protogeni/xmlrpc/am/3.0
ig-uky=urn:publicid:IDN+lan.sdn.uky.edu+authority+cm,https://boss.lan.sdn.uky.edu:12369/protogeni/xmlrpc/am/2.0
ig-of-uky=,https://foam.lan.sdn.uky.edu:3626/foam/gapi/1

""" % omni_config_dict

    return omni_config_file 

def configLogging(opts) :
    global logger
    level = logging.INFO
    if opts.verbose :
        level = logging.DEBUG

    logging.basicConfig(level=level)
    logger = logging.getLogger("omniconfig")
    
def main():
    global logger
    # do initial setup & process the user's call
    argv = sys.argv[1:]
    (opts, args) = parseArgs(argv)
    configLogging(opts)
    logger.debug("Running %s with options %s" %(sys.argv[0], opts))
    initialize(opts)
    logger.debug("Initialize Running %s with options %s" %(sys.argv[0], opts))
    pub_key_file_list = configureSSHKeys(opts)
    createConfigFile(opts,pub_key_file_list)

if __name__ == "__main__":
    sys.exit(main())
