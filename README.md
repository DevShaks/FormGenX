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
uv sync
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

## Disclaimer
This repository and all generated outputs (including images, metadata, synthetic forms, stamps, handwriting overlays, and related artifacts) are provided strictly for educational, research, testing, and demonstration purposes.
All generated data is synthetic and fictitious. It must not be used, relied upon, or deployed in any real-world application, production system, operational workflow, compliance process, medical process, legal process, governmental process, financial system, identity verification process, or decision-making system.
This project is not intended to create or support documents, artifacts, or data for real-world use, impersonation, fraud, or misrepresentation.
No representation or warranty is made regarding the accuracy, completeness, safety, legality, compliance, or fitness of the generated data for any purpose. Any resemblance to real persons, institutions, identifiers, documents, or records is purely coincidental.
By using this repository, users agree that all usage remains limited to lawful educational or experimental contexts. Any use outside these contexts is undertaken entirely at the user's own risk and responsibility.

### Ethical Use
This project is intended to support research, experimentation, and educational work related to synthetic data generation, machine learning, and computer vision. Users are expected to use this repository responsibly and in accordance with applicable laws and ethical standards.
The tools and generated outputs provided by this repository must not be used to create deceptive materials, impersonate individuals or institutions, produce fraudulent documents, or otherwise mislead people or systems.
Any misuse of this project for illegal, harmful, deceptive, or unethical purposes is strictly discouraged and is solely the responsibility of the user.

### Dataset Limitations
All generated images, documents, metadata, and related artifacts produced by this repository are synthetic and may contain inaccuracies, unrealistic artifacts, structural inconsistencies, or incomplete representations of real-world documents.
These outputs are not intended to reflect real institutions, official document formats, or authentic administrative processes. The generated data may also contain biases or simplifications introduced by the generation process.
Users should treat all generated outputs strictly as experimental or illustrative data and should not assume correctness, realism, or suitability for real-world applications.
