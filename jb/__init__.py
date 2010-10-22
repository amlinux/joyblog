from mg import *

class Blog(Module):
    def register(self):
        Module.register(self)
        self.rhook("ext-index.index", self.index)

    def index(self):
        self.call("web.response", "It worked.", {})
