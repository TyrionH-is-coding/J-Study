from .compatibility import render_compatibility_markdown
from .generation import (
    SECTION_PROVIDER_CALL_LIMIT,
    generate_material_section,
    generate_material_section_with_diagnostics,
)
from .models import (
    CitationRun,
    LegacyMaterialPackageV1,
    MaterialPackageV2,
    MaterialSection,
)
from .scheduling import (
    SectionGenerationOutcome,
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
    "SECTION_PROVIDER_CALL_LIMIT",
    "SectionGenerationOutcome",
    "SectionGenerationRequest",
    "SectionGenerationResult",
    "audit_material_package",
    "generate_material_section",
    "generate_material_section_with_diagnostics",
    "generate_sections_bounded",
    "render_compatibility_markdown",
    "validate_material_package",
    "validate_material_package_coordination",
]
