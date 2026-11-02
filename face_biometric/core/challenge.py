import hmac
import secrets

import frappe

DEFAULT_TTL_SECONDS = 60


class ChallengeStore:
	"""One-time nonces, one live nonce per device, kept in Redis.

	A check-in is signed over its nonce, so a captured request cannot be replayed.
	"""

	def __init__(self, ttl_seconds: int = DEFAULT_TTL_SECONDS):
		self.ttl_seconds = ttl_seconds

	def issue(self, device: str) -> str:
		nonce = secrets.token_urlsafe(24)
		frappe.cache.set(self._key(device), nonce, ex=self.ttl_seconds)
		return nonce

	def consume(self, device: str, nonce: str) -> bool:
		"""Spend the nonce. GETDEL is atomic, so two parallel requests cannot both win."""
		stored = frappe.cache.getdel(self._key(device))
		return stored is not None and hmac.compare_digest(stored.decode(), nonce)

	@staticmethod
	def _key(device: str) -> bytes:
		return frappe.cache.make_key(f"face_biometric:challenge:{device}")
