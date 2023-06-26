#!/usr/bin/env python3
import subprocess

# Subset can be a list of all (or none) of [stack, heap, perf]
def run_test_set(instance, iterations=1, subset=[]):
    run_cmd = f"./setup.py run spec2006 --build -i {iterations} --parallel=proc --parallelmax=1 "

    # run base test with no instrumentation
    no_inst_cmd = run_cmd + instance
    subprocess.run(no_inst_cmd, check=False, shell=True)

    # run test with perf instrumentation
    perf_cmd = run_cmd + "perftrack-" + instance
    subprocess.run(perf_cmd, check=False, shell=True)
    
    # run test with libstacktrack instrumentation
    if 'stack' in subset:
        stack_cmd = run_cmd + "libstacktrack-" + instance
        subprocess.run(stack_cmd, check=False, shell=True)

    # run a test with libmalloctrack instrumentation
    if 'heap' in subset:
        stack_cmd = run_cmd + "libmalloctrack-" + instance
        subprocess.run(stack_cmd, check=False, shell=True)

if __name__ == "__main__":
    sanitizer_instances = ['asan', 'msan', 'ubsan-default', 'cfi-vis-hidden', 'clang-lto']
    iters = 3

    # Run the tests for clang-lto for baseline values
    run_test_set(sanitizer_instances[4], iters)

    # Run the tests for asan
    # run_test_set(sanitizer_instances[0], iters)

    # Run the tests for msan
    # run_test_set(sanitizer_instances[1], iters)

    # Run the tests for cfi
    # run_test_set(sanitizer_instances[3], iters)

    # Run the tests for undefined behavior
    # run_test_set(sanitizer_instances[2], iters)