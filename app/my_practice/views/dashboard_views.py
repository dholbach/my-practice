"""
Dashboard views for the payments application.
"""

from datetime import date

from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from ..utils import DashboardContextAssembler


def home(_request: HttpRequest) -> HttpResponse:
    """Home page - redirect to dashboard"""
    return redirect("dashboard")


def dashboard(request: HttpRequest) -> HttpResponse:
    """Dashboard with statistics, widgets, and session heatmap."""
    today = date.today()
    context = DashboardContextAssembler(request, today=today).build()
    return render(request, "my_practice/dashboard.html", context)
