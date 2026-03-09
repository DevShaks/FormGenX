from __future__ import annotations

import math
import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .stamp_models import HandwritingOverlaySpec


DEFAULT_NOTES = [
    "gez.",
    "i.A.",
    "ok",
    "dringend",
    "eilig",
    "heute",
]


def _load_font(font_size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in ("DejaVuSans.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(candidate, size=font_size)
        except OSError:
            continue
    return ImageFont.load_default()


def _signature_points(width: int, height: int, rng: random.Random) -> list[tuple[float, float]]:
    start_x = rng.uniform(width * 0.05, width * 0.25)
    baseline = rng.uniform(height * 0.45, height * 0.72)
    total = rng.randint(12, 20)
    step = width / max(total + 2, 8)
    points: list[tuple[float, float]] = []
    amp = rng.uniform(height * 0.05, height * 0.17)

    for i in range(total):
        x = start_x + i * step
        wobble = math.sin(i * rng.uniform(0.6, 1.0)) * amp
        jitter = rng.uniform(-height * 0.05, height * 0.05)
        y = baseline + wobble + jitter
        points.append((x, y))

    return points


def _render_signature(layer: Image.Image, spec: HandwritingOverlaySpec, rng: random.Random, alpha: int) -> dict:
    draw = ImageDraw.Draw(layer)
    width, height = layer.size
    stroke_count = rng.randint(1, 3)
    metadata = {"type": "signature", "stroke_count": stroke_count}

    for _ in range(stroke_count):
        points = _signature_points(width, height, rng)
        line_width = rng.randint(spec.line_width_min, max(spec.line_width_min, spec.line_width_max))
        draw.line(points, fill=(*spec.color, alpha), width=line_width, joint="curve")

        if rng.random() < 0.45:
            p1 = points[max(1, len(points) // 3)]
            p2 = (p1[0] + rng.uniform(width * 0.08, width * 0.26), p1[1] + rng.uniform(-height * 0.2, height * 0.2))
            draw.line([p1, p2], fill=(*spec.color, alpha), width=max(1, line_width - 1))

    blur = rng.uniform(0.0, 0.35)
    if blur > 0.03:
        layer = layer.filter(ImageFilter.GaussianBlur(radius=blur))
    metadata["blur"] = round(float(blur), 3)
    return metadata, layer


def _render_handwritten_text(layer: Image.Image, spec: HandwritingOverlaySpec, rng: random.Random, alpha: int) -> dict:
    draw = ImageDraw.Draw(layer)
    width, height = layer.size
    choices = spec.text_values or DEFAULT_NOTES
    text = rng.choice(choices)
    font_size = rng.randint(max(12, height // 10), max(13, height // 5))
    font = _load_font(font_size)

    bbox = draw.textbbox((0, 0), text, font=font)
    tw = max(1, bbox[2] - bbox[0])
    th = max(1, bbox[3] - bbox[1])

    x = rng.randint(max(-tw // 5, -2), max(1, width - tw + max(3, tw // 5)))
    y = rng.randint(max(-th // 2, -2), max(1, height - th + max(4, th // 2)))
    draw.text((x, y), text, font=font, fill=(*spec.color, alpha))

    blur = rng.uniform(0.0, 0.22)
    if blur > 0.03:
        layer = layer.filter(ImageFilter.GaussianBlur(radius=blur))

    return {
        "type": "text",
        "text": text,
        "font_size": font_size,
        "x": x,
        "y": y,
        "blur": round(float(blur), 3),
    }, layer


def render_black_handwriting_overlay(size: tuple[int, int], spec: HandwritingOverlaySpec, rng: random.Random):
    layer = Image.new("RGBA", size, (0, 0, 0, 0))

    if not spec.enabled:
        return layer, {"enabled": False, "applied": False}

    if rng.random() > spec.overlap_prob:
        return layer, {"enabled": True, "applied": False, "reason": "overlap_prob"}

    mode = spec.mode
    alpha = int(255 * rng.uniform(spec.opacity_min, spec.opacity_max))

    if mode == "signature":
        meta, layer = _render_signature(layer, spec, rng, alpha)
    elif mode == "text":
        meta, layer = _render_handwritten_text(layer, spec, rng, alpha)
    else:
        p_text = max(0.0, spec.text_prob)
        p_sig = max(0.0, spec.signature_prob)
        if p_text + p_sig <= 0:
            p_text = 0.5
            p_sig = 0.5
        if rng.random() < (p_text / (p_text + p_sig)):
            meta, layer = _render_handwritten_text(layer, spec, rng, alpha)
        else:
            meta, layer = _render_signature(layer, spec, rng, alpha)

    rotation = rng.uniform(spec.rotation_min, spec.rotation_max)
    if abs(rotation) > 0.05:
        layer = layer.rotate(rotation, resample=Image.Resampling.BICUBIC, expand=False)

    metadata = {
        "enabled": True,
        "applied": True,
        "mode": mode,
        "rotation": round(float(rotation), 3),
        "opacity": round(float(alpha / 255.0), 4),
    }
    metadata.update(meta)
    return layer, metadata
