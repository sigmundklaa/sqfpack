
import os
import json
from pathlib import Path
from functools import cached_property, lru_cache
from collections import deque

class Macrofile:
    def __init__(self, macros, module):
        self.macros = macros
        self.module = module

    def __bool__(self):
        return self.macros is not {}

    def encode_macro(self, macro):
        if isinstance(macro, dict):
            name = macro['name']
            args = '({})'.format(
                ','.join(macro['args'])) if macro['args'] is not [] else ''

            value = ' ' + macro['text']
        else:
            name, args, value = macro, '', ''

        return ('#define {name}{args}{value}\n'.format(
            name=name,
            args=args,
            value=value
        ))

    def add_macro(self, name, repl, argc):
        macro = {
            'name': 'name',
            'text': repl,
            'args': ['ARG_' + str(idx + 1) for idx in range(argc)]
        }
        self.macros[name] = macro

        return macro

    @property
    def filename(self):
        return self.module.name + '.incl.h'

    def construct_path(self, base):
        return base.joinpath(self.filename)

    def export(self, outpath):
        filepath = self.construct_path(outpath)
        with open(filepath, 'w') as fp:
            for i in self.macros.values():
                fp.write(self.encode_macro(i))

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

        if initialize: self.initialize(*args, **kwargs)
    
    def initialize(self, ctx, **kwargs):
        if self.initalized: return

        self.ctx = ctx
        self.entries = set()
        self.modules = []
        self.parent = kwargs.get('parent', None)
        self.name = self.path.name

        self._add_all_entries()

        manifest = self.path.joinpath('manifest.json')

        if manifest.exists():
            with open(manifest) as fp:
                kwargs = json.load(fp)

        self.partial_tag = kwargs.get('tag')
        self._include = kwargs.get('include', None)
        self.preInit = kwargs.get('preInit', [])
        self.postInit = kwargs.get('postInit', [])
        self.config = kwargs.get('config', {})
        self.macrof = Macrofile(kwargs.get('macros', {}), self)
        self.initalized = True
        self.functions = {}

    def __str__(self):
        return '{}({})'.format(type(self).__name__, str(self.path))

    def add_function(self, path):
        name = path.stem

        self.functions[name] = {
            'preInit': name in self.preInit,
            'postInit': name in self.postInit
        }

        return self.functions[name]

    def add_entry(self, entry: Path):
        self.entries.add(entry.absolute())

    def add_module(self, path: Path, **kwargs):
        module = Module(path.absolute(), True, self.ctx, parent=self, **kwargs)
        self.modules.append(module)

        return module

    def load_functions(self):
        for f in self.entries:
            self.add_function(f)

        return self.functions

    def load_macros(self):
        if self._include is not None:
            for i in self._include:
                resolved = self.ctx.resolve(i)

                self.macrof.add_macro(
                    resolved.m_name_pretty,
                    resolved.fn_name_real('##ARG_1'), 1)

        return self.macrof

    def include_paths(self, outpath):
        if not self.macrof:
            return

        if self.parent is not None:
            yield from self.parent.include_paths(outpath)

        if self.macrof:
            yield self.macrof.construct_path(outpath)

    def export(self, outpath):
        if not outpath.exists():
            os.mkdir(outpath)

        macrof = self.load_macros()
        functions = self.load_functions()

        macrof.export(outpath)

        for m in self.modules:
            m.export(outpath)

        for i in self.entries:
            if i.suffix == '.sqf':
                export_path = outpath.joinpath(self.file_name_real(i))

                with open(i) as rp, open(export_path, 'w') as wp:
                    for p in self.include_paths(outpath):
                        rel = Path(os.path.relpath(export_path, p))
                        rel = str(rel).replace('/', '\\')

                        wp.write('#include "{}"\n'.format(str(rel)))

                    wp.writelines(rp.readlines())

        return self.config, functions

    @property
    def prefix_tag(self):
        parent_tag = getattr(self.parent, 'prefix_tag', None)
        if parent_tag is not None:
            parent_tag += '_'
        else:
            parent_tag = ''

        return parent_tag + self.partial_tag

    @property
    def m_name_pretty(self):
        m = self
        name = m.name
        name_dq = deque()

        while name:
            name_dq.appendleft(name)
            m = getattr(m, 'parent', None)
            name = getattr(m, 'name', None)

        return '_'.join(name_dq)

    def file_name_real(self, path):
        name = path.name

        if name.startswith('_'):
            return name

        return 'fn_' + name

    def fn_name_real(self, func):
        return '{prefix}_fnc_{func}'.format(
            prefix=self.parent.prefix_tag, func=func)

    def _add_all_entries(self):
        for i in os.listdir(self.path):
            real = self.path.joinpath(i)

            if real.is_dir():
                self.add_module(real)
            else:
                self.add_entry(real)

        return self.entries
