import base64
import binascii

import frappe
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from frappe import _

PAYLOAD_VERSION = "fb1"


class DeviceKey:
	"""A phone's public key: ECDSA P-256, SPKI DER, base64.

	P-256 is what Android Keystore and the iOS Secure Enclave can hold in hardware.
	"""

	def __init__(self, public_key_b64: str):
		self.public_key_b64 = public_key_b64
		self._key = self._load(public_key_b64)

	def verify(self, payload: bytes, signature_b64: str) -> bool:
		try:
			signature = base64.b64decode(signature_b64, validate=True)
			self._key.verify(signature, payload, ec.ECDSA(hashes.SHA256()))
		except InvalidSignature, binascii.Error, ValueError, TypeError:
			return False
		return True

	@staticmethod
	def _load(public_key_b64: str) -> ec.EllipticCurvePublicKey:
		try:
			key = serialization.load_der_public_key(base64.b64decode(public_key_b64, validate=True))
		except binascii.Error, ValueError, TypeError:
			frappe.throw(_("The device public key is not valid."))
		if not isinstance(key, ec.EllipticCurvePublicKey) or not isinstance(key.curve, ec.SECP256R1):
			frappe.throw(_("The device public key must be an ECDSA P-256 key."))
		return key


def signing_payload(
	nonce: str, log_type: str, latitude: float | None, longitude: float | None, embedding_digest: str
) -> bytes:
	"""The exact bytes a phone signs for one check-in. Coordinates use six decimals on both sides."""
	parts = [
		PAYLOAD_VERSION,
		nonce,
		log_type,
		_coordinate(latitude),
		_coordinate(longitude),
		embedding_digest,
	]
	return "|".join(parts).encode()


def _coordinate(value: float | None) -> str:
	return "" if value is None else f"{value:.6f}"


KIOSK_PAYLOAD_VERSION = "fb2"


def kiosk_payload(action: str, device: str, nonce: str, digest: str) -> bytes:
	"""The exact bytes a kiosk signs for one request.

	`digest` binds the request's content: the SHA-256 of the embedding for a face punch, or of the
	employee id and proof photo for a PIN punch. The action stops a signature for one being used for the other.
	"""
	return "|".join([KIOSK_PAYLOAD_VERSION, action, device, nonce, digest]).encode()
