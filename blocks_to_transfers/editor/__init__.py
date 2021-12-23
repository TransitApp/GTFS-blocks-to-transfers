import csv
import enum
import shutil
from pathlib import Path
from .types import Entity
from .schema import GTFS_SUBSET_SCHEMA


def load(gtfs_dir):
    gtfs_dir = Path(gtfs_dir)
    gtfs = Entity()
    for file_schema in GTFS_SUBSET_SCHEMA.values():
        print(f'Loading {file_schema.name}')
        filepath = gtfs_dir / file_schema.filename
        gtfs[file_schema.name] = {}

        if not filepath.exists():
            if file_schema.required:
                raise ValueError(f'{file_schema.filename}: required file is missing')
            else:
                continue

        with open(filepath, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f, skipinitialspace=True)
            header_row = next(reader, None)
            if not header_row:
                if file_schema.required:
                    raise ValueError(f'{file_schema.filename}: required file is empty')
                else:
                    continue

            merge_with_defined_fields(file_schema, header_row)
            entities = {}
            for entity in parse_rows(file_schema, header_row, reader):
                key = entity[file_schema.id]
                if file_schema.group_sort_key:
                    entities.setdefault(key, []).append(entity)
                else:
                    entities[key] = entity

            gtfs[file_schema.name] = sorted_entities(file_schema, entities)

    return gtfs


def merge_with_defined_fields(file_schema, header_row):
    fields = file_schema.get_fields()
    for name, config in fields.items():
        if config.required and name not in header_row:
            raise ValueError(f'{file_schema.filename}:1: missing required field {name}')

    for name in header_row:
        if name not in fields:
            # Create a string attribute to hold the field we discovered in the CSV file
            setattr(file_schema.class_def, name, '')
            file_schema.class_def.__annotations__[name] = str


def parse_rows(file_schema, header_row, reader):
    fields = file_schema.get_fields()
    for lineno, row in enumerate(reader, 2):
        entity = file_schema.class_def()

        for name, value in zip(header_row, row):
            config = fields[name]
            if config.required and not value:
                raise ValueError(f'{file_schema.filename}:{lineno}: required field {name} is empty')

            entity[name] = validate(config, value,
                context_fn=lambda: f'{file_schema}:{lineno} field {name} = {repr(value)}')

        yield entity


def validate(config, value, context_fn):
    try:
        return convert(config, value)
    except Exception as exc:

        raise ValueError(f'{context_fn()}: {exc.args[0]}')

def convert(config, value):
    if issubclass(config.type, enum.IntEnum):
        if not config.required and not value:
            return config.default
        else:
            return config.type(int(value))

    if config.type is bool:
        return bool(int(value))

    return config.type(value)


def sorted_entities(file_schema, entities):
    if file_schema.group_sort_key:
        for group in entities.values():
            group.sort(key=lambda entity: entity[file_schema.group_sort_key])

    return dict(sorted(entities.items(), key=lambda kv: kv[0]))


def patch(gtfs, gtfs_in_dir, gtfs_out_dir):
    gtfs_in_dir = Path(gtfs_in_dir)
    gtfs_out_dir = Path(gtfs_out_dir)
    gtfs_out_dir.mkdir(parents=True, exist_ok=True)

    for original_filename in gtfs_in_dir.iterdir():
        shutil.copy2(original_filename, gtfs_out_dir / original_filename.name)

    for file_schema in GTFS_SUBSET_SCHEMA.values():
        entities = gtfs.get(file_schema.name)
        if not entities:
            continue

        flat_entities = flatten_entities(file_schema, entities)
        fields = file_schema.get_fields()

        with open(gtfs_out_dir / file_schema.filename, 'w', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(fields.keys())
            for entity in flat_entities:
                writer.writerow(serialize_field(entity[name]) for name in fields)



def flatten_entities(file_schema, entities):
    if file_schema.group_sort_key:
        return sum(entities.values(), [])
    else:
        return entities.values()


def serialize_field(value):
    try:
        # bools and enums have both a string-like representation and an integer-like one. GTFS always uses the latter.
        return str(int(value))
    except (TypeError, ValueError):
        return str(value)


def duplicate(entities, key, new_key):
    entries = entities[key]
    if isinstance(entries, list):
        entities[new_key] = [duplicate_1(entity, new_key) for entity in entries]
    else:
        entities[new_key] = duplicate_1(entries, new_key)

    return entities[new_key]


def duplicate_1(entity, new_key):
    field_schema = entity.__class__.SCHEMA
    new_entity = entity.duplicate()
    new_entity[field_schema.id] = new_key
    return new_entity


