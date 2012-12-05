#!/bin/bash
rm -f /tmp/ch-log /tmp/am-log
~/gcf/src/gcf-gch-gib.py &> /tmp/ch-log &
~/gcf/src/gcf-am-gib.py &> /tmp/am-log &

