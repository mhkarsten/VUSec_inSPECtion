#!/usr/bin/env python3
"""
Sets up and runs infrastructure and test for instrumenting benchmarks
"""
import os
import datetime

import infra.infra as inf
from infra.infra.packages import LLVM, LLVMPasses
from infra.infra.util import run, qjoin

llvm = LLVM(version='16.0.1', compiler_rt=True, patches=[])

# LIST OF SHIT I HAVE TO DO
# Finish evaluation, write conclusions intros and juice up analysis                     X
# Write discussion, tak about future work and limitations of the testing methodology    X
# Write conclusion                                                                      X
# Update abstract                                                                       X                                                
# Insert new graphs into document                                                       X
# Reference new graphs in the paper                                                     X
# Add some assembly snipits into the paper                                              X
# Add references                                                                        X
# Add citations into the paper                                                          X
# Mention hardware used for tests in the design section                                 X
# Integrate feedback from supervisor                                                    X

# IF I HAVE TIME
# Remove CFI shit or investigate it
# Run extra tests to back up claims

# EXTRA TESTS
# 

# FINAL DRAFT REVIEW

#F FINAL DRAFT

class HelloWorld(inf.Target):
    name = 'hello-world'

    def is_fetched(self, ctx):
        return True

    def fetch(self, ctx):
        pass

    def build(self, ctx, instance):
        os.chdir(os.path.join(ctx.paths.root, "hello-world"))

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
        run(ctx, ctx.target_run_wrapper + ' ./hello', teeout=True, allow_error=True, shell=True)


class PerfTrack(inf.Instance):
    def __init__(self, sanitizer_instance):

        self.san_instance = sanitizer_instance
        self.name = 'perftrack-' + sanitizer_instance.name
        self.perf_stats = ['instructions', 'cache-references', 'cache-misses', 'branches', 
                           'branch-misses', 'faults', 'minor-faults', 'major-faults',
                           'dTLB-load-misses', 'dTLB-loads', 'dTLB-store-misses', 'dTLB-stores',
                           'L1-dcache-load-misses', 'L1-dcache-loads', 'L1-dcache-stores', 'L1-icache-load-misses',
                           'iTLB-load-misses', "iTLB-loads"]

    def perf_command(self, ctx):
        datestr = datetime.datetime.today().strftime("perftrack.%Y-%m-%d.%H-%M-%S")
        result_dir = os.path.join(ctx.paths.root, "results", datestr, self.name)
        stats = ','.join(self.perf_stats)
        # --call-graph dwarf
        return  f"""mkdir -p {result_dir}; \
                perf record -F 99 \
                -e {stats} -o {result_dir}/$benchmark.\$\$.data -g $command;"""

    def configure(self, ctx):
        # Add debugging flags to allow perf report better output
        cflags = ['-ggdb', '-fno-omit-frame-pointer']
        ctx.cflags += cflags
        ctx.cxxflags += cflags
        ctx.ldflags += cflags
        
        # set the run wrapper for spec and configure the sanitizer instance for compilation
        ctx.target_specrun_wrapper = self.perf_command(ctx)
        self.san_instance.configure(ctx)

    def prepare_run(self, ctx):
        self.san_instance.prepare_run(ctx)

class LibMallocTrack(inf.Instance):
    def __init__(self, sanitizer_instance):
        self.san_instance = sanitizer_instance
        self.runtime = LibMallocwrapperRuntime()
        self.name = 'libmalloctrack-' + self.san_instance.name
        self.so_name = "libmallocwrap.so"

    def dependencies(self):
        yield self.san_instance.llvm
        yield self.runtime

    def configure(self, ctx):
        # Set the build environment (CC, CFLAGS, etc.) for the target program
        result_dir = os.path.join(ctx.paths.root, "results", self.name)
        libpath = self.runtime.path(ctx)

        ctx.target_pre_bench = f"mkdir -p {result_dir}/$lognum/$iter"
        ctx.target_specrun_wrapper = f"""RESULT_OUT_FILE={result_dir}/$lognum/$benchmark.txt.\$\$ \
                                 LD_PRELOAD={libpath}/{self.so_name} $command"""

        self.san_instance.configure(ctx)
        self.runtime.configure(ctx)

    def prepare_run(self, ctx):
        self.san_instance.prepare_run(ctx);
        libpath = self.runtime.path(ctx)

        prevlibpath = os.getenv('LD_PRELOAD', '').split(':')
        ctx.runenv.setdefault('LD_PRELOAD', prevlibpath).insert(0, f'{libpath}/{self.so_name}')


class LibStackTrack(inf.Instance):
    def __init__(self, sanitizer_instance):
        self.san_instance = sanitizer_instance
        passdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'llvm-passes')
        self.passes = LLVMPasses(self.san_instance.llvm, passdir, 'stacktrack', use_builtins=False, gold_passes=False, debug=True)
        self.runtime = LibStackTrackRuntime()
        self.name = 'libstacktrack-' + self.san_instance.name
        self.so_name = "libstacktrack.so"

    def dependencies(self):
        yield self.san_instance.llvm
        yield self.passes
        yield self.runtime

    # Set the build environment (CC, CFLAGS, etc.) for the target program
    def configure(self, ctx):
        result_dir = os.path.join(ctx.paths.root, "results", self.name)
        libpath = self.runtime.path(ctx)

        # Set some context values for result collection for perf
        ctx.target_pre_bench = f"mkdir -p {result_dir}/$lognum"

        ctx.target_specrun_wrapper = f"""RESULT_OUT_FILE={result_dir}/$lognum/$benchmark.txt.\$\$ \
                                  LD_PRELOAD={libpath}/libstacktrack.so $command"""

        # Configure all used classes
        self.san_instance.configure(ctx)
        self.passes.configure(ctx, linktime=False, compiletime=False, new_pm=True)
        self.runtime.configure(ctx)

    def prepare_run(self, ctx):
        # Just before running the target, set LD_LIBRARY_PATH so that it can
        # find the dynamic library
        prevlibpath = os.getenv('LD_LIBRARY_PATH', '').split(':')
        libpath = self.runtime.path(ctx)
        ctx.runenv.setdefault('LD_LIBRARY_PATH', prevlibpath).insert(0, libpath)

        self.san_instance.prepare_run(ctx)

# Custom package for our runtime library in the runtime/ directory
class LibStackTrackRuntime(inf.Package):
    def ident(self):
        return 'libstacktrack-runtime'

    def fetch(self, ctx):
        pass

    def build(self, ctx):
        os.chdir(os.path.join(ctx.paths.root, 'runtime', 'registeralloc'))
        
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
        return 'libmalloctrack-runtime'

    def fetch(self, ctx):
        pass

    def build(self, ctx):
        os.chdir(os.path.join(ctx.paths.root, 'runtime', 'mallocwrapper'))

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
        pass

if __name__ == "__main__":
    setup = inf.Setup(__file__)

    # Basic Instances with no sanitizers
    setup.add_instance(inf.instances.Clang(llvm))
    setup.add_instance(inf.instances.Clang(llvm, lto=True)) # This is needed for many defenses
    setup.add_instance(PerfTrack(inf.instances.Clang(llvm, lto=True)))
    setup.add_instance(LibStackTrack(inf.instances.Clang(llvm, lto=True)))
    setup.add_instance(LibMallocTrack(inf.instances.Clang(llvm, lto=True)))

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
    setup.add_instance(LibMallocTrack(inf.instances.ASan(llvm)))
    setup.add_instance(LibMallocTrack(inf.instances.MSan(llvm)))
    setup.add_instance(LibMallocTrack(inf.instances.UbSan(llvm)))
    setup.add_instance(LibMallocTrack(inf.instances.SafeSan(llvm)))
    setup.add_instance(LibMallocTrack(inf.instances.CFISan(llvm)))


    # Dummy target for testing
    setup.add_target(HelloWorld())
    # Spec2006 target
    setup.add_target(inf.targets.SPEC2006(
        source=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'spec2006.iso'),
        source_type='isofile',
        patches=['dealII-stddef', 'omnetpp-invalid-ptrcheck', 'gcc-init-ptr', 'libcxx', 'asan', 'msan']
    ))
    # Spec2017 target
    setup.add_target(inf.targets.SPEC2017(
        source=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'spec2017.iso'),
        source_type='isofile',
        patches=['asan', 'msan']
    ))

    setup.main()
    