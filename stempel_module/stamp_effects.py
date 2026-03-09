from __future__ import annotations

import io
import random
from typing import Iterable

import numpy as np
from PIL import Image, ImageChops, ImageEnhance, ImageFilter


def _np_rng(rng: random.Random) -> np.random.Generator:
    return np.random.default_rng(rng.randint(0, 2**31 - 1))


def _clip_bbox(bbox: tuple[int, int, int, int], width: int, height: int) -> tuple[int, int, int, int] | None:
    x1, y1, x2, y2 = bbox
    x1 = max(0, min(width, x1))
    y1 = max(0, min(height, y1))
    x2 = max(0, min(width, x2))
    y2 = max(0, min(height, y2))
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2, y2


def apply_character_opacity_map(
    alpha: np.ndarray,
    char_bboxes: Iterable[tuple[int, int, int, int]],
    opacity_min: float,
    opacity_max: float,
    char_dropout_prob: float,
    rng: random.Random,
) -> tuple[np.ndarray, list[float]]:
    sampled = []
    height, width = alpha.shape
    for bbox in char_bboxes:
        clipped = _clip_bbox(bbox, width, height)
        if clipped is None:
            sampled.append(0.0)
            continue
        x1, y1, x2, y2 = clipped
        factor = rng.uniform(opacity_min, opacity_max)
        if rng.random() < char_dropout_prob:
            factor *= rng.uniform(0.05, 0.35)
        alpha[y1:y2, x1:x2] = np.clip(alpha[y1:y2, x1:x2].astype(np.float32) * factor, 0, 255).astype(np.uint8)
        sampled.append(round(float(factor), 4))
    return alpha, sampled


def apply_section_opacity_map(
    alpha: np.ndarray,
    section_bboxes: dict[str, list[tuple[int, int, int, int]]],
    opacity_min: float,
    opacity_max: float,
    section_dropout_prob: float,
    rng: random.Random,
) -> tuple[np.ndarray, dict[str, float]]:
    height, width = alpha.shape
    sampled: dict[str, float] = {}
    for section_id, boxes in section_bboxes.items():
        factor = rng.uniform(opacity_min, opacity_max)
        if rng.random() < section_dropout_prob:
            factor *= rng.uniform(0.05, 0.4)
        sampled[section_id] = round(float(factor), 4)
        for bbox in boxes:
            clipped = _clip_bbox(bbox, width, height)
            if clipped is None:
                continue
            x1, y1, x2, y2 = clipped
            alpha[y1:y2, x1:x2] = np.clip(alpha[y1:y2, x1:x2].astype(np.float32) * factor, 0, 255).astype(np.uint8)
    return alpha, sampled


def apply_dropout_mask(alpha: np.ndarray, dropout_prob: float, rng: random.Random) -> np.ndarray:
    if dropout_prob <= 0:
        return alpha
    np_rng = _np_rng(rng)
    keep = (np_rng.random(alpha.shape) > dropout_prob).astype(np.float32)
    out = (alpha.astype(np.float32) * keep).astype(np.uint8)
    return out


def apply_missing_ink_clusters(alpha: np.ndarray, strength: float, rng: random.Random) -> np.ndarray:
    strength = max(0.0, min(1.0, strength))
    if strength <= 0:
        return alpha

    np_rng = _np_rng(rng)
    h, w = alpha.shape
    low_h = max(6, h // 18)
    low_w = max(6, w // 18)
    low = np_rng.random((low_h, low_w)).astype(np.float32)
    low_img = Image.fromarray((low * 255).astype(np.uint8), mode="L")
    low_img = low_img.resize((w, h), resample=Image.Resampling.BICUBIC)
    low_img = low_img.filter(ImageFilter.GaussianBlur(radius=max(1.2, min(w, h) / 110)))

    noise = np.array(low_img, dtype=np.float32) / 255.0
    mask = np.clip(1.0 - (noise * strength), 0.15, 1.0)
    out = np.clip(alpha.astype(np.float32) * mask, 0, 255).astype(np.uint8)
    return out


def apply_edge_fade(alpha: np.ndarray, strength: float, rng: random.Random) -> np.ndarray:
    h, w = alpha.shape
    y = np.linspace(-1.0, 1.0, h)
    x = np.linspace(-1.0, 1.0, w)
    xx, yy = np.meshgrid(x, y)
    radius = np.sqrt(xx * xx + yy * yy)
    jitter = rng.uniform(0.03, 0.15)
    falloff = np.clip(1.0 - np.maximum(0.0, radius - (0.60 + jitter)) * (1.4 + strength), 0.2, 1.0)
    return np.clip(alpha.astype(np.float32) * falloff, 0, 255).astype(np.uint8)


def apply_gaussian_blur(layer: Image.Image, radius: float) -> Image.Image:
    if radius <= 0:
        return layer
    return layer.filter(ImageFilter.GaussianBlur(radius=radius))


def apply_washed_out_effect(layer: Image.Image, strength: float) -> Image.Image:
    strength = max(0.0, min(1.0, strength))
    if strength <= 0:
        return layer

    rgba = np.array(layer, dtype=np.float32)
    rgb = rgba[:, :, :3]
    alpha = rgba[:, :, 3]

    gray = rgb.mean(axis=2, keepdims=True)
    rgb = rgb * (1.0 - 0.28 * strength) + gray * (0.28 * strength)
    alpha = alpha * (1.0 - 0.55 * strength)

    out = np.dstack([np.clip(rgb, 0, 255), np.clip(alpha, 0, 255)]).astype(np.uint8)
    return Image.fromarray(out, mode="RGBA")


def apply_rotation(layer: Image.Image, angle: float) -> Image.Image:
    if abs(angle) < 0.01:
        return layer
    return layer.rotate(angle, resample=Image.Resampling.BICUBIC, expand=False)


def apply_ghost_stamp(layer: Image.Image, offset: tuple[int, int], opacity_factor: float) -> Image.Image:
    dx, dy = offset
    if dx == 0 and dy == 0:
        return layer

    base = layer.copy()
    ghost = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ghost.paste(base, (dx, dy), base)

    ghost_arr = np.array(ghost, dtype=np.float32)
    ghost_arr[:, :, 3] = np.clip(ghost_arr[:, :, 3] * opacity_factor, 0, 255)
    ghost = Image.fromarray(ghost_arr.astype(np.uint8), mode="RGBA")

    return Image.alpha_composite(base, ghost)


def apply_partial_crop(layer: Image.Image, rng: random.Random, max_ratio: float) -> tuple[Image.Image, dict[str, int]]:
    max_ratio = max(0.0, min(0.95, max_ratio))
    if max_ratio <= 0:
        return layer, {"left": 0, "right": 0, "top": 0, "bottom": 0}

    w, h = layer.size
    crop_left = int(w * rng.uniform(0.0, max_ratio) * (1 if rng.random() < 0.5 else 0))
    crop_right = int(w * rng.uniform(0.0, max_ratio) * (1 if rng.random() < 0.5 else 0))
    crop_top = int(h * rng.uniform(0.0, max_ratio) * (1 if rng.random() < 0.5 else 0))
    crop_bottom = int(h * rng.uniform(0.0, max_ratio) * (1 if rng.random() < 0.5 else 0))

    alpha = layer.split()[3]
    alpha_arr = np.array(alpha, dtype=np.uint8)
    if crop_left > 0:
        alpha_arr[:, :crop_left] = 0
    if crop_right > 0:
        alpha_arr[:, w - crop_right :] = 0
    if crop_top > 0:
        alpha_arr[:crop_top, :] = 0
    if crop_bottom > 0:
        alpha_arr[h - crop_bottom :, :] = 0

    out = layer.copy()
    out.putalpha(Image.fromarray(alpha_arr, mode="L"))
    return out, {"left": crop_left, "right": crop_right, "top": crop_top, "bottom": crop_bottom}


def apply_scan_noise(layer: Image.Image, rng: random.Random, intensity: float = 0.15) -> Image.Image:
    intensity = max(0.0, min(1.0, intensity))
    if intensity <= 0:
        return layer

    arr = np.array(layer, dtype=np.float32)
    h, w, _ = arr.shape
    np_rng = _np_rng(rng)

    noise = np_rng.normal(0.0, 12.0 * intensity, (h, w, 1)).astype(np.float32)
    arr[:, :, :3] = np.clip(arr[:, :, :3] + noise, 0, 255)

    band_count = max(1, int(h / 40))
    for _ in range(band_count):
        y = int(np_rng.integers(0, h))
        band_h = int(np_rng.integers(1, max(2, h // 60)))
        gain = float(np_rng.uniform(0.88, 1.08))
        arr[y : min(h, y + band_h), :, :3] = np.clip(arr[y : min(h, y + band_h), :, :3] * gain, 0, 255)

    return Image.fromarray(arr.astype(np.uint8), mode="RGBA")


def apply_jpeg_like_degradation(layer: Image.Image, rng: random.Random) -> Image.Image:
    quality = int(rng.uniform(32, 68))
    rgb = layer.convert("RGB")
    buffer = io.BytesIO()
    rgb.save(buffer, format="JPEG", quality=quality, subsampling=1)
    buffer.seek(0)
    compressed = Image.open(buffer).convert("RGB")

    alpha = layer.split()[3]
    out = compressed.convert("RGBA")
    out.putalpha(alpha)

    out = out.filter(ImageFilter.BoxBlur(radius=rng.uniform(0.0, 0.6)))
    return out


def reduce_alpha(layer: Image.Image, factor: float) -> Image.Image:
    factor = max(0.0, min(1.0, factor))
    alpha = layer.split()[3]
    alpha = ImageEnhance.Brightness(alpha).enhance(factor)
    out = layer.copy()
    out.putalpha(alpha)
    return out


def multiply_alpha_mask(layer: Image.Image, mask: Image.Image) -> Image.Image:
    alpha = layer.split()[3]
    merged = ImageChops.multiply(alpha, mask.convert("L"))
    out = layer.copy()
    out.putalpha(merged)
    return out
