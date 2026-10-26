# Phase 4: notification API correctness/security review

This review targets the Phase-3 refactored codebase and preserves dynamic
Django-group recipient visibility, direct recipients, and per-user read/deletion
state. It is **not** an assertion that the full regression suite has passed.

## Fixed in this phase

- Model `NotificationPermission` now delegates to the same query policy as
  `.visible_to(user)` rather than implementing a second group-membership rule.
  Anonymous, unsaved, inactive and custom no-groups identities get consistent
  handling. The policy uses the notification's database alias.
- Individual activity soft/hard deletion resolves the object through the
  configured, user-scoped, *seen activity* queryset before invoking lifecycle
  operations. An unaddressed or unread ID does not become globally mutable
  merely because the requester has staff privileges.
- Built-in personal full-detail representations no longer expose other users'
  identities, global seen-state, permission groups, content-type metadata or
  unreviewed arbitrary JSON `data`. The administrative `NotificationSerializer`
  still exists as an explicit trusted-code serializer. Applications depending
  on the old personal detail payload must migrate deliberately.
- Default built-in serializer selection no longer eagerly prefetches unrelated
  groups and seen-by rows when rendering the privacy-safe personal schema.
- Group-membership subqueries use the queryset's DB alias.

## Remaining risks and follow-up gates

1. **GET side effects (HTTP contract):** `retrieve` marks notifications read,
   and mark-all/clear/hard-delete actions currently use GET. Do not deploy
   aggressive prefetchers or cache these endpoints. Replace these with explicit
   unsafe HTTP methods in Phase 5, with an announced compatibility transition.
2. **Admin hard delete:** When expressly enabled, it removes the underlying
   notification for *all* its recipients, even though the initiating admin must
   own a seen activity. Consider making hard deletion a separate administrative
   API protected by specific permissions, or deprecating it for personal feeds.
3. **Custom serializers/configuration:** Explicit `SERIALIZER_CLASS` and
   `SERIALIZER_FIELDS` overrides can disclose arbitrary fields. They require
   an application-level security review; custom serializers are not rewritten.
4. **Direct manager/API trust:** `delete_notification(..., soft_delete=False)`
   is an explicitly privileged internal operation; no general-user permission
   is enforced on this Python callable. Consumers must not expose it directly.
5. **Runtime validation:** Django, DRF, pytest-django and django-filter could
   not be installed in this execution environment. Django system checks,
   migration consistency, complete tests, PostgreSQL concurrency and other
   database backends remain unverified.

## Release gates

- Exercise the full test suite on the project's supported Python/Django/DRF
  matrix; run database migrations and `makemigrations --check --dry-run`.
- Verify custom serializer configuration and production authentication paths.
- Run load/query-count assertions for group feeds and concurrent bulk state
  mutation on supported production database engines.
- Announce the intentional personal full-detail response change to clients.
