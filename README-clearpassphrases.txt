= A script for removing the passphrase from a ProtoGENI certificate = 

clear-passphrases.py is a script that will remove the passphrase from the
private key of your certificate and/or the SSH private key. It will use 
the omni_config file to read the used files. 

If you don't want to use the omni_config file you can specify a specific 
certfile and/or an SSH private key file. 

This script will:
  * Use an omni_config file by default, it uses the same logic as omni.py 
    to locate a default omni_config file
  * Ask the user whether to remove the passphrase from the certificate and/or
    the SSH private key 
  * Check if the cert/key are already unenecrypted (in which case the
    script does nothing)
  * Create a backup of the current certificate file and SSH private key
  * Replace the existing certificate/key file with the unencrypted one

= Usage =

Usage: clear-passphrases.py [options]

Options:
  -h, --help            show this help message and exit
  -c FILE, --configfile=FILE
                        Config file location
  -f FRAMEWORK, --framework=FRAMEWORK
                        Control framework to use for creation/deletion of
                        slices
  -k FILE, --prcertkey=FILE
                        Private key for SSL certificate file location
  -e FILE, --prkey=FILE
                        Private SSH key file location
  -v, --verbose         Turn on verbose command summary for clear-passphrases
                        script
