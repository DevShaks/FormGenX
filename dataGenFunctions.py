# ============================
# DATA GENERATION FUNCTIONS
# ============================
from datetime import datetime, timedelta
import random


class DataGenFunctions:
    def __init__(self, data_store=None):
        self.data_store = data_store

    def from_list(self, params):
        values = params.get("values", [])
        return random.choice(values) if values else ""

    def date(self, params):
        start_year = params.get("start_year", 1970)
        end_year = params.get("end_year", 2020)
        start = datetime(start_year, 1, 1)
        end = datetime(end_year, 12, 31)
        d = start + timedelta(days=random.randint(0, (end - start).days))
        return d.strftime("%d.%m.%Y")

    def checkbox_binary(self, params):
        p = params.get("true_prob", 0.5)
        return random.random() < p

    def checkbox_group_random(self, params):
        children = params.get("children", [])
        mode = params.get("mode", "single")
        missing_prob = params.get("missing_prob", 0.0)

        if not children:
            return []

        if random.random() < missing_prob:
            return []

        names = [c["name"] for c in children]

        if mode == "single":
            return [random.choice(names)]

        k = random.randint(1, len(names))
        return random.sample(names, k)

    # ============================
    # STAMP CONTENT GENERATORS
    # ============================
    def doctor_name(self, params):
        first_names = params.get("first_names", ["Anna", "Max", "Julia", "Leon", "Nina", "David"])
        last_names = params.get("last_names", ["Schmidt", "Mueller", "Weber", "Braun", "Fischer", "Klein"])
        return f"{random.choice(first_names)} {random.choice(last_names)}"

    def doctor_specialty(self, params):
        specialties = params.get(
            "specialties",
            [
                "Allgemeinmedizin",
                "Innere Medizin",
                "Orthopaedie",
                "Dermatologie",
                "Neurologie",
                "Kardiologie",
            ],
        )
        return random.choice(specialties)

    def doctor_bsnr(self, params):
        min_value = int(params.get("bsnr_min", 100000000))
        max_value = int(params.get("bsnr_max", 999999999))
        return str(random.randint(min_value, max_value))

    def doctor_lanr(self, params):
        min_value = int(params.get("lanr_min", 100000000))
        max_value = int(params.get("lanr_max", 999999999))
        return str(random.randint(min_value, max_value))

    def doctor_phone(self, params):
        area_codes = params.get("area_codes", ["030", "040", "0221", "089", "069", "0711"])
        area = random.choice(area_codes)
        body_a = random.randint(100, 999)
        body_b = random.randint(10000, 99999)
        return f"{area} {body_a}{body_b}"

    def handwritten_note(self, params):
        notes = params.get(
            "values",
            ["gez.", "i.A.", "ok", "dringend", "eilig", "heute", datetime.now().strftime("%d.%m.%y")],
        )
        return random.choice(notes)

    def doctor_stamp_lines(self, params):
        first_names = params.get("first_names", ["Anna", "Max", "Julia", "Leon", "Nina", "David"])
        last_names = params.get("last_names", ["Schmidt", "Mueller", "Weber", "Braun", "Fischer", "Klein"])
        specialties = params.get(
            "specialties",
            ["Allgemeinmedizin", "Innere Medizin", "Orthopaedie", "Dermatologie"],
        )
        cities = params.get("cities", ["Berlin", "Koeln", "Hamburg", "Muenchen", "Bonn"])
        streets = params.get("streets", ["Hauptstrasse", "Bahnhofstrasse", "Gartenweg", "Lindenweg"])

        first = random.choice(first_names)
        last = random.choice(last_names)
        doctor_title = random.choice(params.get("titles", ["Dr. med.", "Dr.", "PD Dr."]))
        specialty = random.choice(specialties)
        city = random.choice(cities)
        street = random.choice(streets)

        payload = {
            "full_name": f"{first} {last}",
            "doctor_name": f"{doctor_title} {first} {last}",
            "specialty": specialty,
            "city": city,
            "street": f"{street} {random.randint(1, 90)}",
            "postcode": str(random.randint(10000, 99999)),
            "phone": self.doctor_phone(params),
            "bsnr": self.doctor_bsnr(params),
            "lanr": self.doctor_lanr(params),
        }

        line_template = params.get(
            "line_template",
            [
                "{doctor_name}",
                "Facharzt fuer {specialty}",
                "{street}",
                "{postcode} {city}",
                "Tel.: {phone}",
                "BSNR: {bsnr}",
            ],
        )

        lines = []
        for idx, template in enumerate(line_template):
            try:
                txt = str(template).format(**payload)
            except (KeyError, ValueError):
                txt = str(template)
            if not txt:
                continue
            lines.append(
                {
                    "text": txt,
                    "section_id": f"line_{idx}",
                    "font_size": int(params.get("font_size", 28)),
                }
            )

        return {
            "preset": params.get("preset", "medical_with_black_signature"),
            "lines": lines,
            "fields": payload,
        }
