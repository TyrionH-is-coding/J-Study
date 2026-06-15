# Backend Security Validation

Date: 2026-06-15

## Scope

This document records the current backend security controls for the pilot MVP. It focuses on five areas:

1. Authentication
2. Authorization
3. Input validation
4. Data ownership
5. Injection defense

This is not a full production security program. The current goal is to keep the MVP from regressing while auth, admin settings, upload, and deployment are still evolving.

## Current Validation

Run the focused security checks:

```powershell
python -m unittest discover -s tests -p test_security_controls.py -v
```

Run the full backend suite before deployment:

```powershell
python -m unittest discover -s tests -v
```

## Control Matrix

| Area | Current control | Verified by | Residual risk |
| --- | --- | --- | --- |
| Authentication | Email/password login requires a reusable invite code for registration. Passwords are hashed with `pwdlib[argon2]`. Sessions use opaque random tokens; only SHA-256 token hashes are stored. Session cookies are `HttpOnly`, `SameSite=Lax`, and `Secure` when `JSTUDY_COOKIE_SECURE=true`. | `test_authentication_requires_valid_session_and_sets_hardened_cookie`, `test_auth_service.py` | No session expiry, no login rate limiting, no email verification, no password reset, no MFA. Add these before broad public use. |
| Authorization | Admin endpoints call `require_admin()` and require `JSTUDY_ADMIN_TOKEN` when configured. Normal logged-in users cannot create invite codes. Hidden parser profiles are rejected for normal users. | `test_permission_control_blocks_logged_in_non_admin_from_admin_invites`, existing admin/parser tests | If `JSTUDY_ADMIN_TOKEN` is empty, admin endpoints are open for local development. Production deployment must set it. Query-string admin token is convenient for the temporary UI but should be replaced by a real admin session later. |
| Input validation | Registration validates email presence/shape and password length. Uploads require `.pdf`, `%PDF-` header, and configured max bytes. Upload filenames are normalized and stripped of path traversal characters. Scenario and parser profile values go through routers. | `test_input_validation_rejects_bad_auth_fields_and_sanitizes_upload_name`, existing upload/router tests | Request bodies still use `dict[str, Any]` instead of typed Pydantic models. Outline uploads do not yet have size/type limits. Invite-code format is only non-empty/unique. |
| Data ownership | Generated jobs store `owner_user_id`. All job status and artifact endpoints require a valid session and return `404` when another user requests the job. Job artifacts use private cache headers. | `test_data_ownership_blocks_other_users_from_all_job_artifacts`, existing ownership tests | Job metadata is still JSON-file backed. This is acceptable for the pilot, but formal user history should move job metadata into database tables and artifact access into object-storage ACL/signing rules. |
| Injection defense | Database access uses SQLModel/SQLAlchemy query construction instead of string-built SQL. SQL-injection-shaped email and invite payloads do not bypass login or invite matching. Upload filenames are sanitized before filesystem writes. | `test_sql_injection_payloads_do_not_bypass_login_or_invite_matching`, upload filename test | LLM prompt injection is not solved by SQL defenses. Web search and future MinerU/cloud parser integrations need their own allowlists, timeouts, and output handling. |

## Deployment Gate

Before exposing the pilot to external users:

- Set `JSTUDY_ADMIN_TOKEN`.
- Set `JSTUDY_SESSION_SECRET`.
- Set `POSTGRES_PASSWORD` and keep `DATABASE_URL` consistent with it.
- Set `JSTUDY_COOKIE_SECURE=true` behind HTTPS.
- Keep `JSTUDY_JOB_RETENTION_HOURS` nonzero.
- Use HTTPS on the public domain.
- Create invite codes only from the admin page or admin API.
- Verify:

```powershell
python -m unittest discover -s tests -v
docker compose -f deploy\docker-compose\api.compose.yml config
```

## Not Yet Worth Building

These are important, but not required before the first controlled pilot:

- Full role system beyond admin-token and normal user.
- MFA.
- Password reset workflow.
- Dedicated security event dashboard.
- Object-storage ACLs.
- Virus scanning for uploads.
- Formal SAST/DAST pipeline.

## Next Security Work

Add these in order when the pilot moves closer to real users:

1. Replace `dict[str, Any]` auth/admin request bodies with typed Pydantic models.
2. Add session expiry and session cleanup.
3. Add login/register rate limiting.
4. Add CSRF or Origin checks for cookie-authenticated state-changing routes.
5. Add security headers for the temporary UI or, more likely, enforce them at the reverse proxy.
6. Limit outline upload size and file type.
7. Move job metadata from JSON to database tables when user history becomes persistent.
8. Add LLM prompt-injection handling for user-supplied courseware, outlines, and web-search results.

## References

- OWASP ASVS: https://owasp.org/www-project-application-security-verification-standard/
- OWASP Authentication Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html
- OWASP Session Management Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html
- OWASP Authorization Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html
- OWASP Input Validation Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html
- OWASP SQL Injection Prevention Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html
