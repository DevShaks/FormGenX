# Formular Test Data Generator

FormGenX creates synthetic form datasets from image templates. It supports the existing text and checkbox workflow and now also supports realistic, parameter-driven stamp generation for OCR, document AI, and synthetic training data generation.

The stamp system is implemented as an extension of the current pipeline. Existing configs continue to work unchanged. Stamp rendering is optional and only activates when a field uses `render_mode: "stamp"` or when `stamp_overlays` are configured.

## What the Project Does

- Edit a form template visually with OpenCV.
- Save field coordinates into a layout JSON file.
- Generate many synthetic filled forms from a JSON config.
- Render normal computer text and checkboxes.
- Render realistic stamp content with uneven ink, blur, ghosting, crop, scan-like degradation, and black handwriting/signature overlays.
- Save a metadata JSON next to each generated image.

## Installation

Requirements:
- Python `3.11+`
- A working virtual environment for the repository

Install dependencies:

```bash
uv sync
```

## Quick Start

Edit a template:

```bash
python main.py edit --template template.png
```

Generate a normal sample set without stamps:

```bash
python main.py generate --template examples/without_stempel/example.png --config examples/without_stempel/config.json --gennum 20 --outputfolder out/without_stempel --outputtype png
```

Generate samples with realistic stamps:

```bash
python main.py generate --template examples/with_stempel/example.png --config examples/with_stempel/config.json --gennum 20 --outputfolder out/with_stempel --outputtype png
```

## CLI Reference

### Edit mode

```bash
python main.py edit --template template.png
```

Editor controls:
- `t`: create a text field
- `c`: create a checkbox
- `st`: create a stamp field (layout type `stamp`)
- `ca`: create a checkbox group
- `s`: save layout JSON
- `q`: quit

### Generate mode

```bash
python main.py generate --template template.png --config config.json --gennum 20 --outputfolder out --outputtype png
```

Arguments:
- `--template` / `-t`: template image path
- `--config` / `-c`: generator config path
- `--gennum` / `-n`: number of images to generate
- `--outputfolder` / `-f`: output directory
- `--outputtype` / `-o`: image format such as `png` or `jpg`
- `--data-path` / `-d`: optional extra JSON data file

## Project Structure

- [main.py](main.py): CLI entrypoint
- [generator.py](generator.py): generation pipeline and stamp integration
- [dataGenFunctions.py](dataGenFunctions.py): generator functions for text, checkboxes, and stamp payloads
- `stempel_module/`: stamp rendering subsystem
- `examples/without_stempel/`: baseline example with no stamp
- `examples/with_stempel/`: example with realistic stamp overlay
- `tests/`: unit tests

## Core Config Structure

The generator config uses these top-level sections:

```json
{
  "template": "example.png",
  "layout": "example.json",
  "global": {},
  "fields": {},
  "stamp_presets": {},
  "stamp_overlays": []
}
```

Meaning:
- `template`: image used as the source form
- `layout`: layout JSON created by the editor
- `global`: default rendering settings
- `fields`: per-field generation config
- `stamp_presets`: optional project-specific preset overrides or additions
- `stamp_overlays`: optional stamp blocks that render independently of normal fields

## Standard Field Configuration

Normal text and checkbox fields still work exactly as before.

Example:

```json
{
  "fields": {
    "name": {
      "generator": "from_list",
      "presence_prob": 1.0,
      "style": "computer",
      "params": {
        "values": ["Mueller", "Schmidt"]
      }
    }
  }
}
```

Important field keys:
- `generator`: function name from `DataGenFunctions`
- `presence_prob`: probability the field appears
- `style`: current normal text rendering style
- `params`: parameters passed to the generator function

## Stamp System Overview

The stamp system is Pillow-based and is separate from the normal `cv2.putText(...)` path. OpenCV is still used for the base image and checkbox drawing, but stamp drawing uses layered RGBA rendering so it can support realistic local damage and overlays.

Two stamp entry points are supported:

1. Stamp inside a normal text field
2. Independent stamp overlay block

### Variant 1: Stamp field from editor (`type: "stamp"`)

You can now create stamp regions directly in editor mode with `st`.

Example layout entry produced by the editor:

```json
{
  "name": "arztstempel_region",
  "type": "stamp",
  "x1": 620,
  "y1": 150,
  "x2": 1120,
  "y2": 410
}
```

To render this field, configure `fields.<name>.generator` in config:

```json
{
  "fields": {
    "arztstempel_region": {
      "generator": "doctor_stamp_lines",
      "presence_prob": 0.85,
      "params": {
        "preset": "medical_with_black_signature"
      }
    }
  }
}
```

### Variant 2: Stamp as a text field


Use this when a field region should behave like a stamp instead of normal text.

```json
{
  "fields": {
    "arztstempel": {
      "generator": "doctor_stamp_lines",
      "render_mode": "stamp",
      "presence_prob": 0.85,
      "params": {
        "preset": "medical_with_black_signature",
        "line_template": [
          "Dr. med. {full_name}",
          "Facharzt fuer {specialty}",
          "{street}",
          "{postcode} {city}",
          "BSNR: {bsnr}"
        ]
      }
    }
  }
}
```

How it works:
- the field still comes from the normal layout JSON
- the configured generator returns a structured payload with stamp lines
- `generator.py` detects `render_mode: "stamp"`
- the renderer switches from normal text drawing to the stamp subsystem

### Variant 3: Independent stamp overlay

Use this when the stamp is not tied to a text field and should be placed as a separate overlay region.

```json
{
  "stamp_overlays": [
    {
      "name": "arztstempel_overlay_1",
      "presence_prob": 0.8,
      "region": {
        "x1": 620,
        "y1": 150,
        "x2": 1120,
        "y2": 410
      },
      "generator": "doctor_stamp_lines",
      "params": {
        "preset": "medical_with_black_signature",
        "line_template": [
          "Dr. med. {full_name}",
          "Facharzt fuer {specialty}",
          "{street}",
          "{postcode} {city}",
          "Tel.: {phone}",
          "BSNR: {bsnr}"
        ]
      }
    }
  ]
}
```

How it works:
- the overlay does not require a layout field entry
- the region is defined directly in the config
- the overlay is rendered after the normal layout fields
- this is usually the most flexible way to add stamps to an existing form

## Stamp Presets

Built-in presets currently available in [stempel_module/stamp_presets.py](stempel_module/stamp_presets.py):

- `clean`
- `light_faded`
- `medical_faded`
- `medical_uneven_ink`
- `medical_with_black_signature`
- `medical_with_black_handwriting`
- `medical_ghosted`
- `medical_washed_out`
- `medical_extreme_scan`

Preset intent:
- `clean`: almost no damage, close to a fresh stamp
- `light_faded`: mild fade and mild blur
- `medical_faded`: stronger per-character variation and fade
- `medical_uneven_ink`: more line/section-based unevenness
- `medical_with_black_signature`: faded stamp with black signature overlay
- `medical_with_black_handwriting`: faded stamp with text-style black note overlay
- `medical_ghosted`: stronger double-stamp tendency
- `medical_washed_out`: washed and weak stamp
- `medical_extreme_scan`: degraded scan/fax style output

You can define your own presets under `stamp_presets` in a config. Project-level presets override or extend the built-ins.

Example:

```json
{
  "stamp_presets": {
    "my_heavy_red_stamp": {
      "effects": {
        "ink_color": [160, 60, 60],
        "opacity_min": 0.25,
        "opacity_max": 0.70,
        "visibility_mode": "per_section",
        "ghost_prob": 0.25,
        "blur_radius_min": 0.7,
        "blur_radius_max": 1.4
      },
      "handwriting": {
        "enabled": true,
        "mode": "signature"
      }
    }
  }
}
```

## Stamp Effects and Configuration

The stamp renderer is driven by two main dataclasses:
- `StampEffects`
- `HandwritingOverlaySpec`

Their defaults are defined in [stempel_module/stamp_models.py](stempel_module/stamp_models.py).

### `StampEffects` fields

- `ink_color`: base RGB ink color, usually blue or purple-like
- `opacity_min`, `opacity_max`: visibility range used when sampling glyph and section opacity
- `visibility_mode`: one of `uniform`, `per_character`, `per_word`, `per_section`
- `char_dropout_prob`: chance of heavily weakening individual characters
- `word_dropout_prob`: chance of weakening words
- `section_dropout_prob`: chance of weakening whole sections/lines
- `missing_ink_prob`: chance of applying clustered missing ink
- `missing_ink_strength`: strength of the missing-ink mask
- `blur_radius_min`, `blur_radius_max`: sampled blur range
- `rotation_min`, `rotation_max`: normal rotation range
- `strong_rotation_prob`: chance to use the strong rotation path
- `strong_rotation_min`, `strong_rotation_max`: stronger rotation range
- `ghost_prob`: chance to create a ghost/double stamp
- `ghost_offset_min`, `ghost_offset_max`: offset range for ghost placement
- `ghost_opacity_min`, `ghost_opacity_max`: alpha range for ghost stamp
- `washed_out_prob`: chance to desaturate and weaken the stamp
- `washed_out_strength_min`, `washed_out_strength_max`: washed-out intensity range
- `edge_fade_prob`: chance to weaken edges
- `crop_prob`: chance to apply internal crop and stronger placement offset
- `crop_max_ratio`: maximum crop ratio per side
- `paper_bleed_prob`: chance to modulate stamp alpha by paper brightness
- `scan_noise_prob`: chance to add scan/noise/banding style degradation
- `jpeg_artifact_prob`: chance to apply JPEG-like compression artifacts

### Visibility modes

`uniform`:
- one opacity tendency for the whole stamp
- use this when you want a mostly clean stamp

`per_character`:
- each character can fade independently
- best when you want weak letters like `Dr.` or partially missing characters

`per_word`:
- entire words vary together
- useful for address lines or stamps where one word is much weaker

`per_section`:
- different lines or sections vary separately
- useful when title, address, or BSNR line should have different intensities

### `HandwritingOverlaySpec` fields

- `enabled`: enable black overlay rendering
- `color`: RGB color, typically dark gray or black
- `mode`: `text`, `signature`, or `text_or_signature`
- `text_prob`: probability for text when mixed mode is used
- `signature_prob`: probability for signature when mixed mode is used
- `overlap_prob`: chance that the handwriting overlay is actually applied
- `rotation_min`, `rotation_max`: handwriting rotation
- `text_values`: optional values for handwritten notes
- `opacity_min`, `opacity_max`: handwriting opacity range
- `line_width_min`, `line_width_max`: signature stroke width range

## Stamp Content Generators

The new stamp-related generators live in [dataGenFunctions.py](dataGenFunctions.py).

Available helpers:
- `doctor_stamp_lines`
- `doctor_name`
- `doctor_specialty`
- `doctor_bsnr`
- `doctor_lanr`
- `doctor_phone`
- `handwritten_note`

### `doctor_stamp_lines(params)`

This is the main stamp payload generator. It returns a structure like:

```json
{
  "preset": "medical_with_black_signature",
  "lines": [
    { "text": "Dr. med. Anna Schmidt", "section_id": "line_0", "font_size": 28 },
    { "text": "Facharzt fuer Allgemeinmedizin", "section_id": "line_1", "font_size": 28 }
  ],
  "fields": {
    "full_name": "Anna Schmidt",
    "city": "Berlin",
    "street": "Hauptstrasse 12",
    "postcode": "10115",
    "phone": "030 1234567",
    "bsnr": "123456789",
    "lanr": "123456789"
  }
}
```

Useful parameters:
- `preset`
- `line_template`
- `font_size`
- `first_names`
- `last_names`
- `specialties`
- `cities`
- `streets`
- `titles`
- `area_codes`
- `bsnr_min`, `bsnr_max`
- `lanr_min`, `lanr_max`

Example:

```json
{
  "generator": "doctor_stamp_lines",
  "params": {
    "preset": "medical_faded",
    "font_size": 30,
    "titles": ["Dr. med.", "PD Dr."],
    "specialties": ["Dermatologie", "Neurologie"],
    "cities": ["Berlin", "Hamburg"],
    "line_template": [
      "{doctor_name}",
      "Facharzt fuer {specialty}",
      "{street}",
      "{postcode} {city}",
      "LANR: {lanr}",
      "BSNR: {bsnr}"
    ]
  }
}
```

## Full Configuration Examples

### Example A: Text field rendered as stamp

```json
{
  "fields": {
    "arztstempel": {
      "generator": "doctor_stamp_lines",
      "render_mode": "stamp",
      "presence_prob": 0.85,
      "params": {
        "preset": "medical_with_black_handwriting",
        "line_template": [
          "{doctor_name}",
          "Facharzt fuer {specialty}",
          "{street}",
          "{postcode} {city}",
          "Tel.: {phone}"
        ]
      }
    }
  }
}
```

### Example B: Standalone overlay with custom preset override

```json
{
  "stamp_presets": {
    "my_stamp": {
      "effects": {
        "ink_color": [120, 75, 150],
        "visibility_mode": "per_section",
        "opacity_min": 0.20,
        "opacity_max": 0.75,
        "ghost_prob": 0.3
      },
      "handwriting": {
        "enabled": true,
        "mode": "text_or_signature",
        "text_values": ["gez.", "i.A.", "ok"]
      }
    }
  },
  "stamp_overlays": [
    {
      "name": "approval_stamp",
      "presence_prob": 0.9,
      "region": {
        "x1": 700,
        "y1": 180,
        "x2": 1120,
        "y2": 420
      },
      "generator": "doctor_stamp_lines",
      "params": {
        "preset": "my_stamp",
        "line_template": [
          "{doctor_name}",
          "{street}",
          "{postcode} {city}",
          "BSNR: {bsnr}"
        ]
      }
    }
  ]
}
```

## Output Metadata

Every generated image gets a sibling JSON metadata file.

Stamp metadata includes sampled values such as:
- preset name
- region
- line, word, and character counts
- visibility mode
- sampled opacity min/max
- blur radius
- whether washed-out effect was applied
- whether ghosting was applied
- whether crop was applied
- whether handwriting/signature was applied
- placement offset

This is useful for debugging realism and for future deterministic replay support.

## Examples Directory

See [examples/README.md](examples/README.md) for a guide to the example folders.

Folders:
- [examples/without_stempel/config.json](examples/without_stempel/config.json): baseline config
- [examples/with_stempel/config.json](examples/with_stempel/config.json): stamp-enabled config

## Q&A

### Does the new stamp system break existing configs?

No. Existing configs still use the old text and checkbox rendering path unless stamp-specific config is added.

### When should I use `render_mode: "stamp"` instead of `stamp_overlays`?

Use `render_mode: "stamp"` when the stamp belongs to a known field region in the layout. Use `stamp_overlays` when you want the stamp to be configured independently of layout fields or added after the normal fields.

### Can I still use normal text and checkboxes in the same document?

Yes. The generator supports normal fields and stamp rendering in the same sample.

### How do I make a stamp look more faded?

Use a weaker preset such as `medical_faded` or reduce `opacity_min` and `opacity_max`, increase `missing_ink_prob`, and increase blur or washed-out probabilities.

### How do I get per-character fading?

Set `visibility_mode` to `per_character`. That is the best option when individual letters should weaken differently.

### How do I get line-based or section-based variation?

Set `visibility_mode` to `per_section`. Each line or section can then get a different sampled opacity profile.

### How do I add handwriting or a black signature on top?

Enable handwriting in the preset or config and set `mode` to `text`, `signature`, or `text_or_signature`.

### Can I create my own preset in the config file?

Yes. Add a `stamp_presets` block. Custom presets are merged with the built-in presets and can override them by name.

### Where do the stamp lines come from?

Usually from `doctor_stamp_lines(params)`, which creates structured lines from random doctor data and the `line_template`.

### Can I render more than one stamp on a document?

Yes. Add multiple entries to `stamp_overlays`.

### Is the stamp renderer deterministic?

Not yet by explicit seed control. It uses random sampling internally. Deterministic generation can be added later by introducing seed plumbing through the pipeline.




