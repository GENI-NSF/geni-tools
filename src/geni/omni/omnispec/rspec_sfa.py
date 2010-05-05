from geni.omni.omnispec.omnispec import OmniSpec, OmniResource
import xml.etree.ElementTree as ET


def can_translate(urn, rspec):
    if urn.split('+')[1].lower() == 'plc':
        return True
    return False


def rspec_to_omnispec(urn, rspec):
    ospec = OmniSpec("rspec_sfa", urn)
    doc = ET.fromstring(rspec)
    for network in doc.findall('network'):
        for site in network.findall('site'):
            for node in site.findall('node'):
                
                net_name = network.get('name')
                site_id = site.get('id')
                site_name = site.find('name').text
                hostname = node.find('hostname').text
                    
                r = OmniResource(hostname, '%s %s %s' % (net_name, site_id, hostname), 'vm')
                urn = 'urn:publicid:IDN+%s:%s+node+%s' % (net_name.replace('.', ":"), site_name, hostname.split('.')[0])
                misc = r['misc']
                
                misc['site_id'] = site_id
                misc['site_name'] = site_name
                misc['hostname'] = hostname
                misc['net_name'] = net_name
                misc['node_id'] = node.get('id')
                
                if not node.find('sliver') is None:
                    r.set_allocated(True)

                ospec.add_resource(urn, r)
    return ospec

def omnispec_to_rspec(omnispec):

    # Load up information about all the resources
    networks = {}    
    for _, r in omnispec.get_resources().items():
        net = networks.setdefault(r['misc']['net_name'], {})
        site = net.setdefault(r['misc']['site_id'], {})
        node = site.setdefault(r['misc']['node_id'], {})
        node['site_name'] = r['misc']['site_name']
        node['hostname'] = r['misc']['hostname']
        node['allocate'] = r.allocate()

    # Convert it to XML
    root = ET.Element('RSpec')
    root.set('type', 'SFA')
    
    for net_name, sites in networks.items():
        xnet = ET.SubElement(root, 'network', name=net_name)
        
        for site_id, nodes in sites.items():
            xsite = ET.SubElement(xnet, 'site', id=site_id)

            for node_id, node in nodes.items():
                ET.SubElement(xsite, 'name').text = node['site_name']
                xnode = ET.SubElement(xsite, 'node', id = node_id)
                ET.SubElement(xnode, 'hostname').text = node['hostname']
                if node['allocate']:
                    ET.SubElement(xnode,'sliver')
    return ET.tostring(root)