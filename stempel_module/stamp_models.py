from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional


VisibilityMode = Literal["uniform", "per_character", "per_word", "per_section"]


@dataclass
class StampTextLine:
    text: str
    font_size: int = 34
    font_path: Optional[str] = None
    weight: float = 1.0
    section_id: Optional[str] = None


@dataclass
class HandwritingOverlaySpec:
    enabled: bool = False
    color: tuple[int, int, int] = (25, 25, 25)
    mode: str = "text_or_signature"
    text_prob: float = 0.5
    signature_prob: float = 0.5
    overlap_prob: float = 1.0
    rotation_min: float = -8.0
    rotation_max: float = 8.0
    text_values: list[str] = field(default_factory=list)
    opacity_min: float = 0.65
    opacity_max: float = 0.95
    line_width_min: int = 2
    line_width_max: int = 4


@dataclass
class StampEffects:
    ink_color: tuple[int, int, int] = (110, 70, 170)
    opacity_min: float = 0.35
    opacity_max: float = 0.85
    visibility_mode: VisibilityMode = "per_character"
    char_dropout_prob: float = 0.08
    word_dropout_prob: float = 0.04
    section_dropout_prob: float = 0.10
    missing_ink_prob: float = 0.35
    missing_ink_strength: float = 0.45
    blur_radius_min: float = 0.4
    blur_radius_max: float = 1.1
    rotation_min: float = -3.0
    rotation_max: float = 3.0
    strong_rotation_prob: float = 0.12
    strong_rotation_min: float = -10.0
    strong_rotation_max: float = 10.0
    ghost_prob: float = 0.15
    ghost_offset_min: int = 2
    ghost_offset_max: int = 10
    ghost_opacity_min: float = 0.12
    ghost_opacity_max: float = 0.30
    washed_out_prob: float = 0.20
    washed_out_strength_min: float = 0.20
    washed_out_strength_max: float = 0.45
    edge_fade_prob: float = 0.25
    crop_prob: float = 0.15
    crop_max_ratio: float = 0.30
    paper_bleed_prob: float = 0.10
    scan_noise_prob: float = 0.20
    jpeg_artifact_prob: float = 0.10


@dataclass
class StampSpec:
    lines: list[StampTextLine] = field(default_factory=list)
    effects: StampEffects = field(default_factory=StampEffects)
    handwriting: HandwritingOverlaySpec = field(default_factory=HandwritingOverlaySpec)
    preset_name: Optional[str] = None
