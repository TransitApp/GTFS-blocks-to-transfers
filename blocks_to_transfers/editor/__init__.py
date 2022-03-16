import csv
import enum
import shutil
from pathlib import Path
from . import schema_classes, types, schema


def load(gtfs_dir):
    gtfs_dir = Path(gtfs_dir)
    gtfs = types.Entity()
    for file_schema in schema.GTFS_SUBSET_SCHEMA.values():
        print(f'Loading {file_schema.name}')
        filepath = gtfs_dir / file_schema.filename
        gtfs[file_schema.name] = types.EntityDict(
            file_schema.get_declared_fields())

        if not filepath.exists():
            if file_schema.required:
                raise ValueError(
                    f'{file_schema.filename}: required file is missing')
            else:
                continue

        with open(filepath, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f, skipinitialspace=True)
            header_row = next(reader, None)
            if not header_row:
                if file_schema.required:
                    raise ValueError(
                        f'{file_schema.filename}: required file is empty')
                else:
                    continue

            resolved_fields = merge_header_and_declared_fields(
                file_schema, header_row)
            entities = {}
            for entity in parse_rows(gtfs, file_schema, resolved_fields,
                                     header_row, reader):
                index_entity(file_schema, entities, entity)

            gtfs[file_schema.name] = types.EntityDict(fields=resolved_fields,
                                                      values=sorted_entities(
                                                          file_schema,
                                                          entities))

    return gtfs


def merge_header_and_declared_fields(file_schema, header_row):
    declared_fields = file_schema.get_declared_fields()
    fields = {}

    for name in header_row:
        fields[name] = declared_fields.get(name) or schema_classes.Field(
            str, False, '')

    for name, config in declared_fields.items():
        if config.required and name not in fields:
            raise ValueError(
                f'{file_schema.filename}:1: missing required field {name}')

    return fields


def parse_rows(gtfs, file_schema, fields, header_row, reader):
    for lineno, row in enumerate(reader, 2):
        entity = file_schema.class_def()
        entity._gtfs = gtfs

        for name, value in zip(header_row, row):
            config = fields[name]
            if config.required and not value:
                raise ValueError(
                    f'{file_schema.filename}:{lineno}: required field {name} is empty'
                )

            entity[name] = validate(
                config,
                value,
                context_fn=lambda:
                f'{file_schema}:{lineno} field {name} = {repr(value)}')

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


def index_entity(file_schema, entities, entity):
    key = entity[file_schema.id]
    if not file_schema.group_id:
        entities[key] = entity
        return

    group_key = entity[file_schema.group_id]
    if file_schema.inner_dict:
        entities.setdefault(key, {})[group_key] = entity
    else:
        entities.setdefault(key, []).append(entity)


def sorted_entities(file_schema, entities):
    if file_schema.group_id:
        if file_schema.inner_dict:
            for group_key, group in entities.items():
                entities[group_key] = dict(
                    sorted(group.items(), key=lambda kv: kv[0]))
        else:
            for group in entities.values():
                group.sort(key=lambda entity: entity[file_schema.group_id])

    return sorted(entities.items(), key=lambda kv: kv[0])


def patch(gtfs, gtfs_in_dir, gtfs_out_dir):
    gtfs_in_dir = Path(gtfs_in_dir)
    gtfs_out_dir = Path(gtfs_out_dir)
    gtfs_out_dir.mkdir(parents=True, exist_ok=True)

    for original_filename in gtfs_in_dir.iterdir():
        try:
            shutil.copy2(original_filename,
                         gtfs_out_dir / original_filename.name)
        except shutil.SameFileError:
            pass  # No need to copy if we're working in-place

    for file_schema in schema.GTFS_SUBSET_SCHEMA.values():
        print(f'Writing {file_schema.name}')
        entities = gtfs.get(file_schema.name)
        if not entities:
            continue

        entities_sorted = dict(sorted_entities(file_schema, entities))
        flat_entities = flatten_entities(file_schema, entities_sorted)
        fields = entities._resolved_fields

        with open(gtfs_out_dir / file_schema.filename, 'w',
                  encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(fields.keys())
            for entity in flat_entities:
                writer.writerow(
                    serialize_field(entity.get(name, '')) for name in fields)


def flatten_entities(file_schema, entities):
    if file_schema.group_id:
        flat_entities = []
        for entity_list in entities.values():
            flat_entities.extend(
                entity_list.values() if file_schema.inner_dict else entity_list)
        return flat_entities
    else:
        return entities.values()


def serialize_field(value):
    if isinstance(value, (bool, enum.IntEnum)):
        return str(
            int(value)
        )  # Use the numerical representation of this type in final output

    return str(value)  # Direct conversion to string


def clone(entities, key, new_key):
    if key not in entities:
        return

    entries = entities[key]
    if isinstance(entries, list):
        entities[new_key] = [
            clone_and_index(entity, new_key) for entity in entries
        ]
    else:
        entities[new_key] = clone_and_index(entries, new_key)

    return entities[new_key]


def clone_and_index(entity, new_key):
    field_schema = entity.__class__._schema
    new_entity = entity.clone()
    new_entity[field_schema.id] = new_key
    return new_entity
