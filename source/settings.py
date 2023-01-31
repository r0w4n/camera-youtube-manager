import json
import os.path


def get_settings():
    with open(
        os.path.dirname(os.path.abspath(__file__)) + "/../settings.json", "r"
    ) as f:
        return json.load(f)
