import cv2
import json
import os
import random
import getpass
from datetime import datetime

from dataGenFunctions import DataGenFunctions


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

        layout_path = self.gen_conf.get(
            "layout",
            os.path.splitext(cfg.template)[0] + ".json"
        )

        with open(layout_path, "r", encoding="utf-8") as f:
            self.layout = json.load(f)

        self.layout_path = layout_path

        global_cfg = self.gen_conf.get("global", {})
        self.presence_default = global_cfg.get("default_presence_prob", 1.0)
        self.style_default = global_cfg.get("default_style", "computer")
        self.scale = global_cfg.get("font_scale", 0.6)
        self.thickness = global_cfg.get("font_thickness", 1)

        self.field_cfg = self.gen_conf.get("fields", {})

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
            "status": "pending"
        }

        record["coords"] = self._extract_coords(field)

        if not self._should_render_field(record["presence_prob"]):
            record["status"] = "skipped_by_presence_prob"
            return record

        record["active"] = True

        if ftype == "text":
            return self._handle_text_field(field, cfg, record, img)
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

        self.draw_text(img, field, value, style)
        record["drawn"] = True
        record["status"] = "rendered"
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
            child_infos.append({
                "name": child["name"],
                "coords": self._extract_coords(child)
            })
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

    # ============================
    # OUTPUT HELPERS
    # ============================
    def _build_output_path(self, index):
        name = f"sample_{index + 1}.{self.cfg.outputtype}"
        return os.path.join(self.cfg.outputfolder, name)

    def save_image(self, img, path):
        cv2.imwrite(path, img)
        print("Saved:", path)

    def build_metadata(self, fields, sample_index, image_path):
        return {
            "sample_index": sample_index + 1,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "filled_by": getpass.getuser(),
            "template_path": os.path.abspath(self.cfg.template),
            "layout_path": os.path.abspath(self.layout_path),
            "config_path": os.path.abspath(self.cfg.config_path),
            "data_path": os.path.abspath(self.cfg.data_path) if self.cfg.data_path else None,
            "output_image": os.path.abspath(image_path),
            "fields": fields
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
            img, str(text), pos,
            cv2.FONT_HERSHEY_SIMPLEX,
            scale, (0, 0, 0),
            self.thickness, cv2.LINE_AA
        )

    def draw_checkbox(self, img, field):
        x1, y1, x2, y2 = field["x1"], field["y1"], field["x2"], field["y2"]
        cv2.line(img, (x1, y1), (x2, y2), (0, 0, 0), 2)
        cv2.line(img, (x1, y2), (x2, y1), (0, 0, 0), 2)
