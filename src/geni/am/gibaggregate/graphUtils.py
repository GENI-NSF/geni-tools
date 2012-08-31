
class GraphNode(object) :
    """ This is the base class for all the objects that correspond to 
        nodes in a graph that correspond to the experimenter specified
        topology.  Examples of these objects include VMNodes (hosts),
        NICs and links.

        This commmon base class allows the functions in the graphUtils
        module to handle all these objects in a uniform manner.
    """
    def getNeighbors(self) :
        pass

    def getNodeName(self) :
        pass


def findShortestPath(startNode, endNode, pathSoFar =[]) :
    """ Find the shortest path between the specified GraphNode objects 
        that form the nodes of a graph.
    """
    # Add this node to the path explored so far
    pathSoFar = pathSoFar + [startNode]

    if startNode == endNode :
        # Found path to the endNode!
        return pathSoFar

    # Path from here to the endNode.  We currently don't have such a path
    pathFromHere =  None

    # See if we can get to the endNode through one of our neighbors
    neighbors = startNode.getNeighbors() 
    for i in range(len(neighbors)) :
        if neighbors[i] not in pathSoFar :
            pathThruNeighbor = findShortestPath(neighbors[i], endNode, \
                                                    pathSoFar)
            if pathThruNeighbor != None :
                if (pathFromHere == None) or (len(pathThruNeighbor) < \
                                                  len(pathFromHere)) :
                    # Found a new or shorter path to the endNode 
                    pathFromHere = pathThruNeighbor

    return pathFromHere
