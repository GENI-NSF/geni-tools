#----------------------------------------------------------------------
# Copyright (c) 2015 Inria by David Margery
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
An aggregate manager delegate that raises an APIErrorException to test
behavior in gcf.geni.am.am3.AggregateManager when calling a delagate
that raises an exception.
"""

import gcf.geni.am.am3 as am3

class ExceptionRaiserDelegate(am3.ReferenceAggregateManager):
    def __init__(self, root_cert, urn_authority, url, **kwargs):
        super(ExceptionRaiserDelegate,self).__init__(root_cert,urn_authority,url,**kwargs)

    def Shutdown(self, slice_urn, credentials, options):
        raise am3.ApiErrorException(am3.AM_API.REFUSED, "test exception")
