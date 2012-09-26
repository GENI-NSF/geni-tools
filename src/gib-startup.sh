#!/bin/bash
rm -f /tmp/ch-log /tmp/am-log
~/gcf/src/gcf-pgch.py &> /tmp/ch-log &
~/gcf/src/gcf-am.py &> /tmp/am-log &

