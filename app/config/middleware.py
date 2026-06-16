"""
Middleware for development cache control and practice scoping
"""

from django.utils.deprecation import MiddlewareMixin


class NoCacheMiddleware(MiddlewareMixin):
    """Disable caching in development"""

    def process_response(self, request, response):
        response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response["Pragma"] = "no-cache"
        response["Expires"] = "0"
        return response


class PracticeScopeMiddleware:
    """
    Automatically sets current practice in request based on:
    1. Session cookie ('current_practice_slug')
    2. User's default practice (first practice with ownership)
    3. First available practice

    Sets request.current_practice for use in views and templates.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            request.current_practice = self.get_practice(request)
            # Add unmatched bank transaction count for navigation badge
            request.unmatched_bank_count = self.get_unmatched_bank_count(request)
        else:
            request.current_practice = None
            request.unmatched_bank_count = 0

        response = self.get_response(request)
        return response

    def get_practice(self, request):
        """
        Get current practice for authenticated user.

        Priority:
        1. Session-stored practice slug
        2. User's first practice (where is_owner=True, then any)
        3. None if user has no practices
        """
        from my_practice.models import Practice

        # Try session first
        practice_slug = request.session.get("current_practice_slug")
        if practice_slug:
            practice = Practice.objects.filter(
                slug=practice_slug, users=request.user, is_active=True
            ).first()
            if practice:
                return practice

        # Fall back to user's default practice
        # Prefer owned practices, then any practice
        # Note: memberships__user filter is required to scope the join to current user
        owned_practice = request.user.practices.filter(
            is_active=True,
            memberships__user=request.user,
            memberships__is_owner=True,
        ).first()
        if owned_practice:
            # Store in session for next request
            request.session["current_practice_slug"] = owned_practice.slug
            return owned_practice

        # Any active practice
        any_practice = request.user.practices.filter(is_active=True).first()
        if any_practice:
            request.session["current_practice_slug"] = any_practice.slug
            return any_practice

        return None

    def get_unmatched_bank_count(self, request):
        """
        Count unmatched bank transactions for navigation badge.

        Returns:
            int: Number of unprocessed, unmatched transactions (excludes ignored)
        """
        if not request.current_practice:
            return 0

        from my_practice.models import BankTransaction

        return (
            BankTransaction.objects.filter(
                practice=request.current_practice,
                processed=False,
                matched_invoice__isnull=True,
            )
            .exclude(match_confidence="ignored")
            .count()
        )
