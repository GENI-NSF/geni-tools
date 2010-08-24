import ConfigParser
import sys

GCF_CONFIG_FILE='gcf_config'

# Read the config file into a dictionary where each section
# of the config is its own sub-dictionary
def read_config(path=None):
    confparser = ConfigParser.RawConfigParser()
    try:
        if path:
            conf = path
            confparser.read(path)
        else:
            conf = GCF_CONFIG_FILE
            confparser.read(GCF_CONFIG_FILE)
            
    except ConfigParser.Error as exc:
        sys.exit("Config file %s could not be parsed (or possibly not found): %s"
                 % (conf, str(exc)))    
    
    
    config = {}
    
    for section in confparser.sections():
        config[section] = {}
        for (key,val) in confparser.items(section):
            config[section][key] = val
    
    return config
