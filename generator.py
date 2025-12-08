import cv2
import json
import os
import random
from datetime import datetime, timedelta

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

        with open(cfg.config_path, "r") as f:
            self.gen_conf = json.load(f)

        layout_path = self.gen_conf.get(
            "layout",
            os.path.splitext(cfg.template)[0] + ".json"
        )

        with open(layout_path, "r") as f:
            self.layout = json.load(f)

        global_cfg = self.gen_conf.get("global", {})
        self.presence_default = global_cfg.get("default_presence_prob", 1.0)
        self.style_default = global_cfg.get("default_style", "computer")
        self.scale = global_cfg.get("font_scale", 0.6)
        self.thickness = global_cfg.get("font_thickness", 1)

        self.field_cfg = self.gen_conf.get("fields", {})

        self.data_store = None
        if cfg.data_path and os.path.exists(cfg.data_path):
            with open(cfg.data_path, "r") as f:
                self.data_store = json.load(f)

        # Instantiate the data generator class
        self.data_gen = DataGenFunctions(self.data_store)

        os.makedirs(cfg.outputfolder, exist_ok=True)

    # ============================
    # DYNAMIC FUNCTION LOOKUP 🚀
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
        for i in range(self.cfg.gennum):
            img = self.template_img.copy()
            self.render_sample(img)

            out_path = os.path.join(
                self.cfg.outputfolder,
                f"sample_{i+1}.{self.cfg.outputtype}"
            )
            cv2.imwrite(out_path, img)
            print("Saved:", out_path)

    # ============================
    # SAMPLE RENDERING
    # ============================
    def render_sample(self, img):
        for field in self.layout:
            name = field["name"]
            ftype = field["type"]

            cfg = self.field_cfg.get(name, {})
            p = cfg.get("presence_prob", self.presence_default)

            # missing probability
            if random.random() > p:
                continue

            gen_name = cfg.get("generator")
            params = cfg.get("params", {})

            # --- TEXT FIELD ---
            if ftype == "text":
                if not gen_name:
                    continue
                func = self.get_func(gen_name)
                if not func:
                    continue
                value = func(params)
                if not value:
                    continue
                self.draw_text(img, field, value, cfg.get("style", self.style_default))

            # --- SINGLE CHECKBOX ---
            elif ftype == "checkbox":
                func = self.get_func(gen_name or "checkbox_binary")
                if func(params):
                    self.draw_checkbox(img, field)

            # --- CHECKBOX GROUP ---
            elif ftype == "checkbox_group":
                func = self.get_func(gen_name or "checkbox_group_random")
                children = field["children"]
                selection = func({"children": children, **params})
                by_name = {c["name"]: c for c in children}

                for cname in selection:
                    if cname in by_name:
                        self.draw_checkbox(img, by_name[cname])

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
