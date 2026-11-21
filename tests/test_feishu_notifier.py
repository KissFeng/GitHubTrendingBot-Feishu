"""Offline delivery tests. All HTTP requests are blocked unless explicitly mocked."""

import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import Mock, patch

import requests

import github_trending_bot as bot


# Reserved .invalid hosts; these are placeholders, never real webhook targets.
PRIMARY = "https://primary.invalid/webhook/primary-token"
SECOND = "https://second.invalid/webhook/second-token"
THIRD = "https://third.invalid/webhook/third-token"


def response(body=None, error=None):
    result = Mock()
    result.raise_for_status.side_effect = error
    result.json.return_value = {"code": 0} if body is None else body
    return result


class FeishuNotifierTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch("requests.sessions.Session.request",
                                side_effect=AssertionError("Network is forbidden in tests")))
        self.enterContext(patch.multiple(bot, FEISHU_WEBHOOK_URL=PRIMARY,
                                        FEISHU_EXTRA_WEBHOOK_URLS="",
                                        SILICONFLOW_API_KEY="test-only", LOG_ENABLED=True))
        self.post = self.enterContext(patch.object(bot.requests, "post",
                                                  return_value=response()))
        self.output = io.StringIO()
        self.enterContext(redirect_stdout(self.output))

    def assert_sanitized(self, *extra_secrets):
        output = self.output.getvalue()
        for secret in (PRIMARY, SECOND, THIRD, "primary-token", "second-token",
                       "third-token", *extra_secrets):
            self.assertNotIn(secret, output)

    def test_legacy_single_webhook_and_both_business_success_codes(self):
        for body in ({"StatusCode": 0}, {"code": 0}):
            with self.subTest(body=body):
                self.post.reset_mock()
                self.post.return_value = response(body)
                notifier = bot.FeishuNotifier()
                self.assertTrue(notifier.send("# Digest"))
                self.post.assert_called_once_with(
                    PRIMARY, json=notifier._build_card_message("# Digest"),
                    headers={"Content-Type": "application/json"}, timeout=10)
        self.assert_sanitized()

    def test_one_extra_or_comma_newline_list(self):
        for extras, expected in ((SECOND, [PRIMARY, SECOND]),
                                 (f" \n{SECOND}, \r\n {THIRD}\n, ",
                                  [PRIMARY, SECOND, THIRD])):
            with self.subTest(extras=extras), patch.object(bot, "FEISHU_EXTRA_WEBHOOK_URLS", extras):
                self.post.reset_mock()
                notifier = bot.FeishuNotifier()
                with patch.object(notifier, "_build_card_message",
                                  wraps=notifier._build_card_message) as build:
                    self.assertTrue(notifier.send("# Shared digest"))
                    build.assert_called_once_with("# Shared digest")
                calls = self.post.call_args_list
                self.assertEqual([call.args[0] for call in calls], expected)
                self.assertTrue(all(call.kwargs["json"] is calls[0].kwargs["json"]
                                    for call in calls))
        self.assert_sanitized()

    def test_duplicates_whitespace_and_empty_entries_preserve_order(self):
        with patch.multiple(bot, FEISHU_WEBHOOK_URL=f" {PRIMARY} \n",
                            FEISHU_EXTRA_WEBHOOK_URLS=f", {SECOND},\n{PRIMARY}, {THIRD}\n{SECOND}, ,"):
            self.assertTrue(bot.FeishuNotifier().send("Digest"))
        self.assertEqual([call.args[0] for call in self.post.call_args_list],
                         [PRIMARY, SECOND, THIRD])
        self.assert_sanitized()

    def test_blank_extras_keep_single_webhook(self):
        with patch.object(bot, "FEISHU_EXTRA_WEBHOOK_URLS", " , \r\n, \t"):
            self.assertTrue(bot.FeishuNotifier().send("Digest"))
        self.post.assert_called_once()

    def test_failures_do_not_stop_later_destinations_and_logs_are_sanitized(self):
        marker = "UNTRUSTED_PROVIDER_BODY"
        failures = (
            requests.ConnectionError(f"connection failed: {PRIMARY}"),
            requests.Timeout(f"timed out: {PRIMARY}"),
            requests.exceptions.InvalidURL(f"invalid URL: {PRIMARY}"),
            response(error=requests.HTTPError(f"HTTP failure {PRIMARY}: {marker}")),
            response({"code": 123, "msg": f"{PRIMARY} {marker}"}),
            response({"code": f"{PRIMARY} {marker}"}),
            response({"StatusCode": 123, "msg": marker}),
            response({"msg": marker}),
            response([marker, PRIMARY]),
        )
        bad_json = response()
        bad_json.json.side_effect = ValueError(f"{PRIMARY} {marker}")
        for failure in (*failures, bad_json):
            with self.subTest(failure=type(failure).__name__), patch.object(
                    bot, "FEISHU_EXTRA_WEBHOOK_URLS", SECOND):
                self.post.reset_mock()
                self.post.side_effect = [failure, response()]
                self.assertFalse(bot.FeishuNotifier().send("Digest"))
                self.assertEqual([call.args[0] for call in self.post.call_args_list],
                                 [PRIMARY, SECOND])
                self.assertIn("飞书目标 2 发送成功", self.output.getvalue())
                self.assertIn("成功 1/2，失败 1", self.output.getvalue())
                self.assert_sanitized(marker)

    def test_no_destinations_fails_without_http(self):
        with patch.object(bot, "FEISHU_WEBHOOK_URL", ""):
            self.assertFalse(bot.FeishuNotifier().send("Digest"))
        self.post.assert_not_called()

    def test_primary_remains_required_even_with_extras(self):
        with patch.multiple(bot, FEISHU_WEBHOOK_URL=" \n",
                            FEISHU_EXTRA_WEBHOOK_URLS=SECOND):
            with self.assertRaises(SystemExit) as error:
                bot.validate_env()
        self.assertEqual(error.exception.code, 1)
        self.post.assert_not_called()
        self.assert_sanitized()

    def test_text_message_is_shared_across_destinations(self):
        with patch.multiple(bot, FEISHU_EXTRA_WEBHOOK_URLS=SECOND,
                            FEISHU_MESSAGE_TYPE="text"):
            self.assertTrue(bot.FeishuNotifier().send("Digest"))
        for call in self.post.call_args_list:
            self.assertEqual(call.kwargs["json"],
                             {"msg_type": "text", "content": {"text": "Digest"}})

    def test_main_exit_status_aggregates_delivery_and_builds_digest_once(self):
        outcomes = (([{"code": 0}, {"StatusCode": 0}], 0),
                    ([{"code": 1}, {"code": 0}], 1),
                    ([{"code": 0}, {"code": 1}], 1),
                    ([{"code": 1}, {"code": 1}], 1))
        for bodies, expected_status in outcomes:
            with self.subTest(bodies=bodies), patch.object(
                    bot, "FEISHU_EXTRA_WEBHOOK_URLS", SECOND), patch.object(
                    bot, "GitHubTrendingCrawler") as crawler_cls, patch.object(
                    bot, "SiliconFlowSummarizer") as summarizer_cls, patch.object(
                    bot, "AgentSkillsBeautifier") as beautifier_cls:
                self.post.reset_mock()
                self.post.side_effect = [response(body) for body in bodies]
                repos = [{"name": "test/repo"}]
                crawler = crawler_cls.return_value
                crawler.fetch_trending.return_value = repos
                summarizer_cls.return_value.analyze_repos.return_value = repos
                beautifier_cls.return_value.beautify.return_value = "# Digest"
                with self.assertRaises(SystemExit) as error:
                    bot.main()
                self.assertEqual(error.exception.code, expected_status)
                crawler.fetch_trending.assert_called_once_with()
                summarizer_cls.return_value.analyze_repos.assert_called_once_with(
                    repos, limit=10, crawler=crawler)
                beautifier_cls.return_value.beautify.assert_called_once_with(repos)
                self.assertEqual(self.post.call_count, 2)
                self.assert_sanitized()


if __name__ == "__main__":
    unittest.main()
