"""
Tests for P-012 Operational Checklist feature.

Covers:
- ChecklistItemPause.is_active property (past / future / None dates)
- OperationalChecklistCompletion.is_completed and mark_complete
- OperationalChecklistView GET (items annotated with active pauses)
- checklist_complete POST
- checklist_pause_item POST
- checklist_unpause_item POST
- ChecklistWidgetBuilder pending logic (respects paused items)
"""

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import Client as TestClient
from django.test import TestCase
from django.urls import reverse

from ..models import (
    ChecklistItemPause,
    OperationalChecklistCompletion,
    Practice,
    UserPractice,
)
from ..utils import ChecklistWidgetBuilder

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user_with_practice(username: str) -> tuple:
    """Create a user+practice and return (user, practice, logged-in TestClient)."""
    practice = Practice.objects.create(
        name="Test Practice",
        slug=f"checklist-test-{username}",
        title="Testtherapeutin",
        email="test@example.com",
        city="Berlin",
    )
    user = User.objects.create_user(username=username, password="testpass")
    UserPractice.objects.create(user=user, practice=practice, is_owner=True)
    client = TestClient()
    client.login(username=username, password="testpass")
    return user, practice, client


def _period_start(checklist_type: str) -> date:
    """Return the current period start for a checklist type (mirrors view logic)."""
    today = date.today()
    if checklist_type == "weekly":
        return today - timedelta(days=today.weekday())
    elif checklist_type == "monthly":
        return date(today.year, today.month, 1)
    elif checklist_type == "quarterly":
        q = ((today.month - 1) // 3) * 3 + 1
        return date(today.year, q, 1)
    else:  # annual
        return date(today.year, 1, 1)


# ---------------------------------------------------------------------------
# Model: ChecklistItemPause.is_active
# ---------------------------------------------------------------------------


class ChecklistItemPauseIsActiveTests(TestCase):
    def _make_pause(self, **kwargs) -> ChecklistItemPause:
        defaults = {
            "checklist_type": "monthly",
            "item_id": "pick_source",
            "reason": "Test",
        }
        defaults.update(kwargs)
        return ChecklistItemPause(**defaults)

    def test_indefinite_pause_is_active(self):
        pause = self._make_pause(paused_until=None)
        self.assertTrue(pause.is_active)

    def test_future_date_is_active(self):
        pause = self._make_pause(paused_until=date.today() + timedelta(days=7))
        self.assertTrue(pause.is_active)

    def test_today_is_active(self):
        pause = self._make_pause(paused_until=date.today())
        self.assertTrue(pause.is_active)

    def test_past_date_is_not_active(self):
        pause = self._make_pause(paused_until=date.today() - timedelta(days=1))
        self.assertFalse(pause.is_active)

    def test_str_indefinite(self):
        pause = self._make_pause(paused_until=None)
        self.assertIn("unbegrenzt", str(pause))

    def test_str_with_date(self):
        pause = self._make_pause(paused_until=date(2026, 6, 15))
        self.assertIn("15.06.2026", str(pause))


# ---------------------------------------------------------------------------
# Model: OperationalChecklistCompletion
# ---------------------------------------------------------------------------


class OperationalChecklistCompletionTests(TestCase):
    def setUp(self):
        self.checklist = OperationalChecklistCompletion.objects.create(
            checklist_type="monthly",
            year_month=_period_start("monthly"),
        )

    def test_not_completed_initially(self):
        self.assertFalse(self.checklist.is_completed)

    def test_mark_complete(self):
        self.checklist.mark_complete(notes="All good")
        self.checklist.refresh_from_db()
        self.assertTrue(self.checklist.is_completed)
        self.assertEqual(self.checklist.notes, "All good")

    def test_unique_together_constraint(self):
        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            OperationalChecklistCompletion.objects.create(
                checklist_type="monthly",
                year_month=_period_start("monthly"),
            )


# ---------------------------------------------------------------------------
# View: GET /backups/checklist/<type>/
# ---------------------------------------------------------------------------


class OperationalChecklistViewTests(TestCase):
    def setUp(self):
        self.user, self.practice, self.http = _make_user_with_practice("checklist_view")

    def test_monthly_checklist_renders(self):
        resp = self.http.get(reverse("checklist", kwargs={"checklist_type": "monthly"}))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Monatlicher Restore-Test")

    def test_items_have_pause_annotation(self):
        """Context items should have 'pause' key."""
        resp = self.http.get(reverse("checklist", kwargs={"checklist_type": "monthly"}))
        items = resp.context["items"]
        self.assertTrue(all("pause" in item for item in items))

    def test_active_pause_annotated_on_item(self):
        ChecklistItemPause.objects.create(
            checklist_type="monthly",
            item_id="pick_source",
            reason="Waiting for setup",
            paused_until=None,
        )
        resp = self.http.get(reverse("checklist", kwargs={"checklist_type": "monthly"}))
        items = resp.context["items"]
        paused_item = next(i for i in items if i["id"] == "pick_source")
        self.assertIsNotNone(paused_item["pause"])
        non_paused = [i for i in items if i["id"] != "pick_source"]
        self.assertTrue(all(i["pause"] is None for i in non_paused))

    def test_expired_pause_not_annotated(self):
        ChecklistItemPause.objects.create(
            checklist_type="monthly",
            item_id="pick_source",
            reason="Old pause",
            paused_until=date.today() - timedelta(days=1),
        )
        resp = self.http.get(reverse("checklist", kwargs={"checklist_type": "monthly"}))
        items = resp.context["items"]
        paused_item = next(i for i in items if i["id"] == "pick_source")
        self.assertIsNone(paused_item["pause"])

    def test_invalid_type_defaults_to_monthly(self):
        resp = self.http.get(reverse("checklist", kwargs={"checklist_type": "nonexistent"}))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["checklist_type"], "monthly")

    def test_completed_checklist_shows_completed_view(self):
        checklist = OperationalChecklistCompletion.objects.create(
            checklist_type="monthly",
            year_month=_period_start("monthly"),
        )
        checklist.mark_complete(notes="Done")
        resp = self.http.get(reverse("checklist", kwargs={"checklist_type": "monthly"}))
        self.assertContains(resp, "Abgeschlossen am")


# ---------------------------------------------------------------------------
# View: POST /backups/checklist/<type>/complete/
# ---------------------------------------------------------------------------


class ChecklistCompleteViewTests(TestCase):
    def setUp(self):
        self.user, self.practice, self.http = _make_user_with_practice("checklist_complete")

    def _make_checklist(self, ct: str) -> OperationalChecklistCompletion:
        return OperationalChecklistCompletion.objects.create(
            checklist_type=ct,
            year_month=_period_start(ct),
        )

    def test_post_marks_complete(self):
        checklist = self._make_checklist("monthly")
        resp = self.http.post(
            reverse("checklist_complete", kwargs={"checklist_type": "monthly"}),
            {"notes": "Test pass"},
        )
        self.assertRedirects(resp, reverse("checklist", kwargs={"checklist_type": "monthly"}))
        checklist.refresh_from_db()
        self.assertTrue(checklist.is_completed)
        self.assertEqual(checklist.notes, "Test pass")

    def test_get_redirects(self):
        self._make_checklist("monthly")
        resp = self.http.get(reverse("checklist_complete", kwargs={"checklist_type": "monthly"}))
        self.assertRedirects(resp, reverse("checklist", kwargs={"checklist_type": "monthly"}))

    def test_already_completed_shows_info(self):
        checklist = self._make_checklist("monthly")
        checklist.mark_complete()
        resp = self.http.post(
            reverse("checklist_complete", kwargs={"checklist_type": "monthly"}),
            {},
            follow=True,
        )
        messages = list(resp.context["messages"])
        self.assertTrue(any("bereits" in str(m) for m in messages))


# ---------------------------------------------------------------------------
# View: POST pause / unpause
# ---------------------------------------------------------------------------


class ChecklistPauseViewTests(TestCase):
    def setUp(self):
        self.user, self.practice, self.http = _make_user_with_practice("checklist_pause")

    def test_pause_creates_record(self):
        resp = self.http.post(
            reverse(
                "checklist_pause",
                kwargs={"checklist_type": "monthly", "item_id": "pick_source"},
            ),
            {"reason": "MicroSD not delivered", "paused_until": ""},
        )
        self.assertRedirects(resp, reverse("checklist", kwargs={"checklist_type": "monthly"}))
        pause = ChecklistItemPause.objects.get(checklist_type="monthly", item_id="pick_source")
        self.assertEqual(pause.reason, "MicroSD not delivered")
        self.assertIsNone(pause.paused_until)

    def test_pause_with_date(self):
        self.http.post(
            reverse(
                "checklist_pause",
                kwargs={"checklist_type": "quarterly", "item_id": "pick_card"},
            ),
            {"reason": "Waiting for delivery", "paused_until": "2026-06-01"},
        )
        pause = ChecklistItemPause.objects.get(checklist_type="quarterly", item_id="pick_card")
        self.assertEqual(pause.paused_until, date(2026, 6, 1))

    def test_pause_update_or_create(self):
        """Pausing again replaces the existing pause record."""
        ChecklistItemPause.objects.create(
            checklist_type="monthly", item_id="pick_source", reason="Old reason"
        )
        self.http.post(
            reverse(
                "checklist_pause",
                kwargs={"checklist_type": "monthly", "item_id": "pick_source"},
            ),
            {"reason": "New reason"},
        )
        self.assertEqual(
            ChecklistItemPause.objects.filter(
                checklist_type="monthly", item_id="pick_source"
            ).count(),
            1,
        )
        pause = ChecklistItemPause.objects.get(checklist_type="monthly", item_id="pick_source")
        self.assertEqual(pause.reason, "New reason")

    def test_pause_invalid_item_redirects_with_error(self):
        resp = self.http.post(
            reverse(
                "checklist_pause",
                kwargs={"checklist_type": "monthly", "item_id": "no_such_item"},
            ),
            {"reason": "Test"},
            follow=True,
        )
        messages = list(resp.context["messages"])
        self.assertTrue(any("Unbekanntes" in str(m) for m in messages))
        self.assertEqual(ChecklistItemPause.objects.count(), 0)

    def test_unpause_deletes_record(self):
        ChecklistItemPause.objects.create(
            checklist_type="monthly", item_id="pick_source", reason="Test"
        )
        resp = self.http.post(
            reverse(
                "checklist_unpause",
                kwargs={"checklist_type": "monthly", "item_id": "pick_source"},
            ),
        )
        self.assertRedirects(resp, reverse("checklist", kwargs={"checklist_type": "monthly"}))
        self.assertEqual(ChecklistItemPause.objects.count(), 0)

    def test_unpause_nonexistent_is_safe(self):
        """Unpausing an item that has no pause record should not error."""
        resp = self.http.post(
            reverse(
                "checklist_unpause",
                kwargs={"checklist_type": "monthly", "item_id": "pick_source"},
            ),
        )
        self.assertRedirects(resp, reverse("checklist", kwargs={"checklist_type": "monthly"}))


# ---------------------------------------------------------------------------
# ChecklistWidgetBuilder
# ---------------------------------------------------------------------------


class ChecklistWidgetBuilderTests(TestCase):
    def test_all_types_pending_with_no_data(self):
        """With no completions, all 4 checklist types should be pending."""
        ctx = ChecklistWidgetBuilder().build_context()
        self.assertEqual(ctx["pending_count"], 4)
        self.assertTrue(ctx["show_widget"])

    def test_completed_checklist_not_pending(self):
        checklist = OperationalChecklistCompletion.objects.create(
            checklist_type="monthly",
            year_month=_period_start("monthly"),
        )
        checklist.mark_complete()
        ctx = ChecklistWidgetBuilder().build_context()
        types_pending = [c["type"] for c in ctx["pending_checklists"]]
        self.assertNotIn("monthly", types_pending)

    def test_fully_paused_checklist_not_pending(self):
        """If all items of a checklist type are paused, it should not show as pending."""
        from ..views.operational_views import CHECKLIST_ITEMS

        for item in CHECKLIST_ITEMS["monthly"]:
            ChecklistItemPause.objects.create(
                checklist_type="monthly",
                item_id=item["id"],
                reason="All paused",
                paused_until=None,
            )
        ctx = ChecklistWidgetBuilder().build_context()
        types_pending = [c["type"] for c in ctx["pending_checklists"]]
        self.assertNotIn("monthly", types_pending)

    def test_partially_paused_still_pending(self):
        """If only some items are paused, the checklist should still be pending."""
        ChecklistItemPause.objects.create(
            checklist_type="monthly",
            item_id="pick_source",
            reason="Partial pause",
            paused_until=None,
        )
        ctx = ChecklistWidgetBuilder().build_context()
        types_pending = [c["type"] for c in ctx["pending_checklists"]]
        self.assertIn("monthly", types_pending)

    def test_expired_pauses_do_not_suppress(self):
        """Expired pauses should not suppress the checklist from the widget."""
        from ..views.operational_views import CHECKLIST_ITEMS

        for item in CHECKLIST_ITEMS["monthly"]:
            ChecklistItemPause.objects.create(
                checklist_type="monthly",
                item_id=item["id"],
                reason="Expired",
                paused_until=date.today() - timedelta(days=1),  # expired
            )
        ctx = ChecklistWidgetBuilder().build_context()
        types_pending = [c["type"] for c in ctx["pending_checklists"]]
        self.assertIn("monthly", types_pending)

    def test_no_pending_show_widget_false(self):
        """If all checklists are completed, show_widget is False."""
        for ct, _ in OperationalChecklistCompletion.CHECKLIST_TYPES:
            checklist = OperationalChecklistCompletion.objects.create(
                checklist_type=ct,
                year_month=_period_start(ct),
            )
            checklist.mark_complete()
        ctx = ChecklistWidgetBuilder().build_context()
        self.assertFalse(ctx["show_widget"])
        self.assertEqual(ctx["pending_count"], 0)
