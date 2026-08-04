from .compatibility import render_compatibility_markdown
from .generation import generate_material_section
from .models import (
    CitationRun,
    LegacyMaterialPackageV1,
    MaterialPackageV2,
    MaterialSection,
)
from .scheduling import (
    SectionGenerationRequest,
    SectionGenerationResult,
    generate_sections_bounded,
)
from .validation import (
    MaterialValidationError,
    audit_material_package,
    validate_material_package,
    validate_material_package_coordination,
)

__all__ = [
    "CitationRun",
    "LegacyMaterialPackageV1",
    "MaterialPackageV2",
    "MaterialSection",
    "MaterialValidationError",
    "SectionGenerationRequest",
    "SectionGenerationResult",
    "audit_material_package",
    "generate_material_section",
    "generate_sections_bounded",
    "render_compatibility_markdown",
    "validate_material_package",
    "validate_material_package_coordination",
]
