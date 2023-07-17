#!/usr/bin/env python3
import subprocess
import os
import seaborn as sns
import pandas as pd
import matplotlib.pyplot as plt

RES_DIR = os.path.join(os.getcwd(), "results", "figures")

def collect_stack_results():

    pass

def collect_malloc_results(result_dir, valid_benches):

    result_dict = {}
    for (_, __, files) in os.walk(result_dir):
        for test_file in files:
            bench_name = test_file.split('.')
            bench_name = '.'.join([bench_name[0], bench_name[1]])

            if bench_name not in valid_benches:
                continue
            
            if bench_name not in result_dict.keys():
                result_dict[bench_name] = {}

            with open(os.path.join(result_dir, test_file), 'r', encoding='utf-8') as f:
                results = f.readlines()

                for line in results:
                    toks = line.split(',')

                    result_dict[bench_name][int(toks[1].split(':')[1].strip())] = {
                        'count': int(toks[0].split(':')[1].strip()),
                        'type': toks[2].split(':')[1].strip()
                    }
        break
    
    return result_dict

def sum_heap_allocations(allocations, benchmark, types, sum_size):

    sum = 0
    for size, vals in allocations[benchmark].items():
        if vals['type'] not in types:
            continue
        
        if sum_size:
            sum += (size * vals['count'])
        else:
            sum += vals['count']

    return sum

def collect_perf_results(result_folder, stats, valid_benches):
    cmd = f"""perf report --stdio --stats \
    -i {result_folder}"""

    result_dict = {}
    for (_, __, files) in os.walk(result_folder):
        for test_file in files:
            bench_name = test_file.split('.')
            bench_name = '.'.join([bench_name[0], bench_name[1]])

            if bench_name not in valid_benches:
                continue

            result = subprocess.run(cmd + "/" + test_file, shell=True, capture_output=True, check=False)
            result = result.stdout.decode('utf-8').split('\n');

            result_dict[bench_name] = {}
            for i, line in enumerate(result):
                stat_name = line.split(':')[0]
                if stat_name in stats:
                    stat_value = float(result[i + 1].split(':')[1].strip())
                    result_dict[bench_name][stat_name] = stat_value
        break
    
    return result_dict

def collect_spec_results(result_file, stats, aggregate):
    stat_list = map(lambda x:":".join([x, aggregate]), stats)

    cmd = f"""./setup.py report spec2006 {result_file} \
    --table tsv \
    -f {" ".join(stat_list)}"""

    result = subprocess.run(cmd, shell=True, capture_output=True, check=False)

    output_table = result.stdout.decode("utf-8").split('\n')
    # out_stats = list(map(lambda x: x.strip('\r'), output_table[0].split("\t")))

    output_table = output_table[1:-1]

    result_dict = {}
    for entry in output_table:
        res = list(map(lambda x: x.strip('\r'), entry.split("\t")))
        result_dict[res[0]] = dict(zip(stats, list(map(lambda x: float(x) if "-" not in x else x, res[1:]))))

    return result_dict

def is_valid_result_file(name):
    return (".err" in name or '.stderr' in name) and "spec" not in name and "compare" not in name

# Overhead of test a over test b
def heap_overhead_as_percent(test_a, test_b):

    overheads = {}
    for size, vals in test_a.items():
        if size not in test_b.keys():
            overheads[size] = vals['count']
        else:
            diff = test_b[size]['count'] - test_a[size]['count']
            overheads[size] = (diff / vals['count']) * 100

    return overheads

def overhead_as_percent(base_res, san_res):
    overheads = {}

    for bench, san_stats in san_res.items():
        if "-" not in san_stats.values():
            base_values = base_res[bench]
            for name, value in san_stats.items():
                if bench not in overheads.keys():
                    overheads[bench] = {}
                
                # This is mainly here for major-faults in perf stats which is sometimes 0 so not included
                if name not in base_values.keys():
                    base_values[name] = 0

                if base_values[name] != 0:
                    diff = value - base_values[name]
                    overheads[bench][name] = (diff / base_values[name]) * 100
                else:
                    overheads[bench][name] = value
        else:
            print(f"Failed test: {bench}")

    return overheads

def generate_bench_bar(base_res, san_res, desired_bench, desired_stats, instance_name, ax=None):
    overhead = overhead_as_percent(base_res, san_res)

    plot = False
    if ax is None:
        plot = True
    
    # Remove unndeeded stats:
    for stat in desired_stats:
        if stat not in overhead[desired_bench].keys():
            overhead[desired_bench][stat] = 0

    overhead[desired_bench] = dict(filter(lambda x: x[0] in desired_stats, overhead[desired_bench].items()))
    
    # Form the stat array for the dataframe
    df_stats = {
        "perf Statistic": overhead[desired_bench].keys(),
        "Overhead percentage": overhead[desired_bench].values()
    }
        
    df = pd.DataFrame(df_stats, index=overhead[desired_bench].keys())

    if ax is not None:
        df.plot.barh(rot=0, legend=True, ax=ax)
    else:
        ax = df.plot.barh(rot=0, legend=True)

    ax.set_xlabel("Overhead Percentage")
    ax.set_ylabel("Benchmark")
    ax.set_title(f"Overhead: {instance_name.capitalize()}")

    if plot:
        plt.subplots_adjust(left=0.25)
        plt.savefig(os.path.join(RES_DIR, f"overhead-{instance_name}-{desired_stats[0]}"))

def gernerate_heap_bar(heap_res, tests, valid_types, instance_name, ax=None):
    plot = False if ax is None else True
    
    if len(tests) > 2:
        print("Cannot compare more than two tests")
        return
    
    valid_allocs_a = dict(filter(lambda x: x[1]['type'] in valid_types, heap_res[tests[1]].items()))
    valid_allocs_b = dict(filter(lambda x: x[1]['type'] in valid_types, heap_res[tests[0]].items()))

    overhead = heap_overhead_as_percent(valid_allocs_a, valid_allocs_b)

    overhead = dict(sorted(overhead.items()))

    # Remove ones with 0 overhead, just for clarity
    overhead = dict(filter(lambda x: x[1] != 0, overhead.items()))

    df_stats = {
        'counts': overhead.values(),
        'sizes': list(map(str, overhead.keys()))
    }

    df = pd.DataFrame(df_stats, index=overhead.keys())

    if ax is not None:
        df.plot.bar(rot=0, legend=True, ax=ax)
    else:
        ax = df.plot.bar(rot=0, legend=True)

    ax.set_xlabel("Allocation Size")
    ax.set_ylabel("Allocation Count")
    ax.tick_params(axis='x', labelrotation=-60)
    ax.set_title(f"Heap Allocation Difference: {instance_name.capitalize()}")
    ax.axhline()

    if plot:
        plt.subplots_adjust(left=0.25)
        plt.savefig(os.path.join(RES_DIR, f"heap-allocations-{instance_name}"))


def generate_overhead_bar(base_res, san_res, desired_stats, instance_name, ax=None):
    overhead = overhead_as_percent(base_res, san_res)

    plot = False
    if ax is None:
        plot = True

    for bench, stats in overhead.items():
        for stat in desired_stats:
            if stat not in stats.keys():
                stats[stat] = 0

        overhead[bench] = dict(filter(lambda x: x[0] in desired_stats, stats.items()))

    # Form the stat array for the dataframe
    df_stats = {}
    for bench, stats in overhead.items():
        for name, value in stats.items():
            if name not in df_stats.keys():
                df_stats[name] = []
            
            df_stats[name] += [value]


    df = pd.DataFrame(df_stats, index=overhead.keys())

    if ax is not None:
        df.plot.barh(rot=0, legend=True, ax=ax)
    else:
        ax = df.plot.barh(rot=0, legend=True)

    ax.set_xlabel("Overhead Percentage")
    ax.set_ylabel("Benchmark")
    ax.set_title(f"Overhead: {instance_name.capitalize()}")

    if plot:
        plt.subplots_adjust(left=0.25)
        plt.savefig(os.path.join(RES_DIR, f"overhead-{instance_name}-{desired_stats[0]}"))

def generate_flamegraph(result_file, instance_name, desired_stat):
    res_dir = os.path.join(os.getcwd(), 'results', 'flamegraphs')
    subprocess.run(f"mkdir -p {res_dir}", check=False, shell=True)

    folded_path = f"{res_dir}/{instance_name}.flame.perf-folded"

    # Run stack collapse, put into temp file, also filter for event
    collapse_cmd = f"""perf script -i {result_file} | \
    stackcollapse-perf.pl --event-filter={desired_stat}:u > {folded_path}"""
    subprocess.run(collapse_cmd, shell=True, check=False)


    # run flame graph into svg
    flame_cmd = f"""flamegraph.pl \
    --title "{instance_name.capitalize()}: {desired_stat.capitalize()} Flamegraph" \
    {folded_path} > {res_dir}/{instance_name}.flame.svg"""
    subprocess.run(flame_cmd, shell=True, check=False)

def generate_perf_graphs(base_res, san_res, instance):

    plt.figure(1)

    plt.subplot(2, 3, 1)
    generate_overhead_bar(base_res, san_res, ['instructions', 'branches', 'cache-references'], instance, ax=plt.gca())

    plt.subplot(2, 3, 2)
    generate_overhead_bar(base_res, san_res, ['cache-misses', 'branch-misses'], instance, ax=plt.gca())

    plt.subplot(2, 3, 3)
    generate_overhead_bar(base_res, san_res, ['L1-dcache-load-misses', 'L1-dcache-loads', 'L1-dcache-stores', 'L1-icache-load-misses'], instance, ax=plt.gca())
    
    plt.subplot(2, 3, 4)
    generate_overhead_bar(base_res, san_res, ['dTLB-load-misses', 'dTLB-loads', 'dTLB-store-misses', 'dTLB-stores'], instance, ax=plt.gca())
    # generate_overhead_bar(base_res, san_res, ['dTLB-load-misses', 'dTLB-loads', 'dTLB-stores', "iTLB-loads"], instance, ax=plt.gca())
    
    plt.subplot(2, 3, 5)
    generate_overhead_bar(base_res, san_res, ['iTLB-load-misses', "iTLB-loads"], instance, ax=plt.gca())

    plt.subplot(2, 3, 6)
    generate_overhead_bar(base_res, san_res, ['faults', 'minor-faults', 'major-faults'], instance, ax=plt.gca())
    
    plt.subplots_adjust(hspace=0.25, wspace=0.5)
    plt.show()


def generate_base_graphs(base_res, san_res, instance):

    plt.figure(1)

    plt.subplot(2, 3, 1)
    generate_overhead_bar(base_res, san_res, ["runtime"], instance, ax=plt.gca())

    plt.subplot(2, 3, 2)
    generate_overhead_bar(base_res, san_res, ["maxrss"], instance, ax=plt.gca())

    plt.subplot(2, 3, 3)
    generate_overhead_bar(base_res, san_res, ["io_operations"], instance, ax=plt.gca())
    
    plt.subplot(2, 3, 4)
    generate_overhead_bar(base_res, san_res, ["page_faults"], instance, ax=plt.gca())

    plt.subplot(2, 3, 5)
    generate_overhead_bar(base_res, san_res, ["context_switches"], instance, ax=plt.gca())

    plt.subplots_adjust(hspace=0.25, wspace=0.5)
    plt.show()

def print_result_table(result):
    for bench, stats in result.items():
        print(f"Benchmark name: {bench}")
        for stat, value in stats.items():
            print(f"Stat: {stat}, Value: {value}")

if __name__ == "__main__":
    stats =      [  "runtime", "maxrss", "io_operations", "page_faults", 
                    "context_switches", "status"]

    aggregates = [  "mean", "median", "stdev", "stdev_percent", 
                    "variance", "mad", "min", "max", 
                    "sum", "count", "same", "one", 
                    "first", "all", "sort", "geomean"]

    perf_stats = [  'instructions', 'cache-references', 'cache-misses', 'branches',
                    'branch-misses', 'faults', 'minor-faults', 'major-faults',
                    'dTLB-load-misses', 'dTLB-loads', 'dTLB-store-misses', 'dTLB-stores',
                    'L1-dcache-load-misses', 'L1-dcache-loads', 'L1-dcache-stores', 'L1-icache-load-misses',
                    'iTLB-load-misses', "iTLB-loads"]
    
    
    test_name = "482.sphinx3"
    san_name = "MSan"

    #
    # BASELINE RESULTS
    #

    clang_baseline_res = collect_spec_results("results/run.old-clang-baseline", stats[:5], aggregates[15])

    # san_baseline_res = collect_spec_results("results/run.old-asan-baseline", stats[:5], aggregates[15])
    san_baseline_res = collect_spec_results("results/run.msan-baseline", stats[:5], aggregates[15])
    # san_baseline_res = collect_spec_results("results/run.cfi-baseline", stats[:5], aggregates[15])
    # san_baseline_res = collect_spec_results("results/run.ubsan-baseline", stats[:5], aggregates[15])

    # generate_overhead_bar(clang_baseline_res, san_baseline_res, ['runtime'], 'UBSan')
    
    # print_result_table(clang_baseline_res)
    
    # print_result_table(san_baseline_res)
    
    # print_result_table(overhead_as_percent(clang_baseline_res, san_baseline_res))

    # generate_base_graphs(clang_baseline_res, san_baseline_res, 'msan')

    #
    # PERF RESULTS
    #

    clang_perf_res = collect_perf_results("results/perftrack.clang-lto/perftrack-clang-lto", perf_stats, list(clang_baseline_res.keys()))
    
    valid_benches = list(dict(filter(lambda x: '-' not in x[1].values(), san_baseline_res.items())).keys())
    san_perf_res = collect_perf_results("results/perftrack.msan/perftrack-msan", perf_stats, valid_benches)
    # san_perf_res = collect_perf_results("results/perftrack.cfi/perftrack-cfi-vis-hidden", perf_stats, valid_benches)
    # san_perf_res = collect_perf_results("results/perftrack.ubsan/perftrack-ubsan-default", perf_stats, valid_benches)
    # san_perf_res = collect_perf_results("results/perftrack.asan/perftrack-asan", perf_stats, valid_benches)

    # generate_bench_bar(clang_perf_res,  san_perf_res, test_name, ['faults', 'minor-faults', 'major-faults'], f"{san_name} {test_name.split('.')[1]}")
    
    # generate_overhead_bar(clang_perf_res, san_perf_res, ['cache-misses', 'branch-misses'], 'asan')
    
    # generate_overhead_bar(clang_perf_res, san_perf_res, ['dTLB-load-misses', 'dTLB-store-misses', 'iTLB-load-misses'], 'asan')
    
    # print_result_table(overhead_as_percent(clang_perf_res, san_perf_res))
    
    # generate_perf_graphs(clang_perf_res, san_perf_res, 'msan')
    
    #
    # HEAP RESULTS
    #
    heap_asan_res = collect_malloc_results("results/libmalloctrack-asan/1338", ['400.perlbench', '462.libquantum'])

    sum_perl = sum_heap_allocations(heap_asan_res, '400.perlbench', ['Malloc', 'Calloc'], True)
    sum_lib = sum_heap_allocations(heap_asan_res, '462.libquantum', ['Malloc', 'Calloc'], True)

    gernerate_heap_bar(heap_asan_res, ['400.perlbench', '462.libquantum'], ['Malloc', 'Calloc'], 'perlbench - libquantum')
    

    #
    # FLAME GRAPH RESULTS
    #

    # generate_flamegraph("results/perftrack.2023-07-07.20-09-46/perftrack-asan/400.perlbench.30423.data", "Asan-400.perlbench", "cache-misses")
    
    # generate_flamegraph("results/perftrack.clang-lto/perftrack-clang-lto/400.perlbench.10486.data", "Clang-400.perlbench", "cache-misses")

    #
    # FURTHER TESTING
    #

    ### ASan no quarantine

    ### MSan no complex propagations

    ### UBSan no instrument on VDot

    ### ASan Allocations

    ### UBSan disable subset

