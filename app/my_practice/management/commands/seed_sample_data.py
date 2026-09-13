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
from django.utils import timezone
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
from ...models.gebueh import Leistungserfassung
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

# ── GebüH billing demo clients ────────────────────────────────────────────────
# Client codes billed via the GebüH fee schedule (Client.needs_gebueh_invoice).
# Mode drives what the demo shows on the client detail page:
#   diagnosed       — Arbeitsdiagnose on file; invoices print the ICD-10 code
#   probatorik      — early in the probationary phase, no diagnosis yet
#   probatorik_due  — no diagnosis but >= 5 diagnostic codes billed, so the
#                     client detail callout escalates to its warning variant
GEBUEH_CLIENT_MODES: dict[str, str] = {
    "ARA": "diagnosed",
    "GED": "probatorik",
    "THR": "probatorik_due",
}

# GebüH codes used by the seeder, from the schedule loaded in migration 0006.
GEBUEH_ZIFFER_THERAPY = "19.2"  # Psychotherapie 50–90 Min
GEBUEH_ZIFFER_ANAMNESE = "1"  # Anamnese / Folgeanamnese
GEBUEH_ZIFFER_EXPLORATION = "19.5"  # Psychologische Exploration

# ── Session note templates per archetype ─────────────────────────────────────
NOTE_TEMPLATES: dict[str, list[str]] = {
    "hero": [
        "Client reported recurring dreams of carrying a burden he cannot put down. "
        "Theme: responsibility and self-worth. Homework: journalling.",
        "Theme: sense of duty vs. own needs. Client showed good capacity for reflection. "
        "Next session: resource work.",
        "Marked exhaustion from sustained strain. Psychoeducation on boundaries and "
        "self-care. Introduced a breathing exercise.",
        "Client speaks of a task he must complete at any cost. Explored the inner drivers. "
        "Inner critic identified.",
        "Closing a block of work. Client reflects on progress. Positive development "
        "around self-compassion.",
    ],
    "exile": [
        "Client describes a deep sense of strangeness, even in familiar surroundings. "
        "Discussed EMDR preparation.",
        "Theme: home and belonging. Ambivalent feelings about her origins. "
        "Body work: grounding exercise.",
        "Client explores the question 'who am I outside this context?'. Identity work begun.",
        "Strong feelings of shame about the past. Normalisation and reframing. "
        "Good therapeutic alliance.",
        "Theme: transformation and loss of identity. The image of 'becoming someone else' "
        "surfaces. Parts work begun.",
    ],
    "ruler": [
        "Client describes difficulty asking for help. Perfectionism and need for control "
        "identified as protective strategies.",
        "Loneliness despite considerable social responsibility. Client doubts the "
        "authenticity of his relationships. Attachment work.",
        "Theme: authority and fear of failure. Client had a difficult week. "
        "Repeated stabilisation exercises.",
        "Client reflects on the pattern of showing strength at the cost of his own "
        "vulnerability. Good progress.",
        "First session after a crisis phase. Client stable. Protective factors worked out.",
    ],
    "seeker": [
        "Client searches for meaning in recurring experiences of loss. Existential themes. "
        "Discussed referral to further resources.",
        "Theme: change and fear of the unknown. Introduced a mindfulness exercise.",
        "Client explores her own values. What actually matters? A deep conversation "
        "about life goals.",
        "Dreams of transformation and rebirth. Symbol work. Client very reflective.",
        "Closing an important phase of work. Integration of insights. Client seems more settled.",
    ],
}

# ── Session-log templates per archetype ──────────────────────────────────────
# Each tuple: (content, interventions, therapist_reflection, mood_tags, summary)
# summary = short one-liner ≤120 chars, stored unencrypted — visible in session cockpit
SESSION_LOG_TEMPLATES: dict[str, list[tuple[str, str, str, list[str], str]]] = {
    "hero": [
        (
            "Client reported exhaustion after a particularly demanding week. "
            "Theme: responsibility vs. his own depletion. We explored what drives him "
            "and where the sense of duty comes from. Productive session.",
            "Psychoeducation on self-care. Resource activation. Breathing exercise.",
            "Strong resonance with the theme of self-sacrifice. Watch countertransference.",
            [MoodTag.MITTEL, MoodTag.GUTE_RESSOURCEN],
            "Exhaustion after a hard week – responsibility vs. self-care",
        ),
        (
            "Client reported a conflict he could not avoid. Feeling of powerlessness "
            "alongside an urge to control. Inner driver 'be strong' identified. "
            "Very open session.",
            "Parts work (inner critic vs. vulnerable child). Chair work prepared.",
            "Moved by the client's openness. Good therapeutic alliance palpable.",
            [MoodTag.SCHWER, MoodTag.HOHE_AKTIVIERUNG],
            "Conflict & powerlessness; inner driver 'be strong' recognised",
        ),
        (
            "Client showed clear progress today on setting boundaries. Reported a "
            "situation in which he said no for the first time. Session felt light "
            "and encouraging.",
            "Behavioural experiment reviewed. Positive reinforcement. Next steps planned.",
            "Pleased at the progress. Stay mindful, don't celebrate too early.",
            [MoodTag.LEICHT, MoodTag.FORTSCHRITT, MoodTag.GUTE_RESSOURCEN],
            "Progress: said no for the first time, set boundaries",
        ),
        (
            "Trauma triggers reactivated by external events. Client arrived distressed. "
            "Stabilisation first. Practised safe place. Client was able to self-regulate.",
            "Stabilisation: safe place, breath work. No trauma processing today.",
            "Concern for the client. Raise in supervision. Keep resources in view.",
            [MoodTag.SCHWER, MoodTag.HOHE_AKTIVIERUNG, MoodTag.UNSICHER],
            "Trauma triggers reactivated – stabilisation, safe place",
        ),
        (
            "Closing a longer block of work on autonomy. Client summarises his "
            "insights. We plan the next phase of the work.",
            "Review conversation. Goals formulated for the next phase.",
            "Proud of the development. The relationship has deepened.",
            [MoodTag.LEICHT, MoodTag.FORTSCHRITT, MoodTag.DURCHBRUCH],
            "Closed the autonomy block; next phase planned",
        ),
    ],
    "exile": [
        (
            "Client describes a persistent sense of not belonging. "
            "Theme: home and inner emptiness. Session was deep and moving.",
            "Body work: grounding exercise. Resource image developed.",
            "Deeply moved. My own themes of belonging surfaced briefly — take care.",
            [MoodTag.SCHWER, MoodTag.NIEDRIG_AFFEKTIV],
            "Theme of not belonging; home and inner emptiness",
        ),
        (
            "Client reported a significant dream. Symbols of transformation and loss. "
            "Exploratory work with the dream content. Very fruitful session.",
            "Dream work (exploratory method). Symbolism discussed.",
            "Fascinated by the client's depth. Good transference dynamic.",
            [MoodTag.MITTEL, MoodTag.GUTE_RESSOURCEN],
            "Dream work: symbols of transformation and loss",
        ),
        (
            "Shame was in the foreground today. Client dared to speak about an "
            "experience long kept silent. Great courage. Normalisation.",
            "Psychoeducation on shame vs. guilt. Externalisation. Reframing.",
            "Moved by her courage. Keep the client's dignity in view.",
            [MoodTag.SCHWER, MoodTag.HOHE_AKTIVIERUNG, MoodTag.DURCHBRUCH],
            "Shame – spoke about a long-silenced experience",
        ),
        (
            "Quieter session. Client reports on daily life and how she applies what "
            "she has learned. Some chitchat, but also deeper reflection on relational patterns.",
            "Resource strengthening. Relationship analysis (attachment patterns).",
            "Session felt somewhat diffuse. Focus more clearly next time.",
            [MoodTag.LEICHT, MoodTag.UPDATE_CHITCHAT],
            "Quieter session: daily life and relational patterns",
        ),
        (
            "Client in crisis: a separation has reactivated old wounds. "
            "Crisis intervention. Client left stabilised. Next session brought forward.",
            "Crisis intervention: safety planning discussed, resources activated.",
            "Concerned. Check the client's safety. Plan close contact.",
            [MoodTag.SCHWER, MoodTag.KRISE, MoodTag.HOHE_AKTIVIERUNG],
            "Crisis after separation – intervention, left stabilised",
        ),
    ],
    "ruler": [
        (
            "Client reports a loss of control in a work situation. Feelings of shame "
            "and anger. We explored the inner imperative 'perform'. "
            "Confrontational but productive session.",
            "Cognitive restructuring. Work with inner drivers.",
            "Friction in the session was palpable — healing confrontation. Good.",
            [MoodTag.MITTEL, MoodTag.HOHE_AKTIVIERUNG],
            "Loss of control at work; inner imperative 'perform'",
        ),
        (
            "Client spoke for the first time about his loneliness despite many "
            "social contacts. Important breakthrough. Touching session.",
            "Mirroring emotions. Validation. Psychoeducation on emotional need.",
            "Touched by the client's vulnerability. Protecting these moments matters.",
            [MoodTag.MITTEL, MoodTag.DURCHBRUCH, MoodTag.GUTE_RESSOURCEN],
            "Loneliness despite many contacts – important breakthrough",
        ),
        (
            "Theme: fear of attachment and closeness. Client withdrew somewhat during "
            "the session. We worked with that as in-vivo material.",
            "Relational work as intervention. Process work.",
            "Held the closeness/distance tension well. Consider supervision.",
            [MoodTag.SCHWER, MoodTag.UNSICHER, MoodTag.NIEDRIG_AFFEKTIV],
            "Fear of closeness; withdrawal worked as in-vivo material",
        ),
        (
            "Good session. Client reflects on changes in his leadership style. "
            "Less control, more trust. Insights transferred from therapy.",
            "Transfer work (therapy → everyday life). Review.",
            "Pleased at the development. The client is visibly growing.",
            [MoodTag.LEICHT, MoodTag.FORTSCHRITT],
            "Changed leadership style: more trust, less control",
        ),
        (
            "Client facing a decision. Inner conflict between duty and his own wish. "
            "Values clarification.",
            "Values clarification exercise. Scenario work (what if).",
            "I feel like a companion at an important moment. Good work.",
            [MoodTag.MITTEL, MoodTag.RICHTUNGSLOS],
            "Decision: duty vs. own wish, values clarification",
        ),
    ],
    "seeker": [
        (
            "Client explores meaning in life after a loss. Existential themes. "
            "Profound session with a lot of silence.",
            "Existential conversation. Silence as a therapeutic means.",
            "Touched by the depth of her search. Prompted my own reflection on meaning.",
            [MoodTag.SCHWER, MoodTag.NIEDRIG_AFFEKTIV],
            "Meaning after loss – existential themes, much silence",
        ),
        (
            "Client reports new energy and an appetite for change. "
            "Plans for the future. A real sense of departure.",
            "Resource activation. Vision of the future developed. Goals made concrete.",
            "Infectious energy. Stay mindful — don't slip into busyness.",
            [MoodTag.LEICHT, MoodTag.FORTSCHRITT, MoodTag.GUTE_RESSOURCEN],
            "New energy and momentum; future plans made concrete",
        ),
        (
            "Client has made an important decision. We reflect on the process and "
            "on what carried her through.",
            "Decision analysis. Client's strengths drawn out.",
            "Proud of the client. The work ends soon — prepare for closure.",
            [MoodTag.LEICHT, MoodTag.DURCHBRUCH, MoodTag.FORTSCHRITT],
            "Important decision made; process reflected on",
        ),
        (
            "Client arrives with diffuse restlessness. Searching for something, "
            "doesn't know what. We worked with the image of 'the seeker'. Productive.",
            "Imagination work (inner journey). Symbol work.",
            "Resonance with the theme of searching. Reflected on my own search.",
            [MoodTag.MITTEL, MoodTag.RICHTUNGSLOS],
            "Diffuse restlessness – work with the image of 'the seeker'",
        ),
        (
            "Client reported experiences that shake her view of the world. "
            "Theme: loss of control and basic trust in life.",
            "Psychoeducation on stress and uncertainty. Acceptance work.",
            "Solidarity with the client through a difficult phase.",
            [MoodTag.SCHWER, MoodTag.HOHE_AKTIVIERUNG, MoodTag.UNSICHER],
            "Worldview shaken – loss of control and basic trust",
        ),
    ],
}

# ── Client profile templates per archetype ────────────────────────────────────
# (arbeitsdiagnose, intake_notes, case_notes)
# ICD-10 labels are kept in their official German wording — they are catalogue
# entries, not UI text, and that is what appears on a German invoice.
PROFILE_TEMPLATES: dict[str, list[tuple[str, str, str]]] = {
    "hero": [
        (
            "Anpassungsstörung mit depressiver Reaktion (F43.2)",
            "Client presents with sustained exhaustion and the feeling of no longer "
            "being able to perform. High strain at work. No psychiatric history. "
            "Social environment stable. Motivated to change.",
            "Central themes: inner drivers, perfectionism, self-care. "
            "Resources: strong social bonds, capacity for reflection. "
            "Challenge: fear of change. Next phase: consider trauma assessment.",
        ),
        (
            "Rezidivierende depressive Störung, ggw. mittelgradige Episode (F33.1)",
            "Client reports recurring phases of low mood since adolescence. First "
            "inpatient treatment 8 years ago. Currently outpatient. Good compliance. "
            "Medication managed by a psychiatrist.",
            "Focus: relapse prevention, strengthening self-worth. "
            "Good progress on emotion regulation. "
            "Continued work on early core beliefs.",
        ),
    ],
    "exile": [
        (
            "Posttraumatische Belastungsstörung (F43.1)",
            "Client with long-standing post-traumatic symptoms: intrusions, avoidance, "
            "sleep disturbance. Multiple traumatisation in childhood and early adulthood. "
            "No acute suicidality. Previous attempts at therapy: 2.",
            "Stabilisation phase complete. Trauma processing begun (EMDR prepared). "
            "Good alliance. Challenge: dissociation during exposure. "
            "Resources: creative expression, stable housing.",
        ),
        (
            "Emotional instabile Persönlichkeitsstörung, Borderline-Typ (F60.31)",
            "Client presented after a crisis intervention in A&E. Self-harming behaviour "
            "in the past, currently in remission. Familiar with DBT basics. "
            "Wishes for deeper relational work.",
            "Work on distress tolerance and identity. Relational dynamics in focus. "
            "Use in-vivo material from the therapeutic relationship. "
            "Close support, clear boundaries important.",
        ),
    ],
    "ruler": [
        (
            "Zwanghafte Persönlichkeitsstörung (F60.5)",
            "Client holds a leadership position. Presents with work stress and "
            "relationship difficulties. Perfectionism and a need for control as "
            "leitmotifs. High intelligence, limited access to emotions.",
            "Themes: loss of control, fear of attachment, allowing vulnerability. "
            "Cautious therapeutic process — respect the need for control. "
            "Open up deeper levels slowly.",
        ),
        (
            "Dysthymia (F34.1)",
            "Client describes long-standing, low-grade sadness. Functions well "
            "outwardly, chronically exhausted inwardly. First time in therapy. "
            "Sceptical at first, now motivated.",
            "Relational work in the foreground — client is learning to allow himself "
            "support. Themes: achievement vs. being, loneliness, dignity. "
            "Good collaboration despite initial resistance.",
        ),
    ],
    "seeker": [
        (
            "Anpassungsstörung mit Angst und depressiver Reaktion, gemischt (F43.22)",
            "Client in a period of upheaval (separation + career change). "
            "Sustained exhaustion, diffuse anxiety, crisis of meaning. "
            "No psychiatric history. Good resources.",
            "Themes: identity, values, meaning. Existential conversation. "
            "Client very reflective. Risk: too much cognitive analysis, too little "
            "felt experience. Introduce more body work.",
        ),
        (
            "Generalisierte Angststörung (F41.1)",
            "Client with a years-long tendency to worry. Physical accompanying symptoms: "
            "sleep disturbance, muscle tension. Previous treatment: behavioural therapy. "
            "Would like a psychodynamic approach.",
            "Work on the function of the anxiety. Mindfulness as an anchor. "
            "Exploring the origins in her attachment history. "
            "Client is opening up increasingly — mind the pace.",
        ),
    ],
}

# ── Monthly expenses to seed ──────────────────────────────────────────────────
# (category, description, amount, day_of_month, months_interval)
# The category keys are CompanyExpense choice values — do not translate them.
RECURRING_EXPENSES: list[tuple[str, str, str, int, int]] = [
    ("miete", "Practice rent", "800.00", 1, 1),
    ("konto", "Account maintenance fee", "12.00", 5, 1),
    ("telefon", "Phone & internet", "45.00", 10, 1),
    ("supervision", "Supervision", "150.00", 15, 3),
    ("software", "Practice management software", "25.00", 20, 3),
    ("verband", "Professional association fee", "60.00", 1, 12),
]

# ── Inquiry seed data ─────────────────────────────────────────────────────────
INQUIRIES: list[tuple[str, str, str, str, int]] = [
    # (full_name, source, status, notes_snippet, days_ago)
    ("Voldemort Riddle", "google_organic", "new", "Getting in touch after a long gap.", 2),
    ("Sauron Maia", "referral", "new", "Referred by a colleague.", 5),
    ("Circe Aiaia", "website", "contacted", "First appointment arranged.", 14),
    ("Jadis Narnia", "directory", "intro_meeting", "Intro meeting went well.", 21),
    ("Draco Malfoy", "google_organic", "waitlist", "Added to the waiting list.", 30),
    ("Tom Ripley", "referral", "in_intake", "Intake process under way.", 45),
    ("Iago Othello", "website", "declined", "Not a match, referred on.", 60),
    ("Ursula Thornton", "network", "unreachable", "Tried three times, no call back.", 20),
]

SEED_TODO_TITLES: frozenset[str] = frozenset(
    [
        "File 2024 tax return",
        "Book supervision for next month",
        "Update the practice handbook",
        "Research trauma therapy training",
        "Review the privacy policy",
        "Prepare a new client folder",
    ]
)

# Derived sets for idempotency checks and cleanup
SEED_CODES: frozenset[str] = frozenset(c[0] for c in CHARACTERS)
SEED_NAMES: frozenset[str] = frozenset(c[1] for c in CHARACTERS)
SEED_INQUIRY_NAMES: frozenset[str] = frozenset(i[0] for i in INQUIRIES)
SEED_TAG_NAMES: frozenset[str] = frozenset(
    ["Individual therapy", "Long-term client", "Short-term intervention", "Group therapy"]
)
SEED_TIMEOFF_TITLES: frozenset[str] = frozenset(
    [
        "Easter break",
        "Trauma therapy training",
        "Summer holiday",
        "Autumn break",
        "Christmas holiday",
        "Supervision intensive day",
    ]
)

# ── Legacy German seed strings ────────────────────────────────────────────────
# The seeder produced German todo/tag/time-off titles until the demo data was
# translated. `--clear` matches these rows by exact title, so the old spellings
# stay listed here; without them `--clear` silently leaves pre-translation demo
# data behind. Safe to drop once no installation holds an older demo dataset.
LEGACY_TODO_TITLES: frozenset[str] = frozenset(
    [
        "Steuererklärung 2024 einreichen",
        "Supervision buchen für nächsten Monat",
        "Praxishandbuch aktualisieren",
        "Fortbildung zu Traumatherapie recherchieren",
        "Datenschutzerklärung überprüfen",
        "Neue Klientenmappe vorbereiten",
    ]
)
LEGACY_TAG_NAMES: frozenset[str] = frozenset(
    ["Einzeltherapie", "Langzeitklient", "Kurzzeitintervention", "Gruppentherapie"]
)
LEGACY_TIMEOFF_TITLES: frozenset[str] = frozenset(
    [
        "Osterurlaub",
        "Fortbildung Traumatherapie",
        "Sommerurlaub",
        "Herbstpause",
        "Weihnachtsurlaub",
        "Supervision-Intensivtag",
    ]
)

CLEARABLE_TODO_TITLES: frozenset[str] = SEED_TODO_TITLES | LEGACY_TODO_TITLES
CLEARABLE_TAG_NAMES: frozenset[str] = SEED_TAG_NAMES | LEGACY_TAG_NAMES
CLEARABLE_TIMEOFF_TITLES: frozenset[str] = SEED_TIMEOFF_TITLES | LEGACY_TIMEOFF_TITLES


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
        self._create_gebueh_leistungen(clients, char_map, sessions_by_client)
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
            # Regulated German professional designation — kept untranslated, it is
            # the licence the practice bills under, not UI text.
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
            ("Individual therapy", "general", "blue"),
            ("Long-term client", "general", "green"),
            ("Short-term intervention", "general", "orange"),
            ("Group therapy", "general", "purple"),
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
        today = timezone.localdate()
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
                needs_gebueh_invoice=code in GEBUEH_CLIENT_MODES,
            )
            char_map[client.pk] = char_entry

            # Assign a tag to most clients
            if rng.random() > 0.2:
                if avg_spm >= 3.0:
                    client.tags.add(tags["Long-term client"])
                elif avg_spm <= 1.0:
                    client.tags.add(tags["Short-term intervention"])
                else:
                    client.tags.add(tags["Individual therapy"])

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
        today = timezone.localdate()
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
            code, _, archetype, _, _ = char_map[client.pk]
            templates = PROFILE_TEMPLATES[archetype]
            arbeitsdiagnose, intake_notes, case_notes = rng.choice(templates)
            # Probationary-phase clients have no working diagnosis yet — that is
            # what surfaces the diagnosis callout on the client detail page.
            if GEBUEH_CLIENT_MODES.get(code, "").startswith("probatorik"):
                arbeitsdiagnose = ""
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

    # ── GebüH service entries ─────────────────────────────────────────────────

    def _create_gebueh_leistungen(
        self,
        clients: list[Client],
        char_map: dict[int, tuple],
        sessions_by_client: dict[int, list[Session]],
    ) -> None:
        """
        Record GebüH service lines for the clients billed via the fee schedule.

        Each session gets the therapy code plus, at intake and periodically, a
        diagnostic code. Amounts follow the same rule as the quick-entry UI: a
        code bills its satz_max, capped by whatever is left of the session fee,
        so the recorded lines never exceed what the client is actually charged.
        """
        from ...models.gebueh import GebuhZiffer

        wanted = [
            GEBUEH_ZIFFER_THERAPY,
            GEBUEH_ZIFFER_ANAMNESE,
            GEBUEH_ZIFFER_EXPLORATION,
        ]
        ziffern = {z.nummer: z for z in GebuhZiffer.objects.filter(nummer__in=wanted)}
        if len(ziffern) < len(wanted):
            self.stdout.write("  ℹ️  Skipping GebüH entries (fee schedule not seeded)")
            return

        count = 0
        for client in clients:
            code = char_map[client.pk][0]
            mode = GEBUEH_CLIENT_MODES.get(code)
            if mode is None:
                continue

            sessions = sorted(sessions_by_client.get(client.pk, []), key=lambda s: s.session_date)
            # Early in the probationary phase only the first few sessions are billed.
            if mode == "probatorik":
                sessions = sessions[:3]

            for idx, session in enumerate(sessions):
                nummern = [GEBUEH_ZIFFER_THERAPY]
                if idx == 0:
                    nummern.append(GEBUEH_ZIFFER_ANAMNESE)
                elif mode != "probatorik" and idx % 4 == 0:
                    nummern.append(GEBUEH_ZIFFER_EXPLORATION)

                remaining = Leistungserfassung.compute_vereinbarter_betrag(session)
                agreed = remaining
                for nummer in nummern:
                    if remaining <= 0:
                        break
                    ziffer = ziffern[nummer]
                    betrag = min(ziffer.satz_max, remaining)
                    _, made = Leistungserfassung.objects.get_or_create(
                        session=session,
                        ziffer=ziffer,
                        defaults={"betrag": betrag, "vereinbarter_betrag": agreed},
                    )
                    if made:
                        remaining -= betrag
                        count += 1

        self.stdout.write(f"  ✓ Created {count} GebüH service entries")

    # ── Invoice creation ──────────────────────────────────────────────────────

    def _create_invoices(
        self,
        practice: Practice,
        sessions_by_client: dict[int, list[Session]],
        service_60: ServiceType,
        service_90: ServiceType,
        rng: random.Random,
    ) -> None:
        today = timezone.localdate()
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

        today = timezone.localdate()
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
        today = timezone.localdate()
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
            ("File 2024 tax return", "financial", "high"),
            ("Book supervision for next month", "admin", "medium"),
            ("Update the practice handbook", "admin", "low"),
            ("Research trauma therapy training", "learning", "medium"),
            ("Review the privacy policy", "admin", "medium"),
            ("Prepare a new client folder", "client", "low"),
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
        today = timezone.localdate()
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
            (date(2025, 4, 14), date(2025, 4, 18), TimeOff.Type.VACATION, "Easter break"),
            (
                date(2025, 5, 29),
                date(2025, 5, 30),
                TimeOff.Type.TRAINING,
                "Trauma therapy training",
            ),
            (date(2025, 8, 4), date(2025, 8, 15), TimeOff.Type.VACATION, "Summer holiday"),
            (date(2025, 10, 27), date(2025, 10, 31), TimeOff.Type.VACATION, "Autumn break"),
            (date(2025, 12, 22), date(2026, 1, 2), TimeOff.Type.VACATION, "Christmas holiday"),
            # 2026
            (date(2026, 3, 30), date(2026, 4, 3), TimeOff.Type.VACATION, "Easter break"),
            (
                date(2026, 6, 19),
                date(2026, 6, 19),
                TimeOff.Type.TRAINING,
                "Supervision intensive day",
            ),
            (date(2026, 7, 27), date(2026, 8, 7), TimeOff.Type.VACATION, "Summer holiday"),
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
        has_todos = PracticeTodo.objects.filter(title__in=CLEARABLE_TODO_TITLES).exists()
        has_expenses = (
            demo_practice and CompanyExpense.objects.filter(practice=demo_practice).exists()
        )
        has_inquiries = ClientInquiry.objects.filter(full_name__in=SEED_INQUIRY_NAMES).exists()
        has_timeoff = TimeOff.objects.filter(title__in=CLEARABLE_TIMEOFF_TITLES).exists()

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
        # Leistungserfassung.session is PROTECT, so the GebüH lines have to go
        # before the sessions they hang off.
        Leistungserfassung.objects.filter(session__client__full_name__in=SEED_NAMES).delete()
        Session.objects.filter(client__full_name__in=SEED_NAMES).delete()
        PendingCalendarEvent.objects.filter(
            google_event_id__startswith=SEED_PENDING_EVENT_PREFIX
        ).delete()
        seeded.delete()
        ClientInquiry.objects.filter(full_name__in=SEED_INQUIRY_NAMES).delete()
        PracticeTodo.objects.filter(title__in=CLEARABLE_TODO_TITLES).delete()
        TimeOff.objects.filter(title__in=CLEARABLE_TIMEOFF_TITLES).delete()
        if demo_practice:
            CompanyExpense.objects.filter(practice=demo_practice).delete()
            UserPractice.objects.filter(practice=demo_practice).delete()
            demo_practice.delete()

        # Remove seed tags only if no real (non-seed) clients still use them.
        # Deleting seed clients above already removed the M2M associations, so
        # any remaining .clients are real clients — leave those tags alone.
        deleted_tags = ClientTag.objects.filter(
            name__in=CLEARABLE_TAG_NAMES, clients__isnull=True
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
