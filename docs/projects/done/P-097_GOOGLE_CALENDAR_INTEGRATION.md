# Google Calendar Integration - User Guide

**Status**: ✅ Phase 1-5 Complete
**Last Updated**: 7. September 2026

---

## Overview

Imports therapy sessions from Google Calendar directly into the invoicing system. Automatically creates InvoiceItems for all scheduled sessions.

---

## Features

### ✅ Phase 1-5 Complete

**OAuth2 Integration**:
- Secure authentication with Google
- Filters on the "Praxis" calendar
- Token auto-refresh (proactive 5-min expiry check)
- API pagination (>250 events support)

**Event Parser**:
- Client matching via initials in the event title
- Cancel detection (strikethrough events)
- Colour-coded status display
- Duration-based service type mapping

**Approval UI**:
- Manual corrections (change client/service type)
- Smart auto-selection for ready events
- Duplicate detection with visual indicators
- Status badges with tooltips
- Bulk actions: "Import selected"

**InvoiceItem Creation**:
- Creates items from approved events
- Duplicate prevention (checks existing items)
- Free initial-consultation handling (0€ rate)
- First-seen date auto-tracking
- Single draft invoice per client
- Comprehensive error reporting

**Production Polish**:
- Session storage event caching (30-min cache)
- Performance optimizations
- Error handling

---

## Setup

### 1. Google Cloud Console
1. Create a project: [console.cloud.google.com](https://console.cloud.google.com)
2. Enable the API: **Google Calendar API**
3. Create an OAuth 2.0 client ID:
   - Application type: **Web application**
   - Authorized redirect URIs: `http://localhost:8000/calendar/oauth2callback/`
4. **OAuth consent screen → Audience**: fill in Branding completely (app name, support email, developer contact, homepage/privacy/ToS links pointing at an authorized domain) and click **"Publish App"** to move the app from "Testing" to "In production" — see Troubleshooting below for why this matters.

### 2. Configure Credentials
```bash
# .env file
GOOGLE_CALENDAR_CLIENT_ID=your-client-id
GOOGLE_CALENDAR_CLIENT_SECRET=your-client-secret
```

### 3. First Use
1. Open **Calendar Import** from the main menu
2. Click **"Connect with Google"**
3. Choose the Google account and grant permissions
4. Automatic redirect back to the app

---

## Workflow

### 1. Fetching Events
**Navigation**: Main menu → **Calendar Import**

**Event fetching**:
- Shows events from TODAY to +365 days
- Filters on the "Praxis" calendar
- Session caching (30 minutes)

**Status badges**:
- 🟢 **Ready**: client found, service type mapped, no duplicates
- 🟡 **Needs Attention**: client unclear or service type missing
- 🔴 **Duplicate**: already present in InvoiceItems
- ⚫ **Cancelled**: event struck through

### 2. Reviewing & Correcting Events

**Auto-matching**:
- Parser looks for initials in the event title (e.g. "AB" → "Müller, Anna (AB)")
- Duration → service type mapping:
  - 60min → "Session (60min)"
  - 90min → "Session (90min)"
  - 15min → "Check-in"
  - Default → "Session (60min)"

**Manual corrections**:
- Dropdown: choose client (if auto-match fails)
- Dropdown: change service type (if the default doesn't fit)
- Changes are saved immediately (session storage)

**Smart selection**:
- "Select Ready" button: selects all 🟢 Ready events
- Saves time on bulk import

### 3. Running the Import

**"Import Selected" button**:
- Processes all selected events
- Creates InvoiceItems for each client
- Adds items to a draft invoice (or creates a new draft)

**Duplicate prevention**:
- Checks existing InvoiceItems (same day + client)
- Shows a 🔴 Duplicate badge
- Cannot be imported (checkbox disabled)

**Success feedback**:
- Shows the number of successfully imported sessions
- Lists clients
- Link to the invoice draft

---

## Special Cases

### Initial Consultation
**Detection**: "Vorgespräch" or "Erstgespräch" in the event title

**Automatic handling**:
- Service type: "Session (60min)"
- **Rate: 0€** (free)
- First-seen date: set automatically

### Group Sessions
**Event title format**: must contain initials (e.g. "Gruppe - AB, CD, EF")

**Handling**:
- Each client gets a separate InvoiceItem
- Service type: manually chosen as "Group Session"
- Duration: as specified in the event

### Cancelled Events
**Display**: ⚫ Cancelled badge

**Handling**:
- Checkbox disabled (cannot be imported)
- Stays in the list for visibility
- Optional: manually create a "cancellation" invoice

---

## Technical Details

### Event Parser Logic
```python
# Duration → service type mapping
duration_map = {
    60: "therapy_60",     # Session (60min)
    90: "therapy_90",     # Session (90min)
    15: "check_in",       # Check-in
    120: "therapy_120",   # Session (120min)
}
```

### Client Matching
```python
# 1. Looks for initials in the event title
# 2. Matches against Client.client_code
# 3. If multiple matches: shows all for selection
```

### Duplicate Detection
```python
# Checks InvoiceItem against:
# - Same date (session_date)
# - Same client
# - ±5 minutes duration variance (allows small deviations)
```

### Token Management
- OAuth token is stored in the database (`GoogleCalendarToken`)
- Proactive refresh when <5 minutes of validity remain
- Automatic re-authentication if the token has expired — see Troubleshooting

---

## Files

### Backend
```
app/my_practice/
├── views/calendar_views.py        # OAuth + import views
├── utils/google_calendar.py       # Event parser
├── forms.py                       # CalendarImportForm
└── urls.py                        # /calendar/* routes

app/config/
└── settings.py                    # GOOGLE_CALENDAR_CLIENT_ID/SECRET
```

### Frontend
```
templates/my_practice/
└── calendar_import.html           # Import UI

static/
├── css/calendar_import.css        # Styling
└── js/calendar_import.js          # AJAX + interactions
```

### Tests
```
app/my_practice/tests/
├── test_google_calendar.py        # Event parser tests
└── test_calendar_views.py         # Integration tests
```

---

## Troubleshooting

### "Invalid Grant" Error / Token Keeps Expiring Every ~7 Days
**Cause**: Google caps refresh-token lifetime at **7 days** whenever the OAuth consent screen's publishing status is **"Testing"**. This is unconditional — setting a support/contact email on the consent screen does **not** change it, and neither does adding your account to the **Test users** list. The Test users list only controls who is allowed to complete the consent flow while unverified; it has no effect on refresh-token lifetime.

**Fix**: Google Cloud Console → APIs & Services → OAuth consent screen → **Audience**. Complete Branding fully (app name, support email, developer contact, and homepage/privacy-policy/ToS links that resolve to an authorized domain — `http://localhost` will not validate; point them at a domain you've already authorized, e.g. the GitHub repo URL), then click **"App veröffentlichen" / "Publish App"** to move the app from "Testing" to "In production". After publishing, run `./dev.py calendar-auth` once more to mint a fresh refresh token — you'll see a one-time "Google hasn't verified this app" warning to click through, since `calendar.readonly` is a sensitive (not restricted) scope and doesn't require full verification for personal/single-user use.

### "No Events Found"
**Possible causes**:
- Wrong calendar name (must be "Praxis")
- No events in the next 365 days
- Calendar not shared

**Fix**: Check Google Calendar, adjust the calendar name if needed

### Client Not Found
**Cause**: Initials missing or incorrect in the event title

**Fix**:
- Dropdown: choose the client manually
- Or: correct the event title in Google Calendar

### Duplicate Detected (False Positive)
**Cause**: ±5min variance detection too strict

**Fix**:
- Check the existing item on the invoice
- If it's really a duplicate: ignore
- If false positive: delete the existing item, re-import

---

## Best Practices

1. **Regular import**: weekly or after scheduling appointments
2. **Event title consistency**: always use initials (e.g. "AB - Therapie")
3. **Calendar name**: keep "Praxis" for automatic filtering
4. **Initial-consultation marker**: "Vorgespräch" in the title for 0€ handling
5. **Check draft invoice**: always review the draft invoice after import

---

## Future Extensions (Nice to Have)

- Bi-directional sync (app → Google Calendar)
- Automatic reminder emails
- Recurring appointment templates
- Multi-calendar support
- Automatic cancellation handling (creates a "cancellation" invoice)
