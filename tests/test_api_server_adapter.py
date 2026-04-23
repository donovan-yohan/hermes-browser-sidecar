import json
import unittest

from tests._fakes import FakeUpstreamServer, REPO_ROOT  # noqa: F401  (path setup)

from hermes_browser_sidecar.transports.api_server import HermesAPIServerTransport


RESPONSE_FIXTURE = json.loads(
    (REPO_ROOT / "tests" / "fixtures" / "api_server_response.json").read_text()
)


def _make_handler(records: list[dict] | None = None):
    state = {"deletes": [], "gets": []}

    def handler(method: str, path: str, _headers: dict, body: bytes):
        if records is not None:
            records.append({"method": method, "path": path, "body": body})
        if method == "GET" and path == "/health":
            return 200, {"ok": True, "service": "hermes-api-server"}
        if method == "POST" and path == "/v1/responses":
            payload = json.loads(body.decode("utf-8")) if body else {}
            response = dict(RESPONSE_FIXTURE)
            response["previous_response_id"] = payload.get("previous_response_id")
            return 200, response
        if method == "GET" and path.startswith("/v1/responses/"):
            state["gets"].append(path)
            return 200, RESPONSE_FIXTURE
        if method == "DELETE" and path.startswith("/v1/responses/"):
            state["deletes"].append(path)
            return 200, {"id": path.rsplit("/", 1)[-1], "status": "cancelled"}
        return 404, {"ok": False, "error": "not found"}

    handler.state = state  # type: ignore[attr-defined]
    return handler


class ApiServerSendTests(unittest.TestCase):
    def test_send_posts_to_responses_and_stores_id(self) -> None:
        records: list[dict] = []
        handler = _make_handler(records)
        with FakeUpstreamServer(handler) as srv:
            transport = HermesAPIServerTransport(
                base_url=srv.url + "/v1", api_key="key", model="hermes-test"
            )
            session = transport.send_message(session_id="panel-1", message="hi")
            self.assertEqual(session.session_id, "panel-1")
            self.assertEqual(session.session_key, "resp_abc123")
            assistant = next(m for m in session.messages if m.role == "assistant")
            self.assertEqual(assistant.content, "Hello from Hermes API server.")

        post_record = next(r for r in records if r["method"] == "POST")
        body = json.loads(post_record["body"].decode("utf-8"))
        self.assertEqual(body["model"], "hermes-test")
        self.assertEqual(body["input"][-1], {"role": "user", "content": "hi"})

    def test_second_send_includes_previous_response_id(self) -> None:
        records: list[dict] = []
        handler = _make_handler(records)
        with FakeUpstreamServer(handler) as srv:
            transport = HermesAPIServerTransport(
                base_url=srv.url + "/v1", api_key="", model="hermes"
            )
            transport.send_message(session_id="panel-1", message="first")
            transport.send_message(session_id="panel-1", message="second")

        posts = [r for r in records if r["method"] == "POST"]
        self.assertEqual(len(posts), 2)
        first_body = json.loads(posts[0]["body"].decode("utf-8"))
        second_body = json.loads(posts[1]["body"].decode("utf-8"))
        self.assertNotIn("previous_response_id", first_body)
        self.assertEqual(second_body.get("previous_response_id"), "resp_abc123")


class ApiServerGetStateTests(unittest.TestCase):
    def test_unknown_session_returns_empty(self) -> None:
        with FakeUpstreamServer(_make_handler()) as srv:
            transport = HermesAPIServerTransport(
                base_url=srv.url + "/v1", api_key="", model="hermes"
            )
            session = transport.get_session_state(session_id="never-sent")
            self.assertEqual(session.messages, ())
            self.assertEqual(session.session_id, "never-sent")

    def test_known_session_fetches_from_upstream(self) -> None:
        records: list[dict] = []
        handler = _make_handler(records)
        with FakeUpstreamServer(handler) as srv:
            transport = HermesAPIServerTransport(
                base_url=srv.url + "/v1", api_key="", model="hermes"
            )
            transport.send_message(session_id="panel-1", message="hi")
            transport.get_session_state(session_id="panel-1")

        gets = [r for r in records if r["method"] == "GET" and r["path"].startswith("/v1/responses/")]
        self.assertEqual(len(gets), 1)
        self.assertEqual(gets[0]["path"], "/v1/responses/resp_abc123")


class ApiServerInterruptResetTests(unittest.TestCase):
    def test_interrupt_deletes_latest_response(self) -> None:
        records: list[dict] = []
        handler = _make_handler(records)
        with FakeUpstreamServer(handler) as srv:
            transport = HermesAPIServerTransport(
                base_url=srv.url + "/v1", api_key="", model="hermes"
            )
            transport.send_message(session_id="panel-1", message="hi")
            session = transport.interrupt_session(session_id="panel-1")
            self.assertEqual(session.progress.detail, "interrupted")

        deletes = [r for r in records if r["method"] == "DELETE"]
        self.assertEqual(len(deletes), 1)
        self.assertEqual(deletes[0]["path"], "/v1/responses/resp_abc123")

    def test_reset_clears_local_mapping(self) -> None:
        with FakeUpstreamServer(_make_handler()) as srv:
            transport = HermesAPIServerTransport(
                base_url=srv.url + "/v1", api_key="", model="hermes"
            )
            transport.send_message(session_id="panel-1", message="hi")
            transport.reset_session(session_id="panel-1")
            session = transport.get_session_state(session_id="panel-1")
            self.assertEqual(session.messages, ())
            self.assertEqual(session.session_key, "")


class ApiServerListTests(unittest.TestCase):
    def test_list_returns_local_sessions(self) -> None:
        with FakeUpstreamServer(_make_handler()) as srv:
            transport = HermesAPIServerTransport(
                base_url=srv.url + "/v1", api_key="", model="hermes"
            )
            transport.send_message(session_id="panel-a", message="a")
            transport.send_message(session_id="panel-b", message="b")
            sessions = transport.list_sessions(session_id="panel-a", limit=10)
            ids = {s.session_id for s in sessions}
            self.assertEqual(ids, {"panel-a", "panel-b"})


if __name__ == "__main__":
    unittest.main()
