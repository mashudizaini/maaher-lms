"""Trusted CommonMark policy, executed only by the isolated worker."""
from markdown_it import MarkdownIt
from .course_content import https_resource

def validate_markdown_raw(value):
    # Tokenize only: never render this parser's HTML. Disabling its default URL
    # rejection exposes ALL parsed link destinations to our stricter validator,
    # including javascript/mailto/relative targets. Preserve raw destinations so
    # IDNA/percent normalization cannot erase hidden Unicode before inspection.
    parser = MarkdownIt("commonmark", {"html": False})
    parser.validateLink = lambda _: True
    parser.normalizeLink = lambda url: url
    try:
        pending = parser.parse(value)
        while pending:
            token = pending.pop()
            if token.children:
                pending.extend(token.children)
            if token.type in {"link_open", "image"}:
                target = token.attrGet("href" if token.type == "link_open" else "src")
                if target is not None:
                    https_resource(target)
    except RecursionError:
        raise ValueError("Struktur Markdown terlalu dalam") from None
    return value
