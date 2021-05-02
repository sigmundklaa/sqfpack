
def prep_path(path):
    return path.replace('/', '\\')


def dictmerge(dest, src):
    for key, value in src.items():
        if isinstance(value, dict):
            dest_val = dest.setdefault(key, {})

            dictmerge(dest_val, value)
        else:
            dest[key] = value

    return dest
