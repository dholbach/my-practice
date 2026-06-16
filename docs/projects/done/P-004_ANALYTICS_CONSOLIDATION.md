# P-004: Analytics Konsolidierung

**Status**: ✅ DONE
**Completed**: 15. Februar 2026
**Priority**: MEDIUM
**Effort**: ~7h

---

## Problem

Analytics-Informationen waren über 2 separate Seiten verteilt:
- **analytics.html**: Revenue trends, expense charts, profit analysis
- **practice_analysis.html**: Client classification, capacity metrics, insights

Das führte zu:
- Dropdown-Navigation mit 2 separaten Links
- Inkonsistente Time-Filter zwischen beiden Seiten
- Unnötige Clicks zum Vergleich von Daten

---

## Ziel

Unified Analytics-Seite mit Tab-System:
- **Revenue Tab**: Umsatz-Trends, Gewinn-Analyse, Year-over-Year
- **Clients Tab**: Top Clients, Client Classification Table
- **Capacity Tab**: Kapazitätsauslastung, Practice Metrics, Trends
- **Expenses Tab**: Ausgaben-Trends, Kategorie-Verteilung, TimeOff

**Benefits**:
- Ein Link statt Dropdown (Navigation vereinfacht)
- Konsistente Time-Filter über alle Tabs
- Bessere Info-Gruppierung (related content zusammen)
- 4 Tabs → 1 Seite (weniger Navigation)

---

## Implementation

### Phase 1: View Kombinieren ✅
**Datei**: `app/my_practice/views/analytics_views.py`

```python
def analytics_dashboard(request):
    """Unified analytics dashboard with revenue, clients, capacity, and expenses.

    P-004: Consolidated analytics + practice_analysis into tab-based view.
    """
    # Build analytics context (revenue, profit, trends)
    builder = AnalyticsDashboardBuilder(request, period, custom_start, custom_end)
    context = builder.build_context()
    context["active_tab"] = request.GET.get("tab", "revenue")

    # Build practice analysis context (clients, capacity)
    if start_date and end_date:
        analyzer = PracticeAnalyzer(start_date, end_date)
        analysis = analyzer.analyze_with_insights()
        trends = calculate_quarter_trends(end_date)
        context.update({
            "practice_analysis": analysis,
            "practice_trends": trends,
        })

    return render(request, "my_practice/analytics.html", context)
```

**Backwards Compatibility**:
```python
def practice_analysis_redirect(request):
    """Redirect from old practice_analysis URL to unified analytics with capacity tab."""
    query_string = request.META.get('QUERY_STRING', '')
    redirect_url = f"/analytics/?tab=capacity"
    if query_string:
        redirect_url += f"&{query_string}"
    return redirect(redirect_url)
```

### Phase 2: Tab-System Template ✅
**Datei**: `app/templates/my_practice/analytics.html`

**Struktur**:
1. **Time Period Filter** (oben, gilt für alle Tabs)
   - Dropdown: Alle Jahre / Letztes Jahr / Letztes Quartal / Letzter Monat / Benutzerdefiniert
   - Hidden input: `<input name="tab" value="{{ active_tab }}">` (bewahrt Tab bei Filter-Änderung)

2. **Tab Navigation**
   ```html
   <div class="tabs-nav">
       <button class="tab-button" onclick="switchTab('revenue')">💰 Umsatz</button>
       <button class="tab-button" onclick="switchTab('clients')">👥 Klienten</button>
       <button class="tab-button" onclick="switchTab('capacity')">📊 Kapazität</button>
       <button class="tab-button" onclick="switchTab('expenses')">💸 Ausgaben</button>
   </div>
   ```

3. **Tab Content Panels** (nur aktiver Tab sichtbar)
   - `<div id="revenue-tab" class="tab-content {% if active_tab == 'revenue' %}active{% endif %}">`
   - `<div id="clients-tab" class="tab-content ...>`
   - `<div id="capacity-tab" class="tab-content ...>`
   - `<div id="expenses-tab" class="tab-content ...>`

**JavaScript**:
```javascript
function switchTab(tabName) {
    // Update URL with tab parameter (preserves tab on reload)
    const url = new URL(window.location);
    url.searchParams.set('tab', tabName);
    window.history.pushState({}, '', url);

    // Show/hide tabs
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    document.getElementById(tabName + '-tab').classList.add('active');

    // Update hidden input in filter form
    document.querySelector('input[name="tab"]').value = tabName;
}
```

**Styling**:
```css
.tab-button {
    padding: 1rem 1.5rem;
    border-bottom: 3px solid transparent;
}
.tab-button.active {
    color: var(--primary-color);
    border-bottom-color: var(--primary-color);
}
.tab-content {
    display: none;
}
.tab-content.active {
    display: block;
}
```

### Phase 3: Content-Reorganisation ✅

**Revenue Tab**:
- Profit Analysis Table (Einnahmen - Ausgaben - Entnahmen)
- Revenue vs Expenses vs Withdrawals (Grouped Bar Chart)
- Revenue Trends (Line Chart)
- Link: "Detaillierter Umsatz-Report"

**Clients Tab**:
- Top 10 Clients Table (Rang, Code, Rechnungen, Stunden, Umsatz)
- Client Classification Table (aus practice_analysis)
  - Columns: Code, Name, Status (Badge), Sitzungen (Zeitraum), Gesamt-Sitzungen, Typ, Rechnungen
  - Toggle: "Ruhende Klienten anzeigen"
- Session Type Distribution (Pie-Chart-Ersatz)

**Capacity Tab**:
- Insights Section (💡 Wichtige Erkenntnisse)
- Key Metrics (4 Cards: Aktive Klienten, Gebuchte Sitzungen, Kapazität %, Freie Tage)
- Capacity Analysis (Verfügbare Stunden, Gebuchte Stunden, Freie Kapazität, Arbeitstage)
- 4-Quarter Trends Table
- TimeOff Overview (List)
- Capacity Utilization Trends (Line Chart)

**Expenses Tab**:
- TimeOff Statistics (3 Cards: Tage gesamt, Wochen, Arbeitstage)
- Expense Category Distribution (List mit Amounts)
- Busiest Months (Bar-Chart)
- Yearly TimeOff Breakdown (Table)
- Expense Trends (Bar Chart)
- Links: "Ausgaben verwalten", "Entnahmen verwalten"

### Phase 4: Navigation Vereinfachen ✅
**Datei**: `app/templates/base.html`

**Vorher**:
```html
<div class="dropdown">
    <span>📊 Analysen ▾</span>
    <div class="dropdown-content">
        <a href="{% url 'practice_analysis' %}">🏯 Praxisanalyse</a>
        <a href="{% url 'analytics' %}">📈 Auswertungen</a>
    </div>
</div>
```

**Nachher**:
```html
<a href="{% url 'analytics' %}" {% if request.resolver_match.url_name == 'analytics' %}class="active"{% endif %}>
    📊 Analysen
</a>
```

**Effekt**: 2 Links → 1 Link, kein Dropdown mehr

### Phase 5: Backwards Compatibility ✅
**Datei**: `app/my_practice/urls.py`

```python
path("analytics/", views.analytics_dashboard, name="analytics"),
# P-004: practice_analysis redirect to analytics capacity tab
path("practice-analysis/", views.practice_analysis_redirect, name="practice_analysis"),
```

**Alte Links** (`/practice-analysis/?period=quarter`) werden automatisch auf
**neue URL** (`/analytics/?tab=capacity&period=quarter`) redirected.

---

## Results

**Files Changed**: 5
1. `analytics_views.py` - Views kombiniert + redirect function
2. `analytics.html` - Komplett neu mit Tab-System (1350 Zeilen)
3. `base.html` - Navigation vereinfacht (Dropdown entfernt)
4. `urls.py` - Redirect-URL hinzugefügt
5. `views/__init__.py` - Imports aktualisiert

**Backup**: `analytics_backup_20260215.html` (originales Template)

**Navigation**:
- Dropdown "📊 Analysen ▾" → Single Link "📊 Analysen"
- 2 separate Seiten → 4 Tabs auf 1 Seite

**Code Quality**:
- Tab-Switching via URL Parameter (`?tab=capacity`)
- Tab-State bleibt bei Time-Filter-Änderungen erhalten
- Backwards-compatible redirect für alte Links

---

## Impact

**User Experience**:
- ✅ Weniger Navigation (ein Link statt Dropdown)
- ✅ Konsistente Time-Filter über alle Analytics-Bereiche
- ✅ Related Content zusammen (z.B. Client Stats + Client Table im gleichen Tab)
- ✅ Klare Struktur (Revenue / Clients / Capacity / Expenses)

**Maintainability**:
- ✅ Beide Views in einem File (analytics_views.py)
- ✅ Single Template statt zwei (analytics.html)
- ✅ Backwards-compatible (alte Links funktionieren)
- ✅ Tab-System leicht erweiterbar (z.B. neuer "Forecasting" Tab)

---

## Future Enhancements

**P-013: Workflow-Orientierte Ansichten** (Q2-Q3 2026)
- Tab-System als Basis für workflow-basierte Dashboards nutzen
- Monatlicher Rechnungs-Workflow
- Quartalsweise Steuer-Workflow
- Kapazitäts-Monitoring mit Warnings

**Potential Additional Tabs**:
- **Forecasting Tab**: Revenue predictions, client retention, seasonal trends
- **Comparison Tab**: Year-over-year detailed comparisons
- **Export Tab**: Unified export for all analytics data

---

## Commits

- [TBD] P-004: Analytics konsolidiert (View + Template + Navigation)

---

## References

- Original Issue: P-004 in [PROJECTS.md](../../../PROJECTS.md)
- Related: P-003 (Workflow Dashboard) - bereits partial tab-system
- Related: P-013 (Workflow-Orientierte Ansichten) - nächster Schritt
- User Feedback (15. Feb 2026): Workflow-orientierung gewünscht
