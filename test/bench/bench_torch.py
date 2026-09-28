#!/usr/bin/env python3
"""SS0 字段映射微基准 (实验 B v2)
用法:
  python bench_torch.py fp16          # Tensor 路径 (HGEMM, FP16 输入)
  python bench_torch.py fp32          # FFMA 路径 (FP32 matmul)
  python bench_torch.py all
输出: 各路径 TFLOPS (峰值取多次中位), 供 ss0map 变体间对比。
注意: 变体间对比必须用同一脚本同一参数, 只改 SS0 值。
"""
import statistics
import sys
import time

import torch

M = N = K = 8192
WARMUP = 3
ITERS = 12


def bench(dtype):
    torch.cuda.init()
    a = torch.randn(M, K, device="cuda").to(dtype)
    b = torch.randn(K, N, device="cuda").to(dtype)
    for _ in range(WARMUP):
        torch.matmul(a, b)
    torch.cuda.synchronize()
    times = []
    for _ in range(ITERS):
        t0 = time.perf_counter()
        torch.matmul(a, b)
        torch.cuda.synchronize()
        times.append(time.perf_counter() - t0)
    med = statistics.median(times)
    tflops = 2.0 * M * N * K / med / 1e12
    return tflops


def main():
    if not torch.cuda.is_available():
        print("CUDA 不可用")
        sys.exit(1)
    print(f"device: {torch.cuda.get_device_name(0)}  torch={torch.__version__}")
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("fp16", "all"):
        print(f"FP16 (Tensor) : {bench(torch.float16):8.2f} TFLOPS")
    if which in ("fp32", "all"):
        print(f"FP32 (FFMA)   : {bench(torch.float32):8.2f} TFLOPS")


if __name__ == "__main__":
    main()
