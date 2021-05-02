
import os
from sqfpack.context import Context
from sqfpack.modules import Module


def main(base):
    path = base.joinpath('src')
    out = base.joinpath('out.githide')

    ctx = Context(path, prefix_tag='lm')

    for _, p, kw in [('Mission.Altis', 'client', {'is_addon': False}),
                     ('life_server', 'server', {'is_addon': True})
                     ]:
        p = path.joinpath(p)
        ctx.add_sub(p, **kw)

    srvc_path = path.joinpath('services')
    srvc = ctx.add_sub(srvc_path, **{
                'is_addon': False, 'is_module': False, 'prefix_tag': 'srvc'})

    for i in os.listdir(srvc_path):
        j = srvc_path.joinpath(i)

        if j.is_dir():
            srvc.add_sub(j, is_addon=True, is_module=True)
        else:
            print('File skipped {}'.format(i))

    base_module = Module(srvc_path.joinpath('base'), False)

    if 'services' not in base_module.config:
        base_module.config['services'] = {}

    base_module.config['services']['aliases'] = {}

    for f in os.listdir(srvc_path):
        m = Module(srvc_path.joinpath(f), False)

        base_module.config['services']['aliases'][m.source_name] = m.prefix_tag

    def _print(m, indent=0):
        def _fmt():
            return ('|  ' * indent) + '|--'

        print(_fmt() + m.name + '/')
        indent += 1
        for i in m.entries:
            print(_fmt() + i.name)

        for i in m.modules:
            _print(i, indent)

    ctx.export(out)

    return out
