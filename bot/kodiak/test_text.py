import pytest

from kodiak.text import strip_html_comments_from_markdown


@pytest.mark.parametrize(
    "original,stripped",
    [
        (
            """\
Non dolor velit vel quia mollitia. Placeat cumque a deleniti possimus.

Totam dolor [exercitationem laborum](https://numquam.com)

<!--
- Voluptatem voluptas officiis
- Voluptates nulla tempora
- Officia distinctio ut ab
  + Est ut voluptatum consequuntur recusandae aspernatur
  + Quidem debitis atque dolorum est enim
-->
""",
            """\
Non dolor velit vel quia mollitia. Placeat cumque a deleniti possimus.

Totam dolor [exercitationem laborum](https://numquam.com)


""",
        ),
        (
            'Non dolor velit vel quia mollitia.\r\n\r\nVoluptates nulla tempora.\r\n\r\n<!--\r\n- Voluptatem voluptas officiis\r\n- Voluptates nulla tempora\r\n- Officia distinctio ut ab\r\n  + "Est ut voluptatum" consequuntur recusandae aspernatur\r\n  + Quidem debitis atque dolorum est enim\r\n-->',
            "Non dolor velit vel quia mollitia.\n\nVoluptates nulla tempora.\n\n",
        ),
        ("hello <!-- testing -->world", "hello world"),
        (
            "hello <span>  <p>  <!-- testing --> hello</p></span>world",
            "hello <span>  <p>   hello</p></span>world",
        ),
        (
            "hello <span>  <p>  <!-- testing --> hello<!-- 123 --></p></span>world",
            "hello <span>  <p>   hello</p></span>world",
        ),
        (
            """\
this is an example comment message with a comment from a PR template

<!--
- bullet one
- bullet two
- bullet three
  + sub bullet one
  + sub bullet two
-->
""",
            """\
this is an example comment message with a comment from a PR template


""",
        ),
        (
'### 🏷️ Jira ticket\r\n <!-- Add the Jira ticket corresponding to this Pull request -->\r\n https://company.atlassian.net/browse/COOL-123\r\n ### 📢 Type of change\r\n <!--- Remove what\'s irrelevant -->\r\n - New feature (non-breaking change which adds functionality)\r\n ### 📜 Description\r\n <!--\r\n    Describe your changes in detail.\r\n    Mainly answer the "What" and "How". What is the PR changing? What is it adding/modifying/removing? What will the new behavior be?\r\n    How is the change introduced?\r\n -->\r\n Add feature which is really cool and useful.\r\n ...\r\n\r\n\r\n\r\n'
,
'### 🏷️ Jira ticket\r\n \r\n https://company.atlassian.net/browse/COOL-123\r\n ### 📢 Type of change\r\n \r\n - New feature (non-breaking change which adds functionality)\r\n ### 📜 Description\r\n \r\n Add feature which is really cool and useful.\r\n ...\r\n\r\n\r\n\r\n'
)
    ],
)
def test_strip_html_comments_from_markdown(original: str, stripped: str) -> None:
    assert strip_html_comments_from_markdown(original) == stripped
