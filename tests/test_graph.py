"""Tests for the Graph layer. requests is mocked — nothing leaves the machine."""

from unittest.mock import Mock, patch

import pytest

from entra_stale_accounts import graph
from entra_stale_accounts.graph import (
    Credentials,
    GraphError,
    MissingCredentialsError,
    get_access_token,
    iter_users,
    load_credentials,
)

CREDS = Credentials("tenant-id", "client-id", "client-secret")


def json_response(status_code, payload):
    response = Mock()
    response.status_code = status_code
    response.json.return_value = payload
    response.text = str(payload)
    return response


class TestLoadCredentials:
    def test_reads_all_three_values_from_the_environment(self, monkeypatch, tmp_path):
        monkeypatch.setenv("ENTRA_TENANT_ID", "t")
        monkeypatch.setenv("ENTRA_CLIENT_ID", "c")
        monkeypatch.setenv("ENTRA_CLIENT_SECRET", "s")

        credentials = load_credentials(env_file=str(tmp_path / "absent.env"))
        assert (credentials.tenant_id, credentials.client_id) == ("t", "c")

    def test_finds_dotenv_in_the_working_directory(self, monkeypatch, tmp_path):
        # Regression: dotenv's default discovery starts at the installed
        # package's path, so an installed CLI never saw the user's .env.
        for name in ("ENTRA_TENANT_ID", "ENTRA_CLIENT_ID", "ENTRA_CLIENT_SECRET"):
            monkeypatch.delenv(name, raising=False)
        (tmp_path / ".env").write_text(
            "ENTRA_TENANT_ID=t\nENTRA_CLIENT_ID=c\nENTRA_CLIENT_SECRET=s\n"
        )
        monkeypatch.chdir(tmp_path)

        credentials = load_credentials()
        assert credentials.tenant_id == "t"

    def test_missing_values_are_named_in_the_error(self, monkeypatch, tmp_path):
        monkeypatch.setenv("ENTRA_TENANT_ID", "t")
        monkeypatch.delenv("ENTRA_CLIENT_ID", raising=False)
        monkeypatch.delenv("ENTRA_CLIENT_SECRET", raising=False)

        with pytest.raises(MissingCredentialsError) as excinfo:
            load_credentials(env_file=str(tmp_path / "absent.env"))

        assert "ENTRA_CLIENT_ID" in str(excinfo.value)
        assert "ENTRA_CLIENT_SECRET" in str(excinfo.value)


class TestGetAccessToken:
    def test_returns_the_token_on_success(self):
        with patch.object(graph.requests, "post", return_value=json_response(200, {"access_token": "abc"})):
            assert get_access_token(CREDS) == "abc"

    def test_raises_with_the_error_description(self):
        payload = {"error": "invalid_client", "error_description": "Secret is expired."}
        with patch.object(graph.requests, "post", return_value=json_response(401, payload)):
            with pytest.raises(GraphError, match="Secret is expired"):
                get_access_token(CREDS)

    def test_raises_when_no_token_is_returned(self):
        with patch.object(graph.requests, "post", return_value=json_response(200, {})):
            with pytest.raises(GraphError, match="no access_token"):
                get_access_token(CREDS)


class TestIterUsers:
    def test_requests_sign_in_activity_explicitly(self):
        with patch.object(graph.requests, "get", return_value=json_response(200, {"value": []})) as mock_get:
            list(iter_users("token"))

        url = mock_get.call_args[0][0]
        assert "signInActivity" in url and "$select=" in url

    def test_sends_the_bearer_token(self):
        with patch.object(graph.requests, "get", return_value=json_response(200, {"value": []})) as mock_get:
            list(iter_users("token"))

        assert mock_get.call_args.kwargs["headers"]["Authorization"] == "Bearer token"

    def test_follows_odata_next_link_paging(self):
        pages = [
            json_response(200, {"value": [{"id": "1"}], "@odata.nextLink": "https://graph/next"}),
            json_response(200, {"value": [{"id": "2"}]}),
        ]
        with patch.object(graph.requests, "get", side_effect=pages) as mock_get:
            users = list(iter_users("token"))

        assert [u["id"] for u in users] == ["1", "2"]
        assert mock_get.call_args_list[1][0][0] == "https://graph/next"

    def test_surfaces_graph_error_messages(self):
        payload = {"error": {"code": "Authorization_RequestDenied", "message": "Insufficient privileges."}}
        with patch.object(graph.requests, "get", return_value=json_response(403, payload)):
            with pytest.raises(GraphError, match="Insufficient privileges"):
                list(iter_users("token"))


class TestThrottling:
    def test_waits_out_a_429_and_honors_retry_after(self):
        throttled = json_response(429, {"error": {"message": "Too many requests."}})
        throttled.headers = {"Retry-After": "7"}
        responses = [throttled, json_response(200, {"value": [{"id": "1"}]})]

        with patch.object(graph.requests, "get", side_effect=responses) as mock_get:
            with patch.object(graph.time, "sleep") as mock_sleep:
                users = list(iter_users("token"))

        assert [u["id"] for u in users] == ["1"]
        assert mock_get.call_count == 2
        mock_sleep.assert_called_once_with(7)

    def test_falls_back_to_default_wait_without_retry_after(self):
        throttled = json_response(429, {"error": {"message": "Too many requests."}})
        throttled.headers = {}
        responses = [throttled, json_response(200, {"value": []})]

        with patch.object(graph.requests, "get", side_effect=responses):
            with patch.object(graph.time, "sleep") as mock_sleep:
                list(iter_users("token"))

        mock_sleep.assert_called_once_with(graph.DEFAULT_RETRY_AFTER)

    def test_gives_up_after_repeated_throttling(self):
        throttled = json_response(429, {"error": {"message": "Too many requests."}})
        throttled.headers = {"Retry-After": "1"}

        with patch.object(graph.requests, "get", return_value=throttled) as mock_get:
            with patch.object(graph.time, "sleep") as mock_sleep:
                with pytest.raises(GraphError, match="429"):
                    list(iter_users("token"))

        # The original request plus MAX_THROTTLE_RETRIES retries, then the error.
        assert mock_get.call_count == graph.MAX_THROTTLE_RETRIES + 1
        assert mock_sleep.call_count == graph.MAX_THROTTLE_RETRIES
