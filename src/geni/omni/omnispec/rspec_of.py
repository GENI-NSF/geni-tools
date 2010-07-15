# Copyright (c) 2008 The Board of Trustees of The Leland Stanford
# Junior University
# 
# We are making the OpenFlow specification and associated documentation
# (Software) available for public use and benefit with the expectation
# that others will use, modify and enhance the Software and contribute
# those enhancements back to the community. However, since we would
# like to make the Software available for broadest use, with as few
# restrictions as possible permission is hereby granted, free of
# charge, to any person obtaining a copy of this Software to deal in
# the Software under the copyrights without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
# 
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT.  IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
# 
# The name and trademarks of copyright holder(s) may NOT be used in
# advertising or publicity pertaining to the Software or any
# derivatives without specific, written prior permission.

from geni.omni.omnispec.omnispec import OmniSpec, OmniResource
import xml.etree.ElementTree as ET

def can_translate(urn, rspec):
    if urn.split('+')[1].lower().startswith('openflow'):
        return True
    return False


def rspec_to_omnispec(urn, rspec):
    ospec = OmniSpec("rspec_of", urn)
    ospec = make_skeleton_of_ospec(ospec)
    doc = ET.fromstring(rspec)
    for network in doc.findall('network'):             
        net_name = network.get('name')
        switches = network.findall('switches')[0]
        for switch in switches.findall('switch'):
            # convert:
            #       "<switch urn="urn:publicid:IDN+openflow:stanford+switch:0" />"
            urn = switch.get('urn')
            # switchname = "stanford_network:switch:00:00:00:23:01:35:a5:5d"
            switchname = net_name + ':' + urn.split('+')[1]
            s = OmniResource(switchname, "OpenFlow Switch" ,'switch') 

            s['options']['flowspace'] = 'nw_src=128.8.0.0/16-*,tp_dst=80-85'      
            ospec.add_resource(urn, s)
        for link in network.findall('link'):
            # convert:
            #       <link
            #       src_urn="urn:publicid:IDN+openflow:stanford+switch:0+port:0
            #       dst_urn="urn:publicid:IDN+openflow:stanford+switch:1+port:0
            #       />
            _,domain,src_switch,src_port = link.get('src_urn').split('+')
            _,_,dst_switch,dst_port = link.get('dst_urn').split('+')
            urn = "urn:publicid:IDN+%s+%s+%s+%s+%s" % ( domain, 
                                                        src_switch, src_port,
                                                        dst_switch, dst_port)
            link_name = "%s %s --> %s %s" % ( src_switch, src_port,
                                                        dst_switch, dst_port )
            r = OmniResource(link_name, link_name, 'link') 
            ospec.add_resource(urn, r)
    return ospec

def omnispec_to_rspec(omnispec, filter_allocated):
    # Load up information about all the resources
    user = {}
    project = {}
    slice = {}
    flowspaces = {}
    
    for urn, r in omnispec.get_resources().items():
        if '+user+sliceinfo' in urn:            
            user['firstname'] = r['options']['firstname']
            user['lastname'] = r['options']['lastname']
            user['email'] = r['options']['email']
            user['fv_password'] = r['options']['fv_password']
            
            project['project_name'] = r['options']['project_name']
            project['project_description'] = r['options']['project_description']
            
            slice['slice_name'] = r['options']['slice_name']
            slice['slice_description'] = r['options']['slice_description']
            slice['controller_url'] = r['options']['controller_url']
        if '+switch' in urn:
            if not r.get_allocate():
                continue       
            # Okay, consider this switch part of a flowspace
            flowspace = {}
            flowspace['switch'] = urn
            flowspace['options'] = []
            for opt in r['options']['flowspace'].split(','):
                name,val = opt.split('=')
                spl = val.split('-')
                vto = '*'
                vfrom = spl[0]
                if len(spl) > 1:
                    vto = spl[1]

                flowspace['options'].append((name,vfrom,vto))

            flowspaces[urn] = flowspace
            
            
            
    # Now build the rspec
     
    root = ET.Element('resv_rspec')
    ET.SubElement(root, 'user', firstname=user['firstname'],lastname=user['lastname'], \
                           email=user['email'], fv_password=user['fv_password'])
    ET.SubElement(root, 'project', project_name=project['project_name'], \
                              project_description=project['project_description'])
    ET.SubElement(root, 'slice', slice_name=slice['slice_name'],\
                            slice_description=slice['slice_description'],\
                            controller_url=slice['controller_url'])
    
    for (urn,flowspace) in flowspaces.items():
        flow = ET.SubElement(root, 'flowspace')
        switches = ET.SubElement(flow, 'switches')
        ET.SubElement(switches, 'switch', urn=urn)
        for (name,vfrom,vto) in flowspace['options']:
            opt = ET.SubElement(flow, name)
            opt.attrib['from'] = vfrom
            opt.attrib['to'] = vto
            
    return ET.tostring(root)

def make_skeleton_of_ospec(ospec):
    ''' Add resources for the client to reserve.

        Hacking it in here because Expedient assumes the caller will add them
        themselves.
    '''
    # setup a resource for fv_account
    user = OmniResource("sliceinfo","Slice information for FlowVisor Access",'user')
    # goes in <user>
    user['options']['firstname'] = 'John'
    user['options']['lastname'] = 'Doe'
    user['options']['email'] = 'jdoe@geni.net'
    user['options']['fv_password'] = 'slice_pass'
    # goes in <project>
    user['options']['project_name'] = 'Stanford Networking Group'
    user['options']['project_description'] = 'Internet performance research to ...'
    # goes in <slice>
    user['options']['slice_name'] = 'Crazy Load Balancing Experiment'
    user['options']['slice_description'] = 'Does crazy load balancing and plate spinning'
    user['options']['controller_url'] = 'tcp:localhost:6633'
    user_urn = 'urn:publicid:IDN+openflow:stanford+user+' + user.get_name()

    ospec.add_resource(user_urn, user)
    return ospec

    

##### Example OpenFlow rspec from expedient
'''
<rspec>
    <network name="Stanford" location="Stanford, CA, USA">
        <switches>
            <switch urn="urn:publicid:IDN+openflow:stanford+switch:0" />
            <switch urn="urn:publicid:IDN+openflow:stanford+switch:1" />
            <switch urn="urn:publicid:IDN+openflow:stanford+switch:2" />
        </switches>
        <links>
            <link
            src_urn="urn:publicid:IDN+openflow:stanford+switch:0+port:0
            dst_urn="urn:publicid:IDN+openflow:stanford+switch:1+port:0
            />
            <link
            src_urn="urn:publicid:IDN+openflow:stanford+switch:1+port:0
            dst_urn="urn:publicid:IDN+openflow:stanford+switch:0+port:0
            />
            <link
            src_urn="urn:publicid:IDN+openflow:stanford+switch:0+port:1
            dst_urn="urn:publicid:IDN+openflow:stanford+switch:2+port:0
            />
            <link
            src_urn="urn:publicid:IDN+openflow:stanford+switch:2+port:0
            dst_urn="urn:publicid:IDN+openflow:stanford+switch:0+port:1
            />
            <link
            src_urn="urn:publicid:IDN+openflow:stanford+switch:1+port:1
            dst_urn="urn:publicid:IDN+openflow:stanford+switch:2+port:1
            />
            <link
            src_urn="urn:publicid:IDN+openflow:stanford+switch:2+port:1
            dst_urn="urn:publicid:IDN+openflow:stanford+switch:1+port:1
            />
            </links>
            </network>
            <network name="Princeton" location="USA">
            <switches>
            <switch urn="urn:publicid:IDN+openflow:stanford+switch:3" />
            <switch urn="urn:publicid:IDN+openflow:stanford+switch:4" />
            </switches>
            <links>
            <link
            src_urn="urn:publicid:IDN+openflow:stanford+switch:3+port:0
            dst_urn="urn:publicid:IDN+openflow:stanford+switch:4+port:0
            />
            <link
            src_urn="urn:publicid:IDN+openflow:stanford+switch:4+port:0
            dst_urn="urn:publicid:IDN+openflow:stanford+switch:3+port:0
            />
        </links>
    </network>
</rspec>

specifies a triangular graph at the Stanford network and a single link
at the Princeton network
'''


##### Example reservation back to OpenFlow/Expedient
'''
    Parses the reservation RSpec and returns a tuple:
    (project_name, project_desc, slice_name, slice_desc, 
    controller_url, email, password, agg_slivers) where slivers
    is a list of (aggregate, slivers) tuples, and slivers is a dict suitable
    for use in the create_slice xml-rpc call of the opt-in manager.
    
    The reservation rspec looks like the following:
    
    <resv_rspec>
        <user
            firstname="John"
            lastname="Doe"
            email="john.doe@geni.net"
            password="slice_pass"
        />
        <project
            name="Stanford Networking Group"
            description="Internet performance research to ..."
        />
        <slice
            name="Crazy Load Balancer"
            description="Does this and that..."
            controller_url="tcp:controller.stanford.edu:6633"
        />
        <flowspace>
            <switches>
                <switch urn="urn:publicid:IDN+openflow:stanford+switch:0">
                <switch urn="urn:publicid:IDN+openflow:stanford+switch:2">
            </switches>
            <port from="1" to="4" />
            <dl_src from="22:33:44:55:66:77" to="22:33:44:55:66:77" />
            <dl_dst from="*" to="*" />
            <dl_type from="0x800" to="0x800" />
            <vlan_id from="15" to="20" />
            <nw_src from="192.168.3.0" to="192.168.3.255" />
            <nw_dst from="192.168.3.0" to="192.168.3.255" />
            <nw_proto from="17" to="17" />
            <tp_src from="100" to="100" />
            <tp_dst from="100" to="*" />
        </flowspace>
        <flowspace>
            <switches>
                <switch urn="urn:publicid:IDN+openflow:stanford+switch:1">
            </switches>
            <tp_src from="100" to="100" />
            <tp_dst from="100" to="*" />
        </flowspace>
    </resv_rspec>
    
    Any missing fields from the flowspace mean wildcard. All '*' means any
    value.
    
    All integers can by specified as hex or decimal.
    '''
