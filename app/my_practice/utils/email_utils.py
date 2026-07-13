"""
Email utility functions for invoice sending.
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..models import Client, Invoice, Practice

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
    """Get default email content (subject, body) for sending the GAD-7 PDF.

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
