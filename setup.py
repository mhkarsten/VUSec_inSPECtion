#!/usr/bin/env python3
"""
Sets up and runs infrastructure and test for instrumenting benchmarks
"""
import os

import infra.infra as inf
from infra.infra.packages import LLVM, LLVMPasses
from infra.infra.util import run, qjoin

llvm = LLVM(version='16.0.1', compiler_rt=True, patches=[])

class HelloWorld(inf.Target):
    name = 'hello-world'

    def is_fetched(self, ctx):
        return True

    def fetch(self, ctx):
        pass

    def build(self, ctx, instance):
        os.chdir(os.path.join(ctx.paths.root, self.name))

        run(ctx, [
            'make', '--always-make',
            'OBJDIR=' + self.path(ctx, instance.name),
            'CC=' + ctx.cxx,
            'CFLAGS=' + qjoin(ctx.cflags),
            'LDFLAGS=' + qjoin(ctx.ldflags),
        ])

    def link(self, ctx, instance):
        pass

    def binary_paths(self, ctx, instance):
        return [self.path(ctx, instance.name, 'hello')]

    def run(self, ctx, instance):
        os.chdir(self.path(ctx, instance.name))
        run(ctx, './hello', teeout=True, allow_error=True)

class PerfTrack(inf.Instance):
    def __init__(self, sanitizer_instance):
        self.san_instance = sanitizer_instance
        self.name = 'perf-' + self.san_instance.name
        self.perf_stats = ['instructions', 'cache-references', 'cache-misses', 'branches', 'branch-misses', 'faults', 'minor-faults', 'major-faults']

    def dependencies(self):
        yield self.san_instance.llvm

    def perf_command(self):
        stats = ','.join(self.perf_stats)
        return f'3> perf.out perf stat -e {stats} --log-fd 3'

    def configure(self, ctx):
        # Set the build environment (CC, CFLAGS, etc.) for the target program
        self.san_instance.configure(ctx)
        ctx.target_run_wrapper = self.perf_command()

    def prepare_run(self, ctx):
        pass

class LibMallocWrapper(inf.Instance):
    def __init__(self, sanitizer_instance):
        self.san_instance = sanitizer_instance
        self.name = 'libmallocwrapper-' + self.san_instance.name
        self.runtime = LibMallocwrapperRuntime()

    def dependencies(self):
        yield self.san_instance.llvm
        yield self.runtime

    def configure(self, ctx):
        # Set the build environment (CC, CFLAGS, etc.) for the target program
        libpath = self.runtime.path(ctx)
        self.san_instance.configure(ctx)
        self.runtime.configure(ctx)
        ctx.target_run_wrapper = f'LD_PRELOAD="{libpath}/libmallocwrap.so"'

    def prepare_run(self, ctx):
        libpath = self.runtime.path(ctx)

        ctx.target_run_wrapper = f'LD_PRELOAD="{libpath}/libmallocwrap.so"'

        prevlibpath = os.getenv('LD_PRELOAD', '').split(':')
        ctx.runenv.setdefault('LD_PRELOAD', prevlibpath).insert(0, f'{libpath}/libmallocwrap.so')


class LibStackTrack(inf.Instance):
    def __init__(self, sanitizer_instance):
        self.san_instance = sanitizer_instance
        passdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'llvm-passes')
        self.passes = LLVMPasses(self.san_instance.llvm, passdir, 'stacktrack', use_builtins=False, gold_passes=False, debug=True)
        self.runtime = LibStackTrackRuntime()
        self.name = 'libstacktrack-' + self.san_instance.name

    def dependencies(self):
        yield self.san_instance.llvm
        yield self.passes
        yield self.runtime

    def configure(self, ctx):
        # Set the build environment (CC, CFLAGS, etc.) for the target program
        self.san_instance.configure(ctx)
        self.passes.configure(ctx, linktime=False, new_pm=True)
        self.runtime.configure(ctx)

    def prepare_run(self, ctx):
        # Just before running the target, set LD_LIBRARY_PATH so that it can
        # find the dynamic library
        prevlibpath = os.getenv('LD_LIBRARY_PATH', '').split(':')
        libpath = self.runtime.path(ctx)
        ctx.runenv.setdefault('LD_LIBRARY_PATH', prevlibpath).insert(0, libpath)


# Custom package for our runtime library in the runtime/ directory
class LibStackTrackRuntime(inf.Package):
    def ident(self):
        return 'libstacktrack-runtime'

    def fetch(self, ctx):
        pass

    def build(self, ctx):
        os.chdir(os.path.join(ctx.paths.root, 'registeralloc_runtime'))
        
        run(ctx, [
            'make', '-j%d' % ctx.jobs,
            'OBJDIR=' + self.path(ctx),
            'LLVM_VERSION=' + llvm.version
        ])

    def install(self, ctx):
        pass

    def is_fetched(self, ctx):
        return True

    def is_built(self, ctx):
        return os.path.exists('libstacktrack.so')

    def is_installed(self, ctx):
        return self.is_built(ctx)

    def configure(self, ctx):
        ctx.ldflags += ['-L' + self.path(ctx), '-lstacktrack']

# Custom package for our runtime library in the runtime/ directory
class LibMallocwrapperRuntime(inf.Package):
    def ident(self):
        return 'libmallocwrapper-runtime'

    def fetch(self, ctx):
        pass

    def build(self, ctx):
        os.chdir(os.path.join(ctx.paths.root, 'mallocwrapper_runtime'))

        run(ctx, [
            'make', '-j%d' % ctx.jobs,
            'OBJDIR=' + self.path(ctx),
            'LLVM_VERSION=' + llvm.version
        ])

    def install(self, ctx):
        pass

    def is_fetched(self, ctx):
        return True

    def is_built(self, ctx):
        return os.path.exists('libmallocwrap.so')

    def is_installed(self, ctx):
        return self.is_built(ctx)

    def configure(self, ctx):
        # ctx.ldflags += ['-L' + self.path(ctx), '-lmallocwrap']
        pass


if __name__ == "__main__":
    setup = inf.Setup(__file__)

    setup.ctx.target_run_wrapper = 'LD_PRELOAD="/home/max/University/VU_Amsterdam/Year_3/Thesis/VUSec_inSPECtion/build/packages/libmallocwrapper-runtime/libmallocwrap.so"'

    # Basic Instances with no sanitizers
    setup.add_instance(inf.instances.Clang(llvm))
    setup.add_instance(inf.instances.Clang(llvm, lto=True)) # This is needed for many defenses

    # Sanitizer Instances with no other tooling
    setup.add_instance(inf.instances.ASan(llvm))
    setup.add_instance(inf.instances.MSan(llvm))
    setup.add_instance(inf.instances.UbSan(llvm))
    setup.add_instance(inf.instances.CFISan(llvm))
    setup.add_instance(inf.instances.SafeSan(llvm))

    # Sanitizer instances with StackTrack enabled
    setup.add_instance(LibStackTrack(inf.instances.ASan(llvm)))
    setup.add_instance(LibStackTrack(inf.instances.MSan(llvm)))
    setup.add_instance(LibStackTrack(inf.instances.UbSan(llvm)))
    setup.add_instance(LibStackTrack(inf.instances.SafeSan(llvm)))
    setup.add_instance(LibStackTrack(inf.instances.CFISan(llvm)))

    # Sanitizer instances with perf enabled
    setup.add_instance(PerfTrack(inf.instances.ASan(llvm)))
    setup.add_instance(PerfTrack(inf.instances.MSan(llvm)))
    setup.add_instance(PerfTrack(inf.instances.UbSan(llvm)))
    setup.add_instance(PerfTrack(inf.instances.SafeSan(llvm)))
    setup.add_instance(PerfTrack(inf.instances.CFISan(llvm)))

    # Sanitizer instances with Mallocwrapper enabled
    setup.add_instance(LibMallocWrapper(inf.instances.ASan(llvm)))
    setup.add_instance(LibMallocWrapper(inf.instances.MSan(llvm)))
    setup.add_instance(LibMallocWrapper(inf.instances.UbSan(llvm)))
    setup.add_instance(LibMallocWrapper(inf.instances.SafeSan(llvm)))
    setup.add_instance(LibMallocWrapper(inf.instances.CFISan(llvm)))


    # Dummy target for testing
    setup.add_target(HelloWorld())
    # Spec2006 target
    setup.add_target(inf.targets.SPEC2006(
        source=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'spec2006.iso'),
        source_type='isofile',
        patches=['dealII-stddef', 'omnetpp-invalid-ptrcheck', 'gcc-init-ptr', 'libcxx', 'asan']
    ))
    # Spec2017 target
    setup.add_target(inf.targets.SPEC2017(
        source=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'spec2017.iso'),
        source_type='isofile',
        patches=['asan']
    ))

    setup.main()
    