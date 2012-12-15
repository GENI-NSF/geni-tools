#!/usr/bin/python

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
from subprocess import Popen, PIPE
import ConfigParser
import optparse
import logging
from sfa.trust.certificate import Certificate, Keypair

logger = None

def getYNAns(question):
    valid_ans=['','y', 'n']
    answer = raw_input("%s [Y,n]?" % question).lower()
    while answer not in valid_ans:
        answer = raw_input("Your input has to be 'y' or <ENTER> for yes, 'n' for no:").lower()
    if answer == 'n':
        return False
    return True


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
        k = loadKeyFromFile(src_file)
        if k:
            logger.info("File %s already exists. Loading existing key...", dst_file)
            k_exist = loadKeyFromFile(dst_file)
        if not k or not k_exist or not k_exist.is_same(k) : 
            dst_file = getFileName(dst_file)

    # We don't do a blind copy in case the src file is in .pem format but we
    # extract the key from the file
    f = open(src_file, 'r')
    text = f.read()
    f.close()
    pkey_match = re.search("^-+BEGIN RSA PRIVATE KEY-+$.*^-+END RSA PRIVATE KEY-+$", text, re.MULTILINE|re.S)

    if not pkey_match:
        logger.info("No private key in the file. Exit!")
        sys.exit()
    f = open(dst_file, 'w+')
    f.write(pkey_match.group(0))
    f.close()
    logger.info("Private key stored at: %s", dst_file)
    # Change the permission to something appropriate for keys
    logger.debug("Changing permission on private key to 600")
    os.chmod(dst_file, 0600)
    os.chmod(src_file, 0600)

def parseArgs(argv, options=None):
    """Construct an Options Parser for parsing omni-configure command line
    arguments, and parse them.
    """

    usage = "\n Script for automatically configuring Omni."

    parser = optparse.OptionParser(usage=usage)
    parser.add_option("-c", "--configfile", default="~/.gcf/omni_config",
                      help="Config file location [DEFAULT: %default]", metavar="FILE")
    parser.add_option("-p", "--cert", default="~/.ssl/geni_cert",
                      help="User certificate file location [DEFAULT: %default.pem]", metavar="FILE")
    parser.add_option("-k", "--plkey", default="~/.ssh/geni_pl_key",
                      help="PlanetLab private key file location [DEFAULT: %default]", metavar="FILE")
    parser.add_option("-e", "--prkey", default="~/.ssh/geni_key",
                      help="Private key for loggin to compute resources file location [DEFAULT: %default]", metavar="FILE")
    parser.add_option("-f", "--framework", default="pg", type='choice',
                      choices=['pg', 'pl'],
                      help="Control framework that you have an account with [options: [pg, pl], DEFAULT: %default]")
    parser.add_option("-v", "--verbose", default=False, action="store_true",
                      help="Turn on verbose command summary for omni-configure script")

    if argv is None:
        # prints to stderr
        parser.print_help()
        return

    (opts, args) = parser.parse_args(argv, options)
    print opts
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
    if not cmp(opts.cert, "~/.ssl/geni_cert") : 
        if not cmp(opts.framework,'pg'):
            opts.cert += ".pem"
        else : 
            if not cmp(opts.framework,'pl'):
                opts.cert += ".gid"
        logger.debug("Cert is the default add the appropriate extension. Certfile is %s", opts.cert)
            
    # Expand the cert file to a full path
    opts.cert= os.path.expanduser(opts.cert)
    opts.cert= os.path.abspath(opts.cert)
    logger.info("Using certfile %s", opts.cert)

    # Expand the plkey file to a full path
    opts.plkey = os.path.expanduser(opts.plkey)
    opts.plkey = os.path.abspath(opts.plkey)

    # Expand the private file to a full path
    opts.prkey = os.path.expanduser(opts.prkey)
    opts.prkey = os.path.abspath(opts.prkey)

    # If framework is pgeni, check that the cert file is in the right place
    if not cmp(opts.framework,'pg'):
        if not os.path.exists(opts.cert) or os.path.getsize(opts.cert) < 1:
            sys.exit("Geni certificate not in '"+opts.cert+"'. \nMake sure you \
place the .pem file that you downloaded from the Web UI there,\nor \
use the '-p' option to specify a custom location of the certificate.\n")

    # If framework is planetlab, check that the key are in the right place
    if not cmp(opts.framework,'pl'):
        if not os.path.exists(opts.cert) or os.path.getsize(opts.cert) < 1:
            sys.exit("\nScript currently does not support automatic download of \
PlanetLab cert.\nIf you have a copy place it at '"+opts.cert+"', \nor \
use the '-p' option to specify a custom location of the certificate.\n")
        if not os.path.exists(opts.plkey) or os.path.getsize(opts.cert) < 1:
            sys.exit("\nPlanetLab private key not in '"+opts.plkey+"'. \nMake sure \
you place the private key registered with PlanetLab there or use\n\
the '-k' option to specify a custom location for the key.\n")
    

def createSSHKeypair(opts):
    global logger

    logger.info("\n\n\tCREATING SSH KEYPAIR")

    if not cmp(opts.framework,'pg'):
      logger.debug("Framework is ProtoGENI use as Private SSH key the key in the cert: %s", opts.cert)
      pkey = opts.cert
    else :
      if not cmp(opts.framework,'pl'):
        logger.debug("Framework is PlanetLab use as Private SSH key the pl key: %s", opts.plkey)
        pkey = opts.plkey

    # Use the default place for the geni private key
    private_key_file = opts.prkey

    # Make sure that the .ssh directory exists, if it doesn't create it
    ssh_dir = os.path.expanduser('~/.ssh')
    if not os.path.exists(ssh_dir) :
        logger.info("Creating directory: %s", ssh_dir)
        os.makedirs(ssh_dir)

    copyPrivateKeyFile(pkey, private_key_file)

    public_key_file = generatePublicKey(private_key_file)
    if not public_key_file:
        #we failed at generating a public key, remove the private key and exit
        os.remove(private_key_file)
        sys.exit(-1)

    modifySSHConfigFile(private_key_file)
    
    return private_key_file, public_key_file

def createConfigFile(opts, public_key_file):
    """ This function creates the omni_config file. 
        It will rewrite any existing omni_config file
        and makes a backup of the omni_config file 
        of the form omni_config_<i> 
    """
    global logger

    cert = Certificate(filename=opts.cert)
    # We need to get the issuer and the subject for SFA frameworks
    # issuer -> authority
    # subject -> user
    issuer = cert.get_issuer()
    logger.debug("Issuer of the cert is: %s", issuer)
    subject = cert.get_subject()
    logger.debug("Subject(user) of the cert is: %s", subject)

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

    urn = user_urn_list[0].lstrip('URI:')
    logger.debug("User URN in the cert is: %s", urn)
    user = urn.split('+')[-1]
    logger.debug("User is: %s", user)

    if not cmp(opts.framework,'pg'):
        if urn.find('emulab.net') != -1 :
            sa = 'https://www.emulab.net:443/protogeni/xmlrpc/sa'
        else :
            if urn.find('pgeni.gpolab.bbn.com') != -1 :
                sa = 'https://www.pgeni.gpolab.bbn.com:443/protogeni/xmlrpc/sa'
            else : 
              if urn.find('loni.org') != -1 :
                sa = 'https://cron.loni.org:443/protogeni/xmlrpc/sa'
              else:
                raise Exception("Creation of omni_config for users at %s is not supported. Please contact omni-users@geni.net" % urn.split('+')[-2]) 
        logger.debug("Framework is ProtoGENI, use as SA: %s", sa)
        cf_section = """
[%s]
type = pg
ch = https://www.emulab.net:443/protogeni/xmlrpc/ch
sa = %s
cert = %s
key = %s
""" %(opts.framework, sa, opts.cert, opts.cert)

    else:
      if not cmp(opts.framework, 'pl'):
        cf_section = """
[%s]
type = sfa
authority=%s
user=%s
cert=%s
key=%s
registry=http://www.planet-lab.org:12345
slicemgr=http://www.planet-lab.org:12347
""" %(opts.framework, issuer, subject, opts.cert, opts.plkey)

    omni_config_dict = {
                        'cf' : opts.framework,
                        'user' : user, 
                        'urn' : urn,
                        'pkey' : public_key_file,
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
pg-gpo1=,https://pgeni.gpolab.bbn.com/protogeni/xmlrpc/am/1.0
pg-gpo2=,https://pgeni.gpolab.bbn.com/protogeni/xmlrpc/am/2.0
pg-gpo=,https://pgeni.gpolab.bbn.com/protogeni/xmlrpc/am/2.0
pg-bbn1=,https://pgeni.gpolab.bbn.com/protogeni/xmlrpc/am/1.0
pg-bbn2=,https://pgeni.gpolab.bbn.com/protogeni/xmlrpc/am/2.0
pg-bbn=,https://pgeni.gpolab.bbn.com/protogeni/xmlrpc/am/2.0

pg-utah1=,https://www.emulab.net/protogeni/xmlrpc/am/1.0
pg-utah2=,https://www.emulab.net/protogeni/xmlrpc/am/2.0
pg-utah3=,https://www.emulab.net/protogeni/xmlrpc/am/3.0
pg-utah=,https://www.emulab.net/protogeni/xmlrpc/am/2.0

pg-ky1=,https://www.uky.emulab.net/protogeni/xmlrpc/am/1.0
pg-ky2=,https://www.uky.emulab.net/protogeni/xmlrpc/am/2.0
pg-ky3=,https://www.uky.emulab.net/protogeni/xmlrpc/am/3.0
pg-ky=,https://www.uky.emulab.net/protogeni/xmlrpc/am/2.0

#Plublic PlanetLab AM
plc=,https://www.planet-lab.org:12346
plc3=,https://sfav3.planet-lab.org:12346 

# Private myplc installations
pl-gpo=,http://myplc.gpolab.bbn.com:12346/
pl-bbn=,http://myplc.gpolab.bbn.com:12346/
pl-clemson=,http://myplc.clemson.edu:12346/
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

#Exogeni AMs include OpenFlow ExoGENI AMs
eg-gpo=,https://bbn-hn.exogeni.net:11443/orca/xmlrpc
eg-bbn=,https://bbn-hn.exogeni.net:11443/orca/xmlrpc
eg-of-gpo=,https://bbn-hn.exogeni.net:3626/foam/gapi/1
eg-of-bbn=,https://bbn-hn.exogeni.net:3626/foam/gapi/1

eg-of-renci=,https://rci-hn.exogeni.net:3626/foam/gapi/1 
eg-renci=,https://rci-hn.exogeni.net:11443/orca/xmlrpc

# ExoSM
eg-sm=,https://geni.renci.org:11443/orca/xmlrpc


#InstaGENI AMs, include OpenFlow InstaGENI AMs
ig-utah1=,http://utah.geniracks.net/protogeni/xmlrpc/am
ig-utah2=,http://utah.geniracks.net/protogeni/xmlrpc/am/2.0
ig-utah3=,http://utah.geniracks.net/protogeni/xmlrpc/am/3.0
ig-utah=,http://utah.geniracks.net/protogeni/xmlrpc/am/2.0
ig-of-utah=,https://foam.utah.geniracks.net:3626/foam/gapi/1

ig-gpo1=,http://instageni.gpolab.bbn.com/protogeni/xmlrpc/am/1.0
ig-gpo2=,http://instageni.gpolab.bbn.com/protogeni/xmlrpc/am/2.0
ig-gpo3=,http://instageni.gpolab.bbn.com/protogeni/xmlrpc/am/3.0
ig-gpo=,http://instageni.gpolab.bbn.com/protogeni/xmlrpc/am/2.0
ig-of-gpo=,https://foam.gpolab.bbn.com:3626/foam/gapi/1 
ig-bbn1=,http://instageni.gpolab.bbn.com/protogeni/xmlrpc/am/1.0
ig-bbn2=,http://instageni.gpolab.bbn.com/protogeni/xmlrpc/am/2.0
ig-bbn3=,http://instageni.gpolab.bbn.com/protogeni/xmlrpc/am/3.0
ig-bbn=,http://instageni.gpolab.bbn.com/protogeni/xmlrpc/am/2.0
ig-of-bbn=,https://foam.gpolab.bbn.com:3626/foam/gapi/1 

""" % omni_config_dict

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

    print >>f, omni_config_file
    f.close()
    logger.info("Wrote omni configuration file at: %s", opts.configfile)
   

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
    (pr_key_file, pub_key_file) = createSSHKeypair(opts)
    createConfigFile(opts,pub_key_file)

if __name__ == "__main__":
    sys.exit(main())
