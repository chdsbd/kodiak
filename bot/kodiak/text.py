from collections import defaultdict
from html.parser import HTMLParser
from typing import List, Tuple

from markdown_html_finder import find_html_positions as find_html_byte_positions


class CommentHTMLParser(HTMLParser):
    # define this attribute to make mypy accept `self.offset`
    offset: int

    def __init__(self) -> None:
        self.comments: List[Tuple[int, int]] = []
        super().__init__()

    def handle_comment(self, data: str) -> None:
        start_token_len = len("<!--")
        end_token_len = len("-->")
        tag_len = len(data)
        end = start_token_len + tag_len + end_token_len
        self.comments.append((self.offset, end + self.offset))

    def reset(self) -> None:
        self.comments = []
        super().reset()


html_parser = CommentHTMLParser()


def strip_html_comments_from_markdown(raw_message: str) -> str:
    """
    1. parse string into a markdown AST
    2. find the HTML nodes
    3. parse HTML nodes into HTML
    4. find comments in HTML
    5. slice out comments from original message
    """
    # NOTE(chdsbd): Remove carriage returns so find_html_positions can process
    # html correctly. pulldown-cmark doesn't handle carriage returns well.
    # remark-parse also doesn't handle carriage returns:
    # https://github.com/remarkjs/remark/issues/195#issuecomment-230760892
    stripped_message = raw_message.replace("\r", "")
    html_node_positions = find_html_byte_positions(stripped_message)
    comment_locations = defaultdict(list)

    message_bytes = stripped_message.encode()
    for html_start, html_end in html_node_positions:
        # snippet of HTML bytes
        html_text = message_bytes[html_start:html_end].decode()
        html_parser.feed(html_text)
        for comment_start, comment_end in html_parser.comments:
            comment_locations[(html_start, html_end)].append(
                (comment_start, comment_end)
            )
        html_parser.reset()

    new_message_bytes = message_bytes
    for html_positions, comment_pos in sorted(
        comment_locations.items(), key=lambda x: -x[0][0]
    ):
        html_start_bytes, html_end_bytes = html_positions
        new_message_piece_start = new_message_bytes[:html_start_bytes]
        new_message_piece_middle = new_message_bytes[
            html_start_bytes:html_end_bytes
        ].decode()
        new_message_piece_end = new_message_bytes[html_end_bytes:]
        for comment_start, comment_end in reversed(comment_pos):
            new_message_piece_middle = (
                new_message_piece_middle[:comment_start]
                + new_message_piece_middle[comment_end:]
            )
        new_message_bytes = (
            new_message_piece_start
            + new_message_piece_middle.encode()
            + new_message_piece_end
        )
    return new_message_bytes.decode()
