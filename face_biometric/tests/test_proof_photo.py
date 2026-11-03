import base64
from unittest import TestCase

from face_biometric.core.proof_photo import ProofPhotoError, decode_proof_photo

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64


class TestProofPhoto(TestCase):
	def test_a_jpeg_is_accepted(self):
		self.assertEqual(decode_proof_photo(base64.b64encode(JPEG).decode()), JPEG)

	def test_missing_or_empty_is_refused(self):
		for value in (None, ""):
			with self.assertRaises(ProofPhotoError):
				decode_proof_photo(value)

	def test_non_base64_is_refused(self):
		with self.assertRaises(ProofPhotoError):
			decode_proof_photo("not base64!!")

	def test_something_that_is_not_a_jpeg_is_refused(self):
		with self.assertRaises(ProofPhotoError):
			decode_proof_photo(base64.b64encode(b"MZ\x90\x00 an exe").decode())

	def test_oversize_is_refused_before_decoding(self):
		big = base64.b64encode(JPEG + b"\x00" * 2000).decode()
		with self.assertRaises(ProofPhotoError):
			decode_proof_photo(big, max_bytes=1000)
