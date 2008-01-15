from fbuild import ConfigFailed

# -----------------------------------------------------------------------------

def config_mmap(conf, builder):
    if not conf.configure('have_mmap',
            builder.check_header_exists, 'sys/mman.h'):
        raise ConfigFailed('missing sys/mman.h')

    conf.configure('mmap_macros', detect_mmap_macros, builder)


def detect_mmap_macros(builder):
    return {m: builder.check_macro_defined(m, ['sys/mman.h']) for m in (
        'PROT_EXEC',
        'PROT_READ',
        'PROT_WRITE',
        'MAP_DENYWRITE',
        'MAP_ANON',
        'MAP_FILE',
        'MAP_FIXED',
        'MAP_HASSEMAPHORE',
        'MAP_SHARED',
        'MAP_PRIVATE',
        'MAP_NORESERVE',
        'MAP_LOCKED',
        'MAP_GROWSDOWN',
        'MAP_32BIT',
        'MAP_POPULATE',
        'MAP_NONBLOCK'
    )}

# -----------------------------------------------------------------------------

def config_pthreads(conf, builder):
    if not conf.configure('have_pthreads',
            builder.check_header_exists, 'pthread.h'):
        raise ConfigFailed('missing pthread.h')

    conf.configure('pthread_flags', detect_pthread_flags, builder)


def detect_pthread_flags(builder):
    code = '''
        void* start(void* data) { return NULL; }

        int main(int argc, char** argv) {
            pthread_t thr;
            pthread_attr_t attr;
            pthread_attr_init(&attr);
            pthread_attr_setdetachstate(&attr, PTHREAD_CREATE_DETACHED);
            int res = pthread_create(&thr, &attr, start, NULL);
            pthread_attr_destroy(&attr);
            return res;
        }
    '''

    builder.check('detecting pthread link flags')
    for flags in [], ['-lpthread'], ['-pthread'], ['-pthreads']:
        if builder.try_tempfile_run(code,
                headers=['pthread.h'],
                lflags={'flags': flags}):
            builder.log('ok %r' % ' '.join(flags), color='green')
            return flags

    builder.log('failed', color='yellow')
    raise ConfigFailed('failed to link pthread program')

# -----------------------------------------------------------------------------

def config_sockets(conf, builder):
    if not conf.configure('have_sockets',
            builder.check_header_exists, 'sys/socket.h'):
        raise ConfigFailed('missing sys/socket.h')

    conf.configure('socklen_t', detect_socklen_t, builder)


def detect_socklen_t(builder):
    code = 'extern int accept(int s, struct sockaddr* addr, %s* addrlen);'

    builder.check('determing type of socklen_t')
    for t in 'socklen_t', 'unsigned int', 'int':
        if builder.try_tempfile_compile(code %t,
                headers=['sys/types.h', 'sys/socket.h']):
            builder.log('ok ' + t, color='green')
            return t

    builder.log('failed', color='yellow')
    raise ConfigFailed('failed to detect type of socklen_t')

# -----------------------------------------------------------------------------

def config_posix_support(conf, builder):
    config_mmap(conf, builder)
    config_pthreads(conf, builder)
    config_sockets(conf, builder)
