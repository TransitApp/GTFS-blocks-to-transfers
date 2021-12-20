class Field:
    def __init__(self, required=False, validator=None):
        # True if this field must be present in the CSV and cannot be blank. Note that fallbacks can be set for required
        # fields.
        self.required = required

        # Each validator may:
        #   - Raise an exception on malformed input, terminating the process
        #   - Convert from string to the appropriate data type
        #   - Return a default or fallback value specific to this field
        self.validator = validator if validator else None


class File:
    def __init__(self, id, name, filename=None, required=True, fields=None, group_sort_key=None):
        # Primary key for this file, serves as the key of the generated dict
        self.id = id

        # Objects will appear under gtfs."name"
        self.name = name

        # Objects will be read from "filename".txt
        # If unset, the entity name shall be used instead
        self.filename = filename if filename else name + ".txt"

        # If this file is absent from the GTFS directory, should process abort?
        self.required = required

        # Field definitions. These represent columns in the CSV
        self.fields = fields if fields else []

        # If set, multiple entities may share the same ID. The group sort key is used to provide
        # a deterministic order among entities with a common ID
        self.group_sort_key = group_sort_key


class Schema:
    def __init__(self, *args):
        self.entities = {file.filename: file for file in args}

    def keys(self):
        return self.entities.keys()

    def values(self):
        return self.entities.values()

    def __getitem__(self, item):
        return self.entities[item]