
import os
from pathlib import Path
from sqfpack import load_ctx

def main(base):
    ctx = load_ctx(Path.cwd().joinpath('sqfpack.example.yaml'))
    out = ctx.path.joinpath('..', 'out.githide')

    services = ctx.subs[2]
    base_module = services.resolve('base')

    base_module.config.setdefault('services', {})
    base_module.config['services']['aliases'] = {}

    for f in os.listdir(services.path):
        if not services.path.joinpath(f).is_dir():
            continue

        m = services.resolve(f)

        base_module.config['services']['aliases'][m.source_name] = m.prefix_tag

    ctx.export(out)

    return out
