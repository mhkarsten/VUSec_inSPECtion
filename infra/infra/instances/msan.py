from .clang import Clang
from ..packages import LLVM
from ..util import param_attrs

# pylint: disable=E1101

class MSan(Clang):
    """
    Memory Sanitizer instance. Added ``-fsanitize=memory`` plus any
    configuration options at compile time and link time, and sets
    ``MSAN_OPTIONS`` at runtime.

    :name: msan[-track-origins][-use-after-destroy]
    :param llvm: an LLVM package with compiler-rt included
    :param track_origins: Whether to track the origins of uninitialized values (set to 1 or 2 to enable)
    :param use_after_destroy: Whether to disable use after destroy detection
    :param lto: perform link-time optimizations
    """
    @param_attrs
    def __init__(self, llvm: LLVM, *, track_origins=0, use_after_destroy=False, lto=False, optlevel=2):
        super().__init__(llvm, lto=lto, optlevel=optlevel)

    @property
    def name(self):
        name = "msan-noc"

        if self.track_origins != 0:
            name += "-track-origins"

        if self.use_after_destroy:
            name += "-use-after-destroy"

        return name

    def configure(self, ctx):
        super().configure(ctx)

        cflags = ['-fsanitize=memory']
        cflags += ['-g', '-fno-omit-frame-pointer']

        if self.track_origins is not None:
            cflags += [f"-fsanitize-memory-track-origins={self.track_origins}"]

        if self.use_after_destroy:
            cflags += ["-fno-sanitize-memory-use-after-dtor"]
        
        ctx.cflags += cflags
        ctx.cxxflags += cflags
        ctx.ldflags += ['-fsanitize=memory']
        ctx.ldflags += ['-g', '-fno-omit-frame-pointer']

    def prepare_run(self, ctx):
        opts = {}

        if self.use_after_destroy:
            opts['poison_in_dtor'] = 0

        ctx.runenv.MSAN_OPTIONS = ':'.join('%s=%s' % i for i in opts.items())
        
