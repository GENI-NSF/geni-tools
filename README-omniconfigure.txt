= Configuring Omni = 

GCF v1.6.2 and later comes with a configuration script (omni-configure.py)
that will automatically configure Omni for users with a standard setup.
Users with more complicated setups should manually configure Omni. 

You SHOULD manually configure Omni if :
  * you want to use your account with PlanetLab to reserve GENI resources and 
    you don't already have a copy of your certificate file
  * you want to use multiple GENI accounts (e.g. your account 
    with emulab.net as well as with pgeni.gpolab.bbn.com)
  * you want multiple users to have access to the reserved compute resources. 

== Release Notes ==
As of GCF v2.5, omni-configure by default uses the new `chapi`
interface for talking to the GENI Portal, which enables several new
features. To use the old style interface, supply the option `--not-use-chapi`.

GCF v2.2.1 and later also supports automatic configuration of omni 
for portal credentials. 

Look at help for more info. 
== omni-configure.py script ==

omni-configure.py is a script that will automatically create
the configuration file that Omni requires to run. 

The script is intended for new users that want a standard configuration 
for using omni. 

Currently the omni-configure.py script fully supports ProtoGENI certificates
and certificates from the GENI Portal. It also supports configuration 
using existing SFA certs.

omni-configure.py will :
  * create an omni_config file and place it under ~/.gcf by default. If file
    ~/.gcf/omni_config already exists the user will be prompted about whether a
    backup of the existing file should be created. 
  * create an SSH public key based on the private key of your certificate
    and place it under ~/.ssh (The names of the keys will start with geni_key). 
    If the files already exist the user will be prompted about whether to 
    overwrite them or not. If the user chooses not to overwrite them, a new 
    location will be picked. If you are running with a bundle from the portal
    it will use the SSH key-pair created by the portal. 
    This public key is uploaded to any compute nodes that the user reserves
    using Omni and gives ssh access to the nodes, through the private key.
    key created by the script to login to nodes. 
  * If you are using your account from the GENI portal, then an extra SSH 
    key pair will be created based on your SSL cert (name geni_cert_portal_key)

=== Running omni-configure.py ===
omni-configure.py needs only one file as input: the certificate file, or
the omni bundle file downloaded from the portal

If you have an account with a ProtoGENI site then:
  * login to the web UI (e.g. www.pgeni.gpolab.bbn.com, www.emulab.net)
  * download and save a copy of the cert under ~/.ssl/geni_cert.pem
  * run omni-configure.py

If you have an account at the GENI Portal then:
  * login to the portal (e.g. at panther.gpolab.bbn.com)
  * under your profile tab, follow instruction about downloading the omni bundle
    and save it at ~/Downloads/omni-bundle.zip
  * run omni-configure.py -f portal


=== Usage of omni-configure.py ===
Usage: 
 Script for automatically configuring Omni.

Options:
  -h, --help            show this help message and exit
  -c FILE, --configfile=FILE
                        Config file location [DEFAULT: ~/.gcf/omni_config]
  -p FILE, --cert=FILE  File location of user SSL certificate. Default is
                        based on the selected framework (see -f option)
                        [DEFAULT: {'portal': '~/.ssl/geni_cert_portal.pem',
                        'pg': '~/.ssl/geni_cert_pg.pem', 'pl':
                        '~/.ssl/geni_cert_pl.gid'}]
  -k FILE, --prcertkey=FILE
                        File location of private key for the user SSL
                        certificate. Default is based on the selected
                        framework (see -f option) [DEFAULT: {'portal':
                        '~/.ssl/geni_ssl_portal.key', 'pg':
                        '~/.ssh/geni_cert_key_pg', 'pl':
                        '~/.ssh/geni_cert_key_pl'}]
  -s FILE, --sshdir=FILE
                        Directory for the location of SSH keys for logging in
                        to compute resources, [DEFAULT: ~/.ssh/]
  -z FILE, --portal-bundle=FILE
                        Bundle downloaded from the portal for configuring Omni
                        [DEFAULT: ~/Downloads/omni-bundle.zip]
  -f FRAMEWORK, --framework=FRAMEWORK
                        Control framework that you have an account with
                        [options: [pg, pl, portal], DEFAULT: portal]
  --pick-project        Lets you choose which project to use as default from
                        the projects in the bundle downloaded from the portal
  --not-use-chapi       If available, do not configure the omni_config to use
                        the common Clearinghouse API (CH API).
  -v, --verbose         Turn on verbose command summary for omni-configure

== Manually configuring Omni ==

In summary, to manually configure Omni, please copy omni_config.sample to 
~/.gcf/omni_config and fill in the parameters for at least one
control framework - particularly the location of your certificate 
and key, in its appropriate section.  
Edit the [omni] section to specify that framework as your default. 
Embedded comments describe the meaning of each field. 
(Note that keys for the GCF framework are stored in ~/.gcf by default.)

For step-by-step instructions about how to configure Omni, please look at:
http://trac.gpolab.bbn.com/gcf/wiki/OmniConfigure/Automatic

== Certificate passphrase ==
While executing Omni, you will be prompted for the passphrase of your
certificate multiple times per call. You should keep a passphrase on 
your certificate for security best practices. If you just want a way 
to type your passphrase only once per session look at:
http://trac.gpolab.bbn.com/gcf/wiki/OmniTroubleShoot#Q.WhydoesOmnipromptformyPEMpassphrasesomanytimesCantOmnipromptonlyonce

Also there is a script that will help removing the passphrase from the
certificate. Look at README-clearpassphrases.txt. 
