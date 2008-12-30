import fbuild
import fbuild.builders.ocaml
from fbuild.path import Path

def build():
    ocaml = fbuild.builders.ocaml.config_ocaml()

    lib = ocaml.bytecode.build_lib('lib', Path.glob('lib*.ml{,i}'))
    exe = ocaml.bytecode.build_exe('exe.byte', ['exe.ml'], libs=[lib])

    lib = ocaml.native.build_lib('lib', Path.glob('lib*.ml{,i}'))
    exe = ocaml.native.build_exe('exe.native', ['exe.ml'], libs=[lib])

    lib = ocaml.build_lib('lib', Path.glob('lib*.ml{,i}'))
    exe = ocaml.build_exe('exe', ['exe.ml'], libs=[lib]).bytecode
