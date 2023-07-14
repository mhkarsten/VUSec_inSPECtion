from numpy import True_
from .clang import Clang
from ..packages import LLVM
from ..util import param_attrs

# pylint: disable=E1101

class CFISan(Clang):
    """
    Control Flow Integrity Sanitizer instance. Added ``-fsanitize=cfi`` plus any
    configuration options at compile time and link time.

    :name: cfi[-{schemes}][-shared-support][-vis-{visibility}]
    :param llvm: an LLVM package with compiler-rt included
    :param san_schemes: An explicit list of cfi schemes to instrument
    :param no_san_schemes: An explicit list of cfi schemes not to instrument
    :param visibility: The LTO visibility of classes to instrument, default is set to hidden to enable checks for classes without vis data
    :param trap_schemes: A list of cfi schemes for which to trap instead of abort. Allows diagnostics
    :param recover_schemes: A list of cfi schemes for which to continue instead of abort
    :param so_support: Enable shared library support
    """
    @param_attrs
    def __init__(self, llvm: LLVM, *, san_schemes=None, no_san_schemes=None, visibility="hidden",
                 trap_schemes=None, recover_schemes=None, so_support=False, optlevel=2):
        super().__init__(llvm, lto=True, optlevel=optlevel)

        other_schemes = []
        if trap_schemes:
            other_schemes += trap_schemes
        
        if recover_schemes:
            other_schemes += recover_schemes
        
        # Ensure all checks in trap and recover get added to fsanitize so that the sanitizer gets activated
        if san_schemes is not None:
            for scheme in other_schemes:
                if scheme not in san_schemes:
                    san_schemes += scheme

        # ensure no contradictions in options
        for scheme in other_schemes:
            assert scheme not in no_san_schemes

    @property
    def name(self):
        name = "cfi"

        if self.san_schemes is not None:
            name += "-" + "-".join(self.san_schemes)

        if self.so_support:
            name += "-shared-support"
        
        name += f'-vis-{self.visibility}'

        return name

    def configure(self, ctx):
        super().configure(ctx)

        schemes = "cfi" if self.san_schemes is None else ",".join(self.san_schemes)

        cflags = [f"-fsanitize={schemes}"]
        cflags += ['-g', '-fno-omit-frame-pointer', '-flto']
        cflags += [f"-fvisibility={self.visibility}"]

        if self.so_support:
            cflags += ["-fsanitize-cfi-cross-dso"]

        if self.san_schemes is not None and "mf-call" in self.san_schemes:
            cflags += ["-fcomplete-member-pointers"]
        
        if self.no_san_schemes:
            cflags += [f"-fno-sanitize={','.join(self.no_san_schemes)}"]

        if self.trap_schemes:
            cflags += [f"-fsanitize-trap={','.join(self.trap_schemes)}"]

        if self.recover_schemes:
            cflags += [f"-fno-sanitize-recover={','.join(self.recover_schemes)}"]
        
        ctx.cflags += cflags
        ctx.cxxflags += cflags
        ctx.ldflags += [f"-fsanitize={schemes}"]
        ctx.ldflags += ['-g', '-fno-omit-frame-pointer', '-flto', "-fuse-ld=lld"]

        # Use the llvm linker for lto support
        ctx.ld = "/home/max/University/VU_Amsterdam/Year_3/Thesis/VUSec_inSPECtion/build/packages/llvm-16.0.1-lld/install/bin/lld"