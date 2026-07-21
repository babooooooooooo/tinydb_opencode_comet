# tinydb/cli/highlighter.py
"""SQL syntax highlighter using pygments with graceful degradation."""


class SQLHighlighter:
    """SQL syntax highlighter — wraps pygments, degrades silently if unavailable."""

    # ANSI color codes
    _KEYWORD = "\x1b[34m"    # blue
    _STRING = "\x1b[32m"     # green
    _NUMBER = "\x1b[33m"     # yellow
    _COMMENT = "\x1b[90m"    # gray
    _RESET = "\x1b[0m"

    # Token type constants from pygments (avoid importing at module level)
    _TOKEN_KEYWORD = "Token.Keyword"
    _TOKEN_STRING = "Token.Literal.String"
    _TOKEN_NUMBER = "Token.Literal.Number"
    _TOKEN_COMMENT = "Token.Comment"

    def __init__(self):
        self._lexer = None
        self._formatter = None
        self._enabled = self._init_pygments()

    def _init_pygments(self) -> bool:
        try:
            from pygments.lexers import SqlLexer
            from pygments.formatters import TerminalFormatter
            from pygments.token import Token as PygmentsToken

            self._lexer = SqlLexer()
            self._formatter = TerminalFormatter()

            # Build our own token-to-color mapping
            self._token_colors = {}
            # Keywords
            self._token_colors[PygmentsToken.Keyword] = self._KEYWORD
            self._token_colors[PygmentsToken.Keyword.Constant] = self._KEYWORD
            self._token_colors[PygmentsToken.Keyword.Declaration] = self._KEYWORD
            self._token_colors[PygmentsToken.Keyword.Namespace] = self._KEYWORD
            self._token_colors[PygmentsToken.Keyword.Reserved] = self._KEYWORD
            # Strings
            self._token_colors[PygmentsToken.Literal.String] = self._STRING
            self._token_colors[PygmentsToken.Literal.String.Single] = self._STRING
            self._token_colors[PygmentsToken.Literal.String.Double] = self._STRING
            # Numbers
            self._token_colors[PygmentsToken.Literal.Number] = self._NUMBER
            self._token_colors[PygmentsToken.Literal.Number.Integer] = self._NUMBER
            self._token_colors[PygmentsToken.Literal.Number.Float] = self._NUMBER
            # Comments
            self._token_colors[PygmentsToken.Comment] = self._COMMENT
            self._token_colors[PygmentsToken.Comment.Single] = self._COMMENT
            self._token_colors[PygmentsToken.Comment.Multiline] = self._COMMENT

            return True
        except ImportError:
            return False

    def highlight(self, sql: str) -> str:
        """Return ANSI-colored SQL string. Returns plain text if pygments unavailable."""
        if not self._enabled or not sql:
            return sql

        from pygments import lex

        result_parts = []
        for token_type, value in lex(sql, self._lexer):
            color = self._find_color(token_type)
            if color:
                result_parts.append(f"{color}{value}{self._RESET}")
            else:
                result_parts.append(value)
        return "".join(result_parts)

    def _find_color(self, token_type) -> str | None:
        """Walk up the token type hierarchy to find a color mapping."""
        t = token_type
        while t is not None:
            if t in self._token_colors:
                return self._token_colors[t]
            # Try parent
            parents = t.__mro__[1:] if hasattr(t, "__mro__") else []
            t = parents[0] if parents else None
        return None
