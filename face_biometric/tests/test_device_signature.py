import base64

import frappe
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from frappe.tests import UnitTestCase

from face_biometric.core.device_signature import DeviceKey, signing_payload


def public_key_b64(private_key) -> str:
	der = private_key.public_key().public_bytes(
		serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
	)
	return base64.b64encode(der).decode()


def sign(private_key, payload: bytes) -> str:
	return base64.b64encode(private_key.sign(payload, ec.ECDSA(hashes.SHA256()))).decode()


class TestDeviceSignature(UnitTestCase):
	def setUp(self):
		self.private_key = ec.generate_private_key(ec.SECP256R1())
		self.device = DeviceKey(public_key_b64(self.private_key))
		self.payload = signing_payload("nonce-1", "IN", 18.5204, 73.8567, "abc123")

	def test_accepts_a_valid_signature(self):
		self.assertTrue(self.device.verify(self.payload, sign(self.private_key, self.payload)))

	def test_rejects_a_changed_payload(self):
		signature = sign(self.private_key, self.payload)
		other = signing_payload("nonce-1", "OUT", 18.5204, 73.8567, "abc123")
		self.assertFalse(self.device.verify(other, signature))

	def test_rejects_another_devices_signature(self):
		stranger = ec.generate_private_key(ec.SECP256R1())
		self.assertFalse(self.device.verify(self.payload, sign(stranger, self.payload)))

	def test_rejects_garbage_signatures(self):
		for signature in ("", "***", base64.b64encode(b"junk").decode()):
			with self.subTest(signature):
				self.assertFalse(self.device.verify(self.payload, signature))

	def test_payload_pins_coordinates_to_six_decimals(self):
		self.assertEqual(
			signing_payload("n", "IN", 18.5, None, "d"),
			b"fb1|n|IN|18.500000||d",
		)

	def test_rejects_keys_that_are_not_p256(self):
		with self.assertRaises(frappe.ValidationError):
			DeviceKey(public_key_b64(ec.generate_private_key(ec.SECP384R1())))
		rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
		der = rsa_key.public_key().public_bytes(
			serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
		)
		with self.assertRaises(frappe.ValidationError):
			DeviceKey(base64.b64encode(der).decode())
		with self.assertRaises(frappe.ValidationError):
			DeviceKey("not a key")
