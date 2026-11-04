from face_biometric.patches.single_defaults import fill_missing

DEFAULTS = {
	"offline_enabled": 1,
	"offline_max_hours": 72,
	"offline_clock_tolerance_minutes": 5,
	"held_retention_days": 90,
	"offline_review_floor": 0.4,
}


def execute():
	fill_missing("Face Biometric Settings", DEFAULTS)
