#!/bin/bash

# This script should be run just ONE TIME to configure the host container.
# This script is run as part of the process of setting up a VirtualBox a VM 
#  with GENI-in-a-Box.  GENI-in-a-Box users should not have to run this script

# This script should be run by root


# Add /etc/host entries so the GENI-in-a-Box aggregate manager and 
#    resources can be referenced by name.
# Save current copy of /etc/hosts
cp /etc/hosts /etc/hosts.save   

# Add geni-in-a-box.net as an alias for localhost
cat /etc/hosts.save | sed 's/127.0.0.1[[:space:]]*localhost.localdomain[[:space:]]*localhost/& geni-in-a-box.net/' > /etc/hosts

# Add entries for the VMs.  Use the IP address on the control network
echo "10.0.1.101 pc101.geni-in-a-box.net pc101" >> /etc/hosts
echo "10.0.1.102 pc102.geni-in-a-box.net pc102" >> /etc/hosts
echo "10.0.1.103 pc103.geni-in-a-box.net pc103" >> /etc/hosts
echo "10.0.1.104 pc104.geni-in-a-box.net pc104" >> /etc/hosts
echo "10.0.1.105 pc105.geni-in-a-box.net pc105" >> /etc/hosts
echo "10.0.1.106 pc106.geni-in-a-box.net pc106" >> /etc/hosts

# Copy the .desktop file to the proper place so the gib-startup.sh script is run when the user logs in
mkdir -p ~/.config/autostart
cp ~/gcf/gib-config-files/gibStart.desktop ~/.config/autostart

