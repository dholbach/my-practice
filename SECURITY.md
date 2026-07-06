# Security Policy

## Scope

This policy covers security vulnerabilities in the **my-practice** application itself:

- Authentication and session handling
- Access control (practice scoping, login requirements)
- Handling of personal and health data (client records, session notes, invoices)
- Clinical note encryption (`EncryptedTextField` / Fernet key handling)
- PDF generation, file upload, and export paths
- Django settings and deployment configuration in this repository

**Out of scope:** vulnerabilities in third-party dependencies (Django, PostgreSQL, WeasyPrint, etc.) — report those to the upstream projects. General hardening questions or deployment advice are welcome as regular issues.

## Reporting a Vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.** Health data is involved — a public disclosure before a fix is in place puts real people at risk.

Send a private report to:

**daniel.holbach@gmail.com**

Include in your report:

- A description of the vulnerability and the affected component
- Steps to reproduce (a minimal example is ideal)
- The potential impact as you see it
- Any suggested fix or mitigation, if you have one

## Response Time

This is a one-person project maintained alongside a psychotherapy practice. I aim to:

- **Acknowledge** your report within **5 business days**
- **Assess and respond** with a triage decision within **10 business days**
- **Release a fix** as soon as practically possible, prioritised by severity

If you haven't heard back within 5 business days, a follow-up email is welcome.

## After a Fix

Once a fix is released I'm happy to credit you in the changelog and release notes (if you'd like that). I don't currently offer a bug bounty, but I'm genuinely grateful for responsible disclosures on a project that handles sensitive health data.
