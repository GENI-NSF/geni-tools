#!/bin/bash

if [ $# != 2 ] 
then
    echo "Usage: deletesliver pathToHomeDir pathToSliceSpecificScriptsDir"
    exit 1
fi

# Stop the PCs
echo "Stopping running containers..."
vzctl stop 101
vzctl stop 102
vzctl stop 103
vzctl stop 104
vzctl stop 105
vzctl stop 106

# Destroy containers
echo "Destroying containers..."
vzctl destroy 101
vzctl destroy 102
vzctl destroy 103
vzctl destroy 104
vzctl destroy 105
vzctl destroy 106

# Disable and delete bridges 
echo "Disabling and deleting bridges..."
for i in $(brctl show | awk '{print $1}')
    do
    if  [ $i != "bridge" ]
    then
        echo "Disabling and deleting bridge $i..."
        /sbin/ifconfig $i down
        /usr/sbin/brctl delbr $i
    fi
done

echo "Cleaning up files created for sliver"
rm -f $1/.ssh/known_hosts

# Delete the files that hold the sliver status
rm -f $2/*.status

exit 0
