# Combined refactor verification gate (Phases 1–5)

This gate uses the uploaded `dj-notification-api` 1.2.1 source as the baseline,
followed by the corrected group-access authorization patch and Phases 1–5.
It fixes an authorization issue found during source review; **it is not a
claim that Django runtime validation has passed**.

## Security defect fixed

`ConfigurableAttrsMixin.configure_attrs()` previously replaced DRF's
`permission_classes` supplied to `@action` routes by `ViewSetMixin.as_view()`.
Consequently the `IsAdminUser` restriction on the optional activity hard-delete
actions could be dropped and an ordinary authenticated user could invoke them
for activities they were otherwise entitled to see. This was especially
important for group-addressed notifications: a group member should be able to
read and soft-delete their own activity but must not permanently remove the
notification for everyone else.

The updated mixin enforces `IsAuthenticated` and the project-configured extra
permission while retaining action-specific and class-level permission classes.
The regression tests cover both hard-delete routes, a legitimate staff request,
configured extra permissions, and permission declarations on the view class.

## Source-level verification completed

- Safe original ZIP extraction (no traversal or symlink entries).
- Each of the six historical patches applied sequentially without conflicts:
  corrected group authorization, Phase 1 queryset, Phase 2 lifecycle, Phase 3
  serialization, Phase 4 security, and Phase 5 inbox API.
- Reconstructed source matched the Phase 5 snapshot file-for-file.
- Python 3.9 syntax parsing, compilation, and `git diff --check` passed.
- The fix contains no database schema or migration changes.

## Runtime checks still required

The sandbox cannot resolve `pypi.org` and has no Django/DRF runtime; the
attempted `uv pip install` failed on DNS resolution. **No Django test, system
check, migration, or PostgreSQL race test has been executed in this gate.**
In a dependency-equipped environment, run:

```bash
python -m pytest -q -o addopts='' \
  django_notification/tests/api/security/test_action_permissions.py \
  django_notification/tests/api/test_personal_notification_boundaries.py \
  django_notification/tests/api/test_inbox_api.py
python -m pytest -q -o addopts=''
python manage.py check
python manage.py makemigrations --check --dry-run
```

The source provides a standalone Django test setup in
`django_notification/tests/setup.py`; verify the commands under the CI matrix
and representative supported Django/DRF versions before releasing. Re-run
PostgreSQL-specific concurrency and multi-database checks using a configured
PostgreSQL test environment, since the default test DB is in-memory SQLite.

## Remaining items

- Migrate legacy GET mutations to POST/DELETE after client transition.
- Review conditional action registration and configurable serializer
  extensions for a future compatibility-focused checkpoint.
- Validate permissions and queryset behavior against custom user models,
  both with and without the Django groups relation.
