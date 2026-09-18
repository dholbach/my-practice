"""Stage-appropriate copy-paste email templates for client inquiries (P-037 Ph-3).

"label" is UI chrome (the template picker), translated via gettext_lazy; subject/body/
subject_en/body_en are authored bilingual email content per client-language, not
Django-i18n UI text — same exemption as utils/email_utils.py (see CLAUDE.md i18n rules).
"""

from typing import Any

from django.utils.translation import gettext_lazy

from ..models import InquiryStatus

STAGE_EMAIL_TEMPLATES: dict[str, dict[str, Any]] = {
    InquiryStatus.NEW: {
        "label": gettext_lazy("Acknowledge receipt"),
        "subject": "Ihre Anfrage — Eingangsbestätigung",
        "body": (
            "Hallo <..>,\n\n"
            "Vielen Dank für Ihre Nachricht. Gerne würde ich einen Termin für ein "
            "Vorgespräch mit Ihnen vereinbaren, um mehr über Ihr Anliegen zu erfahren. "
            "Hier können wir auch gemeinsam klären, was für Sie in nächster Zeit "
            "hilfreich sein könnte.\n\n"
            "Hätten Sie Zeit für ein unverbindliches Kennenlernen (ca. 20 Minuten, "
            "per Video-Call oder Telefon)? Um einen Termin zu buchen, wählen Sie bitte "
            "'intro call' auf [Buchungs-URL] aus. "
            "Falls Sie dort kein Konto anlegen möchten, ist das kein Problem — "
            "schreiben Sie mir einfach zurück, wann ein Termin für Sie passen würde.\n\n"
            "Liebe Grüße und alles Gute,\n"
            "[Ihr Name]"
        ),
        "subject_en": "Your inquiry — Thank you for reaching out",
        "body_en": (
            "Hi <..>,\n\n"
            "Thank you for your message. I would love to arrange a time for a brief "
            "introductory meeting to learn more about what brings you here. We can "
            "also explore together what might be helpful for you going forward.\n\n"
            "Would you have time for an informal get-to-know (approx. 20 minutes, "
            "via video call or phone)? To book a time, please choose 'intro call' on "
            "[booking URL] and pick a time. "
            "And if you don't wish to create an account, that's fine — feel free to "
            "just email back a time that would suit you for an introductory call.\n\n"
            "Warm regards and all the best,\n"
            "[Your name]"
        ),
    },
    InquiryStatus.CONTACTED: {
        "label": gettext_lazy("Propose intro meeting"),
        "subject": "Terminvorschlag: Vorgespräch",
        "body": (
            "Guten Tag,\n\n"
            "vielen Dank für Ihre Nachricht. Gerne würde ich einen Termin für ein "
            "Vorgespräch mit Ihnen vereinbaren. Hier können wir gemeinsam schauen, "
            "was für Sie hilfreich sein könnte.\n\n"
            "Hätten Sie Zeit für ein kurzes, unverbindliches Kennenlernen "
            "(ca. 20 Minuten, per Video-Call oder Telefon)? "
            "Hier sind einige Termine, die ich anbieten kann:\n"
            "– [Termin 1]\n"
            "– [Termin 2]\n\n"
            "Mit freundlichen Grüßen"
        ),
    },
    InquiryStatus.INTRO_MEETING: {
        "label": gettext_lazy("After intro meeting"),
        "subject": "Nächster Schritt nach unserem Vorgespräch",
        "body": (
            "Guten Tag,\n\n"
            "es war schön, mit Ihnen zu sprechen. Ich freue mich, eine gute Basis "
            "für eine Zusammenarbeit gefunden zu haben, und würde Sie gerne als "
            "Klient:in aufnehmen.\n\n"
            "Ich werde Ihnen als nächsten Schritt [den Aufnahmebogen / einen ersten "
            "Terminvorschlag] zusenden. Bitte melden Sie sich, wenn Sie bereit sind.\n\n"
            "Mit freundlichen Grüßen"
        ),
    },
    InquiryStatus.WAITLIST: {
        "label": gettext_lazy("Waitlist spot available"),
        "subject": "Freier Therapieplatz — Meldung von der Warteliste",
        "body": (
            "Guten Tag,\n\n"
            "ich möchte Ihnen mitteilen, dass ich derzeit wieder einen freien "
            "Therapieplatz habe und an unsere Anfrage denke.\n\n"
            "Hätten Sie weiterhin Interesse, Gespräche aufzunehmen? "
            "Ich würde mich über eine Rückmeldung bis [Datum] freuen.\n\n"
            "Mit freundlichen Grüßen"
        ),
    },
    InquiryStatus.IN_INTAKE: {
        "label": gettext_lazy("Intake documents"),
        "subject": "Unterlagen für den Aufnahmeprozess",
        "body": (
            "Guten Tag,\n\n"
            "ich freue mich, dass Sie die Aufnahme beginnen möchten. "
            "Anbei erhalten Sie den Aufnahmebogen, den ich Sie bitte ausgefüllt "
            "zurückzusenden.\n\n"
            "[Hier ggf. Link oder Anhang anfügen]\n\n"
            "Bei Fragen können Sie sich jederzeit bei mir melden.\n\n"
            "Mit freundlichen Grüßen"
        ),
    },
    InquiryStatus.DECLINED: {
        "label": gettext_lazy("Friendly decline"),
        "subject": "Rückmeldung zu Ihrer Anfrage",
        "body": (
            "Guten Tag,\n\n"
            "vielen Dank für Ihr Vertrauen und Ihre Anfrage. Nach sorgfältiger "
            "Überlegung muss ich Ihnen leider mitteilen, dass ich Sie zum "
            "jetzigen Zeitpunkt nicht aufnehmen kann.\n\n"
            "Ich empfehle Ihnen, sich an andere Kolleg:innen zu wenden "
            "(z. B. über die Suche unter therapiesuche.de). "
            "In dringenden Fällen steht Ihnen auch die Telefonseelsorge zur "
            "Verfügung (0800 111 0 111, kostenlos und 24h erreichbar).\n\n"
            "Ich wünsche Ihnen alles Gute.\n\n"
            "Mit freundlichen Grüßen"
        ),
    },
    InquiryStatus.NOT_SUITABLE: {
        "label": gettext_lazy("Friendly decline (not a match)"),
        "subject": "Rückmeldung zu Ihrer Anfrage",
        "body": (
            "Guten Tag,\n\n"
            "vielen Dank für Ihr Vertrauen und Ihre Anfrage. Nach unserem Gespräch "
            "bin ich zu dem Schluss gekommen, dass ich leider nicht die beste "
            "Anlaufstelle für Sie bin — nicht weil Ihr Anliegen unwichtig wäre, "
            "sondern weil ich einen anderen Schwerpunkt habe.\n\n"
            "Ich empfehle Ihnen, sich an Kolleg:innen mit dem Schwerpunkt "
            "[Bereich] zu wenden. Über therapiesuche.de oder die Telefonseelsorge "
            "(0800 111 0 111) können Sie weitere Unterstützung finden.\n\n"
            "Ich wünsche Ihnen alles Gute.\n\n"
            "Mit freundlichen Grüßen"
        ),
    },
    InquiryStatus.UNREACHABLE: {
        "label": gettext_lazy("Closing — unreachable"),
        "subject": "Letzte Nachricht — Schließung der Anfrage",
        "body": (
            "Guten Tag,\n\n"
            "ich habe mehrfach versucht, Sie zu erreichen, leider ohne Erfolg. "
            "Ich werde die Anfrage daher vorerst schließen.\n\n"
            "Sollten Sie weiterhin Interesse haben, steht es Ihnen jederzeit frei, "
            "sich erneut bei mir zu melden.\n\n"
            "Mit freundlichen Grüßen"
        ),
    },
}
