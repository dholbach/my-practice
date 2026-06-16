# Type Checking Notes

Known Mypy false positives for this codebase. Safe to ignore unless noted otherwise.

---

## False Positives

### `request.current_practice` attribute error

```
error: "HttpRequest" has no attribute "current_practice"
```

`current_practice` is injected at runtime by `PracticeScopeMiddleware`. Mypy can't
see it. Affects `views/tax_views.py`, `dashboard_views.py`, `api_views.py`,
`invoice_views.py`.

Future fix: define a custom `HttpRequest` Protocol in `config/types.py`.

---

### ManyToMany fields without type annotation

```
error: Need type annotation for "users" [var-annotated]
error: Need type annotation for "tags" [var-annotated]
```

Django creates ManyToMany managers automatically; no explicit annotation needed.
Affects `models/practice.py` (`users`) and `models/client.py` (`tags`).

---

### Optional model attribute

```
error: Item "None" of "Invoice | None" has no attribute "client"
```

QuerySet operations may return `None` per type system, but business logic guarantees
the object exists at these call sites. False positive.

---

### `Type[Model].objects` attribute

```
error: "type[Model]" has no attribute "objects"
```

Django injects the `objects` manager; `django-stubs` would suppress this. Ignore
until stubs are added.

---

### `Field.queryset` attribute

```
error: "Field" has no attribute "queryset"
```

`ModelChoiceField` has `queryset`, but Mypy resolves the generic `Field` base class.
Affects `invoice_forms.py`. False positive.

---

## Known Issues (Not False Positives)

### Return type annotation in `FinancialListContextBuilder`

File: `utils/financial_list_context_builder.py`, lines 105 and 107.  
Return type annotation says `dict` but the actual return value is `list[dict]`.
Fix: narrow the annotation to `list[dict[str, Any]]`.

### Circular import in `import_helpers.py`

File: `utils/import_helpers.py`, line 15.  
`Client` imported at module level causes a circular import.
Fix: move it into a `TYPE_CHECKING` guard.

---

## Tooling Notes

- `W503` (line break before binary operator) is suppressed in `setup.cfg` — PEP 8
  updated in 2016 to prefer breaks *before* operators; W503 and W504 conflict.
- Vulture false positives (Django framework patterns) are whitelisted in
  `.vulture_whitelist.py`.
- Installing `django-stubs` would eliminate most of the manager/queryset false
  positives above; not done yet because it requires annotating all models.
