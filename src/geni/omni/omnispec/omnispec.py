import json
   
   

class OmniSpec(dict):
    def __init__(self, type, urn, filename = None, dictionary = None):
        dict.__init__(self, {})    

        if filename:
            self.from_json_file(filename)
        elif dictionary:
            self.from_dict(dictionary)
        else:            
            self['type'] = type
            self['urn'] = urn
            self['resources'] = {}
        
    def add_resource(self, urn, resource):
        self['resources'][urn] = resource

    def get_resources(self):
        return self.get('resources')
    def get_type(self):
        return self.get('type')
    
    def __str__(self):
        return self.to_json()
    
    def to_json(self):
        return json.dumps(self, indent=4)
    
        
    def from_dict(self, dictionary):
        self.update(dictionary)
        updates = {}
        for u, r in self['resources'].items():
            updates[u] = OmniResource('','','',dictionary=r)
        for u, r in updates.items():
            self['resources'][u] = r
            
    def from_json_file(self, filename):
        string = file(filename,'r').read()
        return self.from_json(self, string)
    

class OmniResource(dict):
    def __init__(self, name, description, type, dictionary=None):
        dict.__init__(self, {})
        if dictionary:
            self.update(dictionary)
        else:
            self.set_name(name)
            self.set_description(description)
            self.set_type(type)
            self['options'] = {}
            self['allocated'] = False
            self['allocate'] = False
            self['misc'] = {}
        
    def set_name(self, name):
        self['name'] = name
    def set_description(self, description):
        self['description'] = description
    def set_type(self, type):
        self['type'] = type
    
    def add_option(self, name, defValue=None):
        if not defValue:
            defValue = ''
        self['option'][name] = defValue
    def set_allocated(self, value):
        self['allocated'] = value
    
    def allocate(self):
        return self['allocate']
    
    def get_misc(self):
        return self['misc']
    
    def __str__(self):
        return self.to_json()
    
    def to_json(self):
        return json.dumps(self, indent=4)
        