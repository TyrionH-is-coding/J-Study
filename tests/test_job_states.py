import unittest

from packages.core.jstudy_core.job_system.states import (
    InvalidJobTransitionError,
    JobState,
    is_terminal,
    progress_for,
    public_status,
    require_transition,
)


class JobStateTest(unittest.TestCase):
    def test_canonical_states_are_stable(self):
        self.assertEqual(
            [state.value for state in JobState],
            [
                "queued",
                "parsing",
                "retrieving",
                "generating",
                "packaging",
                "completed",
                "failed",
                "cancelled",
            ],
        )

    def test_all_allowed_transitions(self):
        allowed = {
            JobState.QUEUED: {JobState.PARSING, JobState.CANCELLED},
            JobState.PARSING: {
                JobState.RETRIEVING,
                JobState.FAILED,
                JobState.CANCELLED,
            },
            JobState.RETRIEVING: {
                JobState.GENERATING,
                JobState.FAILED,
                JobState.CANCELLED,
            },
            JobState.GENERATING: {
                JobState.PACKAGING,
                JobState.FAILED,
                JobState.CANCELLED,
            },
            JobState.PACKAGING: {
                JobState.COMPLETED,
                JobState.FAILED,
                JobState.CANCELLED,
            },
        }

        for current, targets in allowed.items():
            for target in targets:
                with self.subTest(current=current, target=target):
                    self.assertIsNone(require_transition(current, target))

    def test_all_forbidden_transitions(self):
        allowed = {
            (JobState.QUEUED, JobState.PARSING),
            (JobState.QUEUED, JobState.CANCELLED),
            (JobState.PARSING, JobState.RETRIEVING),
            (JobState.PARSING, JobState.FAILED),
            (JobState.PARSING, JobState.CANCELLED),
            (JobState.RETRIEVING, JobState.GENERATING),
            (JobState.RETRIEVING, JobState.FAILED),
            (JobState.RETRIEVING, JobState.CANCELLED),
            (JobState.GENERATING, JobState.PACKAGING),
            (JobState.GENERATING, JobState.FAILED),
            (JobState.GENERATING, JobState.CANCELLED),
            (JobState.PACKAGING, JobState.COMPLETED),
            (JobState.PACKAGING, JobState.FAILED),
            (JobState.PACKAGING, JobState.CANCELLED),
        }

        for current in JobState:
            for target in JobState:
                if (current, target) in allowed:
                    continue
                with self.subTest(current=current, target=target):
                    with self.assertRaises(InvalidJobTransitionError):
                        require_transition(current, target)

    def test_retry_requires_explicit_authorization(self):
        retryable_states = {
            JobState.PARSING,
            JobState.RETRIEVING,
            JobState.GENERATING,
            JobState.PACKAGING,
        }

        for current in retryable_states:
            with self.subTest(current=current, authorized=False):
                with self.assertRaises(InvalidJobTransitionError):
                    require_transition(current, JobState.QUEUED)
            with self.subTest(current=current, authorized=True):
                self.assertIsNone(
                    require_transition(current, JobState.QUEUED, allow_retry=True)
                )

        with self.assertRaises(InvalidJobTransitionError):
            require_transition(JobState.FAILED, JobState.QUEUED, allow_retry=True)

    def test_allow_retry_does_not_enable_other_forbidden_transitions(self):
        normally_allowed = {
            (JobState.QUEUED, JobState.PARSING),
            (JobState.QUEUED, JobState.CANCELLED),
            (JobState.PARSING, JobState.RETRIEVING),
            (JobState.PARSING, JobState.FAILED),
            (JobState.PARSING, JobState.CANCELLED),
            (JobState.RETRIEVING, JobState.GENERATING),
            (JobState.RETRIEVING, JobState.FAILED),
            (JobState.RETRIEVING, JobState.CANCELLED),
            (JobState.GENERATING, JobState.PACKAGING),
            (JobState.GENERATING, JobState.FAILED),
            (JobState.GENERATING, JobState.CANCELLED),
            (JobState.PACKAGING, JobState.COMPLETED),
            (JobState.PACKAGING, JobState.FAILED),
            (JobState.PACKAGING, JobState.CANCELLED),
        }
        retry_allowed = {
            (JobState.PARSING, JobState.QUEUED),
            (JobState.RETRIEVING, JobState.QUEUED),
            (JobState.GENERATING, JobState.QUEUED),
            (JobState.PACKAGING, JobState.QUEUED),
        }

        for current in JobState:
            for target in JobState:
                if (current, target) in normally_allowed | retry_allowed:
                    continue
                with self.subTest(current=current, target=target):
                    with self.assertRaises(InvalidJobTransitionError):
                        require_transition(current, target, allow_retry=True)

    def test_public_status_projection(self):
        expected = {
            JobState.QUEUED: "queued",
            JobState.PARSING: "running",
            JobState.RETRIEVING: "running",
            JobState.GENERATING: "running",
            JobState.PACKAGING: "running",
            JobState.COMPLETED: "completed",
            JobState.FAILED: "failed",
            JobState.CANCELLED: "failed",
        }
        self.assertEqual(
            {state: public_status(state) for state in JobState},
            expected,
        )

    def test_terminal_state_detection(self):
        terminal = {
            JobState.COMPLETED,
            JobState.FAILED,
            JobState.CANCELLED,
        }
        self.assertEqual(
            {state for state in JobState if is_terminal(state)},
            terminal,
        )

    def test_progress_mapping_is_deterministic(self):
        expected = {
            JobState.QUEUED: 0,
            JobState.PARSING: 10,
            JobState.RETRIEVING: 35,
            JobState.GENERATING: 60,
            JobState.PACKAGING: 90,
            JobState.COMPLETED: 100,
            JobState.FAILED: 100,
            JobState.CANCELLED: 100,
        }
        self.assertEqual(
            {state: progress_for(state) for state in JobState},
            expected,
        )


if __name__ == "__main__":
    unittest.main()
