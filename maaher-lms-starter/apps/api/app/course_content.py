"""Authoring URL policy, shared by resources and server-side Markdown checks."""
import ipaddress
import re
import unicodedata
from urllib.parse import unquote, urlsplit

from markdown_it import MarkdownIt


def https_resource(value):
    try:
        decoded = unquote(value, errors="strict")
    except (ValueError, UnicodeError):
        raise ValueError("Tautan memuat encoding yang tidak valid") from None
    if (len(value) > 2048 or re.search(r"%(?![0-9a-fA-F]{2})", value)
            or any(c.isspace() or c == "\\" for c in value)
            or any(unicodedata.category(c) in {"Cc", "Cf", "Cs"} for c in value + decoded)):
        raise ValueError("Tautan HTTPS tidak boleh memuat karakter kontrol atau tersembunyi")
    try:
        url = urlsplit(value)
        host = (url.hostname or "").encode("idna").decode().lower()
        valid = (url.scheme == "https" and url.username is None and url.password is None
                 and url.port in {None, 443} and bool(host) and not host.endswith('.'))
        try:
            valid = valid and ipaddress.ip_address(host).is_global
        except ValueError:
            labels = host.split('.')
            valid = (valid and 1 < len(labels) and len(host) <= 253
                     and not host.endswith((".local", ".localhost", ".internal"))
                     and bool(re.fullmatch(r"(?:[a-z]{2,63}|xn--[a-z0-9-]{2,59})", labels[-1]))
                     and all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in labels))
    except (ValueError, UnicodeError):
        valid = False
    if not valid:
        raise ValueError("Gunakan tautan HTTPS publik tanpa kredensial atau trailing dot")
    return value


def validate_markdown(value):
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
