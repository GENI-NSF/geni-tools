#!/bin/bash

%SOURCE%

#See http://www.gpolab.bbn.com/local-sw/ for gpo software links

FILES="../scripts/doPing.sh ../scripts/maxScript.sh ../scripts/pgScript.sh"
TARFILES="pingPlus-0.1.tar.gz"

echo /usr/bin/scp -i $STITCH_KEYFILE $FILES "$STITCH_USERNAME@$STITCH_HOSTNAME:~/."
/usr/bin/scp -i $STITCH_KEYFILE $FILES "$STITCH_USERNAME@$STITCH_HOSTNAME:~/."

echo /usr/bin/ssh -i $STITCH_KEYFILE $STITCH_USERNAME@$STITCH_HOSTNAME "wget --post-data 'software=pingPlus-0.1.tar.gz&accept=I+have+read+and+accept+the+GPO+terms+of+service+and+disclaimer' http://www.gpolab.bbn.com/local-sw/real_download -O pingPlus-0.1.tar.gz"
/usr/bin/ssh -i $STITCH_KEYFILE $STITCH_USERNAME@$STITCH_HOSTNAME "wget --post-data 'software=pingPlus-0.1.tar.gz&accept=I+have+read+and+accept+the+GPO+terms+of+service+and+disclaimer' http://www.gpolab.bbn.com/local-sw/real_download -O pingPlus-0.1.tar.gz"

#This now happens in pgScript.sh and maxScript.sh
#echo /usr/bin/ssh -i $STITCH_KEYFILE $STITCH_USERNAME@$STITCH_HOSTNAME "tar xzf $TARFILES"
#/usr/bin/ssh -i $STITCH_KEYFILE $STITCH_USERNAME@$STITCH_HOSTNAME "tar xzf $TARFILES"
