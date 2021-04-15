
import os
import json
from pathlib import Path
from functools import cached_property, lru_cache
from collections import deque

class Macrofile:
    def __init__(self, macros, module):
        self.macros = {}
        self.module = module
        self.exported_to = None

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
        return self.module.name + '.incl.h'

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
        if entry.suffix == '.sqf':
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

                if self.ctx == resolved.ctx:
                    from_ = self.ctx.module
                else:
                    from_ = None

                self.macrof.add_macro(
                    resolved.m_name_pretty(from_=from_),
                    resolved.fn_name_real('##ARG_1'), 1)

        return self.macrof

    def include_paths(self):
        if not self.macrof:
            return

        if self.parent is not None:
            yield from self.parent.include_paths()

        if self.macrof:
            yield self.macrof.exported_to

    def export(self, outpath):
        outpath = outpath.joinpath(self.name)

        if not outpath.exists():
            os.mkdir(outpath)

        macrof = self.load_macros()
        functions = {
            self.fn_name_real('CFG'): {
                'tag': self.prefix_tag,
                'functions': self.load_functions()
            }
        }

        macrof.export(outpath)
        config = self.config

        for m in self.modules:
            cf, fn = m.export(outpath)

            config = {**config, **cf}
            functions = {**functions, **fn}

        for i in self.entries:
            export_path = outpath.joinpath(self.file_name_real(i))

            with open(i) as rp, open(export_path, 'w') as wp:
                for p in self.include_paths():
                    rel = Path(os.path.relpath(p, outpath))
                    # rel = outpath.relative_to(p)
                    rel = str(rel).replace('/', '\\')

                    wp.write('#include "{}"\n'.format(str(rel)))

                wp.writelines(rp.readlines())

        return config, functions

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

        return parent_tag + self.partial_tag

    def m_name_pretty(self, from_=None):
        m = self
        name = m.name
        name_dq = deque()

        while name:
            name_dq.appendleft(name)
            m = getattr(m, 'parent', None)

            if m == from_:
                break

            name = getattr(m, 'name', None)

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
