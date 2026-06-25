import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union


class FieldType(Enum):
    """Column data types.

    Values are converted and validated on every write and coerced back on read:
    ``INTEGER`` -> int, ``FLOAT`` -> float, ``BOOLEAN`` -> bool, ``DATE`` /
    ``DATETIME`` -> date/datetime, ``JSON`` -> parsed object, ``STRING`` -> str.
    A field with ``encrypted=True`` is sealed (Fernet) before it reaches the sheet.
    """

    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    JSON = "json"
    ENCRYPTED = "encrypted"


@dataclass
class ValidationRule:
    """Defines a validation rule for a field."""

    condition: Callable[[Any], bool]
    error_message: str


@dataclass
class Field:
    """One column in a `Schema`.

    Args:
        name: the column header.
        field_type: a `FieldType`.
        required: reject writes that omit this field. Defaults to True, but a field
            with a `default` is treated as optional (the default fills it in).
        unique: enforce that values stay unique. Checked on `insert`/`upsert` with a
            read-check-write (Sheets has no DB-level constraint), so a duplicate raises
            `DuplicateKeyError`; concurrent writes of the same new value can still race.
        primary_key: mark this field as the table's key. Implies `required` and `unique`,
            and is the default key `upsert()` matches on. At most one per schema.
        default: value used when the field is omitted on insert; setting it also makes
            the field optional.
        min_length / max_length: string-length bounds.
        pattern: a regex the value must fully satisfy.
        min_value / max_value: numeric bounds.
        validation_rules: extra `ValidationRule` checks.
        encrypted: seal the value with Fernet before writing; requires an
            `encryption_key` on the `SheetManager`.
    """

    name: str
    field_type: FieldType
    required: bool = True
    unique: bool = False
    primary_key: bool = False
    default: Any = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    pattern: Optional[str] = None
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    validation_rules: List[ValidationRule] = None
    encrypted: bool = False

    def __post_init__(self):
        if self.primary_key:
            # A primary key is required and unique by definition.
            self.required = True
            self.unique = True
        self.validation_rules = self.validation_rules or []
        self._add_default_validations()

    def _add_default_validations(self):
        """Add default validation rules based on field type and constraints."""
        if self.min_length is not None:
            self.validation_rules.append(
                ValidationRule(
                    lambda x: len(str(x)) >= self.min_length,
                    f"Value must be at least {self.min_length} characters long",
                )
            )

        if self.max_length is not None:
            self.validation_rules.append(
                ValidationRule(
                    lambda x: len(str(x)) <= self.max_length,
                    f"Value must be at most {self.max_length} characters long",
                )
            )

        if self.pattern is not None:
            self.validation_rules.append(
                ValidationRule(
                    lambda x: bool(re.match(self.pattern, str(x))),
                    f"Value must match pattern: {self.pattern}",
                )
            )

        if self.min_value is not None:
            self.validation_rules.append(
                ValidationRule(
                    lambda x: x >= self.min_value,
                    f"Value must be greater than or equal to {self.min_value}",
                )
            )

        if self.max_value is not None:
            self.validation_rules.append(
                ValidationRule(
                    lambda x: x <= self.max_value,
                    f"Value must be less than or equal to {self.max_value}",
                )
            )


class Schema:
    """Defines the structure of a sheet."""

    def __init__(self, name: str, fields: List[Field]):
        self.name = name
        self.fields = fields
        self._validate_schema()
        self._field_map = {field.name: field for field in fields}
        # The primary-key field name (or None), and every uniqueness-enforced field.
        pks = [field.name for field in fields if field.primary_key]
        self.primary_key: Optional[str] = pks[0] if pks else None
        self.unique_fields: List[Field] = [field for field in fields if field.unique]

    def _validate_schema(self) -> None:
        """Validate schema definition."""
        field_names = set()
        pks = []
        for field in self.fields:
            if field.name in field_names:
                raise ValueError(f"Duplicate field name: {field.name}")
            field_names.add(field.name)
            if field.primary_key:
                pks.append(field.name)
        if len(pks) > 1:
            raise ValueError(
                f"A schema can have at most one primary_key (got {pks}). "
                "Composite keys aren't supported — use a single key column."
            )

    def validate_value(self, field_name: str, value: Any) -> List[str]:
        """Validate one value against its field's type and constraints.

        Checks the type, then every constraint on the field — ``min_value`` /
        ``max_value``, ``min_length`` / ``max_length``, ``pattern`` and any custom
        ``validation_rules`` (all carried as the field's ``validation_rules``).

        Args:
            field_name: Name of the field.
            value: Value to validate.

        Returns:
            List of validation error messages (empty if valid).
        """
        field = self._field_map.get(field_name)
        if not field:
            raise ValueError(f"Unknown field: {field_name}")

        # Missing / explicit None — required unless a default fills it on write.
        if value is None:
            if field.required and field.default is None:
                return [f"Field {field_name} is required"]
            return []

        ft = field.field_type
        # Type checks: a bool is not a number, a number is not a bool, etc.
        if ft in (FieldType.INTEGER, FieldType.FLOAT):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return [f"Invalid value for type {ft}: {value}"]
        elif ft == FieldType.BOOLEAN:
            if not isinstance(value, bool):
                return [f"Invalid value for type {ft}: {value}"]
        elif ft == FieldType.STRING:
            if not isinstance(value, str):
                return [f"Invalid value for type {ft}: {value}"]
        else:
            # DATE / DATETIME / JSON / ENCRYPTED — validate by coercion.
            try:
                self._convert_value(value, ft)
            except ValueError as e:
                return [str(e)]

        # Constraint + custom rules (min/max, lengths, pattern, validation_rules).
        errors = []
        for rule in field.validation_rules:
            try:
                if not rule.condition(value):
                    errors.append(rule.error_message)
            except Exception as e:
                errors.append(f"Validation error: {str(e)}")
        return errors

    def _convert_value(self, value: Any, field_type: FieldType) -> Any:
        """Convert and validate value type."""
        try:
            if field_type == FieldType.INTEGER:
                return int(value)
            elif field_type == FieldType.FLOAT:
                return float(value)
            elif field_type == FieldType.BOOLEAN:
                return bool(value)
            elif field_type == FieldType.DATE:
                if isinstance(value, str):
                    return datetime.strptime(value, "%Y-%m-%d").date()
                elif isinstance(value, date):
                    return value
                raise ValueError("Invalid date format")
            elif field_type == FieldType.DATETIME:
                if isinstance(value, str):
                    return datetime.fromisoformat(value)
                elif isinstance(value, datetime):
                    return value
                raise ValueError("Invalid datetime format")
            elif field_type == FieldType.JSON:
                # Decode a stored JSON string back to an object; pass objects through.
                return json.loads(value) if isinstance(value, str) else value
            else:
                return str(value)
        except Exception as e:
            raise ValueError(f"Invalid value for type {field_type}: {value}") from e

    def validate(self, data: Dict[str, Any]) -> List[str]:
        """Validate a record against the schema (types + every field constraint).

        A field with a `default` is optional — the default fills it on write, so
        its absence is never an error.

        Args:
            data: Dictionary of field values to validate.

        Returns:
            List of validation error messages (empty if valid).
        """
        errors = []
        for field in self.fields:
            errors.extend(self.validate_value(field.name, data.get(field.name)))
        return errors

    def get_field(self, field_name: str) -> Optional[Field]:
        """
        Get field by name.

        Args:
            field_name: Name of the field to retrieve

        Returns:
            Field object if found, None otherwise
        """
        return self._field_map.get(field_name)
