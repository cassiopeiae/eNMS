from logging import CRITICAL, disable
from flask.testing import FlaskClient
from typing import Callable, Dict

disable(CRITICAL)

urls: Dict[str, tuple] = {
    "": ("/", "/dashboard"),
    "/admin": (
        "/user_management",
        "/login",
        "/administration",
        "/advanced",
        "/instance_management",
    ),
    "/inventory": (
        "/device_management",
        "/configuration_management",
        "/link_management",
        "/pool_management",
        "/import_export",
    ),
    "/views": ("/geographical_2D", "/geographical_2DC", "/geographical_3D"),
    "/automation": ("/service_management", "/workflow_management", "/workflow_builder"),
    "/scheduling": ("/task_management", "/calendar"),
    "/logs": ("/log_management", "/log_automation"),
}

free_access = {"/", "/admin/login", "/admin/create_account"}


def check_pages(*pages: str) -> Callable:
    def decorator(function: Callable) -> Callable:
        def wrapper(user_client: FlaskClient) -> None:
            function(user_client)
            for page in pages:
                r = user_client.get(page, follow_redirects=True)
                assert r.status_code == 200

        return wrapper

    return decorator


def check_blueprints(*blueprints: str) -> Callable:
    def decorator(function: Callable) -> Callable:
        def wrapper(user_client: FlaskClient) -> None:
            function(user_client)
            for blueprint in blueprints:
                for page in urls[blueprint]:
                    r = user_client.get(blueprint + page, follow_redirects=True)
                    assert r.status_code == 200

        return wrapper

    return decorator


def test_authentication(base_client: FlaskClient) -> None:
    for blueprint, pages in urls.items():
        for page in pages:
            page_url = blueprint + page
            expected_code = 200 if page_url in free_access else 403
            r = base_client.get(page_url, follow_redirects=True)
            assert r.status_code == expected_code


def test_urls(user_client: FlaskClient) -> None:
    for blueprint, pages in urls.items():
        for page in pages:
            page_url = blueprint + page
            r = user_client.get(page_url, follow_redirects=True)
            assert r.status_code == 200
    r = user_client.get("/admin/logout", follow_redirects=True)
    test_authentication(user_client)
