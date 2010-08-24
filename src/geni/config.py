import ConfigParser
import sys

GCF_CONFIG_FILE='gcf_config'

# Read the config file into a dictionary where each section
# of the config is its own sub-dictionary
def read_config():
    confparser = ConfigParser.RawConfigParser()
    try:
        confparser.read(GCF_CONFIG_FILE)
    except ConfigParser.Error as exc:
        sys.exit("Config file %s could not be parsed: %s"
                 % (GCF_CONFIG_FILE, str(exc)))    
    
    
    config = {}
    
    for section in confparser.sections():
        config[section] = {}
        for (key,val) in confparser.items(section):
            config[section][key] = val
    
    return config
