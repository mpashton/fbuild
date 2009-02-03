"""fbuild.config.c.stdlib extends fbuild.config.c.{c90,c99} to expose many
common extensions to the C standard library."""

import fbuild
import fbuild.config.c as c
from fbuild.config.c.c99 import *

# ------------------------------------------------------------------------------

class errno_h(errno_h):
    # error_t is supported on some posix libraries.
    error_t = c.type_test()

class signal_h(signal_h):
    @c.cacheproperty
    def signal(self):
        if not self.header:
            return None

        # Some implementations don't follow the standard and use "int" as the
        # return type of the signal functions.
        fbuild.logger.check("checking signal in 'signal.h'")

        if not self.builder.try_run('''
                #include <signal.h>
                void foo(int x) {}
                int main() {
                    void (*f)(int) = signal(SIGTERM, foo);
                    return 0;
                }
                '''):
            fbuild.logger.failed()
            return None

        if self.builder.try_run('''
                #include <signal.h>
                void foo(int x) {}
                int main() {
                    return *(signal (0, 0)) (0) == 1;
                }
                '''):
            fbuild.logger.passed('ok int')
            return c.Function(
                c.Function('int', 'int'),
                'int',
                c.Function('int', 'int'))
        else:
            fbuild.logger.passed('ok void')
            return c.Function(
                c.Function('void', 'int'),
                'int',
                c.Function('void', 'int'))