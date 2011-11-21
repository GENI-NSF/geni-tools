from resource import Resource

class Aggregate(object):

    def __init__(self):
        self.resources = []
        self.containers = {}

    def add_resources(self, resources):
        self.resources.extend(resources)

    def catalog(self, container=None):
        if container:
            if container in self.containers:
                return self.containers[container]
            else:
                return []
        else:
            return self.resources

    def allocate(self, container, resources):
        if container not in self.containers:
            self.containers[container] = []
        for r in resources:
            if r.available:
                self.containers[container].append(r)
                r.available = False

    def deallocate(self, container, resources):
        if container and resources:
            # deallocate the given resources from the container
            pass
        elif container:
            # deallocate all the resources in the container
            pass
        elif resources:
            # deallocate the resources from their container
            pass
        # Finally, check if container is empty. If so, delete it.

    def stop(self, container):
        # Mark the resources as 'SHUTDOWN'
        if container in self.containers:
            for r in self.containers[container]:
                r.status = Resource.STATUS_SHUTDOWN
