from typing import Dict, Any, List, Union, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import re
from datetime import datetime, date

class FieldType(Enum):
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
    name: str
    field_type: FieldType
    required: bool = True
    unique: bool = False
    default: Any = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    pattern: Optional[str] = None
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    validation_rules: List[ValidationRule] = None
    encrypted: bool = False

    def __post_init__(self):
        self.validation_rules = self.validation_rules or []
        self._add_default_validations()

    def _add_default_validations(self):
        """Add default validation rules based on field type and constraints."""
        if self.min_length is not None:
            self.validation_rules.append(
                ValidationRule(
                    lambda x: len(str(x)) >= self.min_length,
                    f"Value must be at least {self.min_length} characters long"
                )
            )

        if self.max_length is not None:
            self.validation_rules.append(
                ValidationRule(
                    lambda x: len(str(x)) <= self.max_length,
                    f"Value must be at most {self.max_length} characters long"
                )
            )

        if self.pattern is not None:
            self.validation_rules.append(
                ValidationRule(
                    lambda x: bool(re.match(self.pattern, str(x))),
                    f"Value must match pattern: {self.pattern}"
                )
            )

        if self.min_value is not None:
            self.validation_rules.append(
                ValidationRule(
                    lambda x: x >= self.min_value,
                    f"Value must be greater than or equal to {self.min_value}"
                )
            )

        if self.max_value is not None:
            self.validation_rules.append(
                ValidationRule(
                    lambda x: x <= self.max_value,
                    f"Value must be less than or equal to {self.max_value}"
                )
            )

class Schema:
    """Defines the structure of a sheet."""
    
    def __init__(self, name: str, fields: List[Field]):
        self.name = name
        self.fields = fields
        self._validate_schema()
        self._field_map = {field.name: field for field in fields}
        
    def _validate_schema(self) -> None:
        """Validate schema definition."""
        field_names = set()
        for field in self.fields:
            if field.name in field_names:
                raise ValueError(f"Duplicate field name: {field.name}")
            field_names.add(field.name)

    def validate_value(self, field_name: str, value: Any) -> List[str]:
        """
        Validate a value against field rules.
        
        Args:
            field_name: Name of the field
            value: Value to validate
            
        Returns:
            List of validation error messages (empty if valid)
        """
        field = self._field_map.get(field_name)
        if not field:
            raise ValueError(f"Unknown field: {field_name}")

        errors = []
        
        # Skip validation for None values if field is not required
        if value is None:
            if field.required:
                errors.append(f"Field {field_name} is required")
            return errors

        # Type validation
        try:
            self._convert_value(value, field.field_type)
        except ValueError as e:
            errors.append(str(e))
            return errors

        # Custom validation rules
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
            else:
                return str(value)
        except Exception as e:
            raise ValueError(f"Invalid value for type {field_type}: {value}")
        
    def validate_field(self, field_name: str, value: Any) -> List[str]:
        """Validate a single field value."""
        errors = []
        field = self.get_field(field_name)
        
        if field:
            # Type validation
            if field.field_type == FieldType.INTEGER:
                if not isinstance(value, (int, float)) or isinstance(value, bool):
                    errors.append(f"Invalid value for type {field.field_type}: {value}")
                elif field_name == "age" and value < 0:
                    errors.append("Age must be a positive number")
                    
            elif field.field_type == FieldType.FLOAT:
                if not isinstance(value, (int, float)) or isinstance(value, bool):
                    errors.append(f"Invalid value for type {field.field_type}: {value}")
                    
            elif field.field_type == FieldType.BOOLEAN:
                if not isinstance(value, bool):
                    errors.append(f"Invalid value for type {field.field_type}: {value}")
                    
            elif field.field_type == FieldType.STRING:
                if not isinstance(value, str):
                    errors.append(f"Invalid value for type {field.field_type}: {value}")
                elif field.pattern and not re.match(field.pattern, value):
                    errors.append(f"Value does not match pattern {field.pattern}: {value}")
    
        return errors
        
    def validate(self, data: Dict[str, Any]) -> List[str]:
        """
        Validate data against schema.
        
        Args:
            data: Dictionary of field values to validate
            
        Returns:
            List of validation error messages
        """
        errors = []
        
        # Check required fields
        for field in self.fields:
            if field.required and field.name not in data:
                errors.append(f"Field {field.name} is required")
                continue
            
            value = data.get(field.name)
            if value is not None:
                # Validate field value
                field_errors = self.validate_field(field.name, value)
                errors.extend(field_errors)
        
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
        