MS_PER_MINUTE = 60_000
MS_PER_HOUR = 3_600_000


def time_problems(
	*,
	anchored_ms: int,
	wall_ms: int,
	boot_count: int,
	anchor_boot_count: int,
	now_ms: int,
	max_hours: int,
	tolerance_minutes: int,
) -> list[str]:
	"""Reasons an offline scan's time cannot be trusted. Empty means it can.

	`anchored_ms` is the server's time at the last contact plus the time the phone has run since, which
	a changed clock cannot move. `wall_ms` is what the phone's clock said. A restart resets the running
	time, so it breaks the anchor.
	"""
	tolerance = tolerance_minutes * MS_PER_MINUTE
	problems = []
	if boot_count != anchor_boot_count:
		problems.append(
			"The phone restarted after its last contact with the server, so the time cannot be trusted."
		)
	if abs(anchored_ms - wall_ms) > tolerance:
		problems.append("The phone's clock disagrees with the time worked out from the server.")
	if anchored_ms > now_ms + tolerance:
		problems.append("The scan is dated in the future.")
	elif now_ms - anchored_ms > max_hours * MS_PER_HOUR:
		problems.append(f"The scan is older than {max_hours} hours.")
	return problems
