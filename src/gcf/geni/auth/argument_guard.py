#----------------------------------------------------------------------
# Copyright (c) 2011-2015 Raytheon BBN Technologies
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

from __future__ import absolute_import

# Support for testing arguments/options of an AM call before invoking it
# Possibly raising an exception, possibly modifying the arguments 
# before invocation

from .base_authorizer import AM_Methods

# Base class for argument guard
class Base_Argument_Guard:

    # Check the arguments and options presented to the given call
    # Either return an exception or 
    # return the (same or modified) arguments and options
    def validate_arguments(self, method_name, arguments, options):
        return arguments, options

class TEST_Argument_Guard:

    def validate_arguments(self, method_name, arguments, options):

        options['Test_Entry'] = 'Test_Option_Value'
        arguments['Test_Argument'] = 'Test_Argument_Value'
        return arguments, options
