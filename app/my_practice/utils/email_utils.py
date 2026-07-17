"""
Email utility functions for invoice sending.
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..models import Client, Invoice, Practice, TimeOff

_GERMAN_MONTHS = {
    1: "Januar",
    2: "Februar",
    3: "März",
    4: "April",
    5: "Mai",
    6: "Juni",
    7: "Juli",
    8: "August",
    9: "September",
    10: "Oktober",
    11: "November",
    12: "Dezember",
}

_GERMAN_WEEKDAYS_ABBR = {0: "Mo", 1: "Di", 2: "Mi", 3: "Do", 4: "Fr", 5: "Sa", 6: "So"}


def _build_sessions_intro(invoice: "Invoice", language: str) -> str:
    """Return an opening sentence summarising which sessions the invoice covers.

    Returns text with a trailing newline pair (ready to embed in a template block)
    or empty string if no sessions are attached to the invoice.
    """
    from datetime import date

    session_dates = [
        item.session.session_date
        for item in invoice.items.select_related("session").all()
        if item.session_id
    ]

    if not session_dates:
        return ""

    months = {(d.year, d.month) for d in session_dates}

    if len(months) == 1:
        year, month = next(iter(months))
        n = len(session_dates)
        if language == "en":
            month_name = date(year, month, 1).strftime("%B")
            session_word = "session" if n == 1 else "sessions"
            sentence = f"Here is the invoice for our {session_word} in {month_name}."
        else:
            month_name = _GERMAN_MONTHS[month]
            session_word = "Sitzung" if n == 1 else "Sitzungen"
            sentence = f"Anbei die Rechnung für unsere {session_word} im {month_name}."
    else:
        n = len(session_dates)
        if language == "en":
            session_word = "session" if n == 1 else "sessions"
            sentence = f"Here is the invoice for our last {n} {session_word}."
        else:
            session_word = "Sitzung" if n == 1 else "Sitzungen"
            sentence = f"Anbei die Rechnung für unsere letzten {n} {session_word}."

    return sentence + "\n\n"


def get_salutation_for_client(client: "Client") -> str:
    """
    Get email salutation for a client.
    Returns custom salutation if set, otherwise generates fallback.

    Fallback patterns:
    - EN: "Dear {name}"
    - DE: "Liebe:r {name}" (intentionally awkward to encourage manual setting)
    """
    if client.salutation:
        return client.salutation

    # Generate fallback - intentionally generic to encourage customization
    first_name = client.full_name.split()[0] if client.full_name else "Client"

    if client.language == "en":
        return f"Dear {first_name}"
    else:  # de
        return f"Liebe:r {first_name}"


def render_email_template(template_text: str, context: dict[str, Any]) -> str:
    """
    Render email template by replacing placeholders.

    Supported placeholders:
    - {salutation}: Client salutation
    - {invoice_number}: Invoice number
    - {amount}: Formatted amount with currency
    - {date}: Formatted date
    - {client_name}: Client full name
    """
    return template_text.format(**context)


def prepare_invoice_email_context(
    invoice: "Invoice", practice: "Practice", custom_salutation: str | None = None
) -> dict[str, str]:
    """
    Prepare context dict for invoice email templates.

    Args:
        invoice: Invoice instance
        practice: Practice instance
        custom_salutation: Optional custom salutation override

    Returns:
        dict with all template placeholders
    """
    # Get or generate salutation
    if custom_salutation:
        salutation = custom_salutation
    else:
        salutation = get_salutation_for_client(invoice.client)

    # Format amount
    amount_formatted = f"{invoice.total:.2f} €"

    # Format date
    date_formatted = invoice.invoice_date.strftime("%d.%m.%Y")

    return {
        "salutation": salutation,
        "invoice_number": invoice.invoice_number,
        "amount": amount_formatted,
        "date": date_formatted,
        "client_name": invoice.client.full_name,
    }


def get_invoice_email_content(
    invoice: "Invoice", practice: "Practice", custom_message: str | None = None
) -> tuple[str, str]:
    """
    Get complete email content (subject, body) for an invoice.

    Args:
        invoice: Invoice instance
        practice: Practice instance
        custom_message: Optional custom message to append to body

    Returns:
        tuple: (subject, body)
    """
    # Determine language
    language = invoice.client.language

    # Get templates based on language
    if language == "en":
        subject_template = practice.invoice_email_subject_en
        body_template = practice.invoice_email_body_en
    else:  # de
        subject_template = practice.invoice_email_subject_de
        body_template = practice.invoice_email_body_de

    # Prepare context
    context = prepare_invoice_email_context(invoice, practice)
    context["sessions_intro"] = _build_sessions_intro(invoice, language)

    # Render templates
    subject = render_email_template(subject_template, context)
    body = render_email_template(body_template, context)

    # Add custom message if provided
    if custom_message:
        body = body + "\n\n" + custom_message

    # Add signature with standard email delimiter
    body = body + "\n\n-- \n" + practice.email_signature

    return subject, body


def get_questionnaire_email_content(client: "Client", practice: "Practice") -> tuple[str, str]:
    """
    Get default email content (subject, body) for sending the Anamnesebogen.

    Returns:
        tuple: (subject, body)
    """
    salutation = get_salutation_for_client(client)

    if client.language == "en":
        subject = "Questionnaire"
        body = (
            f"{salutation},\n\n"
            "Here is also the questionnaire I mentioned in one of our previous sessions.\n\n"
            "For me it will be helpful to have some background information. "
            "The important things: if it takes a while to fill out, that's fine. "
            "I'd also leave it to you to decide where you would like to offer more and where less detail. "
            "Also if any of the questions should be emotionally too taxing in the moment or if you prefer "
            "to talk about it at some stage during our sessions, that's fine as well.\n\n"
            "Thanks in any case in advance."
        )
    else:
        subject = "Anamnesebogen"
        body = (
            f"{salutation},\n\n"
            "anbei auch der Anamnesebogen, den ich in einer unserer letzten Sitzungen erwähnt hatte.\n\n"
            "Für mich ist es hilfreich, einige Hintergrundinformationen zu haben. "
            "Das Wichtigste: Wenn das Ausfüllen eine Weile dauert, ist das völlig in Ordnung. "
            "Ich überlasse dir auch gerne, wo du mehr und wo du weniger ins Detail gehst. "
            "Und falls einzelne Fragen gerade emotional zu belastend sein sollten oder du es vorziehst, "
            "darüber im Laufe unserer Sitzungen zu sprechen, ist das selbstverständlich auch kein Problem.\n\n"
            "Vielen Dank schon im Voraus."
        )

    if practice.email_signature:
        body = body + "\n\n-- \n" + practice.email_signature

    return subject, body


def get_intake_email_content(client: "Client", practice: "Practice") -> tuple[str, str]:
    """Get default email content (subject, body) for sending the Aufnahmebogen.

    Returns:
        tuple: (subject, body)
    """
    salutation = get_salutation_for_client(client)

    if client.language == "en":
        subject = "Intake Form"
        body = (
            f"{salutation},\n\n"
            "please find attached the intake form for our work together. "
            "Some details are already pre-filled — you can complete the rest "
            "directly in the PDF or by hand. "
            "Please send it back to me or simply bring it to our next session.\n\n"
            "Feel free to get in touch at any time if you have any questions."
        )
    else:
        subject = "Aufnahmebogen"
        body = (
            f"{salutation},\n\n"
            "anbei findest du den Aufnahmebogen für unsere Zusammenarbeit. "
            "Einige Angaben sind bereits vorausgefüllt — den Rest kannst du "
            "direkt im PDF oder handschriftlich ergänzen. "
            "Bitte sende ihn mir zurück oder bring ihn einfach zur nächsten Sitzung mit.\n\n"
            "Bei Fragen melde dich gerne jederzeit."
        )

    if practice.email_signature:
        body = body + "\n\n-- \n" + practice.email_signature

    return subject, body


def get_gdpr_deletion_email_content(client: "Client", practice: "Practice") -> tuple[str, str]:
    """Return (subject, body) for the GDPR Art. 17 data-deletion notification email."""
    salutation = get_salutation_for_client(client)

    if client.language == "en":
        subject = "Deletion of your personal data"
        body = (
            f"{salutation},\n\n"
            "pursuant to Art. 17 GDPR (right to erasure) I would like to inform you that "
            "your personal data held by my practice has been deleted following the expiry "
            "of the statutory 10-year retention period.\n\n"
            "I hope you are well."
        )
    else:
        subject = "Löschung Ihrer gespeicherten Daten"
        body = (
            f"{salutation},\n\n"
            "gemäß Art. 17 DSGVO (Recht auf Löschung) möchte ich Sie darüber informieren, "
            "dass Ihre bei mir gespeicherten personenbezogenen Daten nach Ablauf der "
            "gesetzlichen Aufbewahrungsfrist von 10 Jahren gelöscht wurden.\n\n"
            "Ich hoffe, es geht Ihnen gut."
        )

    if practice.email_signature:
        body = body + "\n\n-- \n" + practice.email_signature

    return subject, body


def get_questionnaire_pdf_email_content(client: "Client", practice: "Practice") -> tuple[str, str]:
    """Get default email content (subject, body) for sending a questionnaire PDF.

    Returns:
        tuple: (subject, body)
    """
    salutation = get_salutation_for_client(client)

    if client.language == "en":
        subject = "Questionnaire"
        body = (
            f"{salutation},\n\n"
            "please find attached a short questionnaire. You can fill it in "
            "directly in the PDF or by hand. "
            "Please send it back to me or simply bring it to our next session.\n\n"
            "Feel free to get in touch at any time if you have any questions."
        )
    else:
        subject = "Fragebogen"
        body = (
            f"{salutation},\n\n"
            "anbei findest du einen kurzen Fragebogen. Du kannst ihn direkt "
            "im PDF oder handschriftlich ausfüllen. "
            "Bitte sende ihn mir zurück oder bring ihn einfach zur nächsten Sitzung mit.\n\n"
            "Bei Fragen melde dich gerne jederzeit."
        )

    if practice.email_signature:
        body = body + "\n\n-- \n" + practice.email_signature

    return subject, body


def get_contract_email_content(client: "Client", practice: "Practice") -> tuple[str, str]:
    """Get default email content (subject, body) for sending the Behandlungsvertrag.

    Returns:
        tuple: (subject, body)
    """
    salutation = get_salutation_for_client(client)

    if client.language == "en":
        subject = "Treatment Contract"
        body = (
            f"{salutation},\n\n"
            "please find attached the therapy agreement for our work together. "
            "It covers key aspects such as confidentiality and data protection. "
            "Please read it at your leisure, sign it, and send it back to me — "
            "or simply bring it to our next session.\n\n"
            "Feel free to get in touch at any time if you have any questions."
        )
    else:
        subject = "Behandlungsvertrag"
        body = (
            f"{salutation},\n\n"
            "anbei findest du den Behandlungsvertrag für unsere Zusammenarbeit. "
            "Er deckt grundlegende Aspekte wie Verschwiegenheit und Datenschutz ab. "
            "Bitte lies ihn in Ruhe durch, unterschreibe ihn und sende ihn mir zurück — "
            "oder bring ihn einfach zur nächsten Sitzung mit.\n\n"
            "Bei Fragen melde dich gerne jederzeit."
        )

    if practice.email_signature:
        body = body + "\n\n-- \n" + practice.email_signature

    return subject, body


def _ordinal_suffix_en(day: int) -> str:
    if 11 <= (day % 100) <= 13:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")


def _same_month(t: "TimeOff") -> bool:
    return (t.start_date.year, t.start_date.month) == (t.end_date.year, t.end_date.month)


def _format_period_subject_en(t: "TimeOff") -> str:
    """Compact date range for the subject line, e.g. '24-28th July' or '30th Jun-2nd Jul'."""
    start, end = t.start_date, t.end_date
    end_str = f"{end.day}{_ordinal_suffix_en(end.day)}"
    if _same_month(t):
        return f"{start.day}-{end_str} {end.strftime('%B')}"
    start_str = f"{start.day}{_ordinal_suffix_en(start.day)}"
    return f"{start_str} {start.strftime('%B')}-{end_str} {end.strftime('%B')}"


def _format_period_body_en(t: "TimeOff") -> str:
    """Weekday-annotated date range for the body, e.g. 'Fri 24th - Tue 28th July'."""
    start, end = t.start_date, t.end_date
    start_str = f"{start.strftime('%a')} {start.day}{_ordinal_suffix_en(start.day)}"
    end_str = f"{end.strftime('%a')} {end.day}{_ordinal_suffix_en(end.day)}"
    if _same_month(t):
        return f"{start_str} - {end_str} {end.strftime('%B')}"
    return f"{start_str} {start.strftime('%B')} - {end_str} {end.strftime('%B')}"


def _format_period_subject_de(t: "TimeOff") -> str:
    """Compact date range for the subject line, e.g. '24.-28. Juli' or '30. Juni-2. Juli'."""
    start, end = t.start_date, t.end_date
    if _same_month(t):
        return f"{start.day}.-{end.day}. {_GERMAN_MONTHS[end.month]}"
    return f"{start.day}. {_GERMAN_MONTHS[start.month]}-{end.day}. {_GERMAN_MONTHS[end.month]}"


def _format_period_body_de(t: "TimeOff") -> str:
    """Weekday-annotated date range for the body, e.g. 'Fr 24. - Di 28. Juli'."""
    start, end = t.start_date, t.end_date
    start_wd = _GERMAN_WEEKDAYS_ABBR[start.weekday()]
    end_wd = _GERMAN_WEEKDAYS_ABBR[end.weekday()]
    if _same_month(t):
        return f"{start_wd} {start.day}. - {end_wd} {end.day}. {_GERMAN_MONTHS[end.month]}"
    return (
        f"{start_wd} {start.day}. {_GERMAN_MONTHS[start.month]} - "
        f"{end_wd} {end.day}. {_GERMAN_MONTHS[end.month]}"
    )


def get_timeoff_notice_default_content(
    time_offs: list["TimeOff"], practice: "Practice"
) -> tuple[str, str, str, str]:
    """Get default bilingual email content for a time-off heads-up notice.

    Accepts one or more time-off periods (e.g. several separate holidays
    announced in a single email) and summarises them either as a single
    date range (one period) or a bulleted list of ranges (several periods).

    Content is deliberately date-only, not title-based: clients don't need to
    know what the practitioner is doing with the time, just which dates and
    weekdays are affected, so they can scan for their own recurring slot.

    Unlike the other builders here, this one is not rendered for a single client:
    it's used to pre-fill an editable multi-recipient form. The bodies contain a
    literal ``{salutation}`` placeholder that is filled in per-recipient at send
    time via render_email_template(), the same mechanism used for the
    DB-configurable invoice email templates above.

    Returns:
        tuple: (subject_de, body_de, subject_en, body_en)
    """
    subject_de = f"Praxis geschlossen: {', '.join(_format_period_subject_de(t) for t in time_offs)}"
    subject_en = f"Practice closed: {', '.join(_format_period_subject_en(t) for t in time_offs)}"

    if len(time_offs) == 1:
        periods_de = _format_period_body_de(time_offs[0])
        periods_en = _format_period_body_en(time_offs[0])
    else:
        periods_de = "\n".join(f"- {_format_period_body_de(t)}" for t in time_offs)
        periods_en = "\n".join(f"- {_format_period_body_en(t)}" for t in time_offs)

    body_de = (
        "{salutation},\n\n"
        "ich möchte dich frühzeitig informieren: Die Praxis ist geschlossen:\n\n"
        f"{periods_de}\n\n"
        "In dieser Zeit bin ich leider nicht erreichbar. Bei dringenden Anliegen "
        "melde dich bitte rechtzeitig vorher bei mir.\n\n"
        "Ich wünsche dir bis dahin alles Gute."
    )

    body_en = (
        "{salutation},\n\n"
        "I wanted to give you advance notice: the practice will be closed:\n\n"
        f"{periods_en}\n\n"
        "I won't be reachable during this time. If anything urgent comes up, "
        "please get in touch beforehand.\n\n"
        "All the best until then."
    )

    if practice.email_signature:
        body_de = body_de + "\n\n-- \n" + practice.email_signature
        body_en = body_en + "\n\n-- \n" + practice.email_signature

    return subject_de, body_de, subject_en, body_en
