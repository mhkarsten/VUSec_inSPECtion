#!/usr/bin/env python3
import subprocess
import os
import seaborn as sns
import pandas as pd
import matplotlib.pyplot as plt

def collect_stack_results():
    pass

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
        # plt.show()
        plt.savefig(f"overhead-{instance_name}-{desired_stats[0]}")

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
        plt.savefig(f"overhead-{instance_name}-{desired_stats[0]}")

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
    
    #
    # BASELINE RESULTS
    #

    clang_baseline_res = collect_spec_results("results/run.old-clang-baseline", stats[:5], aggregates[15])

    # san_baseline_res = collect_spec_results("results/run.old-asan-baseline", stats[:5], aggregates[15])
    san_baseline_res = collect_spec_results("results/run.msan-baseline", stats[:5], aggregates[15])
    # san_baseline_res = collect_spec_results("results/run.cfi-baseline", stats[:5], aggregates[15])
    # san_baseline_res = collect_spec_results("results/run.ubsan-baseline", stats[:5], aggregates[15])

    # generate_overhead_bar(clang_baseline_res, san_baseline_res, ['runtime'], 'UBSan')
    #print_result_table(clang_baseline_res)
    #print_result_table(san_baseline_res)
    #print_result_table(overhead_as_percent(clang_baseline_res, san_baseline_res))

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
    test_name = "482.sphinx3"
    san_name = "MSan"
    generate_bench_bar(clang_perf_res,  san_perf_res, test_name, ['faults', 'minor-faults', 'major-faults'], f"{san_name} {test_name.split('.')[1]}")
    
    #generate_overhead_bar(clang_perf_res, san_perf_res, ['cache-misses', 'branch-misses'], 'asan')
    #generate_overhead_bar(clang_perf_res, san_perf_res, ['dTLB-load-misses', 'dTLB-store-misses', 'iTLB-load-misses'], 'asan')
    # print_result_table(overhead_as_percent(clang_perf_res, san_perf_res))
    # generate_perf_graphs(clang_perf_res, san_perf_res, 'msan')

    #
    # FLAME GRAPH RESULTS
    #

    # generate_flamegraph("results/perftrack.2023-07-07.20-09-46/perftrack-asan/400.perlbench.30423.data", "Asan-400.perlbench", "cache-misses")
    # generate_flamegraph("results/perftrack.clang-lto/perftrack-clang-lto/400.perlbench.10486.data", "Clang-400.perlbench", "cache-misses")
