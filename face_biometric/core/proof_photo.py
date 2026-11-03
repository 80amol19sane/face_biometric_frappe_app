import base64
import binascii
import io

from PIL import Image, UnidentifiedImageError

MAX_BYTES = 1_500_000
MAX_PIXELS = 4096 * 4096
JPEG_MAGIC = b"\xff\xd8\xff"


class ProofPhotoError(ValueError):
	pass


def decode_proof_photo(encoded: str | None, max_bytes: int = MAX_BYTES) -> bytes:
	"""A PIN punch's proof photo: base64 of a JPEG, small enough to store, nothing else.

	Checking the JPEG header stops the upload being used to park arbitrary files on the server.
	"""
	if not encoded:
		raise ProofPhotoError("A photo is required.")
	if len(encoded) > max_bytes * 4 // 3 + 8:
		raise ProofPhotoError("The photo is too large.")
	try:
		data = base64.b64decode(encoded, validate=True)
	except (binascii.Error, ValueError, TypeError) as error:
		raise ProofPhotoError("The photo is not valid.") from error
	if len(data) > max_bytes:
		raise ProofPhotoError("The photo is too large.")
	if not data.startswith(JPEG_MAGIC) or not _is_decodable_jpeg(data):
		raise ProofPhotoError("The photo must be a JPEG.")
	return data


def _is_decodable_jpeg(data: bytes) -> bool:
	"""A real, bounded JPEG. A valid header on junk would otherwise break file storage after the PIN passed."""
	try:
		with Image.open(io.BytesIO(data)) as image:
			if image.format != "JPEG" or image.width * image.height > MAX_PIXELS:
				return False
			image.verify()
	except UnidentifiedImageError, OSError, ValueError, SyntaxError:
		return False
	return True
