import base64
import binascii

MAX_BYTES = 1_500_000
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
	if not data.startswith(JPEG_MAGIC):
		raise ProofPhotoError("The photo must be a JPEG.")
	return data
