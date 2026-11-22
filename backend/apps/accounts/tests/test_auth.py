import pytest
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db
PW = "correct-horse-battery"


def test_register_sets_httponly_refresh_cookie_and_returns_access():
    c = APIClient()
    r = c.post("/api/auth/register/", {"email": "New@Example.com", "password": PW}, format="json")
    assert r.status_code == 201
    assert r.data["user"]["email"] == "new@example.com"
    assert "refresh" not in r.data  # refresh token never in the JSON body
    cookie = r.cookies["refresh_token"]
    assert cookie["httponly"] and cookie["path"] == "/api/auth/"


def test_register_rejects_weak_password_and_duplicates(user):
    c = APIClient()
    assert c.post("/api/auth/register/", {"email": "x@example.com", "password": "short"}, format="json").status_code == 400
    assert c.post("/api/auth/register/", {"email": "x@example.com", "password": "password123"}, format="json").status_code == 400
    assert c.post("/api/auth/register/", {"email": user.email, "password": PW}, format="json").status_code == 400


def test_login_and_me(user):
    c = APIClient()
    r = c.post("/api/auth/login/", {"email": user.email, "password": PW}, format="json")
    assert r.status_code == 200
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
    assert c.get("/api/auth/me/").data["email"] == user.email


def test_login_wrong_password(user):
    r = APIClient().post("/api/auth/login/", {"email": user.email, "password": "nope-nope-nope"}, format="json")
    assert r.status_code == 401


def test_protected_endpoints_require_auth():
    c = APIClient()
    for url in ["/api/knowledge/", "/api/collections/", "/api/search/history/", "/api/settings/",
                "/api/ai/conversations/", "/api/analytics/summary/", "/api/bookmarks/"]:
        assert c.get(url).status_code == 401, url


def test_refresh_rotates_and_logout_blacklists(user):
    c = APIClient()
    c.post("/api/auth/login/", {"email": user.email, "password": PW}, format="json")
    old = c.cookies["refresh_token"].value
    r = c.post("/api/auth/refresh/")
    assert r.status_code == 200 and r.data["access"]
    assert c.cookies["refresh_token"].value != old
    # the old (rotated) token is blacklisted
    c2 = APIClient()
    c2.cookies["refresh_token"] = old
    assert c2.post("/api/auth/refresh/").status_code == 401
    # logout blacklists the current one
    cur = c.cookies["refresh_token"].value
    assert c.post("/api/auth/logout/").status_code == 204
    c3 = APIClient()
    c3.cookies["refresh_token"] = cur
    assert c3.post("/api/auth/refresh/").status_code == 401


def test_admin_only_user_list(api, user, make_user, client_for):
    assert api.get("/api/auth/users/").status_code == 403
    admin = make_user("admin@example.com")
    admin.role = "admin"
    admin.save()
    assert client_for(admin).get("/api/auth/users/").status_code == 200
