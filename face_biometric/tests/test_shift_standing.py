from datetime import datetime
from unittest import TestCase

from face_biometric.core.shift_standing import ShiftStanding

START = datetime(2026, 11, 2, 9, 0)
END = datetime(2026, 11, 2, 18, 0)


def standing(log_type: str, hour: int, minute: int, late_grace=15, early_grace=10) -> dict:
	return ShiftStanding(
		log_type, datetime(2026, 11, 2, hour, minute), START, END, late_grace, early_grace
	).evaluate()


class TestShiftStanding(TestCase):
	def test_arriving_early_or_exactly_on_time_is_on_time(self):
		self.assertEqual(standing("IN", 8, 52), {"status": "On Time", "minutes": 0})
		self.assertEqual(standing("IN", 9, 0), {"status": "On Time", "minutes": 0})

	def test_lateness_inside_the_grace_window_is_within_grace(self):
		self.assertEqual(standing("IN", 9, 12), {"status": "Within Grace", "minutes": 12})
		self.assertEqual(standing("IN", 9, 15), {"status": "Within Grace", "minutes": 15})

	def test_lateness_past_the_grace_window_is_late(self):
		self.assertEqual(standing("IN", 9, 16), {"status": "Late", "minutes": 16})
		self.assertEqual(standing("IN", 9, 38), {"status": "Late", "minutes": 38})

	def test_no_grace_means_any_lateness_is_late(self):
		self.assertEqual(standing("IN", 9, 1, late_grace=0), {"status": "Late", "minutes": 1})

	def test_leaving_at_or_after_the_end_is_on_time(self):
		self.assertEqual(standing("OUT", 18, 0), {"status": "On Time", "minutes": 0})
		self.assertEqual(standing("OUT", 19, 30), {"status": "On Time", "minutes": 0})

	def test_leaving_inside_the_early_grace_is_on_time(self):
		self.assertEqual(standing("OUT", 17, 50), {"status": "On Time", "minutes": 0})

	def test_leaving_before_the_early_grace_is_an_early_exit(self):
		self.assertEqual(standing("OUT", 17, 49), {"status": "Early Exit", "minutes": 11})
		self.assertEqual(standing("OUT", 15, 0), {"status": "Early Exit", "minutes": 180})
