import base64
import struct

import frappe
from frappe.tests import UnitTestCase

from face_biometric.core.embedding import Embedding


def encode(values: list[float]) -> str:
	return base64.b64encode(struct.pack(f"<{len(values)}f", *values)).decode()


def vector(seed: float, size: int = 128) -> list[float]:
	return [seed + i * 0.01 for i in range(size)]


class TestEmbedding(UnitTestCase):
	def test_same_vector_is_a_perfect_match(self):
		a, b = Embedding(encode(vector(1))), Embedding(encode(vector(1)))
		self.assertAlmostEqual(a.similarity(b), 1.0, places=5)

	def test_scale_does_not_change_similarity(self):
		a = Embedding(encode(vector(1)))
		b = Embedding(encode([v * 5 for v in vector(1)]))
		self.assertAlmostEqual(a.similarity(b), 1.0, places=5)

	def test_opposite_vector_scores_negative(self):
		a = Embedding(encode(vector(1)))
		b = Embedding(encode([-v for v in vector(1)]))
		self.assertAlmostEqual(a.similarity(b), -1.0, places=5)

	def test_digest_changes_with_the_embedding(self):
		self.assertNotEqual(Embedding(encode(vector(1))).digest(), Embedding(encode(vector(2))).digest())

	def test_rejects_bad_input(self):
		bad = {
			"not base64": "***",
			"too short": encode([1.0] * 10),
			"too long": encode([1.0] * 2000),
			"zero vector": encode([0.0] * 128),
			"nan": encode([float("nan")] + [1.0] * 127),
			"infinity": encode([float("inf")] + [1.0] * 127),
			"ragged bytes": base64.b64encode(b"\x00" * 513).decode(),
		}
		for label, encoded in bad.items():
			with self.subTest(label), self.assertRaises(frappe.ValidationError):
				Embedding(encoded)

	def test_rejects_comparing_different_models(self):
		a, b = Embedding(encode(vector(1, 128))), Embedding(encode(vector(1, 256)))
		with self.assertRaises(frappe.ValidationError):
			a.similarity(b)
