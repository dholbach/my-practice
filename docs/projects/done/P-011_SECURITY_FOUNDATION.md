# P-011: Security Foundation

**Status**: ✅ Complete (Phase 1–3 done; Phase 4 = Fernet field encryption, done in P-009)  
**Completed**: Feb 2026

---

## What Was Done

- Full-disk encryption (LUKS) on the practice laptop
- YubiKey FIDO2 enrollment (3 keys) for LUKS unlock
- Encrypted backups: external USB (Pika / AES-256) and NAS
- Systemd backup timer hardened for Bluefin / SELinux
- DPIA template created: [`docs/operations/DPIA-template.md`](../../operations/DPIA-template.md)

## Personal Operational Notes

Detailed setup steps (Bluefin-specific commands, Yubikey enrollment, NAS configuration,
restore smoke-test procedures) live in `memory/P-011_SECURITY_FOUNDATION.md` (gitignored).

## OSS-Relevant Guides

What adopters need to know:

- Encryption model and what you must provide yourself:
  [`docs/guides/CLINICAL_DATA_SECURITY.md`](../../guides/CLINICAL_DATA_SECURITY.md)
- Backup scripts and systemd timers:
  [`docs/operations/SCRIPTS.md`](../../operations/SCRIPTS.md)
  and [`docs/guides/BACKUP_SETUP.md`](../../guides/BACKUP_SETUP.md)
- DPIA template: [`docs/operations/DPIA-template.md`](../../operations/DPIA-template.md)
