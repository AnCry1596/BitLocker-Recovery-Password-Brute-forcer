# gen_numbers.py

import argparse
import os
import subprocess
import sys
import tempfile


def get_max_index(slots=8):
    valid_per_slot = 65536
    return (valid_per_slot ** slots) - 1


def generate_lines(slots=8, width=6, start=0, reverse=False):
    """
    Yield (index, line) of valid BitLocker recovery password candidates.
    Each group must be divisible by 11 and in range 000000-720896.
    Valid values per slot: 0, 11, 22, ..., 720896 (65536 values per slot).
    Total keyspace: 65536^8
    start: resume from this index (counts only valid candidates)
    reverse: iterate from start down to 0 (inclusive)
    """
    from itertools import count
    # Valid slot values: multiples of 11 up to 720896
    # 720896 = 65536 * 11, so valid range is 0..65535 mapped to *11
    valid_per_slot = 65536  # 720896 // 11 + 1

    if reverse:
        for i in range(start, -1, -1):
            parts = []
            remainder = i
            for _ in range(slots):
                parts.append((remainder % valid_per_slot) * 11)
                remainder //= valid_per_slot
            yield i, "-".join(f"{p:06d}" for p in reversed(parts))
        return

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
    parser.add_argument("--start", type=int, default=None,
                        help="Start from this index (to resume a previous run). In --revert mode, defaults to the last key.")
    parser.add_argument("--revert", action="store_true",
                        help="Reverse mode: generate/check from last key to first")
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

    max_index = get_max_index(args.slots)
    if args.start is None:
        args.start = max_index if args.revert else 0

    if args.start < 0 or args.start > max_index:
        print(f"Error: --start must be between 0 and {max_index} for slots={args.slots}")
        sys.exit(2)

    if args.generate_only:
        # Original behavior: write to file, starting from --start
        direction = "descending" if args.revert else "ascending"
        print(f"Generating ({direction}) from index {args.start} to {args.output_file} ...")
        with open(args.output_file, "w", encoding="utf-8") as f:
            first_line = True
            for _, line in generate_lines(args.slots, args.width, args.start, args.revert):
                if not first_line:
                    f.write("\n")
                f.write(line)
                first_line = False
        return

    # Chunked bitcracker mode
    direction = "descending (last -> first)" if args.revert else "ascending (first -> last)"
    print(f"Starting from index {args.start}, chunk size {args.chunk_size}, mode {direction}")
    print(f"Hash file: {args.hash_file}")
    print("Press Ctrl+C to stop. Re-run with --start <last printed index> to resume.\n")

    chunk = []
    current_start = args.start
    chunk_first_idx = None

    def process_chunk(chunk_start_idx, chunk_end_idx):
        nonlocal chunk, current_start
        print(f"[{chunk_start_idx} - {chunk_end_idx}] Running bitcracker ...", flush=True)

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

        current_start = (chunk_end_idx - 1) if args.revert else (chunk_end_idx + 1)
        chunk = []
        print(f"    Resume index: {current_start}", flush=True)

    try:
        for idx, line in generate_lines(args.slots, args.width, args.start, args.revert):
            if not chunk:
                chunk_first_idx = idx
            chunk.append(line)

            if len(chunk) >= args.chunk_size:
                process_chunk(chunk_first_idx, idx)

        # In reverse mode the generator is finite, so process the last partial chunk.
        if chunk:
            process_chunk(chunk_first_idx, 0 if args.revert else chunk_first_idx + len(chunk) - 1)
            if args.revert:
                print("Done: reached index 0.")

    except KeyboardInterrupt:
        print(f"\nInterrupted. Resume with: --start {current_start}")
        if chunk:
            print(f"  (last partial chunk started at {current_start}, {len(chunk)} keys not yet checked)")


if __name__ == "__main__":
    main()
