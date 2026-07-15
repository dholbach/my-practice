# P-121: Time-off CRUD + client heads-up email

`TimeOff` (vacation/holiday/sick/training/other periods) could previously only
be created or edited via `/admin`, and there was no way to notify clients in
advance of a closure other than manually. This adds an in-app screen for the
former and a new bulk-email feature for the latter.

## What changed

**In-app CRUD** (`/timeoff/`, under the "⚙️ Admin" nav dropdown) —
`TimeOffCreateView`/`UpdateView`/`DeleteView` on `views/timeoff_views.py`,
reusing the existing `PracticeScopedCreateView`/etc. mixins even though
`TimeOff` has no `practice` FK (the mixins already no-op practice-scoping
when the model/manager doesn't support it). List view splits entries into
upcoming/current vs. past.

**Heads-up email to clients**, reachable from checkboxes on the upcoming/
current table (`timeoff/notify/?ids=1&ids=2…`, any combination of periods):

- Recipients default to all active clients with an email on file, pre-checked.
- Editable bilingual (DE/EN) subject/body preview before sending — not a
  silent auto-send. Content is **date-only, not title-based**: e.g. subject
  `Practice closed: 24-28th July, 17-30th August`, body lines like
  `fri 24th - tue 28th july` — clients don't need to know what the time off
  is *for*, just which dates/weekdays are affected, so they can scan for
  their own recurring slot. Multiple selected periods render as a bulleted
  list instead of one sentence.
- Salutation is personalized per client via a `{salutation}` token in the
  editable body, substituted at send time with `get_salutation_for_client()`
  — reuses the same `render_email_template()` mechanism already used for the
  DB-configurable invoice email templates, rather than inventing new
  per-client templating.
- Recipient table shows client code (not full name — privacy), a `DE`/`EN`
  language badge, and last/next session date, so a long list can be trimmed
  at a glance instead of requiring a lookup per client. Last/next session
  come from two separately-scoped `Subquery` annotations on `Session`
  (`session_date__lt=today` / `__gte=today`) — a first attempt using a plain
  `Max("sessions__session_date")` incorrectly returned a *future* session as
  "last session" too, since `Max` doesn't distinguish past from future.

## Not in scope

- No "already notified" tracking — no model change, resend anytime.
- `TimeOff` remains a global (non-practice-scoped) model, matching its
  existing design.

## Related

- i18n: this is the first newly-created feature built entirely under the
  P-039 "English msgids" convention; a couple of mid-session mistakes here
  (German text used as a msgid, unwrapped `success_message` strings) led to
  clarifying CLAUDE.md that "touched" always includes newly-created files —
  see [P-039_I18N.md](../wip/P-039_I18N.md).
