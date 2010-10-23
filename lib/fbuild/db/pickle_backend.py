import io
import pickle

import fbuild.db.backend
import fbuild.path

# ------------------------------------------------------------------------------

class PickleBackend(fbuild.db.backend.Backend):
    def __init__(self, ctx):
        super().__init__(ctx)

        self._functions = {}
        self._function_calls = {}
        self._files = {}
        self._call_files = {}
        self._external_srcs = {}
        self._external_dsts = {}

    def save(self, filename):
        """Save the database to the file."""

        f = io.BytesIO()
        pickler = _Pickler(self._ctx, f, pickle.HIGHEST_PROTOCOL)

        pickler.dump((
            self._functions,
            self._function_calls,
            self._files,
            self._call_files,
            self._external_srcs,
            self._external_dsts))

        s = f.getvalue()

        # Try to save the state as atomically as possible. Unfortunately, if
        # someone presses ctrl+c while we're saving, we might corrupt the db.
        # So, we'll write to a temp file, then move the old state file out of
        # the way, then rename the temp file to the filename.
        path = fbuild.path.Path(filename)
        tmp = path + '.tmp'
        old = path + '.old'

        with open(tmp, 'wb') as f:
            f.write(s)

        if path.exists():
            path.rename(old)

        tmp.rename(path)

        if old.exists():
            old.remove()

    def load(self, filename):
        """Load the database from the file."""

        with open(filename, 'rb') as f:
            unpickler = _Unpickler(self._ctx, f)

            self._functions, self._function_calls, self._files, \
                self._call_files, self._external_srcs, \
                self._external_dsts = unpickler.load()


    # --------------------------------------------------------------------------

    def find_function(self, fun_name):
        """Returns the function record or None if it does not exist."""

        # Make sure we got the right types.
        assert isinstance(fun_name, str)

        try:
            return self._functions[fun_name]
        except KeyError:
            # This is the first time we've seen this function.
            return None


    def save_function(self, fun_name, fun_digest):
        """Insert or update the function's digest."""

        # Make sure we got the right types.
        assert isinstance(fun_name, str)
        assert isinstance(fun_digest, str)

        # Since the function changed, delete out all the related data.
        self.delete_function(fun_name)

        self._functions[fun_name] = fun_digest


    def delete_function(self, fun_name):
        """Clear the function from the database."""

        # Make sure we got the right types.
        assert isinstance(fun_name, str)

        try:
            del self._functions[fun_name]
        except KeyError:
            pass

        # Since the function was removed, all of this function's calls and call
        # files are dirty, so delete them.
        try:
            del self._function_calls[fun_name]
        except KeyError:
            pass

        try:
            del self._external_srcs[fun_name]
        except KeyError:
            pass

        try:
            del self._external_dsts[fun_name]
        except KeyError:
            pass

        # Since _call_files is indexed by filename, we need to search through
        # each item and delete any references to this function. The assumption
        # is that the files will change much less frequently compared to
        # functions, so we can have this be a more expensive call.
        remove_keys = []
        for key, value in self._call_files.items():
            try:
                del value[fun_name]
            except KeyError:
                pass

            if not value:
                remove_keys.append(key)

        # If any of the _call_files have no values, remove them.
        for key in remove_keys:
            try:
                del self._call_files[key]
            except KeyError:
                pass

    # --------------------------------------------------------------------------

    def find_call(self, function, bound):
        """Returns the function call index and result or None if it does not
        exist."""

        # Make sure we got the right types.
        assert isinstance(function, str)
        assert isinstance(bound, dict)

        try:
            datas = self._function_calls[function]
        except KeyError:
            # This is the first time we've seen this function.
            return None, None

        # We've called this before, so search the data to see if we've called
        # it with the same arguments.
        for index, (old_bound, old_result) in enumerate(datas):
            if bound == old_bound:
                # We've found a matching call so just return the index.
                return index, old_result

        # Turns out we haven't called it with these args.
        return None, None


    def save_call(self, fun_name, call_id, bound, result):
        """Insert or update the function call."""

        # Make sure we got the right types.
        assert isinstance(call_id, (type(None), int))
        assert isinstance(fun_name, str)
        assert isinstance(bound, dict)

        try:
            datas = self._function_calls[fun_name]
        except KeyError:
            # The function be new or may have been deleted. So ignore the
            # call_id and just create a new list.
            self._function_calls[fun_name] = [(bound, result)]
            return 0
        else:
            if call_id is None:
                datas.append((bound, result))
                return len(datas) - 1
            else:
                datas[call_id] = (bound, result)
        return call_id

    # --------------------------------------------------------------------------

    def find_call_file(self, call_id, fun_name, file_name):
        """Returns the digest of the file from the last time we called this
        function, or None if it does not exist."""

        try:
            return self._call_files[file_name][fun_name][call_id]
        except KeyError:
            # This is the first time we've seen this file with this call.
            return None


    def save_call_file(self, call_id, fun_name, file_name, digest):
        """Insert or update the call file."""

        # Make sure we got the right types.
        assert isinstance(call_id, int)
        assert isinstance(fun_name, str)
        assert isinstance(file_name, str)
        assert isinstance(digest, str)

        self._call_files. \
            setdefault(file_name, {}).\
            setdefault(fun_name, {})[call_id] = digest

    # --------------------------------------------------------------------------

    def find_external_srcs(self, call_id, fun_name):
        """Returns all of the externally specified call src files"""

        try:
            return self._external_srcs[fun_name][call_id]
        except KeyError:
            return set()


    def find_external_dsts(self, call_id, fun_name):
        """Returns all of the externally specified call dst files"""

        try:
            return self._external_dsts[fun_name][call_id]
        except KeyError:
            return set()


    def save_external_files(self, fun_name, call_id, srcs, dsts, digests):
        """Insert or update the externall specified call files."""

        # Make sure we got the right types.
        assert isinstance(call_id, int)
        assert isinstance(fun_name, str)
        assert all(isinstance(src, str) for src in srcs)
        assert all(isinstance(dst, str) for dst in dsts)
        assert all(isinstance(src, str) and isinstance(digest, str)
            for src, digest in digests)

        self._external_srcs.setdefault(fun_name, {})[call_id] = srcs
        self._external_dsts.setdefault(fun_name, {})[call_id] = dsts

        self.save_call_files(call_id, fun_name, digests)

    # --------------------------------------------------------------------------

    def find_file(self, file_name):
        """Returns the mtime and digest of the file, or None if it does not
        exist."""

        try:
            return self._files[file_name]
        except KeyError:
            return None, None


    def save_file(self, file_name, mtime, digest):
        """Insert or update the file."""

        # Make sure we got the right types.
        assert isinstance(file_name, str)
        assert isinstance(mtime, float)
        assert isinstance(digest, str)

        self._files[file_name] = (mtime, digest)


    def delete_file(self, file_name):
        """Remove the file from the database."""

        try:
            del self._files[file_name]
        except KeyError:
            pass

        # And delete all of the related call files.
        try:
            del self._call_files[file_name]
        except KeyError:
            pass

# ------------------------------------------------------------------------------

class _Pickler(pickle._Pickler):
    """Create a custom pickler that won't try to pickle the context."""

    def __init__(self, ctx, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ctx = ctx

    def persistent_id(self, obj):
        if obj is self.ctx:
            return 'ctx'
        else:
            return None

class _Unpickler(pickle._Unpickler):
    """Create a custom unpickler that will substitute the current context."""

    def __init__(self, ctx, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ctx = ctx

    def persistent_load(self, pid):
        if pid == 'ctx':
            return self.ctx
        else:
            raise pickle.UnpicklingError('unsupported persistent object')
