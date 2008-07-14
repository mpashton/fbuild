import os
import io
import textwrap

import fbuild
from fbuild import logger, execute, ConfigFailed, ExecutionError
from fbuild.temp import tempdir
from fbuild.path import make_path, glob_paths
from fbuild.builders import find_program, AbstractCompilerBuilder

# -----------------------------------------------------------------------------

class Ocamldep:
    '''
    Use ocamldoc to generate dependencies for ocaml files.
    '''

    def __init__(self, exe, module_flags=[]):
        self.exe = exe
        self.module_flags = module_flags

    def __call__(self, src, *,
            includes=[],
            flags=[],
            buildroot=fbuild.buildroot):
        dst = make_path(src, root=buildroot) + '.depends'
        fbuild.path.make_dirs(os.path.dirname(dst))

        cmd = [self.exe]
        cmd.extend(self.module_flags)

        for i in includes:
            cmd.extend(('-I', i))

        d = os.path.dirname(src)
        if d and d not in includes:
            cmd.extend(('-I', d))

        cmd.extend(flags)
        cmd.append(src)

        with open(dst, 'w') as f:
            execute(cmd, self.exe, '%s -> %s' % (src, dst),
                stdout=f,
                color='yellow')

        def fix(path):
            base, ext = os.path.splitext(path)
            if ext == '.cmo' or ext == '.cmx':
                return base + '.ml'
            if ext == '.cmi':
                return base + '.mli'

        d = {}
        with open(dst) as f:
            # we need to join lines ending in "\" together
            for line in io.StringIO(f.read().replace('\\\n', '')):
                filename, *deps = line.split()
                d[fix(filename[:-1])] = [fix(d) for d in deps]

        paths = []

        for include_path in os.path.dirname(src) or '.',:
            # note we use listdir to protect against case insensitive
            # filesystems
            dirs = set(os.listdir(include_path))

            for path in d.get(src, []):
                if path not in paths:
                    paths.append(path)

        return paths

def config_ocamldep(conf, exe=None, default_exes=['ocamldep.opt', 'ocamldep']):
    exe = exe or find_program(default_exes)

    conf.setdefault('ocaml', {})['ocamldep'] = Ocamldep(exe)

# -----------------------------------------------------------------------------

class Builder(AbstractCompilerBuilder):
    def __init__(self, exe, *,
            obj_suffix,
            lib_suffix,
            exe_suffix,
            debug_flags=['-g']):
        super().__init__(src_suffix='.ml')

        self.exe = exe
        self.obj_suffix = obj_suffix
        self.lib_suffix = lib_suffix
        self.exe_suffix = exe_suffix
        self.debug_flags = debug_flags

    def _run(self, dst, srcs, *,
            includes=[],
            libs=[],
            pre_flags=[],
            flags=[],
            debug=False,
            buildroot=fbuild.buildroot,
            **kwargs):
        # we need to make sure libraries are built first before we compile
        # the sources
        assert srcs or libs, "%s: no sources or libraries passed in" % dst

        dst = make_path(dst, root=buildroot)
        fbuild.path.make_dirs(os.path.dirname(dst))

        extra_srcs = []
        for lib in libs:
            if os.path.exists(lib):
                extra_srcs.append(lib)
            else:
                extra_srcs.append(lib + self.lib_suffix)

        cmd = [self.exe]
        cmd.extend(pre_flags)

        if debug:
            cmd.extend(self.debug_flags)

        for i in includes:
            cmd.extend(('-I', i))

        d = os.path.dirname(dst)
        if d not in includes:
            cmd.extend(('-I', d))

        cmd.extend(flags)
        cmd.extend(('-o', dst))
        cmd.extend(extra_srcs)
        cmd.extend(srcs)

        execute(cmd, self.exe,
            '%s -> %s' % (' '.join(extra_srcs + srcs), dst),
            **kwargs)

        return dst

    def _compile(self, src, dst=None, *args, obj_suffix, **kwargs):
        src = make_path(src)

        if dst is None:
            dst = os.path.splitext(src)[0] + obj_suffix

        return self._run(dst, [src],
            pre_flags=['-c'],
            color='green',
            *args, **kwargs)

    def compile_implementation(self, *args, **kwargs):
        return self._compile(obj_suffix=self.obj_suffix, *args, **kwargs)

    def compile_interface(self, *args, **kwargs):
        return self._compile(obj_suffix='.cmi', *args, **kwargs)

    def compile(self, src, *args, **kwargs):
        src = make_path(src)

        if src.endswith('.mli'):
            return self.compile_interface(src, *args, **kwargs)
        else:
            return self.compile_implementation(src, *args, **kwargs)

    def _link(self, dst, srcs, *args, libs=[], **kwargs):
        srcs = glob_paths(srcs)

        return self._run(dst, srcs, libs=libs, color='cyan', *args, **kwargs)

    def link_lib(self, dst, *args, **kwargs):
        return self._link(dst + self.lib_suffix,
            pre_flags=['-a'], *args, **kwargs)

    def link_exe(self, dst, *args, **kwargs):
        return self._link(dst + self.exe_suffix, *args, **kwargs)

# -----------------------------------------------------------------------------

def check_builder(builder):
    logger.check('checking if ocaml can make objects')
    if builder.try_compile():
        logger.passed()
    else:
        raise ConfigFailed('ocaml compiler failed')

    logger.check('checking if ocaml can make libraries')
    if builder.try_link_lib():
        logger.passed()
    else:
        raise ConfigFailed('ocaml lib linker failed')

    logger.check('checking if ocaml can make exes')
    if builder.try_link_exe():
        logger.passed()
    else:
        raise ConfigFailed('ocaml exe linker failed')

    logger.check('Checking if ocaml can link lib to exe')
    with tempdir() as dirname:
        src_lib = os.path.join(dirname, 'lib.ml')
        with open(src_lib, 'w') as f:
            print('let x = 5;;', file=f)

        src_exe = os.path.join(dirname, 'exe.ml')
        with open(src_exe, 'w') as f:
            print('print_int Lib.x;;', file=f)

        obj = builder.compile(src_lib, quieter=1)
        lib = builder.link_lib(os.path.join(dirname, 'lib'), [obj],
            quieter=1)

        obj = builder.compile(src_exe, quieter=1)
        exe = builder.link_exe(os.path.join(dirname, 'exe'), [obj],
            libs=[lib],
            quieter=1)

        try:
            stdout, stderr = execute([exe], quieter=1)
        except ExecutionError:
            raise ConfigFailed('failed to link ocaml lib to exe')
        else:
            if stdout != b'5':
               raise ConfigFailed('failed to link ocaml lib to exe')
            logger.passed()

# -----------------------------------------------------------------------------

def make_builder(exe, default_exes, *args, **kwargs):
    builder = Builder(exe or find_program(default_exes), *args, **kwargs)
    check_builder(builder)

    return builder

def config_bytecode(conf,
        exe=None,
        default_exes=['ocamlc.opt', 'ocamlc'],
        **kwargs):
    conf.setdefault('ocaml', {})['bytecode'] = make_builder(exe, default_exes,
        obj_suffix='.cmo',
        lib_suffix='.cma',
        exe_suffix='',
        **kwargs)

def config_native(conf,
        exe=None,
        default_exes=['ocamlopt.opt', 'ocamlopt'],
        **kwargs):
    conf.setdefault('ocaml', {})['native'] = make_builder(exe, default_exes,
        obj_suffix='.cmx',
        lib_suffix='.cmxa',
        exe_suffix='',
        **kwargs)

# -----------------------------------------------------------------------------

def config_ocamllex(conf, exe=None):
    pass

def config_ocamlyacc(conf, exe=None):
    pass

# -----------------------------------------------------------------------------

def config(conf,
        ocamlc=None,
        ocamlopt=None,
        ocamllex=None,
        ocamlyacc=None):
    config_ocamldep(conf, ocamlc)
    config_bytecode(conf, ocamlc)
    config_native(conf, ocamlopt)
    config_ocamllex(conf, ocamllex)
    config_ocamlyacc(conf, ocamlyacc)
