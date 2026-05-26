import datetime
import json
import os
import re
import secrets
import sqlite3
from copy import deepcopy

try:
    from db.schema import metadata as _SCHEMA_METADATA
except Exception:
    _SCHEMA_METADATA = None


_MODEL_REGISTRY = {}
FIELD_MAP = {}


def _to_snake(name):
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    s2 = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1)
    return s2.replace('__', '_').lower()


def _loads_json(value, default):
    if value is None:
        return deepcopy(default)
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return deepcopy(default)
        try:
            return json.loads(text)
        except Exception:
            return deepcopy(default)
    return deepcopy(default)


def _serialize_dynamic(value):
    if isinstance(value, Document):
        return str(value.id)
    if isinstance(value, EmbeddedDocument):
        return value.to_dict()
    if isinstance(value, datetime.datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [_serialize_dynamic(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _serialize_dynamic(v) for k, v in value.items()}
    return value


def _deserialize_dynamic(value):
    if isinstance(value, list):
        return [_deserialize_dynamic(v) for v in value]
    if isinstance(value, dict):
        return {k: _deserialize_dynamic(v) for k, v in value.items()}
    return value


class _MongoDict(dict):
    def to_dict(self):
        return dict(self)


class _SQLiteStore:
    def __init__(self):
        self.path = None
        self._collection_cache = {}
        self._schema_tables = {}
        self._schema_columns = {}

    def configure(self, path=None):
        if path and path.startswith('sqlite:///'):
            path = path.replace('sqlite:///', '', 1)
        if not path:
            path = os.getenv('SQLITE_PATH', 'app.db')
        self.path = os.path.abspath(path)
        folder = os.path.dirname(self.path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        self._load_schema()
        self._ensure_compat_schema()

    def _load_schema(self):
        self._schema_tables = {}
        self._schema_columns = {}
        if _SCHEMA_METADATA is None:
            return
        for table in _SCHEMA_METADATA.tables.values():
            self._schema_tables[table.name] = table
            self._schema_columns[table.name] = {column.name: column for column in table.columns}

    def _conn(self):
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys = ON')
        conn.execute('PRAGMA journal_mode = WAL')
        conn.execute('PRAGMA synchronous = NORMAL')
        conn.execute('PRAGMA temp_store = MEMORY')
        conn.execute('PRAGMA busy_timeout = 10000')
        return conn

    def _ensure_compat_schema(self):
        with self._conn() as conn:
            conn.execute(
                '''
                CREATE TABLE IF NOT EXISTS __document_blobs (
                    collection TEXT NOT NULL,
                    id TEXT NOT NULL,
                    data TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (collection, id)
                )
                '''
            )
            conn.execute(
                'CREATE INDEX IF NOT EXISTS idx_document_blobs_collection ON __document_blobs(collection)'
            )

    def _invalidate_collection_cache(self, collection):
        self._collection_cache.pop(collection, None)

    def _table_exists(self, collection):
        return collection in self._schema_tables

    def _field_map_for(self, collection):
        return FIELD_MAP.get(collection, {})

    def _field_for(self, collection, field_name):
        model_cls = _COLLECTION_MODEL_REGISTRY.get(collection)
        if not model_cls:
            return None
        return model_cls._fields.get(field_name)

    def _encode_field_value(self, field, value):
        value = field.to_storage(value)
        if value is None:
            return None
        if isinstance(field, DateTimeField):
            return value
        if isinstance(field, BooleanField):
            return 1 if bool(value) else 0
        if isinstance(field, IntField):
            return int(value)
        if isinstance(field, FloatField):
            return float(value)
        if isinstance(field, ReferenceField):
            return str(value)
        if isinstance(field, (DictField, ListField, EmbeddedDocumentField, EmbeddedDocumentListField)):
            return json.dumps(_serialize_dynamic(value), ensure_ascii=False)
        if isinstance(value, (dict, list)):
            return json.dumps(_serialize_dynamic(value), ensure_ascii=False)
        return value

    def _decode_field_value(self, field, value):
        if value is None:
            return field.get_default()
        if isinstance(field, BooleanField):
            return bool(value) if not isinstance(value, str) else value.lower() in ('1', 'true', 'yes')
        if isinstance(field, IntField):
            try:
                return int(value)
            except Exception:
                return field.get_default()
        if isinstance(field, FloatField):
            try:
                return float(value)
            except Exception:
                return field.get_default()
        if isinstance(field, DateTimeField):
            return field.from_storage(value)
        if isinstance(field, ReferenceField):
            return field.from_storage(value)
        if isinstance(field, (DictField, ListField, EmbeddedDocumentField, EmbeddedDocumentListField)):
            raw = _loads_json(value, {} if isinstance(field, DictField) else [])
            return field.from_storage(raw)
        return field.from_storage(value)

    def _fetch_blob_rows(self, collection):
        with self._conn() as conn:
            rows = conn.execute(
                'SELECT id, data FROM __document_blobs WHERE collection = ?',
                (collection,)
            ).fetchall()
        result = []
        for row in rows:
            payload = _loads_json(row['data'], {})
            if isinstance(payload, dict):
                result.append((row['id'], payload))
        return result

    def _fetch_legacy_rows(self, collection):
        with self._conn() as conn:
            try:
                rows = conn.execute(
                    'SELECT id, data FROM __documents WHERE collection = ?',
                    (collection,)
                ).fetchall()
            except sqlite3.OperationalError:
                return []
        result = []
        for row in rows:
            payload = _loads_json(row['data'], {})
            if isinstance(payload, dict):
                result.append((row['id'], payload))
        return result

    def _row_to_payload(self, collection, row):
        model_cls = _COLLECTION_MODEL_REGISTRY.get(collection)
        payload = {}
        field_map = self._field_map_for(collection)
        if model_cls is not None:
            for field_name, field in model_cls._fields.items():
                column_name = field_map.get(field_name)
                if column_name and column_name in row.keys():
                    payload[field_name] = self._decode_field_value(field, row[column_name])
                elif field_name in row.keys():
                    payload[field_name] = self._decode_field_value(field, row[field_name])
                elif field_name in payload:
                    continue
                else:
                    default = field.get_default()
                    if default is not None:
                        payload[field_name] = default

        for column_name in row.keys():
            if column_name == 'id':
                continue
            if model_cls and column_name in field_map.values():
                continue
            if column_name not in payload:
                payload[column_name] = _deserialize_dynamic(row[column_name])
        return payload

    def fetch_collection(self, collection):
        cached = self._collection_cache.get(collection)
        if cached is not None:
            return cached

        result = []
        seen = set()
        legacy_rows = self._fetch_legacy_rows(collection)
        if self._table_exists(collection):
            with self._conn() as conn:
                try:
                    rows = conn.execute(f'SELECT * FROM {collection}').fetchall()
                except sqlite3.OperationalError:
                    rows = []
            for row in rows:
                payload = self._row_to_payload(collection, row)
                result.append((row['id'], payload))
                seen.add(str(row['id']))

            for doc_id, extra in self._fetch_blob_rows(collection):
                if str(doc_id) in seen:
                    for idx, (existing_id, existing_payload) in enumerate(result):
                        if str(existing_id) == str(doc_id):
                            merged = dict(existing_payload)
                            merged.update(extra)
                            result[idx] = (existing_id, merged)
                            break
                else:
                    result.append((doc_id, extra))

            if legacy_rows:
                existing_ids = {str(doc_id) for doc_id, _ in result}
                for doc_id, legacy_payload in legacy_rows:
                    if str(doc_id) in existing_ids:
                        for idx, (existing_id, existing_payload) in enumerate(result):
                            if str(existing_id) == str(doc_id):
                                merged = dict(existing_payload)
                                for key, value in legacy_payload.items():
                                    merged.setdefault(key, value)
                                result[idx] = (existing_id, merged)
                                break
                    else:
                        result.append((doc_id, legacy_payload))
        else:
            blob_rows = self._fetch_blob_rows(collection)
            if blob_rows:
                result.extend(blob_rows)
            else:
                result.extend(legacy_rows)

        self._collection_cache[collection] = result
        return result

    def query_collection(self, collection, where_sql='', params=(), order_by_sql='', limit=None, offset=0):
        rows = self.fetch_collection(collection)
        return rows

    def count_collection(self, collection, where_sql='', params=()):
        return len(self.fetch_collection(collection))

    def upsert(self, collection, doc_id, payload, model_cls=None):
        model_cls = model_cls or _COLLECTION_MODEL_REGISTRY.get(collection)
        now = datetime.datetime.utcnow().isoformat()
        field_map = self._field_map_for(collection)
        table_columns = self._schema_columns.get(collection, {})
        extras = {}

        if self._table_exists(collection) and model_cls is not None:
            row = {'id': str(doc_id)}
            used_columns = {'id'}
            for field_name, field in model_cls._fields.items():
                value = payload.get(field_name, field.get_default())
                column_name = field_map.get(field_name)
                if column_name and column_name in table_columns:
                    row[column_name] = self._encode_field_value(field, value)
                    used_columns.add(column_name)
                else:
                    extras[field_name] = _serialize_dynamic(value)

            for key, value in payload.items():
                if key not in model_cls._fields:
                    extras[key] = _serialize_dynamic(value)

            for column_name, column in table_columns.items():
                if column_name in used_columns:
                    continue
                if column.default is not None and column_name not in row:
                    default = column.default.arg if callable(getattr(column.default, 'arg', None)) else getattr(column.default, 'arg', None)
                    if callable(default):
                        default = default()
                    row[column_name] = default

            cols = list(row.keys())
            placeholders = ', '.join('?' for _ in cols)
            update_cols = [name for name in cols if name != 'id']
            update_sql = ', '.join(f'{name}=excluded.{name}' for name in update_cols)

            with self._conn() as conn:
                conn.execute(
                    f"INSERT INTO {collection} ({', '.join(cols)}) VALUES ({placeholders}) ON CONFLICT(id) DO UPDATE SET {update_sql}",
                    [row[col] for col in cols],
                )
                if extras:
                    conn.execute(
                        '''
                        INSERT INTO __document_blobs(collection, id, data, updated_at)
                        VALUES(?, ?, ?, ?)
                        ON CONFLICT(collection, id)
                        DO UPDATE SET data=excluded.data, updated_at=excluded.updated_at
                        ''',
                        (collection, str(doc_id), json.dumps(extras, ensure_ascii=False), now),
                    )
                else:
                    conn.execute(
                        'DELETE FROM __document_blobs WHERE collection = ? AND id = ?',
                        (collection, str(doc_id)),
                    )
                conn.commit()
        else:
            combined = dict(payload)
            with self._conn() as conn:
                conn.execute(
                    '''
                    INSERT INTO __document_blobs(collection, id, data, updated_at)
                    VALUES(?, ?, ?, ?)
                    ON CONFLICT(collection, id)
                    DO UPDATE SET data=excluded.data, updated_at=excluded.updated_at
                    ''',
                    (collection, str(doc_id), json.dumps(_serialize_dynamic(combined), ensure_ascii=False), now),
                )
                conn.commit()

        self._invalidate_collection_cache(collection)

    def delete_ids(self, collection, doc_ids):
        if not doc_ids:
            return 0
        doc_ids = [str(doc_id) for doc_id in doc_ids]
        placeholders = ','.join('?' for _ in doc_ids)
        deleted = 0
        with self._conn() as conn:
            if self._table_exists(collection):
                cursor = conn.execute(
                    f'DELETE FROM {collection} WHERE id IN ({placeholders})',
                    doc_ids,
                )
                deleted = cursor.rowcount or 0
            try:
                conn.execute(
                    f'DELETE FROM __document_blobs WHERE collection = ? AND id IN ({placeholders})',
                    [collection, *doc_ids],
                )
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute(
                    f'DELETE FROM __documents WHERE collection = ? AND id IN ({placeholders})',
                    [collection, *doc_ids],
                )
            except sqlite3.OperationalError:
                pass
            conn.commit()
        self._invalidate_collection_cache(collection)
        return deleted


_store = _SQLiteStore()
_COLLECTION_MODEL_REGISTRY = {}


def connect(host=None, path=None, **kwargs):
    db_path = path or host or os.getenv('SQLITE_PATH', 'app.db')
    _store.configure(db_path)
    return db_path


class BaseField:
    def __init__(self, required=False, default=None, unique=False, choices=None, null=False):
        self.required = required
        self.default = default
        self.unique = unique
        self.choices = choices
        self.null = null
        self.name = None

    def __set_name__(self, owner, name):
        self.name = name

    def get_default(self):
        if callable(self.default):
            return self.default()
        if isinstance(self.default, (dict, list)):
            return deepcopy(self.default)
        return self.default

    def to_storage(self, value):
        return value

    def from_storage(self, value):
        return value

    def __get__(self, instance, owner):
        if instance is None:
            return self
        getter = getattr(instance, '_get_field_value', None)
        if getter:
            return getter(self.name)
        return instance._data.get(self.name)

    def __set__(self, instance, value):
        setter = getattr(instance, '_set_field_value', None)
        if setter:
            setter(self.name, value)
            return
        instance._data[self.name] = self.from_storage(self.to_storage(value))


class StringField(BaseField):
    pass


class BooleanField(BaseField):
    def from_storage(self, value):
        if value is None:
            return self.get_default()
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            return value.strip().lower() in ('1', 'true', 'yes', 'y', 'on')
        return bool(value)


class IntField(BaseField):
    def from_storage(self, value):
        if value is None or value == '':
            return self.get_default()
        try:
            return int(value)
        except Exception:
            return self.get_default()


class FloatField(BaseField):
    def from_storage(self, value):
        if value is None or value == '':
            return self.get_default()
        try:
            return float(value)
        except Exception:
            return self.get_default()


class DictField(BaseField):
    def to_storage(self, value):
        return value if isinstance(value, dict) else {}

    def from_storage(self, value):
        return _loads_json(value, {}) if not isinstance(value, dict) else value


class DynamicField(BaseField):
    pass


class DateTimeField(BaseField):
    def to_storage(self, value):
        if isinstance(value, datetime.datetime):
            return value.isoformat()
        return value

    def from_storage(self, value):
        if isinstance(value, datetime.datetime) or value is None:
            return value
        if isinstance(value, str):
            try:
                if value.endswith('Z'):
                    value = value[:-1] + '+00:00'
                return datetime.datetime.fromisoformat(value)
            except ValueError:
                return None
        return None


class ListField(BaseField):
    def __init__(self, field=None, **kwargs):
        super().__init__(**kwargs)
        self.field = field

    def to_storage(self, value):
        items = value if isinstance(value, list) else []
        if self.field:
            return [self.field.to_storage(v) for v in items]
        return items

    def from_storage(self, value):
        items = _loads_json(value, []) if not isinstance(value, list) else value
        if self.field:
            return [self.field.from_storage(v) for v in items]
        return items


class ReferenceField(BaseField):
    def __init__(self, document_type, **kwargs):
        super().__init__(**kwargs)
        self.document_type = document_type

    def _target_cls(self):
        if isinstance(self.document_type, str):
            return _MODEL_REGISTRY.get(self.document_type)
        return self.document_type

    def to_storage(self, value):
        if value is None:
            return None
        if hasattr(value, 'id'):
            return str(value.id)
        if isinstance(value, dict):
            if value.get('_id') is not None:
                return str(value.get('_id'))
            if value.get('id') is not None:
                return str(value.get('id'))
        return str(value)

    def from_storage(self, value):
        if value is None:
            return None
        return str(value)


class EmbeddedDocumentField(BaseField):
    def __init__(self, document_type, **kwargs):
        super().__init__(**kwargs)
        self.document_type = document_type

    def _build(self, value):
        if value is None:
            return None
        if isinstance(value, self.document_type):
            return value
        if isinstance(value, dict):
            return self.document_type(**value)
        if isinstance(value, str):
            loaded = _loads_json(value, {})
            if isinstance(loaded, dict):
                return self.document_type(**loaded)
        return None

    def to_storage(self, value):
        obj = self._build(value)
        return obj.to_dict() if obj else None

    def from_storage(self, value):
        return self._build(value)


class EmbeddedDocumentListField(ListField):
    def __init__(self, document_type, **kwargs):
        super().__init__(field=None, **kwargs)
        self.document_type = document_type

    def to_storage(self, value):
        items = value if isinstance(value, list) else []
        out = []
        for item in items:
            if isinstance(item, self.document_type):
                out.append(item.to_dict())
            elif isinstance(item, dict):
                out.append(self.document_type(**item).to_dict())
        return out

    def from_storage(self, value):
        items = _loads_json(value, []) if not isinstance(value, list) else value
        out = []
        for item in items:
            if isinstance(item, self.document_type):
                out.append(item)
            elif isinstance(item, dict):
                out.append(self.document_type(**item))
        return out


class DocumentMeta(type):
    def __new__(mcls, name, bases, attrs):
        fields = {}
        for base in bases:
            fields.update(getattr(base, '_fields', {}))
        for key, val in list(attrs.items()):
            if isinstance(val, BaseField):
                fields[key] = val
        cls = super().__new__(mcls, name, bases, attrs)
        cls._fields = fields

        meta = getattr(cls, 'meta', {}) or {}
        cls._meta = meta
        cls._collection = meta.get('collection') or f'{name.lower()}s'

        field_map = {}
        table = _SCHEMA_METADATA.tables.get(cls._collection) if _SCHEMA_METADATA and cls._collection in _SCHEMA_METADATA.tables else None
        columns = {column.name for column in table.columns} if table is not None else set()
        for field_name, field in fields.items():
            candidates = [field_name, _to_snake(field_name)]
            if isinstance(field, ReferenceField):
                snake = _to_snake(field_name)
                candidates.extend([f'{snake}_id', f'{field_name}_id'])
            for candidate in candidates:
                if candidate in columns:
                    field_map[field_name] = candidate
                    break
        cls._field_map = field_map
        FIELD_MAP[cls._collection] = dict(field_map)

        if 'QuerySetDescriptor' in globals():
            cls.objects = QuerySetDescriptor(cls)

        _MODEL_REGISTRY[name] = cls
        _COLLECTION_MODEL_REGISTRY[cls._collection] = cls
        return cls


class EmbeddedDocument(metaclass=DocumentMeta):
    meta = {}

    def __init__(self, **kwargs):
        object.__setattr__(self, '_data', {})
        for name, field in self._fields.items():
            self._data[name] = field.get_default()
        for key, value in kwargs.items():
            setattr(self, key, value)

    def _get_field_value(self, name):
        return self._data.get(name)

    def _set_field_value(self, name, value):
        field = self._fields.get(name)
        if field:
            self._data[name] = field.from_storage(field.to_storage(value))
        else:
            self._data[name] = value

    def __getattr__(self, item):
        if item in self._fields or item in self._data:
            return self._data.get(item)
        raise AttributeError(item)

    def __setattr__(self, key, value):
        if key.startswith('_'):
            object.__setattr__(self, key, value)
            return
        self._set_field_value(key, value)

    def to_dict(self):
        out = {}
        for key, value in self._data.items():
            field = self._fields.get(key)
            if field:
                out[key] = field.to_storage(value)
            else:
                out[key] = _serialize_dynamic(value)
        return out

    def to_mongo(self):
        return _MongoDict(self.to_dict())


class Document(EmbeddedDocument, metaclass=DocumentMeta):
    meta = {}

    def __init__(self, **kwargs):
        object.__setattr__(self, '_ref_cache', {})
        super().__init__(**kwargs)
        if 'id' in kwargs and kwargs['id'] is not None:
            object.__setattr__(self, 'id', str(kwargs['id']))
        elif getattr(self, 'id', None) is None:
            object.__setattr__(self, 'id', _new_id())

    def __getattr__(self, item):
        if item in self._fields:
            field = self._fields[item]
            if isinstance(field, ReferenceField):
                raw = self._data.get(item)
                if raw is None:
                    return None
                if item in self._ref_cache:
                    return self._ref_cache[item]
                target = field._target_cls()
                if not target:
                    return None
                doc = target.objects(id=raw).first()
                self._ref_cache[item] = doc
                return doc
            return self._data.get(item)
        if item in self._data:
            return self._data[item]
        raise AttributeError(item)

    def _get_field_value(self, name):
        field = self._fields.get(name)
        if isinstance(field, ReferenceField):
            raw = self._data.get(name)
            if raw is None:
                return None
            if name in self._ref_cache:
                return self._ref_cache[name]
            target = field._target_cls()
            if not target:
                return None
            doc = target.objects(id=raw).first()
            self._ref_cache[name] = doc
            return doc
        return self._data.get(name)

    def _set_field_value(self, name, value):
        field = self._fields.get(name)
        if field:
            if isinstance(field, ReferenceField):
                self._ref_cache.pop(name, None)
                if value is not None and hasattr(value, 'id'):
                    self._ref_cache[name] = value
            self._data[name] = field.from_storage(field.to_storage(value))
        else:
            self._data[name] = value

    def __setattr__(self, key, value):
        if key in ('id',):
            object.__setattr__(self, key, str(value) if value is not None else None)
            return
        if key.startswith('_'):
            object.__setattr__(self, key, value)
            return
        self._set_field_value(key, value)

    @classmethod
    def _from_store(cls, doc_id, payload):
        obj = cls(id=doc_id)
        object.__setattr__(obj, '_data', {})
        for name, field in cls._fields.items():
            if name in payload:
                obj._data[name] = field.from_storage(payload.get(name))
            else:
                obj._data[name] = field.get_default()
        for key, value in payload.items():
            if key not in cls._fields:
                obj._data[key] = _deserialize_dynamic(value)
        return obj

    def _to_store_payload(self):
        return dict(self._data)

    @classmethod
    def _all_docs(cls):
        rows = _store.fetch_collection(cls._collection)
        return [cls._from_store(doc_id, payload) for doc_id, payload in rows]

    def save(self, *args, **kwargs):
        now = datetime.datetime.utcnow()
        if 'createdAt' in self._fields and not self._data.get('createdAt'):
            self._data['createdAt'] = now
        if 'updatedAt' in self._fields:
            self._data['updatedAt'] = now

        self._validate_uniques()
        _store.upsert(self._collection, self.id, self._to_store_payload(), model_cls=self.__class__)
        return self

    def delete(self):
        return _store.delete_ids(self._collection, [self.id])

    def to_mongo(self):
        payload = self.to_dict()
        payload['_id'] = self.id
        return _MongoDict(payload)

    def _validate_uniques(self):
        unique_fields = [name for name, field in self._fields.items() if getattr(field, 'unique', False)]
        for field_name in unique_fields:
            value = self._data.get(field_name)
            if value in (None, ''):
                continue
            existing = self.__class__.objects(**{field_name: value}).first()
            if existing and str(existing.id) != str(self.id):
                raise ValueError(f'Duplicate value for unique field: {field_name}')

        for idx in self._meta.get('indexes', []) or []:
            if not idx.get('unique'):
                continue
            keys = idx.get('fields', [])
            if not keys:
                continue
            filters = {key: self._data.get(key) for key in keys}
            existing = self.__class__.objects(**filters).first()
            if existing and str(existing.id) != str(self.id):
                joined = ', '.join(keys)
                raise ValueError(f'Duplicate value for unique index: {joined}')


class QuerySetDescriptor:
    def __init__(self, model_cls):
        self.model_cls = model_cls

    def __get__(self, instance, owner):
        return QuerySet(self.model_cls)


class QuerySet:
    def __init__(self, model_cls, filters=None, order_spec=None):
        self.model_cls = model_cls
        self._filters = filters[:] if filters else []
        self._order_spec = order_spec[:] if order_spec else []
        self._evaluated = None

    def __call__(self, **kwargs):
        return self.filter(**kwargs)

    def _clone(self):
        return QuerySet(self.model_cls, self._filters, self._order_spec)

    def filter(self, **kwargs):
        clone = self._clone()
        clone._filters.append(kwargs)
        return clone

    def order_by(self, *fields):
        clone = self._clone()
        clone._order_spec = list(fields)
        return clone

    def first(self):
        items = self._evaluate(limit=1)
        return items[0] if items else None

    def count(self):
        return len(self._evaluate())

    def delete(self):
        docs = self._evaluate()
        return _store.delete_ids(self.model_cls._collection, [d.id for d in docs])

    def update(self, **updates):
        set_updates = {}
        for key, value in updates.items():
            if key.startswith('set__'):
                set_updates[key.split('set__', 1)[1]] = value

        changed = 0
        for doc in self._evaluate():
            for field, value in set_updates.items():
                setattr(doc, field, value)
            doc.save()
            changed += 1
        return changed

    def __iter__(self):
        return iter(self._evaluate())

    def __len__(self):
        return len(self._evaluate())

    def __getitem__(self, key):
        if isinstance(key, slice):
            data = self._evaluate()
            return data[key]
        if isinstance(key, int):
            data = self._evaluate()
            return data[key]
        data = self._evaluate()
        return data[key]

    def _evaluate(self, limit=None, offset=0):
        offset = max(0, int(offset or 0))
        if self._evaluated is None:
            docs = self.model_cls._all_docs()
            for f in self._filters:
                docs = [doc for doc in docs if _doc_matches(doc, f)]
            for field in reversed(self._order_spec):
                reverse = field.startswith('-')
                name = field[1:] if reverse else field
                docs.sort(key=lambda d: _sort_key(_resolve_value(d, name)), reverse=reverse)
            self._evaluated = docs

        if limit is not None:
            return self._evaluated[offset:offset + limit]
        if offset:
            return self._evaluated[offset:]
        return self._evaluated


def _resolve_value(doc, name):
    if name == 'id':
        return str(doc.id)
    if name in doc._fields:
        field = doc._fields[name]
        if isinstance(field, ReferenceField):
            return doc._data.get(name)
    return getattr(doc, name, None)


def _to_dt(value):
    if isinstance(value, datetime.datetime):
        return value
    if isinstance(value, str):
        try:
            if value.endswith('Z'):
                value = value[:-1] + '+00:00'
            return datetime.datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _normalize_filter_expected(value):
    if hasattr(value, 'id'):
        return str(value.id)
    if isinstance(value, datetime.datetime):
        return value.isoformat()
    if value is None:
        return None
    return str(value)


def _sort_key(value):
    if value is None:
        return (0, '')
    if isinstance(value, datetime.datetime):
        return (1, value.timestamp())
    return (1, str(value).lower())


def _eq_value(actual, expected):
    if hasattr(expected, 'id'):
        expected = expected.id
    if hasattr(actual, 'id'):
        actual = actual.id
    if isinstance(actual, datetime.datetime) and isinstance(expected, datetime.datetime):
        return actual == expected
    return str(actual) == str(expected)


def _match_raw(doc, raw_clause):
    if not isinstance(raw_clause, dict):
        return True

    if '$or' in raw_clause:
        rules = raw_clause.get('$or', [])
        for rule in rules:
            if _match_raw(doc, rule):
                return True
        return False

    for field, condition in raw_clause.items():
        actual = _resolve_value(doc, field)
        if isinstance(condition, dict):
            if '$regex' in condition:
                regex = str(condition.get('$regex', ''))
                flags = re.IGNORECASE if 'i' in str(condition.get('$options', '')) else 0
                if not re.search(regex, str(actual or ''), flags=flags):
                    return False
            else:
                if '$gte' in condition and not _gte(actual, condition.get('$gte')):
                    return False
                if '$lte' in condition and not _lte(actual, condition.get('$lte')):
                    return False
        else:
            if not _eq_value(actual, condition):
                return False

    return True


def _gte(actual, expected):
    a = _to_dt(actual)
    e = _to_dt(expected)
    if a and e:
        return a >= e
    try:
        return actual >= expected
    except Exception:
        return False


def _lte(actual, expected):
    a = _to_dt(actual)
    e = _to_dt(expected)
    if a and e:
        return a <= e
    try:
        return actual <= expected
    except Exception:
        return False


def _doc_matches(doc, filter_dict):
    if not filter_dict:
        return True

    raw_clause = filter_dict.get('__raw__')
    if raw_clause is not None and not _match_raw(doc, raw_clause):
        return False

    for key, expected in filter_dict.items():
        if key == '__raw__':
            continue

        parts = key.split('__')
        field_name = parts[0]
        op = parts[1] if len(parts) > 1 else 'eq'
        actual = _resolve_value(doc, field_name)

        if op == 'eq':
            if not _eq_value(actual, expected):
                return False
        elif op == 'in':
            expected_list = list(expected or [])
            if not any(_eq_value(actual, item) for item in expected_list):
                return False
        elif op == 'icontains':
            if str(expected).lower() not in str(actual or '').lower():
                return False
        elif op == 'iexact':
            if str(actual or '').lower() != str(expected or '').lower():
                return False
        else:
            return False

    return True


def _new_id():
    return secrets.token_hex(12)
