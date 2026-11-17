"""The operational checklist items (P-012), shared by the checklist views and the dashboard widget."""

from django.utils.translation import gettext_lazy

# Checklist items per type.
#
# IMPORTANT FOR SELF-HOSTERS: These items reflect one specific backup setup
# (LUKS-encrypted USB drive + NAS + MicroSD offsite rotation). The checklist
# engine (completion tracking, pausing, dashboard widget) is fully reusable —
# but you MUST replace the items below with steps that match your own backup
# and operational procedures. See docs/operations/SECURITY.md for context.
CHECKLIST_ITEMS: dict[str, list[dict[str, str]]] = {
    "weekly": [
        {"id": "connect_usb", "title": gettext_lazy("Connect external USB drive to laptop")},
        {
            "id": "run_backup",
            "title": gettext_lazy("Run backup command (./dev.py backup or scripts/backup.sh)"),
        },
        {"id": "verify_logs", "title": gettext_lazy("Check USB and NAS backup logs for errors")},
        {
            "id": "nas_trigger",
            "title": gettext_lazy("Confirm that NAS backup was triggered automatically"),
        },
        {"id": "disconnect_usb", "title": gettext_lazy("Safely disconnect USB drive")},
    ],
    "monthly": [
        {
            "id": "pick_source",
            "title": gettext_lazy("Pick a random backup source (USB or NAS)"),
        },
        {
            "id": "decrypt",
            "title": gettext_lazy("Decrypt backup (passphrase from sealed envelope)"),
        },
        {"id": "restore_db", "title": gettext_lazy("Restore database to test instance")},
        {
            "id": "verify_counts",
            "title": gettext_lazy("Compare invoice count & client count with production"),
        },
        {
            "id": "test_media",
            "title": gettext_lazy("Download a media file and verify checksum"),
        },
        {
            "id": "log_result",
            "title": gettext_lazy('Log result: "Restore test [DATE] [USB/NAS] [record count] ✅"'),
        },
    ],
    "quarterly": [
        # Rotate every 2 weeks — alternate between Card A and Card B (UHS-I is fine, e.g. SanDisk Ultra / Samsung EVO Plus 32–64 GB)
        {
            "id": "pick_card",
            "title": gettext_lazy(
                "Take the other card from the cabinet (alternate Card A and Card B)"
            ),
        },
        {
            "id": "copy_backup",
            "title": gettext_lazy("Copy latest Pika-Backup snapshot to card"),
        },
        {
            "id": "encrypt_card",
            "title": gettext_lazy("Encrypt card (same passphrase as USB/NAS)"),
        },
        {
            "id": "test_restore",
            "title": gettext_lazy("Quick test: check 1–2 files + database count for readability"),
        },
        {
            "id": "label_card",
            "title": gettext_lazy('Label card: "Card A/B — [Date]"'),
        },
        {
            "id": "store_card",
            "title": gettext_lazy("Store in locked cabinet (location separate from laptop)"),
        },
    ],
    "annual": [
        {
            "id": "microsd_restore",
            "title": gettext_lazy("Full restore test from MicroSD (offsite scenario)"),
        },
        {
            "id": "update_check",
            "title": gettext_lazy("Check backup tool versions & security updates"),
        },
        {
            "id": "dpia_review",
            "title": gettext_lazy("Review DPIA document for processing changes"),
        },
        {
            "id": "audit_logs",
            "title": gettext_lazy("Review backup logs (no unexplained errors)"),
        },
        {
            "id": "refresh_plan",
            "title": gettext_lazy("Update emergency access plan (P-010) if needed"),
        },
    ],
}
