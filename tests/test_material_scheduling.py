import threading
import unittest

from packages.core.jstudy_core.materials.models import (
    MaterialSection,
    SectionQuality,
)
from packages.core.jstudy_core.materials.scheduling import (
    SectionGenerationOutcome,
    SectionGenerationRequest,
    generate_sections_bounded,
)


def request(order: int) -> SectionGenerationRequest:
    return SectionGenerationRequest(
        section_id=f"unit-{order:03d}",
        order=order,
        title=f"Unit {order}",
        evidence=(),
        source_ids=("S001",),
    )


def section_from_call(**kwargs) -> MaterialSection:
    return MaterialSection(
        id=kwargs["section_id"],
        order=kwargs["order"],
        title=kwargs["title"],
        status="failed",
        quality=SectionQuality(
            evidence_status="failed",
            evidence_count=0,
            cited_evidence_count=0,
            citation_coverage=0.0,
        ),
        source_ids=list(kwargs["source_ids"]),
        evidence_ids=[],
        blocks=[],
    )


class MaterialSchedulingTest(unittest.TestCase):
    def run_in_thread(self, callback):
        result = {}
        finished = threading.Event()

        def target():
            try:
                result["value"] = callback()
            except BaseException as exc:
                result["error"] = exc
            finally:
                finished.set()

        thread = threading.Thread(target=target)
        thread.start()
        return thread, finished, result

    def test_default_cap_runs_exactly_three_calls_and_preserves_order(self):
        lock = threading.Lock()
        release = threading.Event()
        three_started = threading.Event()
        active = 0
        observed_max = 0

        def blocking_generator(**kwargs):
            nonlocal active, observed_max
            with lock:
                active += 1
                observed_max = max(observed_max, active)
                if active == 3:
                    three_started.set()
            self.assertTrue(release.wait(timeout=2))
            try:
                return section_from_call(**kwargs)
            finally:
                with lock:
                    active -= 1

        thread, finished, captured = self.run_in_thread(
            lambda: generate_sections_bounded(
                tuple(request(order) for order in range(1, 7)),
                generator=blocking_generator,
                generator_kwargs={},
                max_concurrency=3,
            )
        )
        self.assertTrue(three_started.wait(timeout=2))
        self.assertEqual(observed_max, 3)
        release.set()
        self.assertTrue(finished.wait(timeout=2))
        thread.join(timeout=0)
        self.assertNotIn("error", captured)
        self.assertEqual(
            [item.order for item in captured["value"].sections],
            [1, 2, 3, 4, 5, 6],
        )
        self.assertEqual(captured["value"].max_concurrency, 3)

    def test_reverse_completion_order_does_not_change_result_order(self):
        started = {order: threading.Event() for order in range(1, 4)}
        release = {order: threading.Event() for order in range(1, 4)}
        completed = {order: threading.Event() for order in range(1, 4)}
        completion_order = []
        lock = threading.Lock()

        def reverse_generator(**kwargs):
            order = kwargs["order"]
            started[order].set()
            self.assertTrue(release[order].wait(timeout=2))
            with lock:
                completion_order.append(order)
            completed[order].set()
            return section_from_call(**kwargs)

        thread, finished, captured = self.run_in_thread(
            lambda: generate_sections_bounded(
                tuple(request(order) for order in range(1, 4)),
                generator=reverse_generator,
                generator_kwargs={},
                max_concurrency=3,
            )
        )
        for event in started.values():
            self.assertTrue(event.wait(timeout=2))
        for order in (3, 2, 1):
            release[order].set()
            self.assertTrue(completed[order].wait(timeout=2))
        self.assertTrue(finished.wait(timeout=2))
        thread.join(timeout=0)

        self.assertNotIn("error", captured)
        self.assertEqual(completion_order, [3, 2, 1])
        self.assertEqual(
            [item.order for item in captured["value"].sections],
            [1, 2, 3],
        )
        self.assertEqual(
            [item.order for item in captured["value"].timings],
            [1, 2, 3],
        )

    def test_concurrency_one_preserves_serial_behavior(self):
        lock = threading.Lock()
        active = 0
        observed_max = 0
        call_order = []

        def serial_generator(**kwargs):
            nonlocal active, observed_max
            with lock:
                active += 1
                observed_max = max(observed_max, active)
                call_order.append(kwargs["order"])
            try:
                return section_from_call(**kwargs)
            finally:
                with lock:
                    active -= 1

        result = generate_sections_bounded(
            tuple(request(order) for order in range(1, 4)),
            generator=serial_generator,
            generator_kwargs={},
            max_concurrency=1,
        )

        self.assertEqual(observed_max, 1)
        self.assertEqual(call_order, [1, 2, 3])
        self.assertEqual([item.order for item in result.sections], [1, 2, 3])

    def test_provider_exception_escapes_without_partial_result(self):
        provider_error = RuntimeError("provider unavailable")

        def failing_generator(**kwargs):
            if kwargs["order"] == 2:
                raise provider_error
            return section_from_call(**kwargs)

        with self.assertRaises(RuntimeError) as caught:
            generate_sections_bounded(
                tuple(request(order) for order in range(1, 4)),
                generator=failing_generator,
                generator_kwargs={},
                max_concurrency=2,
            )

        self.assertIs(caught.exception, provider_error)

    def test_concurrency_outside_one_to_four_fails_closed(self):
        for value in (0, 5):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    generate_sections_bounded(
                        (request(1),),
                        generator=section_from_call,
                        generator_kwargs={},
                        max_concurrency=value,
                    )

    def test_safe_generation_diagnostics_are_preserved_in_timing(self):
        def diagnostic_generator(**kwargs):
            return SectionGenerationOutcome(
                section=section_from_call(**kwargs),
                attempt_count=3,
                failure_category="schema_validation",
                failure_code="list_type",
            )

        result = generate_sections_bounded(
            (request(1),),
            generator=diagnostic_generator,
            generator_kwargs={},
            max_concurrency=1,
        )

        timing = result.timings[0]
        self.assertEqual(timing.attempt_count, 3)
        self.assertEqual(timing.failure_category, "schema_validation")
        self.assertEqual(timing.failure_code, "list_type")


if __name__ == "__main__":
    unittest.main()
