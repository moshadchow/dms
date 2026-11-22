# Plan: Add PowerPoint and image file upload support to DMS

## Current State

**Already supported:**
- `.jpg`, `.jpeg`, `.png` via MIME types `image/jpeg`, `image/png` → `FileType.IMAGE`
- `.pdf`, `.docx`, `.xls`, `.xlsx` via their MIME types

**Not supported:**
- `.ppt` → `application/vnd.ms-powerpoint`
- `.pptx` → `application/vnd.openxmlformats-officedocument.presentationml.presentation`
- `.pps` → `application/vnd.ms-powerpoint`
- `.ppsx` → `application/vnd.openxmlformats-officedocument.presentationml.slideshow`

**Validation architecture (single source of truth):**
- `backend/documents/models.py:58-65` — `ALLOWED_MIME_TYPES: dict[str, FileType]` (authoritative)
- `backend/core/config.py:45-51` — `ALLOWED_MIME_TYPES: List[str]` (config mirror, not used for validation)
- `backend/documents/utils.py:36-55` — `validate_file()` checks `file.content_type` against the dict
- `backend/auth/utils.py:11-23` — duplicate `validate_file()` (used by signatures, separate allowlist)
- Frontend `ALLOWED_MIME` / `accept` duplicated in 3 components (UploadModal, CorrespondenceForm, CorrespondenceReplyDialog)

**Storage:** Original filename preserved via `{uuid}_{original_name}` under `STORAGE_ROOT/<short_name>/uploads/<category_id>/<directory_id>/`. No change needed.

**Preview/download:** Both endpoints use stored `mime_type` generically; no per-type logic. PowerPoint will preview inline if browser supports it, otherwise download. No code change needed — already graceful.

## Required Changes

### 1. Backend — `backend/documents/models.py`
- Add PowerPoint MIME types to `ALLOWED_MIME_TYPES` dict:
  - `application/vnd.ms-powerpoint` → `FileType.PPT` (covers .ppt, .pps)
  - `application/vnd.openxmlformats-officedocument.presentationml.presentation` → `FileType.PPT` (.pptx)
  - `application/vnd.openxmlformats-officedocument.presentationml.slideshow` → `FileType.PPT` (.ppsx)
- Add `PPT = "ppt"` to `FileType` enum (line 13-18)
- Images already present — no change needed for .jpg/.jpeg/.png

### 2. Backend — `backend/core/config.py`
- Add the same 3 PowerPoint MIME type strings to `ALLOWED_MIME_TYPES` list (lines 45-51) to keep config in sync with the model dict

### 3. Backend — `backend/documents/utils.py`
- Update `validate_file()` error message to include PowerPoint in the allowed-types list
- Add case-insensitive file-extension validation as defense-in-depth: extract extension from `file.filename`, lowercase it, reject if not in the allowed extension set. This does not weaken MIME validation; it adds a second gate.
- Allowed extension set: `.pdf`, `.docx`, `.xls`, `.xlsx`, `.ppt`, `.pps`, `.pptx`, `.ppsx`, `.jpg`, `.jpeg`, `.png`

### 4. Backend — Database migration
- New Alembic migration: `ALTER TYPE filetype ADD VALUE 'PPT'` (PostgreSQL enum cannot be removed, only added — safe, additive only)
- Migration file: `backend/migrations/versions/<rev>_add_ppt_filetype.py`

### 5. Frontend — 3 components
Update `ALLOWED_MIME` array and `accept` attribute in each:
- `dms-app/src/components/documents/UploadModal.tsx` (lines 9-17, 187)
- `dms-app/src/components/correspondence/CorrespondenceForm.tsx` (lines 31-38, 272)
- `dms-app/src/components/correspondence/CorrespondenceReplyDialog.tsx` (lines 22-29, 130)
- Add PowerPoint MIME types and extensions: `.ppt`, `.pps`, `.pptx`, `.ppsx`
- Images already present — no change needed

### 6. Tests — backend
Add to `backend/tests/test_antivirus.py` (existing upload test file):
- Upload `.pptx` → accepted (200)
- Upload `.ppt` → accepted (200)
- Upload `.pps` → accepted (200)
- Upload `.ppsx` → accepted (200)
- Upload `.jpg` → accepted (200)
- Upload `.jpeg` → accepted (200)
- Upload `.PNG` (uppercase extension) → accepted (case-insensitive)
- Upload `.PPTX` (uppercase extension) → accepted (case-insensitive)
- Upload `.txt` → rejected (422)
- Upload `.exe` → rejected (422)
- Upload `.pdf` → still accepted (regression)

### 7. Tests — frontend
No new frontend tests required; run `npm run build` and `npm run lint` to verify no type/lint errors.

## Rollout / Rollback

- Migration is additive (ADD VALUE to enum) — safe to apply, no data loss
- If issues arise: revert code changes, drop the migration version row, DB enum value remains (harmless — unused enum values don't affect anything)
- No existing file-type validation is removed or weakened

## Validation Steps

1. `alembic upgrade head` applies cleanly
2. `pytest -q` passes (excluding the 2 known baseline failures)
3. `npm run build` and `npm run lint` pass from `dms-app/`
4. Manual: upload `.pptx` via API → 200, stored with original filename, retrievable via `/view` and `/download`
5. Manual: upload `.txt` → 422

## Open Questions (decision needed)

**Add `FileType.PPT` enum value vs. map PowerPoint to existing `FileType.IMAGE`?**
- Recommendation: Add `PPT = "ppt"` to the enum. It is semantically correct and enables future per-type handling. Requires an additive enum migration.
- Alternative: Map all PowerPoint to `FileType.IMAGE` — avoids migration but mislabels presentation files.

**Add magic-number / file-signature validation?**
- Explore agent identified this as a gap (MIME type is client-supplied and spoofable).
- Recommendation: Out of scope for this task. The requirement says "do not weaken existing validation" — we are not adding new security layers, just extending the allowlist.

## Plan Location

`.kilo/plans/1795424399-alembic-no-table-versions.md` (reusing existing plan file path as instructed)
