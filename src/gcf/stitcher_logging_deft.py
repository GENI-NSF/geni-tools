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

# Define a default stitcher logging configuration
# Used only when running from exe on windows or mac,
# when the stitcher_logging.conf file cannot be found

DEFT_STITCHER_LOGGING_CONFIG = """; Stitcher logging config file

; For format info, see
; http://docs.python.org/library/logging.config.html#configuration-file-format

; For built-in variables available in formatters, see
; http://docs.python.org/library/logging.html#logrecord-attributes

; Note the special variable 'optlevel' below: If you use it, that means
; take the log level computed from the command line. Specifically, log
; at INFO usually, and at DEBUG if --debug is given on the command line.

; Also note use of logfilename set with --logoutput

[loggers]
; Add other loggers in a comma separated list.
keys=root,omni

[handlers]
; Add other handlers in a comma separated list.
keys=consoleHandler,omniconsoleHandler,fileHandler

[formatters]
keys=defaultConsoleFormatter,detailFormatter

; By default, everything goes to console and a file
[logger_root]
level=NOTSET ; Log everything
; %(optlevel)s ; Usually, INFO. DEBUG if --debug option specified.
handlers=consoleHandler,fileHandler

; Omni stuff goes to console and file, but less goes to console
[logger_omni]
;level=WARN
handlers=omniconsoleHandler,fileHandler
; qualname is how the code retrieves the logger instance
; Other values: omni.framework, omni.protogeni, omni.sfa, omni.credparsing, cred-verifier
qualname=omni
; set propagate=1 if you want parent loggers to also get the log messages
; But here set to 0 so the root logger doesn't duplicate messages
propagate=0

[handler_consoleHandler]
class=StreamHandler
level=%(optlevel)s ; Log only to the level specified with --debug, etc
formatter=defaultConsoleFormatter
args=(sys.stdout,)

; Log only at WARN level omni stuff to console
[handler_omniconsoleHandler]
class=StreamHandler
level=WARN
formatter=defaultConsoleFormatter
args=(sys.stdout,)

; Log everything to a file
[handler_fileHandler]
class=FileHandler
level=NOTSET ; Log everything
formatter=detailFormatter
; logfilename is from the --logoutput option, default is omni.log for oscript, stitcher.log for stitcher
args=('%(logfilename)s',)

; The default format you get for a console logger
[formatter_defaultConsoleFormatter]
format=%(asctime)s %(levelname)-8s: %(message)s
datefmt=%H:%M:%S

; Add the filename, function, line# if known
[formatter_detailFormatter]
; %(funcName)s
; %(pathname)s of source file
; %(names)s of logger
format=%(asctime)s %(levelname)-8s %(filename)s:%(lineno)d %(message)s
datefmt=%m/%d %H:%S
"""
