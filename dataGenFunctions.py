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