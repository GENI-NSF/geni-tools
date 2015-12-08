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

""" The omni-configure.py script.
    This script is meant to help new users setup their omni config in 
    a standard way. Although many of the parameters can be customized using
    command line options, the user should be able to run the script
    with the default configuration and configure Omni. This script should be
    used by new user that want a default configuration of Omni. If advanced
    configuration is needed (multiple users, etc) this should still be done
    manually by editing the omni configuration file. 
"""
from base64 import b64encode
import datetime
import glob
import string, re
import sys, os, platform, shutil 
import zipfile
from subprocess import Popen, PIPE
import ConfigParser
import optparse
import logging
from gcf.sfa.trust.certificate import Certificate, Keypair
from gcf.gcf_version import GCF_VERSION as OMNI_VERSION
import M2Crypto
import tempfile

logger = None

SCRATCH_DIR = tempfile.mkdtemp('-omni_bundle')
DEFAULT_PRIVATE_CERT_KEY = {
                            'pg' : "~/.ssh/geni_cert_key_pg",
                            # 'pl' : "~/.ssh/geni_cert_key_pl",
                            'portal' : "~/.ssl/geni_ssl_portal.key"
                           }

DEFAULT_PRIVATE_KEY = {
                        'pg' : "geni_key_pg",
                        # 'pl' : "geni_key_pl",
                        'portal' : "geni_key_portal"
                      }

DEFAULT_CERT = {
                 'pg' : "~/.ssl/geni_cert_pg.pem",
                 # 'pl' : "~/.ssl/geni_cert_pl.gid",
                 'portal' : "~/.ssl/geni_cert_portal.pem"
               }

DEFAULT_OMNI_CONFIG = "~/.gcf/omni_config"

writtenfiles = []

def wrotefile(desc, nameoffile, oktodelete=False):
    """
    Track the file written by omni_configure.
    """
    #print "XX %s, %s XX" % (desc,nameoffile, oktodelete)
    writtenfiles.append((desc,nameoffile,oktodelete))

def getYNAns( question, defaultY=True):
    valid_ans=['','y', 'n']
    if defaultY:
        defVal = "[Y,n]"
    else:
        defVal = "[y,N]"
    answer = raw_input("%s %s?" % (question,defVal)).lower()
    while answer not in valid_ans:
        answer = raw_input("Your input has to be 'y' or <ENTER> for yes, 'n' for no:").lower()
    if defaultY:
        if answer == 'n':
            return False
        else:
            return True
    else:
        if answer == 'y':
            return True
        else:
            return False


def copyPrivateKeyFile(src_file, dst_file, msg="Private key", oktodelete=False, replaceAll=False):
    """ This function creates a copy of a private key file
        from 'src_file' to 'dst_file'. The src_file might be in .pem format
        so it is not a simple file copy, but we parse the file to only get
        the private key and write it to the destination file
    """

    if os.path.exists(dst_file):
        # # Load current and existing keys to see if they are the same
        # logger.info("Loading SSH key from %s", src_file)
        # k = loadKeyFromFile(src_file)
        # if k:
        #    logger.info("File %s already exists. Loading SSH key from %s", dst_file, dst_file)
        #    k_exist = loadKeyFromFile(dst_file)
        # if not k or not k_exist or not k_exist.is_same(k) :
        dst_file = getFileName(dst_file, replaceAll=replaceAll)
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
    logger.info("%s stored at: \n\t%s", msg, dst_file)
    wrotefile(msg,dst_file,oktodelete)
    # Change the permission to something appropriate for keys
    logger.debug("Changing permission on private key to 600")
    os.chmod(dst_file, 0o600)
    os.chmod(src_file, 0o600)
    return dst_file
def generatePublicKey(private_key_file):
    """ This function generates a public key based on the
        the private key in the 'private_key_file'
        The function returns the name of the public key file
        or None if the creation failed
    """
    logger.debug("Create public key based on private key.")
    succ = False
    for i in range(0,3) :
        try:
            private_key = M2Crypto.RSA.load_key( private_key_file )
        except:
            logger.warning("Error creating public key, passphrase might be wrong.")
            continue
        succ = True
        break
    # If the key was not loaded properly return None
    if not succ:
        logger.warning("Unable to create public key.")
        return None
    public_key_file = private_key_file + '.pub'

    # generate a public key based on the passed in private key
    public_key = M2Crypto.RSA.new_pub_key( private_key.pub() )
    # Output key in format:
    # ssh-rsa AAAAB3NzaC1yc2EAAAADAQAB <snip>
    # The following is base64 encoding of three pairs of (len, string) where len is the length of the string:
    #  * the string "rsa" (so this is "\x00\x00\x00\x07ssh-rsa")
    #  * public_key.pub()[0] aka 'e' the "RSA public exponent"
    #  * public_key.pub()[1] aka 'n' the "RSA composite of primes"
    # .pub() generates the tuple (e,n) in the appropriate format.  See:
    #    http://nullege.com/codes/search/M2Crypto.RSA.new_pub_key
    # The following line of code is from: http://stackoverflow.com/a/3939477/1804086
    key_output = b64encode('\x00\x00\x00\x07ssh-rsa%s%s' % (public_key.pub()[0], public_key.pub()[1]))
    try :
        f = open(public_key_file,'w')
    except :
        logger.warning("Error opening file %s for writing. Make sure that you have the right permissions." % public_key_file)
        return None
    f.write("ssh-rsa %s\n" % key_output)
    f.close()
    fdesc = "Public SSH key from your SSL cert"
    logger.info("%s stored at: \n\t%s", fdesc, public_key_file)
    wrotefile(fdesc,public_key_file,True)
    return public_key_file
def getFileName(filename, replaceAll=False):
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
        question = "\nFile " + filename + " exists, do you want to replace it "
        if not replaceAll and not getYNAns(question):
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
    if pkey_match == []:
        # It appears that now (updated openssl on nye after ubuntu upgrade?) that the key delimiter is different
        # This version supports PKCS#8, where earlier is PKCS#1.
        # Openssl v1.0.0 changed the default private key format from #1 to #8
        pkey_match = re.findall("^-+BEGIN PRIVATE KEY-+$.*?^-+END PRIVATE KEY-+$", text, re.MULTILINE|re.S)

    return pkey_match

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

class OmniConfigure( object ):
    DO_NOT_DELETE = ['~/.ssh/id_rsa','~/.ssh/id_rsa.pub']
    DO_NOT_DELETE = [os.path.normcase(os.path.expanduser(tmp)) for tmp in DO_NOT_DELETE]

    if platform.system().lower().find('windows') != -1 and  platform.release().lower().find('xp') != -1:
        DEFAULT_DOWNLOADS_FLDR = "~/My Documents/Downloads"
    else:
        DEFAULT_DOWNLOADS_FLDR = "~/Downloads"
    # match "omni (1).bundle" as well as "omni(1).bundle"
    DEFAULT_DOWNLOADS_NUM = "*(*)"
    DEFAULT_DOWNLOADS = [ DEFAULT_DOWNLOADS_FLDR+"/omni.bundle", DEFAULT_DOWNLOADS_FLDR+"/omni-bundle.zip" ]
    DEFAULT_DOWNLOADS_SEARCH1 = [ DEFAULT_DOWNLOADS_FLDR+"/omni.bundle",
                                 DEFAULT_DOWNLOADS_FLDR+"/omni"+DEFAULT_DOWNLOADS_NUM+".bundle"]
    DEFAULT_DOWNLOADS_SEARCH2 = [ DEFAULT_DOWNLOADS_FLDR+"/omni-bundle.zip",
                                 DEFAULT_DOWNLOADS_FLDR+"/omni-bundle"+DEFAULT_DOWNLOADS_NUM+".zip" ]
    DEFAULT_DOWNLOADS_SEARCH1 = [os.path.normcase(os.path.expanduser(tmp)) for tmp in DEFAULT_DOWNLOADS_SEARCH1]
    DEFAULT_DOWNLOADS_SEARCH2 = [os.path.normcase(os.path.expanduser(tmp)) for tmp in DEFAULT_DOWNLOADS_SEARCH2]

    def __init__(self):
        self.framework = None
        self._opts = None
        self._args = None
        self._pub_key_file_list = None

        global logger
        # do initial setup & process the user's call
        self.parseArgs()
        self.configLogging()
        logger.debug("Running %s with options %s" %(sys.argv[0], self._opts))
        self.initialize()
        logger.debug("Initialize Running %s with options %s" %(sys.argv[0], self._opts))

    def deletefile(self, nameoffile, file, ask=True, defTrue=True):
        if os.path.exists(file):
            if file.strip() in self.DO_NOT_DELETE:
                logger.info("\nSkipping %s file to avoid deleting irreplacable files." % file.strip())
                return
            if ask:
                question = "\nDelete %s file %s? " %(nameoffile, file)
                if not getYNAns(question, defaultY=defTrue):
                    return
            try:
                os.remove(file)
                logger.info("Deleted %s file %s" %(nameoffile, file))
            except:
                logger.info("Failed to delete %s file %s" %(nameoffile, file))
    def clean(self):
        global logger
        import gcf.oscript as omni

        # read omni_config from self._opts.configfile
        if os.path.exists(self._opts.configfile):
            # deconflict opts.framework (used differently in omni-configure and omni)
            framework = self._opts.framework
            self._opts.framework=None
            config = omni.load_config(self._opts, logger, filename=self._opts.configfile)
            #print config
            self._opts.framework = framework
        else:
            logger.warn("`omni_config` file does not exist at location specified: `%s`" % (self._opts.configfile))
            logger.warn("Try using the `-c` option to specify an alternative location.")
            return
        filestodelete = []
        if not config.has_key("omni_configure_files"):
            # if command line options are provided, use those instead of omni_config values
            if self._opts.cert != "":
                SSLcert = self._opts.cert
            else:
                SSLcert = config['selected_framework']['cert']

            if config['selected_framework']['type'].strip() == "chapi":
                filestodelete.append(('SSL certificate',SSLcert, str(True)))
            if self._opts.prcertkey != "":
                SSLprivatekey = self._opts.prcertkey
            else:
                SSLprivatekey = config['selected_framework']['key']

            # find all of the public keys
            # NOTE: -s option is not honor because it points to a directory
            # users = config['users']
            # SSHpublickeys = []
            # for user in users:
            #    keys = user['keys']
            #   keys = [key.strip() for key in keys.split(",")]
            #   SSHpublickeys += keys

            # ('SSL certificate private key',SSLprivatekey, False)

            #i = 1
            # for pub in SSHpublickeys:
            #    priv = pub.strip().rsplit('.',1)[0]
            #    filestodelete.append(('SSH public key  %s' % i, pub, True))
            #    filestodelete.append(('SSH private key %s' % i, priv, False))
            #    i += 1
        else:
            filestodelete = config["omni_configure_files"]
            # Fix this
            filestodelete = [(desc,name,oktodelete) for desc, name, oktodelete in filestodelete if oktodelete=="True"]

        # if --clean-all, then also look for files of form omni-bundle.zip and omni.bundle
        if self._opts.clean_all:
            if len(self._opts.portal_bundle_list) > 1:
                allfiles = []
                # search through the DEFAULT_DOWNLOADS files and ...
                # also search through the wildcarded DEFAULT_DOWNLOADS_SEARCH
                for search in self.DEFAULT_DOWNLOADS_SEARCH1 + self.DEFAULT_DOWNLOADS_SEARCH2:
                    search = os.path.abspath(os.path.expanduser(search))
                    allfiles += glob.glob(search)
            else:
                # Honor -z provided on command line
                allfiles = self._opts.portal_bundle_list
            for fvar in allfiles:
                filestodelete.append(('Omni Bundle', fvar, True))

        # delete omni_config last in case you CTRL-C or something goes wrong
        # then you can try again later
        filestodelete.append( ('omni_config',self._opts.configfile, True) )

        # only attempt to delete files that exist
        filestodelete = [(name, loc, defVal) for (name, loc, defVal) in filestodelete if os.path.exists(loc)]

        if self._opts.clean_all:
            logger.info("\nRunning in 'clean-all' mode.  \n")
        else:
            logger.info("\nRunning in 'clean' mode.  \n")

        numfiles = 0
        for fname, floc, defVal in filestodelete:
            if os.path.exists(floc):
                numfiles += 1

        logger.info("This will delete all of the files generated when omni-configure created the omni_config:\n\t'%s'\n" % self._opts.configfile)
        if self._opts.clean_all:
            logger.info("In addition, this will delete all of the input files to omni-configure (i.e. any omni bundles)\n")
        if numfiles == 0:
            logger.info("There are NO files to delete. Exiting.\n")
            return
        #question = "For each of the following files...\n   " + "\n   ".join(["%s: %s"%(nameoffile.ljust(28), file) for nameoffile, file, defVal in filestodelete]) + "\nAsk before deleting? ('n' will delete all without asking)"
        question = "The following files will be deleted...\n   " + "\n   ".join(["%s: %s"%(nameoffile.ljust(28), file) for nameoffile, file, defVal in filestodelete]) + "\n"
        #ask = getYNAns(question)
        ask = True
        logger.info(question)
        for name, file, defTrue in filestodelete:
            self.deletefile(name, file, ask, defTrue)

    def configLogging(self) :
        global logger
        level = logging.INFO
        if self._opts.verbose :
            level = logging.DEBUG

        FORMAT = "%(message)s"
        logging.basicConfig(level=level, format=FORMAT)
        logger = logging.getLogger("omniconfig")


    def createConfigFile(self):
        """ This function creates the omni_config file.
            It will rewrite any existing omni_config file
            and makes a backup of the omni_config file
            of the form omni_config_<i>
        """
        global logger
        opts = self._opts
        public_key_list = self._pub_key_file_list

        cert = Certificate(filename=opts.cert)

        omni_config_str = self.framework.getConfig(opts, public_key_list, cert)

        # Write the config to a file
        omni_bak_file = opts.configfile
        omni_bak_file = getFileName(omni_bak_file, replaceAll=opts.replace_all)
        if omni_bak_file != opts.configfile:
            question = "\n'" + opts.configfile + "' will be backed up at '" + \
                       omni_bak_file + "' and replaced with the new " + \
                       "configuration file. Continue"
            if not getYNAns(question):
                sys.exit("\nExiting! To create a configuration file other than " +\
                         opts.configfile + " use a different filename by using " +\
                         "the '-c' option")

            logger.info("Your old omni configuration file has been backed up at %s" % omni_bak_file)
            shutil.copyfile(opts.configfile, omni_bak_file)

        try:
            f = open(opts.configfile, 'w')
        except:
            logger.warning("Error opening file %s for writing. Make sure that you have the right permissions." % opts.configfile)
            sys.exit(-1)

        print >>f, omni_config_str
        f.close()
        logger.info("Wrote omni configuration file at: \n\t%s\n", opts.configfile)
        wrotefile("omni_config",opts.configfile,True)

    def configureSSHKeys(self):
        global logger
        opts = self._opts
        pubkey_list = []
        # Use the default place for the geni private key
        private_key_file = os.path.join(opts.sshdir,
                               DEFAULT_PRIVATE_KEY[opts.framework])
        pkey=opts.prcertkey

        if not cmp(opts.framework, 'portal') :
          omnizip = zipfile.ZipFile(opts.portal_bundle)
          # For the portal case we have to use a different default name
          # for the key generated by the ssl cert
          private_key_file = os.path.expanduser(os.path.join(
                                       opts.sshdir, "geni_cert_portal_key"))
          # If there are no keys in the bundle create a pair
          # the same was as for a PG framework
          if not self.framework.bundle_has_keys(omnizip) :
            logger.info("Bundle does not have keys, use as Private SSH key the "+
                        "key of the cert "+opts.cert)
          else :
          # if there are keys, then extract them in the right place
          # and return the list of pubkey filenames for use in the
          # omni_config
            pubkey_list = self.framework.bundle_extract_keys(omnizip, opts)
            logger.info("Script will create an extra public key file, based "+
                        "on the private key of the SSL cert:\n\t%s " % opts.cert)
            #return pubkey_list

        #logger.info("CREATING SSH KEYPAIR")

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

        fdesc = "Private SSH key from your SSL cert"
        private_key_file = copyPrivateKeyFile(pkey, private_key_file, msg=fdesc, oktodelete=True, replaceAll=opts.replace_all)
        public_key_file = generatePublicKey(private_key_file)
        if not public_key_file:
            #we failed at generating a public key, remove the private key and exit
            os.remove(private_key_file)
            sys.exit(-1)

        # Commented the modification of SSH config file out, since
        # what it does is not very useful and there is no flag to turn
        # this off
        #modifySSHConfigFile(private_key_file)

        pubkey_list.append(public_key_file)
        self._pub_key_file_list = pubkey_list
        return pubkey_list

    def initialize(self):
        global logger
        opts = self._opts

        #Check if directory for config file exists
        # Expand the configfile to a full path
        opts.configfile= os.path.expanduser(opts.configfile)
        opts.configfile= os.path.abspath(opts.configfile)
        logger.info("Creating omni_config: %s", opts.configfile)
        configdir = os.path.dirname(opts.configfile)

        if not opts.clean and not os.path.exists(configdir):
          # If the directory does not exist but it is the
          # default directory, create it, if not print an error
          if not cmp(os.path.normcase(os.path.expanduser('~/.gcf')), configdir):
            logger.info("Creating directory: %s", configdir)
            os.makedirs(configdir)
          else:
            sys.exit('Directory '+ configdir + ' does not exist!')

        # If the value is the default add the appropriate file extention
        # based on the framework

        if not opts.clean:
            if opts.cert == "" :
                opts.cert = DEFAULT_CERT[opts.framework]
                logger.debug("Cert is the default. Certfile is %s", opts.cert)
        if opts.cert != "":
            # Expand the cert file to a full path
            opts.cert= os.path.expanduser(opts.cert)
            opts.cert= os.path.abspath(opts.cert)

        # Expand the ssh directory to a full path
        opts.sshdir = os.path.expanduser(opts.sshdir)
        opts.sshdir = os.path.abspath(opts.sshdir)
        # Validate that the sshdir does not conflict with the tmp
        # folders used for the portal
        if opts.framework is 'portal':
          if opts.sshdir.startswith(SCRATCH_DIR) :
                sys.exit("\n\nExit!\nYou can't use as your ssh directory "+\
                         opts.sshdir + ". It is used internally by the script, rerun "+\
                         "and choose a directory is not under '"+\
                         SCRATCH_DIR + "' to store your "+\
                         "ssh keys." )

        # Expand the portal bundle file to a full path
        opts.portal_bundle_list = [os.path.expanduser(bundle) for bundle in opts.portal_bundle_list]
        opts.portal_bundle_list = [os.path.abspath(bundle) for bundle in opts.portal_bundle_list]

        #validate we have all the information we need per framework
        if not opts.clean:
            if self.framework.type == "portal":
                searchPattern1 = self.DEFAULT_DOWNLOADS_SEARCH1
                searchPattern2 = self.DEFAULT_DOWNLOADS_SEARCH2
                defaultDownloads = self.DEFAULT_DOWNLOADS
                # print searchPattern1, searchPattern2
            else:
                searchPattern1 = searchPattern2 = defaultDownloads = None
            self.framework.validate(opts, searchPattern1, searchPattern2, defaultDownloads)

        # Expand the prcertkey file to a full path
        # In order to properly set the private key for the cert
        #   we need to parse the cert file and look to see if there
        #   is one included, but we can't do this here, so this
        #   happens in each of the validate calls
        if opts.prcertkey != "":
            opts.prcertkey = os.path.expanduser(opts.prcertkey)
            opts.prcertkey = os.path.abspath(opts.prcertkey)

    def parseArgs(self, argv=sys.argv[1:], options=None):
        """Construct an Options Parser for parsing omni-configure command line
        arguments, and parse them.
        """

        usage = "\n Script for automatically configuring Omni."

        parser = optparse.OptionParser(usage=usage)
        parser.add_option("-c", "--configfile", default=str(DEFAULT_OMNI_CONFIG),
                          help="Config file location [DEFAULT: %default]",
                          metavar="FILE")
        parser.add_option("-p", "--cert", default="",
                          help="File location of user SSL certificate. Default is "+\
                          "based on the selected framework (see -f option) [DEFAULT: %s]"
                          % str(DEFAULT_CERT), metavar="FILE")
        parser.add_option("-k", "--prcertkey", default="",
                          help="File location of private key for the user SSL "+\
                          "certificate. Default is based on the selected framework"+\
                          " (see -f option) [DEFAULT: %s]" % str(DEFAULT_PRIVATE_CERT_KEY),
                          metavar="FILE")
        parser.add_option("-s", "--sshdir", default="~/.ssh/",
                          help="Directory for the location of SSH keys for "+ \
                          "logging in to compute resources, [DEFAULT: %default]" ,
                          metavar="FILE")
        parser.add_option("-z", "--portal-bundle", default=[],
                          action="append", dest="portal_bundle_list",
                          help="Bundle downloaded from the portal for "+ \
                          "configuring Omni [DEFAULT: %s]"%self.DEFAULT_DOWNLOADS, metavar="FILE")
        parser.add_option("-f", "--framework", default="portal", type='choice',
                          choices=['pg', 'portal'],
                          help="Control framework that you have an account " + \
                          "with [options: [pg, portal], DEFAULT: %default]")
        parser.add_option("--pick-project", dest="pick_project",
                          action="store_true",
                          default=False, help="Lets you choose which project to "+ \
                          "use as default from the projects in the bundle "+ \
                          "downloaded from the portal")
        parser.add_option("--not-use-chapi", dest="use_chapi",
                          action="store_false",
                          default=True, help="If available, do not configure the "+ \
                          "omni_config to use the common Clearinghouse API (CH API).")
        parser.add_option("-v", "--verbose", default=False, action="store_true",
                          help="Turn on verbose command summary for omni-configure script")
        parser.add_option("--clean", default=False, action="store_true",
                          help="Clean up files generated by this script. (Does not honor -s/-f options.)")
        parser.add_option("--clean-all", default=False, action="store_true",
                          help="In addition to files deleted by --clean, also remove input files (i.e. omni bundle files).")
        parser.add_option("--replace-all", default=False, action="store_true",
                          help="Answer yes to all questions about replacing a file.")
        if argv is None:
            parser.print_help()
            return

        (opts, args) = parser.parse_args(argv, options)
        if opts.clean_all:
            opts.clean = True
        opts.configfile = os.path.normcase(os.path.expanduser(opts.configfile))
        opts.cert = os.path.normcase(os.path.expanduser(opts.cert))
        opts.prcertkey = os.path.normcase(os.path.expanduser(opts.prcertkey))
        opts.sshdir = os.path.normcase(os.path.expanduser(opts.sshdir))

        # if --omni-bundle not supplied use the list of default values
        if opts.portal_bundle_list == []:
            opts.portal_bundle_list = self.DEFAULT_DOWNLOADS
        opts.portal_bundle_list = [os.path.normcase(os.path.expanduser(bundle)) for bundle in opts.portal_bundle_list]

        if not cmp(opts.framework,'pg'):
            self.framework = PGFramework()
        else :
          if not cmp(opts.framework, 'pl'):
            self.framework = PLFramework()
          else :
            if not cmp(opts.framework, 'portal'):
                self.framework = PortalFramework()

        self._opts = opts
        self._args = args
        return opts, args

class ConfigFramework_Base(object):
    type='base'
    def getConfig(self):
        raise NotImplemented, "getConfig not implemented in %s" % (self.__class__)
    def validate(self):
        raise NotImplemented, "validate not implemented in %s" % (self.__class__)
    def createConfigStr(self, opts, public_key_list, cert, cf_section) :

        (user, user_urn) = self.getUserInfo(cert)

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

#------RSpec nicknames
# When you call
#      omni.py createsliver myslice myrspec
# omni will try to read 'myrspec' by interpreting it in the following order:
# 1. a URL or a file on the local filesystem
# 2. a nickname specified in the omni_config
# 3. a file in a location (file or url) defined as:
#    <default_rspec_server>/<rspec_nickname>.<default_rspec_extension>

[rspec_nicknames]
# Format :
# Nickname= [location of RSpec file]
# myawesometopology = ~/.gcf/rspecs/myrspecfile.rspec
hellogeni = http://www.gpolab.bbn.com/experiment-support/HelloGENI/hellogeni.rspec

default_rspec_location = http://www.gpolab.bbn.com/experiment-support
default_rspec_extension = rspec

#------AM nicknames
# Put your custom aggregate nicknames here.
# To see all available nicknames try: omni.py nicknames
# Format :
# Nickname=URN, URL
# URN is optional
[aggregate_nicknames]
#boston=urn:publicid:IDN+instageni.gpolab.bbn.com+authority+cm,https://boss.instageni.gpolab.bbn.com:12369/protogeni/xmlrpc/am/2.0
""" % omni_config_dict

        omniconfigure_section = self.getOmniConfigureSection()

        return omni_config_file + omniconfigure_section


    def getUserInfo(self, cert) :

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

    def setPrivateCertKey(self, opts):
        ''' This function figures out if there is
            an appropriate ssl key to use for the cert
        '''
        #global logger
        #logger.info( "setPrivateCertKey" )
        # First check the certificate file. If there is a private
        # key included, then use that
        keyList = loadKeyTextFromFile(opts.cert)
        if len(keyList) > 0 :
           if opts.prcertkey != "" :
             #logger.warn("Private key present in the cert file %s. Your option of %s, has been overwritten" % (opts.cert, opts.prcertkey))
             logger.warn("Private key present in the cert file '%s'. Ignoring --prcertkey option '%s'." % (opts.cert, opts.prcertkey))

           opts.prcertkey = opts.cert
        # If the user wants to use the default name
        else :
          if opts.prcertkey == "" :
            opts.prcertkey = DEFAULT_PRIVATE_CERT_KEY[opts.framework]
            opts.prcertkey = os.path.expanduser(opts.prcertkey)
            opts.prcertkey = os.path.abspath(opts.prcertkey)

        logger.debug("Using as private key for the cert file: %s" %opts.prcertkey)
    def getOmniConfigureSection(self):
        currdate = datetime.datetime.utcnow()
        datestr = datetime.datetime.isoformat(currdate)
        filelist = [str(fdesc)+", "+str(fname)+", "+str(oktodelete) for fdesc, fname, oktodelete in writtenfiles]
        return """
#------ omni-configure
# Information about how this file was generated.
# Includes version, date, and other files created
#

[omni_configure]
# Omni Version
version=%s
# Date
date=%s
# Files Written
# Description of File, Location of File, Ok to Delete by --clean?
files=
%s
""" %(OMNI_VERSION, datestr,"\t"+"\n\t".join(filelist))

class PGFramework( ConfigFramework_Base ):
    type='pg'
    def validate(self, opts, *args):
        """ This function verifies that the we have everything we need
            to run if framework is 'pg'
        """
        # If framework is pgeni, check that the cert file is in the right place
        if not os.path.exists(opts.cert) or os.path.getsize(opts.cert) < 1:
                sys.exit("Geni certificate not in '"+opts.cert+"'. \nMake sure you \
    place the .pem file that you downloaded from the Web UI there,\nor \
    use the '-p' option to specify a custom location of the certificate.\n")

        logger.info("Using certfile %s", opts.cert)

        self.setPrivateCertKey(opts)

        if not os.path.exists(opts.prcertkey) or os.path.getsize(opts.prcertkey) < 1:
                sys.exit("Private key for the certificate not in '"+opts.prcertkey+"'. \n")

        logger.debug("Using private key for the cert file %s", opts.prcertkey)
    def getConfig(self, opts, public_key_list, cert) :

        (user, user_urn) = self.getUserInfo(cert)

        # UKY has to go first because emulab.net is a substring of uky.emulab.net
        if user_urn.find('uky.emulab.net') != -1:
            sa = 'https://www.uky.emulab.net:12369/protogeni/xmlrpc/sa'
        elif user_urn.find('emulab.net') != -1:
            sa = 'https://www.emulab.net:12369/protogeni/xmlrpc/sa'
        elif user_urn.find('pgeni.gpolab.bbn.com') != -1:
            sa = 'https://www.pgeni.gpolab.bbn.com:12369/protogeni/xmlrpc/sa'
        elif user_urn.find('loni.org') != -1 :
            sa = 'https://cron.loni.org:443/protogeni/xmlrpc/sa'
        elif user_urn.find('wall2.ilabt.iminds.be') != -1 :
            sa = 'https://www.wall2.ilabt.iminds.be:12369/protogeni/xmlrpc/sa'
        else:
            raise Exception("Creation of omni_config for users at %s is not supported. Please report this on the GENI Users mailing list: https://groups.google.com/forum/#!forum/geni-users" % user_urn.split('+')[-3])

        logger.debug("Framework is ProtoGENI, use as SA: %s", sa)

        cf_section = """
[%s]
type = pg
ch = https://www.emulab.net:12369/protogeni/xmlrpc/ch
sa = %s
cert = %s
key = %s
""" %(opts.framework, sa, opts.cert, opts.prcertkey)

        return self.createConfigStr(opts, public_key_list, cert, cf_section)

class PLFramework( ConfigFramework_Base ):
    type='pl'
    def validate(self, opts, *args):
        """ This function verifies that the we have everything we need
            to run if framework is 'pl'
        """

        # If framework is planetlab, check that the key are in the right place
        if not os.path.exists(opts.cert) or os.path.getsize(opts.cert) < 1:
                sys.exit("\nScript currently does not support automatic download of \
    PlanetLab cert.\nIf you have a copy place it at '"+opts.cert+"', \nor \
    use the '-p' option to specify a custom location of the certificate.\n")

        self.setPrivateCertKey(opts)

        if not os.path.exists(opts.prcertkey) or \
           os.path.getsize(opts.prcertkey) < 1:
          sys.exit("\nPlanetLab private key not in '"+opts.prcertkey+"'. \n\
          Make sure \
    you place the private key registered with PlanetLab there or use\n\
    the '-k' option to specify a custom location for the key.\n")

        logger.info("Using certfile %s", opts.cert)
        logger.info("Using PlanteLab private key file %s", opts.prcertkey)

    def getConfig(self, opts, public_key_list, cert) :
        # We need to get the issuer and the subject for SFA frameworks
        # issuer -> authority
        # subject -> user
        issuer = cert.get_issuer()
        logger.debug("Issuer of the cert is: %s", issuer)
        subject = cert.get_subject()
        logger.debug("Subject(user) of the cert is: %s", subject)

        (user, user_urn) = self.getUserInfo(cert)

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

        return self.createConfigStr(opts, public_key_list, cert, cf_section)

class PortalFramework( ConfigFramework_Base ):
    type='portal'
    def validate_portal_bundle_location(self, portal_bundle):
        """
        Is the file at `portal_bundle` a valid omni bundle?
        """
        # If framework is portal, check that the bundle file is in the right place
        if not os.path.exists(portal_bundle) or \
               os.path.getsize(portal_bundle) < 1 :
            return False, "\nPortal bundle not in '"+str(portal_bundle)+"'.\n\
    Make sure you place the bundle downloaded from the portal there,\nor \
    use the '-z' option to specify a custom location.\n"
        if not zipfile.is_zipfile(portal_bundle) :
            return False, "\nFile '"+portal_bundle+"' not a valid zip file.\n"+\
                     "Exit!"
        return True, portal_bundle
    def validate_possible_bundle_locations(self, searchlist):
        """
        Go through each file in `searchlist` looking for the first file which is
        a valid omni bundle zip file.
        """
        retVal=False
        retStr="No files searched"
        for bundle in searchlist:
            retVal, retStr = self.validate_portal_bundle_location( bundle )
            if retVal:
                break
        return retVal, retStr
    def order_possible_bundle_locations(self, searchPattern):
        """
        Return a list of all files which match `searchPattern`
        ordered by most recent first.
        """
        searchlist = []
        searchPattern = [os.path.abspath(os.path.expanduser(pattern)) for pattern in searchPattern]
        # loop over all search strings
        for searchitem in searchPattern:
            # loop over all files which match this search string
            for fname in glob.glob(searchitem):
                modified = os.path.getmtime(fname)
                searchlist.append( (modified, fname) )
        searchlist.sort()
        searchlist.reverse()
        # for item in searchlist:
        #    print item
        searchlist = [fname for modified, fname in searchlist]
        return searchlist

    def validate(self, opts, searchPattern1, searchPattern2, defaultLocations, *args):
        """ This function verifies that the we have everything we need
            to run if framework is 'portal'
        """
        if len(opts.portal_bundle_list) == 1:
            searchlist = opts.portal_bundle_list
            retVal, retStr = self.validate_possible_bundle_locations(searchlist)
        else:
            searchlist1 = self.order_possible_bundle_locations(searchPattern1)
            retVal, retStr = self.validate_possible_bundle_locations(searchlist1)
            if not retVal:
                searchlist2 = self.order_possible_bundle_locations(searchPattern2)
                retVal, retStr = self.validate_possible_bundle_locations(searchlist2)
        if retVal:
            opts.portal_bundle = retStr
        else:
            bundle="\n\t".join(defaultLocations)
            sys.exit("\nPortal bundle not in a default location:\n\t"+str(bundle)+"\n\n\
Make sure you place the bundle downloaded from the portal \nin one of the above locations, or \
use the '-z' option to\nspecify a custom location.\n")
        self.validate_bundle(opts.portal_bundle)
        logger.info("Using portal bundle: %s", opts.portal_bundle)

        # In the case of the portal there is no cert
        # file yet, extract it
        opts.cert = getFileName(opts.cert, replaceAll=opts.replace_all)
        self.extract_cert_from_bundle(opts.portal_bundle, opts.cert)
        fdesc = "SSL certificate"
        logger.info("%s stored at: \n\t%s", fdesc, opts.cert)
        wrotefile(fdesc, opts.cert,True) # in the portal case the cert is ok to delete
        self.setPrivateCertKey(opts)

        # If the private key for the cert is not in the cert, check
        # that the file actually exist
        if cmp(opts.prcertkey, opts.cert) :
          if not os.path.exists(opts.prcertkey) or \
               os.path.getsize(opts.prcertkey) < 1 :
            os.remove(opts.cert)
            sys.exit("\nPrivate SSL key not in '"+opts.prcertkey+"'.\n\
    Either place your key in the above file or use\n \
    the '-k' option to specify a custom location for the key.\n")

    def bundle_extract_keys(self, omnizip, opts) :
       """ function that will extract any key files in zip bundle
           in the approprate places
             * private key will go to 'opts.sshdir', the name will be
               the same as in the bundle
             * all public keys except from the one corresponding to the
               included private key will go under 'opts.sshdir'
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
            omnizip.extract(x, SCRATCH_DIR)
            prkeyfname = os.path.join(opts.sshdir, DEFAULT_PRIVATE_KEY[opts.framework])
            fdesc = "Private SSH key"
            prkeyfname = copyPrivateKeyFile(os.path.join(SCRATCH_DIR, x), prkeyfname, msg=fdesc, oktodelete=False,replaceAll=opts.replace_all)

            # Place the public key in the right place
            omnizip.extract(xpub, SCRATCH_DIR)
            pubname = prkeyfname +'.pub'

            # Try and see if this public key name exist
            tmp = getFileName(pubname, replaceAll=opts.replace_all)
            # if the file already exists, exit since we can't have a pub key
            # that does not match the private key
            if cmp(tmp, pubname) :
              # Remove the cert, the private key, and the
              # /tmp/tmp<random>-omni_bundle/ssh folder before
              # we exit
              os.remove(opts.cert)
              os.remove(prkeyfname)
              shutil.rmtree(os.path.join(SCRATCH_DIR, 'ssh'))
              sys.exit("There is already a key named "+pubname+". Remove it first "+
                       "and then rerun the script")

            shutil.move(os.path.join(SCRATCH_DIR, xpub), pubname)
            fdesc="Public SSH key"
            logger.info("%s stored at:\n\t%s",fdesc, pubname)
            wrotefile(fdesc,pubname,False)
            pubkey_list.append(pubname)
            pubkey_of_priv_inbundle = xpub
            logger.debug("Place public key %s at %s" \
                         %(pubkey_of_priv_inbundle, pubname))

       # Make a second pass to extract all public keys other than the one that
       # corresponds to the private key
       for x in filelist :
          if x.startswith('ssh/public') and \
             not x.startswith(pubkey_of_priv_inbundle) :

            omnizip.extract(x, SCRATCH_DIR)
            xname = os.path.basename(x)
            xbase = os.path.splitext(xname)[0]
            xfullpath = os.path.join(opts.sshdir, xbase + '.pub')
            xfullpath = os.path.abspath(getFileName(xfullpath, replaceAll=opts.replace_all))

            # Check if the file ~/.ssh exists and create it if not
            dstdir = os.path.dirname(xfullpath)
            if os.path.expanduser(dstdir) :
              if not os.path.exists(dstdir) :
                os.makedirs(dstdir)

            logger.debug("Copy public key %s to %s" %(x, xfullpath))
            shutil.move(os.path.join(SCRATCH_DIR, x), xfullpath)
            fdesc = "Public SSH key"
            logger.info("%s stored at:\n\t%s", fdesc, xfullpath)
            wrotefile(fdesc,xfullpath,False)
            pubkey_list.append(xfullpath)

       shutil.rmtree(os.path.join(SCRATCH_DIR, 'ssh'))

       return pubkey_list

    def bundle_has_keys(self, omnizip) :
       """ function that checks if there are any keys
           in the ZipFile omnizip (downloaded from the portal)
       """
       haskeys = False
       filelist = omnizip.namelist()
       for x in filelist :
          if x.startswith('ssh') :
            haskeys = True
       return haskeys

    def bundle_has_private_key(self, omnizip) :
       """ function that checks if there are any keys
           in the ZipFile omnizip (downloaded from the portal)
       """
       hasprkey = False
       filelist = omnizip.namelist()
       for x in filelist :
          if x.startswith('ssh/private') :
            hasprkey = True
       return hasprkey

    def validate_bundle(self, filename) :
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
            pub_key_file_list = self.get_pub_keys_from_bundle(omnizip)
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


    def get_pub_keys_from_bundle(self, omnizip) :
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

    def extract_cert_from_bundle(self, filename, dest) :
        """ This functions extracts a cert named geni_cert.pem
            out of a bundle downladed from the portal named <filename>
            and saves it at <dest>
        """
        omnizip = zipfile.ZipFile(filename)
        # extract() can only take a directory as argument
        # extract it at /tmp/tmp<random>-omni_bundle and then move it to the file
        # we want
        omnizip.extract('geni_cert.pem', SCRATCH_DIR)
        omnizip.close()
        # If the destination does not exist create it
        destdir = os.path.dirname(dest)
        if os.path.expanduser(destdir) :
          if not os.path.exists(destdir) :
            os.makedirs(destdir)
        shutil.move(SCRATCH_DIR + '/geni_cert.pem', dest)
    def loadProjects(self, filename) :
        f = open(filename)
        content = f.read()
        f.close()
        proj_re = '^#*\s*default_project\s*=\s*(.*)$'
        return re.findall(proj_re, content, re.MULTILINE)
    def getPortalOmniSection(self, opts, config, user, projects) :
        omni_section = """
[omni]
default_cf=%s
users=%s
default_project=%s

""" %(opts.framework, user, config['omni']['default_project'])

        # FIXME: At some point, remove this since default
        # is True as of v2.7
        if config['selected_framework']['type'] == 'chapi':
            omni_section += """
# Over-ride the commandline setting of --useSliceMembers to force it True
useslicemembers = %s
""" %(True)

        for p in projects :
          if p != config['omni']['default_project'] :
            omni_section +="#default_project=%s\n" % p

        return omni_section

    def getPortalSFSection(self, opts, config) :
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


    def getPortalCHAPISFSection(self, opts, config) :

        return """
[portal]
# For use with the Uniform Federation API
type = chapi
# Authority part of the control framework's URN
authority = %s
# Where the CH API server's Clearinghouse service is listening.
# This will be used to find the MA and SA
ch = %s
# Optionally you may explicitly specify where the MA and SA are
#  running, in which case the Clearinghouse service is not used
#  to find them
ma = %s
sa = %s
cert = %s
key = %s
# For debugging
verbose=false

""" %(
          config['selected_framework']['authority'],
          config['selected_framework']['ch'],
          config['selected_framework']['ma'],
          config['selected_framework']['sa'],
          opts.cert, opts.prcertkey)

    def getPortalUserSection(self, opts, user, user_urn, public_key_list) :
        return """
[%s]
urn=%s
keys=%s
""" %(user, user_urn, ','.join(public_key_list))


    def getRSpecNickSection(self, opts, config) :

        return """
#------RSpec nicknames
# When you call
#      omni.py createsliver myslice myrspec
# omni will try to read 'myrspec' by interpreting it in the following order:
# 1. a URL or a file on the local filesystem
# 2. a nickname specified in the omni_config
# 3. a file in a location (file or url) defined as:
#    <default_rspec_server>/<rspec_nickname>.<default_rspec_extension>

[rspec_nicknames]
# Format :
# Nickname= [location of RSpec file]
# myawesometopology = ~/.gcf/rspecs/myrspecfile.rspec
hellogeni = http://www.gpolab.bbn.com/experiment-support/HelloGENI/hellogeni.rspec

default_rspec_location = http://www.gpolab.bbn.com/experiment-support
default_rspec_extension = rspec
"""

    def getPortalAMNickSection(self, opts, config) :

        return """
#------AM nicknames
# Put your custom aggregate nicknames here.
# To see all available nicknames try: omni.py nicknames
# Format :
# Nickname=URN, URL
# URN is optional
[aggregate_nicknames]
# boston=urn:publicid:IDN+instageni.gpolab.bbn.com+authority+cm,https://boss.instageni.gpolab.bbn.com:12369/protogeni/xmlrpc/am/2.0

"""


    def getConfig(self, opts, public_key_list, cert) :
        # The bundle contains and omni_config
        # extract it and load it
        omnizip = zipfile.ZipFile(opts.portal_bundle)
        bundle_omni_configs = ['omni_config']
        if opts.use_chapi:
            # if want to use CH API, then look in 'omni_config_chapi' first
            bundle_omni_configs = ['omni_config_chapi'] + bundle_omni_configs
        for config_loc in bundle_omni_configs:
            try:
                omnizip.extract(config_loc, SCRATCH_DIR)
                config_path = os.path.join(SCRATCH_DIR, config_loc)
                config = loadConfigFile(config_path)
                break
            except:
                pass

        if not config and not config['selected_framework'].has_key('authority'):
          sys.exit("\nERROR: Your omni bundle is old, you must get a new version:\n"+
                      "\t 1. Download new omni-bundle.zip from the Portal\n"+
                      "\t 2. Rerun omni-configure.py"+
                      "\nExiting!")
        projects = self.loadProjects(config_path)
        os.remove(config_path)

        if len(projects) == 0 :
          logger.warn("\nWARNING: You are not a member of any projects! You will need to:\n"+
                      "\t 1. Join a project in the portal\n"+
                      "\t 2. Use the -r flag with omni.py to specify your project "+
                      "or \n\t    download a new bundle and rerun omni-configure.py")

          defproj = ""
        else :
          defproj = config['omni']['default_project']
          if len(projects) > 1 and opts.pick_project :
            defproj = self.selectProject(projects, defproj)

        # Replace default project with the selected one
        config['omni']['default_project'] = defproj

        (user, user_urn) = self.getUserInfo(cert)

        omni_section = self.getPortalOmniSection(opts, config, user, projects)
        user_section = self.getPortalUserSection(opts, user, user_urn, public_key_list)
        if config['selected_framework']['type'] == 'chapi':
            cf_section = self.getPortalCHAPISFSection(opts, config)
        else:
            cf_section = self.getPortalSFSection(opts, config)
        rspecnick_section = self.getRSpecNickSection(opts, config)
        amnick_section = self.getPortalAMNickSection(opts, config)
        omniconfigure_section = self.getOmniConfigureSection()

        return omni_section + user_section + cf_section + rspecnick_section + amnick_section + omniconfigure_section

    def selectProject(self, projects, defproj) :
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


def fixNicknames(config) :
    config['aggregate_nicknames'] = {}
    # ExoGENI AMs


def main():
    global logger
    oconfig = OmniConfigure()
    try:
        if oconfig._opts.clean:
            oconfig.clean()
        else:
            oconfig.configureSSHKeys()
            oconfig.createConfigFile()
            logger.info("="*80+"\n")
            logger.info("Omni is now configured!\n")
            cloc = ""
            if oconfig._opts.configfile != os.path.normcase(os.path.abspath(os.path.expanduser(DEFAULT_OMNI_CONFIG))):
                cloc = "-c %s " % oconfig._opts.configfile
            logger.info("To test your configuration, run: \n\tomni %s-a gpo-ig getversion \n"%cloc)
            shutil.rmtree(SCRATCH_DIR)
    except KeyboardInterrupt:
        print "\n\nGoodbye.\n"
        shutil.rmtree(SCRATCH_DIR)
        return

if __name__ == "__main__":
    sys.exit(main())
