import fbuild

# -----------------------------------------------------------------------------

class Package:
    def build(self, conf):
        raise NotImplemented

def build(src, conf):
    if isinstance(src, Package):
        return src.build(conf)
    return src
