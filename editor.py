import cv2
import json
import os


class EditConfig:
    def __init__(self, template: str):
        self.template = template


class Editor:
    def __init__(self, config: EditConfig):
        self.template_path = config.template
        self.img = cv2.imread(self.template_path)

        if self.img is None:
            raise FileNotFoundError(f"Template not found: {self.template_path}")

        self.display_img = self.img.copy()
        self.fields = []

    # ============================
    # MAIN LOOP
    # ============================
    def run(self):
        print("=== FORMULAR EDITOR ===")

        while True:
            mode = self.ask_mode()

            if mode == "t":
                self.process_field_loop("text")

            elif mode == "c":
                self.process_field_loop("checkbox")

            elif mode == "ca":
                self.process_checkbox_area()

            elif mode == "s":
                end = self.template_path.split(".")[-1]
                cv2.imwrite(f"edited_image.{end}",self.display_img)
                self.save_json()

            elif mode == "q":
                print("Exiting editor.")
                break

    # ============================
    # MODE SELECTOR
    # ============================
    def ask_mode(self):
        print("\n--- Select mode ---")
        print("t: text field")
        print("c: checkbox field")
        print("ca: checkbox area (parent + children)")
        print("s: save")
        print("q: quit")

        while True:
            mode = input("Mode: ").lower().strip()
            if mode in ["t", "c", "ca", "s", "q"]:
                return mode
            print("Invalid mode. Use t/c/ca/s/q.")

    # ============================
    # SIMPLE TEXT OR CHECKBOX FIELD
    # ============================
    def process_field_loop(self, field_type):
        print(f"\n=== {field_type.upper()} MODE ACTIVE ===")
        print("Select area with mouse, press ENTER to confirm.")
        print("Press 'q' in ROI window to return to mode selection.")

        while True:
            roi = cv2.selectROI("Select Field", self.display_img,
                                showCrosshair=True, fromCenter=False)

            # User pressed q → ROI empty
            if roi == (0, 0, 0, 0):
                print("Returning to mode selection...")
                cv2.destroyWindow("Select Field")
                return

            x, y, w, h = roi
            cv2.destroyWindow("Select Field")

            x1, y1, x2, y2 = x, y, x + w, y + h
            print(f"Selected: {x1}, {y1} → {x2}, {y2}")

            name = input("Enter field name: ").strip()

            field = {
                "name": name,
                "type": field_type,
                "x1": int(x1),
                "y1": int(y1),
                "x2": int(x2),
                "y2": int(y2)
            }

            self.fields.append(field)
            self.draw_field(field, (0, 0, 255))  # red

    # ============================
    # CHECKBOX GROUP MODE
    # ============================
    def process_checkbox_area(self):
        print("\n=== CHECKBOX AREA MODE ===")
        print("Select PARENT checkbox area.")

        roi = cv2.selectROI("Select Parent Checkbox", self.display_img,
                            showCrosshair=True, fromCenter=False)
        cv2.destroyWindow("Select Parent Checkbox")

        x, y, w, h = roi
        if w == 0 or h == 0:
            print("Cancelled.")
            return

        x1, y1, x2, y2 = x, y, x + w, y + h
        pname = input("Parent checkbox group name: ").strip()

        parent = {
            "name": pname,
            "type": "checkbox_group",
            "x1": int(x1),
            "y1": int(y1),
            "x2": int(x2),
            "y2": int(y2),
            "children": []
        }

        self.draw_field(parent, (0, 0, 255))

        print("Now select CHILD checkboxes.")
        print("Press C in ROI window to finish child selection.")

        while True:
            roi = cv2.selectROI("Select Child Checkbox", self.display_img,
                                showCrosshair=True, fromCenter=False)

            if roi == (0, 0, 0, 0):
                cv2.destroyWindow("Select Child Checkbox")
                print("Finished child selection.")
                break

            x, y, w, h = roi
            cname = input("Child checkbox name: ").strip()

            child = {
                "name": cname,
                "type": "checkbox",
                "x1": int(x),
                "y1": int(y),
                "x2": int(x + w),
                "y2": int(y + h)
            }

            parent["children"].append(child)
            self.draw_field(child, (0, 255, 0))  # green

        self.fields.append(parent)

    # ============================
    # DRAW BOX + LABEL
    # ============================
    def draw_field(self, field, color):
        x1, y1, x2, y2 = field["x1"], field["y1"], field["x2"], field["y2"]
        name = field["name"]

        cv2.rectangle(self.display_img, (x1, y1), (x2, y2), color, 2)

        cv2.putText(
            self.display_img,
            name,
            (x1, max(15, y1 - 5)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            color,
            2
        )

        cv2.imshow("Template", self.display_img)
        cv2.waitKey(10)

    # ============================
    # SAVE JSON
    # ============================
    def save_json(self):
        out = os.path.splitext(self.template_path)[0] + ".json"
        with open(out, "w") as f:
            json.dump(self.fields, f, indent=4)
        print(f"Saved layout JSON → {out}")
