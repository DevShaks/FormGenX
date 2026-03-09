from __future__ import annotations

import random

import numpy as np
from PIL import Image, ImageEnhance


def apply_subtle_paper_texture(stamp_layer: Image.Image, base_region_rgb: Image.Image, rng: random.Random, strength: float = 0.2) -> Image.Image:
    """
    Modulate stamp alpha by local paper luminance to mimic absorbency differences.
    """
    strength = max(0.0, min(1.0, strength))
    if strength <= 0:
        return stamp_layer

    gray = base_region_rgb.convert("L")
    gray_arr = np.array(gray, dtype=np.float32) / 255.0
    gray_arr = 0.85 + (gray_arr - 0.5) * (0.35 * strength)
    gray_arr = np.clip(gray_arr, 0.65, 1.2)

    alpha = np.array(stamp_layer.split()[3], dtype=np.float32)
    alpha *= gray_arr

    out = stamp_layer.copy()
    out.putalpha(Image.fromarray(np.clip(alpha, 0, 255).astype(np.uint8), mode="L"))
    return out


def apply_local_contrast_reduction(img_rgb: Image.Image, rng: random.Random, strength: float = 0.08) -> Image.Image:
    strength = max(0.0, min(1.0, strength))
    if strength <= 0:
        return img_rgb
    factor = 1.0 - rng.uniform(0.0, strength)
    return ImageEnhance.Contrast(img_rgb).enhance(factor)
