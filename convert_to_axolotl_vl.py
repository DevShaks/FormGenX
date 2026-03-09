import os
import json
import shutil
from pathlib import Path

# ---------------- CONFIG ----------------

INPUT_DIR = "out"      # your raw data folder
OUTPUT_DIR = "dataset" # your target data folder
IMAGES_DIR = os.path.join(OUTPUT_DIR, "images")
OUTPUT_JSONL = os.path.join(OUTPUT_DIR, "train.jsonl")

INSTRUCTION_TEXT = (
    "Extract all form fields from this document and return the result as structured JSON. "
    "Return ONLY valid JSON. Do not include explanations."
)

# Optional key normalization
KEY_MAP = {
    "geb": "birth_date",
    "strasse": "street",
    "telefon": "phone",
    "beruf": "profession",
    "verart": "insurance",
    "warten": "reason_for_visit",
    "alergia": "allergies",
    "erkrankung": "conditions"
}

# ---------------- HELPERS ----------------

def normalize_key(key: str) -> str:
    return KEY_MAP.get(key, key)

def extract_fields(annotation_json: dict) -> dict:
    result = {}

    for field in annotation_json.get("fields", []):
        name = field.get("name")
        value = field.get("value")

        if value is None:
            continue

        key = normalize_key(name)

        # Checkbox groups → arrays
        if isinstance(value, list):
            result[key] = value
        else:
            result[key] = value

    return result

# ---------------- MAIN ----------------

def main():
    input_path = Path(INPUT_DIR)
    output_path = Path(OUTPUT_DIR)
    images_path = Path(IMAGES_DIR)

    if not input_path.exists():
        raise FileNotFoundError(f"Input folder not found: {INPUT_DIR}")

    # Create output folders
    output_path.mkdir(exist_ok=True)
    images_path.mkdir(exist_ok=True)

    samples_written = 0

    with open(OUTPUT_JSONL, "w", encoding="utf-8") as jsonl_file:
        for json_file in input_path.glob("*.json"):
            base_name = json_file.stem
            image_file = input_path / f"{base_name}.png"

            if not image_file.exists():
                print(f"[WARN] Image missing for {json_file.name}, skipping.")
                continue

            # Load annotation
            with open(json_file, "r", encoding="utf-8") as f:
                annotation = json.load(f)

            extracted_data = extract_fields(annotation)

            # Copy image
            target_image_path = images_path / image_file.name
            shutil.copy(image_file, target_image_path)

            # Build Axolotl / Qwen2.5-VL sample
            sample = {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "image": f"images/{image_file.name}"
                            },
                            {
                                "type": "text",
                                "text": INSTRUCTION_TEXT
                            }
                        ]
                    },
                    {
                        "role": "assistant",
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(
                                    extracted_data,
                                    ensure_ascii=False,
                                    indent=2
                                )
                            }
                        ]
                    }
                ]
            }

            jsonl_file.write(json.dumps(sample, ensure_ascii=False) + "\n")
            samples_written += 1

    print(f"✅ Done. {samples_written} samples written to {OUTPUT_JSONL}")

if __name__ == "__main__":
    main()
