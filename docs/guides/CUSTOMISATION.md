# Customisation Guide

This app was built for one specific practice. Before using it for your own, there are a few
places where the defaults reflect a particular setup and need to be swapped out.

---

## Replace with your own content

These files exist and work, but their *content* is practice-specific. The framework is
reusable; only the text inside needs replacing.

| Item | Location | What to do |
|------|----------|------------|
| Treatment contract PDF | `app/templates/my_practice/treatment_contract_pdf.html` | Contains DE-specific legal clauses (§ Heilpraktiker, GebüH, cancellation policy, DSGVO). Replace the body text with your own contract. A comment at the top of the file marks the sections to change. |
| Contract email template | `app/templates/my_practice/send_contract_email.html` | Short cover email accompanying the contract. Read it before sending — it will need your wording. |
| Backup checklist items | `app/my_practice/views/operational_views.py` → `CHECKLIST_ITEMS` | The checklist engine (completion tracking, pausing, dashboard widget) is fully reusable. The default steps match one specific LUKS/Yubikey/NAS setup. Replace them with your own rotation steps. See [BACKUP_SETUP.md](BACKUP_SETUP.md) for context. |

---

## Known limitations (longer-term fixes)

These are hardcoded for one setup and would need code changes to adapt. Documented here
so you know what you're taking on.

| Item | Location | Notes |
|------|----------|-------|
| Calendar duration → service code mapping | `app/my_practice/utils/google_calendar.py` → `DURATION_TO_SERVICE_CODE` | Maps event lengths to service type codes seeded by `seed_sample_data`. If your service types differ, update this dict or configure service types via the admin. |
| Public holidays | `app/my_practice/utils/practice_days.py` → `berlin_public_holidays()` | Capacity utilisation is calculated against Berlin/Brandenburg public holidays. Other states or countries will need the holiday set replaced. |

---

## Already configurable — no changes needed

Everything below is set via the setup wizard or the admin interface.

| Item | How |
|------|-----|
| Practice name, address, IBAN, bank details | `Practice` model fields, set via the settings page |
| Hourly rates per client | `Client.hourly_rate` |
| Email templates (payment reminder, contract cover letter) | Stored in the database via `Practice`; editable in the settings UI |
| Logo, signature image | `Practice.logo` / `Practice.signature` file fields |
| Tax settings (Kleinunternehmer vs. Heilpraktiker VAT exemption) | `Practice.is_kleinunternehmer` |
| Session / service types | Seeded by `seed_sample_data`, then fully editable in the admin |
| Bank CSV format | `Practice.csv_delimiter` / `csv_column_*` fields, set in the Django admin. Defaults match GLS Bank's export; other banks: adjust delimiter and column names to match your export, no code changes needed |
