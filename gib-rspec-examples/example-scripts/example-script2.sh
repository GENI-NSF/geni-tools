#!/bin/bash

echo "The script 'example-script2.sh' has been installed!"
echo "This one also does other things such as create directories and files!"

mkdir -p /tmp/gib-examples
touch /tmp/gib-examples/gib-example-install.README
echo "This is a example file used for demonstrating install scripts for GENI-in-a-Box">>/tmp/gib-examples/gib-example-install.README

echo "Created an example file under /tmp/gib-examples/gib-example-install.README for the given container"
