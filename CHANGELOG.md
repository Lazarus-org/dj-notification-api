# Changelog

## Unreleased

### Release hardening (version pending approval)

- Generate a real uv lock and verify Python 3.10–3.14 / Django 5.2, 6.0, 6.1 / DRF 3.18.
- **Breaking security default:** GET mutations and automatic read marking on GET
  are disabled by default. POST/DELETE routes and explicit legacy switches remain.
- Bulk sends and the admin send action now emit per-notification delivery intent
  while retaining the aggregate event. Low-level ORM writes remain outside this contract.
- Redact signal receiver exceptions before Django's robust-dispatch logger sees them.
- Serialize late digest fan-out with finalization; reopen completed slots for new
  children and keep failed slots under explicit requeue policy.
- Correct custom AdminSite instantiation and source typing; preserve historical migrations.
- Repair tox's runner, use isolated coverage files, add real PostgreSQL and installed-core
  CI gates, and require the full reusable CI workflow before gated publication.

### Infrastructure modernization (Phase 21, unreleased)

- Standardized build metadata on PEP 621 / Hatchling; uv replaces Poetry
  for development dependency management.
- Established Python 3.10–3.14, Django 5.2/6.0/6.1 and DRF 3.18 compatibility
  branches (breaking minimum supported version change; not yet released).
- Declared runtime `django-filter` and optional Channels/Redis extras.
- Replaced stale requirements exports and redundant pre-commit CI manifest;
  introduced tox-uv, Ruff, GitHub Actions OIDC publishing controls, and an
  offline metadata/matrix consistency check.
- **Release gate:** generate uv.lock, execute migrations and full test matrix,
  validate wheel/sdist and security scans before publishing.

### Documentation overhaul

- Replaced the legacy monolithic README with a concise package-facing overview,
  installation example, capability map, and links to focused references.
- Updated the Sphinx landing page, quick start, REST API reference, audience/role
  guide, contributor instructions, and supported version/tooling guidance.
- Aligned the optional Channels installation examples and removed dead Sphinx
  static/template references. No application behavior or dependency changes.


### Internal worker robustness (Phase 20)

- Share bounded retry-configuration and exponential-backoff logic between the
  outbox and external-delivery workers (including digest retries).
- Reconcile abandoned, retry-exhausted outbox/delivery claims in finite pages
  of at most 500 rows per claim attempt. A large backlog no longer triggers an
  unbounded terminal-state UPDATE in a single worker pass; claim readiness is
  rechecked before modifying rows to protect newly renewed leases.
- No public API, model, migration, or default delivery-policy changes.


### Added (phase 19)

- Read-only, database-backed historical delivery analytics with creation-time
  cohorts, terminal success rates, average/maximum queue latency and buckets,
  retry/attempt distributions, bounded category breakdowns, and UTC daily trends.
- Aggregated JSON/CSV/text operator reports via
  ``notification_delivery_report``. No recipient or notification content is
  collected or exported. No new schema, API endpoints, or required dependencies.
- Focused regression tests added; full Django runtime validation remains
  deferred to the final integration and release gate.


### Added (phase 18)

- Optional operator-managed category, priority-range and notification-status
  routing policies for external email/SMS/push/webhook channels. Deterministic
  REPLACE/ADD/REMOVE actions support priority-based channel escalation.
- Provider configuration and per-user preferences remain authoritative;
  route changes are rechecked immediately before individual or digest sends.
  No rules preserves existing delivery fan-out. Migration ``0012`` and
  ``docs/routing_rules.rst`` describe policy ordering and no-backfill limits.
- Added focused regression coverage. Full Django runtime validation remains
  deferred until the final integration gate.


### Added (phase 17)

- Read-only delivery observability across outbox, immediate-delivery and digest
  queues: status, due/scheduled work, expired and stranded leases, oldest due
  age, and privacy-safe per-channel aggregates. Exposed as importable snapshots
  and a management command with text, JSON and Prometheus exposition formats.
- Configurable health thresholds with opt-in nonzero exit status for monitoring,
  plus a bounded recent-failure report with allowlisted attempt-code labels.
- Dry-run previews for existing targeted requeue commands; default recovery
  behavior and worker state semantics are unchanged. No new migrations or
  required dependencies. Runtime verification remains deferred.


### Added (phase 16)

- Opt-in, per-channel IANA-timezone quiet hours with midnight and DST handling.
- Daily/weekly email digest envelopes, per-job membership and preference checks,
  leased processing, retry/backoff, and explicit failed-digest requeue.
- Mandatory and urgent notifications bypass delivery scheduling.
- Email digest sends use the existing localized message renderer with no
  stored plaintext content. REST schedule controls and migration ``0011``.
- Added focused regression tests. Django runtime verification remains deferred.


### Added (phase 15)

- Optional category/channel/locale message templates for email, SMS and push,
  with restricted string placeholders, recipient locale fallback, and admin
  editing. Built-in email delivery uses the renderer; custom provider adapters
  can opt in without introducing additional dependencies.
- Per-user external channel preferences, effective-state REST endpoints,
  mandatory-category enforcement, and bounded per-recipient-batch opt-out checks
  at enqueue with another eligibility check immediately before sending.
- Migration ``0010`` and usage/limitations in ``docs/templates_and_channels.rst``.
  Existing notifications and delivery behavior remain unchanged when no
  templates or overrides are configured. Full runtime validation deferred.


### Added (phase 14)

- Opt-in external email/SMS/push/webhook delivery pipeline built on the Phase 13
  durable outbox. A unique notification/recipient/channel job prevents duplicate
  fan-out after outbox replay; workers track independent leased retries.
- Django email and fixed-URL signed HTTPS webhook adapters, and a simple
  backend protocol for application-supplied SMS/push/provider adapters.
- Sanitized append-only attempt history, explicit failure requeue, stale-job
  cancellation on revoked user visibility, and no mandatory provider dependencies.
- Migration ``0009`` and ``docs/delivery.rst``; external delivery is disabled
  unless an application explicitly configures and registers it.
- Read-only Django admin views for delivery status and sanitized attempts.


### Added (phase 13)

- Opt-in transactional notification outbox with persistent ID-only lifecycle
  metadata, migration ``0008``, and ``DJANGO_NOTIFICATION_API_EVENT_DELIVERY``
  setting (``signal`` remains the default).
- Worker command for leased multi-worker claims, expired-lease recovery,
  bounded retries, and safe failure handling, plus operator requeue and
  delivered-only cleanup commands.
- Durable-mode Channels error propagation so failed layer dispatch is retried.
  At-least-once semantics, duplicate-handling requirements, operational
  deployment, and limitations documented in ``docs/outbox.rst``.


### Added (phase 12)

- Opt-in Django Channels integration under
  ``django_notification.integrations.channels``: explicit signal registration,
  a session-authenticated read-only WebSocket consumer, and an ASGI URL route.
- Bounded database-backed per-user fan-out for direct targets and dynamic or
  snapshot Django-group audiences, with privacy and preference filtering.
- Safe ID-only event hints, opaque per-user Channels groups, and fresh
  authorization checks immediately before sending over a socket.
- Documentation in ``docs/channels.rst`` and optional integration regression
  tests. Channels, Redis and Daphne remain optional, and no migration is added.
- Limitations are explicit: best-effort delivery, no hard-delete or aggregate
  sent push, and REST reconciliation after reconnect.


### Added (phase 11)

- Optional ``django_notification.events.notification_event`` Django signal
  with an immutable ID-only payload and stable lifecycle event kinds.
- Commit-aware dispatch for manager/service creation, updates, sends,
  read/unread transitions, soft clear, and hard deletion. Idempotent retries
  and sequential no-op single transitions do not re-emit events.
- ``Notification.mark_as_seen()`` now emits commit-aware read-state events
  without changing its historical permission-only eligibility rule.
- Event-consumer usage, rollback and best-effort limitations are documented in
  ``docs/events.rst``. No extra runtime dependency or migration is required.


### Added (phase 10)

- Managed ``NotificationCategory`` catalog, creation-time priority levels,
  per-user ``NotificationPreference`` opt-outs, and migration ``0007``.
  Existing notifications are assigned the seeded ``general`` category.
- Personal preference GET/PUT/PATCH endpoints, category catalog endpoint,
  and optional category/priority query filters for personal lists and counts.
- Mandatory categories bypass user opt-outs; optional categories can be
  re-enabled without modifying stored notification recipients or states.
- Idempotency and deduplication creation identity now includes category and
  priority. Compact list response defaults are unchanged; personal full
  detail responses add category and priority.


### Added

- Optional ``Notification.expires_at`` and migration ``0006``. Personal
  inbox queries and lifecycle operations now exclude expired records,
  while administrative querysets can still access retained records.
- Chainable ``active_at()`` and ``expired_at()`` selectors, and an opt-in
  ``prune_expired_notifications`` command with dry-run by default, an
  explicit execution switch, retention cutoff and bounded batches.
- Expiration-aware idempotency fingerprints and deduplication reuse rules.


- Transactional application-level ``idempotency_key`` and fixed-window
  ``deduplication_key``/``deduplication_window`` options on
  ``Notification.objects.create_notification()``. Concurrent retries share a
  unique database claim; conflicting event/audience reuse raises ``ValueError``.
  Existing unkeyed creation remains unchanged.
- ``NotificationCreationKey`` model and migration ``0005`` for atomic,
  database-backed event identity and deduplication windows (no Redis required).
  Claims cascade on hard deletion; expired deduplication claims are reusable.

- Optional `group_audience_mode="SNAPSHOT"` when creating notifications via the
  manager, persisting creation-time group members as direct recipients. Default
  `DYNAMIC` remains compatible with existing current-membership targeting.
- Django migration `0004` adds the audience mode field (existing rows remain
  dynamic), with admin visibility and trusted serializer metadata.

- Personal inbox summary (total/read/unread), safe preview, explicit per-item
  read/unread actions, bounded and atomic bulk read/unread, and selected
  activity soft-deletion endpoints. Counts and mutations respect both direct
  and current group recipients and each user's independent state.
- HTTP-correct POST/DELETE equivalents for existing mark-all and activity
  clear actions, including ``DELETE /activities/{id}/``.
- ``DJANGO_NOTIFICATION_API_ALLOW_LEGACY_GET_MUTATIONS`` and
  ``DJANGO_NOTIFICATION_API_RETRIEVE_MARKS_SEEN`` compatibility settings.

### Changed

- Legacy mutating GET responses include deprecation and no-store headers.
  The old mutating GET actions can be disabled without disabling new POST/
  DELETE counterparts; detail retrieval can be made read-only.

- Reuse the composable ``visible_to(user)`` policy for model-level permission
  checks, including inactive users and custom user models without groups.
- Scope individual activity clear and configured administrative hard-delete
  actions to the acting user's **seen, visible, undeleted** activity queryset.
- Use a privacy-safe full personal serializer: other recipient identities,
  group relationships/permissions, other users' seen state, internal
  content-type metadata, and arbitrary notification ``data`` are no longer
  returned by built-in self-service detail or full-list responses. This is
  an intentional HTTP response-contract change; the old comprehensive
  ``NotificationSerializer`` remains available for trusted admin code.

- Use model-backed, chainable querysets for notification and activity REST lists;
  preserve the existing compact JSON fields and configured detail serializers.
- Move legacy ``display_detail`` dictionary projection into a compatibility
  adapter outside the composable queryset implementation.
- Support both notification model instances and legacy dictionaries in the
  dynamic serializer, including the original default title behavior.

- Move notification creation, selective updates, hard/soft deletion, sent-state
  updates, and per-user read/clear mutations into a transactional lifecycle
  service. Manager entry points keep their existing signatures.
- Bound per-user bulk state writes to 500-ID keyset batches, with atomic
  rollback and conflict-tolerant inserts for concurrent duplicate attempts.
- Make notification creation and recipient/group assignment atomic.
- Keep legacy filtered-queryset mutation methods as deprecated delegating
  compatibility shims; new code should use the manager for state changes.

- Add composable model-returning notification filters for visibility,
  targeting, sent status, read state, and per-user soft deletion.
- Make recipient and group matching use OR semantics and database ``Exists``
  predicates, avoiding duplicated notifications and pagination counts.
- Treat explicitly empty recipient/group constraints as match-none, without
  changing the meaning of omitted constraints.
- Preserve legacy queryset response projections while consolidating their
  filtering logic; personal seen/unseen queries now include current group
  membership by default and cannot be widened by arbitrary target filters.


### Security

- Scope notification/activity self-service endpoints and per-user read/soft-delete state to direct recipients and members of targeted Django groups; staff status alone grants no access.
- Stop staff status from implicitly widening sent/unsent query results.
- Stop staff status from automatically selecting the full serializer for notification/activity list responses; personal detail retrieval now uses the privacy-safe serializer for authorized direct recipients and group members.

## v1.2.1 (2025-01-15)

### Refactor

- **serializers**: Improve notification serializer to support dynamic fields
- **settings**: Add dynamic serialization for Notification

## v1.2.0 (2024-10-13)

### 🛠️ Refactoring
- **refactor(docs)**: Improve settings and API guide structure. ([3f90aa3](https://github.com/MEHRSHAD-MIRSHEKARY/dj-notification-api/commit/3f90aa3))
  - Enhanced the structure of the settings and API guide documentation for better clarity and usability.

- **refactor(README)**: Improve settings section structure. ([583d733](https://github.com/MEHRSHAD-MIRSHEKARY/dj-notification-api/commit/583d733))
  - Reorganized the README settings section for a more intuitive flow and easier configuration understanding.

### 🔧 Chores
- **chore**: Update CI configuration for Python 3.13 support. ([c6d2bca](https://github.com/MEHRSHAD-MIRSHEKARY/dj-notification-api/commit/c6d2bca))
  - Updated CI pipeline configuration to add support for Python 3.13 and ensure compatibility.

- **chore**: Add support for Python 3.13 and drop support for Python 3.8. ([1516559](https://github.com/MEHRSHAD-MIRSHEKARY/dj-notification-api/commit/1516559))
  - Officially added support for Python 3.13 while discontinuing support for Python 3.8.

- **chore**: Update project details and required Python version. ([6904a08](https://github.com/MEHRSHAD-MIRSHEKARY/dj-notification-api/commit/6904a08))
  - Updated project documentation with the latest required Python version details.

### 📚 Documentation
- **docs(contributing)**: Fix typo in contributing.md. ([3efec98](https://github.com/MEHRSHAD-MIRSHEKARY/dj-notification-api/commit/3efec98))
  - Corrected minor typos in the contributing guide to enhance readability and accuracy.

### 🐛 Bug Fixes
- **fix**: Fix missing throttle rate for user scope in API throttling. ([43f0639](https://github.com/MEHRSHAD-MIRSHEKARY/dj-notification-api/commit/43f0639))
  - Resolved an issue where throttle rates were incorrectly applied or missing for the 'user' scope.

## v1.1.0 (2024-09-29)

### ✨ Features
- **feat(migrations)**: Add `db_comment` migration file. ([f6acab9](https://github.com/lazarus-org/dj-notification-api/commit/f6acab9))
  - Added a migration file to include database comments for improved documentation of database schema fields.

- **feat(conf)**: Add `exclude_serializer_null_fields` config. ([cd0e648](https://github.com/lazarus-org/dj-notification-api/commit/cd0e648))
  - Introduced a new configuration option to exclude null fields in serializer responses dynamically.

- **feat(models)**: Add `db_comment` for various models. ([ce29509](https://github.com/lazarus-org/dj-notification-api/commit/ce29509), [52e236b](https://github.com/lazarus-org/dj-notification-api/commit/52e236b), [fd96159](https://github.com/lazarus-org/dj-notification-api/commit/fd96159), [268bcff](https://github.com/lazarus-org/dj-notification-api/commit/268bcff))
  - Added `db_comment` to fields in the `Notification`, `NotificationRecipient`, `NotificationSeen`, and `DeletedNotification` models for better database schema clarity and maintenance.

- **feat(queryset)**: Add `NotificationDataAccessLayer` custom manager. ([88a6f92](https://github.com/lazarus-org/dj-notification-api/commit/88a6f92))
  - Implemented a custom manager providing data access methods for notifications, including creating, updating, and filtering notifications.

- **feat(admin)**: Add dynamic admin site support for Admin. ([114ff1c](https://github.com/lazarus-org/dj-notification-api/commit/114ff1c))
  - Integrated dynamic support for custom admin sites in the `dj-notification-api` package through configurable admin site settings.

### 🛠️ Refactoring
- **refactor(serializers)**: Update serializers to apply `exclude null fields` config. ([842aed0](https://github.com/lazarus-org/dj-notification-api/commit/842aed0))
  - Refactored `to_representation` method of serializers to accommodate the new configuration for excluding null fields.

- **refactor(models)**: Update model `Manager` class and apply ModelManager to `NotificationViewSet`. ([84d460d](https://github.com/lazarus-org/dj-notification-api/commit/84d460d), [b790f57](https://github.com/lazarus-org/dj-notification-api/commit/b790f57), [a420ca5](https://github.com/lazarus-org/dj-notification-api/commit/a420ca5))
  - Refined the `Notification` model’s manager for better data handling and incorporated the new manager into API viewsets.

### 🐛 Bug Fixes
- **fix(throttlings)**: Fix missing rate for 'user' scope error. ([43f0639](https://github.com/lazarus-org/dj-notification-api/commit/43f0639))
  - Fixed an issue where the throttle rates for different user roles were missing or incorrectly applied.

### 📚 Documentation
- **docs(contributing)**: Update contributing documentation to add migration-linter hints. ([4c863e0](https://github.com/lazarus-org/dj-notification-api/commit/4c863e0))
  - Expanded the contributing guide to include information and usage hints for the new migration-linter tool.

### 🔧 Chores
- **chore(pyproject)**: Add `django-migration-linter` config. ([2a29525](https://github.com/lazarus-org/dj-notification-api/commit/2a29525))
  - Added `django-migration-linter` as a development dependency and pre-commit hook for migration linting.

- **chore(dependency)**: Update `rest_framework` minimum version & pytest marker. ([69d7906](https://github.com/lazarus-org/dj-notification-api/commit/69d7906))
  - Updated the minimum required version of `django-rest-framework` and configured pytest markers for testing compatibility.

### ✅ Tests
- **tests**: Update test configurations for Manager and API tests. ([1ffef3a](https://github.com/lazarus-org/dj-notification-api/commit/1ffef3a), [c1339b2](https://github.com/lazarus-org/dj-notification-api/commit/c1339b2))
  - Applied the new ModelManager to the test cases for better validation and coverage of the new data access layer.

## v1.0.0 (2024-09-23)
- 🎉initial Release
