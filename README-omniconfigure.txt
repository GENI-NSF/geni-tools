= Configuring Omni = 

GCF v1.6.2 and later comes with a configuration script (omni-configure.py)
that will automatically configure Omni for users with a standard setup.
Users with more complicated setups should manually configure Omni. 

You SOULD manually configure Omni if :
  * you want to use your account with PlanetLab to reserve GENI resources
  * you want to configure to use multiple GENI accounts (e.g. your account 
    with emulab.net as well as with pgeni.gpolab.bbn.com)
  * you want multiple uses to have access to the reserved compute resources. 

== omni-configure.py script ==

omni-configure.py is a script that will automatically create
the configuration file that Omni requires to run. 

The script is intended for new users that want a default configuration 
for using omni. 

Currently the omni-configure.py script fully supports ProtoGENI certificates,
and also supports configuration using existing SFA certs.

omni-configure.py will :
  * create an omni_config file and place it under ~/.gcf by default. If file
    ~/.gcf/omni_config already exists the user will be prompted about whether a
    backup of the existing file should be created. 
  * create an SSH public key based on the private key of your certificate
    and place it under ~/.ssh (~/.ssh/geni_key and ~/.ssh/geni_key.pub). 
    If the files already exist the user will be prompted about whether to 
    overwrite them or not. If the user chooses not to overwrite them, a new 
    location will be picked. 
    This public key is uploaded to any compute nodes that the user reserves
    using Omni and gives ssh access to the nodes, through the private key.
  * Updates the ssh config file (~/.ssh/config) to use by default the private
    key created by the script to login to nodes. 

=== Running omni-configure.py ===
omni-configure.py needs only one file as input, the certificate file. 

If you have an account with a ProtoGENI site then:
  * login to the web UI (e.g. www.pgeni.gpolab.bbn.com, www.emulab.net)
  * download and save a copy of the cert under ~/.ssl/geni_cert.pem
  * run omni-configure.py

=== Usage of omni-configure.py ===

Usage: 
 Script for automatically configuring Omni.

Options:
  -h, --help            show this help message and exit
  -c FILE, --configfile=FILE
                        Config file location [DEFAULT: ~/.gcf/omni_config]
  -p FILE, --cert=FILE  User certificate file location [DEFAULT:
                        ~/.ssl/geni_cert.pem]
  -k FILE, --plkey=FILE
                        PlanetLab private key file location [DEFAULT:
                        ~/.ssh/geni_pl_key]
  -f FRAMEWORK, --framework=FRAMEWORK
                        Control framework that you have an account with
                        [options: [pg, pl], DEFAULT: pg]
  -v, --verbose         Turn on verbose command summary for omni-configure
                        script

== Manually configuring Omni ==

In summary, to manually configure Omni, please copy omni_config.sample to 
~/.gcf/omni_config and fill in the parameters for at least one
control framework - particularly the location of your certificate 
and key, in its appropriate section.  
Edit the [omni] section to specify that framework as your default. 
Embedded comments describe the meaning of each field. 
(Note that keys for the GCF framework are stored in ~/.gcf by default.)

For step-by-step instructions about how to configure Omni, please look at:
http://trac.gpolab.bbn.com/gcf/wiki/OmniConfigure
