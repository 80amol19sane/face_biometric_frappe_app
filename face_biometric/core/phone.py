def mask_phone(number: str | None) -> str:
	"""Keep the first four and last two digits, e.g. 9812345678 -> 9812••••78. Admin lists never need the whole number."""
	digits = (number or "").strip()
	if len(digits) < 8:
		return "•" * len(digits)
	return f"{digits[:4]}{'•' * (len(digits) - 6)}{digits[-2:]}"
