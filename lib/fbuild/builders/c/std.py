from itertools import chain

from fbuild.builders.c import tempfile
from fbuild import ExecutionError, ConfigFailed

# -----------------------------------------------------------------------------

default_types_int = tuple('%s%s' % (prefix, typename)
    for prefix in ('', 'signed ', 'unsigned ')
    for typename in ('char', 'short', 'int', 'long', 'long long'))

default_types_float = ('float', 'double', 'long double')

default_types_misc = ('void*',)

default_types = default_types_int + default_types_float + default_types_misc

default_types_stddef_h = ('size_t', 'wchar_t', 'ptrdiff_t')

# -----------------------------------------------------------------------------

def get_type_data(builder, typename, *args, int_type=False, **kwargs):
    builder.check('getting type %r info' % typename)

    code = '''
        #include <stddef.h>
        #include <stdio.h>

        typedef %s type;
        struct TEST { char c; type mem; };
        int main(int argc, char** argv) {
            printf("%%d\\n", (int)offsetof(struct TEST, mem));
            printf("%%d\\n", (int)sizeof(type));
        #ifdef INTTYPE
            printf("%%d\\n", (type)~3 < (type)0);
        #endif
            return 0;
        }
    ''' % typename

    if int_type:
        cflags = dict(kwargs.get('cflags', {}))
        cflags['macros'] = cflags.get('macros', []) + ['INTTYPE=1']
        kwargs['cflags'] = cflags

    try:
        data = builder.tempfile_run(code, *args, **kwargs)[0].split()
    except ExecutionError:
        builder.log('failed', color='yellow')
        raise ConfigFailed('failed to discover type data for %r' % typename)

    d = {'alignment': int(data[0]), 'size': int(data[1])}
    s = 'alignment: %(alignment)s size: %(size)s'

    if int_type:
        d['signed'] = int(data[2]) == 1
        s += ' signed: %(signed)s'

    builder.log(s % d, color='green')

    return d


def get_types_data(builder, types, *args, **kwargs):
    d = {}
    for t in types:
        try:
            d[t] = get_type_data(builder, t, *args, **kwargs)
        except ConfigFailed:
            pass

    return d


def get_type_conversions(builder, type_pairs, *args, **kwargs):
    lines = []
    for t1, t2 in type_pairs:
        lines.append(
            'printf("%%d %%d\\n", '
            '(int)sizeof((%(t1)s)0 + (%(t2)s)0), '
            '(%(t1)s)~3 + (%(t2)s)1 < (%(t1)s)0 + (%(t2)s)0);' %
            {'t1': t1, 't2': t2})

    code = '''
    #include <stdio.h>

    int main(int argc, char** argv) {
        %s
        return 0;
    }
    ''' % '\n'.join(lines)

    try:
        data = builder.tempfile_run(code, *args, **kwargs)[0]
    except ExecutionError:
        builder.log('failed', color='yellow')
        raise ConfigFailed('failed to detect type conversions for %s' % types)

    d = {}
    for line, (t1, t2) in zip(data.decode('utf-8').split('\n'), type_pairs):
        size, sign = line.split()
        d[(t1, t2)] = (int(size), int(sign) == 1)

    return d

# -----------------------------------------------------------------------------

def detect_types(builder):
    d = {}
    d.update(get_types_data(builder, default_types_int, int_type=True))
    d.update(get_types_data(builder, default_types_float))
    d.update(get_types_data(builder, default_types_misc))

    return d

def detect_type_conversions_int(builder):
    type_pairs = [(t1, t2)
        for t1 in default_types_int
        for t2 in default_types_int]

    builder.check('getting int type conversions')
    try:
        d = get_type_conversions(builder, type_pairs)
    except ConfigFailed:
        builder.log('failed', color='yellow')
    else:
        builder.log('ok', color='green')

    return d

def detect_stddef_h(builder):
    return get_types_data(builder, default_types_stddef_h)

# -----------------------------------------------------------------------------

def config_types(conf, builder):
    conf.configure('std.types', detect_types, builder)
    conf.configure('std.int_type_conversions',
        detect_type_conversions_int, builder)

def config_stddef_h(conf, builder):
    if not builder.check_header_exists('stddef.h'):
        raise ConfigFailed('missing stddef.h')

    conf.configure('std.stddef_h.types', detect_stddef_h, builder)

def config(conf, builder):
    config_types(conf, builder)
    config_stddef_h(conf, builder)

# -----------------------------------------------------------------------------

def types_int(conf):
    return (t for t in default_types_int if t in conf.std.types)

def types_float(conf):
    return (t for t in default_types_float if t in conf.std.types)

def type_aliases_int(conf):
    d = {}
    for t in types_int(conf):
        data = conf.std.types[t]
        d.setdefault((data['size'], data['signed']), t)

    return d

def type_aliases_float(conf):
    d = {}
    for t in types_float(conf):
        data = conf.std.types[t]
        d.setdefault(data['size'], t)

    return d

def type_conversions_int(conf):
    aliases = type_aliases_int(conf)
    return {type_pair: aliases[size_signed]
        for type_pair, size_signed in conf.std.int_type_conversions.items()}
