"""
Practice analysis utilities.

Provides analysis tools for practice planning, capacity management,
and client overview for a given time period.
"""

from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.db.models import FloatField, Sum
from django.db.models.functions import Cast

from ..models import Client, Invoice
from ..models.session import Session


class ClientClassification:
    """Classification of clients based on their activity."""

    PROBATORIC = "probatoric"  # < 5 sessions total (new clients)
    ACTIVE = "active"  # [Deprecated] Use ESTABLISHED or PROBATORIC instead
    ESTABLISHED = "established"  # >= 5 sessions total AND active in period
    DORMANT = "dormant"  # Has history but no sessions in current period


class PracticeAnalyzer:
    """
    Analyze practice data for a specific time period.

    Provides insights into client activity, capacity usage, and planning metrics.
    """

    def __init__(self, start_date, end_date, practice=None):
        """
        Initialize analyzer for a time period.

        Args:
            start_date (date): Start of analysis period
            end_date (date): End of analysis period
            practice: Practice instance to scope queries; None means all practices
        """
        self.start_date = start_date
        self.end_date = end_date
        self.practice = practice
        self.period_days = (end_date - start_date).days + 1

    def analyze(self):
        """
        Run complete analysis for the period.

        Returns:
            dict: Comprehensive analysis data
        """
        # Fetch all clients for this practice (including dormant — needed for full classification)
        clients = (
            Client.objects.filter(practice=self.practice) if self.practice else Client.objects.all()
        )

        # Get session data for period
        period_sessions = self._get_period_sessions()

        # Classify and analyze each client
        client_data = []
        online_count = 0
        active_count = 0  # Active = not dormant
        established_count = 0
        probatoric_count = 0
        dormant_count = 0

        for client in clients:
            client_info = self._analyze_client(client, period_sessions)
            if client_info:
                client_data.append(client_info)

                # Count classifications
                if client_info["classification"] == ClientClassification.ESTABLISHED:
                    established_count += 1
                    active_count += 1  # Established clients are active
                elif client_info["classification"] == ClientClassification.PROBATORIC:
                    probatoric_count += 1
                    active_count += 1  # Probatoric clients are active
                elif client_info["classification"] == ClientClassification.DORMANT:
                    dormant_count += 1

                if client_info["is_online"]:
                    online_count += 1

        # Get time off data
        timeoff_data = self._get_timeoff_data()

        # Calculate capacity metrics
        capacity = self._calculate_capacity(period_sessions)

        return {
            "period": {
                "start_date": self.start_date,
                "end_date": self.end_date,
                "days": self.period_days,
                "label": self._format_period_label(),
            },
            "clients": {
                "total": len(clients),
                "active_in_period": active_count,
                "established": established_count,
                "probatoric": probatoric_count,
                "dormant": dormant_count,
                "online": online_count,
                "list": sorted(client_data, key=lambda x: x["sessions_in_period"], reverse=True),
            },
            "capacity": capacity,
            "timeoff": timeoff_data,
            "summary": {
                "total_sessions_booked": sum(c["sessions_in_period"] for c in client_data),
                "average_sessions_per_client": (
                    sum(c["sessions_in_period"] for c in client_data) / len(client_data)
                    if client_data
                    else 0
                ),
            },
        }

    def analyze_with_insights(self):
        """Run analysis and generate insights."""
        analysis = self.analyze()
        analysis["insights"] = self.generate_insights(analysis)
        return analysis

    def _get_period_sessions(self) -> dict[int, float]:
        """
        Get total session hours per client for the period from Session objects.

        Returns dict mapping client_id -> hours (duration/60, not therapist-normalised
        so group-session clients are counted individually).
        """
        hours_by_client: dict[int, float] = {}
        practice_filter = {"client__practice": self.practice} if self.practice else {}
        qs = Session.objects.filter(
            session_date__gte=self.start_date,
            session_date__lte=self.end_date,
            cancelled=False,
            **practice_filter,
        ).values("client_id", "duration")
        for row in qs:
            hours_by_client[row["client_id"]] = (
                hours_by_client.get(row["client_id"], 0.0) + row["duration"] / 60.0
            )
        return hours_by_client

    def _analyze_client(self, client, period_sessions):
        """Analyze a single client for the period."""

        client_code = client.client_code
        sessions_in_period = period_sessions.get(client.id, 0.0)
        total_sessions_ever = self._get_total_sessions_for_client(client)

        # Skip clients with no history
        if total_sessions_ever == 0 and sessions_in_period == 0:
            return None

        # Classify and gather data
        classification = self._classify_client(sessions_in_period, total_sessions_ever)
        revenue_in_period = self._get_revenue_for_client(client)
        invoices_count = self._get_invoices_count_for_client(client)

        return {
            "client": client,
            "client_code": client_code,
            "client_name": client.full_name,
            "is_online": client.is_online_client,
            "sessions_in_period": sessions_in_period,
            "sessions_total": total_sessions_ever,
            "revenue_in_period": revenue_in_period,
            "classification": classification,
            "invoices_count": invoices_count,
        }

    def _get_total_sessions_for_client(self, client) -> float:
        """Get total non-cancelled session hours ever for a client."""
        result = Session.objects.filter(client=client, cancelled=False).aggregate(
            total=Sum(Cast("duration", FloatField()))
        )
        return (result["total"] or 0.0) / 60.0

    def _classify_client(self, sessions_in_period: float, total_sessions: float) -> str:
        """
        Classify client based on activity.

        Returns:
            ClientClassification: DORMANT, PROBATORIC, or ESTABLISHED
        """
        if sessions_in_period == 0:
            return ClientClassification.DORMANT
        elif total_sessions < 5:
            return ClientClassification.PROBATORIC
        else:
            # >= 5 sessions total AND active in period
            return ClientClassification.ESTABLISHED

    def _get_revenue_for_client(self, client) -> Decimal:
        """Get paid revenue for client in analysis period."""
        return Invoice.objects.filter(
            client=client,
            status="paid",
            invoice_date__gte=self.start_date,
            invoice_date__lte=self.end_date,
        ).aggregate(total=Sum("total"))["total"] or Decimal("0.00")

    def _get_invoices_count_for_client(self, client) -> int:
        """Get count of invoices for client in analysis period."""
        return Invoice.objects.filter(
            client=client,
            invoice_date__gte=self.start_date,
            invoice_date__lte=self.end_date,
        ).count()

    def _get_timeoff_data(self):
        """Get time off periods that overlap with analysis period."""
        from .timeoff_helpers import calculate_timeoff_for_period

        result = calculate_timeoff_for_period(self.start_date, self.end_date)
        return {
            "total_days": result["total_days"],
            "total_weeks": result["total_weeks"],
            "workdays": result["total_workdays"],
            "entries": result["entries"],
            "capacity_impact": f"{result['total_workdays']} Arbeitstage",
        }

    def _calculate_capacity(self, period_sessions):
        """Calculate capacity metrics for the period."""
        from .capacity_helpers import calculate_period_capacity

        # Use centralized capacity calculation
        # (Accounts for varying capacity over time and time off)
        return calculate_period_capacity(self.start_date, self.end_date)

    def _format_period_label(self):
        """Format a human-readable period label."""
        if self.start_date.year == self.end_date.year:
            if self.start_date.month == 1 and self.end_date.month == 12:
                return str(self.start_date.year)
            elif self.start_date.month == self.end_date.month:
                return self.start_date.strftime("%B %Y")
            else:
                return f"{self.start_date.strftime('%b')} - {self.end_date.strftime('%b %Y')}"
        else:
            return f"{self.start_date.strftime('%b %Y')} - {self.end_date.strftime('%b %Y')}"

    def generate_insights(self, analysis) -> list[str]:
        """Generate actionable insights from the analysis data."""
        clients = analysis["clients"]["list"]
        return (
            self._period_insights(analysis)
            + self._client_insights(clients)
            + self._capacity_insights(analysis["capacity"])
            + self._revenue_insights(clients)
        )

    def _period_insights(self, analysis) -> list[str]:
        insights = [
            f"📅 Analyzing {analysis['period']['label']} ({analysis['period']['days']} days)"
        ]
        active_count = analysis["clients"]["active_in_period"]
        total_count = analysis["clients"]["total"]
        if active_count > 0:
            active_pct = (active_count / total_count * 100) if total_count > 0 else 0
            insights.append(
                f"👥 {active_count} of {total_count} clients active ({active_pct:.0f}%)"
            )
        return insights

    def _client_insights(self, clients) -> list[str]:
        insights = []

        # Concentration
        if clients:
            total_sessions = sum(c["sessions_in_period"] for c in clients)
            if total_sessions > 0:
                top_3 = sum(c["sessions_in_period"] for c in clients[:3])
                concentration = (top_3 / total_sessions) * 100
                if concentration > 60:
                    insights.append(
                        f"⚠️ High concentration: Top 3 clients = {concentration:.0f}% of sessions"
                    )
                elif concentration > 40:
                    insights.append(
                        f"📊 Top 3 clients account for {concentration:.0f}% of sessions"
                    )

        # Average per active client
        active = [c for c in clients if c["classification"] in ["established", "probatoric"]]
        if active:
            avg = sum(c["sessions_in_period"] for c in active) / len(active)
            insights.append(f"📈 Average: {avg:.1f}h per active client")

        # Probatoric
        probatoric = [c for c in clients if c["classification"] == "probatoric"]
        if probatoric:
            ph = sum(c["sessions_in_period"] for c in probatoric)
            s = "s" if len(probatoric) != 1 else ""
            insights.append(f"🌱 {len(probatoric)} new probatoric client{s} ({ph:.1f}h)")

        # Dormant
        dormant = [c for c in clients if c["classification"] == "dormant"]
        if len(dormant) > 5:
            insights.append(f"💤 {len(dormant)} dormant clients (no activity this period)")

        return insights

    def _capacity_insights(self, capacity) -> list[str]:
        cap_pct = capacity["capacity_percentage"]
        rem = capacity["remaining_hours"]
        if cap_pct < 30:
            return [f"📉 Low utilization: Only {cap_pct}% capacity used ({rem:.0f}h available)"]
        if cap_pct < 60:
            return [f"📊 Moderate utilization: {cap_pct}% capacity used ({rem:.0f}h available)"]
        if cap_pct < 80:
            return [f"✅ Good utilization: {cap_pct}% capacity used ({rem:.0f}h available)"]
        if cap_pct < 100:
            return [f"⚠️ High utilization: {cap_pct}% capacity used (only {rem:.0f}h remaining)"]
        return [f"🔴 At/over capacity: {cap_pct}% utilized"]

    def _revenue_insights(self, clients) -> list[str]:
        unbilled = [c for c in clients if c["invoices_count"] == 0 and c["sessions_in_period"] > 0]
        if unbilled:
            return [
                f"💰 Revenue opportunity: {len(unbilled)} client(s) with sessions but no invoices"
            ]
        return []


def calculate_quarter_trends(target_date, practice=None):
    """Calculate capacity and activity trends for last 4 quarters ending with target_date."""
    trends: list[dict] = []

    # Get current quarter boundaries for target_date
    quarter = (target_date.month - 1) // 3
    quarter_end_month = quarter * 3 + 3

    # Determine last day of quarter end month
    if quarter_end_month in [4, 6, 9, 11]:
        last_day = 30
    elif quarter_end_month == 2:
        last_day = 29 if target_date.year % 4 == 0 else 28
    else:
        last_day = 31

    current_q_end = target_date.replace(month=quarter_end_month, day=last_day)

    # Go back 4 quarters
    for i in range(4):
        offset = 3 * i
        q_end = current_q_end - relativedelta(months=offset)
        # Start of quarter: first day of month, 2 months before end
        q_start = q_end.replace(day=1) - relativedelta(months=2)

        # Run analyzer for this quarter
        analyzer = PracticeAnalyzer(q_start, q_end, practice=practice)
        analysis = analyzer.analyze()

        trends.insert(
            0,
            {
                "label": analysis["period"]["label"],
                "capacity_percentage": analysis["capacity"]["capacity_percentage"],
                "active_clients": analysis["clients"]["active_in_period"],
                "total_sessions": analysis["summary"]["total_sessions_booked"],
                "timeoff_days": analysis["timeoff"]["workdays"],
            },
        )

    return trends
