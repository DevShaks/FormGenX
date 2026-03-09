from __future__ import annotations

import copy
import random
from dataclasses import asdict
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .overlay_renderer import render_black_handwriting_overlay
from .paper_effects import apply_subtle_paper_texture
from .stamp_effects import (
    apply_character_opacity_map,
    apply_dropout_mask,
    apply_edge_fade,
    apply_gaussian_blur,
    apply_ghost_stamp,
    apply_jpeg_like_degradation,
    apply_missing_ink_clusters,
    apply_partial_crop,
    apply_rotation,
    apply_scan_noise,
    apply_section_opacity_map,
    apply_washed_out_effect,
)
from .stamp_models import HandwritingOverlaySpec, StampEffects, StampSpec, StampTextLine
from .stamp_presets import STAMP_PRESETS


def _deep_merge(base: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def _build_dataclass(cls, data: dict[str, Any] | None):
    data = data or {}
    valid = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
    return cls(**valid)


def _normalize_lines(lines_payload: list[Any] | None, effects: StampEffects) -> list[StampTextLine]:
    lines: list[StampTextLine] = []
    if not lines_payload:
        return lines

    default_size = 26 if effects.visibility_mode == "uniform" else 28

    for idx, item in enumerate(lines_payload):
        if isinstance(item, str):
            lines.append(StampTextLine(text=item, font_size=default_size, section_id=f"line_{idx}"))
            continue
        if isinstance(item, dict):
            data = {k: v for k, v in item.items() if k in StampTextLine.__dataclass_fields__}
            if "text" not in data:
                continue
            data.setdefault("font_size", default_size)
            data.setdefault("section_id", f"line_{idx}")
            lines.append(StampTextLine(**data))

    return lines


def _resolve_stamp_spec(payload: dict[str, Any] | None, cfg: dict[str, Any] | None, preset_map: dict[str, Any] | None) -> StampSpec:
    payload = payload or {}
    cfg = cfg or {}

    base = asdict(StampSpec())

    params = cfg.get("params", {}) if isinstance(cfg, dict) else {}
    preset_name = payload.get("preset") or params.get("preset") or cfg.get("preset") or "clean"

    merged_presets = {}
    merged_presets.update(STAMP_PRESETS)
    if isinstance(preset_map, dict):
        merged_presets.update(preset_map)

    preset_data = merged_presets.get(preset_name, {})
    if isinstance(preset_data, dict):
        base = _deep_merge(base, preset_data)

    # Field-level stamp config can override preset defaults.
    if isinstance(cfg.get("stamp"), dict):
        base = _deep_merge(base, cfg["stamp"])

    if isinstance(payload.get("effects"), dict):
        base = _deep_merge(base, {"effects": payload["effects"]})

    if isinstance(payload.get("handwriting"), dict):
        base = _deep_merge(base, {"handwriting": payload["handwriting"]})

    lines_payload = payload.get("lines")
    if isinstance(lines_payload, str):
        lines_payload = [lines_payload]
    if lines_payload is None and isinstance(payload.get("value"), str):
        lines_payload = [payload["value"]]

    effects = _build_dataclass(StampEffects, base.get("effects"))
    handwriting = _build_dataclass(HandwritingOverlaySpec, base.get("handwriting"))
    lines = _normalize_lines(lines_payload, effects)

    if not lines and payload.get("text"):
        lines = _normalize_lines([str(payload["text"])], effects)

    spec = StampSpec(
        lines=lines,
        effects=effects,
        handwriting=handwriting,
        preset_name=preset_name,
    )
    return spec


def _load_font(font_path: str | None, font_size: int):
    candidates = []
    if font_path:
        candidates.append(font_path)
    candidates.extend(["DejaVuSans.ttf", "arial.ttf"])

    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=font_size)
        except OSError:
            continue
    return ImageFont.load_default()


def _pick_color(effects: StampEffects, rng: random.Random) -> tuple[int, int, int]:
    r, g, b = effects.ink_color
    jitter = lambda c: int(max(0, min(255, c + rng.randint(-8, 8))))
    return jitter(r), jitter(g), jitter(b)


def _render_clean_stamp_layer(size: tuple[int, int], spec: StampSpec, rng: random.Random):
    width, height = size
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    effects = spec.effects
    color = _pick_color(effects, rng)

    if not spec.lines:
        return layer, {
            "line_count": 0,
            "char_count": 0,
            "word_count": 0,
            "char_bboxes": [],
            "section_bboxes": {},
            "sampled": {},
        }

    top_margin = max(2, int(height * 0.06))
    left_margin = max(2, int(width * 0.04))
    available_h = max(1, height - top_margin * 2)
    slot_h = available_h / max(1, len(spec.lines))

    visibility = effects.visibility_mode
    char_bboxes: list[tuple[int, int, int, int]] = []
    section_bboxes: dict[str, list[tuple[int, int, int, int]]] = {}
    word_boxes: list[tuple[int, int, int, int]] = []
    sampled_per_char: list[float] = []
    sampled_per_word: list[float] = []
    sampled_per_section: dict[str, float] = {}

    uniform_factor = rng.uniform(effects.opacity_min, effects.opacity_max)

    for idx, line in enumerate(spec.lines):
        section_id = line.section_id or f"line_{idx}"
        font = _load_font(line.font_path, max(10, line.font_size))

        y = int(top_margin + idx * slot_h + rng.uniform(-2.0, 2.0))
        x = int(left_margin + rng.uniform(-3.0, 4.0))
        section_boxes: list[tuple[int, int, int, int]] = []

        if visibility == "per_section":
            factor = rng.uniform(effects.opacity_min, effects.opacity_max)
            if rng.random() < effects.section_dropout_prob:
                factor *= rng.uniform(0.05, 0.4)
            sampled_per_section[section_id] = round(float(factor), 4)

        words = line.text.split(" ")
        for word in words:
            if visibility == "per_word":
                word_factor = rng.uniform(effects.opacity_min, effects.opacity_max)
                if rng.random() < effects.word_dropout_prob:
                    word_factor *= rng.uniform(0.05, 0.45)
                sampled_per_word.append(round(float(word_factor), 4))
            else:
                word_factor = 1.0

            word_x_start = x
            for ch in word:
                if visibility == "uniform":
                    alpha_factor = uniform_factor
                elif visibility == "per_character":
                    alpha_factor = rng.uniform(effects.opacity_min, effects.opacity_max)
                    if rng.random() < effects.char_dropout_prob:
                        alpha_factor *= rng.uniform(0.05, 0.35)
                elif visibility == "per_word":
                    alpha_factor = word_factor
                else:
                    alpha_factor = sampled_per_section.get(section_id, 1.0)

                sampled_per_char.append(round(float(alpha_factor), 4))

                bbox = draw.textbbox((x, y), ch, font=font)
                ch_w = max(1, bbox[2] - bbox[0])
                ch_h = max(1, bbox[3] - bbox[1])

                alpha = int(max(0, min(255, 255 * alpha_factor * max(0.1, line.weight))))
                if alpha > 0:
                    draw.text((x, y), ch, fill=(*color, alpha), font=font)

                adjusted_bbox = (x, y, x + ch_w, y + ch_h)
                char_bboxes.append(adjusted_bbox)
                section_boxes.append(adjusted_bbox)
                x += ch_w

            word_box = (word_x_start, y, x, y + max(1, int(slot_h * 0.72)))
            word_boxes.append(word_box)

            # Space width uses font metrics so word separations look natural.
            space_bbox = draw.textbbox((0, 0), " ", font=font)
            space_w = max(2, space_bbox[2] - space_bbox[0])
            x += space_w

        section_bboxes[section_id] = section_boxes

    metadata = {
        "line_count": len(spec.lines),
        "char_count": len(char_bboxes),
        "word_count": len(word_boxes),
        "char_bboxes": char_bboxes,
        "word_bboxes": word_boxes,
        "section_bboxes": section_bboxes,
        "sampled": {
            "uniform_factor": round(float(uniform_factor), 4),
            "char_factors": sampled_per_char,
            "word_factors": sampled_per_word,
            "section_factors": sampled_per_section,
        },
    }
    return layer, metadata


def _apply_alpha_effects(layer: Image.Image, clean_meta: dict[str, Any], spec: StampSpec, rng: random.Random):
    effects = spec.effects
    alpha = np.array(layer.split()[3], dtype=np.uint8)

    # Enforce requested visibility control at mask level too for stronger local differences.
    visibility_mode = effects.visibility_mode
    section_sampled = {}
    char_sampled = []

    if visibility_mode == "per_character":
        alpha, char_sampled = apply_character_opacity_map(
            alpha,
            clean_meta.get("char_bboxes", []),
            effects.opacity_min,
            effects.opacity_max,
            effects.char_dropout_prob,
            rng,
        )
    elif visibility_mode == "per_section":
        alpha, section_sampled = apply_section_opacity_map(
            alpha,
            clean_meta.get("section_bboxes", {}),
            effects.opacity_min,
            effects.opacity_max,
            effects.section_dropout_prob,
            rng,
        )
    elif visibility_mode == "uniform":
        uniform = rng.uniform(effects.opacity_min, effects.opacity_max)
        alpha = np.clip(alpha.astype(np.float32) * uniform, 0, 255).astype(np.uint8)
    else:
        # Per-word already applied strongly at glyph render stage; keep mild pixel dropout here.
        alpha = apply_dropout_mask(alpha, effects.word_dropout_prob * 0.35, rng)

    missing_ink_applied = False
    if rng.random() < effects.missing_ink_prob:
        alpha = apply_missing_ink_clusters(alpha, effects.missing_ink_strength, rng)
        missing_ink_applied = True

    edge_fade_applied = False
    if rng.random() < effects.edge_fade_prob:
        alpha = apply_edge_fade(alpha, strength=rng.uniform(0.2, 0.9), rng=rng)
        edge_fade_applied = True

    out = layer.copy()
    out.putalpha(Image.fromarray(alpha, mode="L"))

    return out, {
        "char_factors_mask_stage": char_sampled[:120],
        "section_factors_mask_stage": section_sampled,
        "missing_ink_applied": missing_ink_applied,
        "edge_fade_applied": edge_fade_applied,
    }


def _apply_degradation_pipeline(
    layer: Image.Image,
    base_region_rgb: Image.Image,
    spec: StampSpec,
    clean_meta: dict[str, Any],
    rng: random.Random,
):
    effects = spec.effects
    metadata: dict[str, Any] = {
        "visibility_mode": effects.visibility_mode,
        "preset": spec.preset_name,
    }

    layer, alpha_meta = _apply_alpha_effects(layer, clean_meta, spec, rng)
    metadata.update(alpha_meta)

    blur_radius = rng.uniform(effects.blur_radius_min, effects.blur_radius_max)
    layer = apply_gaussian_blur(layer, blur_radius)
    metadata["blur_radius"] = round(float(blur_radius), 3)

    washed_out = False
    washed_out_strength = 0.0
    if rng.random() < effects.washed_out_prob:
        washed_out = True
        washed_out_strength = rng.uniform(effects.washed_out_strength_min, effects.washed_out_strength_max)
        layer = apply_washed_out_effect(layer, washed_out_strength)
    metadata["washed_out"] = washed_out
    metadata["washed_out_strength"] = round(float(washed_out_strength), 3)

    if rng.random() < effects.strong_rotation_prob:
        rotation = rng.uniform(effects.strong_rotation_min, effects.strong_rotation_max)
        metadata["rotation_mode"] = "strong"
    else:
        rotation = rng.uniform(effects.rotation_min, effects.rotation_max)
        metadata["rotation_mode"] = "slight"
    layer = apply_rotation(layer, rotation)
    metadata["rotation_deg"] = round(float(rotation), 3)

    ghost_applied = False
    ghost_offset = (0, 0)
    ghost_opacity = 0.0
    if rng.random() < effects.ghost_prob:
        ghost_applied = True
        ghost_offset = (
            rng.randint(-effects.ghost_offset_max, effects.ghost_offset_max),
            rng.randint(-effects.ghost_offset_max, effects.ghost_offset_max),
        )
        if abs(ghost_offset[0]) < effects.ghost_offset_min and abs(ghost_offset[1]) < effects.ghost_offset_min:
            ghost_offset = (effects.ghost_offset_min, 0)
        ghost_opacity = rng.uniform(effects.ghost_opacity_min, effects.ghost_opacity_max)
        layer = apply_ghost_stamp(layer, ghost_offset, ghost_opacity)
    metadata["ghost_applied"] = ghost_applied
    metadata["ghost_offset"] = {"x": ghost_offset[0], "y": ghost_offset[1]}
    metadata["ghost_opacity"] = round(float(ghost_opacity), 3)

    crop_applied = False
    crop_values = {"left": 0, "right": 0, "top": 0, "bottom": 0}
    if rng.random() < effects.crop_prob:
        crop_applied = True
        layer, crop_values = apply_partial_crop(layer, rng, effects.crop_max_ratio)
    metadata["crop_applied"] = crop_applied
    metadata["crop_values"] = crop_values

    paper_bleed = False
    if rng.random() < effects.paper_bleed_prob:
        paper_bleed = True
        layer = apply_subtle_paper_texture(layer, base_region_rgb, rng, strength=rng.uniform(0.08, 0.32))
    metadata["paper_bleed_applied"] = paper_bleed

    scan_noise = False
    if rng.random() < effects.scan_noise_prob:
        scan_noise = True
        layer = apply_scan_noise(layer, rng, intensity=rng.uniform(0.08, 0.28))
    metadata["scan_noise_applied"] = scan_noise

    jpeg_degrade = False
    if rng.random() < effects.jpeg_artifact_prob:
        jpeg_degrade = True
        layer = apply_jpeg_like_degradation(layer, rng)
    metadata["jpeg_like_degradation_applied"] = jpeg_degrade

    return layer, metadata


def _compose_full_image(
    full_rgba: Image.Image,
    stamp_layer: Image.Image,
    region: dict[str, int],
    rng: random.Random,
    allow_border_cutoff: bool,
):
    x1 = int(region["x1"])
    y1 = int(region["y1"])
    x2 = int(region["x2"])
    y2 = int(region["y2"])
    width = max(1, x2 - x1)
    height = max(1, y2 - y1)

    # Mild random offset to mimic imperfect placement. A stronger shift is used when
    # border-cutoff is enabled so the stamp can leave the region/page.
    if allow_border_cutoff:
        max_dx = max(2, int(width * 0.18))
        max_dy = max(2, int(height * 0.18))
    else:
        max_dx = max(1, int(width * 0.05))
        max_dy = max(1, int(height * 0.05))

    dx = rng.randint(-max_dx, max_dx)
    dy = rng.randint(-max_dy, max_dy)

    full_rgba.alpha_composite(stamp_layer, dest=(x1 + dx, y1 + dy))
    return full_rgba, {"dx": dx, "dy": dy}


def render_stamp_on_image(
    base_img_bgr,
    region,
    stamp_payload,
    cfg: dict[str, Any] | None = None,
    rng: random.Random | None = None,
    preset_map: dict[str, Any] | None = None,
):
    """
    High-level stamp API used by generator.py.
    Returns (updated_bgr_image, metadata)
    """
    if rng is None:
        rng = random.Random()

    spec = _resolve_stamp_spec(stamp_payload, cfg, preset_map)

    x1 = int(region["x1"])
    y1 = int(region["y1"])
    x2 = int(region["x2"])
    y2 = int(region["y2"])
    width = max(1, x2 - x1)
    height = max(1, y2 - y1)

    full_rgb = cv2.cvtColor(base_img_bgr, cv2.COLOR_BGR2RGB)
    full_rgba = Image.fromarray(full_rgb).convert("RGBA")

    stamp_clean, clean_meta = _render_clean_stamp_layer((width, height), spec, rng)

    base_region = full_rgba.crop((x1, y1, x2, y2)).convert("RGB")
    stamp_degraded, fx_meta = _apply_degradation_pipeline(stamp_clean, base_region, spec, clean_meta, rng)

    handwriting_meta = {"enabled": False, "applied": False}
    overlay = None
    if spec.handwriting.enabled:
        overlay, handwriting_meta = render_black_handwriting_overlay((width, height), spec.handwriting, rng)
        stamp_degraded = Image.alpha_composite(stamp_degraded, overlay)

    allow_border_cutoff = fx_meta.get("crop_applied", False)
    full_rgba, placement_meta = _compose_full_image(full_rgba, stamp_degraded, region, rng, allow_border_cutoff)

    out_rgb = np.array(full_rgba.convert("RGB"))
    out_bgr = cv2.cvtColor(out_rgb, cv2.COLOR_RGB2BGR)

    sampled_char_factors = clean_meta.get("sampled", {}).get("char_factors", [])
    opacity_min_sampled = min(sampled_char_factors) if sampled_char_factors else None
    opacity_max_sampled = max(sampled_char_factors) if sampled_char_factors else None

    metadata = {
        "type": "stamp",
        "preset": spec.preset_name,
        "region": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
        "line_count": clean_meta.get("line_count", 0),
        "char_count": clean_meta.get("char_count", 0),
        "word_count": clean_meta.get("word_count", 0),
        "visibility_mode": spec.effects.visibility_mode,
        "opacity_min_sampled": round(float(opacity_min_sampled), 4) if opacity_min_sampled is not None else None,
        "opacity_max_sampled": round(float(opacity_max_sampled), 4) if opacity_max_sampled is not None else None,
        "fx": fx_meta,
        "handwriting": handwriting_meta,
        "placement": placement_meta,
        "sampled": {
            "char_factors_preview": sampled_char_factors[:80],
            "section_factors": clean_meta.get("sampled", {}).get("section_factors", {}),
            "word_factors_preview": clean_meta.get("sampled", {}).get("word_factors", [])[:40],
        },
    }

    return out_bgr, metadata

