
from pathlib import Path
from collections import deque

class Module:
    _instances = {}

    def __new__(cls, path, initialize=False, *args, **kwargs):
        try:
            inst = cls._instances[path]
        except KeyError:
            inst = super().__new__(cls)
            inst.__init__(path, initialize, *args, **kwargs)
            cls._instances[path] = inst

            return inst
        else:
            if initialize:
                inst.initialize(*args, **kwargs)
            
            return inst

    def __init__(self, path: Path, initialize, *args, **kwargs):
        self.path = path
        self.initalized = False

        if initialize: self.initialize(*args, **kwargs):
    
    def initialize(
        self,
        ctx,
        parent=None,
        tag=None,
        include=None,
        preInit=None,
        postInit=None,
        config=None,
        macros=None
    ):

        assert not self.initalized, (
            '{} already initialized'.format(str(self)))

        self.ctx = ctx
        self.parent = parent
        self.name = self.path.name

        self.partial_tag = tag

        if macros is not None:
            self.macros = macros
        else:
            self.macros = {}

        self.include = self._process_include(include)
        self.preInit = preInit
        self.postInit = postInit
        self.config = config
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

    def add_module(self, path, *args, **kwargs):
        module = Module(path, True, self.ctx, self, *args, **kwargs)
        self.modules.append(module)

        return module

    def add_macro(self, name, repl, argc):
        macro = {
            'text': repl,
            'args': ['ARG_' + str(idx + 1) for idx in range(argc)]
        }
        self.macros[name] = macro

        return macro

    def find_macro(self, key):
        try:
            return self.macros[key]
        except KeyError:
            if self.parent is not None:
                return self.parent.find_macro(key)

            raise

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

    def fn_name_real(self, func):
        return '{prefix}_fnc_{func}'.format(
            prefix=self.parent.prefix_tag, func=func)

    def _process_include(self, include):
        processed = []

        if include is not None:
            for i in include:
                resolved = ctx.resolve(i)
                processed.append(resolved)

                self.add_macro(
                    resolved.m_name_pretty,
                    resolved.fn_name_real('##ARG_1'), 1)

        return processed
