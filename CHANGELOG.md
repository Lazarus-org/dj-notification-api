# Changelog

## v2.0.1 (2026-10-30)

### Fixed

- Declare Python 3.14 support in the package metadata, matching the existing
  tox and GitHub Actions compatibility matrices.

## v2.0.0 (2026-10-30)

Version 2.0 adds recipient-scoped inboxes, notification lifecycle services,
and optional background delivery. This major release changes personal API
permissions, response fields, and the HTTP methods used to change notification
state. Review the [upgrade guide](docs/upgrading.rst) before upgrading from 1.x.

### Breaking changes and security

- **GET requests are read-only by default.** Retrieving a notification no longer
  marks it as seen. Use POST for read-state and bulk mutations, and DELETE for
  deletion. Session-authenticated clients must provide CSRF tokens for writes.
- **Staff and superusers follow recipient rules on personal endpoints.** Access
  requires a direct recipient relationship or eligible group membership; staff
  status no longer widens notification selections or grants cross-user access.
- **Personal detail responses protect recipient privacy.** Built-in personal
  serializers omit other recipients, groups, other users' read state, and
  arbitrary notification data. Staff no longer automatically receive a full
  administrative representation from personal list endpoints.
- **Framework requirements have changed.** Python 3.10+ and DRF 3.18 are required.
  Python 3.10/3.11 use Django 5.2; Python 3.12+ use Django 6.0 or 6.1 under the
  package's dependency constraints. Upgrade older framework installations first.
- Queryset mutation helpers are deprecated in favor of `Notification.objects`
  manager methods. Direct ORM writes do not emit the lifecycle events used by
  delivery integrations.

### Inbox, audiences, and notification lifecycle

- Add composable, model-returning queryset selectors for audience visibility,
  sent state, read state, deletion, and expiration. Keep legacy projection
  selectors available while separating serialization from database selection.
- Add inbox summary counts, read-only previews, and bulk read/unread actions.
  Read and cleared state belong to each recipient independently; clearing one
  user's activity does not remove shared content for other recipients.
- Combine direct and group recipients without duplicate inbox items. Support
  dynamic group audiences that follow current membership and snapshot audiences
  that copy the group's members into direct recipients at creation time.
- Add idempotency keys for notification creation so retried application requests
  can reuse an existing notification instead of creating duplicates.
- Add expiration timestamps that remove expired notifications from personal
  access, plus a retention cleanup command with a dry-run preview.
- Add categories, priorities, and per-user category preferences. Mandatory
  categories remain visible despite an optional-category preference.
- Add transaction-aware lifecycle events for manager operations. Receivers run
  after successful commits; rolled-back mutations do not dispatch events.

### Optional delivery and integrations

- Add a transactional outbox that persists lifecycle event intent with the
  notification mutation. Workers dispatch persisted events with leases,
  retry limits, backoff, pruning, and explicit failed-event requeue commands.
- Add pluggable email, SMS, push, and webhook delivery channels. Provide a Django
  email backend and interfaces for application-provided adapters; each recipient
  and channel has independent delivery state and retry handling.
- Add localized notification templates, rendering context, and per-user channel
  preferences. Add configurable routing rules to select delivery channels.
- Add per-user, per-channel quiet hours and delivery schedules, including daily
  and weekly email digests. Scheduling handles local time zones and daylight
  saving transitions; mandatory categories and urgent notifications bypass
  quiet hours and digest batching.
- Add an optional Django Channels integration with authenticated consumers,
  recipient-aware event fan-out, and configurable channel-layer delivery.
- External delivery and Channels require explicit configuration and receiver
  registration. Channels, Redis, Celery, and provider SDKs remain optional;
  the core inbox does not require external delivery workers.

### Correctness, recovery, and diagnostics

- Preserve action-specific DRF permissions when applying configurable view
  settings, including the administrator restriction on permanent deletion.
- Make bulk sends and the admin send action emit individual notification event
  intent while preserving the aggregate event for existing receivers.
- Redact signal receiver exceptions before robust dispatch logs them.
- Bound exhausted-job recovery work, share capped retry backoff across workers,
  and recheck claim eligibility before terminal-state updates.
- Serialize late digest additions with finalization, reopen completed slots for
  new entries, and retain explicit recovery for failed digest slots.
- Add queue health reports, sanitized failure diagnostics, delivery analytics,
  and targeted requeue previews for outbox events, delivery jobs, and digests.
  External providers still need idempotency handling for at-least-once delivery.
- Correct custom admin-site initialization and support swapped user models,
  including direct-only notification use without a Django groups relationship.

### Packaging and development

- Replace Poetry and requirements-file development setup with uv and a committed
  lockfile. Refresh dependency constraints and retain compatible tooling versions
  for Python 3.10 through Python-version markers.
- Expand CI to cover the framework matrix, PostgreSQL concurrency, installed
  packages without optional integrations, documentation, security, and packaging.
  Keep the 100% coverage requirement in the test and pre-commit configuration.
- Make Commitizen update the package version in both `pyproject.toml` and
  `uv.lock`, validate the lockfile offline, and include it in the bump commit.
- Expand documentation with configuration examples, delivery setup, worker
  operations, troubleshooting, and migration guidance.

### Upgrading from 1.x

1. Install a compatible Python/Django/DRF environment and apply the package's
   migrations with `python manage.py migrate`; retain existing migration history.
2. Update clients to explicit POST/DELETE operations and review assumptions about
   personal response fields and staff access. Temporary legacy GET switches are
   documented in the [upgrade guide](docs/upgrading.rst); leave them disabled
   after clients have migrated.
3. Move application mutations to manager methods before enabling lifecycle
   receivers, the outbox, or external delivery. Existing notifications are not
   automatically backfilled into a newly enabled delivery integration.
4. Configure optional integrations deliberately and exercise recipient access,
   retries, retention previews, and provider idempotency in the host application.

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
