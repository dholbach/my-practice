# Multi-Practice Architecture Plan

**Status**: Planning Phase
**Target**: Q2 2026
**Purpose**: Support multiple business lines (Therapy + Coaching) in single system

---

## 🎯 Goal

Enable management of multiple separate businesses (Therapy Practice + Coaching Business) with:
- Separate clients, invoices, expenses, withdrawals
- Individual logos, bank details, email templates
- Practice-specific settings and service types
- Combined overview dashboard
- Easy switching between practices

---

## 📊 Current State

**Existing Infrastructure:**
- ✅ Practice Model exists (single instance assumed)
  - Logo, signature, bank details
  - Email templates (subject, body)
  - Practice-wide settings
- ❌ No practice scoping on data models
- ❌ No multi-user practice assignment
- ❌ No practice switching UI

**Assumptions to Change:**
- Currently: One user = One practice (implicit)
- Future: One user = Multiple practices (explicit)

---

## 🏗️ Architecture Design

### Option A: Practice-Scoped Data (Selected)

```
┌──────────────────────────────────────────────────┐
│                    User                          │
└────────────┬─────────────────────────────────────┘
             │
             ↓
┌──────────────────────────────────────────────────┐
│              UserPractice (M2M)                  │
│  - user_id, practice_id                          │
│  - is_owner (bool)                               │
│  - created_at                                    │
└────────────┬─────────────────────────────────────┘
             │
             ↓
┌──────────────────────────────────────────────────┐
│                  Practice                        │
│  - name (e.g., "Therapy Practice", "Coaching")  │
│  - slug (e.g., "therapy", "coaching")           │
│  - logo, signature, bank_details                │
│  - email_templates                              │
│  - is_active (bool)                             │
└────────────┬─────────────────────────────────────┘
             │
     ┌───────┴───────┬──────────────┬──────────────┐
     ↓               ↓              ↓              ↓
  Client      CompanyExpense   CompanyWithdrawal  ServiceType
  (+ practice_id FK)
     ↓
  Invoice
  (+ practice_id FK)
     ↓
  InvoiceItem
  (inherited from Invoice)
```

### Data Scoping Strategy

**Every practice-specific model gets:**
```python
practice = models.ForeignKey(
    Practice,
    on_delete=models.PROTECT,
    related_name="%(class)s_set"
)
```

**Models to scope:**
- ✅ Client
- ✅ Invoice (inherits to InvoiceItem via FK)
- ✅ CompanyExpense
- ✅ CompanyWithdrawal
- ✅ ServiceType
- ✅ GoogleCalendarToken (practice-specific calendar)
- ⚠️ ClientTag (shared across practices? or scoped?)
- ❌ Practice (top-level, no FK needed)
- ❌ User (Django built-in)

---

## 📋 Implementation Phases

### Phase 1: Data Model & Migrations (2-3 hours)

**Tasks:**
1. Create UserPractice model (Many-to-Many through table)
2. Add practice FK to all scoped models
3. Create migration with default practice
4. Backfill existing data to default practice

**Migration Strategy:**
```python
# Migration pseudocode
def forwards(apps, schema_editor):
    Practice = apps.get_model('my_practice', 'Practice')

    # Create default "Therapy Practice" if none exists
    default_practice, _ = Practice.objects.get_or_create(
        slug='therapy',
        defaults={
            'name': 'Therapy Practice',
            'is_active': True
        }
    )

    # Backfill all existing records
    Client.objects.all().update(practice=default_practice)
    Invoice.objects.all().update(practice=default_practice)
    CompanyExpense.objects.all().update(practice=default_practice)
    CompanyWithdrawal.objects.all().update(practice=default_practice)
    ServiceType.objects.all().update(practice=default_practice)
```

**Files to modify:**
- `app/my_practice/models/practice.py` - Add UserPractice model
- `app/my_practice/models/client.py` - Add practice FK
- `app/my_practice/models/invoice.py` - Add practice FK
- `app/my_practice/models/financial.py` - Add practice FK to Expense/Withdrawal
- `app/my_practice/models/service.py` - Add practice FK
- `app/my_practice/models/calendar.py` - Add practice FK to GoogleCalendarToken

**New Migration:** `0026_multi_practice_support.py`

---

### Phase 2: Practice Scoping Infrastructure (2-3 hours)

**A. Middleware for Auto-Scoping**
```python
# app/config/middleware.py
class PracticeScopeMiddleware:
    """
    Sets current practice in request based on:
    1. Session cookie ('current_practice_slug')
    2. User's default practice
    3. First available practice
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            request.current_practice = self.get_practice(request)
        else:
            request.current_practice = None

        response = self.get_response(request)
        return response

    def get_practice(self, request):
        practice_slug = request.session.get('current_practice_slug')

        if practice_slug:
            practice = Practice.objects.filter(
                slug=practice_slug,
                userpractice__user=request.user
            ).first()
            if practice:
                return practice

        # Default to first practice
        return request.user.practices.filter(is_active=True).first()
```

**B. QuerySet Managers**
```python
# app/my_practice/models/base.py
class PracticeScopedQuerySet(models.QuerySet):
    def for_practice(self, practice):
        """Filter by practice."""
        return self.filter(practice=practice)

    def for_current_practice(self, request):
        """Filter by request's current practice."""
        if hasattr(request, 'current_practice') and request.current_practice:
            return self.for_practice(request.current_practice)
        return self.none()

class PracticeScopedManager(models.Manager):
    def get_queryset(self):
        return PracticeScopedQuerySet(self.model, using=self._db)

    def for_practice(self, practice):
        return self.get_queryset().for_practice(practice)
```

**C. View Helpers**
```python
# app/my_practice/utils/practice_helpers.py
def get_current_practice(request):
    """Get current practice from request."""
    return getattr(request, 'current_practice', None)

def require_practice(view_func):
    """Decorator to ensure practice is set."""
    def wrapper(request, *args, **kwargs):
        if not hasattr(request, 'current_practice') or not request.current_practice:
            messages.error(request, "Keine Praxis ausgewählt")
            return redirect('practice_select')
        return view_func(request, *args, **kwargs)
    return wrapper
```

**Files to create:**
- `app/config/middleware.py` - PracticeScopeMiddleware
- `app/my_practice/models/base.py` - QuerySet managers
- `app/my_practice/utils/practice_helpers.py` - Helper functions

**Files to modify:**
- `app/config/settings.py` - Add middleware
- All model files - Add `objects = PracticeScopedManager()`

---

### Phase 3: UI/UX (2-3 hours)

**A. Practice Switcher in Menu**
```html
<!-- app/templates/includes/header.html -->
<div class="practice-switcher">
    <select onchange="window.location.href='{% url 'switch_practice' %}?slug=' + this.value">
        {% for practice in request.user.practices.all %}
        <option value="{{ practice.slug }}"
                {% if practice == request.current_practice %}selected{% endif %}>
            {{ practice.name }}
        </option>
        {% endfor %}
    </select>
</div>
```

**B. Visual Indicator in Header**
```html
<!-- Show current practice logo and name -->
<div class="current-practice">
    {% if request.current_practice.logo %}
    <img src="{{ request.current_practice.logo.url }}" alt="Logo">
    {% endif %}
    <span>{{ request.current_practice.name }}</span>
</div>
```

**C. Practice Management Page**
- List all practices user has access to
- Create new practice
- Edit practice settings
- Transfer ownership
- Deactivate practice

**D. Combined Dashboard**
```python
# New view: Combined Analytics
def combined_dashboard(request):
    """Show metrics across all practices."""
    practices = request.user.practices.filter(is_active=True)

    combined_metrics = {
        'total_revenue': sum(p.total_revenue for p in practices),
        'total_clients': sum(p.clients.count() for p in practices),
        'total_invoices': sum(p.invoices.count() for p in practices),
    }

    # Per-practice breakdown
    practice_breakdown = [
        {
            'practice': p,
            'revenue': p.total_revenue,
            'clients': p.clients.count(),
        }
        for p in practices
    ]

    return render(request, 'combined_dashboard.html', {
        'combined_metrics': combined_metrics,
        'practice_breakdown': practice_breakdown,
    })
```

**New Files:**
- `app/templates/my_practice/practice_select.html`
- `app/templates/my_practice/practice_management.html`
- `app/templates/my_practice/combined_dashboard.html`
- `app/static/css/practice_switcher.css`

**Modified Files:**
- `app/templates/includes/header.html`
- `app/templates/base.html`
- `app/my_practice/urls.py`

---

### Phase 4: View Updates (1-2 hours)

**Update all views to scope by practice:**
```python
# Before:
clients = Client.objects.all()

# After:
clients = Client.objects.for_current_practice(request)
```

**Views to update:**
- ClientListView, ClientDetailView
- InvoiceListView, InvoiceDetailView
- ExpenseListView, WithdrawalListView
- DashboardView, AnalyticsDashboardView
- TaxYearSummaryView
- Calendar import views

**Helper pattern:**
```python
class PracticeScopedListView(ListView):
    """Base view that auto-scopes queryset by practice."""

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.for_current_practice(self.request)
```

---

### Phase 5: Testing (1-2 hours)

**Test Coverage:**
- ✅ UserPractice model tests
- ✅ Practice scoping middleware tests
- ✅ QuerySet manager tests
- ✅ Practice switcher integration tests
- ✅ Migration tests (default practice creation)
- ✅ Combined dashboard tests

**Edge Cases:**
- User with no practices assigned
- Practice switching during form submission
- Calendar import with multiple practices
- Analytics across practice boundaries

---

## 🎨 User Experience Flow

### Initial Setup
1. User logs in → Has one default practice (migrated data)
2. Can create new practice: "Coaching Business"
3. System creates empty practice with default settings

### Daily Usage
1. **Practice Switcher** always visible in header
2. Click dropdown → Select "Coaching" or "Therapy"
3. All data instantly scoped to that practice
4. Visual indicator shows current practice

### Combined View
1. Navigate to "🏢 All Businesses" (new menu item)
2. See aggregate metrics across all practices
3. Charts show breakdown per practice
4. Can drill down to specific practice

---

## 📝 Data Migration Strategy

**Backwards Compatibility:**
- Existing single-practice systems continue working
- Migration creates "Default Practice" automatically
- All existing data assigned to default practice
- Zero downtime migration

**Multi-Practice Activation:**
- User creates second practice → Multi-practice features activate
- Practice switcher appears
- Combined dashboard becomes available

---

## 🔒 Security & Permissions

**Access Control:**
- UserPractice.is_owner flag for admin rights
- Practice-level permissions (view/edit/delete)
- No cross-practice data leakage

**Validation:**
- QuerySet always filtered by practice
- Forms validate practice ownership
- API endpoints check practice access

---

## 🚀 Rollout Plan

### Week 1: Foundation
- [ ] Phase 1: Data Model & Migrations
- [ ] Phase 2: Infrastructure (Middleware, Managers)

### Week 2: UI & Views
- [ ] Phase 3: Practice Switcher UI
- [ ] Phase 4: Update all views

### Week 3: Testing & Polish
- [ ] Phase 5: Comprehensive testing
- [ ] Documentation updates
- [ ] User acceptance testing

### Week 4: Production
- [ ] Deploy migration
- [ ] Monitor for issues
- [ ] User training/documentation

---

## 💡 Future Enhancements

**Phase 6 (Optional):**
- Practice-specific user roles (admin/accountant/viewer)
- Practice sharing (invite other users)
- Practice templates (clone settings to new practice)
- Practice archival (soft delete)
- Cross-practice reporting (consolidated tax summary)

**Phase 7 (Advanced):**
- Multi-currency support per practice
- Practice-specific branding (full white-label)
- Practice export/import (data portability)
- Practice analytics comparison

---

## 📊 Estimated Impact

**Benefits:**
- ✅ Support multiple business lines
- ✅ Clean data separation
- ✅ Flexible user management
- ✅ Scalable architecture
- ✅ Combined insights

**Costs:**
- ~8-10 hours development
- Migration complexity (low risk)
- Additional UI complexity (minimal)
- Testing overhead (manageable)

**Risk Assessment:** Low
- Backwards compatible
- Well-defined scope
- Clear migration path
- Incremental rollout possible

---

## 🔗 Related Documentation

- [FEATURES.md](../FEATURES.md) - Feature list
- [CODE_STRUCTURE.md](../architecture/CODE_STRUCTURE.md) - Architecture
- [CHANGELOG.md](../CHANGELOG.md) - Version history

---

**Next Steps:**
1. Finish Google Calendar Phase 5
2. Review and approve this plan
3. Begin Phase 1 implementation
