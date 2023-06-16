from .clang import Clang
from ..packages import LLVM
from ..util import param_attrs

class SafeSan(Clang):
    """
    safe Stack Sanitizer instance. Added ``-fsanitize=safe-stack`` plus any
    configuration options at compile time and link time.

    :name: msan[-track-origins][-use-after-destroy]
    :param llvm: an LLVM package with compiler-rt included
    :param lto: perform link-time optimizations
    """
    @param_attrs
    def __init__(self, llvm: LLVM, *, lto=False, optlevel=2):
        super().__init__(llvm, lto=lto, optlevel=optlevel)

    @property
    def name(self):
        name = "safe-stack"

        return name

    def configure(self, ctx):
        super().configure(ctx)

        cflags = ['-fsanitize=safe-stack']
        cflags += ['-g', '-fno-omit-frame-pointer']
        
        ctx.cflags += cflags
        ctx.cxxflags += cflags
        ctx.ldflags += ['-fsanitize=safe-stack']
        ctx.ldflags += ['-g', '-fno-omit-frame-pointer']