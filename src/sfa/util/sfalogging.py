#!/usr/bin/python

import os
import traceback
import logging, logging.handlers

# a logger that can handle tracebacks 
class _SfaLogger:
    def __init__ (self,logfile=None,loggername=None,level=logging.INFO):
        # default is to locate loggername from the logfile if avail.
        if not logfile:
            loggername='console'
            handler=logging.StreamHandler()
            handler.setFormatter(logging.Formatter("%(message)s"))
        else:
            if not loggername:
                loggername=os.path.basename(logfile)
            try:
                handler=logging.handlers.RotatingFileHandler(logfile,maxBytes=1000000, backupCount=5) 
            except IOError:
                # This is usually a permissions error becaue the file is
                # owned by root, but httpd is trying to access it.
                tmplogfile=os.getenv("TMPDIR", "/tmp") + os.path.sep + os.path.basename(logfile)
                handler=logging.handlers.RotatingFileHandler(tmplogfile,maxBytes=1000000, backupCount=5) 
            handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))

        self.logger=logging.getLogger(loggername)
        self.logger.setLevel(level)
        self.logger.addHandler(handler)

    def setLevel(self,level):
        self.logger.setLevel(level)

    ####################
    def wrap(fun):
        def wrapped(self,msg,*args,**kwds):
            native=getattr(self.logger,fun.__name__)
            return native(msg,*args,**kwds)
        #wrapped.__doc__=native.__doc__
        return wrapped

    @wrap
    def critical(): pass
    @wrap
    def error(): pass
    @wrap
    def warning(): pass
    @wrap
    def info(): pass
    @wrap
    def debug(): pass
    
    # logs an exception - use in an except statement
    def log_exc(self,message):
        self.error("%s BEG TRACEBACK"%message+"\n"+traceback.format_exc().strip("\n"))
        self.error("%s END TRACEBACK"%message)
    
    def log_exc_critical(self,message):
        self.critical("%s BEG TRACEBACK"%message+"\n"+traceback.format_exc().strip("\n"))
        self.critical("%s END TRACEBACK"%message)
    
    # for investigation purposes, can be placed anywhere
    def log_stack(self,message):
        to_log="".join(traceback.format_stack())
        self.debug("%s BEG STACK"%message+"\n"+to_log)
        self.debug("%s END STACK"%message)

sfa_logger=_SfaLogger(logfile='/var/log/sfa.log')
sfa_import_logger=_SfaLogger(logfile='/var/log/sfa_import.log')
console_logger=_SfaLogger()

########################################
import time

def profile(logger):
    """
    Prints the runtime of the specified callable. Use as a decorator, e.g.,
    
    @profile(logger)
    def foo(...):
        ...
    """
    def logger_profile(callable):
        def wrapper(*args, **kwds):
            start = time.time()
            result = callable(*args, **kwds)
            end = time.time()
            args = map(str, args)
            args += ["%s = %s" % (name, str(value)) for (name, value) in kwds.items()]
            # should probably use debug, but then debug is not always enabled
            logger.info("PROFILED %s (%s): %.02f s" % (callable.__name__, ", ".join(args), end - start))
            return result
        return wrapper
    return logger_profile


if __name__ == '__main__': 
    print 'testing sfalogging into logger.log'
    logger=_SfaLogger('logger.log')
    logger.critical("logger.critical")
    logger.error("logger.error")
    logger.warning("logger.warning")
    logger.info("logger.info")
    logger.debug("logger.debug")
    logger.setLevel(logging.DEBUG)
    logger.debug("logger.debug again")
    
    @profile(console_logger)
    def sleep(seconds = 1):
        time.sleep(seconds)

    
    console_logger.info('console.info')
    sleep(0.5)
    console_logger.setLevel(logging.DEBUG)
    sleep(0.25)
