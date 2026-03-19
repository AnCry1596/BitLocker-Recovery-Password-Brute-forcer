# gen_numbers.py

import argparse
import os
import subprocess
import sys
import tempfile


def generate_lines(slots=8, width=6, start=0):
    """
    Yield (index, line) of valid BitLocker recovery password candidates.
    Each group must be divisible by 11 and in range 000000-720896.
    Valid values per slot: 0, 11, 22, ..., 720896 (65536 values per slot).
    Total keyspace: 65536^8
    start: resume from this index (counts only valid candidates)
    """
    from itertools import count
    # Valid slot values: multiples of 11 up to 720896
    # 720896 = 65536 * 11, so valid range is 0..65535 mapped to *11
    valid_per_slot = 65536  # 720896 // 11 + 1

    for i in count(start):
        parts = []
        remainder = i
        for _ in range(slots):
            parts.append((remainder % valid_per_slot) * 11)
            remainder //= valid_per_slot
        yield i, "-".join(f"{p:06d}" for p in reversed(parts))


def run_bitcracker(hash_file, wordlist_file, threads=8, blocks=38, gpu=0, extra_args=None):
    cmd = [
        "./bitcracker_cuda",
        "-f", hash_file,
        "-d", wordlist_file,
        "-t", str(threads),
        "-b", str(blocks),
        "-g", str(gpu),
        "-r"
    ]
    if extra_args:
        cmd.extend(extra_args)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=script_dir)
    # Print output so user can see progress
    if result.stdout:
        print(result.stdout, end="", flush=True)
    if result.stderr:
        print(result.stderr, end="", flush=True)
    # bitcracker exits 0 for both found and not-found; detect by output text
    found = "Password found:" in result.stdout or "password found" in result.stdout.lower()
    return found


def main():
    parser = argparse.ArgumentParser(description="Generate keys and feed to bitcracker in chunks")
    parser.add_argument("--start", type=int, default=0,
                        help="Start from this index (to resume a previous run)")
    parser.add_argument("--chunk-size", type=int, default=100_000,
                        help="Number of keys per batch sent to bitcracker (default: 100000)")
    parser.add_argument("--hash-file", default="hash_recv_pass.txt",
                        help="Hash file for bitcracker -f argument")
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--blocks", type=int, default=38)
    parser.add_argument("--gpu", type=int, default=0)
    parser.add_argument("--slots", type=int, default=8)
    parser.add_argument("--width", type=int, default=6)
    parser.add_argument("--generate-only", action="store_true",
                        help="Only generate numbers.txt (no bitcracker), runs indefinitely")
    parser.add_argument("--output-file", default="numbers.txt",
                        help="Output file (only used with --generate-only)")
    args = parser.parse_args()

    if args.generate_only:
        # Original behavior: write to file, starting from --start
        print(f"Generating from index {args.start} to {args.output_file} ...")
        with open(args.output_file, "w", encoding="utf-8") as f:
            for idx, line in generate_lines(args.slots, args.width, args.start):
                if idx > args.start:
                    f.write("\n")
                f.write(line)
        return

    # Chunked bitcracker mode
    print(f"Starting from index {args.start}, chunk size {args.chunk_size}")
    print(f"Hash file: {args.hash_file}")
    print("Press Ctrl+C to stop. Re-run with --start <last printed index> to resume.\n")

    chunk = []
    current_start = args.start

    try:
        for idx, line in generate_lines(args.slots, args.width, args.start):
            chunk.append(line)

            if len(chunk) >= args.chunk_size:
                print(f"[{idx - args.chunk_size + 1} - {idx}] Running bitcracker ...", flush=True)

                # Write chunk to a temp file in the same directory as the script
                script_dir = os.path.dirname(os.path.abspath(__file__))
                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".txt", delete=False, encoding="utf-8",
                    dir=script_dir
                ) as tmp:
                    tmp.write("\n".join(chunk))
                    tmp_path = tmp.name

                try:
                    found = run_bitcracker(args.hash_file, os.path.basename(tmp_path), args.threads, args.blocks, args.gpu)
                    if found:
                        print(f"[!] Password found! Stopping.")
                        sys.exit(0)
                finally:
                    os.unlink(tmp_path)  # delete checked keys regardless

                current_start = idx + 1
                chunk = []
                print(f"    Resume index: {current_start}", flush=True)

    except KeyboardInterrupt:
        print(f"\nInterrupted. Resume with: --start {current_start}")
        if chunk:
            print(f"  (last partial chunk started at {current_start}, {len(chunk)} keys not yet checked)")


if __name__ == "__main__":
    main()
