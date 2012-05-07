= A script for configuring omni = 

omni-configure.py is a script that will automatically create
the configuration file that Omni requires to run. 

The script is intended for new users that want a default configuration 
for using omni. 

Currently the omni-configure.py script fully supports ProtoGENI certificates,
and also supports configuration using existing SFA certs.

omni-configure.py will :
  * create an omni_config file and place it under ~/.gcf by default
  * create a public key based on the private key of your certificate and place
  it under ~/.ssh. This public key is uploaded to any compute nodes that you
  might reserve and give ssh access to the nodes 

= Running omni-configure.py =
omni-configure.py needs only one file as input, the certificate file. 

If you have an account with a ProtoGENI site then:
  * login to the web UI (e.g. www.pgeni.gpolab.bbn.com, www.emulab.net)
  * download and save a copy of the cert under ~/.ssl/
  * run omni-configure.py

= Usage of omni-configure.py =

nriga@pella:~/gcf$ omni-configure.py -h 
Usage: 
 Script for automatically configuring Omni.

Options:
  -h, --help            show this help message and exit
  -c FILE, --configfile=FILE
                        Config file location (DEFAULT: ~/.gcf/omni_config)
  -p FILE, --cert=FILE  User certificate file location (DEFAULT: ~/.ssl/geni_cert.pem)
  -k FILE, --plkey=FILE
                        PlanetLab private key file location (DEFAULT: ~/.ssh/geni_pl_key) 
  -f FRAMEWORK, --framework=FRAMEWORK
                        Control framework that you have an account with
                        (DEFAULT: pg)
  -v, --verbose         Turn on verbose command summary for omni-configure
                        script



