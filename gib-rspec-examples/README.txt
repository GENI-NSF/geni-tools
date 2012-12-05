This file outlines the various example RSpec files available with
geni-in-a box. It includes the basic layout for each RSpec as well as
its purpose.

All containers that are generated are dependent on the host OS despite the
node type that is specified in the example RSpec, i.e. an Ubuntu host machine
will create Ubuntu containers, a Fedora host will create Fedora containers.


1. two-nodes-iperf.rspec

    Description:
        This is used to demonstrate setting up two nodes
        that are connected by a single LAN connection.  The rspec
        asks the aggregate manager to download and install a script
        on both nodes and execute this script.
        The script installs iperf on both nodes and starts iperf as a client
        on node left and server on node right.  The output of iperf are logged
        so the experimenter and ssh into the nodes and view the output.
        
    Nodes:
        1. right
        2. left
        
    Links:
        1. left-right-lan
            This is the LAN connecting the two nodes marked "left" and "right".

    ASCII topology:

        left---left-right-lan---right




2. three-nodes-lan.rspec

    Description:
        This demonstrates setting up three nodes that are all connected
        to a single LAN, but are not directly connected to each other individually.
        
    Nodes:
        1. left    
        2. middle
        3. right
        
    Links:
        1. lan0
            This is the LAN connecting the three nodes.

    ASCII topology:

              lan0
              /| \
             / |  \
            /  |   \
           /   |    \
          /    |     \
         /     |      \
       left  middle  right




3. four-nodes-lan.rspec

    Description:
        This demonstrates setting up four nodes that form a diamond shaped connection.
        
    Nodes:
        1. left    
        2. right
        3. top
        4. bottom
        
    Links:
        1. left-right-lan
        2. left-to-bottom-if
        3. right-to-bottom-if
        4. top-to-left
        5. top-to-right

    ASCII topology:

              top
              /  \
            L4    L5
            /      \
         left--L1--right
            \      /
            L2    L3
              \  /
             bottom

        where L1-L5 are the links defined above.




4. install-example.rspec

    Description:
        This demonstrates setting up two nodes that install shell
        scripts and then executes them on the containers.
        
    Nodes:
        1. left
            Installs a shell script different from node "right" that echos text once executed.
            
        2. right
            Installs a shell script different from node "left" that echos text once executed.
        
    Links:
        1. left-right-lan

    ASCII topology:

         left---left-right-lan---right




5. islands.rspec

    Description:
        This demonstrates setting up two nodes that have no LAN connections,
        and two other nodes that are connected by a single LAN.
        
    Nodes:
        1. island1
        2. island2
        3. connected1
        4. connected2
        
    Links:
        1. lan0

    ASCII topology:

         island1        island2
         
         connected1---lan0---connected2










