
Instructions
============

1. Initialize the certificate authority and generate keys and certificates:

 $ src/init-ca.py

 This creates a certificate authority key and certificate and then
 creates keys and certificates for a clearinghouse (ch), an aggregate
 manager (am), and a researcher (alice).

2. Start the clearinghouse server:

 $ src/gch.py -r ca-cert.pem -c am-cert.pem -k am-key.pem

3. Start the aggregate manager server:

 $ src/gam.py -r ca-cert.pem -c am-cert.pem -k am-key.pem

4. Run the client

 $ client.py -c alice-cert.pem -k alice-key.pem --ch localhost:8000 \
     --am localhost:8001

 The output should show some basic API testing, and possibly some
 debug output.


Running the clearinghouse
=========================

 $ src/gch.py runserver -c demoCA/cacert.pem -k demoCA/private/cakey.pem  -r demoCA/cacert.pem
 
 $ src/client.py --ch -c alice-cert.pem -k alice-keys.pem
 
 
References
==========

http://panoptic.com/wiki/aolserver/How_to_generate_self-signed_SSL_certificates

http://shib.kuleuven.be/docs/ssl_commands.shtml


Notes
=====

 - We need private keys without passwords in order to avoid typing the
   password on every connection. A password can be removed from a key:

   $ openssl rsa -in cakey.pem -out cakey2.pem

 - Certs should have an appropriate URN as the common name. Create
   such a cert and document how.

 - It would be nice to generate a request from a key (separating the
   two). This would enable an external party to submit a key and get
   back a certificate. Bonus points for doing this with a ssh key.


Creating certs in detail
========================

# Create a key and certificate request
$ openssl req -new -keyout chcert/ch-key.pem -out chcert/ch-req.pem -days 365
Generating a 1024 bit RSA private key
..++++++
..............++++++
writing new private key to 'chcert/ch-key.pem'
Enter PEM pass phrase:
Verifying - Enter PEM pass phrase:
-----
You are about to be asked to enter information that will be incorporated
into your certificate request.
What you are about to enter is what is called a Distinguished Name or a DN.
There are quite a few fields but you can leave some blank
For some fields there will be a default value,
If you enter '.', the field will be left blank.
-----
Country Name (2 letter code) [AU]:.
State or Province Name (full name) [Some-State]:.
Locality Name (eg, city) []:.
Organization Name (eg, company) [Internet Widgits Pty Ltd]:.
Organizational Unit Name (eg, section) []:.
Common Name (eg, YOUR name) []:urn:geni:clearinghouse:127.0.0.1:8000
Email Address []:.

Please enter the following 'extra' attributes
to be sent with your certificate request
A challenge password []:
An optional company name []:



# Sign the certificate
$ ./gch.py sign -i chcert/ch-req.pem -o chcert/ch-cert.pem
Opts = <Values at 0x100707f80: {'directory': '.', 'outfile': 'chcert/ch-cert.pem', 'keyfile': None, 'infile': 'chcert/ch-req.pem', 'verbose': True}>
Args = ['sign']
Using configuration from /System/Library/OpenSSL/openssl.cnf
Enter pass phrase for ./demoCA/private/cakey.pem:
Check that the request matches the signature
Signature ok
Certificate Details:
        Serial Number: 2 (0x2)
        Validity
            Not Before: Mar 22 15:30:04 2010 GMT
            Not After : Mar 22 15:30:04 2011 GMT
        Subject:
            commonName                = urn:geni:clearinghouse:127.0.0.1:8000
        X509v3 extensions:
            X509v3 Basic Constraints: 
                CA:FALSE
            Netscape Comment: 
                OpenSSL Generated Certificate
            X509v3 Subject Key Identifier: 
                7A:58:AB:DF:58:AF:B4:27:89:69:C1:4D:B6:DC:EA:F8:76:4C:88:28
            X509v3 Authority Key Identifier: 
                keyid:B2:65:4D:35:F4:D5:FD:E6:3A:8C:29:15:80:A8:65:51:6D:42:6E:AE

Certificate is to be certified until Mar 22 15:30:04 2011 GMT (365 days)
Sign the certificate? [y/n]:y


1 out of 1 certificate requests certified, commit? [y/n]y
Write out database with 1 new entries
Data Base Updated



# Remove the password from the key
$ openssl rsa -in chcert/ch-key.pem -out ch-key2.pem
Enter pass phrase for chcert/ch-key.pem:
writing RSA key
