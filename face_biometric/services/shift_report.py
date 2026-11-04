import frappe
from frappe.utils import cint

from face_biometric.core.shift_standing import ShiftStanding


def shift_standing(checkin) -> dict | None:
	"""How a punch sits against its shift. HRMS resolves the shift while inserting the checkin; None when off-shift."""
	if not checkin.shift:
		return None
	grace = frappe.db.get_value(
		"Shift Type", checkin.shift, ["late_entry_grace_period", "early_exit_grace_period"], as_dict=True
	)
	standing = ShiftStanding(
		checkin.log_type,
		checkin.time,
		checkin.shift_start,
		checkin.shift_end,
		cint(grace.late_entry_grace_period),
		cint(grace.early_exit_grace_period),
	)
	return {"name": checkin.shift, **standing.evaluate()}
