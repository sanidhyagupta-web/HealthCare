"""
One-time setup script: quantize Qwen2.5-7B to 4-bit MLX format and convert
the PEFT LoRA adapter to MLX format.

Run once from the project root:
    python scripts/convert_to_mlx.py

Outputs:
    mlx_model/    ~4-5 GB  (4-bit quantized, ready for fast inference)
    mlx_adapter/  ~1 MB    (converted LoRA weights)

After this script completes, start the server:
    uvicorn llm.ade_api:app --host 0.0.0.0 --port 8001
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import torch
from safetensors import safe_open
from safetensors.torch import save_file

BASE_MODEL   = "Qwen/Qwen2.5-7B-Instruct"
ADAPTER_DIR  = Path("qlora-adapter-happy-sweep-1_v0")
MLX_MODEL_DIR   = Path("mlx_model")
MLX_ADAPTER_DIR = Path("mlx_adapter")

# Qwen2.5-7B has 28 transformer layers
QWEN_NUM_LAYERS = 28


def convert_base_model() -> None:
    print("=" * 60)
    print("Step 1: Download + quantize base model")
    print("  Streams layer-by-layer — never holds 14 GB in RAM at once")
    print("  Expected time: ~15-20 min")
    print("=" * 60)

    subprocess.run(
        [
            sys.executable, "-m", "mlx_lm.convert",
            "--hf-path", BASE_MODEL,
            "--mlx-path", str(MLX_MODEL_DIR),
            "-q",          # 4-bit quantization
            "--q-bits", "4",
        ],
        check=True,
    )
    print(f"\nBase model saved to {MLX_MODEL_DIR}/\n")


def convert_adapter() -> None:
    print("=" * 60)
    print("Step 2: Convert PEFT adapter → MLX format")
    print("=" * 60)

    safetensors_path = ADAPTER_DIR / "adapter_model.safetensors"
    if not safetensors_path.exists():
        raise FileNotFoundError(f"Adapter not found: {safetensors_path}")

    MLX_ADAPTER_DIR.mkdir(exist_ok=True)

    # Load PEFT weights
    tensors: dict[str, torch.Tensor] = {}
    with safe_open(str(safetensors_path), framework="pt", device="cpu") as f:
        for key in f.keys():
            tensors[key] = f.get_tensor(key)

    # Remap key format
    # PEFT: base_model.model.model.layers.N.self_attn.q_proj.lora_A.weight
    # MLX:  model.layers.N.self_attn.q_proj.lora_a
    mlx_tensors: dict[str, torch.Tensor] = {}
    for key, tensor in tensors.items():
        new_key = key.replace("base_model.model.", "")
        new_key = new_key.replace(".lora_A.weight", ".lora_a")
        new_key = new_key.replace(".lora_B.weight", ".lora_b")
        t = tensor.to(torch.float32)
        # MLX matmul convention: x @ lora_a, so lora_a must be (in, rank).
        # PEFT stores lora_A as (rank, in) and lora_B as (out, rank) — transpose both.
        if ".lora_a" in new_key or ".lora_b" in new_key:
            t = t.T.contiguous()
        mlx_tensors[new_key] = t

    save_file(mlx_tensors, str(MLX_ADAPTER_DIR / "adapters.safetensors"))
    print(f"  Remapped {len(mlx_tensors)} weight tensors")

    # Build MLX adapter config from PEFT config
    peft_cfg = json.loads((ADAPTER_DIR / "adapter_config.json").read_text())
    r     = peft_cfg["r"]
    alpha = float(peft_cfg["lora_alpha"])

    mlx_adapter_cfg = {
        "num_layers": QWEN_NUM_LAYERS,
        "lora_parameters": {
            "rank":    r,
            "alpha":   alpha,
            "dropout": float(peft_cfg.get("lora_dropout", 0.0)),
            "scale":   alpha / r,
        },
    }
    (MLX_ADAPTER_DIR / "adapter_config.json").write_text(
        json.dumps(mlx_adapter_cfg, indent=2)
    )
    print(f"  Adapter config: r={r}, alpha={alpha}, scale={alpha/r}")
    print(f"  Saved to {MLX_ADAPTER_DIR}/\n")


if __name__ == "__main__":
    convert_base_model()
    convert_adapter()
    print("=" * 60)
    print("Setup complete!")
    print("Start the inference server:")
    print("  uvicorn llm.ade_api:app --host 0.0.0.0 --port 8001")
    print("=" * 60)
