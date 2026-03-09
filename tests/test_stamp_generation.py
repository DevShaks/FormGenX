import json
import os
import tempfile
import unittest

import cv2
import numpy as np

from generator import Generator, GeneratorConfig


class TestStampGeneration(unittest.TestCase):
    def _write_json(self, path, data):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _blank_template(self, path, width=420, height=280):
        img = np.full((height, width, 3), 255, dtype=np.uint8)
        cv2.putText(img, "FORM TEXT", (20, 120), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (60, 60, 60), 2, cv2.LINE_AA)
        cv2.imwrite(path, img)

    def test_backward_compat_text_and_checkbox_generation(self):
        with tempfile.TemporaryDirectory() as td:
            template = os.path.join(td, "template.png")
            layout = os.path.join(td, "layout.json")
            config = os.path.join(td, "config.json")
            out_dir = os.path.join(td, "out")

            self._blank_template(template)
            self._write_json(
                layout,
                [
                    {"name": "name", "type": "text", "x1": 40, "y1": 30, "x2": 220, "y2": 60},
                    {"name": "accept", "type": "checkbox", "x1": 30, "y1": 180, "x2": 50, "y2": 200},
                ],
            )
            self._write_json(
                config,
                {
                    "template": template,
                    "layout": layout,
                    "global": {"default_presence_prob": 1.0},
                    "fields": {
                        "name": {
                            "generator": "from_list",
                            "presence_prob": 1.0,
                            "style": "computer",
                            "params": {"values": ["Alice"]},
                        },
                        "accept": {
                            "generator": "checkbox_binary",
                            "presence_prob": 1.0,
                            "params": {"true_prob": 1.0},
                        },
                    },
                },
            )

            gcfg = GeneratorConfig(template=template, config_path=config, gennum=1, outputfolder=out_dir, outputtype="png")
            gen = Generator(gcfg)

            img = gen.template_img.copy()
            fields = gen.render_sample(img)

            statuses = {f["name"]: f["status"] for f in fields if f["type"] != "stamp_overlay"}
            self.assertEqual(statuses["name"], "rendered")
            self.assertEqual(statuses["accept"], "checked")
            self.assertTrue((img < 250).any(), "Expected rendered ink on image")

    def test_stamp_overlay_render_and_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            template = os.path.join(td, "template.png")
            layout = os.path.join(td, "layout.json")
            config = os.path.join(td, "config.json")
            out_dir = os.path.join(td, "out")

            self._blank_template(template)
            self._write_json(layout, [])
            self._write_json(
                config,
                {
                    "template": template,
                    "layout": layout,
                    "global": {"default_presence_prob": 1.0},
                    "fields": {},
                    "stamp_overlays": [
                        {
                            "name": "arztstempel_1",
                            "presence_prob": 1.0,
                            "region": {"x1": 90, "y1": 70, "x2": 390, "y2": 230},
                            "generator": "doctor_stamp_lines",
                            "params": {
                                "preset": "medical_with_black_signature",
                                "line_template": [
                                    "Dr. med. {full_name}",
                                    "Facharzt fuer {specialty}",
                                    "{street}",
                                    "{postcode} {city}",
                                    "Tel.: {phone}",
                                ],
                            },
                        }
                    ],
                },
            )

            gcfg = GeneratorConfig(template=template, config_path=config, gennum=1, outputfolder=out_dir, outputtype="png")
            gen = Generator(gcfg)

            img = gen.template_img.copy()
            fields = gen.render_sample(img)

            overlays = [f for f in fields if f["type"] == "stamp_overlay"]
            self.assertEqual(len(overlays), 1)
            overlay = overlays[0]
            self.assertEqual(overlay["status"], "rendered_stamp_overlay")
            self.assertTrue(overlay["drawn"])
            self.assertIn("stamp_meta", overlay)

            stamp_meta = overlay["stamp_meta"]
            self.assertEqual(stamp_meta["preset"], "medical_with_black_signature")
            self.assertIn("fx", stamp_meta)
            self.assertIn("rotation_deg", stamp_meta["fx"])
            self.assertIn("handwriting", stamp_meta)
            self.assertTrue(stamp_meta["handwriting"]["enabled"])
            self.assertTrue((img < 250).any(), "Expected visible stamp pixels")

    def test_text_field_stamp_mode_per_character_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            template = os.path.join(td, "template.png")
            layout = os.path.join(td, "layout.json")
            config = os.path.join(td, "config.json")
            out_dir = os.path.join(td, "out")

            self._blank_template(template)
            self._write_json(
                layout,
                [
                    {"name": "arztstempel", "type": "text", "x1": 60, "y1": 60, "x2": 380, "y2": 230},
                ],
            )
            self._write_json(
                config,
                {
                    "template": template,
                    "layout": layout,
                    "global": {"default_presence_prob": 1.0},
                    "fields": {
                        "arztstempel": {
                            "generator": "doctor_stamp_lines",
                            "render_mode": "stamp",
                            "presence_prob": 1.0,
                            "params": {
                                "preset": "medical_with_black_signature",
                                "line_template": [
                                    "Dr. med. {full_name}",
                                    "Facharzt fuer {specialty}",
                                    "BSNR: {bsnr}",
                                ],
                            },
                        }
                    },
                },
            )

            gcfg = GeneratorConfig(template=template, config_path=config, gennum=1, outputfolder=out_dir, outputtype="png")
            gen = Generator(gcfg)

            img = gen.template_img.copy()
            fields = gen.render_sample(img)

            stamp_records = [f for f in fields if f["name"] == "arztstempel"]
            self.assertEqual(len(stamp_records), 1)
            rec = stamp_records[0]
            self.assertEqual(rec["status"], "rendered_stamp")

            stamp_meta = rec["stamp_meta"]
            self.assertEqual(stamp_meta["visibility_mode"], "per_character")
            self.assertIsNotNone(stamp_meta["opacity_min_sampled"])
            self.assertIsNotNone(stamp_meta["opacity_max_sampled"])
            self.assertGreater(stamp_meta["opacity_max_sampled"], stamp_meta["opacity_min_sampled"])
            self.assertIn("blur_radius", stamp_meta["fx"])
            self.assertIn("ghost_applied", stamp_meta["fx"])
            self.assertTrue((img < 250).any(), "Expected visible stamp pixels")

    def test_stamp_layout_field_type_renders(self):
        with tempfile.TemporaryDirectory() as td:
            template = os.path.join(td, "template.png")
            layout = os.path.join(td, "layout.json")
            config = os.path.join(td, "config.json")
            out_dir = os.path.join(td, "out")

            self._blank_template(template)
            self._write_json(
                layout,
                [
                    {"name": "stamp_region", "type": "stamp", "x1": 70, "y1": 70, "x2": 360, "y2": 220},
                ],
            )
            self._write_json(
                config,
                {
                    "template": template,
                    "layout": layout,
                    "global": {"default_presence_prob": 1.0},
                    "fields": {
                        "stamp_region": {
                            "generator": "doctor_stamp_lines",
                            "presence_prob": 1.0,
                            "params": {
                                "preset": "medical_with_black_signature",
                                "line_template": [
                                    "Dr. med. {full_name}",
                                    "{street}",
                                    "{postcode} {city}",
                                ],
                            },
                        }
                    },
                },
            )

            gcfg = GeneratorConfig(template=template, config_path=config, gennum=1, outputfolder=out_dir, outputtype="png")
            gen = Generator(gcfg)

            img = gen.template_img.copy()
            fields = gen.render_sample(img)

            self.assertEqual(len(fields), 1)
            rec = fields[0]
            self.assertEqual(rec["type"], "stamp")
            self.assertEqual(rec["status"], "rendered_stamp")
            self.assertIn("stamp_meta", rec)
            self.assertTrue((img < 250).any(), "Expected visible stamp pixels")


if __name__ == "__main__":
    unittest.main()
