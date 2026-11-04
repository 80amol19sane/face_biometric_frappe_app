from face_biometric.patches.single_defaults import fill_missing

DEFAULTS = {
	"require_liveness": 1,
	"identify_margin": 0.05,
	"kiosk_return_seconds": 5,
	"pin_enabled": 1,
	"pin_min_length": 4,
	"pin_max_length": 6,
	"photo_retention_days": 30,
}


def execute():
	fill_missing("Face Biometric Settings", DEFAULTS)
