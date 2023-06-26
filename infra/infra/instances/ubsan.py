from .clang import Clang
from ..packages import LLVM
from ..util import param_attrs

# pylint: disable=E1101

class UbSan(Clang):
    """
    Undefined Behavior Sanitizer instance. Added ``-fsanitize=[checks]`` plus any
    configuration options at compile time and link time, and sets
    ``UBSAN_OPTIONS`` at runtime.

    These runtime options are currently hardcoded to the following:

    - ``silence_unsigned_overflow=0``
    - ``print_stacktrace=1``


    :name: ubsan[-checks][-strip][-minimal]
    :param llvm: an LLVM package with compiler-rt included
    :param san_checks: The list of undefined behavior checks to instrument
    :param no_checks: The list of undefined behavior to not instrument
    :param trap_checks: The list of undefined behavior that execute a trap instruction
    :param no_recover_checks: The list of checks that cause an error to be printed and the program to exit
    :param strip_path: Whether to strip path components from inserted check data
    :param minimal_rt: Whether to use the minimal runtime for ubsan
    :param rt_suppression: Enable runtime suppressions. Provide a .supp file with desired suppressions
    :param lto: perform link-time optimizations
    """
    @param_attrs
    def __init__(self, llvm: LLVM, *, san_checks=None, no_cheks=None, trap_checks=None, no_recover_checks=None,
                 strip_path=None, minimal_rt=False, rt_suppression=False, default_checks=True, lto=False, optlevel=2):
        super().__init__(llvm, lto=lto, optlevel=optlevel)

        if default_checks:
            self.san_checks = ["bounds", "vla-bound", "pointer-overflow"]

        # Ensure all checks in trap and recover get added to fsanitize so that the sanitizer gets activated
        other_checks = []
        if trap_checks:
            other_checks += trap_checks
        
        if no_recover_checks:
            other_checks += no_recover_checks

        for check in other_checks:
            if check not in san_checks:
                san_checks += check

    @property
    def name(self):
        name = "ubsan"
        
        if self.default_checks:
            name += "-default"
        if not self.default_checks and self.san_checks:
            name += "-" + "-".join(self.san_checks)

        if self.strip_path:
            name += "-strip" + f"-{self.strip_path}"

        if self.minimal_rt:
            name += "-minimal-rt"

        return name

    def configure(self, ctx):
        super().configure(ctx)

        checks = ",".join(self.san_checks)

        cflags = [f'-fsanitize={checks}']
        cflags += ['-g', '-fno-omit-frame-pointer']
        
        if self.minimal_rt:
            cflags += ["-fsanitize-minimal-runtime"]

        if self.strip_path is not None:
            cflags += [f"-fsanitize-undefined-strip-path-components={self.strip_path}"]

        if self.no_checks:
            cflags += [f"-fno-sanitize={','.join(self.no_checks)}"]

        if self.trap_checks:
            cflags += [f"-fsanitize-trap={','.join(self.trap_checks)}"]

        if self.no_recover_checks:
            cflags += [f"-fno-sanitize-recover={','.join(self.no_recover_checks)}"]

        ctx.cflags += cflags
        ctx.cxxflags += cflags
        ctx.ldflags += ['-g', '-fno-omit-frame-pointer']
        ctx.ldflags += [f'-fsanitize={checks}']

    def prepare_run(self, ctx):
        opts = {
            'silence_unsigned_overflow': 0,
            'print_stacktrace': 1
        }

        if self.rt_suppressions is not None:
            opts['suppressions'] = self.rt_suppressions

        ctx.runenv.UBSAN_OPTIONS = ':'.join('%s=%s' % i for i in opts.items())