
import yaml
from pathlib import Path
from .context import Context

YAML_FILE = 'sqfpack.yaml'

def load_subs(ctx, subs):
    _glob = subs.pop('glob', None)

    if _glob is not None:
        is_addon = subs.pop('is_addon', False)
        is_module = subs.pop('is_module', True)

        if subs:
            raise Exception('Unknown key(s) {}'.format(
                ','.join(list(subs.keys()))
            ))

        for f in ctx.path.glob(_glob):
            p = Path(f).absolute()

            if not p.is_dir():
                continue

            ctx.add_sub(p, is_addon=is_addon, is_module=is_module)
    else:
        for s in subs.values():
            path = Path(s.pop('path'))

            if not path.is_absolute():
                path = ctx.path.joinpath(path).absolute()

            subsubs = s.pop('subs', None)
            c = ctx.add_sub(path, **s)

            if subsubs is not None:
                load_subs(c, subsubs)

def load_ctx(yaml_f=None):
    if yaml_f is None:
        yaml_f = Path.cwd().joinpath(YAML_FILE)

    with open(yaml_f) as fp:
        config = yaml.load(fp, Loader=yaml.FullLoader)
        fpath = fp.name

    path = Path(config.pop('path'))

    if not path.is_absolute():
        path = Path(fpath).joinpath(path)

    subs = config.pop('subs', {})
    ctx = Context(path, **config)

    load_subs(ctx, subs)

    return ctx
