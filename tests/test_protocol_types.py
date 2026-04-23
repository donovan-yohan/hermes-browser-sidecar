import unittest

from tests._fakes import (  # noqa: F401  (path setup)
    Capabilities,
    PageContext,
    SidecarMessage,
    SidecarProgress,
    SidecarSession,
)


class ProgressTests(unittest.TestCase):
    def test_round_trip(self) -> None:
        original = SidecarProgress(running=True, error="boom", detail="explained")
        self.assertEqual(SidecarProgress.from_dict(original.to_dict()), original)

    def test_from_dict_requires_running(self) -> None:
        with self.assertRaises(ValueError):
            SidecarProgress.from_dict({})

    def test_from_dict_rejects_non_string_error(self) -> None:
        with self.assertRaises(ValueError):
            SidecarProgress.from_dict({"running": False, "error": 42})


class PageContextTests(unittest.TestCase):
    def test_round_trip(self) -> None:
        ctx = PageContext(
            title="Title",
            url="https://example.com/",
            selection="hello",
            page_text="body text",
            content_kind="webpage",
            metadata={"source": "test"},
        )
        self.assertEqual(PageContext.from_dict(ctx.to_dict()), ctx)

    def test_from_dict_requires_title(self) -> None:
        with self.assertRaises(ValueError):
            PageContext.from_dict({"url": "u", "selection": "", "page_text": "", "content_kind": "webpage"})

    def test_to_dict_uses_snake_case(self) -> None:
        ctx = PageContext(
            title="t", url="u", selection="s", page_text="p", content_kind="webpage", metadata={}
        )
        keys = set(ctx.to_dict().keys())
        self.assertEqual(
            keys, {"title", "url", "selection", "page_text", "content_kind", "metadata"}
        )


class MessageTests(unittest.TestCase):
    def test_round_trip_with_metadata(self) -> None:
        msg = SidecarMessage(
            role="user",
            content="hi",
            timestamp="2026-04-22T10:00:00Z",
            kind="text",
            metadata={"source": "browser"},
        )
        self.assertEqual(SidecarMessage.from_dict(msg.to_dict()), msg)

    def test_round_trip_without_metadata(self) -> None:
        msg = SidecarMessage(
            role="assistant",
            content="ok",
            timestamp="2026-04-22T10:00:01Z",
        )
        restored = SidecarMessage.from_dict(msg.to_dict())
        self.assertEqual(restored, msg)


class SessionTests(unittest.TestCase):
    def test_round_trip(self) -> None:
        session = SidecarSession(
            session_id="panel-1",
            session_key="resume-token",
            messages=(
                SidecarMessage(role="user", content="hi", timestamp="t1"),
                SidecarMessage(role="assistant", content="hello", timestamp="t2"),
            ),
            progress=SidecarProgress(running=False),
            updated_at="t2",
        )
        self.assertEqual(SidecarSession.from_dict(session.to_dict()), session)

    def test_from_dict_requires_session_id(self) -> None:
        with self.assertRaises(ValueError):
            SidecarSession.from_dict(
                {
                    "session_key": "k",
                    "messages": [],
                    "progress": {"running": False},
                    "updated_at": "t",
                }
            )


class CapabilitiesTests(unittest.TestCase):
    def test_to_dict_keys(self) -> None:
        cap = Capabilities()
        self.assertEqual(
            set(cap.to_dict().keys()),
            {
                "health_check",
                "capability_discovery",
                "session_state",
                "session_list",
                "session_send",
                "session_reset",
                "session_interrupt",
                "page_context",
                "attachments",
                "tts",
                "stt",
            },
        )

    def test_union_or_merges_flags(self) -> None:
        a = Capabilities(session_send=True, session_reset=True)
        b = Capabilities(session_interrupt=True, page_context=True)
        merged = Capabilities.union(a, b)
        self.assertTrue(merged.session_send)
        self.assertTrue(merged.session_reset)
        self.assertTrue(merged.session_interrupt)
        self.assertTrue(merged.page_context)
        self.assertFalse(merged.attachments)
        self.assertTrue(merged.health_check)
        self.assertTrue(merged.capability_discovery)


if __name__ == "__main__":
    unittest.main()
