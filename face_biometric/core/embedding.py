import base64
import binascii
import hashlib
import math
import struct

import frappe
from frappe import _

MIN_DIMENSIONS = 64
MAX_DIMENSIONS = 1024
BYTES_PER_VALUE = 4


class Embedding:
	"""A face embedding as the phone sends it: base64 of little-endian float32 values.

	The wire form is raw bytes, not a JSON list, so the phone and the server hash and sign
	exactly the same thing. Float text formatting differs between JS and Python.
	"""

	def __init__(self, encoded: str):
		self.encoded = encoded
		self.raw = self._decode(encoded)
		self.values = self._unpack(self.raw)
		self.norm = math.sqrt(sum(v * v for v in self.values))
		if not math.isfinite(self.norm) or self.norm < 1e-6:
			frappe.throw(_("The face embedding is empty or invalid."))

	@property
	def dimensions(self) -> int:
		return len(self.values)

	def digest(self) -> str:
		"""Hash the device signs, so a signature cannot be reused with another face."""
		return hashlib.sha256(self.raw).hexdigest()

	def similarity(self, other: "Embedding") -> float:
		"""Cosine similarity in [-1, 1]. Higher means more alike."""
		if self.dimensions != other.dimensions:
			frappe.throw(_("The face embedding does not match the enrolled model."))
		dot = sum(a * b for a, b in zip(self.values, other.values, strict=True))
		return dot / (self.norm * other.norm)

	@staticmethod
	def _decode(encoded: str) -> bytes:
		try:
			return base64.b64decode(encoded, validate=True)
		except binascii.Error, ValueError, TypeError:
			frappe.throw(_("The face embedding is not valid base64."))

	@staticmethod
	def _unpack(raw: bytes) -> tuple[float, ...]:
		count, remainder = divmod(len(raw), BYTES_PER_VALUE)
		if remainder or not MIN_DIMENSIONS <= count <= MAX_DIMENSIONS:
			frappe.throw(
				_("The face embedding must have {0} to {1} values.").format(MIN_DIMENSIONS, MAX_DIMENSIONS)
			)
		values = struct.unpack(f"<{count}f", raw)
		if not all(math.isfinite(v) for v in values):
			frappe.throw(_("The face embedding has values that are not numbers."))
		return values
