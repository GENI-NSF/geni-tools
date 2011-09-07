------------------------------------------------------------------
Intro:
------------------------------------------------------------------

libstitch is a python module which helps to abstract away the complexities
associated with aggregate stitching for GENI aggregates. libstitch
can be used to facilitate all or a subset of the actions involved with
GENI aggregate stitching.

Some of these involve: 
    -Topology discovery
    -RSpec parsing and interpretation
    -Calculation of dependencies between aggregates
    -Submission of RSpecs to aggregates
    -Generation of setup and login scripts for allocated resources
    -Generation of a graph of allocated resources

The main interface is very high-level, however there are some useful
models and abstractions lower in the stack which are also available
for use.


------------------------------------------------------------------
Changelog:
------------------------------------------------------------------

HEAD:
    -Outlined how to use the library as a python mod in readme
    -Reading topology and adjacency from advertisement rspecs
    -Starting a session no longer uses filehandles, strings instead
    -Parallelize requests by non-dependent RSpecs
    -Output of graphs and scripts are now separate calls

gec-stitching-demo-v1:
    -Base functionality for GEC 11



------------------------------------------------------------------
Requirements:
------------------------------------------------------------------

== Linux ==

-- Omni --
Use Omni 1.3+
 - Install
    put gcf/src from the omni package on your PYTHONPATH
EG
export PYTHONPATH=$PYTHONPATH:~/gcf/src

 - Configure Omni 
    By default, your omni config should be named omni_config 
  in the directory '.gcf'. But this is configurable using the
  '-c' argument.
     - use PLC as your default_cf to work with the MAX and ION AMs
     - Declare a user whose SSH key your config points to
     - See a sample omni_config at the bottom of this file

-- LXML --
Used for parsing XML
- Install
    Ubuntu: suto aptitude install python-lxml

-- Graphviz --
Used for creating graphs (optional)
 - Install
    Ubuntu: sudo aptitude install python-pygraphviz

-- Nose --
Used for the unit tests (optional)
 - Install
    Ubuntu: sudo aptitude install python-nose

-- libstitch --
Add the folder libstitch is in to your PYTHONPATH env variable. 
Note: do not add the libstitch folder itself, but the folder it sits in.
EG
export PYTHONPATH=$PYTHONPATH:~/gcf/examples/stitching


== Windows ==
Unsupported


== Mac ==
Untested


------------------------------------------------------------------
How to use: As a library
------------------------------------------------------------------

Put the libstitch folder somewhere in your PYTHONPATH. EG
export PYTHONPATH=$PYTHONPATH:~/gcf/src:~/gcf/examples/stitching


---- Basic Example ----

import libstitch

rspecs = [open('rspec1.xml'),open('rspec2.xml'),open('rspec3.xml')]
s = libstitch.Stitch('myslicename',rspecs)
s.startSession()
sequence = s.calculateSequence()
assigned_vlans = s.executeSequence(sequence)


---- More Complex Example ----

see: sample.py

This example can be used to do basic stitching work. Make sure you edit
the scripts in the 'templates' directory for your use. 
You can edit the setup template to upload a custom payload of 
whatever you like.


------------------------------------------------------------------
Project Organization:
------------------------------------------------------------------

Python Source:

    sample.py   
        A sample, basic usage of the high-level interface that comes
        with libstitch.

    libstitch/
        Main python module folder for libstitch.

    libstitch/stitch.py   
        The high-level interface if you just want to use what is already
         supported.

    libstitch/src/def.py
        Shared constants used throughout the project, placed here for
        easy inclusion.

    libstitch/src/exception.py
        Any exceptions used are included here.

    libstitch/src/request.py
        Contains the threading class(es) for running requests to aggregates
         in parallel.

    libstitch/src/rspec.py
        Contains models for Request, Manifest and Advert RSpecs
        for several different formats. ReqRSpecs are responsible for
        determining which version their input is in (if known), parsing it,
        manipulating it and writing it out to string for submission to
        an aggregate. ManRSpecs mainly provide information extraction
        functions for sofar unsubmitted ReqRSpecs. AdRSpecs are used
        mainly for topology computation, and are rather sparse.

    libstitch/src/stitchsession.py
        Contains models to represent something called a 'stitch
        session'. Not rigidly defined, a stitchsession is generally
        any operation which involves more than one RSpec object or
        requires some consistent state or context throughout usage of
        the library 

    libstitch/src/util.py
        Contains only functions which have no state. Helper functions
        which do not fit in the context of an instance function.


Tests:
    
    libstitch/tests/test_rspec.py
        Contains tests for libstitch/src/rspec.py
        
    libstitch/tests/test_util.py
        Contains tests for libstitch/src/util.py


Supporting Items:

    libstitch/runTests.sh
        Shell script to find all included tests and run them.

    libstitch/createDocs.sh
        Shell script to generate code documentation based on
        libstitch.py. By default, documentation will be placed in
        libstitch/docs.

    libstitch/libstitch.doxy
        Doxygen config file for libstitch.
                    
    libstitch/cache/
        The folder where topology discovery functions will search for
        advertisement rspecs by default.

    libstitch/samples/
        Sample Request and Manifest RSpec files.

    libstitch/templates/
        Template scripts used to generate login and setup scripts for
        allocated nodes.


------------------------------------------------------------------
Developer Notes:
------------------------------------------------------------------

Overview:

The general description of how this library works is as follows. We
read in rspec files and pass them into new ReqRSpec objects, and
pass those objects into a new Stitch session. After a session has
been 'started' we calculate restrictions. A restriction is just a
key/value pair associated with a ReqRSpec or specific interface in 
that ReqRSpec (aggregate) which can be used later
on to help in dependency calculation, and is essentially any property
which might remotely be involved in relation to other ReqRSpecs. We
use 'vlanTags'='list of vlans' and 'vlanTranslation'='True/False' right
now. Once all restrictions have been derived from the XML, we use them
to compute dependencies. Dependencies are one-way relationships between
ReqRSpecs (aggregates) which describe which of two ReqRSpecs must be
submitted and returned first. Once we have dependencies, we can easily
create a sequence of aggregates in which the ReqRSpecs can be submitted
in order not to violate any of the dependencies we calculated. From here
we simply submit the sequence of ReqRSpecs in order.

Adding support for aggregate negotiation

    First write a new function which deals with the actual negotiation
    procedure between the aggregates, possibly placed in util.py. Such
    a function might take two ReqRSpec objects (likely adjacent to
    each other) and return vlan tags which were decided on. This would
    likely include going off, talking to aggregates and using negotiation
    features (currently unimplemented) and could likely take advantage of
    several tools in util.py for sending rspecs to aggregates. Calling
    of this function would fit best in the ReqRSpec class in rspec.py
    where dependencies between aggregates are computed. This is likely
    the earliest one can do negotiation because there are still many
    unknowns at that point. The exact place to add this functionality
    is likely the end of ReqRSpec.calculateDeps(). 


IonReqRSpec special case

    Ideally, each subclass of ReqRSpec is intended to correspond with
    one supported rspec format, not be aggregate specific. IonReqRSpec
    is an outlier, in that it uses the Max native format and should
    generally be supported by MaxReqRSpec. This is not the case here,
    mainly because the Max native RSpec format does not include any
    information regarding certain properties which we care about such as
    whether vlanTranslation is supported. It is for this reason that Ion
    has its own class, for hardcoded properties we know in advance. It
    is unfortunate and eventually we probably want to merge these two
    classes into one for consistency once the RSpec files contain enough
    information. The 'util.getKnownAggregateData' function has the format
    of the Ion aggregate as 'max', because they should be the same for now.

Adding support for new aggregates and RSpec Formats

    If a new Aggregate is to be supported, we need to modify the
    hard-coded data-structure returned by the getKnownAggregateData()
    function in util.py. Add an entry for the new aggregate into the
    dictionary under the correct format. If the new aggregate has a new
    format, add a new format entry and enter your new aggregate. If
    you had to add a new format, you must build support for it. 
    TODO: Find RSpec format/namespaces and aggregate URL in RSpecs.

    To add support for a new RSpec format, you need to create a
    corresponding ReqRSpec, ManRSpec, and AdRSpec format in rspec.py
    where applicable. You also need to add a new detection case in the
    findRSpecFormat() function in util.py, which is used by the ReqRSpec
    class to determin which subclass is to be used.

    Additionally, make sure the new aggregate's topology information is
    included in an advertisement file in libstitch/cache if not already.

Other design questions:

    - Q: What is the definedVlans struct in an RSpec, and how is it filled?
      A: definedVlans is a dictionary in a ManRSpec object. When a 
        ReqRSpec is submitted and a ManRSpec is collected in response,
        the interface URNs and the Vlan tags assigned to them by the
        aggregate are stripped out of the XML by ManRSpec and put into
        definedVlans for easy access by other objects.
	definedVlans maps the remote interface URN to the VLAN ID
	assigned to the link to that interface.

    - Q: What are presetRoutes, and how are they filled/used?
      A: presetRoutes is a dictionary containing
        [aggregateURL->
            Dictionary[localifaceURN -> remoteifaceURN]] 
        which tells us which local interfaces in an aggregate are 
        connected to which remote interfaces
        of other aggregates, according to the aggregate advertisements. 
        This is all stripped out of the ad rspecs
        by the topology discovery function in util.py

    - Q: What are adjacentAggregates? Is that specific to a particular
         experimental topology, or about physical interconnections?
      A: adjacentAggregates is a dictionary of 
        [aggregateURL->List[aggregateURL,aggregateURL,...] which is just
        a simpler description of physically connected aggregates
        to make computation a bit easier. 
        ['agg1']->['agg2','agg3'] just means that agg1 is connected to
        both agg2 and agg3
	This mapping is computed from the advertisement RSpecs, and
	defines 2 aggregates as adjacent if they both define a link
	that connects them.

    - Q: The cache folder: what goes in there, and how is it used?
         How could we replace that folder with a service?
      A: The cache folder is intended to be full of advertisement rspecs
        currently. The original idea was that you could have a cronjob
        refreshing adverts, people manually do it, or the code grab 
        them if the cache folder is empty. 
        Replacing this is just a matter of re-implementing the 
        util.getTopologyData() function.
        

------------------------------------------------------------------
Future Work:
------------------------------------------------------------------

    - Represent a 'switch'. Which can itself have properties
    - Derive aggregate namespaces, URL from RSpecs
    - Support a service for getting topology information
    - Support VLAN tag negotiation
    - Implement insertVlanData in PGReqRSpec
    - Make IONRSpecs inherit from MAX versions for code re-use


------------------------------------------------------------------
Current Caveats
------------------------------------------------------------------

- Request RSpecs must have an XML comment of a particular form
that includes the aggregate URL for us to ID the aggregate. See the
examples. Obviously there are better ways to do this.  


------------------------------------------------------------------
Source Documentation:
------------------------------------------------------------------

Documentation in the form of HTML, PDF or Manpages that can be generated with
doxygen.

The included script does this for you:
 $ cd libstitch
 $ ./createDocs.sh


------------------------------------------------------------------
Tests:
------------------------------------------------------------------

To run the included unit tests:
 $ cd libstitch
 $ ./runTests.sh


------------------------------------------------------------------
Sample omni_config:
------------------------------------------------------------------

[omni]
default_cf = my_sfa

users = Aaron

aggregates =    http://www.emulab.net/protogeni/xmlrpc/am, 
                http://alpha.east.isi.edu:12346, 
                http://max-myplc.dragon.maxgigapop.net:12346

# ==================================
# Configure Control Frameworks here

[my_sfa]
type=sfa
authority=plc.bbn
user=plc.bbn.ahelsing
cert=~/.gcf/plc-ahelsing-cert-enc.pem
key=~/.gcf/plc-ahelsing-cert-dec.pem
registry=http://www.planet-lab.org:12345
slicemgr=http://www.planet-lab.org:12347

# ===================================
# Define users here.

[Aaron]
urn=urn:publicid:IDN+plc:bbn+user+ahelsing
keys=~/.ssh/id_rsa_geni.pub

