#!/usr/bin/env python3
"""Lazy OpenCLIP encoder; model packages and weights stay outside the Skill."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from catalog_lib import cache_dir


DEFAULT_MODEL = "ViT-B-32"
DEFAULT_PRETRAINED = "laion2b_s34b_b79k"
DEFAULT_MODEL_CARD = "https://huggingface.co/laion/CLIP-ViT-B-32-laion2B-s34B-b79K"
INSTALL_HINT = "python3 -m pip install open_clip_torch torch pillow"


class OpenClipUnavailable(RuntimeError):
    pass


def _normalize(values: Any, np: Any) -> Any:
    norms = np.linalg.norm(values, axis=1, keepdims=True)
    return values / np.maximum(norms, 1e-12)


class OpenClipEncoder:
    """Encode text and OpenCV BGR frames in one shared embedding space."""

    def __init__(
        self,
        *,
        model_name: str = DEFAULT_MODEL,
        pretrained: str = DEFAULT_PRETRAINED,
        device: str = "auto",
        model_cache: Path | None = None,
    ) -> None:
        try:
            import numpy as np  # type: ignore
            import open_clip  # type: ignore
            import torch  # type: ignore
            from PIL import Image  # type: ignore
        except ImportError as exc:
            raise OpenClipUnavailable(
                "OpenCLIP is optional and is not available in this Python runtime. "
                f"Install it outside the Skill with: {INSTALL_HINT}"
            ) from exc

        if device == "auto":
            if torch.cuda.is_available():
                device = "cuda"
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                device = "mps"
            else:
                device = "cpu"
        if device not in {"cpu", "cuda", "mps"}:
            raise ValueError("OpenCLIP device must be auto, cpu, cuda, or mps")

        resolved_cache = model_cache or cache_dir() / "models" / "openclip"
        resolved_cache.mkdir(parents=True, exist_ok=True)
        try:
            model, _, preprocess = open_clip.create_model_and_transforms(
                model_name,
                pretrained=pretrained,
                cache_dir=str(resolved_cache),
            )
            tokenizer = open_clip.get_tokenizer(model_name)
            model = model.to(device)
            model.eval()
        except Exception as exc:
            raise OpenClipUnavailable(
                f"Could not load OpenCLIP model {model_name}/{pretrained}: {exc}. "
                "The first successful run may need network access to cache the checkpoint."
            ) from exc

        self.model_name = model_name
        self.pretrained = pretrained
        self.device = device
        self.model_cache = resolved_cache
        self._np = np
        self._open_clip = open_clip
        self._torch = torch
        self._Image = Image
        self._model = model
        self._preprocess = preprocess
        self._tokenizer = tokenizer

    @property
    def metadata(self) -> dict[str, Any]:
        return {
            "backend": "open_clip",
            "model": self.model_name,
            "pretrained": self.pretrained,
            "device": self.device,
            "model_card": DEFAULT_MODEL_CARD if self.pretrained == DEFAULT_PRETRAINED else None,
            "license_note": "Verify the selected checkpoint model card; library and checkpoint licenses are separate.",
        }

    def encode_images(self, frames: list[Any], *, batch_size: int = 16) -> Any:
        if not frames:
            raise ValueError("encode_images requires at least one frame")
        outputs = []
        for start in range(0, len(frames), batch_size):
            batch_frames = frames[start : start + batch_size]
            tensors = []
            for frame in batch_frames:
                if getattr(frame, "ndim", 0) != 3 or frame.shape[2] < 3:
                    raise ValueError("each frame must be an OpenCV-style BGR image")
                rgb = frame[..., :3][:, :, ::-1]
                tensors.append(self._preprocess(self._Image.fromarray(rgb.astype("uint8"))))
            batch = self._torch.stack(tensors).to(self.device)
            with self._torch.no_grad():
                encoded = self._model.encode_image(batch)
            outputs.append(encoded.float().cpu().numpy())
        return _normalize(self._np.concatenate(outputs, axis=0), self._np).astype(self._np.float32)

    def encode_texts(self, texts: list[str]) -> Any:
        clean = [str(text).strip() for text in texts]
        if not clean or any(not text for text in clean):
            raise ValueError("encode_texts requires non-empty strings")
        tokens = self._tokenizer(clean).to(self.device)
        with self._torch.no_grad():
            encoded = self._model.encode_text(tokens)
        return _normalize(encoded.float().cpu().numpy(), self._np).astype(self._np.float32)
