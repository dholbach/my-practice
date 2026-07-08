"""Email sending views for invoices."""

import logging
from datetime import date

from django.conf import settings
from django.contrib import messages
from django.core.mail import EmailMessage
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _
from django.views import View

from ..email_forms import InvoiceEmailForm
from ..models import Client, Invoice, Practice
from ..utils.email_utils import (
    get_contract_email_content,
    get_intake_email_content,
    get_invoice_email_content,
    get_questionnaire_email_content,
)
from .api_views import (
    _prepare_practice_images,
    _render_invoice_pdf_bytes,
    generate_contract_pdf_bytes,
    generate_intake_form_pdf_bytes,
)

logger = logging.getLogger("my_practice.email")


# ── Module-level helpers ────────────────────────────────────────────────────


def _make_from_email(practice: Practice) -> str:
    """Build a From address, optionally with a display name."""
    if practice.email_from_name:
        return f"{practice.email_from_name} <{practice.email}>"
    return practice.email


def _dispatch_email(
    request: HttpRequest,
    msg: "EmailMessage",
    *,
    success_html: str,
    redirect_url: str,
) -> HttpResponse:
    """
    Send *msg*, set a Django message for the result, and redirect.

    Returns an HttpResponse redirect in all cases (success, soft failure,
    or exception), so callers can ``return _dispatch_email(...)`` directly.
    """
    try:
        result = msg.send()
        if result == 1:
            messages.success(request, mark_safe(success_html))
        else:
            messages.error(
                request, _("Email sending failed (result: %(result)s).") % {"result": result}
            )
    except Exception as e:
        logger.exception(f"Failed to send email: {e}")
        messages.error(request, _("Error while sending: %(error)s") % {"error": e})
    return redirect(redirect_url)


# ── Base class ──────────────────────────────────────────────────────────────


class BaseClientEmailView(View):
    """
    Shared scaffolding for client-scoped email views.

    Handles: client/practice lookup, missing-practice guard, missing-email
    guard, form init (GET) and form validation + dispatch (POST).

    Subclasses must set ``template_name`` and implement
    ``get_default_content`` and ``get_success_html``.
    """

    template_name: str

    # ── hooks ──────────────────────────────────────────────────────────────

    def get_default_content(self, client: Client, practice: Practice) -> tuple[str, str]:
        """Return ``(subject, body)`` for the pre-filled form."""
        raise NotImplementedError

    def get_success_html(self, recipient: str) -> str:
        """Return safe HTML for the success flash message."""
        raise NotImplementedError

    def get_extra_context(self, client: Client, practice: Practice) -> dict:
        """Additional template context beyond ``{client, form}``."""
        return {}

    def get_attachment(self, client: Client, practice: Practice) -> tuple[str, bytes, str] | None:
        """
        Return ``(filename, content_bytes, mimetype)`` or ``None`` for no attachment.
        Raise an exception to trigger an error message and redirect.
        """
        return None

    def extra_get_checks(
        self, request: HttpRequest, client: Client, practice: Practice, pk: int
    ) -> HttpResponse | None:
        """
        Optional extra validation before rendering the form on GET.
        Return an ``HttpResponse`` to abort early, or ``None`` to continue.
        """
        return None

    def after_send(self, client: Client) -> None:
        """Optional side-effect called just before the email is dispatched."""

    # ── shared machinery ───────────────────────────────────────────────────

    def _get_client_and_practice(
        self, request: HttpRequest, pk: int
    ) -> tuple[Client, Practice | None]:
        client = get_object_or_404(Client.objects.for_current_practice(request), pk=pk)
        practice = request.current_practice
        return client, practice

    def _redirect_to_detail(self, pk: int) -> HttpResponse:
        return redirect(reverse("client_detail", kwargs={"pk": pk}))

    def get(self, request: HttpRequest, pk: int) -> HttpResponse:
        client, practice = self._get_client_and_practice(request, pk)

        if not practice:
            messages.error(request, _("Practice settings not configured."))
            return self._redirect_to_detail(pk)

        if not client.email:
            messages.error(
                request,
                _("Client %(code)s has no email address on file.") % {"code": client.client_code},
            )
            return self._redirect_to_detail(pk)

        if early := self.extra_get_checks(request, client, practice, pk):
            return early

        subject, body = self.get_default_content(client, practice)
        form = InvoiceEmailForm(
            initial={"recipient": client.email, "subject": subject, "body": body}
        )
        ctx = {"client": client, "form": form, **self.get_extra_context(client, practice)}
        return render(request, self.template_name, ctx)

    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        client, practice = self._get_client_and_practice(request, pk)

        if not practice:
            messages.error(request, _("Practice settings not configured."))
            return self._redirect_to_detail(pk)

        form = InvoiceEmailForm(request.POST)
        if not form.is_valid():
            ctx = {"client": client, "form": form, **self.get_extra_context(client, practice)}
            return render(request, self.template_name, ctx)

        recipient = form.cleaned_data["recipient"]
        subject = form.cleaned_data["subject"]
        body = form.cleaned_data["body"]

        try:
            attachment = self.get_attachment(client, practice)
        except Exception as e:
            logger.exception(f"Attachment generation failed: {e}")
            messages.error(request, _("Error creating attachment: %(error)s") % {"error": e})
            return self._redirect_to_detail(pk)

        msg = EmailMessage(
            subject=subject,
            body=body,
            from_email=_make_from_email(practice),
            to=[recipient],
        )
        if attachment:
            fname, fbytes, fmime = attachment
            msg.attach(fname, fbytes, fmime)

        self.after_send(client)

        return _dispatch_email(
            request,
            msg,
            success_html=self.get_success_html(recipient),
            redirect_url=reverse("client_detail", kwargs={"pk": client.pk}),
        )


# ── Concrete email views ────────────────────────────────────────────────────


class SendInvoiceEmailView(View):
    """
    Send invoice email with two modes:
    - POST with 'quick': Send immediately with default template
    - GET or POST with 'customize': Show form for customization
    """

    def get(self, request: HttpRequest, invoice_id: int) -> HttpResponse:
        """Show email customization form"""
        invoice = get_object_or_404(Invoice.objects.for_current_practice(request), pk=invoice_id)
        practice = invoice.practice

        # Prevent sending if already sent
        if invoice.status == "sent":
            messages.warning(
                request,
                _("Invoice %(number)s has already been sent. Change the status to send it again.")
                % {"number": invoice.invoice_number},
            )
            return redirect("invoice_detail", pk=invoice_id)

        invoice.sync_invoice_date()

        # Generate default email content
        subject, body = get_invoice_email_content(invoice, practice)

        # Pre-fill form
        form = InvoiceEmailForm(
            initial={
                "recipient": invoice.client.email,
                "subject": subject,
                "body": body,
            }
        )

        context = {
            "invoice": invoice,
            "form": form,
        }

        return render(request, "my_practice/send_invoice_email.html", context)

    def post(self, request: HttpRequest, invoice_id: int) -> HttpResponse:
        """Send email - either quick or custom"""
        invoice = get_object_or_404(Invoice.objects.for_current_practice(request), pk=invoice_id)
        practice = invoice.practice

        # Prevent sending if already sent
        if invoice.status == "sent":
            messages.warning(
                request,
                _("Invoice %(number)s has already been sent. Change the status to send it again.")
                % {"number": invoice.invoice_number},
            )
            return redirect("invoice_detail", pk=invoice_id)

        # Check for quick send
        if "quick_send" in request.POST:
            return self._send_quick_email(request, invoice, practice)

        # Custom send with form validation
        form = InvoiceEmailForm(request.POST)
        if form.is_valid():
            return self._send_custom_email(request, invoice, practice, form)

        # Form validation failed
        context = {
            "invoice": invoice,
            "form": form,
        }
        return render(request, "my_practice/send_invoice_email.html", context)

    def _send_quick_email(
        self, request: HttpRequest, invoice: Invoice, practice: Practice
    ) -> HttpResponse:
        """Send email immediately with default template"""
        subject, body = get_invoice_email_content(invoice, practice)
        recipient = invoice.client.email

        return self._send_email(request, invoice, practice, recipient, subject, body)

    def _send_custom_email(
        self, request: HttpRequest, invoice: Invoice, practice: Practice, form: InvoiceEmailForm
    ) -> HttpResponse:
        """Send email with customized content from form"""
        recipient = form.cleaned_data["recipient"]
        subject = form.cleaned_data["subject"]
        body = form.cleaned_data["body"]

        return self._send_email(request, invoice, practice, recipient, subject, body)

    def _send_email(
        self,
        request: HttpRequest,
        invoice: Invoice,
        practice: Practice,
        recipient: str,
        subject: str,
        body: str,
    ) -> HttpResponse:
        """Send the invoice email with PDF attachment."""
        logger.info(f"Starting email send for invoice {invoice.invoice_number}")
        logger.info("Sending to recipient (subject length: %d chars)", len(subject))

        if invoice.sync_invoice_date():
            logger.info(f"Updated invoice date to {invoice.invoice_date}")
            messages.info(
                request,
                _("Invoice date was updated to %(date)s")
                % {"date": invoice.invoice_date.strftime("%d.%m.%Y")},
            )

        try:
            pdf_content = self._generate_pdf(invoice, practice)
            logger.info(f"PDF generated ({len(pdf_content)} bytes)")
        except Exception as e:
            logger.exception(f"PDF generation failed: {e}")
            messages.error(request, _("Error creating the PDF: %(error)s") % {"error": e})
            return redirect("invoice_detail", pk=invoice.id)

        filename = (
            f"Rechnung_{invoice.invoice_number}.pdf"
            if invoice.client.language == "de"
            else f"Invoice_{invoice.invoice_number}.pdf"
        )
        msg = EmailMessage(
            subject=subject,
            body=body,
            from_email=_make_from_email(practice),
            to=[recipient],
        )
        msg.attach(filename, pdf_content, "application/pdf")

        # _dispatch_email handles send + messages + redirect, but we need to
        # update invoice status on success — so we send manually and then use
        # the helper only for the error path.
        try:
            result = msg.send()
            logger.info(f"Email send result: {result}")
        except Exception as e:
            logger.exception(f"Exception while sending invoice email: {e}")
            messages.error(request, _("Error sending the email: %(error)s") % {"error": e})
            return redirect("invoice_detail", pk=invoice.id)

        if result == 1:
            if invoice.status == "draft":
                invoice.status = "sent"
                invoice.save()
                logger.info("Invoice status updated to 'sent'")
            messages.success(
                request,
                mark_safe(
                    _("✅ Invoice successfully sent to %(recipient)s")
                    % {"recipient": f'<span class="sensitive-data">{recipient}</span>'}
                ),
            )
        else:
            logger.error(f"Email send failed with result: {result}")
            messages.error(
                request, _("Email sending failed (result: %(result)s).") % {"result": result}
            )

        return redirect("invoice_detail", pk=invoice.id)

    def _generate_pdf(self, invoice: Invoice, practice: Practice) -> bytes:
        """Generate PDF bytes for invoice via shared api_views helpers."""
        logo_data, signature_data = _prepare_practice_images(practice)
        pdf_bytes, _filename = _render_invoice_pdf_bytes(
            invoice, practice, logo_data, signature_data
        )
        return pdf_bytes


class SendPaymentReminderView(BaseClientEmailView):
    """Send a payment reminder email listing all open (sent, not-yet-paid) invoices."""

    template_name = "my_practice/send_payment_reminder.html"

    def _get_open_invoices(self, client: Client, practice: Practice) -> list[Invoice]:
        # Cache per view instance (one instance per request) to avoid repeated DB queries
        # when both get_default_content and get_extra_context call this in the same request.
        if not hasattr(self, "_open_invoices_cache"):
            self._open_invoices_cache = list(
                Invoice.objects.filter(
                    client=client,
                    practice=practice,
                    status="sent",
                ).order_by("invoice_date")
            )
        return self._open_invoices_cache

    def extra_get_checks(
        self, request: HttpRequest, client: Client, practice: Practice, pk: int
    ) -> HttpResponse | None:
        if not self._get_open_invoices(client, practice):
            messages.warning(
                request,
                _("No open invoices for %(code)s.") % {"code": client.client_code},
            )
            return self._redirect_to_detail(pk)
        return None

    def get_default_content(self, client: Client, practice: Practice) -> tuple[str, str]:
        open_invoices = self._get_open_invoices(client, practice)
        return self._build_email_content(client, practice, open_invoices)

    def get_extra_context(self, client: Client, practice: Practice) -> dict:
        open_invoices = self._get_open_invoices(client, practice)
        total = sum(float(inv.total) for inv in open_invoices)
        return {
            "open_invoices": open_invoices,
            "open_invoices_total": total,
        }

    def get_success_html(self, recipient: str) -> str:
        return _("✅ Payment reminder sent to %(recipient)s") % {
            "recipient": f'<span class="sensitive-data">{recipient}</span>'
        }

    def _build_email_content(
        self, client: Client, practice: Practice, open_invoices: list[Invoice]
    ) -> tuple[str, str]:
        """Build default subject and body for the payment reminder."""
        total = sum(float(inv.total) for inv in open_invoices)
        count = len(open_invoices)
        lang = client.language  # 'de' or 'en'

        lines = []

        # Invoice table (shared by both languages)
        max_num_len = max(len(inv.invoice_number) for inv in open_invoices)
        invoice_rows = []
        for inv in open_invoices:
            num = inv.invoice_number.ljust(max_num_len)
            date_str = inv.invoice_date.strftime("%d.%m.%Y")
            invoice_rows.append(f"  {num}  {date_str}  {float(inv.total):,.2f} €".replace(",", "."))

        if lang == "en":
            invoice_word = "invoice" if count == 1 else "invoices"
            lines.append(client.salutation + "," if client.salutation else "Hi,")
            lines.append("")
            lines.append(
                f"Can you take a look and see if you received {'this invoice' if count == 1 else 'these invoices'}?"
            )
            lines.append("")
            lines.extend(invoice_rows)
            lines.append("")
            lines.append(f"Total outstanding: {total:,.2f} €".replace(",", "."))
            lines.append("")
            lines.append(
                "I'm happy to re-send if they got lost in transit. "
                "If I made a mistake and missed your payment, please disregard. "
                "Otherwise please transfer the amount to the usual bank account:"
            )
            if practice.iban:
                lines.append(f"  {practice.bank_name}: {practice.iban}")
                if practice.bic:
                    lines.append(f"  BIC: {practice.bic}")
            lines.append("")
            lines.append("All the best,")
            lines.append("-- ")
            lines.append(practice.email_signature)
            subject = f"Payment Reminder – {count} outstanding {invoice_word}"
        else:
            # German (default)
            rechnung_pl = "Rechnungen" if count != 1 else "Rechnung"
            lines.append(client.salutation + "," if client.salutation else "Hallo,")
            lines.append("")
            lines.append(
                f"kannst du mal schauen, ob du {'diese Rechnungen' if count != 1 else 'diese Rechnung'} erhalten hast?"
            )
            lines.append("")
            lines.extend(invoice_rows)
            lines.append("")
            lines.append(f"Gesamtbetrag offen: {total:,.2f} €".replace(",", "."))
            lines.append("")
            lines.append(
                "Ich schicke sie gerne noch einmal, falls sie verloren gegangen sind. "
                "Falls ich einen Fehler gemacht habe und deine Zahlung übersehen habe, bitte einfach ignorieren. "
                "Ansonsten bitte den Betrag auf das übliche Konto überweisen:"
            )
            if practice.iban:
                lines.append(f"  {practice.bank_name}: {practice.iban}")
                if practice.bic:
                    lines.append(f"  BIC: {practice.bic}")
            lines.append("")
            lines.append("Liebe Grüße,")
            lines.append("-- ")
            lines.append(practice.email_signature)
            subject = f"Zahlungserinnerung – {count} offene {rechnung_pl}"

        return subject, "\n".join(lines)


class SendCancellationEmailView(BaseClientEmailView):
    """Send a session-cancellation-due-to-illness email to a client."""

    template_name = "my_practice/send_cancellation_email.html"

    def get_default_content(self, client: Client, practice: Practice) -> tuple[str, str]:
        lang = client.language
        first_name = client.full_name.split()[0] if client.full_name else client.client_code
        if client.salutation:
            greeting = client.salutation + ","
        elif lang == "en":
            greeting = f"Dear {first_name},"
        else:
            greeting = f"Liebe/r {first_name},"

        if lang == "en":
            subject = "Cancellation of tomorrow's session"
            lines = [
                greeting,
                "",
                (
                    "Unfortunately I will have to cancel tomorrow's session due to illness. "
                    "I expect to be well again the following week. "
                    "We can already arrange a new appointment."
                ),
                "",
                "All the best,",
            ]
        else:
            subject = "Absage unserer morgigen Sitzung"
            lines = [
                greeting,
                "",
                (
                    "Leider werde ich unsere morgige Sitzung aus Krankheitsgründen absagen müssen. "
                    "Ich denke aber, dass ich in der darauffolgenden Woche wieder gesund sein werde. "
                    "Wir können auch gleich schon einen neuen Termin ausmachen."
                ),
                "",
                "Liebe Grüße und alles Gute,",
            ]

        if practice.email_signature:
            lines += ["-- ", practice.email_signature]

        return subject, "\n".join(lines)

    def get_success_html(self, recipient: str) -> str:
        return _("✅ Cancellation sent to %(recipient)s") % {
            "recipient": f'<span class="sensitive-data">{recipient}</span>'
        }


class SendQuestionnaireEmailView(BaseClientEmailView):
    """Send the Anamnesebogen .docx as an email attachment with editable body."""

    template_name = "my_practice/send_questionnaire_email.html"

    def _get_docx(self, lang: str) -> tuple[str, bytes] | None:
        """Return (filename, bytes) for the docx, or None if not found."""
        docx_name = "Anamnesebogen.docx" if lang == "de" else "Anamnesebogen (eng).docx"
        docx_path = settings.PAYMENTS_DATA_DIR / "documents" / docx_name
        if not docx_path.exists():
            return None
        return docx_name, docx_path.read_bytes()

    def extra_get_checks(
        self, request: HttpRequest, client: Client, practice: Practice, pk: int
    ) -> HttpResponse | None:
        lang = client.language or "de"
        if self._get_docx(lang) is None:
            docx_name = "Anamnesebogen.docx" if lang == "de" else "Anamnesebogen (eng).docx"
            messages.error(
                request,
                _(
                    "File not found: %(path)s. "
                    "Please place the .docx file under PAYMENTS_DATA_DIR/documents/."
                )
                % {"path": settings.PAYMENTS_DATA_DIR / "documents" / docx_name},
            )
            return self._redirect_to_detail(pk)
        return None

    def get_default_content(self, client: Client, practice: Practice) -> tuple[str, str]:
        return get_questionnaire_email_content(client, practice)

    def get_extra_context(self, client: Client, practice: Practice) -> dict:
        result = self._get_docx(client.language or "de")
        return {"docx_name": result[0] if result else ""}

    def get_attachment(self, client: Client, practice: Practice) -> tuple[str, bytes, str] | None:
        lang = client.language or "de"
        result = self._get_docx(lang)
        if result is None:
            docx_name = "Anamnesebogen.docx" if lang == "de" else "Anamnesebogen (eng).docx"
            raise FileNotFoundError(
                _("File not found: %(path)s.")
                % {"path": settings.PAYMENTS_DATA_DIR / "documents" / docx_name}
            )
        docx_name, docx_bytes = result
        return (
            docx_name,
            docx_bytes,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

    def after_send(self, client: Client) -> None:
        client.questionnaire_sent_date = date.today()
        client.save(update_fields=["questionnaire_sent_date"])

    def get_success_html(self, recipient: str) -> str:
        return _("✅ Questionnaire sent to %(recipient)s") % {
            "recipient": f'<span class="sensitive-data">{recipient}</span>'
        }


class SendContractEmailView(BaseClientEmailView):
    """Email the pre-filled Behandlungsvertrag PDF to the client for signing."""

    template_name = "my_practice/send_contract_email.html"

    def _get_filename(self, client: Client) -> str:
        lang = client.language or "de"
        safe_code = client.client_code.replace("/", "-")
        return (
            f"Behandlungsvertrag_{safe_code}.pdf"
            if lang == "de"
            else f"TreatmentContract_{safe_code}.pdf"
        )

    def get_default_content(self, client: Client, practice: Practice) -> tuple[str, str]:
        return get_contract_email_content(client, practice)

    def get_extra_context(self, client: Client, practice: Practice) -> dict:
        return {"filename": self._get_filename(client)}

    def get_attachment(self, client: Client, practice: Practice) -> tuple[str, bytes, str] | None:
        lang = client.language or "de"
        pdf_bytes, _filename = generate_contract_pdf_bytes(client, practice, lang)
        return (self._get_filename(client), pdf_bytes, "application/pdf")

    def get_success_html(self, recipient: str) -> str:
        return _("✅ Treatment contract sent to %(recipient)s") % {
            "recipient": f'<span class="sensitive-data">{recipient}</span>'
        }


class SendIntakeFormEmailView(BaseClientEmailView):
    """Email the pre-filled, fillable Aufnahmebogen PDF to the client."""

    template_name = "my_practice/send_intake_form_email.html"

    def _get_filename(self, client: Client) -> str:
        lang = client.language or "de"
        safe_code = client.client_code.replace("/", "-")
        return f"Aufnahmebogen_{safe_code}.pdf" if lang == "de" else f"IntakeForm_{safe_code}.pdf"

    def get_default_content(self, client: Client, practice: Practice) -> tuple[str, str]:
        return get_intake_email_content(client, practice)

    def get_extra_context(self, client: Client, practice: Practice) -> dict:
        return {"filename": self._get_filename(client)}

    def get_attachment(self, client: Client, practice: Practice) -> tuple[str, bytes, str] | None:
        lang = client.language or "de"
        pdf_bytes, _filename = generate_intake_form_pdf_bytes(client, practice, lang)
        return (self._get_filename(client), pdf_bytes, "application/pdf")

    def after_send(self, client: Client) -> None:
        client.intake_sent_date = date.today()
        client.save(update_fields=["intake_sent_date"])

    def get_success_html(self, recipient: str) -> str:
        return _("✅ Intake form sent to %(recipient)s") % {
            "recipient": f'<span class="sensitive-data">{recipient}</span>'
        }
