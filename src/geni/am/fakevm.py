
import uuid
from resource import Resource

class FakeVM(Resource):
    def __init__(self):
        super(FakeVM, self).__init__(str(uuid.uuid4()), "fakevm")
