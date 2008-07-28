from itertools import chain
from functools import partial

import fbuild
import fbuild.packages as packages

# -----------------------------------------------------------------------------

class BytecodeModule(packages.OneToOnePackage):
    def command(self, conf, *args, **kwargs):
        return conf['ocaml']['bytecode'].compile(*args, **kwargs)

class NativeModule(packages.OneToOnePackage):
    def command(self, conf, *args, **kwargs):
        return conf['ocaml']['native'].compile(*args, **kwargs)

class BytecodeImplementation(packages.OneToOnePackage):
    def command(self, conf, *args, **kwargs):
        return conf['ocaml']['bytecode'].compile_implementation(*args, **kwargs)

class NativeImplementation(packages.OneToOnePackage):
    def command(self, conf, *args, **kwargs):
        return conf['ocaml']['native'].compile_implementation(*args, **kwargs)

class BytecodeInterface(packages.OneToOnePackage):
    def command(self, conf, *args, **kwargs):
        return conf['ocaml']['bytecode'].compile_interface(*args, **kwargs)

class NativeInterface(packages.OneToOnePackage):
    def command(self, conf, *args, **kwargs):
        return conf['ocaml']['native'].compile_interface(*args, **kwargs)

# -----------------------------------------------------------------------------

class _Linker(packages.ManyToOnePackage):
    def __init__(self, dst, srcs, *, includes=[], libs=[], **kwargs):
        super().__init__(dst, packages.glob_paths(srcs), **kwargs)

        self.includes = includes
        self.libs = libs

    def dependencies(self, conf):
        # filter out system libraries
        return chain(super().dependencies(conf), (lib for lib in self.libs
            if isinstance(lib, packages.Package)))

    def run(self, conf):
        libs = packages.build_srcs(conf, self.libs)
        srcs = packages.build_srcs(conf, self.srcs)

        # make sure that we include the parent of the src and the dst in the
        # include paths
        includes = set(self.includes)
        for src in srcs:
            if src.parent:
                includes.add(src.parent)
                includes.add(src.parent.replace_root(fbuild.buildroot))

        #  Note that we don't need the -modules flag since at the point
        # all of the source files will have been evaluated
        objs = fbuild.scheduler.map_with_dependencies(
            partial(conf['ocaml']['ocamldep'], includes=includes),
            partial(self.compiler, conf, includes=includes),
            srcs)

        objs = [obj for obj in objs if not obj.endswith('cmi')]

        return self.command(conf, packages.build(conf, self.dst), objs,
            includes=includes,
            libs=libs)

class BytecodeLibrary(_Linker):
    def compiler(self, conf, *args, **kwargs):
        return conf['ocaml']['bytecode'].compile(*args, **kwargs)

    def command(self, conf, *args, **kwargs):
        return conf['ocaml']['bytecode'].link_lib(*args, **kwargs)

class NativeLibrary(_Linker):
    def compiler(self, conf, *args, **kwargs):
        return conf['ocaml']['native'].compile(*args, **kwargs)

    def command(self, conf, *args, **kwargs):
        return conf['ocaml']['native'].link_lib(*args, **kwargs)

class BytecodeExecutable(_Linker):
    def compiler(self, conf, *args, **kwargs):
        return conf['ocaml']['bytecode'].compile(*args, **kwargs)

    def command(self, conf, *args, **kwargs):
        return conf['ocaml']['bytecode'].link_exe(*args, **kwargs)

class NativeExecutable(_Linker):
    def compiler(self, conf, *args, **kwargs):
        return conf['ocaml']['native'].compile(*args, **kwargs)

    def command(self, conf, *args, **kwargs):
        return conf['ocaml']['native'].link_exe(*args, **kwargs)

# -----------------------------------------------------------------------------

class Library(_Linker):
    '''
    Choose the native compiler if it is available, or if not available, fall
    back to the bytecode compiler.
    '''

    def compiler(self, conf, *args, **kwargs):
        try:
            return conf['ocaml']['native'].compile(*args, **kwargs)
        except KeyError:
            return conf['ocaml']['bytecode'].compile(*args, **kwargs)

    def command(self, conf, *args, **kwargs):
        try:
            return conf['ocaml']['native'].link_lib(*args, **kwargs)
        except KeyError:
            return conf['ocaml']['bytecode'].link_lib(*args, **kwargs)

class Executable(_Linker):
    def compiler(self, conf, *args, **kwargs):
        try:
            return conf['ocaml']['native'].compile(*args, **kwargs)
        except KeyError:
            return conf['ocaml']['bytecode'].compile(*args, **kwargs)

    def command(self, conf, *args, **kwargs):
        try:
            return conf['ocaml']['native'].link_exe(*args, **kwargs)
        except KeyError:
            return conf['ocaml']['bytecode'].link_exe(*args, **kwargs)

# -----------------------------------------------------------------------------

class Ocamllex(packages.SimplePackage):
    def command(self, conf, *args, **kwargs):
        return conf['ocaml']['ocamllex'](*args, **kwargs)

class Ocamlyacc(packages.SimplePackage):
    def command(self, conf, *args, **kwargs):
        return conf['ocaml']['ocamlyacc'](*args, **kwargs)
