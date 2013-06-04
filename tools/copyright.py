#!/usr/bin/env python
#----------------------------------------------------------------------
# Copyright (c) 2010-2013 Raytheon BBN Technologies
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
# Copyright (c) 2013 Raytheon BBN Technologies
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

def find_grep():
    for dir in os.getenv('PATH', '/bin:/usr/bin').split(':'):
        candidate = os.path.join(dir, 'grep')
        if os.path.exists(candidate):
            return candidate

def report_file(path, exceptions):
    # Only report if the file is not empty?
    if not path in exceptions and os.path.getsize(path):
        print('No copyright in %r' % (path))

def report_dir(dir, grep, exceptions):
    logger.debug('Reporting from %s', dir)
    for (dirpath, dirnames, filenames) in os.walk(dir):
        for filename in filenames:
            if filename.endswith('.py'):
                path = os.path.join(dirpath, filename)
                # Need to send the output somewhere...
                cmd = '%s -q -L -i copyright %s' % (grep, path)
                logger.debug('Checking %s', cmd)
                status = os.system(cmd)
                logger.debug('\t==> %d', status)
                if status:
                    report_file(path, exceptions)


def do_report(dirs, exceptions):
    grep = find_grep()
    for dir in dirs:
        report_dir(dir, grep, exceptions)
                        
def parse_args(argv):
    usage = "usage: %prog [options] dir1 dir2"
    parser = optparse.OptionParser(usage=usage)
    parser.add_option("--debug", action="store_true", default=False,
                      help="enable debugging output")
    parser.add_option("-e", "--exception", action="append", default=[],
                      metavar="FILE", help="add a FILE exception")
    return parser.parse_args()

def main(argv=None):
    if argv is None:
        argv = sys.argv
    opts, args = parse_args(argv)
    level = logging.INFO
    logging.basicConfig(level=level)
    if opts.debug:
        level = logging.DEBUG
    global logger
    logger = logging.getLogger("copyright")
    logger.setLevel(level)
    if not args:
        args = ('.')
    do_report(args, exceptions=opts.exception)

if __name__ == "__main__":
    sys.exit(main())
