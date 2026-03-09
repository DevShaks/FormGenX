# Examples

This folder contains two ready-to-run example setups for FormGenX.

## Folders

- [without_stempel/config.json](without_stempel/config.json): baseline generation with normal text and checkboxes only
- [with_stempel/config.json](with_stempel/config.json): same base form plus a realistic stamp overlay

Each example folder contains:
- `example.png`: template image
- `example.json`: layout file
- `config.json`: generator config

## Run the baseline example

```bash
python main.py generate --template examples/without_stempel/example.png --config examples/without_stempel/config.json --gennum 10 --outputfolder out/without_stempel --outputtype png
```

Use this example when you want to verify the original pipeline:
- normal text fields
- checkbox groups
- no stamp subsystem

## Run the stamp example

```bash
python main.py generate --template examples/with_stempel/example.png --config examples/with_stempel/config.json --gennum 10 --outputfolder out/with_stempel --outputtype png
```

Use this example when you want to verify:
- normal field generation still works
- `stamp_overlays` are active
- `doctor_stamp_lines` is used
- preset `medical_with_black_signature` is used
- output metadata includes stamp-specific sampled values

## What the stamp example demonstrates

The `with_stempel` config shows:
- independent overlay-based stamp rendering
- structured doctor stamp line generation
- per-character unevenness from the preset
- blur, fade, and possible ghosting
- black signature overlay support

## How to adapt an example

Common edits:
- change `presence_prob` to control appearance frequency
- change `preset` to switch realism profile
- edit `line_template` to change the visible stamp text
- change `region` to move the stamp
- add more entries to `stamp_overlays` for multiple stamps

## Recommended starting point

- Start with `without_stempel` if you only want to validate the existing pipeline.
- Start with `with_stempel` if you want to build stamp training data or tune realism effects.

