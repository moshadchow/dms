Gap Analysis
The remarks field already exists and is already saved — the gap is purely in the data-to-PDF pipeline:
Layer
DB model
API input
Service save
PDF data retrieval
PDF rendering
The remarks data is sitting in the database on every WorkflowAction record — it's just never read into the PDF generation pipeline.
Implementation Plan
Change 1: memos/service.py — Include remarks in approval_entries
Location: generate_final_draft(), lines 719-725
Add "remarks" to the dict appended to approval_entries:
# BEFORE (line 719-725):
approval_entries.append({
    "step_name": step_name or f"Step {action.workflow_step_id}",
    "acted_by_name": acted_by_name,
    "action": action.action.value if hasattr(action.action, 'value') else str(action.action),
    "signature_path": signature_path,
    "acted_at": acted_at,
})

# AFTER:
approval_entries.append({
    "step_name": step_name or f"Step {action.workflow_step_id}",
    "acted_by_name": acted_by_name,
    "action": action.action.value if hasattr(action.action, 'value') else str(action.action),
    "signature_path": signature_path,
    "acted_at": acted_at,
    "remarks": action.remarks,
})
That's it for the service — one line addition.
Change 2: memos/pdf_generator.py — Update docstring
Location: generate_memo_pdf() docstring, lines 487-492
Add remarks to the documented keys:
# BEFORE:
approval_entries: List[dict],  # each a dict with keys:
    # - step_name (str)
    # - acted_by_name (str)
    # - action (str)
    # - signature_path (Optional[Path])
    # - acted_at (str)

# AFTER:
approval_entries: List[dict],  # each a dict with keys:
    # - step_name (str)
    # - acted_by_name (str)
    # - action (str)
    # - signature_path (Optional[Path])
    # - acted_at (str)
    # - remarks (Optional[str])
Change 3: memos/pdf_generator.py — Render remarks after each approver's signature
Location: Lines 600-628 (the approver signature rendering loop)
After the signature image and before the Spacer, add a remarks paragraph:
# Current code (simplified):
for entry in approval_entries:
    # ... label, name, date, signature image ...
    story.append(Spacer(1, 8))

# After change:
for entry in approval_entries:
    # ... label, name, date, signature image ...
    
    # NEW: Display remarks if available
    remarks = entry.get("remarks")
    if remarks:
        story.append(Paragraph(
            f'<i>"{_sanitize_for_reportlab(remarks)}"</i>',
            styles["SignatureInfo"],
        ))
    
    story.append(Spacer(1, 8))
The SignatureInfo style (line 116-123) is already used for approver name/date — it's 8pt gray text. Using italic (<i>) with quotation marks makes the remarks visually distinct as a quoted note.
Change 4: memos/pdf_generator.py — Add remarks to the APPROVAL INFORMATION summary table
Location: Lines 630-657
This is optional but adds value. Add a "Notes" row to the summary table showing the count of approvers who provided remarks:
# After the existing summary_data rows, before creating the table:
remarks_count = sum(1 for e in approval_entries if e.get("remarks"))
if remarks_count > 0:
    summary_data.append(["Notes", f"{remarks_count} approver note(s) included"])
Summary of all edits
#	File
1	memos/service.py
2	memos/pdf_generator.py
3	memos/pdf_generator.py
4	memos/pdf_generator.py
What NOT to change
- WorkflowAction model — remarks field already exists
- approval_service.py — already saves remarks from the API payload
- WorkflowActionCreate schema — already accepts remarks
- Frontend — already sends remarks in the action payload
- No migration needed — no schema changes
Verification
- pytest — run existing tests to ensure no regressions
- Manual test: Create a memo → submit for approval → have approvers add remarks → approve → download final draft → verify remarks appear in the PDF
Edge cases handled
- No remarks provided: The if remarks: guard skips rendering empty/None remarks — no empty quotes appear
- Multiple approvers with remarks: Each entry renders its own remarks independently — no overwriting
- Return then resubmit: Each action is a separate WorkflowAction record with its own remarks — both appear in order
- Parallel workflows: Each approver's action is a separate record — all remarks preserved individually
- Special characters in remarks: _sanitize_for_reportlab() (already exists) strips malformed XML tags before rendering