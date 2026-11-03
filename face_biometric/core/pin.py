import hashlib
import hmac
import itertools
import secrets

ITERATIONS = 310_000
SCHEME = "pbkdf2_sha256"


class PinHash:
	"""A salted, slow hash of a short numeric PIN. The PIN itself is never stored or logged.

	A 4-6 digit PIN has few possibilities, so safety comes from the lockout in the caller and from
	the cost of each guess here, not from the hash alone.
	"""

	@staticmethod
	def make(pin: str, iterations: int = ITERATIONS) -> str:
		salt = secrets.token_hex(16)
		return f"{SCHEME}${iterations}${salt}${PinHash._digest(pin, salt, iterations)}"

	@staticmethod
	def verify(pin: str, stored: str | None) -> bool:
		try:
			scheme, iterations, salt, digest = (stored or "").split("$")
			if scheme != SCHEME:
				return False
			expected = PinHash._digest(pin, salt, int(iterations))
		except ValueError:
			return False
		return hmac.compare_digest(expected, digest)

	@staticmethod
	def _digest(pin: str, salt: str, iterations: int) -> str:
		return hashlib.pbkdf2_hmac("sha256", pin.encode(), bytes.fromhex(salt), iterations).hex()


WEAK = {
	"0000",
	"1111",
	"2222",
	"3333",
	"4444",
	"5555",
	"6666",
	"7777",
	"8888",
	"9999",
	"1234",
	"4321",
	"1212",
	"2580",
}


def pin_problem(pin: str, min_length: int, max_length: int) -> str | None:
	"""Why this PIN cannot be used, or None when it is acceptable."""
	if not pin.isascii() or not pin.isdigit():
		return "A PIN can only contain digits."
	if not min_length <= len(pin) <= max_length:
		return f"A PIN must be {min_length} to {max_length} digits."
	if len(set(pin)) == 1 or pin[:4] in WEAK or _is_sequence(pin):
		return "That PIN is too easy to guess."
	return None


def _is_sequence(pin: str) -> bool:
	steps = {int(b) - int(a) for a, b in itertools.pairwise(pin)}
	return steps in ({1}, {-1})
