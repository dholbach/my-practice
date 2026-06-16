"""
Base helper classes for CSV imports.
Provides common functionality to reduce code duplication across import views.
"""

import csv
import io
from typing import TYPE_CHECKING, Any

from django.contrib import messages
from django.db import models
from django.http import HttpRequest

if TYPE_CHECKING:
    from ..models import Client


def build_client_map() -> dict[str, "Client"]:
    """
    Build a dictionary mapping client codes to Client instances.

    Optimized to only fetch necessary fields (id, client_code, full_name).

    Returns:
        Dict mapping client_code (str) -> Client instance

    Example:
        >>> client_map = build_client_map()
        >>> client = client_map.get('XX')  # Get client with code 'XX'
    """
    from ..models import Client

    return {
        client.client_code: client
        for client in Client.objects.only("id", "client_code", "full_name")
    }


class BaseCSVImporter:
    """
    Base class for CSV import views.
    Handles common CSV reading, error tracking, and success messages.

    Subclasses should override:
    - model: The Django model to import into
    - template_name: Template for the import form
    - success_redirect: URL name to redirect after success
    - get_stats(): Return context dict with existing data stats
    - process_row(row, row_num): Process a single CSV row
    """

    model: type[models.Model] | None = None
    template_name: str | None = None
    success_redirect: str | None = None

    def __init__(self, request: HttpRequest) -> None:
        self.request = request
        self.imported_count: int = 0
        self.updated_count: int = 0
        self.skipped_count: int = 0
        self.errors: list[str] = []

    def read_csv(self, csv_file: Any) -> csv.DictReader:
        """
        Read and parse CSV file.
        Returns csv.DictReader object.
        """
        decoded_file = csv_file.read().decode("utf-8")
        io_string = io.StringIO(decoded_file)
        return csv.DictReader(io_string)

    def add_error(self, row_num: int, message: str) -> None:
        """Add an error message for a specific row."""
        self.errors.append(f"Zeile {row_num}: {message}")

    def increment_imported(self) -> None:
        """Increment imported counter."""
        self.imported_count += 1

    def increment_updated(self) -> None:
        """Increment updated counter."""
        self.updated_count += 1

    def increment_skipped(self) -> None:
        """Increment skipped counter."""
        self.skipped_count += 1

    def show_results(self) -> None:
        """
        Display result messages to the user.
        Shows success/info/warning messages based on import results.
        """
        summary_parts = []
        if self.imported_count:
            summary_parts.append(f"{self.imported_count} neu importiert")
        if self.updated_count:
            summary_parts.append(f"{self.updated_count} aktualisiert")
        if self.skipped_count:
            summary_parts.append(f"{self.skipped_count} übersprungen")

        summary = ", ".join(summary_parts) if summary_parts else "Keine Daten importiert"

        if self.imported_count > 0 and not self.errors:
            messages.success(self.request, f"✓ {summary}!")
        elif self.errors:
            messages.warning(
                self.request,
                f"Import abgeschlossen: {summary}. {len(self.errors)} Fehler aufgetreten.",
            )
            # Show first 5-10 errors
            for error in self.errors[:10]:
                messages.error(self.request, error)
        else:
            messages.info(self.request, summary)

    def get_stats(self) -> dict[str, Any]:
        """
        Get statistics about existing data in database.
        Override in subclass to provide model-specific stats.
        Returns dict with context variables.
        """
        if not self.model:
            return {}

        total = self.model.objects.count()
        date_range = self.model.objects.aggregate(
            earliest=models.Min("date"), latest=models.Max("date")
        )
        return {
            "total": total,
            "date_range": date_range,
        }

    def process_row(self, row: dict[str, str], row_num: int) -> None:
        """
        Process a single CSV row.
        Override in subclass to implement row-specific logic.

        Args:
            row: Dict with CSV row data
            row_num: Row number (for error messages)

        Should call increment_imported/updated/skipped and add_error as needed.
        """
        raise NotImplementedError("Subclasses must implement process_row()")

    def process_csv(self, csv_file: Any) -> bool:
        """
        Main processing loop: read CSV and process each row.
        Returns True if successful, False if errors occurred.
        """
        try:
            reader = self.read_csv(csv_file)

            for row_num, row in enumerate(reader, start=2):
                try:
                    self.process_row(row, row_num)
                except Exception as e:
                    self.add_error(row_num, str(e))

            self.show_results()
            return len(self.errors) == 0

        except Exception as e:
            messages.error(self.request, f"Import-Fehler: {str(e)}")
            return False


class SimpleCSVImporter(BaseCSVImporter):
    """
    Simplified CSV importer for straightforward imports.

    Usage:
        importer = SimpleCSVImporter(request)
        importer.model = MyModel
        importer.success_redirect = 'my_list_view'

        if importer.process_csv(csv_file):
            return redirect(importer.success_redirect)
    """

    pass
