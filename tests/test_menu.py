import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine, SQLModel
from database import get_session
from main import app
from models.auth import User, Token, TokenUser, UserRole
from models.menu import Menu
from models.helper import id_generator
from datetime import datetime, timezone, timedelta


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture(name="admin_token")
def admin_token_fixture(session: Session):
    # Create admin user
    admin_user = User(
        username="admin",
        email="admin@test.com",
        hashed_password="hashed_password",
        role=UserRole.ADMIN,
        is_active=True
    )
    session.add(admin_user)
    session.commit()
    session.refresh(admin_user)

    # Create token
    token = Token(
        access_token="admin_token_123",
        refresh_token="refresh_123",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24)
    )
    session.add(token)
    session.commit()
    session.refresh(token)

    # Link token to user
    token_user = TokenUser(token_id=token.id, user_id=admin_user.id)
    session.add(token_user)
    session.commit()

    return token.access_token


@pytest.fixture(name="member_token")
def member_token_fixture(session: Session):
    # Create member user
    member_user = User(
        username="member",
        email="member@test.com",
        hashed_password="hashed_password",
        role=UserRole.MEMBER,
        is_active=True
    )
    session.add(member_user)
    session.commit()
    session.refresh(member_user)

    # Create token
    token = Token(
        access_token="member_token_123",
        refresh_token="refresh_123",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24)
    )
    session.add(token)
    session.commit()
    session.refresh(token)

    # Link token to user
    token_user = TokenUser(token_id=token.id, user_id=member_user.id)
    session.add(token_user)
    session.commit()

    return token.access_token


@pytest.fixture(name="sample_menu")
def sample_menu_fixture(session: Session):
    menu = Menu(
        icon="mdi-test",
        url="/test-url"
    )
    session.add(menu)
    session.commit()
    session.refresh(menu)
    return menu


def test_create_menu_success_admin(client: TestClient, admin_token: str):
    """Test creating menu item as admin."""
    response = client.post(
        "/menu/",
        json={
            "icon": "mdi-home",
            "url": "/home"
        },
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["icon"] == "mdi-home"
    assert data["url"] == "/home"
    assert "id" in data


def test_create_menu_forbidden_member(client: TestClient, member_token: str):
    """Test creating menu item as member (should fail)."""
    response = client.post(
        "/menu/",
        json={
            "icon": "mdi-home",
            "url": "/home"
        },
        headers={"Authorization": f"Bearer {member_token}"}
    )

    assert response.status_code == 403


def test_list_menu_items_success(client: TestClient, admin_token: str, sample_menu: Menu):
    """Test listing menu items."""
    response = client.get(
        "/menu/",
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert "menus" in data
    assert "total_count" in data
    assert data["total_count"] == 1
    assert len(data["menus"]) == 1


def test_list_menu_items_member_access(client: TestClient, member_token: str, sample_menu: Menu):
    """Test that member users can list menu items."""
    response = client.get(
        "/menu/",
        headers={"Authorization": f"Bearer {member_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total_count"] == 1


def test_get_menu_item_success(client: TestClient, admin_token: str, sample_menu: Menu):
    """Test getting specific menu item."""
    response = client.get(
        f"/menu/{sample_menu.id}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == sample_menu.id
    assert data["icon"] == sample_menu.icon
    assert data["url"] == sample_menu.url


def test_get_menu_item_not_found(client: TestClient, admin_token: str):
    """Test getting non-existent menu item."""
    response = client.get(
        "/menu/nonexistent_id",
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert response.status_code == 404


def test_update_menu_success_admin(client: TestClient, admin_token: str, sample_menu: Menu):
    """Test updating menu item as admin."""
    response = client.put(
        f"/menu/{sample_menu.id}",
        json={
            "icon": "mdi-updated",
            "url": "/updated-url"
        },
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["icon"] == "mdi-updated"
    assert data["url"] == "/updated-url"


def test_update_menu_forbidden_member(client: TestClient, member_token: str, sample_menu: Menu):
    """Test updating menu item as member (should fail)."""
    response = client.put(
        f"/menu/{sample_menu.id}",
        json={
            "icon": "mdi-updated",
            "url": "/updated-url"
        },
        headers={"Authorization": f"Bearer {member_token}"}
    )

    assert response.status_code == 403


def test_update_menu_not_found(client: TestClient, admin_token: str):
    """Test updating non-existent menu item."""
    response = client.put(
        "/menu/nonexistent_id",
        json={
            "icon": "mdi-updated",
            "url": "/updated-url"
        },
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert response.status_code == 404


def test_delete_menu_success_admin(client: TestClient, admin_token: str, sample_menu: Menu):
    """Test deleting menu item as admin."""
    response = client.delete(
        f"/menu/{sample_menu.id}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Menu item deleted successfully"


def test_delete_menu_forbidden_member(client: TestClient, member_token: str, sample_menu: Menu):
    """Test deleting menu item as member (should fail)."""
    response = client.delete(
        f"/menu/{sample_menu.id}",
        headers={"Authorization": f"Bearer {member_token}"}
    )

    assert response.status_code == 403


def test_delete_menu_not_found(client: TestClient, admin_token: str):
    """Test deleting non-existent menu item."""
    response = client.delete(
        "/menu/nonexistent_id",
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert response.status_code == 404


def test_create_menu_partial_update(client: TestClient, admin_token: str, sample_menu: Menu):
    """Test partial update of menu item."""
    # Only update icon
    response = client.put(
        f"/menu/{sample_menu.id}",
        json={
            "icon": "mdi-partial"
        },
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["icon"] == "mdi-partial"
    assert data["url"] == sample_menu.url  # Should remain unchanged


def test_unauthorized_access(client: TestClient):
    """Test accessing endpoints without token."""
    response = client.get("/menu/")
    assert response.status_code == 401

    response = client.post("/menu/", json={"icon": "mdi-test", "url": "/test"})
    assert response.status_code == 401