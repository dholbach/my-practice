"""Tests for practice analysis utilities."""

from datetime import date
from decimal import Decimal

from django.test import TestCase
from my_practice.models import (
    Client,
    Invoice,
    InvoiceItem,
    Practice,
    ServiceType,
    Session,
    TimeOff,
)
from my_practice.utils.practice_analysis import (
    ClientClassification,
    PracticeAnalyzer,
    calculate_quarter_trends,
)


class PracticeAnalyzerTestCase(TestCase):
    """Tests for PracticeAnalyzer class"""

    def setUp(self):
        """Create test data"""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="practice_analysis-1",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        # Create service type
        self.service_type = ServiceType.objects.create(
            code="therapy_60",
            name="Session",
            name_de="Sitzung",
            name_en="Session",
            default_duration=60,
            practice=self.practice,
        )

        # Create clients
        self.established_client = Client.objects.create(
            client_code="EST",
            full_name="Established Client",
            email="est@test.com",
            language="de",
            practice=self.practice,
        )

        self.probatoric_client = Client.objects.create(
            client_code="PRO",
            full_name="Probatoric Client",
            email="pro@test.com",
            language="de",
            practice=self.practice,
        )

        self.dormant_client = Client.objects.create(
            client_code="DOR",
            full_name="Dormant Client",
            email="dor@test.com",
            language="de",
            practice=self.practice,
        )

        # Create historical invoice for established client (Jan-Sep 2025)
        # This ensures total_sessions_ever >= 5 for established classification
        historical_invoice = Invoice.objects.create(
            client=self.established_client,
            invoice_number="2025-001",
            invoice_date=date(2025, 1, 1),
            total=Decimal("4320.00"),
            status="paid",
            practice=self.practice,
        )
        # Create 36 hours (9 months * 4 hours) in Jan-Sep 2025
        for month in range(1, 10):  # Jan-Sep 2025
            for day in [5, 12, 19, 26]:  # 4 sessions per month = 4h
                InvoiceItem.objects.create(
                    invoice=historical_invoice,
                    session=Session.objects.create(
                        client=self.established_client,
                        session_date=date(2025, month, day),
                        duration=60,
                    ),
                    service_type=self.service_type,
                    rate=Decimal("120.00"),
                    quantity=1,
                )

        # Probatoric client: 3 sessions in period, 3 total
        # (InvoiceItems created below in main test data)

        # Dormant client: 0 sessions in period, but has history
        dormant_invoice = Invoice.objects.create(
            client=self.dormant_client,
            invoice_number="2025-008",
            invoice_date=date(2025, 8, 1),
            total=Decimal("600.00"),
            status="paid",
            practice=self.practice,
        )
        # 5 sessions in August 2025 (before analysis period)
        for day in [3, 10, 17, 24, 31]:
            InvoiceItem.objects.create(
                invoice=dormant_invoice,
                session=Session.objects.create(
                    client=self.dormant_client,
                    session_date=date(2025, 8, day),
                    duration=60,
                ),
                service_type=self.service_type,
                rate=Decimal("120.00"),
                quantity=1,
            )

        # Create invoices for established client
        self.invoice = Invoice.objects.create(
            client=self.established_client,
            invoice_number="2025-010",
            invoice_date=date(2025, 11, 1),
            total=Decimal("720.00"),
            status="paid",
            practice=self.practice,
        )

        # Create invoice items to match expected booked hours (21h total in Q4)
        # EST client: 18h in Q4 (6h per month)
        for day in [5, 12, 19, 26]:  # 4 sessions in October = 4h
            InvoiceItem.objects.create(
                invoice=self.invoice,
                session=Session.objects.create(
                    client=self.established_client,
                    session_date=date(2025, 10, day),
                    duration=60,
                ),
                service_type=self.service_type,
                rate=Decimal("120.00"),
                quantity=1,
            )
        for day in [2, 9]:  # 2 more sessions in October = 2h (total 6h)
            InvoiceItem.objects.create(
                invoice=self.invoice,
                session=Session.objects.create(
                    client=self.established_client,
                    session_date=date(2025, 10, day),
                    duration=60,
                ),
                service_type=self.service_type,
                rate=Decimal("120.00"),
                quantity=1,
            )
        for day in [5, 12, 19, 26]:  # 4 sessions in November = 4h
            InvoiceItem.objects.create(
                invoice=self.invoice,
                session=Session.objects.create(
                    client=self.established_client,
                    session_date=date(2025, 11, day),
                    duration=60,
                ),
                service_type=self.service_type,
                rate=Decimal("120.00"),
                quantity=1,
            )
        for day in [2, 9]:  # 2 more sessions in November = 2h (total 6h)
            InvoiceItem.objects.create(
                invoice=self.invoice,
                session=Session.objects.create(
                    client=self.established_client,
                    session_date=date(2025, 11, day),
                    duration=60,
                ),
                service_type=self.service_type,
                rate=Decimal("120.00"),
                quantity=1,
            )
        for day in [3, 10, 17]:  # 3 sessions in December = 3h
            InvoiceItem.objects.create(
                invoice=self.invoice,
                session=Session.objects.create(
                    client=self.established_client,
                    session_date=date(2025, 12, day),
                    duration=60,
                ),
                service_type=self.service_type,
                rate=Decimal("120.00"),
                quantity=1,
            )
        for day in [1, 8, 15]:  # 3 more sessions in December = 3h (total 6h)
            InvoiceItem.objects.create(
                invoice=self.invoice,
                session=Session.objects.create(
                    client=self.established_client,
                    session_date=date(2025, 12, day),
                    duration=60,
                ),
                service_type=self.service_type,
                rate=Decimal("120.00"),
                quantity=1,
            )
        # Total EST: 18h

        # PRO client: 3h in Q4
        pro_invoice = Invoice.objects.create(
            client=self.probatoric_client,
            invoice_number="2025-011",
            invoice_date=date(2025, 11, 15),
            total=Decimal("360.00"),
            status="paid",
            practice=self.practice,
        )
        for day in [10, 17, 24]:  # 3 sessions in November = 3h
            InvoiceItem.objects.create(
                invoice=pro_invoice,
                session=Session.objects.create(
                    client=self.probatoric_client,
                    session_date=date(2025, 11, day),
                    duration=60,
                ),
                service_type=self.service_type,
                rate=Decimal("120.00"),
                quantity=1,
            )
        # Total PRO: 3h
        # Total booked: 18 + 3 = 21h

        # Create time off in Q4
        TimeOff.objects.create(
            title="Vacation",
            type="vacation",
            start_date=date(2025, 12, 23),
            end_date=date(2025, 12, 31),
        )

    def test_analyze_basic_structure(self):
        """Test that analyze returns correct structure"""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="test-practice",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        analyzer = PracticeAnalyzer(date(2025, 10, 1), date(2025, 12, 31))
        analysis = analyzer.analyze()

        self.assertIn("period", analysis)
        self.assertIn("clients", analysis)
        self.assertIn("capacity", analysis)
        self.assertIn("timeoff", analysis)
        self.assertIn("summary", analysis)

    def test_client_classification_established(self):
        """Test established client classification (>=5 sessions, active in period)"""
        analyzer = PracticeAnalyzer(date(2025, 10, 1), date(2025, 12, 31))
        analysis = analyzer.analyze()

        est_client = next(
            (c for c in analysis["clients"]["list"] if c["client_code"] == "EST"), None
        )
        self.assertIsNotNone(est_client)
        self.assertEqual(est_client["classification"], ClientClassification.ESTABLISHED)
        self.assertEqual(est_client["sessions_in_period"], 18.0)  # 3 months * 6h
        self.assertEqual(est_client["sessions_total"], 54.0)  # 9*4 + 3*6

    def test_client_classification_probatoric(self):
        """Test probatoric client classification (<5 sessions total)"""
        analyzer = PracticeAnalyzer(date(2025, 10, 1), date(2025, 12, 31))
        analysis = analyzer.analyze()

        pro_client = next(
            (c for c in analysis["clients"]["list"] if c["client_code"] == "PRO"), None
        )
        self.assertIsNotNone(pro_client)
        self.assertEqual(pro_client["classification"], ClientClassification.PROBATORIC)
        self.assertEqual(pro_client["sessions_in_period"], 3.0)
        self.assertEqual(pro_client["sessions_total"], 3.0)

    def test_client_classification_dormant(self):
        """Test dormant client classification (no sessions in period)"""
        analyzer = PracticeAnalyzer(date(2025, 10, 1), date(2025, 12, 31))
        analysis = analyzer.analyze()

        dor_client = next(
            (c for c in analysis["clients"]["list"] if c["client_code"] == "DOR"), None
        )
        self.assertIsNotNone(dor_client)
        self.assertEqual(dor_client["classification"], ClientClassification.DORMANT)
        self.assertEqual(dor_client["sessions_in_period"], 0.0)
        self.assertEqual(dor_client["sessions_total"], 5.0)

    def test_client_counts(self):
        """Test client count aggregations"""
        analyzer = PracticeAnalyzer(date(2025, 10, 1), date(2025, 12, 31))
        analysis = analyzer.analyze()

        self.assertEqual(analysis["clients"]["established"], 1)
        self.assertEqual(analysis["clients"]["probatoric"], 1)
        self.assertEqual(analysis["clients"]["dormant"], 1)
        self.assertEqual(analysis["clients"]["active_in_period"], 2)  # EST + PRO

    def test_capacity_calculation(self):
        """Test capacity metrics calculation"""
        analyzer = PracticeAnalyzer(date(2025, 10, 1), date(2025, 12, 31))
        analysis = analyzer.analyze()

        capacity = analysis["capacity"]

        # Q4 working days excl. Berlin public holidays:
        # Oct: 23 Mon-Fri − 2 holidays (Oct 3 Einheit, Oct 31 Reformationstag) = 21
        # Nov: 20 Mon-Fri − 0 holidays = 20
        # Dec: 23 Mon-Fri − 2 holidays (Dec 25+26 Weihnachten) = 21  →  total 62
        self.assertEqual(capacity["working_days_total"], 62)

        # TimeOff Dec 23-31: 7 Mon-Fri − 2 holidays (Dec 25+26) = 5 workdays; 62 − 5 = 57
        self.assertEqual(capacity["working_days_available"], 57)

        # Available hours: 57 days * 8 hours = 456
        self.assertEqual(capacity["available_hours"], 456)

        # Booked hours: 18 (EST) + 3 (PRO) = 21
        self.assertEqual(capacity["booked_hours"], 21.0)

        # Usable capacity: 57 days / 5 * 20h/week = 228
        self.assertAlmostEqual(capacity["usable_capacity_hours"], 228.0, places=1)

        # Capacity percentage: 21 / 240 * 100 ≈ 8.75%
        self.assertGreater(capacity["capacity_percentage"], 7)
        self.assertLess(capacity["capacity_percentage"], 10)

    def test_timeoff_integration(self):
        """Test time off data integration"""
        analyzer = PracticeAnalyzer(date(2025, 10, 1), date(2025, 12, 31))
        analysis = analyzer.analyze()

        timeoff = analysis["timeoff"]

        # Dec 23-31 = 9 days total
        self.assertEqual(timeoff["total_days"], 9)

        # Workdays: Dec 23,24,29,30,31 = 5 (excl. Dec 25+26 Berlin public holidays)
        self.assertEqual(timeoff["workdays"], 5)

    def test_insights_generation(self):
        """Test that insights are generated"""
        analyzer = PracticeAnalyzer(date(2025, 10, 1), date(2025, 12, 31))
        analysis = analyzer.analyze_with_insights()

        self.assertIn("insights", analysis)
        self.assertIsInstance(analysis["insights"], list)
        self.assertGreater(len(analysis["insights"]), 0)

        # Should have period overview insight
        period_insights = [i for i in analysis["insights"] if "Oct - Dec 2025" in i]
        self.assertGreater(len(period_insights), 0)

    def test_period_label_formatting(self):
        """Test period label formatting for different ranges"""
        # Same year, same month
        analyzer = PracticeAnalyzer(date(2025, 11, 1), date(2025, 11, 30))
        analysis = analyzer.analyze()
        self.assertEqual(analysis["period"]["label"], "November 2025")

        # Same year, different months
        analyzer = PracticeAnalyzer(date(2025, 10, 1), date(2025, 12, 31))
        analysis = analyzer.analyze()
        self.assertEqual(analysis["period"]["label"], "Oct - Dec 2025")

        # Full year
        analyzer = PracticeAnalyzer(date(2025, 1, 1), date(2025, 12, 31))
        analysis = analyzer.analyze()
        self.assertEqual(analysis["period"]["label"], "2025")

    def test_online_client_counting(self):
        """Test online client counting"""
        # Add online client
        online_client = Client.objects.create(
            client_code="ONL",
            full_name="Online Client",
            email="onl@test.com",
            language="en",
            is_online_client=True,
            practice=self.practice,
        )

        # Create InvoiceItems for online client in analysis period (Q4 2025)
        online_invoice = Invoice.objects.create(
            client=online_client,
            invoice_number="2025-ONL",
            invoice_date=date(2025, 11, 1),
            total=Decimal("600.00"),
            status="paid",
            practice=self.practice,
        )
        # 5 sessions in November 2025
        for day in [3, 10, 17, 24]:
            InvoiceItem.objects.create(
                invoice=online_invoice,
                session=Session.objects.create(
                    client=online_client,
                    session_date=date(2025, 11, day),
                    duration=60,
                ),
                service_type=self.service_type,
                rate=Decimal("120.00"),
                quantity=1,
            )
        InvoiceItem.objects.create(
            invoice=online_invoice,
            session=Session.objects.create(
                client=online_client,
                session_date=date(2025, 11, 5),
                duration=60,
            ),
            service_type=self.service_type,
            rate=Decimal("120.00"),
            quantity=1,
        )

        analyzer = PracticeAnalyzer(date(2025, 10, 1), date(2025, 12, 31))
        analysis = analyzer.analyze()

        self.assertEqual(analysis["clients"]["online"], 1)

    def test_revenue_in_period(self):
        """Test revenue calculation for period"""
        analyzer = PracticeAnalyzer(date(2025, 10, 1), date(2025, 12, 31))
        analysis = analyzer.analyze()

        est_client = next(
            (c for c in analysis["clients"]["list"] if c["client_code"] == "EST"), None
        )

        # Should have invoice revenue (but aggregate returns invoice.total, not item sum)
        self.assertGreater(est_client["revenue_in_period"], 0)


class CalculateQuarterTrendsTestCase(TestCase):
    """Tests for calculate_quarter_trends function"""

    def setUp(self):
        """Create test data spanning multiple quarters"""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="practice_analysis-2",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        # Create service type
        self.service_type = ServiceType.objects.create(
            code="therapy_60",
            name="Session",
            name_de="Sitzung",
            name_en="Session",
            default_duration=60,
            practice=self.practice,
        )

        # Create client
        self.client = Client.objects.create(
            client_code="TRE",
            full_name="Trend Client",
            email="trend@test.com",
            language="de",
            practice=self.practice,
        )

        # Create InvoiceItems for 4 quarters with increasing session counts
        trend_invoice = Invoice.objects.create(
            client=self.client,
            invoice_number="2025-TRE",
            invoice_date=date(2025, 1, 1),
            total=Decimal("10000.00"),
            status="paid",
            practice=self.practice,
        )

        # Create sessions distributed across 4 quarters
        # Q1: 30 sessions (10h/month * 3 months)
        # Q2: 45 sessions (15h/month * 3 months)
        # Q3: 60 sessions (20h/month * 3 months)
        # Q4: 75 sessions (25h/month * 3 months)
        quarters = [
            (1, 10),  # Q1: Jan-Mar, 10 sessions/month
            (4, 15),  # Q2: Apr-Jun, 15 sessions/month
            (7, 20),  # Q3: Jul-Sep, 20 sessions/month
            (10, 25),  # Q4: Oct-Dec, 25 sessions/month
        ]

        for start_month, sessions_per_month in quarters:
            for month_offset in range(3):  # 3 months per quarter
                month = start_month + month_offset
                # Create session items (1 item per session)
                for day in range(1, min(sessions_per_month + 1, 29)):
                    InvoiceItem.objects.create(
                        invoice=trend_invoice,
                        session=Session.objects.create(
                            client=self.client,
                            session_date=date(2025, month, day),
                            duration=60,
                        ),
                        service_type=self.service_type,
                        rate=Decimal("120.00"),
                        quantity=1,
                    )

    def test_calculate_quarter_trends_structure(self):
        """Test that quarter trends returns correct structure"""
        trends = calculate_quarter_trends(date(2025, 12, 31))

        self.assertEqual(len(trends), 4)

        for trend in trends:
            self.assertIn("label", trend)
            self.assertIn("capacity_percentage", trend)
            self.assertIn("active_clients", trend)
            self.assertIn("total_sessions", trend)
            self.assertIn("timeoff_days", trend)

    def test_quarter_trends_ordering(self):
        """Test that trends are ordered chronologically (oldest first)"""
        trends = calculate_quarter_trends(date(2025, 12, 31))

        # Should start with Q1 and end with Q4
        self.assertIn("2025", trends[0]["label"])
        self.assertIn("2025", trends[-1]["label"])

        # Total sessions should increase (10->15->20->25 per month, 3 months each)
        self.assertLess(trends[0]["total_sessions"], trends[-1]["total_sessions"])

    def test_quarter_trends_active_clients(self):
        """Test active client counting in trends"""
        trends = calculate_quarter_trends(date(2025, 12, 31))

        # Should have 1 active client in each quarter
        for trend in trends:
            self.assertEqual(trend["active_clients"], 1)

    def test_quarter_trends_capacity_percentage(self):
        """Test capacity percentage is calculated"""
        trends = calculate_quarter_trends(date(2025, 12, 31))

        for trend in trends:
            self.assertIsInstance(trend["capacity_percentage"], int)
            self.assertGreaterEqual(trend["capacity_percentage"], 0)
            self.assertLessEqual(trend["capacity_percentage"], 100)


class PracticeAnalyzerEdgeCasesTestCase(TestCase):
    """Test edge cases and error handling"""

    def setUp(self):
        """Create test practice"""
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="practice-analyzer-edge",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

    def test_empty_period(self):
        """Test analysis with no clients or sessions"""
        analyzer = PracticeAnalyzer(date(2025, 10, 1), date(2025, 12, 31))
        analysis = analyzer.analyze()

        self.assertEqual(analysis["clients"]["active_in_period"], 0)
        self.assertEqual(analysis["clients"]["established"], 0)
        self.assertEqual(analysis["clients"]["probatoric"], 0)
        self.assertEqual(len(analysis["clients"]["list"]), 0)

    def test_single_day_period(self):
        """Test analysis for single day"""
        # Nov 17, 2025 is a Monday
        analyzer = PracticeAnalyzer(date(2025, 11, 17), date(2025, 11, 17))
        analysis = analyzer.analyze()

        self.assertEqual(analysis["period"]["days"], 1)
        self.assertEqual(analysis["capacity"]["working_days_total"], 1)

    def test_weekend_only_period(self):
        """Test period that's only weekends"""
        # Nov 1-2, 2025 is Sat-Sun
        analyzer = PracticeAnalyzer(date(2025, 11, 1), date(2025, 11, 2))
        analysis = analyzer.analyze()

        self.assertEqual(analysis["capacity"]["working_days_total"], 0)
        self.assertEqual(analysis["capacity"]["available_hours"], 0)

    def test_client_with_no_sessions(self):
        """Test client that exists but has no sessions"""
        Client.objects.create(
            client_code="NEW",
            full_name="New Client",
            email="new@test.com",
            language="de",
            practice=self.practice,
        )

        analyzer = PracticeAnalyzer(date(2025, 10, 1), date(2025, 12, 31))
        analysis = analyzer.analyze()

        # Client with no history should not appear in list
        new_client = next(
            (c for c in analysis["clients"]["list"] if c["client_code"] == "NEW"), None
        )
        self.assertIsNone(new_client)
