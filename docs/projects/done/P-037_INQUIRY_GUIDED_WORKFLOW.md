# P-037: Geführter Anfragen-Workflow (Guided Inquiry Flow)

**Status**: DONE (Ph-1/2/3 abgeschlossen; Ph-4 DB-Modell optional/zurückgestellt)
**Abgeschlossen**: April 2026

## Ziel

Den Anfragen-Funnel von `/inquiries/` zu einer geführten Arbeitsumgebung ausbauen:
kontextgebundene E-Mail-Vorlagen, Micro-Guides für entscheidende Kontaktmomente
(z. B. Erstgespräch) und strukturierte Erfassung aus dem Erstkontakt.

Keine neue Hauptstruktur — alles ist Erweiterung des bestehenden `ClientInquiry`-Moduls
(P-031, P-034).

---

## Ideen-Cluster

### 1. Kontextgebundene E-Mail-Vorlagen (Contextual Copy-Paste Templates)

**Problem**: Um eine Anfrage weiterzubewegen (Erstgespräch vereinbaren, ablehnen,
auf Warteliste setzen …) verlässt man die App und bastelt die E-Mail aus dem Kopf.

**Idee**: Beim Öffnen oder Bearbeiten einer Anfrage — oder beim Klick auf
einen Status-Wechsel — gibt es einen Panel/Abschnitt „Vorlage für diesen Schritt"
mit dem passenden Text zum Kopieren.

Passende Vorlagen je Stage:
| Aktueller Status | Vorlage |
|---|---|
| `new` | Eingangsbestätigung (kurz, max. 2 Sätze) |
| `contacted` | Terminvorschlag Erstgespräch |
| `intro_meeting` | Aufnahme oder Warteliste-Nachricht |
| `waitlist` | Warteliste-Update / Platz frei |
| `in_intake` | Aufnahmebogen-Link / Vertrag-Hinweis |
| `declined` / `not_suitable` | Freundliche Absage mit Alternativen |
| `unreachable` | Abschlussmail nach mehrfach kein Kontakt |

**Umsetzungsoptionen** (Entscheidung offen):
- Option A: Kleines Drawer/Off-canvas auf `InquiryUpdateView` — zeigt Vorlage für
  aktuellen Stage, Copy-to-clipboard Button. Keine DB-Kosten.
- Option B: Integration in den bestehenden Textbaustein-Bereich (`/tools/boilerplate/`),
  aber dort mit Stage-Filter/Tag, damit man sie direkt drills. Einfacher zu pflegen.
- Option C: Kombiniert — Textbausteine (P-033) erweitern um `inquiry_stage`-Tag;
  auf der Anfrage-Seite werden passende Bausteine per HTMX eingeblendet.

Option C erscheint am elegantesten — keine Duplizierung mit P-033.

---

### 2. In-Situ-Guides für Schlüssel-Momente (Micro-Guides / Checklisten)

**Problem**: Für Kontakt-Momente wie das Erstgespräch gibt es klare Leitfäden
(Reihenfolge, Zeitplan, Formulierungen) — aber die sind nicht in der App, sondern
auf Papier oder im Kopf.

**Idee**: An der richtigen Stelle eine aufklappbare „Erinnerungskarte" einblenden —
kein Feature-Bloat, nur ein diskretes ? oder 📋-Icon das einen Guide öffnet.

Konkretes Beispiel — Erstgespräch-Leitfaden (Status `intro_meeting`):

| Zeit | Schritt | Hinweis |
|---|---|---|
| ~1 min | Ankommen | Honorar nennen, Kanal-Frage — bevor sich die Person emotional einlässt |
| ~5 min | Lebenssituation & Ressourcen | Beschäftigung, soziales Umfeld, erste Einschätzung Regulationsfähigkeit |
| ~5 min | Anliegen & Veränderungsziel | Vorige Therapieerfahrung, Erwartungen |
| ~2 min | Akute Lage | Ein Satz — Krisen, Psychiatrie, Medikation; nicht wie ein Formular |
| ~4 min | Ansatz erklären | SE, körperorientiert; bei Neueinsteigern Fremdartigkeit normalisieren |
| ~2 min | Abschluss & nächster Schritt | Nächste Handlung klar benennen, keine offene Unklarheit über Kontaktweg |
| Σ ~19 min + 1 Puffer | | |

**Umsetzungsoptionen**:
- Option A: Statisches Markdown in der App (hard-coded Template-Snippet), aufklappbar
  via `<details><summary>` — kein Modell nötig.
- Option B: Neues `PracticeGuide`-Modell (Titel, Stage, Markdown-Body) —
  in Practice-Settings pflegbar. Mehr Aufwand, aber flexibel.
- Option C: Guide als Upload-Funktion — eigene Datei (PDF / Markdown) hochladen und
  pro Stage verknüpfen. Noch mehr Aufwand, eventuell Overkill.

Option A ist der pragmatische Start. Option B wäre die nächste Ausbaustufe wenn
sich mehrere Guides ansammeln.

---

### 3. Notizen aus dem Erstkontakt strukturiert erfassen

**Problem**: Die E-Mail-Anfrage enthält oft relevante Infos (Hauptthema, bisherige
Therapieerfahrung, Verfügbarkeit), die aktuell nirgendwo landen ausser im Freitext-`notes`.

**Idee**: Optionale Semi-strukturierende Felder auf `ClientInquiry` für den Erstkontakt:

| Feld | Typ | Zweck |
|---|---|---|
| `initial_topic` | TextField (kurz) | Hauptanliegen aus erster E-Mail (1–2 Sätze) |
| `prior_therapy` | BooleanField / charfield | Vorige Therapieerfahrung: ja / nein / unklar |
| `availability_notes` | TextField (kurz) | Präferenzen Uhrzeit / Wochentag |
| `referral_person` | CharField | Name der verweisenden Person (wenn Source = `referral`) |

Alternativ: Kein eigenes Modell — stattdessen ein Freitext-Block `initial_contact_notes`
plus ein visuell strukturiertes Template (Abschnitte per `<fieldset>`) das die relevanten
Gesprächspunkte vorgibt aber nicht erzwingt.

**Offene Frage**: Wie viel Struktur ist hilfreich vs. zu viel Aufwand beim Ausfüllen?
Erst mal ein strukturiertes Freitext-Feld ausprobieren, dann ggf. aufteilen.

---

## Abhängigkeiten

- P-031 (ClientInquiry-Modell) — Basis, DONE ✅
- P-034 (Analytics + Milestone-Dates) — liefert Stage-Logik, DONE ✅
- P-033 (Textbausteine) — bei Option C für Cluster 1 relevant, DONE ✅

---

## Phasen-Vorschlag

| Phase | Inhalt | Aufwand |
|---|---|---|
| Ph-1 | `initial_contact_notes`-Feld auf `ClientInquiry` + Formular-Integration | ~1h |
| Ph-2 | Erstgespräch-Leitfaden als aufklappbarer Guide bei Status `intro_meeting` | ~2h |
| Ph-3 | Textbausteine (P-033) mit Stage-Tags + Einblendung auf Anfrage-Seite (Option C) | ~3–4h |
| Ph-4 | (Optional) `PracticeGuide`-Modell für pflegbare Guides | ~3h |
