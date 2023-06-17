#!/usr/bin/env python3
"""
Sets up and runs infrastructure and test for instrumenting benchmarks
"""
import os
from pandas import infer_freq

from pyparsing import infix_notation

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

class LibStackTrack(inf.Instance):
    name = 'libstacktrack'

    def __init__(self):
        passdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'llvm-passes')
        self.passes = LLVMPasses(llvm, passdir, 'stacktrack', use_builtins=False, gold_passes=False, debug=True)
        self.runtime = LibStackTrackRuntime()

    def dependencies(self):
        yield llvm
        yield self.passes
        yield self.runtime

    def configure(self, ctx):
        # Set the build environment (CC, CFLAGS, etc.) for the target program
        llvm.configure(ctx)
        self.passes.configure(ctx, linktime=False, new_pm=True)
        self.runtime.configure(ctx)
        # LLVM.add_plugin_flags(ctx, '-stacktrack', gold_passes=False)

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
        os.chdir(os.path.join(ctx.paths.root, 'runtime'))

        ctx.cflags += ["-mllvm", "-debug-only=stacktrack"]
        ctx.cxxflags += ["-mllvm", "-debug-only=stacktrack"]

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

ld_preload_command = 'LD_PRELOAD="utils/mallocwrapper.so"'

perf_stats = ['instructions', 'cache-references', 'cache-misses', 'branches', 'branch-misses', 'faults', 'minor-faults', 'major-faults']

def perf_command():
    stats = ','.join(perf_stats)
    return f'3> perf.out perf stat -e {stats} --log-fd 3'


if __name__ == "__main__":
    setup = inf.Setup(__file__)

    setup.ctx.target_run_wrapper = perf_command()
    # setup.ctx.target_run_wrapper = ld_preload_command

    # Basic Instances
    setup.add_instance(inf.instances.Clang(llvm))
    setup.add_instance(inf.instances.Clang(llvm, lto=True)) # This is needed for many defenses

    # Sanitizer Instances
    setup.add_instance(inf.instances.ASan(llvm))
    setup.add_instance(inf.instances.MSan(llvm))
    setup.add_instance(inf.instances.UbSan(llvm))
    setup.add_instance(inf.instances.CFISan(llvm))
    setup.add_instance(inf.instances.SafeSan(llvm))


    setup.add_instance(LibStackTrack())

    # Dummy target for testing
    setup.add_target(HelloWorld())

    # Benchmark Targets
    setup.add_target(inf.targets.SPEC2006(
        source=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'spec2006.iso'),
        source_type='isofile',
        patches=['dealII-stddef', 'omnetpp-invalid-ptrcheck', 'gcc-init-ptr', 'libcxx', 'asan']
    ))

    
    # setup.add_target(inf.targets.SPEC2017(
    #     source=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'spec2017.iso'),
    #     source_type='isofile',
    #     patches=['asan']
    # ))

    setup.main()
    