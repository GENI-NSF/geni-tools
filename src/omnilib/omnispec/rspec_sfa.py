#----------------------------------------------------------------------
# Copyright (c) 2010 Raytheon BBN Technologies
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
from omnilib.omnispec.omnispec import OmniSpec, OmniResource
import xml.etree.ElementTree as ET


def can_translate(rspec):
    return '<RSpec ' in rspec and ' type="SFA"' in rspec

def rspec_to_omnispec(urn, rspec):
    # URN is that of the AM
    ospec = OmniSpec("rspec_sfa", urn)
    doc = ET.fromstring(rspec)
    for network in doc.findall('network'):
        if network.find('site'):
            for site in network.findall('site'):
                for node in site.findall('node'):
                    
                    net_name = network.get('name')
                    site_id = site.get('id')
                    site_name = site.find('name').text
                    hostname = node.find('hostname').text.strip()

                    r = OmniResource(hostname, '%s %s %s' % (net_name, site_id, hostname), 'vm')
                    urn = 'urn:publicid:IDN+%s:%s+node+%s' % (net_name.replace('.', ":"), site_name, hostname.split('.')[0])
                    misc = r['misc']

                    misc['site_id'] = site_id
                    misc['site_name'] = site_name
                    misc['hostname'] = hostname
                    misc['net_name'] = net_name
                    misc['node_id'] = node.get('id')

                    for child in list(node):
                        if child.tag == 'location':
                            misc['location'] = "%s Lat, %s Long" % (child.get('latitude'), child.get('longitude'))
                        elif child.tag == 'bw_limit':
                            misc['bw_limit'] = child.text.strip() + child.get('units')
                        elif child.tag == 'bw_unallocated':
                            misc['bw_unallocated'] = child.text.strip() + child.get('units')
                        else:
                            val = child.get('value')
                            val2 = child.text
                            value = ""
                            if val is not None:
                                value = val
                            if val2 is not None:
                                value += val2.strip()
                            misc[child.tag] = value
                
                    if not node.find('sliver') is None:
                        r.set_allocated(True)

                    ospec.add_resource(urn, r)
                #for link in network.findall('link'):
                    # endpoints="princeton i2newy"
                    #<description>sdfasfd</description>
                    #<bw_unallocated units="kbps">#</sdf>
        else:
#        for site in network.findall('site'):
            for node in network.findall('node'):
                
                net_name = network.get('name')
                site_id = node.get('site_id')
#                site_name = site.find('name').text
                hostname = node.find('hostname').text.strip()
                    
                r = OmniResource(hostname, '%s %s %s' % (net_name, site_id, hostname), 'vm')
                comp_id = node.get('component_id')
                comp_mgr_id = node.get('component_manager_id')
#                urn = 'urn:publicid:IDN+%s:%s+node+%s' % (net_name.replace('.', ":"), site_name, hostname.split('.')[0])
                urn = comp_id
                misc = r['misc']
                misc['component_manager_id'] = comp_mgr_id
                misc['site_id'] = site_id
#                misc['site_name'] = site_name
                misc['hostname'] = hostname
                misc['net_name'] = net_name
                misc['node_id'] = node.get('node_id')

                for child in list(node):
                    if child.tag == 'location':
                        misc['location'] = "%s Lat, %s Long" % (child.get('latitude'), child.get('longitude'))
                    elif child.tag == 'bw_limit':
                        misc['bw_limit'] = child.text.strip() + child.get('units')
                    elif child.tag == 'bw_unallocated':
                        misc['bw_unallocated'] = child.text.strip() + child.get('units')
                    else:
                        val = child.get('value')
                        val2 = child.text
                        value = ""
                        if val is not None:
                            value = val
                        if val2 is not None:
                            value += val2.strip()
                        misc[child.tag] = value
                
                if not node.find('sliver') is None:
                    r.set_allocated(True)

                ospec.add_resource(urn, r)

    return ospec

def omnispec_to_rspec(omnispec, filter_allocated):
    useSites = False

    # Load up information about all the resources
    networks = {}    
    for urn, r in omnispec.get_resources().items():
        if filter_allocated and not r.get_allocate():
            continue
        net = networks.setdefault(r['misc']['net_name'], {})
        if r['misc'].has_key('site_name'):
            useSites = True
            site = net.setdefault(r['misc']['site_id'], {})
            node = site.setdefault(r['misc']['node_id'], {})
            node['site_name'] = r['misc']['site_name']
        else:
            node = net.setdefault(r['misc']['node_id'], {})
            node['site_id'] = r['misc']['site_id']
            node['component_id'] = urn
            node['component_manager_id'] = r['misc']['component_manager_id']
            node['node_id'] = r['misc']['node_id']
            # location, arch, fcdistro, bw_limit, bw_unallocated...
        node['hostname'] = r['misc']['hostname']
        node['allocate'] = r.get_allocate()

    # Convert it to XML
    root = ET.Element('RSpec')
    root.set('type', 'SFA')
    
    for net_name, sites in networks.items():
        xnet = ET.SubElement(root, 'network', name=net_name)
        
        if useSites:
            for site_id, nodes in sites.items():
                xsite = ET.SubElement(xnet, 'site', id=site_id)

                ET.SubElement(xsite, 'name').text = node['site_name']

                for node_id, node in nodes.items():
                    xnode = ET.SubElement(xsite, 'node', id = node_id)
                    ET.SubElement(xnode, 'hostname').text = node['hostname']
                    if node['allocate']:
                        ET.SubElement(xnode,'sliver')
        else:
            nodes = sites
            for node_id, node in nodes.items():
                xnode = ET.SubElement(xnet, 'node', node_id=node_id, site_id=node['site_id'], component_id=node['component_id'], component_manager_id=node['component_manager_id'])
                ET.SubElement(xnode, 'hostname').text = node['hostname']
                # location, arch, fcdistro, bw_limit, bw_unallocated...
                if node['allocate']:
                    ET.SubElement(xnode,'sliver')

    return ET.tostring(root)
