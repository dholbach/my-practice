"""
Base models and managers for practice-scoped data.

Provides QuerySet and Manager classes that automatically filter
by practice, enabling multi-practice data separation.

Models without a practice are shared on purpose: TimeOff (the practitioner's
own absences, which affect every practice), ClientTag (a tag vocabulary; the
tagged clients are scoped), the operational checklists (instance-level backup
routines) and GebuhZiffer (a published fee schedule).
"""

from typing import TYPE_CHECKING, Any, TypeAlias

from django.db import models
from django.http import HttpRequest

if TYPE_CHECKING:
    from .practice import Practice


class _AllPractices:
    """Type of ALL_PRACTICES; see scope_to_practice()."""

    def __repr__(self) -> str:
        return "ALL_PRACTICES"


# Explicit request for data across every practice (e.g. income tax is per
# person, not per practice). Never the default: see scope_to_practice().
ALL_PRACTICES = _AllPractices()

# What every practice-scoped query helper takes: a practice, ALL_PRACTICES, or
# None (= nothing, see scope_to_practice).
PracticeScope: TypeAlias = "Practice | _AllPractices | None"


def scope_to_practice[QS: models.QuerySet[Any]](
    queryset: QS,
    practice: PracticeScope,
    field: str = "practice",
) -> QS:
    """Restrict ``queryset`` to one practice, failing closed.

    - a Practice: rows of that practice (via ``field``, e.g. "invoice__practice")
    - ALL_PRACTICES: every row — the caller has to ask for this explicitly
    - None: no rows. ``request.current_practice`` is None for a user with no
      practice; the old ``if practice: qs = qs.filter(...)`` pattern handed
      such a user every practice's figures instead of none.
    """
    if practice is ALL_PRACTICES:
        return queryset
    if practice is None:
        return queryset.none()
    return queryset.filter(**{field: practice})


class PracticeScopedQuerySet(models.QuerySet):
    """
    QuerySet for models that are scoped to a practice.

    Provides helper methods to filter by practice and ensures
    data isolation between practices.
    """

    def for_practice(self, practice: "Practice" | None) -> "PracticeScopedQuerySet":
        """
        Filter queryset to specific practice.

        Args:
            practice: Practice instance or None

        Returns:
            QuerySet filtered by practice
        """
        if practice is None:
            return self.none()
        return self.filter(practice=practice)

    def for_current_practice(self, request: HttpRequest) -> "PracticeScopedQuerySet":
        """
        Filter queryset by request's current practice.

        Args:
            request: HttpRequest with current_practice attribute

        Returns:
            QuerySet filtered by current practice, or empty if no practice
        """
        if hasattr(request, "current_practice") and request.current_practice:
            return self.for_practice(request.current_practice)
        return self.none()

    def for_current_practice_with_globals(self, request: HttpRequest) -> "PracticeScopedQuerySet":
        """
        Filter queryset by current practice OR global items (practice=NULL).

        Useful for models like ServiceType where some items (e.g., cancellation,
        initial_consultation) should be available across all practices.

        Args:
            request: HttpRequest with current_practice attribute

        Returns:
            QuerySet filtered by current practice OR practice=NULL
        """
        if hasattr(request, "current_practice") and request.current_practice:
            return self.filter(
                models.Q(practice=request.current_practice) | models.Q(practice__isnull=True)
            )
        # If no current practice, return only global items
        return self.filter(practice__isnull=True)


class PracticeScopedManager(models.Manager):
    """
    Manager for practice-scoped models.

    Returns PracticeScopedQuerySet for all queries, enabling
    practice filtering via .for_practice() and .for_current_practice().

    Subclasses using a custom QuerySet (e.g. with extra methods) should use
    Manager.from_queryset(MyQuerySet) — get_queryset() respects _queryset_class
    so that from_queryset() works correctly.
    """

    _queryset_class = PracticeScopedQuerySet

    def get_queryset(self) -> PracticeScopedQuerySet:
        """Return PracticeScopedQuerySet (or subclass when using from_queryset)."""
        return self._queryset_class(self.model, using=self._db)

    def for_practice(self, practice: "Practice" | None) -> PracticeScopedQuerySet:
        """
        Get queryset filtered by practice.

        Args:
            practice: Practice instance

        Returns:
            QuerySet filtered by practice
        """
        return self.get_queryset().for_practice(practice)

    def for_current_practice(self, request: HttpRequest) -> PracticeScopedQuerySet:
        """
        Get queryset filtered by request's current practice.

        Args:
            request: HttpRequest with current_practice attribute

        Returns:
            QuerySet filtered by current practice
        """
        return self.get_queryset().for_current_practice(request)

    def for_current_practice_with_globals(self, request: HttpRequest) -> PracticeScopedQuerySet:
        """
        Get queryset filtered by current practice OR global items (practice=NULL).

        Args:
            request: HttpRequest with current_practice attribute

        Returns:
            QuerySet filtered by current practice OR practice=NULL
        """
        return self.get_queryset().for_current_practice_with_globals(request)


class TimestampedModel(models.Model):
    """
    Abstract base for models that track creation and modification time.

    Use this as a base for all NEW models instead of defining
    created_at / updated_at inline. Example:

        class MyModel(TimestampedModel):
            name = models.CharField(max_length=100)
    """

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
