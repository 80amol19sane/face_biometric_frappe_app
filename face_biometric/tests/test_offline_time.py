from unittest import TestCase

from face_biometric.core.offline_time import MS_PER_HOUR, MS_PER_MINUTE, time_problems

NOW = 1_800_000_000_000


def check(**changes):
	args = {
		"anchored_ms": NOW - MS_PER_HOUR,
		"wall_ms": NOW - MS_PER_HOUR,
		"boot_count": 7,
		"anchor_boot_count": 7,
		"now_ms": NOW,
		"max_hours": 72,
		"tolerance_minutes": 5,
	}
	return time_problems(**{**args, **changes})


class TestTimeProblems(TestCase):
	def test_a_recent_scan_with_a_steady_clock_is_fine(self):
		self.assertEqual(check(), [])

	def test_a_restart_breaks_the_anchor(self):
		self.assertEqual(len(check(boot_count=8)), 1)

	def test_a_changed_clock_is_caught_either_way(self):
		self.assertEqual(len(check(wall_ms=NOW - MS_PER_HOUR + 6 * MS_PER_MINUTE)), 1)
		self.assertEqual(len(check(wall_ms=NOW - MS_PER_HOUR - 6 * MS_PER_MINUTE)), 1)

	def test_a_small_drift_is_allowed(self):
		self.assertEqual(check(wall_ms=NOW - MS_PER_HOUR + 4 * MS_PER_MINUTE), [])

	def test_a_future_scan_is_caught(self):
		self.assertEqual(len(check(anchored_ms=NOW + 6 * MS_PER_MINUTE, wall_ms=NOW + 6 * MS_PER_MINUTE)), 1)

	def test_a_scan_older_than_the_window_is_caught(self):
		old = NOW - 73 * MS_PER_HOUR
		self.assertEqual(len(check(anchored_ms=old, wall_ms=old)), 1)
		fresh = NOW - 72 * MS_PER_HOUR
		self.assertEqual(check(anchored_ms=fresh, wall_ms=fresh), [])

	def test_every_problem_is_reported(self):
		old = NOW - 100 * MS_PER_HOUR
		self.assertEqual(len(check(anchored_ms=old, wall_ms=NOW, boot_count=9)), 3)
