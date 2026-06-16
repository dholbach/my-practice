# P-030: Session List Collapse on Client Detail

## Ziel
Um die Ladezeit der Übersichtlichkeit und Performance willen, sollen lange Listen von `SessionLog` Einträgen auf der Klienten-Detailseite (Tab "Protokoll") standardmäßig eingeklappt werden. Nur die aktuellsten 10 Logs bleiben sichtbar.

## Steps
1. **Template Anpassung (`client_detail.html`)**:
   - Im *Protokoll* Tab: Iteriere über alle `log_entries`.
   - Wickle alle Iterationen nach dem 10. Element (`if forloop.counter > 10`) in einen Container: `<div class="old-entries collapsed">`.
   - Die Anzahl der eingeklappten Elemente wird via Template-Tags `{{ log_entries|length|add:"-10" }}` generiert und angezeigt.

2. **Styling (`client_detail.css` oder inline über Block)**:
   - CSS Regel: `.old-entries.collapsed { display: none; }`
   
3. **Interaktivität (JS)**:
   - Ein Toggle Button unterhalb der Liste:
     - Initiale Beschriftung: "Ältere Einträge anzeigen (X mehr)"
     - Beim Klicken entfernt er die `collapsed` Klasse.
     - Ändert den Text dann auf "Einklappen".
     - Beim erneuten Klicken wird die Klasse wieder hinzugefügt und der Text zurückgesetzt.
   
4. **Backend**:
   - **Keine Änderung am Backend nötig.** Es ist eine reine Rendering- und Frontend-Lösung.

## Relevante Dateien
- `app/templates/my_practice/client_detail.html`
- `app/static/css/client_detail.css` (bzw. `{% block extra_css %}`)
