# Prompt: Replace Memo Textarea with Production-Grade Rich Text Editor

## Role

Act as an **Expert UI/UX Designer and Senior Frontend Engineer**.

Replace the existing native HTML `<textarea>` used for Memo writing with a modern **WYSIWYG Rich Text Editor** using a mature third-party React editor library.

## Existing Implementation

Current Memo editor:

- **File:** `dms-app/src/components/memo/MemoForm.tsx`
- **Current input:** Native `<textarea>`
- **Content format:** Raw Markdown

The textarea currently supports manually entered Markdown such as:

```markdown
# Heading
**Bold**
*Italic*
- Bullet item
```

Memo display currently performs simple Markdown-to-HTML conversion in:

- `dms-app/src/pages/MemoDetailPage.tsx`

Remove this limited editing/rendering approach and replace it with a proper rich-text solution.

### Recommended Architecture

- Evaluate a production-ready editor such as **TipTap** and use it if compatible with the existing React/TypeScript application.
- Prefer an extensible editor architecture rather than implementing rich-text behavior manually.
- Do not build contentEditable formatting logic from scratch.

## Core Editor Features

### Text Formatting

- Bold
- Italic
- Underline
- Strikethrough
- Inline code
- Text color
- Highlight color
- Font family
- Font size
- Clear formatting

### Paragraph Formatting

- Paragraph
- H1–H6
- Left / Center / Right / Justify
- Indent / Outdent
- Line height

### Lists

- Bullet list
- Numbered list
- Checklist
- Nested lists

### Insert

- Hyperlinks
- Images
- Horizontal divider
- Blockquote
- Code block

### Tables

- Insert table
- Add/remove rows
- Add/remove columns
- Merge/split cells
- Cell background
- Cell alignment
- Column resizing

### Editor Utilities

- Undo / Redo
- Word count
- Character count
- Placeholder
- Read-only mode
- Keyboard shortcuts
- Auto-save callback support

## UI/UX

Create a professional editing experience similar to modern document editors.

Use:

- Sticky formatting toolbar
- Clear active formatting states
- Tooltips
- Appropriate icons
- Contextual controls where useful
- Bubble menu for selected text
- Table contextual controls
- Responsive layout
- Light/Dark mode compatibility
- Accessible keyboard/focus behavior

The editor should integrate visually with the existing DMS rather than looking like a separate application.

## Component Architecture

Keep the implementation modular.

Suggested structure:

```
components/memo/editor/
├── MemoRichTextEditor.tsx
├── EditorToolbar.tsx
├── BubbleMenu.tsx
├── TableMenu.tsx
└── editorExtensions.ts
```

Adjust the structure if the existing project conventions suggest a better location.

## Content Storage

This is a critical migration requirement.

The existing application stores Memo content as Markdown/plain text, while the new editor will produce structured rich-text content.

Before implementation:

1. Inspect the existing Memo model and API contract.
2. Determine how content is currently persisted.
3. Choose one canonical rich-text storage format supported by the selected editor, preferably sanitized HTML or editor JSON.
4. Ensure Create Memo, Edit Memo, Memo Detail, Approval Workflow, and Final Draft generation all use the same content model.

Do not maintain separate incompatible rendering implementations.

## Existing Memo Compatibility

Existing Memos containing Markdown/plain text must remain readable.

Implement a safe compatibility/migration strategy so existing records are not corrupted.

Do not destructively convert existing Memo content without verifying the migration path.

## Memo Form Integration

Replace the existing `<textarea>` in:

- `dms-app/src/components/memo/MemoForm.tsx`

with the new reusable editor.

It must work correctly for both:

### Create Memo

- The editor starts blank.

### Edit Memo

- The editor loads only the current Memo's saved content and formatting.
- State from a previously edited Memo must never leak into another Memo or a new Memo.

## Memo Rendering

Update:

- `dms-app/src/pages/MemoDetailPage.tsx`

Remove the current regex-based Markdown rendering once the new content format is adopted.

- Render the stored rich-text content safely and consistently.
- Do not render unsanitized user-generated HTML.
- Apply appropriate sanitization/XSS protection before displaying persisted HTML.

## Approval Workflow Compatibility

The editor enhancement must not break the existing Memo Approval Workflow.

Verify:

```
Create Memo
    ↓
Rich Text Content
    ↓
Save Memo
    ↓
Submit for Approval
    ↓
Approver Preview
    ↓
Approval
    ↓
Final Draft
```

Memo formatting must remain intact when:

- Viewing a Memo
- Editing a Memo
- Viewing Pending Approvals
- Reviewing Memo content as an Approver
- Generating/downloading the final approved draft

Do not modify workflow business rules as part of this task.

## Image Handling

Do not store large image data as Base64 directly inside Memo content for production use.

Where image upload is supported:

```
Editor
   ↓
Upload Image
   ↓
Existing/appropriate backend file API
   ↓
Receive file URL/reference
   ↓
Insert image into editor
```

Reuse existing file/attachment infrastructure where appropriate.

## Security

Ensure:

- Rich-text HTML is sanitized.
- Scripts cannot be embedded.
- Unsafe event handlers are removed.
- Unsafe URLs are rejected.
- Image/file uploads follow existing authentication and authorization.
- Existing RBAC and User Level restrictions remain unchanged.

## Performance

Avoid:

- Re-rendering the entire editor unnecessarily.
- Recreating the editor instance on every keystroke.
- Excessive API calls.
- Saving on every individual keystroke.

If auto-save is implemented, use an appropriate debounce strategy.

## Acceptance Criteria

- [ ] Native Memo `<textarea>` is replaced by a rich-text editor.
- [ ] Users no longer need to type Markdown syntax for formatting.
- [ ] Core formatting toolbar is functional.
- [ ] Lists, links, images, headings, alignment, and tables work correctly.
- [ ] Create Memo starts with a clean editor.
- [ ] Edit Memo correctly loads existing content.
- [ ] Editor state does not leak between Memos.
- [ ] Rich-text formatting persists after save/reload.
- [ ] Memo Detail renders the same formatting produced by the editor.
- [ ] Approvers see the correctly formatted Memo.
- [ ] Final approved draft preserves Memo formatting.
- [ ] Existing Memos remain readable.
- [ ] Rich-text content is protected against XSS.
- [ ] Light/Dark mode remains usable.
- [ ] Existing Memo workflow, attachments, signatures, RBAC, and User Level functionality remain unaffected.
- [ ] TypeScript, lint, and production build pass.

## Final Instruction

First inspect the existing Memo frontend/backend content flow and determine the safest content-storage migration strategy.

Then implement the rich-text editor end-to-end, not merely as a visual replacement for the `<textarea>`.

The editor, persisted Memo content, Memo Detail rendering, approval preview, and final draft must all use a consistent and secure rich-text representation.

Avoid unrelated refactoring.
