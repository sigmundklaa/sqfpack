
import os
import json
import shutil
from collections import deque

from .modules import Module


class NotAddon(Exception):
    pass


class Context:
    def __init__(self, path):
        self.path = path
        self.subs = []

    def __str__(self):
        return '{}({})'.format(type(self).__name__, str(self.path))

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
                 is_module=True,
                 prefix_tag=''
                 ):

        if is_addon and not is_module:
            raise Exception('An addon can only be a module')

        self.name = name
        self.parent = parent
        self.path = path
        self.is_module = is_module
        self.is_addon = is_addon
        self.prefix_tag = prefix_tag

        if self.is_module:
            self.path = path
            self.module = Module(self.path,
                                 True,
                                 self,
                                 is_addon_module=self.is_addon,
                                 name=self.name)
            self.subs = None
        else:
            super().__init__(path)

            self.module = None

    def __str__(self):
        return '{}({})'.format(type(self).__name__, self.name)

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
    def ctx_prefix_tag(self):
        parent = self.parent
        tag_dq = deque()

        while isinstance(parent, Subcontext):
            if parent.prefix_tag:
                tag_dq.appendleft(parent.prefix_tag)

            parent = parent.parent

        return '_'.join(tag_dq)

    @property
    def ctx_name_pretty(self):
        parent = self.parent
        name_dq = deque()

        while isinstance(parent, Subcontext):
            name_dq.appendleft(parent.name)
            parent = parent.parent

        return '_'.join(name_dq)

    @property
    def addon_filename(self):
        if not self.is_addon:
            raise NotAddon(self)

        return self.name + '.pbo'

    @property
    def addon_prefix(self):
        if not self.is_addon:
            raise NotAddon(self)

        return f'\\{self.name}\\'
