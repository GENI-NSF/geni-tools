import logging
import os

#SFA access log initialization
TMPDIR = os.getenv("TMPDIR", "/tmp")
SFA_HTTPD_ACCESS_LOGFILE = TMPDIR + "/" + 'sfa_httpd_access.log'
SFA_ACCESS_LOGFILE='/var/log/sfa_access.log'
logger=logging.getLogger('sfa')
logger.setLevel(logging.INFO)

try:
    logfile=logging.FileHandler(SFA_ACCESS_LOGFILE)
except IOError:
    # This is usually a permissions error becaue the file is
    # owned by root, but httpd is trying to access it.
    logfile=logging.FileHandler(SFA_HTTPD_ACCESS_LOGFILE)
    
formatter = logging.Formatter("%(asctime)s - %(message)s")
logfile.setFormatter(formatter)
logger.addHandler(logfile)
def get_sfa_logger():
    return logger
