
class Factory:
    _instances = {}

    def __new__(cls, path, *args, **kwargs):
        if path in cls._instances:
            inst = cls._instances[path]

            if isinstance(inst, cls):
                return cls._instances[path]

        inst = super().__new__(cls)
        inst.__init__(path, *args, **kwargs)
        cls._instances[path] = inst

        return inst


class Section(Factory):
    def __init__(self, path):
        self.path = path
        self.modules = []

    def add_module(self, module):
        self.modules.append(module)


class Module(Factory):
    def __init__(self, path):
        self.path = path


if __name__ == '__main__':
    a = Section('a')
    b = Section('b')
    c = Section('a')

    d = Module('a')
    e = Module('b')
    f = Module('a')

    print(c is a, b is a, d is a, f is d, f is c)
