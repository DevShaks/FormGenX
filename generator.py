import cv2
import json
import os
import random
import getpass
from datetime import datetime

from dataGenFunctions import DataGenFunctions
from stempel_module.stamp_renderer import render_stamp_on_image


# ============================
# GENERATOR CONFIG
# ============================
class GeneratorConfig:
    def __init__(self, template, config_path, gennum, outputfolder, outputtype, data_path=None):
        self.template = template
        self.config_path = config_path
        self.gennum = gennum
        self.outputfolder = outputfolder
        self.outputtype = outputtype
        self.data_path = data_path


# ============================
# GENERATOR IMPLEMENTATION
# ============================
class Generator:
    def __init__(self, cfg: GeneratorConfig):
        self.cfg = cfg

        self.template_img = cv2.imread(cfg.template)
        if self.template_img is None:
            raise FileNotFoundError("Template not found: " + cfg.template)

        with open(cfg.config_path, "r", encoding="utf-8") as f:
            self.gen_conf = json.load(f)

        layout_path = self.gen_conf.get("layout", os.path.splitext(cfg.template)[0] + ".json")

        with open(layout_path, "r", encoding="utf-8") as f:
            self.layout = json.load(f)

        self.layout_path = layout_path

        global_cfg = self.gen_conf.get("global", {})
        self.presence_default = global_cfg.get("default_presence_prob", 1.0)
        self.style_default = global_cfg.get("default_style", "computer")
        self.scale = global_cfg.get("font_scale", 0.6)
        self.thickness = global_cfg.get("font_thickness", 1)

        self.field_cfg = self.gen_conf.get("fields", {})
        self.stamp_presets = self.gen_conf.get("stamp_presets", {})
        self.stamp_overlays = self.gen_conf.get("stamp_overlays", [])

        self.data_store = None
        if cfg.data_path and os.path.exists(cfg.data_path):
            with open(cfg.data_path, "r", encoding="utf-8") as f:
                self.data_store = json.load(f)

        self.data_gen = DataGenFunctions(self.data_store)

        os.makedirs(cfg.outputfolder, exist_ok=True)

    # ============================
    # FUNCTION LOOKUP
    # ============================
    def get_func(self, name: str):
        func = getattr(self.data_gen, name, None)

        if func is None:
            print(f"[WARN] Generator function '{name}' not found.")
            return None

        if not callable(func):
            print(f"[WARN] '{name}' exists but is not callable.")
            return None

        return func

    # ============================
    # MAIN LOOP
    # ============================
    def run(self):
        for idx in range(self.cfg.gennum):
            img = self.template_img.copy()
            fields = self.render_sample(img)

            image_path = self._build_output_path(idx)
            self.save_image(img, image_path)

            metadata = self.build_metadata(fields, idx, image_path)
            self.save_metadata(metadata, image_path)

    # ============================
    # SAMPLE RENDERING
    # ============================
    def render_sample(self, img):
        entries = []
        for field in self.layout:
            entries.append(self._process_field(field, img))

        overlay_entries = self._render_stamp_overlays(img)
        entries.extend(overlay_entries)
        return entries

    def _process_field(self, field, img):
        name = field["name"]
        ftype = field["type"]
        cfg = self.field_cfg.get(name, {})
        params = dict(cfg.get("params", {}))

        record = {
            "name": name,
            "type": ftype,
            "generator": cfg.get("generator"),
            "params": params,
            "presence_prob": cfg.get("presence_prob", self.presence_default),
            "active": False,
            "drawn": False,
            "value": None,
            "status": "pending",
        }

        record["coords"] = self._extract_coords(field)

        if not self._should_render_field(record["presence_prob"]):
            record["status"] = "skipped_by_presence_prob"
            return record

        record["active"] = True

        if ftype == "text":
            return self._handle_text_field(field, cfg, record, img)
        if ftype == "stamp":
            return self._handle_stamp_field(field, cfg, record, img)
        if ftype == "checkbox":
            return self._handle_checkbox_field(field, cfg, record, img)
        if ftype == "checkbox_group":
            return self._handle_checkbox_group(field, cfg, record, img)

        record["status"] = "unsupported_field_type"
        return record

    def _should_render_field(self, probability):
        return random.random() <= probability

    def _handle_text_field(self, field, cfg, record, img):
        generator_name = cfg.get("generator")
        if not generator_name:
            record["status"] = "no_generator_configured"
            return record

        func = self.get_func(generator_name)
        if not func:
            record["status"] = "missing_generator_function"
            return record

        value = func(record["params"])
        record["value"] = value
        style = cfg.get("style", self.style_default)
        record["style"] = style

        if not value:
            record["status"] = "no_value_generated"
            return record

        render_mode = cfg.get("render_mode", "text")
        record["render_mode"] = render_mode

        if render_mode == "stamp":
            payload = value if isinstance(value, dict) else {"lines": [str(value)]}
            img, stamp_meta = self.draw_stamp(img=img, field=field, payload=payload, cfg=cfg)
            record["value"] = payload
            record["stamp_meta"] = stamp_meta
            record["drawn"] = True
            record["status"] = "rendered_stamp"
            return record

        self.draw_text(img, field, value, style)
        record["drawn"] = True
        record["status"] = "rendered"
        return record

    def _handle_stamp_field(self, field, cfg, record, img):
        generator_name = cfg.get("generator")
        if not generator_name:
            record["status"] = "no_generator_configured"
            return record

        func = self.get_func(generator_name)
        if not func:
            record["status"] = "missing_generator_function"
            return record

        payload = func(record["params"])
        if not payload:
            record["status"] = "no_value_generated"
            return record

        payload = payload if isinstance(payload, dict) else {"lines": [str(payload)]}
        img, stamp_meta = self.draw_stamp(img=img, field=field, payload=payload, cfg=cfg)

        record["value"] = payload
        record["render_mode"] = "stamp"
        record["stamp_meta"] = stamp_meta
        record["drawn"] = True
        record["status"] = "rendered_stamp"
        return record

    def _handle_checkbox_field(self, field, cfg, record, img):
        generator_name = cfg.get("generator") or "checkbox_binary"
        record["generator"] = generator_name

        func = self.get_func(generator_name)
        if not func:
            record["status"] = "missing_generator_function"
            return record

        value = bool(func(record["params"]))
        record["value"] = value

        if value:
            self.draw_checkbox(img, field)
            record["drawn"] = True
            record["status"] = "checked"
        else:
            record["status"] = "unchecked"
        return record

    def _handle_checkbox_group(self, field, cfg, record, img):
        generator_name = cfg.get("generator") or "checkbox_group_random"
        record["generator"] = generator_name

        func = self.get_func(generator_name)
        if not func:
            record["status"] = "missing_generator_function"
            return record

        children = field.get("children", [])
        child_map = {}
        child_infos = []
        for child in children:
            child_map[child["name"]] = child
            child_infos.append({"name": child["name"], "coords": self._extract_coords(child)})
        record["children"] = child_infos

        render_params = {**record["params"], "children": children}
        selection = func(render_params) or []
        record["value"] = selection

        if selection:
            for child_name in selection:
                child_field = child_map.get(child_name)
                if child_field:
                    self.draw_checkbox(img, child_field)
            record["drawn"] = True
            record["status"] = "selection"
        else:
            record["status"] = "no_selection"
        return record

    def _extract_coords(self, field):
        coords = {}
        for key in ("x1", "y1", "x2", "y2"):
            if key in field:
                coords[key] = field[key]
        return coords

    def _overlay_region(self, overlay_cfg):
        region = overlay_cfg.get("region", {})
        if all(k in region for k in ("x1", "y1", "x2", "y2")):
            return {
                "x1": int(region["x1"]),
                "y1": int(region["y1"]),
                "x2": int(region["x2"]),
                "y2": int(region["y2"]),
            }

        if all(k in overlay_cfg for k in ("x1", "y1", "x2", "y2")):
            return {
                "x1": int(overlay_cfg["x1"]),
                "y1": int(overlay_cfg["y1"]),
                "x2": int(overlay_cfg["x2"]),
                "y2": int(overlay_cfg["y2"]),
            }
        return None

    def _render_stamp_overlays(self, img):
        records = []
        for index, overlay_cfg in enumerate(self.stamp_overlays):
            name = overlay_cfg.get("name", f"stamp_overlay_{index + 1}")
            params = dict(overlay_cfg.get("params", {}))
            presence_prob = overlay_cfg.get("presence_prob", self.presence_default)
            generator_name = overlay_cfg.get("generator")

            region = self._overlay_region(overlay_cfg)
            record = {
                "name": name,
                "type": "stamp_overlay",
                "generator": generator_name,
                "params": params,
                "presence_prob": presence_prob,
                "active": False,
                "drawn": False,
                "value": None,
                "status": "pending",
                "coords": region,
            }

            if region is None:
                record["status"] = "missing_region"
                records.append(record)
                continue

            if not self._should_render_field(presence_prob):
                record["status"] = "skipped_by_presence_prob"
                records.append(record)
                continue

            record["active"] = True

            payload = None
            if generator_name:
                func = self.get_func(generator_name)
                if not func:
                    record["status"] = "missing_generator_function"
                    records.append(record)
                    continue
                payload = func(params)
            else:
                payload = {
                    "lines": overlay_cfg.get("lines", []),
                    "preset": params.get("preset", overlay_cfg.get("preset", "medical_with_black_signature")),
                }

            if not payload:
                record["status"] = "no_value_generated"
                records.append(record)
                continue

            stamp_cfg = {
                "params": params,
                "preset": params.get("preset", overlay_cfg.get("preset")),
                "stamp": overlay_cfg.get("stamp", {}),
            }
            img2, stamp_meta = render_stamp_on_image(
                base_img_bgr=img,
                region=region,
                stamp_payload=payload,
                cfg=stamp_cfg,
                rng=random,
                preset_map=self.stamp_presets,
            )
            img[:] = img2

            record["value"] = payload
            record["stamp_meta"] = stamp_meta
            record["drawn"] = True
            record["status"] = "rendered_stamp_overlay"
            records.append(record)

        return records

    # ============================
    # OUTPUT HELPERS
    # ============================
    def _build_output_path(self, index):
        name = f"sample_{index + 1}.{self.cfg.outputtype}"
        return os.path.join(self.cfg.outputfolder, name)

    def save_image(self, img, path):
        cv2.imwrite(path, img)
        print("Saved:", path)

    def _to_rel_path(self, path):
        if not path:
            return None
        try:
            return os.path.relpath(os.path.abspath(path), os.getcwd())
        except ValueError:
            # Fallback for uncommon cross-drive situations on Windows.
            return path

    def build_metadata(self, fields, sample_index, image_path):
        return {
            "sample_index": sample_index + 1,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "filled_by": getpass.getuser(),
            "template_path": self._to_rel_path(self.cfg.template),
            "layout_path": self._to_rel_path(self.layout_path),
            "config_path": self._to_rel_path(self.cfg.config_path),
            "data_path": self._to_rel_path(self.cfg.data_path),
            "output_image": self._to_rel_path(image_path),
            "fields": fields,
        }

    def save_metadata(self, metadata, image_path):
        metadata_path = self._metadata_path_for(image_path)
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        print("Saved metadata:", metadata_path)

    def _metadata_path_for(self, image_path):
        base = os.path.splitext(image_path)[0]
        return base + ".json"

    # ============================
    # DRAW HELPERS
    # ============================
    def draw_text(self, img, field, text, style):
        x1, y1, x2, y2 = field["x1"], field["y1"], field["x2"], field["y2"]
        height = y2 - y1
        pos = (x1 + 2, y1 + int(height * 0.7))

        scale = self.scale if style == "computer" else self.scale * 0.9

        cv2.putText(
            img,
            str(text),
            pos,
            cv2.FONT_HERSHEY_SIMPLEX,
            scale,
            (0, 0, 0),
            self.thickness,
            cv2.LINE_AA,
        )

    def draw_checkbox(self, img, field):
        x1, y1, x2, y2 = field["x1"], field["y1"], field["x2"], field["y2"]
        cv2.line(img, (x1, y1), (x2, y2), (0, 0, 0), 2)
        cv2.line(img, (x1, y2), (x2, y1), (0, 0, 0), 2)

    def draw_stamp(self, img, field, payload, cfg):
        region = {
            "x1": field["x1"],
            "y1": field["y1"],
            "x2": field["x2"],
            "y2": field["y2"],
        }
        updated_img, stamp_meta = render_stamp_on_image(
            base_img_bgr=img,
            region=region,
            stamp_payload=payload,
            cfg=cfg,
            rng=random,
            preset_map=self.stamp_presets,
        )
        img[:] = updated_img
        return img, stamp_meta

