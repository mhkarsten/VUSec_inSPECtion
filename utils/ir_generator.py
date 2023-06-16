#!/usr/bin/env python3
import subprocess

targets = { "examples/ub.cpp":       "undefined",
            "examples/safestack.c":  "safe-stack", 
            "examples/asan.cpp":     "address", 
            "examples/cfi.cpp":        "cfi", 
            "examples/msan.cpp":     "memory"}
CLANG_PATH = "build/packages/llvm-16.0.1/install/bin/"
OUT_DIR = "ir_out"
DIFF_DIR = "diff_out"

def gen_ir_diff(base_command, file_name, sanitizer):
    instrument_command = f"{base_command} -fsanitize={sanitizer}"

    # Emit llvm ir with instrumentation
    subprocess.run(f"{instrument_command} -flto -fvisibility=hidden -emit-llvm -o {OUT_DIR}/{sanitizer}_ir_san.out {file_name}", shell=True, check=True)
    # Emit llvm ir without instrumentation
    subprocess.run(f"{base_command} -flto -fvisibility=hidden -emit-llvm -o {OUT_DIR}/{sanitizer}_ir_no_san.out {file_name}", shell=True, check=True)

    # Generate diffs of ir
    subprocess.run(f"diff {OUT_DIR}/{sanitizer}_ir_no_san.out {OUT_DIR}/{sanitizer}_ir_san.out > {DIFF_DIR}/{sanitizer}_diff.txt",  shell=True, check=False)

if __name__ == "__main__":

    # Make sure you are in the folder with your example programs, otherwise this script will not work
    # Or adjust the paths so it does work

    for target_file, target_def in targets.items():
        if "cpp" in target_file:
            base_command = f"{CLANG_PATH}clang++ -O2 -S -g -fno-omit-frame-pointer"
        else:
            base_command = f"{CLANG_PATH}clang  -O2 -S -g -fno-omit-frame-pointer"
    
        gen_ir_diff(base_command, target_file, target_def)
