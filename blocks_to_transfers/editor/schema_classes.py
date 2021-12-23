from collections import namedtuple
Field = namedtuple('Field', ('type', 'required', 'default'))


class File:
    def __init__(self, id, name, filename=None, required=True, group_sort_key=None):
        # Primary key for this file, serves as the key of the generated dict
        self.id = id

        # Objects will appear under gtfs."name"
        self.name = name

        # Objects will be read from "filename".txt
        # If unset, the entity name shall be used instead
        self.filename = filename if filename else name + ".txt"

        # If this file is absent from the GTFS directory, should process abort?
        self.required = required

        # If set, multiple entities may share the same ID. The group sort key is used to provide
        # a deterministic order among entities with a common ID
        self.group_sort_key = group_sort_key

        # Will be set to point to the class defining this file
        self.class_def = None

    def get_fields(self):
        return {k: Field(type=v, required=k not in self.class_def.__dict__, default=self.class_def.__dict__.get(k))
                for k, v in self.class_def.__annotations__.items()}


class Schema:
    def __init__(self, *args):
        self.entities = {}
        for file in args:
            file.SCHEMA.class_def = file
            self.entities[file.SCHEMA.filename] = file.SCHEMA

    def keys(self):
        return self.entities.keys()

    def values(self):
        return self.entities.values()

    def __getitem__(self, item):
        return self.entities[item]