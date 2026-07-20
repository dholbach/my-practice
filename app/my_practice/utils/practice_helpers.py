"""
Practice-related utility functions for multi-practice support.
"""

from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect
from django.utils.translation import gettext as _


def get_current_practice(request):
    """
    Get current practice from request.

    Args:
        request: HttpRequest with current_practice attribute (set by middleware)

    Returns:
        Practice instance or None
    """
    return getattr(request, "current_practice", None)


def require_practice(view_func):
    """
    Decorator to ensure a practice is selected before accessing view.

    Redirects to practice selection page if no practice is set.

    Usage:
        @require_practice
        def my_view(request):
            practice = request.current_practice
            ...
    """

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not hasattr(request, "current_practice") or not request.current_practice:
            messages.error(request, _("Please select a practice."))
            return redirect("practice_select")
        return view_func(request, *args, **kwargs)

    return wrapper


def switch_practice(request, practice_slug):
    """
    Switch current practice by slug.

    Args:
        request: HttpRequest
        practice_slug: URL slug of practice to switch to

    Returns:
        True if successful, False if practice not found or user has no access
    """
    from my_practice.models import Practice

    if not request.user.is_authenticated:
        return False

    practice = Practice.objects.filter(
        slug=practice_slug, users=request.user, is_active=True
    ).first()

    if practice:
        request.session["current_practice_slug"] = practice.slug
        request.current_practice = practice
        return True

    return False


def get_user_practices(user):
    """
    Get all practices a user has access to.

    Args:
        user: User instance

    Returns:
        QuerySet of Practice objects (ordered by ownership, then name)
    """
    if not user.is_authenticated:
        return []

    return user.practices.filter(is_active=True).order_by("-memberships__is_owner", "name")


def is_practice_owner(user, practice):
    """
    Check if user is owner of practice.

    Args:
        user: User instance
        practice: Practice instance

    Returns:
        bool: True if user owns practice
    """
    if not user.is_authenticated or not practice:
        return False

    from my_practice.models import UserPractice

    return UserPractice.objects.filter(user=user, practice=practice, is_owner=True).exists()
