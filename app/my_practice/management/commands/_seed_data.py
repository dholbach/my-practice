"""Fixture literals for the seed_sample_data management command.

Fictional characters (Tolkien, Le Guin, Greek mythology) and their clinical
demo copy — pure data, no seeding logic. Kept separate from
management/commands/seed_sample_data.py so the command's actual logic isn't
buried under ~400 lines of literals.
"""

from ...models.clinical import MoodTag

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
