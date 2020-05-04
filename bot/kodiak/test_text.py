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
    ],
)
def test_strip_html_comments_from_markdown(original: str, stripped: str) -> None:
    assert strip_html_comments_from_markdown(original) == stripped
