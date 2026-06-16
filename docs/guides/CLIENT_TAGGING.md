# Client Tagging System - User Guide

**Last Updated**: 2 February 2026

## Overview

The client tagging system enables flexible categorisation of clients with colour-coded tags.
Replaces external tools like Trello for client organisation.

---

## Features

### 🏷️ Manual Tags
Create tags for different purposes:
- **Process**: `missing-paperwork`, `needs-documentation`, `follow-up`
- **Status**: `end-process`, `no-fit`, `probationary-period`
- **Priority**: `urgent`, `vip`, `priority-client`

### 🤖 Automatic System Tags
- **`no-next-session`**: Automatically applied to active clients without future sessions
  - Invoice in the last 90 days (recently active)
  - NO future sessions scheduled
  - Helps with follow-up scheduling

---

## Usage

### Creating Tags
1. **Clients** → **Tags verwalten**
2. **"➕ Neues Tag erstellen"**
3. Fill in the fields:
   - **Name**: Short, descriptive (e.g. `missing-paperwork`)
   - **Farbe**: 8 colours available
   - **Beschreibung**: Optional

### Adding Tags to Clients

**Method 1: Client Detail Page**
- **"➕ Tag hinzufügen"** in the client header
- Select tag from dropdown
- Applied immediately

**Method 2: Django Admin**
- Admin → Clients → Edit
- Select tags in the "Organization" section
- Save

### Filtering by Tags
- **Client List**: Click a tag in the filter bar
- Shows only clients with that tag
- Tag count shows the number

### Removing Tags
- Client detail page: click **×** next to the tag
- Browser prompt confirms removal
- System tags cannot be removed manually

---

## Workflow-Focused Client List

### 3-Section Layout
**⚠️ Needs Attention**: Active clients with:
- Urgent tags (`no-next-session`, `missing-paperwork`, `follow-up`, `urgent`)
- >90 days since last invoice

**✅ Active & OK**: Active clients without issues

**💤 Inactive**: Inactive clients

### Card-Based Grid
- 350px min width, responsive
- Shows: name, code, tags, last invoice date, total revenue
- Hover: extended actions

---

## Automatic Tag Updates

### Run Command
```bash
./dev.py manage update_client_tags
```

### Cron Job Setup (recommended: daily)
```bash
# crontab -e
0 6 * * * cd /path/to/payments && ./dev.py manage update_client_tags
```

### How It Works
1. Checks invoices from the last 90 days (activity check)
2. Checks future session dates in InvoiceItems
3. Recently active BUT no future sessions → add tag
4. Conditions not met → remove tag

---

## Use Cases

### Active Clients
- **`missing-paperwork`**: Intake documents incomplete
- **`follow-up`**: Check-in or follow-up contact needed
- **`needs-documentation`**: Session notes or diagnosis materials outstanding
- **`no-next-session`**: (Automatic) Schedule next appointment

### Inactive Clients
- **`end-process`**: Therapy successfully completed
- **`no-fit`**: Client decided therapy is not a good fit
- **`moved-away`**: Relocation
- **`referral-out`**: Referred to another practice

Helps with tracking why clients leave the practice and identifying patterns.

---

## Technical Details

### Files
```
app/my_practice/
├── models/tag.py                  # ClientTag model
├── views/tag_views.py             # CRUD + AJAX endpoints
├── views/client_views.py          # Workflow ClientListView
├── management/commands/
│   └── update_client_tags.py      # Auto-tagging
└── urls.py                        # Routes

templates/
├── includes/client_tags.html      # Reusable component
└── my_practice/
    ├── client_list_cards.html     # Workflow view
    └── tag_*.html                 # Tag management

static/css/
└── tailwind.css                   # All styles (tag card layout lives in @layer components here)
```

### Model
```python
class ClientTag(models.Model):
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=50, unique=True)
    color = models.CharField(max_length=20, choices=COLOR_CHOICES)
    description = models.TextField(blank=True)
    is_system_tag = models.BooleanField(default=False)
```

### Management Command
```python
# Create default tags
./dev.py manage create_default_tags

# Update automatic tags
./dev.py manage update_client_tags
```

---

## Future Extensions (Not Implemented)

- **Notes system**: Client-specific notes/TODO lists
- **Task tracking**: Paperwork and follow-ups
- **Timeline view**: Client interactions
- **Session documentation import**: Session notes and diagnosis materials
