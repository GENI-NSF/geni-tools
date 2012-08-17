= A script for removing the passphrase from a ProtoGENI certificate = 

clear-passphrases.py is a script that will remove the passphrase from the
private key of your certificate and/or the SSH private key.

This script will:
  * Ask the user whether to remove the passphrase from the certificate and/or
  the SSH private key given by the command line options
  * Check if the cert/key are already unenecrypted (in which case the
  script does nothing)
  * Create a backup of the current certificate file
  * Replace the existing certificate/key file with the unencrypted one

= Usage =

$ src/clear-passphrases.py [options]

Options:
  -h, --help            show this help message and exit
  -p FILE, --cert=FILE  User certificate file location [DEFAULT:
                        ~/.ssl/geni_cert.pem]
  -k FILE, --key=FILE   Private SSH key file location [DEFAULT:
                        ~/.ssh/geni_key]
  -v, --verbose         Turn on verbose command summary for clear-passphrases
                        script
