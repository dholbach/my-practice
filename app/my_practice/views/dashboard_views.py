"""
Dashboard views for the payments application.
"""

from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from ..utils import DashboardContextAssembler


def home(_request: HttpRequest) -> HttpResponse:
    """Home page - redirect to dashboard"""
    return redirect("dashboard")


def dashboard(request: HttpRequest) -> HttpResponse:
    """Dashboard with statistics, widgets, and session heatmap."""
    if request.current_practice is None:
        return redirect("practice_create")
    today = timezone.localdate()
    context = DashboardContextAssembler(request, today=today).build()
    return render(request, "my_practice/dashboard.html", context)
