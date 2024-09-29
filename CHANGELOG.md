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
