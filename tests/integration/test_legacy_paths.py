"""Ensure deprecated API paths remain unavailable."""

from http import HTTPStatus

from flask.testing import FlaskClient


LEGACY_PATHS = (
    "/api/v1/share",
    "/api/v1/share/<token>",
    "/api/v1/export",
)


def test_legacy_share_and_export_paths_removed(client: FlaskClient) -> None:
    """Legacy share/export endpoints should now return HTTP 404."""

    for path in LEGACY_PATHS:
        response = client.get(path.replace("<token>", "example"))
        assert response.status_code == HTTPStatus.NOT_FOUND
