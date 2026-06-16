"""
Google Calendar API utilities for OAuth2 and event parsing.
"""

from datetime import datetime
from typing import cast

from django.conf import settings
from django.utils import timezone
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from ..models import Client, GoogleCalendarToken, ServiceType

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


# Duration to ServiceType code mapping
DURATION_TO_SERVICE_CODE = {
    (14, 16): "therapy_15",  # 15min = Check-in
    (18, 22): "therapy_free",  # 20min = initial consultation
    (50, 65): "therapy_60",  # 50-60min = Standard session
    (80, 95): "therapy_90",  # 80-90min = Extended session
}


class GoogleCalendarOAuth:
    """Handle Google Calendar OAuth2 authentication flow."""

    @staticmethod
    def create_flow(redirect_uri: str) -> Flow:
        """
        Create OAuth2 flow instance with client credentials.

        Args:
            redirect_uri: The OAuth2 callback URI

        Returns:
            Configured Flow instance
        """
        client_config = {
            "web": {
                "client_id": settings.GOOGLE_CALENDAR_CLIENT_ID,
                "client_secret": settings.GOOGLE_CALENDAR_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect_uri],
            }
        }
        flow = Flow.from_client_config(client_config, scopes=SCOPES)
        flow.redirect_uri = redirect_uri
        return flow

    @staticmethod
    def save_token(credentials, practice=None) -> GoogleCalendarToken:
        """
        Save OAuth2 credentials to database.

        Args:
            credentials: OAuth2 Credentials object
            practice: Practice instance to associate with this token (required for
                      multi-practice setups; without it the management command
                      cannot fetch events for this practice)

        Returns:
            Created GoogleCalendarToken instance
        """
        # Deactivate old tokens for this practice (or all if practice is None)
        qs = GoogleCalendarToken.objects.filter(is_active=True)
        if practice is not None:
            qs = qs.filter(practice=practice)
        qs.update(is_active=False)

        # Convert expiry to timezone-aware datetime if present
        expires_at = None
        if credentials.expiry:
            expires_at = (
                timezone.make_aware(credentials.expiry)
                if timezone.is_naive(credentials.expiry)
                else credentials.expiry
            )

        # Store new token in database
        return GoogleCalendarToken.objects.create(
            token=credentials.token,
            refresh_token=credentials.refresh_token or "",
            token_uri=credentials.token_uri,
            client_id=credentials.client_id,
            client_secret=credentials.client_secret,
            scopes=credentials.scopes,
            expires_at=expires_at,
            is_active=True,
            practice=practice,
        )

    @staticmethod
    def get_service(practice=None):
        """
        Get authenticated Google Calendar API service.
        Automatically refreshes expired tokens.

        Args:
            practice: Optional Practice instance; when provided only that
                      practice's token is used.

        Returns:
            Google Calendar API service object or None if no valid token exists
        """
        try:
            token_qs = GoogleCalendarToken.objects.filter(is_active=True)
            if practice is not None:
                token_qs = token_qs.filter(practice=practice)
            token = token_qs.latest("created_at")

            # Proactively refresh if token expires within 5 minutes
            needs_refresh = False
            if token.expires_at:
                time_until_expiry = (token.expires_at - timezone.now()).total_seconds()
                needs_refresh = time_until_expiry < 300  # 5 minutes

            if (needs_refresh or token.is_expired) and token.refresh_token:
                # Refresh the token using Google's OAuth2 flow
                from google.auth.transport.requests import Request

                credentials = Credentials(
                    token=token.token,
                    refresh_token=token.refresh_token,
                    token_uri=token.token_uri,
                    client_id=token.client_id,
                    client_secret=token.client_secret,
                    scopes=token.scopes,
                )

                try:
                    credentials.refresh(Request())

                    # Update token in database
                    token.token = credentials.token or ""
                    if credentials.expiry:
                        token.expires_at = (
                            timezone.make_aware(credentials.expiry)
                            if timezone.is_naive(credentials.expiry)
                            else credentials.expiry
                        )
                    token.save(update_fields=["token", "expires_at"])

                except Exception as e:
                    # Token refresh failed — most likely the refresh_token itself
                    # has been revoked (Google limits unverified-app refresh tokens
                    # to 7 days).  Leave the token active so subsequent runs report
                    # the same clear error rather than "no active tokens found".
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.error(f"Token refresh failed: {e}")
                    return None

            # Build credentials
            credentials = Credentials(
                token=token.token,
                refresh_token=token.refresh_token,
                token_uri=token.token_uri,
                client_id=token.client_id,
                client_secret=token.client_secret,
                scopes=token.scopes,
            )

            return build("calendar", "v3", credentials=credentials)

        except GoogleCalendarToken.DoesNotExist:
            return None


class CalendarEventParser:
    """Parse Google Calendar events into structured data."""

    @staticmethod
    def map_duration_to_service_type(duration_minutes: int) -> tuple:
        """
        Map event duration to ServiceType object and description.

        Args:
            duration_minutes: Event duration in minutes

        Returns:
            Tuple of (ServiceType object, suggested_description) or (None, None)
        """
        for (min_dur, max_dur), service_code in DURATION_TO_SERVICE_CODE.items():
            if min_dur <= duration_minutes <= max_dur:
                service_type = ServiceType.objects.filter(code=service_code).first()
                if service_type:
                    return (service_type, service_type.name_de or service_type.name)
        return (None, None)

    @staticmethod
    def parse_datetime(date_str: str) -> datetime | None:
        """
        Parse ISO format datetime string.

        Args:
            date_str: ISO format datetime or date string

        Returns:
            Parsed datetime object or None on error
        """
        try:
            if "T" in date_str:  # DateTime
                return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            else:  # All-day event (date only)
                return datetime.fromisoformat(date_str)
        except Exception:
            return None

    @staticmethod
    def calculate_duration(start_dt: datetime | None, end_dt: datetime | None) -> int:
        """
        Calculate event duration in minutes.

        Args:
            start_dt: Event start datetime
            end_dt: Event end datetime

        Returns:
            Duration in minutes, or 0 if dates are invalid
        """
        if start_dt and end_dt:
            try:
                # Check if datetime has time component (not just date)
                if start_dt.hour or start_dt.minute or start_dt.second:
                    return int((end_dt - start_dt).total_seconds() / 60)
            except AttributeError:
                pass
        return 0

    @staticmethod
    def match_client(summary: str, clients=None) -> "Client | None":
        """
        Match client by client_code in event summary.

        Args:
            summary: Event title/summary
            clients: List/QuerySet of clients (fetched if not provided)

        Returns:
            Matched Client instance or None
        """
        if clients is None:
            # Use optimized query - only fetch needed fields
            clients = Client.objects.only("id", "client_code")

        summary_upper = summary.upper()
        for client in clients:
            if client.client_code and client.client_code.upper() in summary_upper:
                return cast(Client, client)
        return None

    @staticmethod
    def is_cancelled(summary: str) -> bool:
        """
        Check if event is cancelled.

        Args:
            summary: Event title/summary

        Returns:
            True if event contains cancel indicator
        """
        summary_lower = summary.lower()
        return "(cancel)" in summary_lower or "cancel" in summary_lower

    @staticmethod
    def is_blocked(summary: str) -> bool:
        """
        Check if event is a calendar block (unavailability placeholder).

        Events whose summary contains "blocked" are availability markers, not
        sessions, and should be ignored entirely.

        Args:
            summary: Event title/summary

        Returns:
            True if event is a blocking placeholder
        """
        return "blocked" in summary.lower()

    @classmethod
    def parse_event(cls, event: dict, clients=None) -> dict:
        """
        Parse a Google Calendar event into structured data.

        Args:
            event: Raw event dict from Google Calendar API
            clients: Optional QuerySet of clients for matching

        Returns:
            Dict with parsed event data:
                - original: Raw event dict
                - summary: Event title
                - start: Parsed start datetime
                - end: Parsed end datetime
                - duration_minutes: Duration in minutes
                - matched_client: Matched Client instance or None
                - is_cancelled: Boolean indicating if cancelled
                - suggested_service_type: Service type name or None
                - suggested_description: Description for the service or None
        """
        summary = event.get("summary", "")
        start_str = event["start"].get("dateTime", event["start"].get("date"))
        end_str = event["end"].get("dateTime", event["end"].get("date"))

        # Parse dates and duration
        start_dt = cls.parse_datetime(start_str)
        end_dt = cls.parse_datetime(end_str)
        duration_minutes = cls.calculate_duration(start_dt, end_dt)

        # Match client and check cancellation
        matched_client = cls.match_client(summary, clients)
        is_cancelled = cls.is_cancelled(summary)

        # Map duration to service type
        service_type_obj, description = cls.map_duration_to_service_type(duration_minutes)

        # Override for cancellations - try to find "cancel" service type
        if is_cancelled:
            cancel_service = ServiceType.objects.filter(code__icontains="cancel").first()
            if cancel_service:
                service_type_obj = cancel_service
                description = "Ausgefallener Termin"

        return {
            "id": event.get("id"),  # Add event ID for tracking
            "original": event,
            "summary": summary,
            "start": start_dt,
            "end": end_dt,
            "duration_minutes": duration_minutes,
            "matched_client": matched_client,
            "is_cancelled": is_cancelled,
            "suggested_service_type": description,
            "suggested_service_type_obj": service_type_obj,  # ServiceType object
        }

    @classmethod
    def parse_events(cls, events: list, clients=None) -> list:
        """
        Parse multiple Google Calendar events.

        Args:
            events: List of raw event dicts from Google Calendar API
            clients: Optional QuerySet of clients (fetched once if not provided)

        Returns:
            List of parsed event dicts
        """
        if clients is None:
            # Use optimized query - only fetch needed fields
            clients = Client.objects.only("id", "client_code")

        return [
            cls.parse_event(event, clients)
            for event in events
            if not cls.is_blocked(event.get("summary", ""))
        ]


def find_calendar_by_name(service, calendar_name: str) -> str | None:
    """
    Find calendar ID by name.

    Args:
        service: Google Calendar API service object
        calendar_name: Name of calendar to find (case-insensitive)

    Returns:
        Calendar ID or None if not found
    """
    try:
        calendar_list = service.calendarList().list().execute()
        calendar_name_lower = calendar_name.lower()

        for calendar_entry in calendar_list.get("items", []):
            if calendar_entry.get("summary", "").lower() == calendar_name_lower:
                return cast(str, calendar_entry["id"])
    except Exception:
        pass

    return None
