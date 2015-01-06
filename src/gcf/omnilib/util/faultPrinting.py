#----------------------------------------------------------------------
# Copyright (c) 2010-2015 Raytheon BBN Technologies
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
import re

def cln_xmlrpclib_fault(fault):
    ''' XMLRPCLIB Faults often come escaped - particularly embedded stack traces.
    Clean them up for printing.'''
    clnfault = re.sub(r'\\\\n', "\n", str(fault))
    clnfault = re.sub(r"\\\\\\", r"\\", clnfault)
    clnfault = re.sub(r"\\'", "'", clnfault)
#    ret = ("%s (%s)" % (re.sub("'Traceback", "\nTraceback", clnfault), str(fault)))
    ret = re.sub("'Traceback", "\nTraceback", clnfault)
    if len(ret) > 80:
        ret = re.sub("\.\ +(?=[^\n])", ".\n    ", ret)
    return ret

