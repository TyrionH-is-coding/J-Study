from .compatibility import render_compatibility_markdown
from .generation import generate_material_section
from .models import (
    CitationRun,
    LegacyMaterialPackageV1,
    MaterialPackageV2,
    MaterialSection,
)
from .validation import (
    MaterialValidationError,
    audit_material_package,
    validate_material_package,
)

__all__ = [
    "CitationRun",
    "LegacyMaterialPackageV1",
    "MaterialPackageV2",
    "MaterialSection",
    "MaterialValidationError",
    "audit_material_package",
    "generate_material_section",
    "render_compatibility_markdown",
    "validate_material_package",
]
