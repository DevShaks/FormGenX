# Formular Test Data Generator

This project provides a complete workflow for creating synthetic form datasets. It includes a visual editor for defining field regions on a template image and a generator that fills these templates with synthetic data. The system is fully extensible and allows adding new data generation functions without modifying the generator code. The license is intentionally open so it can be used commercially as long as it remains open.

## Features

- Visual template editor using OpenCV.
- Supports text fields, single checkboxes, and checkbox groups.
- Generates synthetic datasets with realistic variability.
- Configurable data generation through external JSON files.
- Dynamic discovery of generation functions.
- Outputs image-based form examples.
- Stores a JSON per sample that captures who filled the form and which values/checks were applied.
- Fully open licensing for commercial use.

## Installation

1. Install Python 3.10 or higher.
2. Install dependencies:

```
pip install opencv-python
```

3. Place your template image in the project folder.

## Usage

### 1. Editing a Template

Run the editor to define text fields and checkbox areas on your template:

```
python main.py edit --template template.png
```

Controls:
- t for text fields
- c for single checkbox fields
- ca for checkbox groups
- s to save annotations
- q to quit

A JSON layout file will be generated automatically.

### 2. Generating Data

Use a config JSON to map fields to generator functions.

Example:

```
python main.py generate --template example.png --config config.json --gennum 20 --outputfolder out --outputtype png
```

The generator will create multiple synthetic example images based on the template and configuration.

Each output sample now produces a companion JSON file in the same folder. The metadata file shares the image's base name and ends with `.json` (for example `sample_1.json`) and records when the form was generated, who triggered the run, and the exact field values or checkbox selections that were written to the image.

