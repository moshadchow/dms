# Prompt: Storage Usage Visibility in Admin Panel

## Objective

Add a **Storage Usage** section to the Admin Panel so administrators can monitor the system's storage consumption.

## Requirements

Display the following information:

- **Overall Storage Usage**
  - Total storage capacity
  - Used storage
  - Available storage
  - Usage percentage

- **Usage by Category**
  - Storage consumed by each document category
  - Usage percentage per category
  - Number of files/documents where available

- **Available Capacity**
  - Total available storage
  - Clearly indicate remaining capacity

## UI/UX

Create a clean Admin Panel dashboard/widget showing:

```text
Storage Usage
────────────────────────
Used:       65 GB
Available:  35 GB
Total:     100 GB
Usage:       65%

Usage by Category
────────────────────────
Category A    25 GB
Category B    20 GB
Category C    12 GB
Other          8 GB
```

Use suitable charts/visualizations where appropriate.

## Backend

- Calculate storage usage from the actual file/storage data.
- Do not rely on hardcoded values.
- Provide an API for the Admin Panel to retrieve storage statistics.
- Include overall usage, category-wise usage, and available capacity.
- Restrict the API to authorized administrators using the existing RBAC mechanism.

## Acceptance Criteria

- Admin can view overall storage usage.
- Admin can view total, used, and available capacity.
- Admin can view storage usage by category.
- Usage percentage is calculated correctly.
- Data reflects actual storage consumption.
- Only authorized administrators can access the information.
- Existing storage, document, and RBAC functionality remains unchanged.
