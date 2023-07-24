#!/usr/bin/env python3
from re import S
import subprocess
import os
import seaborn as sns
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib as mpl
import numpy as np

RES_DIR = os.path.join(os.getcwd(), "results", "figures")
graph_counter = 0

def collect_stack_results(result_dir, valid_benches):
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

                    result_dict[bench_name][int(toks[0].split(':')[1].strip())] = {
                        'count': int(toks[0].split(' ')[0].strip()),
                        'type': toks[1].split(':')[1].strip()
                    }
        break
    
    return result_dict

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
        # else:
        #     print(f"Failed test: {bench}")

    return overheads

def generate_bench_bar(base_res, san_res, desired_bench, desired_stats, instance_name, ax=None):
    overhead = overhead_as_percent(base_res, san_res)

    plot = ax is None
    
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
        plt.savefig(os.path.join(RES_DIR, f"bench-{instance_name}-{desired_stats[0]}.pdf"))

def gernerate_heap_bar(heap_res, tests, valid_types, instance_name, ax=None):
    plot = ax is None
    
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
        plt.savefig(os.path.join(RES_DIR, f"heap-allocations-{instance_name}.pdf"))

def generate_bench_comparison_bar(base_res, before_res, after_res, desired_stat, instance_name, ax=None):
    plot = ax is None
    
    overhead_before = overhead_as_percent(base_res, before_res)
    overhead_after = overhead_as_percent(base_res, after_res)

    valid_benches = []
    for key in overhead_before.keys():
        if key in overhead_after.keys():
            valid_benches += [key]

    # Ensure both sets have all needed results
    df_stats = {}
    df_stats['value'] = []
    df_stats['type'] = []
    df_stats['bench'] = []
    for bench in valid_benches:
        df_stats['bench'] += [bench, bench]
        df_stats['type'] += ['before', 'after']
        df_stats['value'] += [overhead_before[bench][desired_stat], overhead_after[bench][desired_stat]]

    # Form the stat array for the dataframe
    
    df = pd.DataFrame(df_stats, index=df_stats['bench'])

    ax = sns.barplot(
        df,
        x='value',
        y='bench',
        orient='h',
        hue='type',
        palette='mako'
    )

    ax.set_xlabel(f"{desired_stat.capitalize()} Overhead %")
    ax.set_ylabel("Benchmark")
    ax.legend(loc=1)
    ax.set_title(f"{desired_stat.capitalize()} Comparison: {instance_name}")

    if plot:
        plt.subplots_adjust(left=0.3)
        plt.savefig(os.path.join(RES_DIR, f"bench-compare-{instance_name}-{desired_stat}.pdf"))

def generate_comparison_bar(base_res, before_res, after_res, bench_name, desired_stats, instance_name, ax=None):
    plot = ax is None
    
    overhead_before = overhead_as_percent(base_res, before_res)
    overhead_after = overhead_as_percent(base_res, after_res)
    
    # Remove unndeeded stats:
    overhead_before[bench_name] = dict(filter(lambda x: x[0] in desired_stats, overhead_before[bench_name].items()))
    overhead_after[bench_name] = dict(filter(lambda x: x[0] in desired_stats, overhead_after[bench_name].items()))

    # Ensure both sets have all needed results
    for stat in desired_stats:
        if stat not in overhead_before[bench_name].keys():
            overhead_before[bench_name][stat] = 0
        if stat not in overhead_after[bench_name].keys():
            overhead_after[bench_name][stat] = 0

    # Form the stat array for the dataframe
    df_stats = {
        "stat": list(overhead_before[bench_name].keys()) + list(overhead_before[bench_name].keys()),
        "results": list(overhead_before[bench_name].values()) + list(overhead_after[bench_name].values()),
        "type": (['before'] * len(overhead_before[bench_name].values())) + (['after'] * len(overhead_after[bench_name].values())),
    }

    df = pd.DataFrame(df_stats)

    ax = sns.barplot(
        df,
        x='results',
        y='stat',
        hue='type',
        palette='mako'
    )

    ax.set_xlabel("Overhead Percentage")
    ax.set_ylabel("Statistic")
    ax.legend(loc=1)
    ax.set_title(f"Overhead Comparison: {instance_name}")

    if plot:
        plt.subplots_adjust(left=0.3)
        plt.savefig(os.path.join(RES_DIR, f"compare-{instance_name}-{desired_stats[0]}.pdf"))

def generate_heap_sum_bar(heap_res, instance_name, valid_types, ax=None):
    plot = ax is None
    
    mpl.style.use('seaborn-v0_8')
    mpl.rcParams['axes.facecolor'] = 'none'
    mpl.rcParams['axes.edgecolor'] = 'black'
    mpl.rcParams['axes.linewidth'] = '1.0'

    mpl.rcParams['xtick.major.size'] = '8.0'
    mpl.rcParams['xtick.minor.size'] = '5.0'
    mpl.rcParams['ytick.major.size'] = '8.0'
    mpl.rcParams['ytick.minor.size'] = '5.0'

    res = {}
    for bench, vals in heap_res.items():
        res[bench] = dict(filter(lambda x: x[1]['type'] in valid_types, vals.items()))
        
        res[bench] = {}
        for type in valid_types:
            res[bench][type] = sum_heap_allocations(heap_res, bench, [type], False)
    
    res = dict(sorted(res.items(), key=lambda x: sum(x[1].values())))
    print_heap_sum_table(res)
    
    df_stats = {}
    for type in valid_types:
        df_stats[type] = list(map(lambda x: x[type], res.values()))

    df = pd.DataFrame(df_stats, index=res.keys())

    if ax is not None:
        df.plot.barh(rot=0, legend=True, ax=ax, stacked=True)
    else:
        ax = df.plot.barh(rot=0, legend=True, stacked=True)

    ax.set_xlabel("Total Allocations")
    ax.set_ylabel("Benchmark")
    ax.set_title(f"Sorted Total Heap Allocations: {instance_name.capitalize()}")
    ax.set_xscale('log', base=2)
    # ax.axhline()

    if plot:
        plt.subplots_adjust(left=0.25)
        plt.savefig(os.path.join(RES_DIR, f"heap-sum-bar-{instance_name}.pdf"))

def generate_stack_sum_bar(stack_res, instance_name, valid_types, ax=None):
    plot = ax is None
    
    mpl.style.use('seaborn-v0_8')
    mpl.rcParams['axes.facecolor'] = 'none'
    mpl.rcParams['axes.edgecolor'] = 'black'
    mpl.rcParams['axes.linewidth'] = '1.0'

    mpl.rcParams['xtick.major.size'] = '8.0'
    mpl.rcParams['xtick.minor.size'] = '5.0'
    mpl.rcParams['ytick.major.size'] = '8.0'
    mpl.rcParams['ytick.minor.size'] = '5.0'

    type_sorted = {}
    for bench, stats in stack_res.items():
        type_sorted[bench] = {}

        # Sum by type
        for size, stat in stats.items():
            if stat['type'] not in type_sorted[bench].keys():
                type_sorted[bench][stat['type']] = stat['count']
            else:
                type_sorted[bench][stat['type']] += stat['count']


    res = dict(sorted(type_sorted.items(), key=lambda x: sum(x[1].values())))
    print_stack_table(res)
    
    df_stats = {}
    for type in valid_types:
        df_stats[type] = list(map(lambda x: x[type] if type in x.keys() else 0, res.values()))

    df_stats = dict(filter(lambda x: sum(x[1]) != 0, df_stats.items()))

    df = pd.DataFrame(df_stats, index=res.keys())

    if ax is not None:
        df.plot.barh(rot=0, legend=True, ax=ax, stacked=True)
    else:
        ax = df.plot.barh(rot=0, legend=True, stacked=True)

    ax.set_xlabel("Total Allocations")
    ax.set_ylabel("Benchmark")
    ax.set_title(f"Sorted Total Stack Allocations: {instance_name.capitalize()}")
    ax.set_xscale('log', base=2)

    if plot:
        plt.subplots_adjust(left=0.25)
        plt.savefig(os.path.join(RES_DIR, f"stack-sum-{instance_name}.pdf"))

def generate_lib_scatter(bench_heap_res, instance_name, valid_types, lib, cumulative, ax=None):
    plot = ax is None
    
    # print(bench_heap_res)

    # Filter out frees
    bench_heap_res = dict(filter(lambda x: x[1]['type'] in valid_types, bench_heap_res.items()))

    stats = {
        'count': list(map(lambda x: x['count'], bench_heap_res.values())),
        'type': list(map(lambda x: x['type'], bench_heap_res.values())),
        'size': list(bench_heap_res.keys())
    }


    ax = sns.scatterplot(
        stats, x='size', y='count', palette='mako', hue='type', linewidth=0, alpha=0.7, s=10, ax=ax)

    ax.set_title(f"{lib} Allocations: {instance_name.capitalize()}")
    ax.set_xlabel("Allocation Size")
    ax.set_ylabel("Allocation Count")
    ax.legend(loc=1)
    ax.set_yscale('log', base=2)
    ax.set_xscale('log', base=2)
    
    if cumulative:
        ax2 = ax.twinx()
        ax2 = sns.ecdfplot(stats, x='size', color='#48233C', stat='proportion', log_scale=2, legend=True, weights=stats['count'], label="% of allocations")
        ax2.legend(loc=2)
        ax2.set_ylim([-0.01, 1.01])
        ax2.set_title(f"{lib} Allocations: {instance_name.capitalize()}")
        ax2.set_xlabel("Allocation Size")
    
    if plot:
        # pass
        # plt.subplots_adjust(left=0.25)
        plt.savefig(os.path.join(RES_DIR, f"{lib}-allocations-scatter-{instance_name.split('-')[1]}.pdf"))

def generate_bar(results, unit, desired_stats, instance_name, ax=None):
    overhead = results
    
    plot = ax is None

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

    ax.set_xlabel(f"{unit}")
    ax.set_ylabel("Benchmark")
    ax.set_title(f"Overhead: {instance_name.capitalize()}")
    
    if plot:
        plt.subplots_adjust(left=0.25)
        plt.savefig(os.path.join(RES_DIR, f"basic-bar-{instance_name}-{desired_stats[0]}.pdf"))

def generate_overhead_bar(base_res, san_res, desired_stats, instance_name, log=False, ax=None):
    overhead = overhead_as_percent(base_res, san_res)
    plot = ax is None

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
    if log:
        ax.set_xscale('log')

    ax.set_ylabel("Benchmark")
    ax.set_title(f"Overhead: {instance_name.capitalize()}")
    
    if plot:
        plt.subplots_adjust(left=0.25)
        plt.savefig(os.path.join(RES_DIR, f"overhead-{instance_name}-{desired_stats[0]}.pdf"))

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

def generate_heap_scatters(heap_res, tests, valid_stats, instance):

    plt.figure(2)

    plt.subplot(2, 4, 1)
    generate_lib_scatter(heap_res[tests[0]], f"{instance} - {tests[0]}", valid_stats, "Heap", True, ax=plt.gca())

    plt.subplot(2, 4, 2)
    generate_lib_scatter(heap_res[tests[1]], f"{instance} - {tests[1]}", valid_stats, "Heap", True, ax=plt.gca())

    plt.subplot(2, 4, 3)
    generate_lib_scatter(heap_res[tests[2]], f"{instance} - {tests[2]}", valid_stats, "Heap", True, ax=plt.gca())

    plt.subplot(2, 4, 4)
    generate_lib_scatter(heap_res[tests[3]], f"{instance} - {tests[3]}", valid_stats, "Heap", True, ax=plt.gca())

    plt.subplot(2, 4, 5)
    generate_lib_scatter(heap_res[tests[4]], f"{instance} - {tests[4]}", valid_stats, "Heap", True, ax=plt.gca())

    plt.subplot(2, 4, 6)
    generate_lib_scatter(heap_res[tests[5]], f"{instance} - {tests[5]}", valid_stats, "Heap", True, ax=plt.gca())

    plt.subplot(2, 4, 7)
    generate_lib_scatter(heap_res[tests[6]], f"{instance} - {tests[6]}", valid_stats, "Heap", True, ax=plt.gca())

    plt.subplot(2, 4, 8)
    generate_lib_scatter(heap_res[tests[7]], f"{instance} - {tests[7]}", valid_stats, "Heap", True, ax=plt.gca())

    plt.subplots_adjust(hspace=0.25, wspace=0.5)

def generate_perf_compare_bars(base_res, before_res, after_res, instance):

    plt.figure(3)

    plt.subplot(2, 4, 1)
    generate_bench_comparison_bar(base_res, before_res, after_res, "branch-misses", instance, ax=plt.gca())

    plt.subplot(2, 4, 2)
    generate_bench_comparison_bar(base_res, before_res, after_res, "cache-misses", instance, ax=plt.gca())

    plt.subplot(2, 4, 3)
    generate_bench_comparison_bar(base_res, before_res, after_res, "L1-icache-load-misses", instance, ax=plt.gca())

    plt.subplot(2, 4, 4)
    generate_bench_comparison_bar(base_res, before_res, after_res, "L1-dcache-load-misses", instance, ax=plt.gca())

    plt.subplot(2, 4, 5)
    generate_bench_comparison_bar(base_res, before_res, after_res, "iTLB-load-misses", instance, ax=plt.gca())

    plt.subplot(2, 4, 6)
    generate_bench_comparison_bar(base_res, before_res, after_res, "dTLB-store-misses", instance, ax=plt.gca())

    plt.subplot(2, 4, 7)
    generate_bench_comparison_bar(base_res, before_res, after_res, "dTLB-load-misses", instance, ax=plt.gca())

    plt.subplot(2, 4, 8)
    generate_bench_comparison_bar(base_res, before_res, after_res, "faults", instance, ax=plt.gca())

    plt.subplots_adjust(hspace=0.25, wspace=0.5)

def generate_base_compare_bars(base_res, before_res, after_res, instance):
    plt.figure(4)

    plt.subplot(2, 3, 1)
    generate_bench_comparison_bar(base_res, before_res, after_res, "runtime", instance, ax=plt.gca())

    plt.subplot(2, 3, 2)
    generate_bench_comparison_bar(base_res, before_res, after_res, "maxrss", instance, ax=plt.gca())

    plt.subplot(2, 3, 3)
    generate_bench_comparison_bar(base_res, before_res, after_res, "io_operations", instance, ax=plt.gca())

    plt.subplot(2, 3, 4)
    generate_bench_comparison_bar(base_res, before_res, after_res, "page_faults", instance, ax=plt.gca())

    plt.subplot(2, 3, 5)
    generate_bench_comparison_bar(base_res, before_res, after_res, "context_switches", instance, ax=plt.gca())

    plt.subplots_adjust(hspace=0.25, wspace=0.5)

def generate_stack_scatters(heap_res, tests, valid_stats, instance):

    plt.figure(5)

    plt.subplot(2, 4, 1)
    generate_lib_scatter(heap_res[tests[0]], f"{instance} - {tests[0]}", valid_stats, "Stack", False, ax=plt.gca())

    plt.subplot(2, 4, 2)
    generate_lib_scatter(heap_res[tests[1]], f"{instance} - {tests[1]}", valid_stats, "Stack", False, ax=plt.gca())

    plt.subplot(2, 4, 3)
    generate_lib_scatter(heap_res[tests[2]], f"{instance} - {tests[2]}", valid_stats, "Stack", False, ax=plt.gca())

    plt.subplot(2, 4, 4)
    generate_lib_scatter(heap_res[tests[3]], f"{instance} - {tests[3]}", valid_stats, "Stack", False, ax=plt.gca())

    plt.subplot(2, 4, 5)
    generate_lib_scatter(heap_res[tests[4]], f"{instance} - {tests[4]}", valid_stats, "Stack", False, ax=plt.gca())

    plt.subplot(2, 4, 6)
    generate_lib_scatter(heap_res[tests[5]], f"{instance} - {tests[5]}", valid_stats, "Stack", False, ax=plt.gca())
    
    plt.subplot(2, 4, 7)
    generate_lib_scatter(heap_res[tests[6]], f"{instance} - {tests[6]}", valid_stats, "Stack", False, ax=plt.gca())

    plt.subplot(2, 4, 8)
    generate_lib_scatter(heap_res[tests[7]], f"{instance} - {tests[7]}", valid_stats, "Stack", False, ax=plt.gca())

    # plt.subplots_adjust(hspace=0.25, wspace=0.5)

def generate_base_graphs(base_res, san_res, instance):

    plt.figure(6)

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

def geomean(vals):
    return np.exp((np.log(vals)).mean())

def print_result_table(result, instance, mean=False, geo=False, stat=None):
    if mean or geo:
        if stat is None:
            print("A stat must be selected")
            return

        if geo:
            gmean = geomean(list(map(lambda x: 0 if stat not in x[1].keys() else x[1][stat], result.items())))
            print(f"The geomean of {instance} {stat} is {gmean}")
        
        mean = 0
        for bench, stats in result.items():
            if stat not in stats.keys():
                mean += 0
            else:
                mean += stats[stat]

        mean /= len(result.keys())
        print(f"The mean of {instance} {stat} is: {mean}")
        return
    
    for bench, stats in result.items():
        print(f"Benchmark name: {bench}")
        for stat, value in stats.items():
            print(f"Stat: {stat}, Value: {value}")

def print_heap_sum_table(result):
    for bench, val in result.items():

        total_allocs = sum(val.values())
        print(f"Benchmark name: {bench}")
        for type, count in val.items():
            percent_allocs = (count / total_allocs) * 100
            print(f"\t - {percent_allocs} are {type}")

def sum_stack_allocations(result):
    type_sorted = {}
    for bench, stats in result.items():
        type_sorted[bench] = {}

        # Sum total
        total_allocations = sum(list(map(lambda x: x[1]['count'], result[bench].items())))

        # Sum by type
        for size, stat in stats.items():
            if stat['type'] not in type_sorted[bench].keys():
                type_sorted[bench][stat['type']] = stat['count']
            else:
                type_sorted[bench][stat['type']] += stat['count']

        # Calculate percents
        for type, count in type_sorted[bench].items():
            type_sorted[bench][type] = (count / total_allocations) * 100

    return type_sorted

def print_stack_table(results):
    for bench, stats in results.items():
        print(f"BENCHMARK: {bench}")
        total_allocs = sum(stats.values())
        for name, val in stats.items():
            percent = (val / total_allocs) * 100
            print(f"Type: {name} - {percent}%")


def print_overhead_compare_table(before_overhead, after_overhead, agg=None):
    
    total = {}
    for bench, stats in before_overhead.items():
        if bench not in after_overhead.keys():
            continue

        print(f"BENCHMARK: {bench}")
        for name, value in stats.items():
            if name not in after_overhead[bench].keys():
                after_overhead[bench][name] = 0

            diff = value - after_overhead[bench][name]
            if value != 0:
                improve = (diff / value) * 100
            else:
                improve = 100 - diff

            if name not in total.keys():
                total[name] = [improve]
            else:
                total[name] += [improve]

            print(f"{name} before: {value} - after: {after_overhead[bench][name]} - improvement: {improve}")

    for stat, values in total.items():
        if 'mean' in agg:
            print(f"The average improvement of {stat} is: {sum(values) / len(values)}")
        # if 'geo' in agg:
        #     print(f"The geomean improvement of {stat} is: {geomean(values)}")

styles = ['seaborn-v0_8', 'seaborn-v0_8-bright', 'seaborn-v0_8-colorblind', 'seaborn-v0_8-dark', 'seaborn-v0_8-dark-palette', 'seaborn-v0_8-darkgrid', 'seaborn-v0_8-deep', 'seaborn-v0_8-muted', 'seaborn-v0_8-notebook', 'seaborn-v0_8-paper', 'seaborn-v0_8-pastel', 'seaborn-v0_8-poster', 'seaborn-v0_8-talk', 'seaborn-v0_8-ticks', 'seaborn-v0_8-white', 'seaborn-v0_8-whitegrid']

if __name__ == "__main__":
    stats =      [  "runtime", "maxrss", "page_faults", "context_switches", "io_operations",
                    "status"]

    aggregates = [  "mean", "median", "stdev", "stdev_percent", 
                    "variance", "mad", "min", "max", 
                    "sum", "count", "same", "one", 
                    "first", "all", "sort", "geomean"]

    perf_stats = [  'instructions', 'cache-references', 'cache-misses', 'branches',
                    'branch-misses', 
                    'dTLB-load-misses', 'dTLB-loads', 'dTLB-store-misses', 'dTLB-stores',
                    'L1-dcache-load-misses', 'L1-dcache-loads', 'L1-dcache-stores', 'L1-icache-load-misses',
                    'iTLB-load-misses', "iTLB-loads", 'faults', 'minor-faults', 'major-faults']
    
    stack_types = ["16-bit floating point", "16-bit floating point (7-bit significand)", "32-bit floating point",
        "64-bit floating point", "80-bit floating point (X87)", "128-bit floating point (112-bit significand) ", "128-bit floating point (two 64-bits, PowerPC) ",
        "void", "label", "metadata", "MMX vectors (64 bits, X86 specific)", "AMX vectors (8192 bits, X86 specific)", "token", "integer", "function",
        "pointer", "struct", "array", "Fixed width SIMD vector", "Scalable SIMD vector"]
    
    test_name = "400.perlbench"
    san_name = "UBsan"

    # print(mpl.rcParams)

    #
    # BASELINE RESULTS
    #

    clang_baseline_res = collect_spec_results("results/run.new-clang-baseline", stats[:5], aggregates[15])

    # san_baseline_res = collect_spec_results("results/run.old-asan-baseline", stats[:5], aggregates[15])
    # san_baseline_res = collect_spec_results("results/run.msan-baseline", stats[:5], aggregates[15])
    # san_baseline_res = collect_spec_results("results/run.cfi-baseline", stats[:5], aggregates[15])
    san_baseline_res = collect_spec_results("results/run.ubsan-baseline", stats[:5], aggregates[15])

    # generate_overhead_bar(clang_baseline_res, san_baseline_res, ['runtime'], san_name)
    # generate_bar(clang_baseline_res, "stdev", ['maxrss'], san_name)
    # print_result_table(clang_baseline_res, "clang")
    

    # print_result_table(san_baseline_res, san_name)
    # print_result_table(overhead_as_percent(clang_baseline_res, san_baseline_res), san_name)
    
    # for stat in stats[:5]:
    #     print_result_table(overhead_as_percent(clang_baseline_res, san_baseline_res), san_name, True, True, stat)


    #generate_base_graphs(clang_baseline_res, san_baseline_res, san_name)

    #
    # PERF RESULTS
    #

    clang_perf_res = collect_perf_results("results/perftrack.clang-lto/perftrack-clang-lto", perf_stats, list(clang_baseline_res.keys()))
    
    valid_benches = list(dict(filter(lambda x: '-' not in x[1].values(), san_baseline_res.items())).keys())
    # san_perf_res = collect_perf_results("results/perftrack.msan/perftrack-msan", perf_stats, valid_benches)
    # san_perf_res = collect_perf_results("results/perftrack.cfi/perftrack-cfi-vis-hidden", perf_stats, valid_benches)
    san_perf_res = collect_perf_results("results/perftrack.ubsan/perftrack-ubsan-default", perf_stats, valid_benches)
    # san_perf_res = collect_perf_results("results/perftrack.asan/perftrack-asan", perf_stats, valid_benches)

    # generate_bench_bar(clang_perf_res,  san_perf_res, test_name, ['faults', 'minor-faults', 'major-faults'], f"{san_name} {test_name.split('.')[1]}")
     
    # generate_overhead_bar(clang_perf_res, san_perf_res, ['instructions', 'iTLB-loads', 'dTLB-load-misses', 'iTLB-load-misses'], san_name, log=True)
    
    # generate_overhead_bar(clang_perf_res, san_perf_res, ['dTLB-load-misses', 'dTLB-store-misses', 'iTLB-load-misses'], 'asan')
    
    # print_result_table(san_perf_res, san_name)
    # print_result_table(overhead_as_percent(clang_perf_res, san_perf_res), san_name)
    
    # for stat in perf_stats:
    #     print_result_table(overhead_as_percent(clang_perf_res, san_perf_res), san_name, True, True, stat)

    # generate_perf_graphs(clang_perf_res, san_perf_res, san_name)
    
    #
    # HEAP RESULTS
    #

    heap_clang_res = collect_malloc_results("results/heaptrack.clang-lto/libmalloctrack-clang-lto", list(clang_baseline_res.keys()))

    # generate_heap_sum_bar(heap_clang_res, san_name, ['Malloc', 'Calloc', 'Realloc'])
    test_name = '482.sphinx3'
    # generate_lib_scatter(heap_clang_res[test_name], f"{san_name} - {test_name}", ['Malloc', 'Calloc', 'Realloc'], "Heap", True)
    
    # generate_heap_scatters(heap_clang_res, ['400.perlbench', '471.omnetpp', '453.povray', '447.dealII', '483.xalancbmk', '462.libquantum'], ['Malloc', 'Calloc', 'Realloc', 'Free'], "heap track")
    # generate_heap_scatters(heap_clang_res, ['471.omnetpp', '482.sphinx3', '456.hmmer', '462.libquantum', '403.gcc', '453.povray', '483.xalancbmk', '400.perlbench'], ['Malloc', 'Calloc', 'Realloc', 'Free'], "heap track")
    
    # gernerate_heap_bar(heap_clang_res, ['400.perlbench', '462.libquantum'], ['Malloc', 'Calloc'], 'perlbench - libquantum')
    

    #
    # STACK RESULTS
    #

    stack_clang_res = collect_stack_results("results/stacktrack.clang-lto/libstacktrack-clang-lto",  list(clang_baseline_res.keys()))

    # generate_stack_scatters(stack_clang_res, ['400.perlbench', '462.libquantum', '471.omnetpp', '447.dealII', '483.xalancbmk', '482.sphinx3'], stack_types, "stack track")
    
    # generate_stack_sum_bar(stack_clang_res, san_name, stack_types)
    
    # stack_percents = sum_stack_allocations(stack_clang_res)
    # print(stack_clang_res)

    #
    # FLAME GRAPH RESULTS
    #

    # generate_flamegraph("results/perftrack.2023-07-07.20-09-46/perftrack-asan/400.perlbench.30423.data", "Asan-400.perlbench", "cache-misses")
    
    # generate_flamegraph("results/perftrack.clang-lto/perftrack-clang-lto/400.perlbench.10486.data", "Clang-400.perlbench", "cache-misses")

    #
    # FURTHER TESTING
    #

    ### ASan no quarantine (only has perlbench, compare with libquantum as well?)
    no_quar_base = collect_spec_results("results/run.asan-noq", stats[:5], aggregates[15])
    no_quar_perf = collect_perf_results("results/perftrack.asan-noq/perftrack-asan-noq", perf_stats, list(no_quar_base.keys()))

    # print_overhead_compare_table(overhead_as_percent(clang_baseline_res, san_baseline_res), overhead_as_percent(clang_baseline_res, no_quar_base), ['mean', 'geo'])
    # print_overhead_compare_table(overhead_as_percent(clang_perf_res, san_perf_res), overhead_as_percent(clang_perf_res, no_quar_perf), ['mean', 'geo'])
    
    # generate_bench_comparison_bar(clang_baseline_res, san_baseline_res, no_quar_base, "runtime", 'Asan - no quarantine')
    # generate_bench_comparison_bar(clang_baseline_res, san_baseline_res, no_quar_base, "maxrss", "Asan - no quarantine")

    # generate_base_compare_bars(clang_baseline_res, san_baseline_res, no_quar_base, "ASan quarantine disabled")
    # generate_perf_compare_bars(clang_perf_res, san_perf_res, no_quar_perf, "ASan quarantine disabled")

    # generate_comparison_bar(clang_baseline_res, san_baseline_res, no_quar_base, '400.perlbench', stats[:4], "perlbench - ASan quarantine disabled")
    # generate_comparison_bar(clang_perf_res, san_perf_res, no_quar_perf, '400.perlbench', perf_stats[:-3], "perlbench - ASan quarantine disabled")
    
    ### MSan no complex propagations (only has gcc, compare with sphinx3 as well?)
    no_complex_base = collect_spec_results("results/run.msan-noc", stats[:5], aggregates[15])
    no_complex_perf = collect_perf_results("results/perftrack.msan-noc/perftrack-msan-noc", perf_stats, list(no_complex_base.keys()))

    # print_overhead_compare_table(overhead_as_percent(clang_baseline_res, san_baseline_res), overhead_as_percent(clang_baseline_res, no_complex_base), ['mean', 'geo'])
    print_overhead_compare_table(overhead_as_percent(clang_perf_res, san_perf_res), overhead_as_percent(clang_perf_res, no_complex_perf), ['mean', 'geo'])
    
    # generate_bench_comparison_bar(clang_baseline_res, san_baseline_res, no_complex_base, "runtime", 'MSan - less shadow propagation')
    # generate_bench_comparison_bar(clang_baseline_res, san_baseline_res, no_complex_base, "maxrss", 'MSan - less shadow propagation')

    # generate_base_compare_bars(clang_baseline_res, san_baseline_res, no_complex_base, "MSan no complex propagation")
    # generate_perf_compare_bars(clang_perf_res, san_perf_res, no_complex_perf, "MSan no complex propagation")

    # generate_comparison_bar(clang_baseline_res, san_baseline_res, no_complex_base, '403.gcc', stats[:4], "gcc - MSan no complex propagation")
    # generate_comparison_bar(clang_perf_res, san_perf_res, no_complex_perf, '403.gcc', perf_stats[:-3], "gcc - MSan no complex propagation")

    ### UBSan no instrument on VDot (test only valid for povray)
    no_vdot_base = collect_spec_results("results/run.ubsan_no_vdot_2", stats[:5], aggregates[15])
    no_vdot_perf = collect_perf_results("results/perftrack.ubsan_no_vdot_2/perftrack-ubsan-default", perf_stats, list(no_vdot_base.keys()))

    no_check_base = collect_spec_results("results/run.ubsan-no-checks", stats[:5], aggregates[15])
    no_check_perf = collect_perf_results("results/perftrack.ubsan-no-checks/perftrack-ubsan-no-checks", perf_stats, list(no_check_base.keys()))
    
    # generate_comparison_bar(clang_baseline_res, san_baseline_res, no_vdot_base, '453.povray', stats[:4], "povray - UBSan no_instrument VDot")
    # generate_comparison_bar(clang_perf_res, san_perf_res, no_vdot_perf, '453.povray', perf_stats, "povray - UBSan no_instrument VDot")
    
    # print_overhead_compare_table(overhead_as_percent(clang_baseline_res, san_baseline_res), overhead_as_percent(clang_baseline_res, no_vdot_base), ['mean', 'geo'])
    # print_overhead_compare_table(overhead_as_percent(clang_perf_res, san_perf_res), overhead_as_percent(clang_perf_res, no_vdot_perf), ['mean', 'geo'])

    # generate_comparison_bar(clang_baseline_res, san_baseline_res, no_check_base, '456.hmmer', stats[:3], "hmmer - UBSan no pointer checks")
    # generate_comparison_bar(clang_perf_res, san_perf_res, no_check_perf, '456.hmmer', perf_stats, "hmmer - UBSan no pointer checks")
    
    # print_overhead_compare_table(overhead_as_percent(clang_baseline_res, san_baseline_res), overhead_as_percent(clang_baseline_res, no_check_base), ['mean', 'geo'])
    print_overhead_compare_table(overhead_as_percent(clang_perf_res, san_perf_res), overhead_as_percent(clang_perf_res, no_check_perf), ['mean', 'geo'])

    # ubsan_stack = collect_stack_results("results/stacktrack.ubsan/libstacktrack-ubsan-default", ['453.povray'])
    # ubsan_heap = collect_heap_results("results/heaptrack.ubsan/libmalloctrack-ubsan-default", ['453.povray'])

    # generate_heap_sum_bar()
    # generate_stack_sum_bar()

    ### UBSan disable subset (disable most common instrument ??? )
    # No valid run for this yet, do we bother? No time it seems
    
    ### Heap Allocations                            X
    # generate_heap_sum_bar(heap_clang_res, san_name, ['Malloc', 'Calloc', 'Realloc', 'Free'])

    # ASan graphs

    # generate_lib_scatter(heap_clang_res['400.perlbench'], "Clang - 400.perlbench", ['Malloc', 'Calloc', 'Realloc'], "Heap", True, ax=None)
    # generate_lib_scatter(heap_clang_res['462.libquantum'], "Clang - 462.libquantum", ['Malloc', 'Calloc', 'Realloc'], "Heap", True, ax=None)

    ### Stack Allocations                           X
    # generate_stack_sum_bar(stack_clang_res, "Stack Track", stack_types)

    # MSan graphs

    # UBSan graphs

    plt.show()
