"""
QLoRA-adapted Qwen2.5-7B-Instruct for drug-ADE extraction via MLX.

Runs natively on Apple Silicon — 4-bit quantized, no CUDA required.
Load once via load(), then call extract() for every inference request.
"""
from __future__ import annotations

import json
from pathlib import Path

from mlx_lm import load as mlx_load
from mlx_lm import generate as mlx_generate

MLX_MODEL_DIR   = Path(__file__).parent.parent / "mlx_model"
MLX_ADAPTER_DIR = Path(__file__).parent.parent / "mlx_adapter"

SYSTEM_PROMPT = (
    "You are a clinical pharmacovigilance extraction system.\n\n"
    "Given a medical sentence, extract the drug name and its associated adverse effect.\n\n"
    'Return ONLY valid JSON with keys: "drug", "adverse_effect", "sentence".\n'
    "Do not explain anything."
)


class AdeModel:
    def __init__(self) -> None:
        self.model = None
        self.tokenizer = None

    @property
    def loaded(self) -> bool:
        return self.model is not None

    def load(
        self,
        model_path: str | Path = MLX_MODEL_DIR,
        adapter_path: str | Path = MLX_ADAPTER_DIR,
    ) -> None:
        """Load 4-bit MLX model + adapter. Call once at server startup."""
        model_path   = Path(model_path)
        adapter_path = Path(adapter_path)

        if not model_path.exists():
            raise FileNotFoundError(
                f"MLX model not found: {model_path}\n"
                "Run:  python scripts/convert_to_mlx.py"
            )
        if not adapter_path.exists():
            raise FileNotFoundError(
                f"MLX adapter not found: {adapter_path}\n"
                "Run:  python scripts/convert_to_mlx.py"
            )

        self.model, self.tokenizer = mlx_load(
            str(model_path),
            adapter_path=str(adapter_path),
        )

    def extract(self, sentence: str, max_new_tokens: int = 150) -> dict:
        """Run inference on one medical sentence. Returns {drug, adverse_effect, sentence}."""
        if not self.loaded:
            raise RuntimeError("Model not loaded — call load() first")

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": sentence},
        ]
        prompt = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )

        pred_text = mlx_generate(
            self.model,
            self.tokenizer,
            prompt=prompt,
            max_tokens=max_new_tokens,
            verbose=False,
        )

        try:
            result = json.loads(pred_text)
            return {
                "drug":           result.get("drug"),
                "adverse_effect": result.get("adverse_effect"),
                "sentence":       result.get("sentence", sentence),
                "raw":            None,
            }
        except (json.JSONDecodeError, ValueError):
            return {"drug": None, "adverse_effect": None, "sentence": sentence, "raw": pred_text}
