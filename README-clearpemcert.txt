= A script for removing the passphrase from a ProtoGENI certificate = 

clear-pem-cert.py is a script that will remove the passphrase from the 
private key of your certificate. 

This script will:
  * create a backup of the current certificate file
  * replace the existing certificate file with the unencrypted one

= Usage of omni-configure.py =

Usage: clear-pem-cert.py [options]

Options:
  -h, --help            show this help message and exit
  -p FILE, --cert=FILE  User certificate file location [DEFAULT:
                        ~/.ssl/geni_cert.pem]
  -v, --verbose         Turn on verbose command summary for omni-configure
                        script
