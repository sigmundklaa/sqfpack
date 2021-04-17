
import os
import json
import shutil
from collections import deque

from .modules import Module


class NotAddon(Exception):
    pass


class Context:
    def __init__(self, path, prefix_tag=''):
        self.path = path
        self.subs = []
        self.prefix_tag = prefix_tag

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
                 path,
                 parent=None,
                 is_addon=False,
                 is_module=True,
                 prefix_tag=''
                 ):

        if is_addon and not is_module:
            raise Exception('An addon can only be a module')

        self.parent = parent
        self.path = path
        self.is_module = is_module
        self.is_addon = is_addon

        if self.is_module:
            self.prefix_tag = prefix_tag
            self.path = path
            self.name = None
            self.source_name = None
            self.module = Module(self.path,
                                 True,
                                 self,
                                 is_addon_module=self.is_addon)
            self.subs = None
        else:
            super().__init__(path, prefix_tag)

            self.module = None
            self.name = self.path.name
            self.source_name = self.name

    def set_names(self, *args):
        self.name, self.source_name = args

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
        ctx = self
        tag_dq = deque()

        while isinstance(ctx, Context):
            if ctx.prefix_tag:
                tag_dq.appendleft(ctx.prefix_tag)

            ctx = getattr(ctx, 'parent', None)

        return '_'.join(tag_dq)

    @property
    def ctx_name_pretty(self):
        parent = self.parent
        name_dq = deque()

        while isinstance(parent, Subcontext):
            try:
                name_dq.appendleft(parent.source_name)
            except AttributeError:
                pass
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
