from kodiak.messages import get_markdown_for_api_call_errors


def test_get_markdown_for_api_call_errors() -> None:
    class APICallRetry:
        api_name = "pull_request/merge"
        http_status = "405"
        response_body = '{"message":"This branch must not contain merge commits.","documentation_url":"https://docs.github.com/articles/about-protected-branches”}'

    assert (
        get_markdown_for_api_call_errors(errors=[APICallRetry(), APICallRetry()])
        == """\
Errors encountered when contacting GitHub API.

- API call 'pull_request/merge' failed with HTTP status '405' and response: '{"message":"This branch must not contain merge commits.","documentation_url":"https://docs.github.com/articles/about-protected-branches”}'
- API call 'pull_request/merge' failed with HTTP status '405' and response: '{"message":"This branch must not contain merge commits.","documentation_url":"https://docs.github.com/articles/about-protected-branches”}'
        

If you need help, you can open a GitHub issue, check the docs, or reach us privately at support@kodiakhq.com.

[docs](https://kodiakhq.com/docs/troubleshooting) | [dashboard](https://app.kodiakhq.com) | [support](https://kodiakhq.com/help)

"""
    )
