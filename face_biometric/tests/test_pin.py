from unittest import TestCase

from face_biometric.core.pin import PinHash, pin_problem


class TestPinHash(TestCase):
	def test_a_correct_pin_verifies_and_a_wrong_one_does_not(self):
		stored = PinHash.make("4821", iterations=1000)
		self.assertTrue(PinHash.verify("4821", stored))
		self.assertFalse(PinHash.verify("4822", stored))

	def test_the_same_pin_hashes_differently_each_time(self):
		self.assertNotEqual(PinHash.make("4821", iterations=1000), PinHash.make("4821", iterations=1000))

	def test_the_pin_is_not_in_the_stored_value(self):
		self.assertNotIn("4821", PinHash.make("4821", iterations=1000))

	def test_junk_or_missing_hashes_never_verify(self):
		for stored in (None, "", "garbage", "md5$1$aa$bb", "pbkdf2_sha256$x$aa$bb"):
			self.assertFalse(PinHash.verify("4821", stored))


class TestPinProblem(TestCase):
	def test_a_good_pin_has_no_problem(self):
		self.assertIsNone(pin_problem("4821", 4, 6))
		self.assertIsNone(pin_problem("739402", 4, 6))

	def test_length_and_characters_are_checked(self):
		self.assertIn("4 to 6", pin_problem("123", 4, 6))
		self.assertIn("4 to 6", pin_problem("1234567", 4, 6))
		self.assertIn("digits", pin_problem("48a1", 4, 6))
		self.assertIn("digits", pin_problem("\uff14\uff18\uff12\uff11", 4, 6))

	def test_easy_guesses_are_refused(self):
		for pin in ("1111", "0000", "1234", "4321", "1212", "2580", "56789", "987654"):
			self.assertIn("easy", pin_problem(pin, 4, 6), pin)
