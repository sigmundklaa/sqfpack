
import os
import json
import shutil

from .modules import Module


class Context:
    def __init__(self, path):
        self.path = path
        self.subs = []

    def add_sub(self, *args, **kwargs):
        kwargs['parent'] = self

        sub = Subcontext(*args, **kwargs)
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
            i.export(outpath)


class Subcontext(Context):
    def __init__(self,
                 name,
                 path,
                 parent=None,
                 is_addon=False,
                 is_module=True
                 ):

        if is_addon and not is_module:
            raise Exception('An addon can only be a module')

        self.name = name
        self.parent = parent
        self.path = path
        self.is_module = is_module

        if self.is_module:
            self.path = path
            self.module = Module(self.path, True, self, config={
                'CfgPatches': {
                    self.name: {
                        'fileName': self.name + '.pbo'
                    }
                }
            })
            self.subs = None
        else:
            super().__init__(path)

            self.module = None

        self.is_addon = is_addon

    def resolve(self, path):
        if not isinstance(self.parent, Subcontext):
            if path.startswith('/'):
                path = path.lstrip('/')
            else:
                return super().resolve(path)

        return self.parent.resolve(path)

    def export(self, basepath):
        if self.is_module:
            config, functions = self.module.export(basepath, None)

            with (
                open(self.module.construct_path(basepath).joinpath(
                    'config.json'), 'w')) as wp:

                json.dump({
                    'config': config,
                    'functions': functions
                }, wp, indent=4)

        else:
            basepath = basepath.joinpath(self.name)

            if not basepath.exists():
                os.mkdir(basepath)

            for s in self.subs:
                s.export(basepath)

    @property
    def addon_prefix(self):
        if not self.is_addon:
            raise Exception('{} not an addon'.format(str(self)))

        return f'\\{self.name}\\'
