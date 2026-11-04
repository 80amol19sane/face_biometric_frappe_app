from unittest import TestCase

from face_biometric.core.matcher import AMBIGUOUS, MATCHED, NO_MATCH, FaceMatcher


class TestFaceMatcher(TestCase):
	def setUp(self):
		self.matcher = FaceMatcher(threshold=0.5, margin=0.05)

	def test_a_clear_best_match_wins(self):
		result = self.matcher.decide([("A", 0.81), ("B", 0.12), ("C", 0.30)])
		self.assertEqual((result.status, result.employee), (MATCHED, "A"))
		self.assertAlmostEqual(result.similarity, 0.81)
		self.assertAlmostEqual(result.runner_up, 0.30)

	def test_nobody_reaching_the_threshold_is_no_match(self):
		result = self.matcher.decide([("A", 0.49), ("B", 0.10)])
		self.assertEqual((result.status, result.employee), (NO_MATCH, None))

	def test_exactly_the_threshold_counts(self):
		self.assertEqual(self.matcher.decide([("A", 0.5)]).status, MATCHED)

	def test_two_close_candidates_are_ambiguous_not_guessed(self):
		result = self.matcher.decide([("A", 0.70), ("B", 0.68)])
		self.assertEqual((result.status, result.employee), (AMBIGUOUS, None))

	def test_a_gap_just_wide_enough_is_accepted(self):
		self.assertEqual(self.matcher.decide([("A", 0.70), ("B", 0.64)]).status, MATCHED)

	def test_a_single_enrolled_person_needs_only_the_threshold(self):
		self.assertEqual(self.matcher.decide([("A", 0.55)]).employee, "A")

	def test_nobody_enrolled_is_no_match(self):
		self.assertEqual(self.matcher.decide([]).status, NO_MATCH)
