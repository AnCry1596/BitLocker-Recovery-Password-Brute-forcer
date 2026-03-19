# BitLocker Recovery Password Brute-forcer

Uses [BitCracker](https://github.com/e-ago/bitcracker) with a GPU to brute-force BitLocker recovery passwords.

> **Disclaimer:** This tool is intended solely for recovering access to your own BitLocker-encrypted drives. Do not use it on drives you do not own or have explicit permission to access.

---

## Requirements

- Linux (Ubuntu recommended)
- NVIDIA GPU with CUDA support
- CUDA Toolkit installed
- Python 3.6+

---

## Step 1: Build bitcracker_cuda

You must build `bitcracker_cuda` yourself from the BitCracker source.

```bash
git clone https://github.com/e-ago/bitcracker.git
cd bitcracker
```

Before building, edit the `src_CUDA/Makefile` to match your GPU's compute capability:

| GPU Series | Example Models | CUDA Arch Flag |
|---|---|---|
| Maxwell | GTX 750, GTX 950 | `arch=compute_50,code=sm_50` |
| Pascal | GTX 1060, GTX 1070, GTX 1080 | `arch=compute_61,code=sm_61` |
| Volta | Tesla V100 | `arch=compute_70,code=sm_70` |
| Turing | RTX 2060, RTX 2070, RTX 2080 | `arch=compute_75,code=sm_75` |
| Ampere | RTX 3060, RTX 3070, RTX 3080, RTX 3090 | `arch=compute_86,code=sm_86` |
| Ada Lovelace | RTX 4070, RTX 4080, RTX 4090 | `arch=compute_89,code=sm_89` |

> **Note:** If you don't see your GPU here, please Google: `"your GPU name" CUDA compute capability` to find the correct `sm_XX` value.

In the `Makefile`, find the line with `-gencode` and change it to match your GPU. Example for RTX 3060 Ti:

```makefile
-gencode arch=compute_86,code=sm_86
```

Then build:

```bash
./build.sh
```

Copy the resulting `/build/bitcracker_cuda` binary into the same folder as `main.py`.

---

## Step 2: Extract the hash

Use `bitcracker_hash` (also built from BitCracker source) to extract the hash from your BitLocker-encrypted drive or image:

```bash
./bitcracker_hash -o hash_recv_pass.txt -i /path/to/image.img
```

Place `hash_recv_pass.txt` in the same folder as `main.py`.

---

## Step 3: Run

```bash
python3 main.py --hash-file hash_recv_pass.txt
```

### Resume from a previous run

When interrupted, the script prints a resume index. Use it to continue:

```bash
python3 main.py --hash-file hash_recv_pass.txt --start 21564736
```

### Options

| Argument | Default | Description |
|---|---|---|
| `--hash-file` | `hash_recv_pass.txt` | Hash file extracted by `bitcracker_hash` |
| `--start` | `0` | Resume from this index |
| `--chunk-size` | `100000` | Passwords per GPU batch |
| `--threads` | `8` | CUDA threads (`-t`) |
| `--blocks` | `38` | CUDA blocks (`-b`) — set to your GPU's multiprocessor count |
| `--gpu` | `0` | GPU device ID (`-g`) |

> **Note:** The default values for `--threads` and `--blocks` are tuned for an **RTX 3060 Ti** (38 multiprocessors, `sm_86`). If you have a different GPU, adjust `--blocks` to match its multiprocessor count and update the CUDA arch flag accordingly.

---

## Performance

Tested on an **RTX 3060 Ti** with default settings (`--threads 8 --blocks 38 --chunk-size 100000`):

| Metric | Value |
|---|---|
| Passwords per batch | 100,000 |
| Total keyspace | ~282 billion valid candidates |
| Speed | varies by CUDA config — tune `--threads` and `--blocks` for your GPU |

> **Tip:** Increase `--chunk-size` if your GPU has enough VRAM to improve throughput.

---

## Troubleshooting

**`make` fails with `unsupported gpu architecture`**
— Your `-gencode` flag doesn't match your GPU. Check the table in Step 1 and update the `Makefile`.

**`bitcracker_cuda: not found`**
— Make sure the binary is in the same folder as `main.py`, not left in `bitcracker/build/`.

**`nvcc: command not found`**
— CUDA Toolkit is not installed or not in your `PATH`. Install it from the [NVIDIA CUDA Toolkit page](https://developer.nvidia.com/cuda-downloads).

**Hash extraction fails**
— Ensure your image/drive is BitLocker-encrypted with a recovery password (not just a PIN or startup key). TPM-only encryption does not use a recovery password.

---

## License

[WTFPL](LICENSE) — Do What The Fuck You Want To Public License

---

## How it works

BitLocker recovery passwords consist of 8 groups of 6 digits, where each group must be divisible by 11 (range `000000`–`720896`). This script generates all valid candidates and feeds them to `bitcracker_cuda` in batches, deleting each batch after it is checked to avoid filling the disk.
