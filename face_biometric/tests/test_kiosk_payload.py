from unittest import TestCase

from face_biometric.core.device_signature import kiosk_payload


class TestKioskPayload(TestCase):
	def test_the_payload_is_versioned_and_ordered(self):
		self.assertEqual(
			kiosk_payload("identify", "BDEV-00004", "nonce123", "ab12"),
			b"fb2|identify|BDEV-00004|nonce123|ab12",
		)

	def test_a_signature_for_one_action_cannot_serve_another(self):
		self.assertNotEqual(kiosk_payload("identify", "D", "n", "x"), kiosk_payload("pin", "D", "n", "x"))

	def test_it_cannot_be_confused_with_a_personal_phone_payload(self):
		self.assertTrue(kiosk_payload("identify", "D", "n", "x").startswith(b"fb2|"))
