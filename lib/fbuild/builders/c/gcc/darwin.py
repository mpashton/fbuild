from .. import gcc

# -----------------------------------------------------------------------------

def config_static(conf, *, **kwargs):
    return gcc.config_static(conf, **kwargs)

def config_shared(conf, *,
        lib_suffix='.dylib',
        lib_link_flags=['-dynamiclib'],
        **kwargs):
    return gcc.config_shared(conf,
        lib_suffix=lib_suffix,
        lib_link_flags=lib_link_flags,
        **kwargs)

def config(conf, *, **kwargs):
    config_static(conf, **kwargs)
    config_shared(conf, **kwargs)
