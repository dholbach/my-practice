"""
Management command to seed a demo practice with realistic fictional data.

Populates: Practice, Clients, Sessions, Invoices, ClientInquiries,
           PracticeTodos, CompanyExpenses — using characters drawn from
           Tolkien, Le Guin, and Greek mythology.

Usage:
    ./dev.py manage seed_sample_data
    ./dev.py manage seed_sample_data --clear    # drop demo data first
    ./dev.py manage seed_sample_data --seed 99  # different random run
"""

import random
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

from ...models import (
    Client,
    ClientInquiry,
    ClientNote,
    ClientTag,
    CompanyExpense,
    Invoice,
    InvoiceItem,
    PendingCalendarEvent,
    Practice,
    PracticeTodo,
    ServiceType,
    Session,
    TimeOff,
    UserPractice,
)
from ...models.clinical import ClientProfile, MoodTag, SessionLog
from ...utils.invoice_helpers import get_next_invoice_number

DEMO_SLUG = "demo"
SEED_PENDING_EVENT_PREFIX = "seed-demo-event-"

# ── Character data ────────────────────────────────────────────────────────────
# (client_code, full_name, archetype, avg_sessions_per_month, has_90min)
# archetype: hero / exile / ruler / seeker
# avg_sessions_per_month: float, used as base Poisson-ish rate
# has_90min: True → ~30% of sessions are 90 min instead of 60 min

CHARACTERS: list[tuple[str, str, str, float, bool]] = [
    # Tolkien — 15 characters
    ("FB", "Frodo Baggins", "hero", 3.0, True),
    ("SAG", "Samwise Gamgee", "hero", 2.0, False),
    ("GAL", "Galadriel", "ruler", 1.5, True),
    ("ARA", "Aragorn", "hero", 2.5, True),
    ("LEG", "Legolas", "seeker", 2.0, False),
    ("BO", "Boromir", "ruler", 1.0, False),
    ("GIM", "Gimli", "hero", 1.5, False),
    ("PEK", "Peregrin Took", "seeker", 3.0, False),
    ("MB", "Meriadoc Brandybuck", "exile", 2.0, False),
    ("FA", "Faramir", "exile", 2.5, True),
    ("EO", "Eowyn", "exile", 3.5, True),
    ("AW", "Arwen", "seeker", 1.0, True),
    ("TH", "Theoden", "ruler", 1.5, True),
    ("GL", "Glorfindel", "ruler", 1.0, True),
    ("ELR", "Elrond", "seeker", 1.0, True),
    # Le Guin — 15 characters
    ("GED", "Ged", "seeker", 2.5, True),
    ("TN", "Tenar", "exile", 3.0, True),
    ("SHV", "Shevek", "seeker", 2.0, True),
    ("GEN", "Genly Ai", "exile", 2.0, False),
    ("EST", "Estraven", "exile", 1.5, True),
    ("THR", "Therru", "seeker", 2.5, True),
    ("OIR", "Orm Irian", "seeker", 1.5, True),
    ("OGI", "Ogion", "ruler", 0.8, False),
    ("VET", "Vetch", "hero", 2.0, False),
    ("ALD", "Alder", "hero", 2.5, False),
    ("SEL", "Selver", "exile", 1.5, True),
    ("PEC", "Pechvarry", "hero", 3.0, False),
    ("HA", "Hare", "exile", 2.0, False),
    ("COB", "Cob", "ruler", 1.0, True),
    ("ORM", "Orm Embar", "hero", 1.5, False),
    # Greek mythology — 15 characters
    ("OD", "Odysseus", "hero", 2.5, True),
    ("PE", "Penelope", "exile", 2.0, True),
    ("ACH", "Achilles", "hero", 3.5, False),
    ("MED", "Medea", "ruler", 2.0, True),
    ("PRS", "Persephone", "exile", 3.0, True),
    ("HRM", "Hermes", "seeker", 1.5, False),
    ("AI", "Ariadne", "seeker", 2.5, True),
    ("DAE", "Daedalus", "seeker", 1.5, True),
    ("IC", "Icarus", "hero", 4.0, False),
    ("DEM", "Demeter", "ruler", 2.0, True),
    ("APO", "Apollo", "ruler", 1.0, True),
    ("ATH", "Athena", "seeker", 1.5, False),
    ("HEC", "Hecate", "ruler", 1.5, True),
    ("ORP", "Orpheus", "exile", 2.5, True),
    ("EUR", "Eurydice", "exile", 1.0, True),
]

# ── Session note templates per archetype ─────────────────────────────────────
NOTE_TEMPLATES: dict[str, list[str]] = {
    "hero": [
        "Klient berichtete von wiederkehrenden Träumen, in denen er eine Last trägt, "
        "die er nicht ablegen kann. Thema Verantwortung und Selbstwert. Hausaufgabe: Journaling.",
        "Thema Pflichtgefühl vs. eigene Bedürfnisse. Klient zeigte gute Reflexionsfähigkeit. "
        "Nächste Sitzung: Ressourcenarbeit.",
        "Starke Erschöpfung durch anhaltende Belastung. Psychoedukation zu Grenzen und "
        "Selbstfürsorge. Atemübung eingeführt.",
        "Klient spricht von einer Aufgabe, die er um jeden Preis erfüllen muss. Exploration "
        "der inneren Antreiber. Innerer Kritiker identifiziert.",
        "Abschluss eines Themenblocks. Klient reflektiert Fortschritte. Positive Entwicklung "
        "beim Thema Selbstmitgefühl.",
    ],
    "exile": [
        "Klientin beschreibt tiefes Gefühl der Fremdheit, auch in vertrauten Umgebungen. "
        "EMDR-Vorbereitung besprochen.",
        "Thema Heimat und Zugehörigkeit. Ambivalente Gefühle bezüglich Herkunft. "
        "Körperarbeit: Verortungsübung.",
        "Klientin exploriert die Frage 'Wer bin ich ohne diesen Kontext?'. Identitätsarbeit begonnen.",
        "Starkes Schamgefühl bezüglich Vergangenheit. Normalisierung und Reframing. "
        "Gute therapeutische Allianz.",
        "Thema Transformation und Identitätsverlust. Das Bild 'jemand anderes werden' taucht auf. "
        "Teilearbeit begonnen.",
    ],
    "ruler": [
        "Klient beschreibt Schwierigkeit, um Hilfe zu bitten. Perfektionismus und Kontrollbedürfnis "
        "als Schutzstrategien identifiziert.",
        "Einsamkeit trotz hoher sozialer Verantwortung. Klient zweifelt an Echtheit seiner "
        "Beziehungen. Bindungsarbeit.",
        "Thema Autorität und Angst vor Versagen. Klient hatte schwierige Woche. "
        "Stabilisierungsübungen wiederholt.",
        "Klient reflektiert Muster: Stärke zeigen auf Kosten der eigenen Verletzlichkeit. "
        "Guter Fortschritt.",
        "Erste Sitzung nach Krisenphase. Klient stabil. Schutzfaktoren erarbeitet.",
    ],
    "seeker": [
        "Klientin sucht Sinn in wiederkehrenden Verlusterfahrungen. Existenzielle Themen. "
        "Verweis auf Ressourcen besprochen.",
        "Thema Wandel und Angst vor dem Unbekannten. Achtsamkeitsübung eingeführt.",
        "Klientin exploriert eigene Werte. Was ist wirklich wichtig? Tiefes Gespräch "
        "über Lebensziele.",
        "Träume über Verwandlung und Neugeburt. Symbolarbeit. Klientin sehr reflektiert.",
        "Abschluss einer wichtigen Arbeitsphase. Integration von Erkenntnissen. "
        "Klientin wirkt gefestigter.",
    ],
}

# ── Session-log templates per archetype ──────────────────────────────────────
# Each tuple: (content, interventions, therapist_reflection, mood_tags, summary)
# summary = short one-liner ≤120 chars, stored unencrypted — visible in session cockpit
SESSION_LOG_TEMPLATES: dict[str, list[tuple[str, str, str, list[str], str]]] = {
    "hero": [
        (
            "Klient berichtete von Erschöpfung nach einer besonders anstrengenden Woche. "
            "Thema Verantwortung vs. eigene Erschöpfung. Wir erkundeten, was ihn antreibt "
            "und woher das Pflichtgefühl kommt. Sitzung war produktiv.",
            "Psychoedukation zu Selbstfürsorge. Ressourcenaktivierung. Atemübung.",
            "Starke Resonanz mit dem Thema Aufopferung. Gegenübertragung beachten.",
            [MoodTag.MITTEL, MoodTag.GUTE_RESSOURCEN],
            "Erschöpfung nach harter Woche – Verantwortung vs. Selbstfürsorge",
        ),
        (
            "Klient berichtete von einem Konflikt, den er nicht vermeiden konnte. "
            "Gefühl der Ohnmacht und gleichzeitig Drang zur Kontrolle. "
            "Innerer Antreiber 'Sei stark' identifiziert. Sehr offene Sitzung.",
            "Teilearbeit (Innerer Kritiker vs. Verletzliches Kind). Stuhlarbeit vorbereitet.",
            "Bewegt von der Offenheit des Klienten. Gute therapeutische Allianz spürbar.",
            [MoodTag.SCHWER, MoodTag.HOHE_AKTIVIERUNG],
            "Konflikt & Ohnmacht; innerer Antreiber 'Sei stark' erkannt",
        ),
        (
            "Klient zeigte heute deutlichen Fortschritt beim Thema Grenzen setzen. "
            "Berichtete von einer Situation, in der er erstmals Nein gesagt hat. "
            "Sitzung leicht und ermutigend.",
            "Verhaltensexperiment ausgewertet. Positives Reinforcement. Nächste Schritte geplant.",
            "Freude über den Fortschritt. Achtsam bleiben, nicht zu früh zu feiern.",
            [MoodTag.LEICHT, MoodTag.FORTSCHRITT, MoodTag.GUTE_RESSOURCEN],
            "Fortschritt: erstmals Nein gesagt, Grenzen gesetzt",
        ),
        (
            "Thema Trauma-Trigger durch äußere Ereignisse reaktiviert. Klient kam belastet. "
            "Stabilisierung zuerst. Sicherer Ort geübt. Klient konnte sich regulieren.",
            "Stabilisierung: sicherer Ort, Atemarbeit. Kein Trauma-Processing heute.",
            "Sorge um den Klienten. Supervision besprechen. Ressourcen im Blick behalten.",
            [MoodTag.SCHWER, MoodTag.HOHE_AKTIVIERUNG, MoodTag.UNSICHER],
            "Trauma-Trigger reaktiviert – Stabilisierung, sicherer Ort",
        ),
        (
            "Abschluss eines längeren Themenblocks rund um Autonomie. Klient fasst "
            "Erkenntnisse zusammen. Wir planen nächste Phase der Arbeit.",
            "Bilanzierungsgespräch. Ziele für nächste Phase formuliert.",
            "Stolz auf die Entwicklung. Beziehung hat sich vertieft.",
            [MoodTag.LEICHT, MoodTag.FORTSCHRITT, MoodTag.DURCHBRUCH],
            "Abschluss Themenblock Autonomie; nächste Phase geplant",
        ),
    ],
    "exile": [
        (
            "Klientin beschreibt anhaltendes Gefühl des Nicht-dazugehörens. "
            "Thema Heimat und innere Leere. Sitzung war tief und berührend.",
            "Körperarbeit: Verortungsübung. Ressourcenbild entwickelt.",
            "Tief berührt. Eigene Themen von Zugehörigkeit kurz hochgekommen — achtgeben.",
            [MoodTag.SCHWER, MoodTag.NIEDRIG_AFFEKTIV],
            "Thema Nicht-dazugehören; Heimat und innere Leere",
        ),
        (
            "Klientin berichtete von einem bedeutsamen Traum. Symbole der Verwandlung "
            "und des Verlusts. Explorative Arbeit mit dem Trauminhalt. Sehr fruchtbare Sitzung.",
            "Traumarbeit (explorative Methode). Symbolik besprochen.",
            "Faszination für die Tiefe der Klientin. Gute Übertragungsdynamik.",
            [MoodTag.MITTEL, MoodTag.GUTE_RESSOURCEN],
            "Traumarbeit: Symbole von Verwandlung und Verlust",
        ),
        (
            "Schamthema heute im Vordergrund. Klientin wagte es, über ein lange "
            "verschwiegenes Erlebnis zu sprechen. Große Courage. Normalisierung.",
            "Psychoedukation Scham vs. Schuld. Externalisierung. Reframing.",
            "Bewegt von der Courage. Würde der Klientin im Blick behalten.",
            [MoodTag.SCHWER, MoodTag.HOHE_AKTIVIERUNG, MoodTag.DURCHBRUCH],
            "Schamthema – lange verschwiegenes Erlebnis angesprochen",
        ),
        (
            "Ruhigere Sitzung. Klientin berichtet über Alltag und wie sie Erlerntes anwendet. "
            "Etwas Chitchat, aber auch tiefere Reflexion über Beziehungsmuster.",
            "Ressourcenstärkung. Beziehungsanalyse (Bindungsmuster).",
            "Sitzung wirkte etwas diffus. Nächste Mal klarer fokussieren.",
            [MoodTag.LEICHT, MoodTag.UPDATE_CHITCHAT],
            "Ruhigere Sitzung: Alltag und Beziehungsmuster",
        ),
        (
            "Klientin in einer Krise: Trennungssituation hat alte Wunden aktiviert. "
            "Krisenintervention. Klientin stabilisiert entlassen. Nächste Sitzung vorgezogen.",
            "Krisenintervention: Sicherheitsplanung besprochen, Ressourcen aktiviert.",
            "Sorge. Sicherheit der Klientin prüfen. Engmaschiger Kontakt planen.",
            [MoodTag.SCHWER, MoodTag.KRISE, MoodTag.HOHE_AKTIVIERUNG],
            "Krise nach Trennung – Krisenintervention, stabilisiert entlassen",
        ),
    ],
    "ruler": [
        (
            "Klient berichtet über Kontrollverlust in einer beruflichen Situation. "
            "Gefühle von Scham und Wut. Wir erkundeten den inneren Imperativ 'Funktioniere'. "
            "Sitzung konfrontativ aber produktiv.",
            "Kognitive Umstrukturierung. Arbeit mit inneren Antreibern.",
            "Reibung in der Sitzung spürbar — heilsame Konfrontation. Gut.",
            [MoodTag.MITTEL, MoodTag.HOHE_AKTIVIERUNG],
            "Kontrollverlust im Beruf; innerer Imperativ 'Funktioniere'",
        ),
        (
            "Klient sprach erstmals über seine Einsamkeit trotz vieler sozialer Kontakte. "
            "Wichtiger Durchbruch. Berührende Sitzung.",
            "Spiegeln von Emotionen. Validierung. Psychoedukation zu emotionaler Bedürftigkeit.",
            "Gerührt von der Verletzlichkeit des Klienten. Schutz dieser Momente wichtig.",
            [MoodTag.MITTEL, MoodTag.DURCHBRUCH, MoodTag.GUTE_RESSOURCEN],
            "Einsamkeit trotz vieler Kontakte – wichtiger Durchbruch",
        ),
        (
            "Thema Bindungsangst und Nähe. Klient zog sich in Sitzung etwas zurück. "
            "Wir arbeiteten damit als In-Vivo-Material.",
            "Beziehungsgestaltung als Intervention. Prozessarbeit.",
            "Spannungsfeld Nähe/Distanz gut gehalten. Supervision erwägen.",
            [MoodTag.SCHWER, MoodTag.UNSICHER, MoodTag.NIEDRIG_AFFEKTIV],
            "Bindungsangst & Nähe; Rückzug als In-Vivo-Material bearbeitet",
        ),
        (
            "Gute Sitzung. Klient reflektiert Veränderungen in seinem Führungsstil. "
            "Weniger Kontrolle, mehr Vertrauen. Erkenntnisse aus der Therapie transferiert.",
            "Transferarbeit (Therapie → Alltag). Bilanzierung.",
            "Freude über die Entwicklung. Klient wächst spürbar.",
            [MoodTag.LEICHT, MoodTag.FORTSCHRITT],
            "Veränderter Führungsstil: mehr Vertrauen, weniger Kontrolle",
        ),
        (
            "Klient in einer Entscheidungssituation. Innerer Konflikt zwischen "
            "Pflicht und eigenem Wunsch. Werteklärung.",
            "Werteklärungsübung. Szenarioarbeit (Was wäre wenn).",
            "Fühle mich als Begleiter in einem wichtigen Moment. Gute Arbeit.",
            [MoodTag.MITTEL, MoodTag.RICHTUNGSLOS],
            "Entscheidung: Pflicht vs. eigener Wunsch, Werteklärung",
        ),
    ],
    "seeker": [
        (
            "Klientin exploriert Lebenssinn nach einem Verlust. Existenzielle Themen. "
            "Tiefgründige Sitzung mit viel Stille.",
            "Existenzielle Gesprächsführung. Stille als therapeutisches Mittel.",
            "Berührt von der Tiefe der Suche. Eigene Reflexion über Sinn angestoßen.",
            [MoodTag.SCHWER, MoodTag.NIEDRIG_AFFEKTIV],
            "Lebenssinn nach Verlust – existenzielle Themen, viel Stille",
        ),
        (
            "Klientin berichtet von neuer Energie und Lust auf Veränderung. "
            "Pläne für die Zukunft. Viel Aufbruchsstimmung.",
            "Ressourcenaktivierung. Zukunftsvision erarbeitet. Ziele konkretisiert.",
            "Ansteckende Energie. Achtsam sein — nicht in Aktionismus verfallen.",
            [MoodTag.LEICHT, MoodTag.FORTSCHRITT, MoodTag.GUTE_RESSOURCEN],
            "Neue Energie und Aufbruch; Zukunftspläne konkretisiert",
        ),
        (
            "Klientin hat eine wichtige Entscheidung getroffen. Wir reflektieren "
            "den Prozess und was sie getragen hat.",
            "Entscheidungsanalyse. Stärken der Klientin herausgearbeitet.",
            "Stolz auf die Klientin. Beziehung endet bald — Abschied vorbereiten.",
            [MoodTag.LEICHT, MoodTag.DURCHBRUCH, MoodTag.FORTSCHRITT],
            "Wichtige Entscheidung getroffen; Prozess reflektiert",
        ),
        (
            "Klientin kommt mit diffuser Unruhe. Sucht etwas, weiß nicht was. "
            "Wir arbeiteten mit dem Bild des 'Suchenden'. Produktiv.",
            "Imaginationsarbeit (Innere Reise). Symbolarbeit.",
            "Resonanz mit dem Thema Suchen. Reflexion meiner eigenen Suchbewegungen.",
            [MoodTag.MITTEL, MoodTag.RICHTUNGSLOS],
            "Diffuse Unruhe – Arbeit mit dem Bild des 'Suchenden'",
        ),
        (
            "Klientin berichtete von Erfahrungen, die ihr Weltbild erschüttern. "
            "Thema Kontrollverlust und Vertrauen ins Leben.",
            "Psychoedukation zu Stress und Unsicherheit. Akzeptanzarbeit.",
            "Solidarität mit der Klientin in einer schwierigen Phase.",
            [MoodTag.SCHWER, MoodTag.HOHE_AKTIVIERUNG, MoodTag.UNSICHER],
            "Weltbild erschüttert – Kontrollverlust und Urvertrauen",
        ),
    ],
}

# ── Client profile templates per archetype ────────────────────────────────────
# (arbeitsdiagnose, intake_notes, case_notes)
PROFILE_TEMPLATES: dict[str, list[tuple[str, str, str]]] = {
    "hero": [
        (
            "Anpassungsstörung mit depressiver Reaktion (F43.2)",
            "Klient stellt sich vor mit anhaltender Erschöpfung und dem Gefühl, "
            "nicht mehr leisten zu können. Hohe Belastung im Beruf. Keine psychiatrische "
            "Vorgeschichte. Soziales Umfeld stabil. Motivation zur Veränderung vorhanden.",
            "Zentrale Themen: innere Antreiber, Perfektionismus, Selbstfürsorge. "
            "Ressourcen: starke soziale Bindungen, Reflexionsfähigkeit. "
            "Herausforderung: Veränderungsangst. Nächste Phase: Traumadiagnostik prüfen.",
        ),
        (
            "Rezidivierende depressive Störung, ggw. mittelgradige Episode (F33.1)",
            "Klient berichtet von wiederkehrenden Phasen der Niedergeschlagenheit seit "
            "der Jugend. Erste stationäre Behandlung vor 8 Jahren. Aktuell ambulant. "
            "Gute Compliance. Medikation durch Psychiater begleitet.",
            "Schwerpunkt: Rückfallprävention, Stärkung des Selbstwerts. "
            "Gute Fortschritte im Bereich Emotionsregulation. "
            "Weiterhin Arbeit an frühen Glaubenssätzen.",
        ),
    ],
    "exile": [
        (
            "Posttraumatische Belastungsstörung (F43.1)",
            "Klientin mit langjährigen Traumafolgesymptomen: Intrusionen, Vermeidung, "
            "Schlafstörungen. Mehrfachtraumatisierung in Kindheit und frühem Erwachsenenalter. "
            "Keine akute Suizidalität. Bisherige Therapieversuche: 2.",
            "Stabilisierungsphase abgeschlossen. Traumabearbeitung begonnen (EMDR vorbereitet). "
            "Gute Allianz. Herausforderung: Dissoziation bei Exposition. "
            "Ressourcen: kreative Ausdrucksfähigkeit, stabile Wohnsituation.",
        ),
        (
            "Emotional instabile Persönlichkeitsstörung, Borderline-Typ (F60.31)",
            "Klientin vorstellig nach Krisenintervention in Notaufnahme. Selbstverletzendes "
            "Verhalten in der Vergangenheit, derzeit remittiert. DBT-Grundlagen bekannt. "
            "Wunsch nach tiefergehender Beziehungsarbeit.",
            "Arbeit an Emotionstoleranz und Identität. Beziehungsdynamiken im Fokus. "
            "In-Vivo-Material aus der therapeutischen Beziehung nutzen. "
            "Engmaschige Begleitung, klare Grenzen wichtig.",
        ),
    ],
    "ruler": [
        (
            "Zwanghafte Persönlichkeitsstörung (F60.5)",
            "Klient führt eine leitende Position. Stellt sich vor mit beruflichem Stress "
            "und Beziehungsschwierigkeiten. Perfektionismus und Kontrollbedürfnis "
            "als Leitmotive. Hohe Intelligenz, eingeschränkter Zugang zu Emotionen.",
            "Themen: Kontrollverlust, Bindungsangst, Verletzlichkeit zulassen. "
            "Vorsichtiger Therapieprozess — Kontrollbedürfnis respektieren. "
            "Langsam tiefere Ebenen zugänglich machen.",
        ),
        (
            "Dysthymia (F34.1)",
            "Klient beschreibt lang anhaltende, unterschwellige Traurigkeit. "
            "Funktioniert gut nach außen, innen chronisch erschöpft. "
            "Erstmals in Therapie. Anfangs skeptisch, jetzt motiviert.",
            "Beziehungsarbeit im Vordergrund — Klient lernt, sich Unterstützung zuzugestehen. "
            "Themen: Leistung vs. Sein, Einsamkeit, Würde. "
            "Gute Zusammenarbeit trotz anfänglicher Abwehr.",
        ),
    ],
    "seeker": [
        (
            "Anpassungsstörung mit Angst und depressiver Reaktion, gemischt (F43.22)",
            "Klientin in einer Lebensumbruchphase (Trennung + Berufswechsel). "
            "Anhaltende Erschöpfung, diffuse Ängste, Sinnkrise. "
            "Keine psychiatrische Vorgeschichte. Gute Ressourcen.",
            "Themen: Identität, Werte, Lebenssinn. Existenzielle Gesprächsführung. "
            "Klientin sehr reflexiv. Gefahr: zu viel kognitive Analyse, zu wenig Erleben. "
            "Mehr Körperarbeit einführen.",
        ),
        (
            "Generalisierte Angststörung (F41.1)",
            "Klientin mit seit Jahren anhaltender Sorgenneigung. Körperliche Begleitsymptome: "
            "Schlafstörungen, Muskelverspannungen. Bisherige Behandlung: Verhaltenstherapie. "
            "Wünscht sich tiefenpsychologischen Zugang.",
            "Arbeit an der Funktion der Angst. Achtsamkeit als Anker. "
            "Exploration der Ursprünge in Bindungsgeschichte. "
            "Klientin öffnet sich zunehmend — Tempo beachten.",
        ),
    ],
}

# ── Monthly expenses to seed ──────────────────────────────────────────────────
# (category, description, amount, day_of_month, months_interval)
RECURRING_EXPENSES: list[tuple[str, str, str, int, int]] = [
    ("miete", "Praxismiete", "800.00", 1, 1),
    ("konto", "Kontoführungsgebühr", "12.00", 5, 1),
    ("telefon", "Telefon & Internet", "45.00", 10, 1),
    ("supervision", "Supervision", "150.00", 15, 3),
    ("software", "Praxisverwaltung Software", "25.00", 20, 3),
    ("verband", "Verbandsbeitrag", "60.00", 1, 12),
]

# ── Inquiry seed data ─────────────────────────────────────────────────────────
INQUIRIES: list[tuple[str, str, str, str, int]] = [
    # (full_name, source, status, notes_snippet, days_ago)
    ("Voldemort Riddle", "google_organic", "new", "Meldet sich nach langer Pause.", 2),
    ("Sauron Maia", "referral", "new", "Empfehlung durch Kollegin.", 5),
    ("Circe Aiaia", "website", "contacted", "Erstgespräch vereinbart.", 14),
    ("Jadis Narnia", "directory", "intro_meeting", "Vorgespräch lief gut.", 21),
    ("Draco Malfoy", "google_organic", "waitlist", "Auf Warteliste gesetzt.", 30),
    ("Tom Ripley", "referral", "in_intake", "Aufnahmeprozess läuft.", 45),
    ("Iago Othello", "website", "declined", "Kein Match, weitergeleitet.", 60),
    ("Ursula Thornton", "network", "unreachable", "Dreimal versucht, kein Rückruf.", 20),
]

SEED_TODO_TITLES: frozenset[str] = frozenset(
    [
        "Steuererklärung 2024 einreichen",
        "Supervision buchen für nächsten Monat",
        "Praxishandbuch aktualisieren",
        "Fortbildung zu Traumatherapie recherchieren",
        "Datenschutzerklärung überprüfen",
        "Neue Klientenmappe vorbereiten",
    ]
)

# Derived sets for idempotency checks and cleanup
SEED_CODES: frozenset[str] = frozenset(c[0] for c in CHARACTERS)
SEED_NAMES: frozenset[str] = frozenset(c[1] for c in CHARACTERS)
SEED_INQUIRY_NAMES: frozenset[str] = frozenset(i[0] for i in INQUIRIES)
SEED_TAG_NAMES: frozenset[str] = frozenset(
    ["Einzeltherapie", "Langzeitklient", "Kurzzeitintervention", "Gruppentherapie"]
)
SEED_TIMEOFF_TITLES: frozenset[str] = frozenset(
    [
        "Osterurlaub",
        "Fortbildung Traumatherapie",
        "Sommerurlaub",
        "Herbstpause",
        "Weihnachtsurlaub",
        "Supervision-Intensivtag",
    ]
)


class Command(BaseCommand):
    help = "Seed demo practice with fictional clients, sessions, and invoices"

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete all demo data before seeding",
        )
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Skip confirmation prompt",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=42,
            help="Random seed for reproducibility (default: 42)",
        )

    def handle(self, *args, **options) -> None:
        rng = random.Random(options["seed"])

        if options["clear"]:
            self._clear(options["yes"])
            return  # clear-only; run without --clear to reseed

        # Always ensure the demo practice has the correct display name (idempotent).
        Practice.objects.filter(slug=DEMO_SLUG).exclude(short_title_de="Therapie (Demo)").update(
            short_title_de="Therapie (Demo)", short_title_en="Therapy (Demo)"
        )

        # Idempotency check: fictional names like "Frodo Baggins" won't appear in a real practice
        if Client.objects.filter(full_name__in=SEED_NAMES).exists():
            self.stdout.write("ℹ️  Demo data already exists. Use --clear to reset.")
            return

        self.stdout.write("🌱 Seeding demo data...")

        practice = self._get_or_create_practice()
        self._assign_superusers(practice)
        service_60, service_90 = self._get_or_create_service_types()
        tags = self._create_tags()
        clients, char_map = self._create_clients(practice, tags, rng)
        sessions_by_client = self._create_sessions(clients, char_map, rng)
        self._create_notes(clients, char_map, sessions_by_client, rng)
        self._create_session_logs(clients, char_map, sessions_by_client, rng)
        self._create_profiles(clients, char_map, rng)
        self._create_invoices(practice, sessions_by_client, service_60, service_90, rng)
        self._create_pending_events(practice, clients, char_map, service_60, rng)
        self._create_inquiries(practice, rng)
        self._create_todos(practice)
        self._create_expenses(practice)
        self._create_time_off()

        total_sessions = sum(len(s) for s in sessions_by_client.values())
        total_invoices = Invoice.objects.filter(client__full_name__in=SEED_NAMES).count()
        total_pending = PendingCalendarEvent.objects.filter(
            google_event_id__startswith=SEED_PENDING_EVENT_PREFIX
        ).count()
        self.stdout.write(
            self.style.SUCCESS(
                f"✅ Seeded: {len(clients)} clients, {total_sessions} sessions, "
                f"{total_invoices} invoices, {total_pending} pending events, "
                f"{len(INQUIRIES)} inquiries, 6 todos, expenses"
            )
        )

    # ── Setup helpers ─────────────────────────────────────────────────────────

    def _get_or_create_practice(self) -> Practice:
        practice = Practice.objects.filter(slug=DEMO_SLUG).first()
        if practice:
            return practice

        # Always create/use a dedicated demo practice to keep sample data isolated
        # from real bookkeeping data.
        practice = Practice.objects.create(
            slug=DEMO_SLUG,
            name="Anna Schmidt",
            short_title_de="Therapie (Demo)",
            short_title_en="Therapy (Demo)",
            title="Heilpraktikerin für Psychotherapie",
        )
        self.stdout.write(f"  ✓ Created practice: {practice.name}")
        return practice

    def _assign_superusers(self, practice: Practice) -> None:
        from django.contrib.auth import get_user_model

        User = get_user_model()
        assigned = 0
        for user in User.objects.filter(is_superuser=True):
            _, created = UserPractice.objects.get_or_create(
                user=user,
                practice=practice,
                defaults={"is_owner": True},
            )
            if created:
                assigned += 1
        if assigned:
            self.stdout.write(f"  ✓ Assigned {assigned} superuser(s) to demo practice")

    def _get_or_create_service_types(self) -> tuple[ServiceType, ServiceType]:
        service_60, _ = ServiceType.objects.get_or_create(
            code="therapy_60",
            defaults={
                "name": "60-Min Therapy Session",
                "name_de": "Psychotherapie, 60 Min.",
                "name_en": "60-Min Therapy Session",
                "default_duration": 60,
                "practice": None,
            },
        )
        service_90, _ = ServiceType.objects.get_or_create(
            code="therapy_90",
            defaults={
                "name": "90-Min Therapy Session",
                "name_de": "Psychotherapie, 90 Min.",
                "name_en": "90-Min Therapy Session",
                "default_duration": 90,
                "practice": None,
            },
        )
        return service_60, service_90

    def _create_tags(self) -> dict[str, ClientTag]:
        tag_specs = [
            ("Einzeltherapie", "general", "blue"),
            ("Langzeitklient", "general", "green"),
            ("Kurzzeitintervention", "general", "orange"),
            ("Gruppentherapie", "general", "purple"),
        ]
        tags = {}
        for name, category, color in tag_specs:
            slug = slugify(name)
            tag, _ = ClientTag.objects.get_or_create(
                slug=slug,
                defaults={"name": name, "category": category, "color": color},
            )
            tags[name] = tag
        return tags

    # ── Client creation ───────────────────────────────────────────────────────

    def _create_clients(
        self,
        practice: Practice,
        tags: dict[str, ClientTag],
        rng: random.Random,
    ) -> tuple[list[Client], dict[int, tuple]]:
        today = date.today()
        two_years_ago = today - timedelta(days=730)
        rate_presets = [
            (Decimal("90.00"), Decimal("130.00")),  # standard (80%)
            (Decimal("80.00"), Decimal("115.00")),  # reduced (10%)
            (Decimal("100.00"), Decimal("145.00")),  # premium (10%)
        ]

        clients = []
        char_map: dict[int, tuple] = {}  # client.pk → CHARACTERS entry
        existing_codes: set[str] = set(Client.objects.values_list("client_code", flat=True))
        for char_entry in CHARACTERS:
            code, name, archetype, avg_spm, has_90 = char_entry
            # Intake date: random within the 2-year window, at least 3 months back
            intake_days_back = rng.randint(90, 730)
            intake_date = today - timedelta(days=intake_days_back)
            intake_date = max(intake_date, two_years_ago)

            # Rate preset
            rate_60, rate_90 = rng.choices(rate_presets, weights=[80, 10, 10])[0]

            # Mark ~30% of clients as inactive (therapy ended)
            active = rng.random() > 0.3

            # Avoid code collision with existing real clients
            safe_code = code
            suffix = 0
            while safe_code in existing_codes:
                suffix += 1
                safe_code = f"{code}{suffix}"[:10]
            existing_codes.add(safe_code)

            client = Client.objects.create(
                practice=practice,
                client_code=safe_code,
                full_name=name,
                hourly_rate_60=rate_60,
                hourly_rate_90=rate_90,
                active=active,
                first_seen_date=intake_date,
            )
            char_map[client.pk] = char_entry

            # Assign a tag to most clients
            if rng.random() > 0.2:
                if avg_spm >= 3.0:
                    client.tags.add(tags["Langzeitklient"])
                elif avg_spm <= 1.0:
                    client.tags.add(tags["Kurzzeitintervention"])
                else:
                    client.tags.add(tags["Einzeltherapie"])

            clients.append(client)

        self.stdout.write(f"  ✓ Created {len(clients)} clients")
        return clients, char_map

    # ── Session generation with seasonality ───────────────────────────────────

    def _session_factor(self, d: date) -> float:
        """Return a seasonality multiplier for the given date."""
        m, day = d.month, d.day
        if m in (7, 8):
            return 0.6
        if m == 12 and day >= 22:
            return 0.05
        if m == 1 and day <= 4:
            return 0.05
        if m in (9, 1):
            return 1.15
        return 1.0

    def _create_sessions(
        self,
        clients: list[Client],
        char_map: dict[int, tuple],
        rng: random.Random,
    ) -> dict[int, list[Session]]:
        today = date.today()
        sessions_by_client: dict[int, list[Session]] = {}

        for client in clients:
            _, _, archetype, avg_spm, has_90 = char_map[client.pk]

            intake = client.first_seen_date or (today - timedelta(days=365))
            # Inactive clients stopped therapy 1-12 months ago
            if not client.active:
                end_offset = rng.randint(30, 365)
                end_date = min(today - timedelta(days=end_offset), today)
            else:
                end_date = today

            # Weekly probability: avg_spm sessions per month ≈ avg_spm/4.33 per week
            base_prob = min(0.9, avg_spm / 4.33)

            client_sessions: list[Session] = []
            current = intake
            while current <= end_date:
                # Pick a weekday in this "week"
                factor = self._session_factor(current)
                jitter = rng.uniform(0.8, 1.2)
                if rng.random() < base_prob * factor * jitter:
                    # Random weekday offset 0-4 (Mon-Fri)
                    offset = rng.randint(0, 4)
                    session_date = current + timedelta(days=offset)
                    if session_date > end_date or session_date > today:
                        current += timedelta(days=7)
                        continue

                    duration = 90 if (has_90 and rng.random() < 0.30) else 60
                    # ~8% cancellation rate — realistic for a therapy practice
                    cancelled = rng.random() < 0.08
                    session = Session.objects.create(
                        client=client,
                        session_date=session_date,
                        duration=duration,
                        cancelled=cancelled,
                    )
                    client_sessions.append(session)

                current += timedelta(days=7)

            sessions_by_client[client.pk] = client_sessions

        total = sum(len(s) for s in sessions_by_client.values())
        self.stdout.write(f"  ✓ Created {total} sessions across {len(clients)} clients")
        return sessions_by_client

    def _create_notes(
        self,
        clients: list[Client],
        char_map: dict[int, tuple],
        sessions_by_client: dict[int, list[Session]],
        rng: random.Random,
    ) -> None:
        from django.conf import settings

        if not settings.FERNET_KEY:
            self.stdout.write("  ℹ️  Skipping clinical notes (FERNET_KEY not set)")
            return

        count = 0
        for client in clients:
            _, _, archetype, _, _ = char_map[client.pk]
            sessions = sessions_by_client.get(client.pk, [])
            if not sessions:
                continue
            # Spread 2-4 notes across the client's session history
            n_notes = rng.randint(2, 4)
            sample_sessions = rng.sample(sessions, min(n_notes, len(sessions)))
            templates = NOTE_TEMPLATES[archetype]
            for session in sample_sessions:
                ClientNote.objects.create(
                    client=client,
                    note_date=session.session_date,
                    content=rng.choice(templates),
                )
                count += 1
        self.stdout.write(f"  ✓ Created {count} clinical notes")

    def _create_session_logs(
        self,
        clients: list[Client],
        char_map: dict[int, tuple],
        sessions_by_client: dict[int, list[Session]],
        rng: random.Random,
    ) -> None:
        from django.conf import settings

        if not settings.FERNET_KEY:
            self.stdout.write("  ℹ️  Skipping session logs (FERNET_KEY not set)")
            return

        count = 0
        for client in clients:
            _, _, archetype, _, _ = char_map[client.pk]
            sessions = [s for s in sessions_by_client.get(client.pk, []) if not s.cancelled]
            if not sessions:
                continue
            templates = SESSION_LOG_TEMPLATES[archetype]
            for session in sessions:
                # ~75% of sessions get a protocol — leaves some as "missing"
                if rng.random() > 0.75:
                    continue
                content, interventions, reflection, mood_tags, summary = rng.choice(templates)
                # First session of each client is an intake
                session_type = (
                    SessionLog.SessionType.ERSTGESPRAECH
                    if session == sessions[0]
                    else SessionLog.SessionType.STANDARD
                )
                SessionLog.objects.get_or_create(
                    session=session,
                    defaults={
                        "session_type": session_type,
                        "content": content,
                        "interventions": interventions,
                        "therapist_reflection": reflection,
                        "mood_tags": mood_tags,
                        "summary": summary,
                    },
                )
                count += 1
        self.stdout.write(f"  ✓ Created {count} session logs")

    def _create_profiles(
        self,
        clients: list[Client],
        char_map: dict[int, tuple],
        rng: random.Random,
    ) -> None:
        from django.conf import settings

        if not settings.FERNET_KEY:
            self.stdout.write("  ℹ️  Skipping client profiles (FERNET_KEY not set)")
            return

        count = 0
        for client in clients:
            _, _, archetype, _, _ = char_map[client.pk]
            templates = PROFILE_TEMPLATES[archetype]
            arbeitsdiagnose, intake_notes, case_notes = rng.choice(templates)
            _, created = ClientProfile.objects.get_or_create(
                client=client,
                defaults={
                    "arbeitsdiagnose": arbeitsdiagnose,
                    "intake_notes": intake_notes,
                    "case_notes": case_notes,
                },
            )
            if created:
                count += 1
        self.stdout.write(f"  ✓ Created {count} client profiles")

    # ── Invoice creation ──────────────────────────────────────────────────────

    def _create_invoices(
        self,
        practice: Practice,
        sessions_by_client: dict[int, list[Session]],
        service_60: ServiceType,
        service_90: ServiceType,
        rng: random.Random,
    ) -> None:
        today = date.today()
        invoice_count = 0

        for client_pk, sessions in sessions_by_client.items():
            client = Client.objects.get(pk=client_pk)

            # Group sessions by (year, month)
            by_month: dict[tuple[int, int], list[Session]] = {}
            for s in sessions:
                key = (s.session_date.year, s.session_date.month)
                by_month.setdefault(key, []).append(s)

            for (year, month), month_sessions in sorted(by_month.items()):
                last_session_date = max(s.session_date for s in month_sessions)
                invoice_date = last_session_date + timedelta(days=rng.randint(3, 14))
                if invoice_date > today:
                    invoice_date = today

                months_old = (today.year - year) * 12 + (today.month - month)
                status, paid_date = self._pick_invoice_status(months_old, invoice_date, rng)

                invoice = Invoice(
                    practice=practice,
                    client=client,
                    invoice_number=get_next_invoice_number(client),
                    invoice_date=invoice_date,
                    status=status,
                    paid_date=paid_date,
                )
                invoice.save(skip_validation=True)

                for session in month_sessions:
                    service = service_90 if session.duration == 90 else service_60
                    rate = (
                        client.hourly_rate_90 if session.duration == 90 else client.hourly_rate_60
                    )
                    InvoiceItem.objects.create(
                        invoice=invoice,
                        service_type=service,
                        rate=rate,
                        quantity=Decimal("1.00"),
                        session=session,
                    )

                invoice.calculate_total()
                invoice.save(
                    skip_validation=True,
                    update_fields=["subtotal", "tax_amount", "total"],
                )
                invoice_count += 1

        self.stdout.write(f"  ✓ Created {invoice_count} invoices")

    def _pick_invoice_status(
        self,
        months_old: int,
        invoice_date: date,
        rng: random.Random,
    ) -> tuple[str, date | None]:
        """Return (status, paid_date) based on how old the invoice is."""
        if months_old >= 6:
            # Old invoices: mostly paid, small chance of written-off (bad debt)
            statuses = ["draft", "sent", "paid", "written_off"]
            weights = [3, 7, 86, 4]
        elif months_old >= 2:
            statuses = ["draft", "sent", "paid"]
            weights = [10, 30, 60]
        else:
            statuses = ["draft", "sent", "paid"]
            weights = [40, 45, 15]

        status = rng.choices(statuses, weights=weights)[0]
        if status == "paid":
            paid_date = invoice_date + timedelta(days=rng.randint(15, 45))
            return "paid", paid_date
        return status, None

    # ── Pending calendar events ───────────────────────────────────────────────

    def _create_pending_events(
        self,
        practice: Practice,
        clients: list[Client],
        char_map: dict[int, tuple],
        service_60: ServiceType,
        rng: random.Random,
    ) -> None:
        from datetime import time as dt_time

        today = date.today()
        active_clients = [c for c in clients if c.active]
        # Pick 6 active clients for pending events in the current billing period
        event_clients = rng.sample(active_clients, min(6, len(active_clients)))

        slot_times = [
            dt_time(9, 0),
            dt_time(10, 0),
            dt_time(11, 0),
            dt_time(14, 0),
            dt_time(15, 0),
            dt_time(16, 0),
        ]
        count = 0
        for i, client in enumerate(event_clients):
            event_id = f"{SEED_PENDING_EVENT_PREFIX}{client.client_code}-{i}"
            if PendingCalendarEvent.objects.filter(google_event_id=event_id).exists():
                continue

            # Spread events across the last three weeks
            days_back = rng.randint(1, 21)
            event_date = today - timedelta(days=days_back)
            while event_date.weekday() >= 5:
                event_date -= timedelta(days=1)

            _, _, _, _, has_90 = char_map[client.pk]
            duration = 90 if (has_90 and rng.random() < 0.3) else 60

            PendingCalendarEvent.objects.create(
                practice=practice,
                google_event_id=event_id,
                summary=f"Therapie {client.client_code}",
                event_date=event_date,
                event_time=rng.choice(slot_times),
                duration_minutes=duration,
                matched_client=client,
                suggested_service_type=service_60,
                status=PendingCalendarEvent.Status.PENDING,
            )
            count += 1

        self.stdout.write(f"  ✓ Created {count} pending calendar events")

    # ── Inquiries ─────────────────────────────────────────────────────────────

    def _create_inquiries(self, practice: Practice, rng: random.Random) -> None:
        today = date.today()
        for full_name, source, status, notes, days_ago in INQUIRIES:
            ClientInquiry.objects.create(
                practice=practice,
                full_name=full_name,
                email=f"{slugify(full_name.split()[0])}@example.com",
                source=source,
                status=status,
                notes=notes,
                inquiry_date=today - timedelta(days=days_ago),
            )
        self.stdout.write(f"  ✓ Created {len(INQUIRIES)} inquiries")

    # ── Todos ─────────────────────────────────────────────────────────────────

    def _create_todos(self, practice: Practice) -> None:
        todo_specs = [
            ("Steuererklärung 2024 einreichen", "financial", "high"),
            ("Supervision buchen für nächsten Monat", "admin", "medium"),
            ("Praxishandbuch aktualisieren", "admin", "low"),
            ("Fortbildung zu Traumatherapie recherchieren", "learning", "medium"),
            ("Datenschutzerklärung überprüfen", "admin", "medium"),
            ("Neue Klientenmappe vorbereiten", "client", "low"),
        ]
        for title, category, priority in todo_specs:
            PracticeTodo.objects.create(
                practice=practice,
                title=title,
                category=category,
                priority=priority,
            )
        self.stdout.write(f"  ✓ Created {len(todo_specs)} todos")

    # ── Expenses ──────────────────────────────────────────────────────────────

    def _create_expenses(self, practice: Practice) -> None:
        today = date.today()
        two_years_ago = today - timedelta(days=730)
        expense_count = 0
        existing_count = 0

        for category, description, amount_str, day_of_month, interval in RECURRING_EXPENSES:
            amount = Decimal(amount_str)
            # Walk from two_years_ago to today, stepping by interval months
            current = date(two_years_ago.year, two_years_ago.month, 1)
            month_step = 0
            while True:
                # Advance by interval months
                target_month = current.month + month_step * interval
                target_year = current.year + (target_month - 1) // 12
                target_month = (target_month - 1) % 12 + 1
                expense_date = date(
                    target_year,
                    target_month,
                    min(day_of_month, _days_in_month(target_year, target_month)),
                )
                if expense_date > today:
                    break
                _, created = CompanyExpense.objects.get_or_create(
                    practice=practice,
                    date=expense_date,
                    amount=amount,
                    description=description,
                    category=category,
                    defaults={
                        "is_tax_deductible": True,
                    },
                )
                if created:
                    expense_count += 1
                else:
                    existing_count += 1
                month_step += 1

        self.stdout.write(
            f"  ✓ Created {expense_count} expenses ({existing_count} already existed)"
        )

    def _create_time_off(self) -> None:
        # Realistic vacation + training blocks for a solo practice over 2025–2026.
        # Dates are fixed so re-runs stay idempotent via get_or_create on (start_date, end_date, type).
        entries = [
            # 2025
            (date(2025, 4, 14), date(2025, 4, 18), TimeOff.Type.VACATION, "Osterurlaub"),
            (
                date(2025, 5, 29),
                date(2025, 5, 30),
                TimeOff.Type.TRAINING,
                "Fortbildung Traumatherapie",
            ),
            (date(2025, 8, 4), date(2025, 8, 15), TimeOff.Type.VACATION, "Sommerurlaub"),
            (date(2025, 10, 27), date(2025, 10, 31), TimeOff.Type.VACATION, "Herbstpause"),
            (date(2025, 12, 22), date(2026, 1, 2), TimeOff.Type.VACATION, "Weihnachtsurlaub"),
            # 2026
            (date(2026, 3, 30), date(2026, 4, 3), TimeOff.Type.VACATION, "Osterurlaub"),
            (
                date(2026, 6, 19),
                date(2026, 6, 19),
                TimeOff.Type.TRAINING,
                "Supervision-Intensivtag",
            ),
            (date(2026, 7, 27), date(2026, 8, 7), TimeOff.Type.VACATION, "Sommerurlaub"),
        ]
        created = 0
        for start, end, kind, title in entries:
            _, made = TimeOff.objects.get_or_create(
                start_date=start,
                end_date=end,
                type=kind,
                defaults={"title": title},
            )
            if made:
                created += 1
        self.stdout.write(f"  ✓ Created {created} time-off entries")

    # ── Clear ─────────────────────────────────────────────────────────────────

    def _clear(self, skip_confirm: bool) -> None:
        seeded = Client.objects.filter(full_name__in=SEED_NAMES)
        demo_practice = Practice.objects.filter(slug=DEMO_SLUG).first()
        has_todos = PracticeTodo.objects.filter(title__in=SEED_TODO_TITLES).exists()
        has_expenses = (
            demo_practice and CompanyExpense.objects.filter(practice=demo_practice).exists()
        )
        has_inquiries = ClientInquiry.objects.filter(full_name__in=SEED_INQUIRY_NAMES).exists()
        has_timeoff = TimeOff.objects.filter(title__in=SEED_TIMEOFF_TITLES).exists()

        if (
            not seeded.exists()
            and not has_todos
            and not has_expenses
            and not has_inquiries
            and not has_timeoff
            and not demo_practice
        ):
            self.stdout.write("  Nothing to clear.")
            return

        count = seeded.count()
        if not skip_confirm:
            import sys

            if not sys.stdin.isatty():
                self.stdout.write(
                    self.style.WARNING("⚠️  No interactive terminal. Use --yes to confirm.")
                )
                self.stdout.write(self.style.ERROR("❌ Aborted"))
                return
            answer = input(
                f"⚠️  Delete all seeded demo data ({count} clients, todos, expenses, inquiries)? (yes/no): "
            )
            if answer.lower() != "yes":
                raise CommandError("Aborted.")

        # Delete in dependency order
        Invoice.objects.filter(client__full_name__in=SEED_NAMES).delete()
        Session.objects.filter(client__full_name__in=SEED_NAMES).delete()
        PendingCalendarEvent.objects.filter(
            google_event_id__startswith=SEED_PENDING_EVENT_PREFIX
        ).delete()
        seeded.delete()
        ClientInquiry.objects.filter(full_name__in=SEED_INQUIRY_NAMES).delete()
        PracticeTodo.objects.filter(title__in=SEED_TODO_TITLES).delete()
        TimeOff.objects.filter(title__in=SEED_TIMEOFF_TITLES).delete()
        if demo_practice:
            CompanyExpense.objects.filter(practice=demo_practice).delete()
            UserPractice.objects.filter(practice=demo_practice).delete()
            demo_practice.delete()

        # Remove seed tags only if no real (non-seed) clients still use them.
        # Deleting seed clients above already removed the M2M associations, so
        # any remaining .clients are real clients — leave those tags alone.
        deleted_tags = ClientTag.objects.filter(
            name__in=SEED_TAG_NAMES, clients__isnull=True
        ).delete()
        n_tags = deleted_tags[0]

        parts = []
        if count:
            parts.append(f"{count} clients")
        if has_todos:
            parts.append("todos")
        if has_inquiries:
            parts.append("inquiries")
        if has_timeoff:
            parts.append("time-off entries")
        if has_expenses:
            parts.append("expenses")
        if n_tags:
            parts.append(f"{n_tags} tags")
        if demo_practice:
            parts.append("demo practice")
        self.stdout.write(self.style.WARNING(f"🗑  Cleared seeded: {', '.join(parts)}."))


def _days_in_month(year: int, month: int) -> int:
    """Return the number of days in the given month."""
    import calendar

    return calendar.monthrange(year, month)[1]
