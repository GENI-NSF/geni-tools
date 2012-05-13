= A script for removing the passphrase from a ProtoGENI certificate = 

clear-passphrase.py is a script that will remove the passphrase from the 
private key of your certificate and/or the ssh private key.

This script will:
  * ask the user whether to remove the passphrase from the certificate and/or
  the ssh private key given by the command line options
  * check if the cert/key are already unenecrypted in which case is a noop
  * create a backup of the current certificate file
  * replace the existing certificate/key file with the unencrypted one

= Usage of omni-configure.py =

Usage: clear-passphrases.py [options]

Options:
  -h, --help            show this help message and exit
  -p FILE, --cert=FILE  User certificate file location [DEFAULT:
                        ~/.ssl/geni_cert.pem]
  -k FILE, --key=FILE   Private SSH key file location [DEFAULT:
                        ~/.ssh/geni_key]
  -v, --verbose         Turn on verbose command summary for omni-configure
                        script

