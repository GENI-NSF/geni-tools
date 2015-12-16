#!/bin/bash

#----------------------------------------------------------------------
# Copyright (c) 2014-2015 Raytheon BBN Technologies
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and/or hardware specification (the "Work") to
# deal in the Work without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Work, and to permit persons to whom the Work
# is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Work.
#
# THE WORK IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE WORK OR THE USE OR OTHER DEALINGS
# IN THE WORK.
#----------------------------------------------------------------------

# This script sets up shell aliases for the commands in the GENI 
# omniTools package. The commands are written to one of the user's 
# bash rc files.  It looks for an rc file in the same order bash on
# Mac OS looks for bash rc files.

## Function that writes aliases to the specified rc file
writeAliases () {
    # Append a blank last line if there isn't one already
    lastline=`tail -1 $1`
    if [ "$lastline" != "" ]; then
	echo $'\n' >> $1
    fi
    echo "# Aliases for commands in the GENI omniTools-2.10 package" >> $1
    echo "alias omni='/Applications/omniTools-2.10/omni.app/Contents/MacOS/omni'" >> $1
    echo "alias stitcher='/Applications/omniTools-2.10/stitcher.app/Contents/MacOS/stitcher'" >> $1
    echo "alias omni-configure='/Applications/omniTools-2.10/omni-configure.app/Contents/MacOS/omni-configure'" >> $1
    echo "alias readyToLogin='/Applications/omniTools-2.10/readyToLogin.app/Contents/MacOS/readyToLogin'" >> $1
    echo "alias addMemberToSliceAndSlivers='/Applications/omniTools-2.10/addMemberToSliceAndSlivers.app/Contents/MacOS/addMemberToSliceAndSlivers'" >> $1
    echo "alias clear-passphrases='/Applications/omniTools-2.10/clear-passphrases.app/Contents/MacOS/clear-passphrases'" >> $1
    echo "alias remote-execute='/Applications/omniTools-2.10/remote-execute.app/Contents/MacOS/remote-execute'" >> $1
}

# Function that removes lines that look like what writeAliases adds
removeAliases () {
   sed -i".bak" '/\/Applications\/omniTools/d;/# Aliases for commands in the GENI omniTools/d' $1
}

wroteAliases=false

# Look for a file with aliases in 3 usual spots
# First, delete any existing aliases
for rcFile in $HOME/.bash_profile $HOME/.bash_login $HOME/.profile ; do
    if [ -f $rcFile ] ; then
	removeAliases $rcFile
    fi
done

# Then add the new aliases - but only once
for rcFile in $HOME/.bash_profile $HOME/.bash_login $HOME/.profile ; do
    if [ -f $rcFile ] ; then
        writeAliases $rcFile
        wroteAliases=true
        break
    fi
done

# If none of the bash rc files are found, create a .bash_profile and write 
# aliases into it.
if ! $wroteAliases ; then
    rcFile="$HOME/.bash_profile"
    echo $rcFile
    touch $rcFile
    writeAliases $rcFile
fi
