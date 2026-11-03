from unittest import TestCase

from face_biometric.core.phone import mask_phone


class TestMaskPhone(TestCase):
	def test_the_middle_is_hidden(self):
		self.assertEqual(mask_phone("9812345678"), "9812••••78")

	def test_short_or_missing_numbers_are_fully_hidden(self):
		self.assertEqual(mask_phone("12345"), "•••••")
		self.assertEqual(mask_phone(None), "")
