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
        else:
            request.current_practice = None

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


class TwoFactorRequiredMiddleware:
    """
    With REQUIRE_TWO_FACTOR on, send a signed-in user who has no confirmed
    authenticator to the setup page until they add one.

    Opt-in because an instance on a home network behind its own login may not
    want it; a hosted instance reachable from the internet should turn it on.
    """

    # The pages the setup itself needs, plus signing out and switching language.
    ALLOWED_URL_NAMES = {"two_factor_settings", "logout", "set_language", "login", "login_verify"}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        from django.conf import settings
        from django.shortcuts import redirect

        if not settings.REQUIRE_TWO_FACTOR or not request.user.is_authenticated:
            return None
        if request.resolver_match and request.resolver_match.url_name in self.ALLOWED_URL_NAMES:
            return None
        from my_practice.models import TwoFactorDevice

        if TwoFactorDevice.objects.filter(user=request.user, confirmed_at__isnull=False).exists():
            return None
        return redirect("two_factor_settings")
