from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any

from .models import MaterialSection


@dataclass(frozen=True)
class SectionGenerationRequest:
    section_id: str
    order: int
    title: str
    evidence: tuple[Mapping[str, Any], ...]
    source_ids: tuple[str, ...]


@dataclass(frozen=True)
class SectionGenerationOutcome:
    section: MaterialSection
    attempt_count: int
    failure_category: str | None
    failure_code: str | None


SectionGenerator = Callable[..., MaterialSection | SectionGenerationOutcome]


@dataclass(frozen=True)
class SectionTiming:
    section_id: str
    order: int
    status: str
    duration_ms: int
    attempt_count: int
    failure_category: str | None
    failure_code: str | None


@dataclass(frozen=True)
class SectionGenerationResult:
    sections: tuple[MaterialSection, ...]
    total_duration_ms: int
    max_concurrency: int
    timings: tuple[SectionTiming, ...]


def _generate_measured(
    request: SectionGenerationRequest,
    *,
    generator: SectionGenerator,
    generator_kwargs: Mapping[str, Any],
) -> tuple[MaterialSection, SectionTiming]:
    started = time.perf_counter()
    generated = generator(
        section_id=request.section_id,
        order=request.order,
        title=request.title,
        evidence=list(request.evidence),
        source_ids=list(request.source_ids),
        **generator_kwargs,
    )
    if isinstance(generated, SectionGenerationOutcome):
        outcome = generated
    else:
        outcome = SectionGenerationOutcome(
            section=generated,
            attempt_count=1,
            failure_category=(
                "generation" if generated.status == "failed" else None
            ),
            failure_code=(
                "section_failed" if generated.status == "failed" else None
            ),
        )
    section = outcome.section
    duration_ms = int((time.perf_counter() - started) * 1000)
    return section, SectionTiming(
        section_id=request.section_id,
        order=request.order,
        status=section.status,
        duration_ms=duration_ms,
        attempt_count=outcome.attempt_count,
        failure_category=outcome.failure_category,
        failure_code=outcome.failure_code,
    )


def generate_sections_bounded(
    requests: tuple[SectionGenerationRequest, ...],
    *,
    generator: SectionGenerator,
    generator_kwargs: Mapping[str, Any],
    max_concurrency: int,
) -> SectionGenerationResult:
    if (
        isinstance(max_concurrency, bool)
        or not isinstance(max_concurrency, int)
        or not 1 <= max_concurrency <= 4
    ):
        raise ValueError("max_concurrency must be an integer from 1 to 4")

    started = time.perf_counter()
    if not requests:
        return SectionGenerationResult(
            sections=(),
            total_duration_ms=0,
            max_concurrency=max_concurrency,
            timings=(),
        )

    executor = ThreadPoolExecutor(
        max_workers=min(max_concurrency, len(requests)),
        thread_name_prefix="jstudy-section",
    )
    futures: list[Future[tuple[MaterialSection, SectionTiming]]] = []
    completed: list[tuple[MaterialSection, SectionTiming]] = []
    try:
        for request in requests:
            futures.append(
                executor.submit(
                    _generate_measured,
                    request,
                    generator=generator,
                    generator_kwargs=generator_kwargs,
                )
            )
        for future in as_completed(futures):
            completed.append(future.result())
    except BaseException:
        for future in futures:
            future.cancel()
        executor.shutdown(wait=True, cancel_futures=True)
        raise
    else:
        executor.shutdown(wait=True)

    completed.sort(key=lambda item: item[0].order)
    return SectionGenerationResult(
        sections=tuple(item[0] for item in completed),
        total_duration_ms=int((time.perf_counter() - started) * 1000),
        max_concurrency=max_concurrency,
        timings=tuple(item[1] for item in completed),
    )
