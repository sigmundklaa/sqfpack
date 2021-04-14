
import os
import shutil
from pathlib import Path
from .modules import Module

class Context:
    def __init__(self, path):
        self.path = path
        self.subs = []

    def add_sub(self, path):
        sub = Subcontext(path, self)
        self.subs.append(sub)

        return sub

    def resolve(self, path):
        # This will raise an error if the module has not yet been initialized
        return Module(self.path.joinpath(path).absolute())

    def export(self, outpath):
        if outpath.exists():
            shutil.rmtree(outpath)

        os.mkdir(outpath)

        for i in self.subs:
            module = i.module
            dir_ = outpath.joinpath(module.name)

            config, functions = module.export(dir_)

            print(config, functions)

class Subcontext(Context):
    def __init__(self, path, parent):
        super().__init__(path)
        self.parent = parent
        self.module = Module(path.absolute(), True, self)

    def resolve(self, path):
        if path.startswith('/'):
            return self.parent.resolve(path.lstrip('/'))
        else:
            return super().resolve(path)
