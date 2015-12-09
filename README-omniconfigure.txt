= Configuring Omni = 

GCF/Omni comes with a configuration script (omni-configure)
that will automatically configure Omni for users with a standard setup.
Users with more complicated setups should manually configure Omni. 

You SHOULD manually configure Omni if :
  * you want to use your account with PlanetLab to reserve GENI resources and 
    you don't already have a copy of your certificate file
  * you want to use multiple GENI accounts (e.g. your account 
    with portal.geni.net as well as emulab.net)
  * you want multiple users to have access to the reserved compute resources. 

== Release Notes ==

As of GCF v.2.5.3, `omni-configure` better handles being run on a system that
is already configured for use with omni.  This is useful, for example, when
renewing a certificate.

To reconfigure an existing config and be asked before overwriting any relevant
files run:
      `omni-configure`

To reconfigure an existing config and overwrite any relevant
files without being asked run:
      `omni-configure --replace-all`

To delete most files created by `omni-configure`, run:
      `omni-configure --clean`

As of GCF v2.5, omni-configure by default uses the new `chapi`
interface for talking to the GENI Portal, which enables several new
features. To use the old style interface, supply the option `--not-use-chapi`.

GCF v2.2.1 and later also supports automatic configuration of omni 
for portal credentials. 

Look at help for more info. 
== omni-configure script ==

omni-configure is a script that will automatically create
the configuration file that Omni requires to run. 

The script is intended for users that want a standard configuration
for using omni. 

Currently the omni-configure script fully supports ProtoGENI certificates
and certificates from the GENI Portal.

omni-configure will :
  * create an omni_config file and place it under ~/.gcf by default. If file
    ~/.gcf/omni_config already exists the user will be prompted about whether a
    backup of the existing file should be created (unless run with `--replace-all`).
  * create an SSH public key based on the private key of your certificate
    and place it under ~/.ssh (The names of the keys will start with geni_key). 
    If the files already exist the user will be prompted about whether to 
    overwrite them or not (unless run with `--replace-all`). If the user chooses
    not to overwrite them, a new location will be picked. If you are running
    with a bundle from the portal it will use the SSH key-pair created by the portal.
    This public key is uploaded to any compute nodes that the user reserves
    using Omni and gives ssh access to the nodes, through the private key created by
    the script.
  * If you are using your account from the GENI portal, then an extra SSH 
    key pair will be created based on your SSL cert (named geni_cert_portal_key)

=== Running omni-configure ===
omni-configure needs only one file as input: the certificate file for ProtoGENI
accounts, or the omni bundle file downloaded from the GENI Portal for Portal accounts.

If you have an account with a ProtoGENI site then:
  * login to the web UI (e.g. www.emulab.net)
  * download and save a copy of the cert under ~/.ssl/geni_cert.pem
  * run `omni-configure -f pg`

If you have an account at the GENI Portal then:
  * login to the portal (e.g. at portal.geni.net)
  * under your profile tab, follow instruction about downloading the omni bundle
    and save it at ~/Downloads/omni.bundle (or ~/Downloads/omni-bundle.zip)
  * run `omni-configure`


=== Usage of omni-configure ===
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
                        [DEFAULT: []]
  -f FRAMEWORK, --framework=FRAMEWORK
                        Control framework that you have an account with
                        [options: [pg, pl, portal], DEFAULT: portal]
  --pick-project        Lets you choose which project to use as default from
                        the projects in the bundle downloaded from the portal
  --not-use-chapi       If available, do not configure the omni_config to use
                        the common Clearinghouse API (CH API).
  -v, --verbose         Turn on verbose command summary for omni-configure
                        script
  --clean               Clean up files generated by this script. (Does not
                        honor -s/-f options.)
  --clean-all           In addition to files deleted by --clean, also remove
                        input files (i.e. omni bundle files).
  --replace-all         Answer yes to all questions about replacing a file.

== Manually configuring Omni ==

In summary, to manually configure Omni, please copy omni_config.sample to 
~/.gcf/omni_config and fill in the parameters for at least one
control framework - particularly the location of your certificate 
and key, in its appropriate section.  
Edit the [omni] section to specify that framework as your default. 
Embedded comments describe the meaning of each field. 
(Note that keys for the GCF framework are stored in ~/.gcf by default.)

For step-by-step instructions about how to configure Omni, please look at:
https://github.com/GENI-NSF/geni-tools/wiki/Omni-Configuration-Automatically

== Certificate passphrase ==
While executing Omni, you will be prompted for the passphrase of your
certificate multiple times per call. You should keep a passphrase on 
your certificate for security best practices. If you just want a way 
to type your passphrase only once per session look at:
https://github.com/GENI-NSF/geni-tools/wiki/Omni-Troubleshooting#q-why-does-omni-prompt-for-my-pem-passphrase-so-many-times-cant-omni-prompt-only-once

Also there is a script that will help removing the passphrase from the
certificate. Look at README-clearpassphrases.txt. 
