### Face Biometric

Face-verified attendance for Frappe HRMS. Phones act as shared kiosks (face or PIN) and HR manages everything from an admin area.
Faces are matched on-device as numeric embeddings and verified on the server; no photo of a face check-in is stored.

#### What it adds

| DocType | Purpose |
| --- | --- |
| Face Template | One encrypted face template per employee, enrolled by HR in person |
| Employee PIN | A salted PBKDF2 hash of the employee's PIN, with an on/off switch |
| Biometric Device | A registered phone: `Personal` (one employee's own phone) or `Kiosk` (shared, with a Shift Location) |
| Face Verification Log | Every punch and every refusal, with method (Face / PIN), similarity and detail |
| Face Biometric Settings | Threshold, match margin, liveness, PIN length, lockout, photo retention |

Check-ins are ordinary HRMS `Employee Checkin` rows, so shifts, grace periods and auto attendance work as usual.

#### API (`face_biometric.api.*`)

- `kiosk.get_challenge`, `kiosk.identify`, `kiosk.look_up`, `kiosk.pin_check_in`: guest endpoints for a kiosk. Each action needs a one-time nonce and an
  ECDSA P-256 signature (`fb2|action|device|nonce|digest`) from the key an HR user registered. All are rate limited.
- `admin.*`: HR Manager / System Manager only. `register_kiosk`, `dashboard`, `employees`, `employee_profile`, `set_pin`, `set_pin_enabled`,
  `biometric_history`, `attendance_logs`, `failed_attempts`, `devices`, `revoke_device`, `sync_status`, `get_settings`, `update_settings`.
- `enrolment.enrol_employee_face`: HR enrols or replaces a face in person. `enrolment.register_device`, `checkin.*`: the earlier personal-phone flow, kept until old apps are retired.

#### Security notes

- A kiosk request is trusted only by signature. PIN checks give one error for every wrong-ID/wrong-PIN case at equal cost; failures share a per-employee lockout
  (default 5 tries / 15 min) and pause a kiosk for a minute after 5 failures. Nobody can set their own PIN or enrol their own face.
- Face search accepts a match only above `match_threshold` and ahead of the runner-up by `identify_margin`.
- `Employee PIN` is not version-tracked so the hash never reaches the Version table. Proof photos from PIN punches are private files, deleted daily after `photo_retention_days`.

#### After installing or updating

Run `bench --site <site> migrate`. Patches mark existing devices `Personal` and fill defaults for the newer settings.
Calibrate `match_threshold` and `identify_margin` against your own model; the shipped 0.6 is conservative for MobileFaceNet.

#### Tests

```bash
bench --site <site> run-tests --app face_biometric   # integration tests
python -m unittest discover -s face_biometric/tests   # pure unit tests (core logic)
```

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch N
bench install-app face_biometric
```

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/face_biometric
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### License

mit
