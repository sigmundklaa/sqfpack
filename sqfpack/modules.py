
import os
import json
import glob
import shutil
from pathlib import Path
from collections import deque, OrderedDict

import aewl

from .utils import prep_path, dictmerge

MANIFEST = 'manifest.json'

BASE_MACROS = OrderedDict(
    q={
        'repl': '#ARG_1',
        'argc': 1
    },
    __rest_args={
        'repl': (
            'private ARG_1 = ARG_2 select [##ARG_3##, ((count ARG_2##) - 1)]'),
        'argc': 3
    },
    var={
        'repl': '__TAG##_##ARG_1',
        'argc': 1
    },
    qvar={
        'repl': '#var(ARG_1)',
        'argc': 1
    },
    xvar={
        'repl': 'ARG_1##_##ARG_2',
        'argc': 2
    },
    qxvar={
        'repl': '#xvar(ARG_1,ARG_2)',
        'argc': 2
    },
    __config={
        'repl': 'qxvar(ARG_1,cfg)',
        'argc': 1
    }
)

BASE_FILE_EXT = set({'.sqf', '.h', '.hpp', '.sqm'})


class Macrofile:
    def __init__(self, macros, module, pre=None):
        self.macros = OrderedDict()
        self.module = module
        self.exported_to = None

        if pre is None:
            pre = {}

        macros = {**pre, **BASE_MACROS, **macros}

        for k, v in macros.items():
            if isinstance(v, dict):
                self.add_macro(v.get('name', k), **v)
            else:
                self.add_macro(k, v)

    def __bool__(self):
        return self.macros is not {}

    def encode_macro(self, macro):
        name = macro['name']
        args = '({})'.format(
            ','.join(macro['args'])) if macro['args'] else ''

        value = ' ' + macro['text']

        return ('#define {name}{args}{value}\n'.format(
            name=name,
            args=args,
            value=value
        ))

    def add_macro(self, name, repl='', argc=0):
        macro = {
            'name': name,
            'text': repl,
            'args': ['ARG_' + str(idx + 1) for idx in range(argc)]
        }
        self.macros[name] = macro

        return macro

    @property
    def filename(self):
        return self.module.source_name + '.incl.h'

    def construct_path(self, base):
        return base.joinpath(self.filename)

    def export(self, outpath):
        filepath = self.construct_path(outpath)
        with open(filepath, 'w') as fp:
            for i in self.macros.values():
                fp.write(self.encode_macro(i))

        self.exported_to = filepath

        return filepath


class ModuleFactory(type):
    _instances = {}

    def __call__(cls, path, initialize=False, *args, **kwargs):
        try:
            inst = cls._instances[path]
        except KeyError:
            inst = Module.__new__(Module)
            inst.__init__(path, initialize, *args, **kwargs)
            cls._instances[path] = inst

            return inst
        else:
            if initialize:
                inst.initialize(*args, **kwargs)

            return inst


class Module(metaclass=ModuleFactory):
    def __init__(self, path: Path, initialize, *args, **kwargs):
        self.path = path
        self.initalized = False

        if initialize:
            self.initialize(*args, **kwargs)

    def initialize(self, ctx, **kwargs):
        if self.initalized:
            return

        self.ctx = ctx
        self.entries = set()
        self.modules = []
        self.parent = kwargs.get('parent', None)
        self.is_addon_module = kwargs.get('is_addon_module', False)
        self.source_name = self.path.name

        manifest = self.path.joinpath(MANIFEST)

        if manifest.exists():
            with open(manifest) as fp:
                kwargs = {**kwargs, **json.load(fp)}

        self.name = kwargs.get('name', self.source_name)

        if self.parent is None:
            self.ctx.set_names(self.name, self.source_name)

        self.partial_tag = kwargs.get('tag')
        self._include = set(kwargs.get('include', []))

        self._include.add(os.path.relpath(self.path, self.ctx.path))

        self.preInit = kwargs.get('preInit', [])
        self.postInit = kwargs.get('postInit', [])
        self.attributes = kwargs.get('attributes', {})
        self.config = kwargs.get('config', {})
        self._full_config = {
            self.prefix_tag + '_cfg': self.config,
            **self.attributes
        }

        macros = OrderedDict(kwargs.get('macros', {}).items())

        self.macrof = Macrofile(macros, self, pre={
            '__TAG': self.prefix_tag
        })
        self.file_exts = BASE_FILE_EXT.union(kwargs.get('filetypes', set()))

        if self.ctx.is_addon:
            if self.is_addon_module:
                # Maybe move to @property with is_Addon check
                self.addon_details = kwargs.get('addon_details', {})
                self._full_config['CfgPatches'] = {
                    self.name: self.addon_details
                }

                self.addon_details.setdefault(
                    'filename', self.ctx.addon_filename)
            else:
                self.addon_details = self.parent.addon_details
        else:
            self.addon_details = None

        self.initalized = True
        self.functions = {}

        self._add_all_entries()

    def __str__(self):
        return '{}({})'.format(type(self).__name__, str(self.path))

    def add_function(self, path):
        name = path.stem
        if name.startswith('_'):
            return

        self.functions[name] = {}

        for i in ('preInit', 'postInit'):
            if name in getattr(self, i, []):
                self.functions[name][i] = True

        return self.functions[name]

    def add_entry(self, entry: Path):
        self.entries.add(entry.absolute())

    def add_module(self, path: Path, **kwargs):
        module = Module(path.absolute(), True, self.ctx, parent=self, **kwargs)
        self.modules.append(module)

        return module

    def load_functions(self):
        for f in self.entries:
            if f.suffix == '.sqf':
                self.add_function(f)

        return self.functions

    def load_includes(self):
        for i in self._include:
            for g in glob.glob(str(self.ctx.resolve_path(i)), recursive=True):
                g = Path(g)

                if not g.is_dir():
                    continue

                resolved = self.ctx.resolve(g)

                if self.ctx == resolved.ctx:
                    from_ = self.ctx.module
                else:
                    if self.ctx.is_addon and resolved.ctx.is_addon:
                        if 'requiredAddons' not in self.addon_details:
                            self.addon_details['requiredAddons'] = []

                        self.addon_details['requiredAddons'].append(
                            resolved.ctx.module.name
                        )

                    from_ = None

                pretty = resolved.m_name_pretty(from_=from_)

                self.macrof.add_macro(pretty,
                    resolved.fn_name_real('##ARG_1'), 1)

                self.macrof.add_macro('tag__' + pretty,
                    resolved.prefix_tag
                )

    def include_paths(self):
        if not self.macrof:
            return

        if self.parent is not None:
            yield from self.parent.include_paths()

        if self.macrof:
            yield self.macrof.exported_to

    def export(self, outpath, ctxpath=None):
        outpath = self.construct_path(outpath)

        if ctxpath is None:
            ctxpath = outpath

        if not outpath.exists():
            os.mkdir(outpath)

        self.load_includes()

        function_path = prep_path(os.path.relpath(outpath, ctxpath))
        if outpath == ctxpath:
            function_path = ''

        if self.ctx.is_addon:
            function_path = self.ctx.addon_prefix + function_path

        functions = {
            self.fn_name_real('CFG'): {
                'tag': self.prefix_tag,
                'functions': {
                    'file': str(function_path).rstrip('\\'),
                    **self.load_functions()
                }
            }
        }

        self.macrof.export(outpath)
        config = self._full_config

        for m in self.modules:
            cf, fn = m.export(outpath, ctxpath)

            dictmerge(config, cf)  # deep merge
            functions = {**functions, **fn}

        for i in self.entries:
            if i.suffix == '.sqf':
                export_path = outpath.joinpath(self.file_name_real(i))
                with open(i) as rp, open(export_path, 'w') as wp:
                    for p in self.include_paths():
                        if self.ctx.is_addon:
                            rel = (self.ctx.addon_prefix + prep_path(
                                os.path.relpath(p, ctxpath)
                            ))
                        else:
                            rel = prep_path(os.path.relpath(p, outpath))

                        wp.write('#include "{}"\n'.format(rel))

                    wp.writelines(rp.readlines())
            elif i.suffix == '.aewl':
                with open(i) as fp:
                    ctx = aewl.open_file(fp)

                    self._full_config.setdefault('rsctitles', {})

                    for x in ctx.children:
                        if x.is_resource():
                            target = self._full_config['rsctitles']
                        else:
                            target = self._full_config

                        target[x.export.name] = x.export
            elif i.suffix == '.json' and i.name != MANIFEST:
                with open(i) as fp:
                    dictmerge(self.config, json.load(fp))
            elif i.suffix in self.file_exts:
                export_path = outpath.joinpath(i.name)
                shutil.copyfile(i, export_path)

        return config, functions

    def construct_path(self, base):
        return base.joinpath(self.name)

    @property
    def parents(self):
        if self.parent is not None:
            yield self.parent
            yield from self.parents.parent

    @property
    def prefix_tag(self):
        parent_tag = getattr(self.parent, 'prefix_tag', None)
        if parent_tag is not None:
            parent_tag += '_'
        else:
            parent_tag = ''

        if self.parent is None:
            ctx_tag = self.ctx.ctx_prefix_tag
            if ctx_tag:
                parent_tag = ctx_tag + '_' + parent_tag

        return parent_tag + self.partial_tag

    def m_name_pretty(self, from_=None):
        m = self
        name = m.source_name
        name_dq = deque()

        while name:
            name_dq.appendleft(name)
            m = getattr(m, 'parent', None)
            name = getattr(m, 'source_name', None)

            if m is from_:
                break

        if from_ is None:
            ctx_name_pretty = self.ctx.ctx_name_pretty
            if ctx_name_pretty:
                name_dq.appendleft(ctx_name_pretty)

        return '_'.join(name_dq)

    def file_name_real(self, path):
        name = path.name

        if name.startswith('_'):
            return name

        return 'fn_' + name

    def fn_name_real(self, func):
        return '{prefix}_fnc_{func}'.format(
            prefix=self.prefix_tag, func=func)

    def _add_all_entries(self):
        for i in os.listdir(self.path):
            real = self.path.joinpath(i)

            if real.is_dir():
                self.add_module(real)
            else:
                self.add_entry(real)

        return self.entries
