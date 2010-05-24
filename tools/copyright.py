#!/usr/bin/env python
#----------------------------------------------------------------------
# Copyright (c) 2010 Raytheon BBN Technologies
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

import logging
import optparse
import os
import sys

copyright = """#----------------------------------------------------------------------
# Copyright (c) 2010 Raytheon BBN Technologies
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
"""

logger = None

def do_report(top):
    logger.debug('Reporting from %s', top)
    for (dirpath, dirnames, filenames) in os.walk(top):
        for filename in filenames:
            if filename.endswith('.py'):
                path = os.path.join(dirpath, filename)
                logger.debug('Checking %s', path)
                # Need to send the output somewhere...
                status = os.system('/usr/bin/grep -q -L -i copyright %s' % (path))
                logger.debug('\t==> %d', status)
                if status:
                    # Only report if the file is not empty?
                    if os.path.getsize(path):
                        print('No copyright in %r' % (path))

def parse_args(argv):
    parser = optparse.OptionParser()
    parser.add_option("--debug", action="store_true", default=False,
                       help="enable debugging output")
    return parser.parse_args()

commands = {
    'report': do_report
}

def main(argv=None):
    if argv is None:
        argv = sys.argv
    opts, args = parse_args(argv)
    level = logging.INFO
    logging.basicConfig(level=level)
    logging.debug('bar')
    if opts.debug:
        level = logging.DEBUG
    global logger
    logger = logging.getLogger("copyright")
    logger.setLevel(level)
    if not args:
        args = ('report',)
    commands[args[0]](*args[1:])

if __name__ == "__main__":
    sys.exit(main())
