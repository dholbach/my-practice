# ADR-0008: `.doc` uploads are accepted, with the macro risk on the opener

## Context

Since #717, expense receipts and client documents accept legacy Word `.doc`
files next to `.docx`, PDFs and images (`UPLOAD_EXTENSIONS` in
[`validators.py`](../../app/my_practice/validators.py), migration 0015). A
`.doc` is an OLE2 container that can carry macros. The validators check the
extension only, as they already do for `.docx`.

The server never opens these files. `process_upload` stores them unchanged,
`serve_media` sends them as a download (`application/msword`, `nosniff`) to
members of the owning practice, and nothing converts or previews them. The
security audit of 2026-11-25 (run 7) traced this and found no server-side
exposure; the risk sits with whoever opens the file in a desktop application.

## Decision

**Accept the risk.** The practice owner decided this on 2026-11-25. Clients and
payers send `.doc` files, and refusing them would push the owner to convert
them by hand first.

## Consequences

- Do not add server-side conversion, text extraction or inline preview for
  `.doc` or `.docx` without a new ADR and a security review: that would turn an
  opener-side risk into a server-side one.
- `.doc` must never join the inline-served types in `serve_media`.
- If macro-bearing files become a real problem, restrict the accept list to
  `.docx` (which cannot carry macros) in a new ADR.
