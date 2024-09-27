from typing import List

# Contributing to dj-notification-api


We’re excited that you’re interested in contributing to `dj-notification-api`! Whether you’re fixing a bug, adding a feature, or improving the project, your help is appreciated.

## Overview


- **Setting Up Your Environment**
- **Testing Your Changes**
- **Code Style Guidelines**
- **Utilizing Pre-commit Hooks**
- **Creating a Pull Request**
- **Reporting Issues**
- **Resources**

## Setting Up Your Environment


1. **Fork the Repository:**

   Begin by forking the `dj-notification-api` repository on GitHub. This creates your own copy where you can make changes.

2. **Clone Your Fork:**

   Use the following command to clone your fork locally:

   ```bash
   git clone https://github.com/your-username/dj-notification-api.git
   cd dj-notification-api
   ```

3. **Install Dependencies:**

   Install the necessary dependencies using `Poetry`. If Poetry isn't installed on your machine, you can find installation instructions on the [Poetry website](https://python-poetry.org/docs/#installation).

   ```bash
   poetry install
   ```

4. **Create a Feature Branch:**

   It’s a good practice to create a new branch for your work:

   ```bash
   git checkout -b feature/your-feature-name
   ```

## Testing Your Changes

We use `pytest` for running tests. Before submitting your changes, ensure that all tests pass:

   ```bash
   poetry run pytest
   ```

If you’re adding a new feature or fixing a bug, don’t forget to write tests to cover your changes.


## Code Style Guidelines

Maintaining a consistent code style is crucial. We use `black` for code formatting and `isort` for import sorting. Make sure your code adheres to these styles:

   ```bash
    poetry run black .
    poetry run isort .
   ```
For linting, `pylint` is used to enforce style and catch potential errors:

   ```bash
   poetry run pylint dj-notification-api
   ```

## Utilizing Pre-commit Hooks

Pre-commit hooks are used to automatically check and format code before you make a commit. This ensures consistency and quality in the codebase.

1. **Install Pre-commit:**

   ```bash
   poetry add --dev pre-commit
   ```

2. **Set Up the Hooks:**

   Install the pre-commit hooks by running:

   ```bash
   poetry run pre-commit install
   ```
3. **Set Up django_migration_linter:**

    To ensure that `django_migration_linter` functions properly, add it to the INSTALLED_APPS section in your `settings.py` file:

   ```python
   INSTALLED_APPS = [
      # ...
      'django_migration_linter'
      # ...
   ]
   ```
This step integrates the migration linter into your Django project, allowing it to monitor migrations effectively.

4. **Manual Hook Execution (Optional):**

   To run all hooks manually on your codebase:

   ```bash
   poetry run pre-commit run --all-files
   ```

## Creating a Pull Request

Once your changes are ready, follow these steps to submit them:

1. **Commit Your Changes:**

   Write clear and concise commit messages. Following the [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) format is recommended:

   ```bash
   git commit -am 'refactor: update api notification permission class'
   ```
2. **Push Your Branch:**

   Push your branch to your fork on GitHub:

   ```bash
   git push origin feature/your-feature-name
   ```

3. **Open a Pull Request:**

   Go to the original `dj-notification-api` repository and open a pull request. Include a detailed description of your changes and link any related issues.

4. **Respond to Feedback:**

   After submitting, a maintainer will review your pull request. Be prepared to make revisions based on their feedback.

## Reporting Issues

Found a bug or have a feature request? We’d love to hear from you!

1. **Open an Issue:**

   Head over to the `Issues` section of the `dj-notification-api` repository and click "New Issue".

2. **Describe the Problem:**

   Fill out the issue template with as much detail as possible. This helps us understand and address the issue more effectively.

## Resources

Here are some additional resources that might be helpful:

- [Poetry Documentation](https://python-poetry.org/docs/)
- [Black Documentation](https://black.readthedocs.io/en/stable/)
- [isort Documentation](https://pycqa.github.io/isort/)
- [pytest Documentation](https://docs.pytest.org/en/stable/)
- [pylint Documentation](https://pylint.pycqa.org/en/latest/)
- [Pre-commit Documentation](https://pre-commit.com/)

---

Thank you for your interest in contributing to `dj-notification-api`! We look forward to your contributions.
