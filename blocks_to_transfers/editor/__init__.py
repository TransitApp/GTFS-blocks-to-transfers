import csv
import shutil
from pathlib import Path
from .types import Entity, ExportDict
from .schema import GTFS_SUBSET_SCHEMA


def load(gtfs_dir):
    gtfs_dir = Path(gtfs_dir)
    gtfs = Entity()
    for file_schema in GTFS_SUBSET_SCHEMA.values():
        print(f'Loading {file_schema.name}')
        filepath = gtfs_dir / file_schema.filename
        if not filepath.exists():
            if file_schema.required:
                raise ValueError(f'{file_schema.filename}: required file is missing')
            else:
                gtfs[file_schema.name] = ExportDict()
                gtfs[file_schema.name]._exportable_fields = list(file_schema.fields.items())
                continue

        with open(filepath, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f, skipinitialspace=True)
            header_row = next(reader, None)
            if not header_row:
                if file_schema.required:
                    raise ValueError(f'{file_schema.filename}: required file is empty')
                else:
                    continue

            entities = load_file(file_schema, header_row, reader)
            gtfs[file_schema.name] = sorted_entities(file_schema, entities)

    return gtfs


def load_file(file_schema, header_row, reader):
    # Set version used for membership checks, while list version determines order
    header_row_set = set(header_row)

    parse_schema = [(name, file_schema.fields.get(name)) for name in header_row]
    default_init_fields = [(name, field_schema) for name, field_schema  in file_schema.fields.items()
                           if name not in header_row_set]
    exportable_fields = header_row + default_init_fields

    entities = ExportDict()
    entities._exportable_fields = exportable_fields

    for lineno, row in enumerate(reader, 2):
        entity = Entity()

        for (name, field_schema), value in zip(parse_schema, row):
            if not field_schema:
                entity[name] = value
                continue

            if field_schema.required and value == '':
                raise ValueError(f'{file_schema.filename}:{lineno}: required field {name} is empty.')
            
            entity[name] = validate_with_context(file_schema, lineno, field_schema.validator, name, value)
            
        for name, field_schema in default_init_fields:
            if field_schema.required:
                raise ValueError(f'{file_schema.filename}:{lineno}: required field {name} not defined as column.')

            entity[name] = validate_with_context(file_schema, lineno, field_schema.validator, name, '')

        key = entity[file_schema.id]
        if file_schema.group_sort_key:
            entities.setdefault(key, []).append(entity)
        else:
            entities[key] = entity

    return entities


def validate_with_context(file_schema, lineno, validator, name, value):
    if not validator:
        return value
    
    try:
        return validator(value)
    except ValueError as e:
        raise ValueError(
            f'{file_schema.filename}:{lineno}: field {name} = {repr(value)} cannot be converted: {e.args[0]}')


def sorted_entities(file_schema, entities):
    if file_schema.group_sort_key:
        for group in entities.values():
            group.sort(key=lambda entity: entity[file_schema.group_sort_key])

    sorted_dict = ExportDict(sorted(entities.items(), key=lambda kv: kv[0]))
    sorted_dict._exportable_fields = entities._exportable_fields
    return sorted_dict


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

        with open(gtfs_out_dir / file_schema.filename, 'w', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(entities._exportable_fields)
            for entity in flat_entities:
                writer.writerow(serialize_field(entity[name]) for name in entities._exportable_fields)


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







