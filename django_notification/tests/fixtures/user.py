import pytest
from django.contrib.auth.models import User, Group, ContentType, Permission


@pytest.fixture
def user(db) -> User:
    """
    Fixture to create a standard User instance for testing.

    Args:
        db: The database fixture to set up the test database.

    Returns:
        User: The created User instance with username "testuser".
    """
    return User.objects.create_user(
        username="testuser", password="12345", email="testuser@example.com"
    )


@pytest.fixture
def qs_user(db) -> User:
    """
    Fixture to create a secondary User instance for testing.

    Args:
        db: The database fixture to set up the test database.

    Returns:
        User: The created User instance with username "queryset_user".
    """
    return User.objects.create_user(
        username="queryset_user", password="12345", email="queryset_user@example.com"
    )


@pytest.fixture
def admin_user(db) -> User:
    """
    Fixture to create a superuser with admin access for testing.

    Args:
        db: The database fixture to set up the test database.

    Returns:
        User: The created superuser with username "admin".
    """
    return User.objects.create_superuser(username="admin", password="password")


@pytest.fixture
def another_user(db) -> User:
    """
    Fixture to create another User instance for testing.

    Args:
        db: The database fixture to set up the test database.

    Returns:
        User: The created User instance with username "anotheruser".
    """
    return User.objects.create_user(
        username="anotheruser", password="54321", email="anotheruser@example.com"
    )


@pytest.fixture
def group(db) -> Group:
    """
    Fixture to create a Group instance for testing.

    Args:
        db: The database fixture to set up the test database.

    Returns:
        Group: The created Group instance with name "testgroup".
    """
    return Group.objects.create(name="testgroup")


@pytest.fixture
def qs_group(db) -> Group:
    """
    Fixture to create a secondary Group instance for testing.

    Args:
        db: The database fixture to set up the test database.

    Returns:
        Group: The created Group instance with name "queryset_group".
    """
    return Group.objects.create(name="queryset_group")


@pytest.fixture
def permission() -> Permission:
    """
    Fixture to create a sample Permission object for testing.


    Returns:
        Permission: The created Permission object with name "Can add user".
    """
    return Permission.objects.create(
        name="Can add user", codename="add_user", content_type_id=1
    )


@pytest.fixture
def group_with_perm(permission: Permission) -> Group:
    """
    Fixture to create a Group instance with a specific Permission attached.

    Args:
        permission (Permission): The Permission object to be added to the group.

    Returns:
        Group: The created Group instance with the given Permission.
    """
    group = Group.objects.create(name="Admins")
    group.permissions.add(permission)
    return group


@pytest.fixture
def user_content_type(db) -> ContentType:
    """
    Fixture to retrieve the ContentType for the User model.

    Args:
        db: The database fixture to set up the test database.

    Returns:
        ContentType: The ContentType instance for the User model.
    """
    return ContentType.objects.get_for_model(User)
