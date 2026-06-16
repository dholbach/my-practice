# P-003: Workflow-Driven Dashboard Redesign

**Status**: ✅ COMPLETED (2. Februar 2026)
**Priority**: HIGH
**Effort**: ~10h (5 Phases)
**Completed**: 2. Februar 2026

## Summary

Successfully implemented one-page workflow dashboard with 4 actionable widgets, reducing navigation from 4 pages to 1 page. Added session time tracking, combined sessions + todos in chronological timeline, and centralized widget styling.

## Implementation Results

### Phase 1: Data Foundation (Commit c01774d)
- ✅ Added `session_time` field to InvoiceItem (TIME type)
- ✅ Updated Google Calendar import to preserve time
- ✅ Modified admin + forms to support time input

### Phase 2: AgendaWidget (Commit aba6789)
- ✅ Combined InvoiceItems + PracticeTodos in chronological timeline
- ✅ Smart badges: "X Sitzungen, Y TODOs" with collapsible state
- ✅ Session/TODO rendering with icons and client codes

### Phase 3: Widget System (Commit cba21d1)
- ✅ Created widget_base.html with collapse/expand functionality
- ✅ Implemented widgets.js with LocalStorage persistence
- ✅ Added data-widget-id attributes for state management

### Phase 4: Additional Widgets (Commit 00fa726)
- ✅ Session Import Widget (Google Calendar badge + quick import)
- ✅ Client Attention Widget (follow-up, pause, ending tags + no-next-session alerts)
- ✅ Invoice Actions Widget (unpaid, overdue, draft invoices)

### Phase 5: Bug Fixes + Style Centralization (Commit 2f0e3e1)
- ✅ Fixed NoReverseMatch: calendar_auth → calendar_authorize
- ✅ Fixed FieldError: ClientTag is global (no practice field)
- ✅ Created widgets.css (280 lines) with unified classes
- ✅ Fixed dark-on-dark text: var(--bg-secondary) → var(--card-bg) + borders
- ✅ Terminology: "Sessionen" → "Sitzungen" (4 files)

### Phase 6: Performance + Query Optimization (Commit 7793f4d, ongoing)
- ✅ Fixed calculate_total() method name error
- ✅ Added prefetch_related("tags") to client attention queries
- ✅ Verified select_related("client") on all invoice queries

## Impact

- **Navigation**: 4 pages → 1 page dashboard
- **Workflow**: Real-time session agenda with time-based sorting
- **Actionability**: Widgets for import, client attention, invoice management
- **Performance**: Optimized queries with select_related/prefetch_related
- **Theme**: Improved dark theme compatibility with consistent styling

---

## Original Planning Document

## Problem

Daten über 4 Seiten verteilt, viel Navigation nötig:
- **Dashboard**: Basic stats, recent items
- **Analytics**: Revenue breakdown, client analysis
- **Client List**: Client overview, tags
- **Invoice List**: Unbezahlte Rechnungen, overdue alerts

**Pain Points**:
- Keine zentrale Workflow-Ansicht (was muss ich heute tun?)
- Sessions sind in Google Calendar, nicht im System sichtbar
- TODOs isoliert, nicht im täglichen Kontext
- Viele Klicks um von "heutigen Sessions" zu "unbezahlte Rechnungen" zu kommen

## Ziel

**One-Page Workflow Dashboard** mit kollabierenden Widgets:
- Zeigt alle wichtigen Workflows auf einer Seite
- Agenda View (Tag/Woche) mit Sessions + Tasks kombiniert
- Actionable Widgets (Quick-Import, Batch-Actions)
- Reduktion von Navigation (4 Seiten → 1 Seite)

## Central Workflow Insight

**User's primary tool**: Google Calendar
- Used on phone, across devices
- Clients request changes via email → Calendar update
- Combines work + personal calendars

**Implication**:
- Calendar remains source of truth for scheduling
- System should **import + display** session times (not replace calendar)
- Dashboard Agenda View = Sessions (from Calendar) + Tasks (from DB)

## Workflow Stages (Priority Order)

### 1. **Today's Agenda** (NEW - highest value)
Kombinierte Ansicht: Sessions + Tasks für heute/diese Woche

**Data Sources**:
- Sessions from InvoiceItems (with time!)
- Tasks from PracticeTodo (with due_date)

**Features**:
- Timeline view (09:00 Session, 14:00 Task, etc.)
- Quick actions: "Mark done", "Reschedule", "Create invoice"
- Weekly toggle: Today | This Week
- Total hours/sessions counter

**Technical Requirement**:
- [ ] Add `session_time` field to InvoiceItem (or session_datetime)
- [ ] Import time from Google Calendar events (currently discarded)
- [ ] Join InvoiceItems + PracticeTodos sorted by date+time

### 2. **Session Import**
Quick-import recent calendar events

**Current State**: Separate page (calendar_import.html)
**Proposed**: Collapsible widget on dashboard

**Features**:
- Badge with unimported event count (last 30 days)
- One-click "Import All" button
- Expand to see preview (approval UI)

### 3. **Client Attention**
Clients needing follow-up or action

**Signals**:
- Clients with tags (requires_attention, follow_up)
- Clients without next scheduled session (no future InvoiceItem)
- Clients overdue for invoice (last session >30 days ago, no invoice)

**Features**:
- Card-based layout (name, last session, action needed)
- Quick actions: "Schedule session", "Send email", "Update tags"

### 4. **Invoice Actions**
Unbezahlte Rechnungen und Overdue Alerts

**Current State**: Scattered across invoice_list + analytics
**Proposed**: Collapsible widget with batch actions

**Features**:
- List of unpaid invoices (sorted by due date)
- Overdue alerts (red badge)
- Batch actions: "Send all overdue", "Mark paid", "Send reminder"
- Quick stats: "3 unbezahlt (2680 €), 1 überfällig"

### 5. **Financial Snapshot**
Recent expenses/withdrawals, running tax total

**Current State**: Separate lists, no dashboard visibility
**Proposed**: Compact widget with totals

**Features**:
- Last 5 expenses/withdrawals (quick glance)
- YTD running totals: Revenue, Expenses, Tax-deductible
- Link to full analytics

### 6. **Capacity Planning** (Optional)
Time-off widget, workload distribution

**Features**:
- Next vacation/time-off (from TimeOff model)
- Sessions per week trend (burnout warning?)
- Available capacity (hours/week target vs. actual)

## Technical Requirements

### Database Schema Changes

**Option A: Extend InvoiceItem (Recommended)**
```python
class InvoiceItem(models.Model):
    # Existing fields
    session_date = models.DateField(...)

    # NEW: Add time component
    session_time = models.TimeField(
        null=True,
        blank=True,
        verbose_name="Uhrzeit",
        help_text="Session start time (imported from Google Calendar)"
    )

    # Or combine into DateTimeField:
    # session_datetime = models.DateTimeField(...)
    # Migration: Populate from session_date + default time (e.g., 09:00)
```

**Pros**:
- Minimal schema changes
- Leverages existing invoice workflow
- Works with current Google Calendar import

**Cons**:
- InvoiceItem tied to invoicing (not all sessions invoiced immediately)
- Historical items won't have time (migration challenge)

**Option B: Separate SessionSchedule Model**
```python
class SessionSchedule(models.Model):
    """Scheduled therapy sessions (from Google Calendar)"""
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    session_datetime = models.DateTimeField(verbose_name="Termin")
    duration = models.IntegerField(default=60, verbose_name="Dauer (Min)")
    calendar_event_id = models.CharField(max_length=200, unique=True)
    is_completed = models.BooleanField(default=False)
    invoice_item = models.OneToOneField(
        InvoiceItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Link to invoice item if session has been invoiced"
    )
    created_at = models.DateTimeField(auto_now_add=True)
```

**Pros**:
- Clear separation: Scheduling vs. Invoicing
- Can import future sessions (not yet invoiced)
- Better for agenda view (shows upcoming sessions)

**Cons**:
- More complex schema
- Two sources of truth (SessionSchedule vs. InvoiceItem)
- Requires syncing logic

**Recommendation**: **Option A** (extend InvoiceItem with session_time)
- Simpler migration path
- Most sessions are invoiced anyway
- Can populate time retroactively from calendar if needed

### Google Calendar Import Changes

**Current Behavior** (calendar_views.py):
```python
# Parses datetime but only stores date
start_dt = cls.parse_datetime(start_str)  # datetime object
# ...
InvoiceItem.objects.create(
    session_date=parsed_event["start"].date(),  # Loses time!
    # ...
)
```

**Proposed Change**:
```python
# Store both date and time
start_dt = cls.parse_datetime(start_str)  # datetime object
InvoiceItem.objects.create(
    session_date=start_dt.date(),
    session_time=start_dt.time(),  # NEW
    # ...
)
```

### Dashboard View Architecture

**Widget System** (inspired by customizable dashboards):
```python
# Abstract base class for widgets
class DashboardWidget:
    title: str
    template: str
    is_collapsible: bool
    default_collapsed: bool

    def get_context(self, request) -> dict:
        """Build widget-specific context"""
        raise NotImplementedError

# Concrete widgets
class AgendaWidget(DashboardWidget):
    def get_context(self, request):
        today = date.today()
        sessions = InvoiceItem.objects.filter(
            session_date=today,
            invoice__practice=request.current_practice
        ).select_related('invoice__client', 'service_type')

        todos = PracticeTodo.objects.filter(
            due_date=today,
            practice=request.current_practice,
            is_completed=False
        )

        # Combine and sort by time
        agenda_items = sorted(
            list(sessions) + list(todos),
            key=lambda x: getattr(x, 'session_time', None) or getattr(x, 'due_time', time(0, 0))
        )

        return {'agenda_items': agenda_items, 'date': today}
```

**Dashboard View**:
```python
def dashboard(request):
    widgets = [
        AgendaWidget(),
        SessionImportWidget(),
        ClientAttentionWidget(),
        InvoiceActionsWidget(),
        FinancialSnapshotWidget(),
    ]

    context = {
        'widgets': [
            {
                'title': w.title,
                'content': render_to_string(w.template, w.get_context(request)),
                'is_collapsible': w.is_collapsible,
                'default_collapsed': w.default_collapsed,
            }
            for w in widgets
        ]
    }
    return render(request, 'my_practice/dashboard_workflow.html', context)
```

### UI/UX Design

**Layout**: Single-column with collapsible cards
```
┌─────────────────────────────────────────┐
│ 📅 Heute - 2. Februar 2026         ▼   │ ← Always expanded
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│ 09:00-10:00  📍 Session: Marie K.      │
│ 11:30-13:00  📍 Session: Thomas B.     │
│ 14:00        ✅ Rechnung versenden      │
│ 15:00-16:00  📍 Session: Laura S.      │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│ 3 Sessions · 1 Aufgabe · 4.5h         │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ 📥 Kalender Import (3 neue)        ▶   │ ← Collapsed by default
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ ⚠️  Klienten mit Aufmerksamkeit (2) ▶  │ ← Collapsed
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ 💰 Rechnungen (3 unbezahlt)        ▼   │ ← Expanded
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│ RE-2026-001  Marie K.   680€  📧 Sent  │
│ RE-2026-002  Thomas B. 1300€  ⚠️ Fällig│
│ RE-2026-003  Laura S.   680€  📧 Sent  │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│ [Alle überfälligen versenden]         │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ 📊 Finanzen (Januar 2026)          ▶   │ ← Collapsed
└─────────────────────────────────────────┘
```

**State Management**: LocalStorage for collapsed/expanded state
```javascript
// Save user preference
localStorage.setItem('dashboard-widget-agenda', 'expanded');

// Restore on page load
document.querySelectorAll('.widget').forEach(widget => {
    const state = localStorage.getItem(`dashboard-widget-${widget.id}`);
    if (state === 'collapsed') widget.classList.add('collapsed');
});
```

**Optional: Drag & Drop Reordering**
- Use Sortable.js for widget reordering
- Store order in UserPreference model
- Low priority (Phase 2)

## Implementation Phases

### Phase 1: Data Foundation (2-3h)
- [ ] Add `session_time` field to InvoiceItem model
- [ ] Create migration (default time = 09:00 for existing items)
- [ ] Update Google Calendar import to store time
- [ ] Test import with time preservation

### Phase 2: Agenda Widget (2-3h)
- [ ] Create AgendaWidget class
- [ ] Build agenda_widget.html template
- [ ] Implement combined Sessions + Tasks query
- [ ] Add timeline rendering logic
- [ ] Quick actions: "Mark done", "View invoice"

### Phase 3: Dashboard Integration (2-3h)
- [ ] Refactor dashboard view to widget system
- [ ] Create collapsible widget base template
- [ ] Add expand/collapse JavaScript
- [ ] LocalStorage state persistence
- [ ] Migrate existing dashboard cards to widgets

### Phase 4: Additional Widgets (2-3h)
- [ ] Session Import Widget (badge + quick import)
- [ ] Client Attention Widget (tags + no-next-session)
- [ ] Invoice Actions Widget (unbezahlt + batch actions)
- [ ] Financial Snapshot Widget (compact stats)

### Phase 5: Polish & Testing (1-2h)
- [ ] Mobile responsive design
- [ ] Loading states (async widget loading?)
- [ ] Error handling (missing time, etc.)
- [ ] Performance optimization (N+1 queries)
- [ ] User acceptance testing

## Benefits

**Time Savings**:
- ✅ Reduce navigation: 4 pages → 1 page
- ✅ One-glance overview of daily work
- ✅ Quick actions without page reload

**Workflow Improvements**:
- ✅ See today's sessions + tasks in context
- ✅ Prioritize work based on time (agenda view)
- ✅ Batch operations (send all overdue invoices)

**Better Integration**:
- ✅ Google Calendar → System (agenda view)
- ✅ Sessions → Invoices → Payments (full lifecycle)
- ✅ Tasks integrated with daily schedule

## Risks & Mitigations

**Risk 1: Session time missing for old items**
- Mitigation: Default to 09:00 in migration
- Show "Time unknown" in agenda view
- Optionally: Batch-update from calendar history

**Risk 2: Widget complexity (performance)**
- Mitigation: Eager loading (select_related, prefetch_related)
- Async widget loading (HTMX?)
- Cache heavy queries (5-minute TTL)

**Risk 3: User overwhelm (too much info)**
- Mitigation: Collapsed by default (except Agenda)
- Configurable widget visibility
- Progressive disclosure (show more/less)

## Success Metrics

- Dashboard load time < 500ms
- All workflows accessible from one page
- Reduction in navigation clicks (measure with analytics)
- User feedback: "I can see my day at a glance"

## Related Projects

- **P-097**: Google Calendar Integration (completed, provides data source)
- **P-009**: Client Documentation (could add "Session notes" quick link in agenda)

## References

- Root: [PROJECTS.md](../../../PROJECTS.md#p-003-workflow-driven-dashboard-redesign)
- Google Calendar Import: [docs/guides/EMAIL_IMPLEMENTATION.md](../../guides/EMAIL_IMPLEMENTATION.md)
- PracticeTodo Model: [app/my_practice/models/todo.py](../../../app/my_practice/models/todo.py)

## Status

**⚠️ CONCEPT PHASE**

Next steps:
1. Review wireframe with user
2. Decide on Option A vs. B (extend InvoiceItem or new model)
3. Prototype Agenda Widget (proof of concept)
4. Validate time import from Google Calendar

**Blocker**: Requires decision on `session_time` field addition
