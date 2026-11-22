import json

from django.conf import settings
from django.db import models


class EmbeddingField(models.Field):
    """pgvector `vector(N)` on PostgreSQL; plain text elsewhere (SQLite is for tests only)."""

    def __init__(self, *args, dimensions=None, **kwargs):
        self.dimensions = dimensions or 1536
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        kwargs["dimensions"] = self.dimensions
        return name, path, args, kwargs

    def db_type(self, connection):
        return f"vector({self.dimensions})" if connection.vendor == "postgresql" else "text"

    def get_prep_value(self, value):
        if value is None:
            return None
        if isinstance(value, str):
            return value
        return "[" + ",".join(repr(float(x)) for x in value) + "]"

    def from_db_value(self, value, expression, connection):
        if value is None:
            return None
        if isinstance(value, str):
            return json.loads(value)
        return [float(x) for x in value]

    def to_python(self, value):
        if isinstance(value, str):
            return json.loads(value)
        return value


def vector_literal(vec):
    return "[" + ",".join(repr(float(x)) for x in vec) + "]"
