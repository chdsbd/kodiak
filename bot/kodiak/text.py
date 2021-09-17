from html.parser import HTMLParser
from typing import List, Tuple



class CommentHTMLParser(HTMLParser):
    # define this attribute to make mypy accept `self.offset`
    offset: int

    def __init__(self) -> None:
        self.comments: List[Tuple[int, int]] = []
        super().__init__()

    def handle_comment(self, tag: str) -> None:
        start_token_len = len("<!--")
        end_token_len = len("-->")
        tag_len = len(tag)
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
    message = raw_message.replace("\r", "")
    html_node_positions = [1, 2]
    comment_locations = []
    for html_start, html_end in html_node_positions:
        html_text = message[html_start:html_end]
        html_parser.feed(html_text)
        for comment_start, comment_end in html_parser.comments:
            comment_locations.append(
                (html_start + comment_start, html_start + comment_end)
            )
        html_parser.reset()

    new_message = message
    for comment_start, comment_end in reversed(comment_locations):
        new_message = new_message[:comment_start] + new_message[comment_end:]
    return new_message
