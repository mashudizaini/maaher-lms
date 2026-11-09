# 02 — REA evidence register & authorized scope

## Current evidence status
- **PUBLIC:** `https://lms.timedooracademy.com/` responds, but the public web extractor did not yield authenticated LMS UI content. Nothing about its private DB/API can be inferred reliably.
- **OWNER-SUPPLIED:** five screenshots were shared in chat. They serve as a visual reference; retain only redacted, authorized copies outside repository or in a secured asset store. **Screen-specific interpretation and click outcomes are not verified here.**
- **PENDING:** owner-guided, authorized authenticated navigation on a local browser session.

## REA rules
- Authorized account, permitted UI and normal developer tools only; do not bypass auth/access controls, attempt rate-limit evasion, scrape other users, dump tokens or request protected APIs.
- Use a dedicated test account when possible, with synthetic learner data; remove email/student names, course materials protected by copyright, credentials and session identifiers from evidence.
- Record features and flows, not vendor's assets/source. Build original branded Maaher UI and code.
- A page observation is not proof of backend architecture.

## Evidence template (repeat per screen)
| Field | Entry |
|---|---|
| Evidence ID | REA-001 |
| Screen / URL path | To inspect with owner |
| Role | student / teacher / admin |
| Trigger / interaction | e.g. open course → lesson → submit |
| Visible result | Observed, exact words (no PII) |
| Status | OBSERVED / INFERRED / UNKNOWN |
| Screenshot reference (sanitized) | private artifact pointer |
| Equivalent Maaher requirement | LMS-xx |
| Owner approval | pending |

## Investigation route (ordered)
Login → dashboard → my courses → course overview → lesson → exercise/coding editor → submit → grade/feedback → progress. Repeat as teacher: course setup → assignment → submissions → rubric/feedback. Admin: tenant users → course/cohorts → reports. If navigation unavailable for a role, mark UNKNOWN; do not guess.

## Initial feature matrix
| Feature | Reference evidence | Maaher decision |
|---|---|---|
| Role-specific dashboard | UNKNOWN (authenticated evidence pending) | implement per `LMS-01` |
| Course / lesson hierarchy | UNKNOWN | implement per `LMS-02` |
| Coding editor / runtime | UNKNOWN | editor planned; runner gated |
| Assignments / grading | UNKNOWN | implement `LMS-05`/`06` |
| Progress visualization | UNKNOWN | implement `LMS-09` |

## REA setup
Inspect the upstream README and package's exact setup flags **at install time**. Avoid copy/pasting unverified `--client` or `--dry-run` options; start with `npx rea-agents setup --help` and review package provenance/permissions. REA is optional; ordinary permitted browser observation can document the same functional requirements.
