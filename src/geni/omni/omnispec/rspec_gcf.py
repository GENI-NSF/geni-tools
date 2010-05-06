from geni.omni.omnispec.omnispec import OmniSpec, OmniResource
import xml.etree.ElementTree as ET


def can_translate(urn, rspec):
    if urn.split('+')[1].lower().startswith('gcf'):
        return True
    return False



def rspec_to_omnispec(urn, rspec):
    ospec = OmniSpec("rspec_gcf", urn)
    doc = ET.fromstring(rspec)
    
    for res in doc.findall('resource'):        
        type = res.find('type').text
        id = res.find('id').text
        available = res.find('')
        
        r = OmniResource(id, 'node ' + id, type)
        
        if available:
            r.set_allocated(False)
            
        spl = urn.split('+')
        spl[1] += ':' + spl[-1]
        spl[-2] = 'node'
        spl[-1] = id
            
        rurn = '+'.join(spl)
        
        ospec.add_resource(rurn, r)
        
    return ospec

def omnispec_to_rspec(omnispec, filter_allocated):
    # Convert it to XML
    root = ET.Element('rspec')
    for _, r in omnispec.get_resources().items():
        if filter_allocated and not r.get_allocate():
            continue
        
        res = ET.SubElement(root, 'resource')
        ET.SubElement(res, 'type').text = r.get_type()
        ET.SubElement(res, 'id').text = r.get_name()
        ET.SubElement(res, 'available').text = str(not r.get_allocated())

    return ET.tostring(root)
    