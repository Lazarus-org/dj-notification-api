## Code of Conduct for Contributing to dj-notification-api

we’re thrilled that you want to contribute to `dj-notification-api`! to ensure a positive and protective environment for everyone involved, please adhere to the following guidelines.

## Contribution Workflow

1. **Fork and Clone**: Start by forking the `dj-notification-api` repository on Github and cloning it to your local machine:
    ```bash
    git clone https://github.com/lazarus-org/dj-notification-api.git
    cd dj-notification-api
    ```

2. **Create a Branch**: Create a new branch for your feature or bugfix:
    ```bash
    git checkout -b feature/your-feature-name
    ```

3. **Install Dependencies**: Use Poetry to install the project’s dependencies. if poetry isn’t installed, refer to the [Poetry installation guide](https://python-poetry.org/docs/#installation)
    ```bash
    poetry install
    ```

4. **Write Code and Tests**: Make your changes and write tests for your new code. Ensure that all tests pass:
   ```bash
    poetry run pytest
    ```
5. **Run Code Quality Checks**: Ensure code quality with Pylint:
    ```bash
    poetry run pylint django_notification
    ```

6. **Commit Your Changes**: Use Commitizen to commit your changes according to the Conventional Commits specification:
    ```bash
    cz commit
    ```

7. **Push and Create a PR**: Push your changes to your fork on GitHub and open a pull request:
    ```bash
    git push origin feature/your-feature-name
    ```

8. **Bump Version**: Use Commitizen to update the version.
    ```bash
    cz bump
    ```

9. **Generate Changelog**: Create a changelog with Commitizen:
    ```bash
    cz changelog
    ```

10. **Export Dependencies**: Export the project dependencies for development and production:
    ```bash
    poetry export -f requirements.txt --output packages/requirements.txt --without-hashes
    poetry export -f requirements.txt --dev --output packages/requirements-dev.txt --without-hashes
    ```

## Commitizen Message Rule

Commitizen follows the Conventional Commits specification. Your commit message should be structured as follows:

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

## Example of Commit Messages

### 1. Initialization of Core
```
feat(core): initialize the core module

- Set up the core structure
- Added initial configurations and settings
- Created basic utility functions
```

### 2. Release with Build and Tag Version
```
chore(release): build and tag version 1.0.0

- Built the project for production
- Created a new tag for version 1.0.0
- Updated changelog with release notes
```

### 3. Adding a New Feature
```
feat(auth): add user authentication

- Implemented user login and registration
- Added JWT token generation and validation
- Created middleware for protected routes
```

### 4. Fixing a Bug
```
fix(api): resolve issue with data fetching

- Fixed bug causing incorrect data responses
- Improved error handling in API calls
- Added tests for the fixed bug
```

### 5. Update Documentation (Sphinx)
```
docs(sphinx): update API documentation

- Updated the Sphinx documentation for API changes
- Added examples for new endpoints
- Fixed typos and formatting issues
```

### 6. Update Dependencies
```
chore(deps): update project dependencies

- Updated all outdated npm packages
- Resolved compatibility issues with new package versions
- Ran tests to ensure no breaking changes
```

### 7. Update Version for Build and Publish
```
chore(version): update version to 2.1.0 for build and publish

- Incremented version number to 2.1.0
- Updated package.json with the new version
- Prepared for publishing the new build
```

### 8. Adding Unit Tests
```
test(auth): add unit tests for authentication module

- Created tests for login functionality
- Added tests for registration validation
- Ensured 100% coverage for auth module
```

### 9. Refactoring Codebase
```
refactor(core): improve code structure and readability

- Refactored core module to enhance readability
- Extracted utility functions into separate files
- Updated documentation to reflect code changes
```

### 10. Improving Performance
```
perf(parser): enhance parsing speed

- Optimized parsing algorithm for better performance
- Reduced the time complexity of the parsing function
- Added benchmarks to track performance improvements
```

Thank you for contributing to `dj-notification-api`! We look forward to your contributions.
