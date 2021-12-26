import json


def sanitize_value(value):
    try:
        int(value)
        return int(value)
    except ValueError:
        return value


class Settings:
    def __init__(self):
        file = open("settings.json", "r")
        self.property_groups = json.loads(file.read())
        file.close()
        file = open("options.json", "r")
        self.options = json.loads(file.read())
        file.close()

    def get_property(self, property_group, property_name):
        return self.property_groups[property_group][property_name]

    def set_property(self, property_group, property_name, value):
        sanitized = sanitize_value(value)
        self.property_groups[property_group][property_name] = sanitized
        file = open("settings.json", "w")
        json.dump(self.property_groups, file, sort_keys=True, indent=4)
        file.close()

    def get_all_settings(self):
        return json.dumps(self.property_groups, sort_keys=True, indent=4)

    def get_all_options(self):
        return json.dumps(self.options, sort_keys=True, indent=4)
