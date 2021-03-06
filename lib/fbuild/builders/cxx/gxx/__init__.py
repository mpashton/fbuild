import fbuild.builders.c.gcc
import fbuild.db

# ------------------------------------------------------------------------------

def make_gxx(ctx, exe=None, default_exes=['g++', 'c++'], **kwargs):
    return fbuild.builders.c.gcc.make_gcc(ctx, exe, default_exes, **kwargs)

# ------------------------------------------------------------------------------

@fbuild.db.caches
def static(*args, make_gxx=make_gxx, src_suffix='.cc', **kwargs):
    return fbuild.builders.c.gcc.static(*args,
        make_gcc=make_gxx,
        src_suffix=src_suffix,
        **kwargs)

@fbuild.db.caches
def shared(*args, make_gxx=make_gxx, src_suffix='.cc', **kwargs):
    return fbuild.builders.c.gcc.shared(*args,
        make_gcc=make_gxx,
        src_suffix=src_suffix,
        **kwargs)
