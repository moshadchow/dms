### Summary of this Application (document Management System)

# This DMS is a role-based internal document repository for organizing business files by category -> directory ->document, with controlled access per user and per role.

  # From a user point of view, the application is built around these main jobs:

  - Users sign in with JWT-based authentication, can view their own profile context, and can change their password.
  - On the dashboard, users see only the categories they are allowed to access. Each category shows document and
    directory counts, so the landing experience is permission-aware rather than global.

  - Inside a category, users browse a nested directory tree and open a document workspace for a selected folder.
  - Documents can be searched by name and filtered by file type such as PDF, DOCX, Excel, or image.
  - Depending on permissions, users can upload documents, preview them in the browser, download them, edit metadata,
    archive them, restore archived items, or soft-delete them.

  - The viewer supports a stronger review workflow than a basic file browser: users can create private annotated
    copies of documents. For PDFs they can place point notes, and for DOCX files they can attach notes to selected
    text. Those annotations are saved as a private variant owned by that user, not a shared edit to the original file.

  - Admins get a dedicated admin panel to manage users, roles, permissions, and category-level access assignments.

  # The access model is a major part of the product. It combines:

  - Role permissions:
    Admin, Maker, Checker, Auditor

  - Action permissions:
    view, download, create, update, delete

  - Category-wise access:
    admins can explicitly choose which categories each user is allowed to see

  In practical terms, that means this app is not just for storing files. It is meant for controlled document
  operations in teams where different people create, review, audit, and manage documents with limited visibility.

  # A concise user-centric summary would be:

  This Document Management System helps organizations store, organize, search, review, and control access to
  documents. Users browse only the categories and folders they are permitted to see, preview and download files, and
  in some roles upload or maintain them. Review-oriented users can keep private annotated versions of documents for
  checking or audit work. Administrators manage users, role-based permissions, and category-specific visibility,
  making the system suitable for structured internal document governance rather than simple file sharing.