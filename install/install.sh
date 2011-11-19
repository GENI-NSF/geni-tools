# Debian/Ubuntu
sudo apt-get install python-m2crypto python-dateutil \
                     python-pyopenssl libxmlsec1 xmlsec1 \
                     libxmlsec1-openssl libxmlsec1-dev

# RedHat/Fedora
# sudo yum install m2crypto python-dateutil pyOpenSSL xmlsec1 \
#                  xmlsec1-devel xmlsec1-openssl xmlsec1-openssl-devel


python ../gcf/src/gen-certs.py 
run_gcf.sh