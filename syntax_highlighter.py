"""
Module containing the SyntaxHighlighter class.
"""

from PyQt6.QtGui import QFont, QSyntaxHighlighter, QTextCharFormat, QColor, QTextDocument
from PyQt6.QtCore import Qt, QRegularExpression, QSettings

# State Constants for Multi-line Highlighting
STATE_NORMAL = -1 # Default Qt state
STATE_ML_COMMENT = 1 # Inside a /* ... */ comment (C++, C#, JS, CSS, HTML)
STATE_ML_STRING_DQ = 2 # Inside Python """...""" string
STATE_ML_STRING_SQ = 3 # Inside Python '''...''' string

# Default colors (used if setting is missing)
DEFAULT_COLORS = {
    "keyword": "#C586C0", "comment": "#6A9955", "string": "#CE9178",
    "number": "#B5CEA8", "function": "#DCDCAA", "class_type": "#4EC9B0",
    "operator_brace": "#D4D4D4", "preprocessor_decorator": "#808080",
    "tag": "#569CD6", "attribute": "#9CDCFE", "selector": "#D7BA7D",
    "property": "#9CDCFE",
}

class SyntaxHighlighter(QSyntaxHighlighter):
    """Applies syntax highlighting with more detailed rules and multi-line support."""
    def __init__(self, parent: QTextDocument, language: str = "Text"):
        super().__init__(parent)
        self.language = language.lower()
        self.highlighting_rules = [] # Rules for single-line patterns

        # Load Colors from Settings
        self.settings = QSettings("Jasher", "SnippetManager")
        self._load_colors() # Load colors into instance variables

        # Multi-line delimiters
        self._setup_delimiters_and_rules()

    def _load_colors(self):
        """Loads syntax colors from QSettings into instance variables."""
        self.keyword_color = QColor(self.settings.value("syntax_colors/keyword", DEFAULT_COLORS["keyword"]))
        self.comment_color = QColor(self.settings.value("syntax_colors/comment", DEFAULT_COLORS["comment"]))
        self.string_color = QColor(self.settings.value("syntax_colors/string", DEFAULT_COLORS["string"]))
        self.number_color = QColor(self.settings.value("syntax_colors/number", DEFAULT_COLORS["number"]))
        self.function_color = QColor(self.settings.value("syntax_colors/function", DEFAULT_COLORS["function"]))
        self.class_type_color = QColor(self.settings.value("syntax_colors/class_type", DEFAULT_COLORS["class_type"]))
        # Combine operator/brace loading for simplicity, can be split if needed
        op_brace_color_str = self.settings.value("syntax_colors/operator_brace", DEFAULT_COLORS["operator_brace"])
        self.operator_color = QColor(op_brace_color_str)
        self.brace_color = QColor(op_brace_color_str) # Use same color by default
        # Load other specific colors
        predec_color_str = self.settings.value("syntax_colors/preprocessor_decorator", DEFAULT_COLORS["preprocessor_decorator"])
        self.preprocessor_color = QColor(predec_color_str)
        self.decorator_color = QColor(predec_color_str) # Share color
        self.tag_color = QColor(self.settings.value("syntax_colors/tag", DEFAULT_COLORS["tag"]))
        self.attribute_color = QColor(self.settings.value("syntax_colors/attribute", DEFAULT_COLORS["attribute"]))
        self.selector_color = QColor(self.settings.value("syntax_colors/selector", DEFAULT_COLORS["selector"]))
        self.property_color = QColor(self.settings.value("syntax_colors/property", DEFAULT_COLORS["property"]))
        # Add fallbacks for other colors if needed
        self.value_color = self.string_color
        self.css_value_color = self.string_color
        self.md_header_color = self.tag_color
        self.md_emphasis_color = self.keyword_color
        self.md_code_color = self.number_color
        self.cpp_type_color = self.class_type_color
        self.cpp_literal_color = self.number_color
        self.self_format_color = self.attribute_color # Python self/cls, C#/JS this
        self.builtin_format_color = self.class_type_color
        self.regex_format_color = self.string_color

    def _setup_delimiters_and_rules(self):
        """Sets up multi-line delimiters and single-line rules based on language."""
        self.highlighting_rules = [] # Reset rules
        self.ml_comment_start = None
        self.ml_comment_end = None
        self.ml_string_dq_start = None
        self.ml_string_dq_end = None
        self.ml_string_sq_start = None
        self.ml_string_sq_end = None

        # Common Formats
        self.keyword_format = QTextCharFormat(); self.keyword_format.setForeground(self.keyword_color); self.keyword_format.setFontWeight(QFont.Weight.Bold)
        self.operator_format = QTextCharFormat(); self.operator_format.setForeground(self.operator_color)
        self.brace_format = QTextCharFormat(); self.brace_format.setForeground(self.brace_color)
        self.comment_format = QTextCharFormat(); self.comment_format.setForeground(self.comment_color); self.comment_format.setFontItalic(True)
        self.string_format = QTextCharFormat(); self.string_format.setForeground(self.string_color)
        self.number_format = QTextCharFormat(); self.number_format.setForeground(self.number_color)
        self.function_format = QTextCharFormat(); self.function_format.setForeground(self.function_color)
        self.class_type_format = QTextCharFormat(); self.class_type_format.setForeground(self.class_type_color)
        self.decorator_format = QTextCharFormat(); self.decorator_format.setForeground(self.decorator_color)
        self.preprocessor_format = QTextCharFormat(); self.preprocessor_format.setForeground(self.preprocessor_color)
        self.tag_format = QTextCharFormat(); self.tag_format.setForeground(self.tag_color); self.tag_format.setFontWeight(QFont.Weight.Bold)
        self.attribute_format = QTextCharFormat(); self.attribute_format.setForeground(self.attribute_color); self.attribute_format.setFontItalic(True)
        self.value_format = QTextCharFormat(); self.value_format.setForeground(self.value_color)
        self.selector_format = QTextCharFormat(); self.selector_format.setForeground(self.selector_color); self.selector_format.setFontWeight(QFont.Weight.Bold)
        self.property_format = QTextCharFormat(); self.property_format.setForeground(self.property_color)
        self.css_value_format = QTextCharFormat(); self.css_value_format.setForeground(self.css_value_color)
        self.md_header_format = QTextCharFormat(); self.md_header_format.setForeground(self.md_header_color); self.md_header_format.setFontWeight(QFont.Weight.Bold)
        md_emphasis_format = QTextCharFormat(); md_emphasis_format.setForeground(self.md_emphasis_color); md_emphasis_format.setFontWeight(QFont.Weight.Bold)
        md_italic_format = QTextCharFormat(); md_italic_format.setForeground(self.md_emphasis_color); md_italic_format.setFontItalic(True)
        self.md_code_format = QTextCharFormat(); self.md_code_format.setForeground(self.md_code_color); self.md_code_format.setBackground(QColor("#404040"))
        md_code_block_marker_format = QTextCharFormat(); md_code_block_marker_format.setForeground(self.comment_color)
        link_format = QTextCharFormat(); link_format.setForeground(self.tag_color); link_format.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SingleUnderline)
        entity_format = QTextCharFormat(); entity_format.setForeground(self.number_color)
        unit_format = QTextCharFormat(); unit_format.setForeground(self.number_color)
        color_format = QTextCharFormat(); color_format.setForeground(self.number_color)
        self_format = QTextCharFormat(); self_format.setForeground(self.self_format_color)
        builtin_format = QTextCharFormat(); builtin_format.setForeground(self.builtin_format_color)
        regex_format = QTextCharFormat(); regex_format.setForeground(self.regex_format_color)
        cpp_type_format = QTextCharFormat(); cpp_type_format.setForeground(self.cpp_type_color)
        cpp_literal_format = QTextCharFormat(); cpp_literal_format.setForeground(self.cpp_literal_color); cpp_literal_format.setFontWeight(QFont.Weight.Bold)

        # General Patterns
        self.highlighting_rules.append((QRegularExpression("\".*?(?<!\\\\)\""), self.string_format))
        self.highlighting_rules.append((QRegularExpression("'.*?(?<!\\\\)'"), self.string_format))
        if self.language == "javascript": self.highlighting_rules.append((QRegularExpression("`.*?`"), self.string_format))
        if self.language == "c++": self.highlighting_rules.append((QRegularExpression('R"\\((?:(?!\\)).)*\\)"'), self.string_format))
        self.highlighting_rules.append((QRegularExpression("\\b[0-9]+\\.?[0-9]*([eE][-+]?[0-9]+)?\\b"), self.number_format))
        self.highlighting_rules.append((QRegularExpression("\\b0[xX][0-9a-fA-F]+\\b"), self.number_format))
        self.highlighting_rules.append((QRegularExpression("\\b0[bB][01]+\\b"), self.number_format))
        self.highlighting_rules.append((QRegularExpression("\\b0[oO]?[0-7]+\\b"), self.number_format))
        ops = r'[=\+\-\*\/%<>&\|\^~!:\.\?,\.;]'
        braces = r'[\(\)\{\}\[\]]'
        self.highlighting_rules.append((QRegularExpression(ops), self.operator_format))
        self.highlighting_rules.append((QRegularExpression(braces), self.brace_format))

        # Language Specific Setup

        # Multi-line comment delimeters
        if self.language in ["c++", "c#", "javascript", "css"]:
             self.ml_comment_start = QRegularExpression("/\\*")
             self.ml_comment_end = QRegularExpression("\\*/")
        if self.language == "html": # HTML uses different ML comments
            self.ml_comment_start = QRegularExpression("<!--")
            self.ml_comment_end = QRegularExpression("-->")
        if self.language == "python":
            self.ml_string_dq_start = QRegularExpression('"""')
            self.ml_string_dq_end = QRegularExpression('"""')
            self.ml_string_sq_start = QRegularExpression("'''")
            self.ml_string_sq_end = QRegularExpression("'''")

        # Single line comments
        if self.language in ["python", "markdown", "text"]:
            self.highlighting_rules.append((QRegularExpression("#[^\n]*"), self.comment_format))
        if self.language in ["c++", "c#", "javascript"]:
            self.highlighting_rules.append((QRegularExpression("//[^\n]*"), self.comment_format))
        if self.language == "sql":
             self.highlighting_rules.append((QRegularExpression("--[^\n]*"), self.comment_format))
        # NOTE: HTML single-line comments aren't standard, rely on multi-line <!-- -->

        # Single line strings
        self.highlighting_rules.append((QRegularExpression("\".*?(?<!\\\\)\""), self.string_format)) # Double quotes, handle escaped quote
        self.highlighting_rules.append((QRegularExpression("'.*?(?<!\\\\)'"), self.string_format)) # Single quotes, handle escaped quote
        if self.language == "javascript":
             self.highlighting_rules.append((QRegularExpression("`.*?`"), self.string_format)) # Basic template literals (no multi-line support)
        if self.language == "c++":
             # C++ raw strings R"(...)"
             self.highlighting_rules.append((QRegularExpression('R"\\((?:(?!\\)).)*\\)"'), self.string_format))

        function_call_rule = (QRegularExpression("\\b\\w+(?=\\s*\\()"), self.function_format)

        # Python Specific
        if self.language == "python":
            py_keywords = [
                "and", "as", "assert", "async", "await", "break", "class", "continue",
                "def", "del", "elif", "else", "except", "False", "finally", "for", "from",
                "global", "if", "import", "in", "is", "lambda", "None", "nonlocal", "not",
                "or", "pass", "raise", "return", "True", "try", "while", "with", "yield"
            ]
            self.highlighting_rules.append((QRegularExpression("\\bdef\\s+(\\w+)"), self.function_format)) # Function def
            self.highlighting_rules.append((QRegularExpression("\\bclass\\s+(\\w+)"), self.class_type_format)) # Class def
            self.highlighting_rules.append((QRegularExpression("^\\s*@\\w+"), self.decorator_format)) # Decorators
            self.highlighting_rules.append((QRegularExpression("\\bself\\b"), self_format)) # self
            self.highlighting_rules.append((QRegularExpression("\\bcls\\b"), self_format)) # cls
            self.highlighting_rules.append(function_call_rule) # Function calls
            py_builtins = ["int", "str", "float", "list", "dict", "tuple", "set", "bool", "print", "len", "range", "open", "super", "isinstance", "type"]
            self.highlighting_rules.extend([(QRegularExpression(f"\\b{bi}\\b"), builtin_format) for bi in py_builtins])
            self.highlighting_rules.extend([(QRegularExpression(f"\\b{kw}\\b"), self.keyword_format) for kw in py_keywords])

        # C++ Specific
        elif self.language == "c++":
            # Common types
            cpp_types = ["int", "float", "double", "char", "void", "bool", "string", "vector", "map", "set", "pair", "tuple", "istream", "ostream", "fstream", "size_t"]
            self.highlighting_rules.extend([(QRegularExpression(f"\\b(std::)?{t}\\b"), cpp_type_format) for t in cpp_types]) # Handle std:: prefix optionally
             # Literals
            self.highlighting_rules.append((QRegularExpression("\\b(true|false|nullptr)\\b"), cpp_literal_format))
             # Class/Struct definition
            self.highlighting_rules.append((QRegularExpression("\\b(class|struct)\\s+(\\w+)"), self.class_type_format))
             # Function calls
            self.highlighting_rules.append((QRegularExpression("\\b\\w+(?=\\s*\\()"), self.function_format))
             # Preprocessor directives
            self.highlighting_rules.append((QRegularExpression("^\\s*#\\w+.*"), self.preprocessor_format))
            # 'this' keyword
            self.highlighting_rules.append((QRegularExpression("\\bthis\\b"), self_format))
            # Function calls
            self.highlighting_rules.append(function_call_rule)
            # Keywords
            cpp_keywords = [
                "alignas", "alignof", "and", "and_eq", "asm", "atomic_cancel",
                "atomic_commit", "atomic_noexcept", "auto", "bitand", "bitor", "bool",
                "break", "case", "catch", "char", "char8_t", "char16_t", "char32_t",
                "class", "compl", "concept", "const", "consteval", "constexpr",
                "constinit", "const_cast", "continue", "co_await", "co_return",
                "co_yield", "decltype", "default", "delete", "do", "double",
                "dynamic_cast", "else", "enum", "explicit", "export", "extern", "false",
                "float", "for", "friend", "goto", "if", "inline", "int", "long",
                "mutable", "namespace", "new", "noexcept", "not", "not_eq", "nullptr",
                "operator", "or", "or_eq", "private", "protected", "public",
                "reflexpr", "register", "reinterpret_cast", "requires", "return", "short",
                "signed", "sizeof", "static", "static_assert", "static_cast", "struct",
                "switch", "synchronized", "template", "this", "thread_local", "throw",
                "true", "try", "typedef", "typeid", "typename", "union", "unsigned",
                "using", "virtual", "void", "volatile", "wchar_t", "while", "xor", "xor_eq"
            ]
            self.highlighting_rules.extend([(QRegularExpression(f"\\b{kw}\\b"), self.keyword_format) for kw in cpp_keywords])

        # SQL Specific
        elif self.language == "sql":
            sql_keywords = [
                "SELECT", "FROM", "WHERE", "INSERT", "UPDATE", "DELETE", "CREATE", "ALTER",
                "DROP", "TABLE", "VIEW", "INDEX", "JOIN", "LEFT", "RIGHT", "INNER", "OUTER",
                "ON", "AS", "GROUP", "BY", "ORDER", "ASC", "DESC", "AND", "OR", "NOT",
                "NULL", "IN", "LIKE", "BETWEEN", "CASE", "WHEN", "THEN", "ELSE", "END",
                "DISTINCT", "HAVING", "UNION", "ALL", "EXISTS", "VALUES", "INTO", "SET",
                "BEGIN", "TRANSACTION", "COMMIT", "ROLLBACK", "PRIMARY", "FOREIGN", "KEY",
                "REFERENCES", "CONSTRAINT", "DEFAULT", "CHECK", "TRIGGER", "PROCEDURE",
                "FUNCTION", "CAST", "CONVERT", "DECLARE", "EXEC", "EXECUTE", "GO", "IF",
                "IS", "VARCHAR", "INT", "FLOAT", "DATETIME", "TEXT", "BLOB"
            ]
            sql_funcs = ["COUNT", "SUM", "AVG", "MIN", "MAX", "GETDATE", "NOW", "DATE", "SUBSTRING", "LOWER", "UPPER", "ABS", "ROUND", "COALESCE", "ISNULL"]

            for func in sql_funcs:
                pattern = QRegularExpression(f"\\b{func}\\b", QRegularExpression.PatternOption.CaseInsensitiveOption)
                self.highlighting_rules.append((pattern, self.function_format))

            for kw in sql_keywords:
                pattern = QRegularExpression(f"\\b{kw}\\b", QRegularExpression.PatternOption.CaseInsensitiveOption)
                self.highlighting_rules.append((pattern, self.keyword_format))

        # Markdown Specific
        elif self.language == "markdown":
            self.highlighting_rules.append((QRegularExpression("^#{1,6}\\s+.*"), self.md_header_format)) # Headers
            self.highlighting_rules.append((QRegularExpression("\\*\\*(.*?)\\*\\*"), md_emphasis_format)) # Bold **
            self.highlighting_rules.append((QRegularExpression("__([^_]+)__"), md_emphasis_format)) # Bold __
            self.highlighting_rules.append((QRegularExpression("\\*([^*]+)\\*"), md_italic_format))   # Italic *
            self.highlighting_rules.append((QRegularExpression("_([^_]+)_"), md_italic_format))   # Italic _
            self.highlighting_rules.append((QRegularExpression("`(.+?)`"), self.md_code_format)) # Inline code
            self.highlighting_rules.append((QRegularExpression("^```.*"), md_code_block_marker_format)) # Code block markers
            self.highlighting_rules.append((QRegularExpression("!?\\[.*?\\]\\(.*?\\)"), link_format)) # Links/Images
            self.highlighting_rules.append((QRegularExpression("^\\s*[-*+]\\s+.*"), self.operator_format)) # List items
            self.highlighting_rules.append((QRegularExpression("^>\\s+.*"), self.comment_format)) # Blockquotes

        # C# Specific
        elif self.language == "c#":
            cs_keywords = [
                "abstract", "as", "base", "bool", "break", "byte", "case", "catch", "char",
                "checked", "class", "const", "continue", "decimal", "default", "delegate",
                "do", "double", "else", "enum", "event", "explicit", "extern", "false",
                "finally", "fixed", "float", "for", "foreach", "goto", "if", "implicit",
                "in", "int", "interface", "internal", "is", "lock", "long", "namespace",
                "new", "null", "object", "operator", "out", "override", "params", "private",
                "protected", "public", "readonly", "ref", "return", "sbyte", "sealed",
                "short", "sizeof", "stackalloc", "static", "string", "struct", "switch",
                "this", "throw", "true", "try", "typeof", "uint", "ulong", "unchecked",
                "unsafe", "ushort", "using", "virtual", "void", "volatile", "while",
                "get", "set", "value", "var", "add", "remove", "yield", "dynamic", "await", "async"
            ]
            self.highlighting_rules.append((QRegularExpression("\\b(class|interface|enum|struct)\\s+(\\w+)"), self.class_type_format))
            # Very basic method detection - needs improvement for generics, attributes etc.
            self.highlighting_rules.append((QRegularExpression("\\b\\w+\\s+(\\w+)\\s*\\("), self.function_format))
            self.highlighting_rules.append((QRegularExpression("^\\s*\\[.*\\]"), self.decorator_format)) # Attributes like [TestMethod]
            self.highlighting_rules.append((QRegularExpression("^\\s*#\\w+.*"), self.preprocessor_format)) # Preprocessor
            self.highlighting_rules.append((QRegularExpression("\\bthis\\b"), self_format)) # this
            self.highlighting_rules.append(function_call_rule) # Function calls
            self.highlighting_rules.extend([(QRegularExpression(f"\\b{kw}\\b"), self.keyword_format) for kw in cs_keywords])

        # HTML Specific
        elif self.language == "html":
            # Rules for HTML need refinement, especially for embedded CSS/JS (not handled here)
            self.ml_comment_start = QRegularExpression("<!--") # Override default /*
            self.ml_comment_end = QRegularExpression("-->")

            self.highlighting_rules.append((QRegularExpression("</?([a-zA-Z0-9\\-]+)\\b"), self.tag_format)) # Tags </?tag>
            self.highlighting_rules.append((QRegularExpression("<!DOCTYPE\\b"), self.tag_format)) # DOCTYPE special case
            self.highlighting_rules.append((QRegularExpression("\\b([a-zA-Z\\-]+)\\s*="), self.attribute_format)) # Attributes attr=
            # Values inside quotes handled by general string rule
            self.highlighting_rules.append((QRegularExpression("&[a-zA-Z0-9#]+;"), entity_format)) # Entities  

        # CSS Specific
        elif self.language == "css":
             # Selectors
            self.highlighting_rules.append((QRegularExpression("^\\s*([\\*\\.#]?[a-zA-Z0-9\\-_]+(?:\\s*[,>+~ ]\\s*[\\*\\.#]?[a-zA-Z0-9\\-_]+)*)"), self.selector_format)) # More complex selectors
            self.highlighting_rules.append((QRegularExpression(":[a-zA-Z\\-]+(\\(.*?\\))?"), self.selector_format)) # Pseudo classes/elements like :hover, :nth-child(n)

            self.highlighting_rules.append((QRegularExpression("\\b([a-zA-Z\\-]+)\\s*:"), self.property_format)) # Property name:
            self.highlighting_rules.append((QRegularExpression("\\b\\d+(px|em|rem|%|pt|vh|vw|s|ms)\\b"), unit_format)) # Units
            self.highlighting_rules.append((QRegularExpression("#[0-9a-fA-F]{3,8}\\b"), color_format)) # Colors #rgb, #rrggbb, #rrggbbaa
            self.highlighting_rules.append((QRegularExpression("\\b(rgb|rgba|hsl|hsla)\\(.*?\\)"), color_format)) # Color functions
            # CSS values (keywords)
            css_vals = ["auto", "inherit", "initial", "unset", "none", "block", "inline", "flex", "grid", "bold", "italic", "normal", "absolute", "relative", "fixed", "static"]
            self.highlighting_rules.extend([(QRegularExpression(f"\\b{v}\\b"), self.css_value_format) for v in css_vals])

        # JavaScript Specific
        elif self.language == "javascript":
            js_keywords = [
                "break", "case", "catch", "class", "const", "continue", "debugger", "default",
                "delete", "do", "else", "export", "extends", "false", "finally", "for",
                "function", "if", "import", "in", "instanceof", "let", "new", "null",
                "return", "super", "switch", "this", "throw", "true", "try", "typeof",
                "var", "void", "while", "with", "yield", "async", "await", "static",
                "get", "set", "arguments", "of", "undefined"
            ]
            js_builtins = [
                "console", "Math", "JSON", "Promise", "Object", "Array", "String", "Number", "Boolean", "Date",
                "RegExp", "Error", "Symbol", "Map", "Set", "WeakMap", "WeakSet", "Intl", "isNaN", "parseFloat", "parseInt",
                "document", "window", "fetch", "setTimeout", "setInterval", "clearTimeout", "clearInterval", "alert", "confirm", "prompt"
            ]
            self.highlighting_rules.extend([(QRegularExpression(f"\\b{bi}\\b"), builtin_format) for bi in js_builtins])
            self.highlighting_rules.append((QRegularExpression("\\b(function|const|let|var)\\s+\\*?(\\w+)"), self.function_format)) # Function/Generator def
            self.highlighting_rules.append((QRegularExpression("=>"), self.operator_format)) # Arrow function operator
            self.highlighting_rules.append((QRegularExpression("\\bclass\\s+(\\w+)"), self.class_type_format)) # Class def
            self.highlighting_rules.append((QRegularExpression("/[^/\\n\\\\]*(?:\\\\.[^/\\n\\\\]*)*/[gimyus]*"), regex_format)) # Regex literal
            self.highlighting_rules.append((QRegularExpression("\\bthis\\b"), self_format)) # this
            self.highlighting_rules.append(function_call_rule) # Function calls
            self.highlighting_rules.extend([(QRegularExpression(f"\\b{kw}\\b"), self.keyword_format) for kw in js_keywords])

    def highlightBlock(self, text: str):
        """Applies the highlighting rules to the current text block, handling multi-line state."""
        current_block = self.currentBlock()
        previous_state = self.previousBlockState()
        current_state = STATE_NORMAL # Assume normal state unless changed

        start_index = 0

        # Handle Multi-line Continuations
        if previous_state == STATE_ML_COMMENT and self.ml_comment_end:
            match = self.ml_comment_end.match(text)
            end_index = match.capturedStart() if match.hasMatch() else -1
            comment_len = match.capturedLength() if match.hasMatch() else len(text)

            if end_index == -1: # Comment continues
                self.setFormat(0, len(text), self.comment_format)
                current_state = STATE_ML_COMMENT
            else: # Comment ends in this block
                self.setFormat(0, end_index + comment_len, self.comment_format)
                start_index = end_index + comment_len # Start processing rest of line after comment
                current_state = STATE_NORMAL
            self.setCurrentBlockState(current_state)
            # If comment ended, continue to process rest of line with single-line rules below

        elif previous_state == STATE_ML_STRING_DQ and self.ml_string_dq_end:
            match = self.ml_string_dq_end.match(text)
            end_index = match.capturedStart() if match.hasMatch() else -1
            string_len = match.capturedLength() if match.hasMatch() else len(text)

            if end_index == -1: # String continues
                self.setFormat(0, len(text), self.string_format)
                current_state = STATE_ML_STRING_DQ
            else: # String ends
                self.setFormat(0, end_index + string_len, self.string_format)
                start_index = end_index + string_len
                current_state = STATE_NORMAL
            self.setCurrentBlockState(current_state)

        elif previous_state == STATE_ML_STRING_SQ and self.ml_string_sq_end:
            match = self.ml_string_sq_end.match(text)
            end_index = match.capturedStart() if match.hasMatch() else -1
            string_len = match.capturedLength() if match.hasMatch() else len(text)

            if end_index == -1: # String continues
                self.setFormat(0, len(text), self.string_format)
                current_state = STATE_ML_STRING_SQ
            else: # String ends
                self.setFormat(0, end_index + string_len, self.string_format)
                start_index = end_index + string_len
                current_state = STATE_NORMAL
            self.setCurrentBlockState(current_state)

        # Apply Single-Line Rules and Detect Multi-line Starts
        # Only process from start_index onwards if not fully consumed by multi-line continuation
        if start_index < len(text) or len(text) == 0: # Ensure empty lines are handled correctly
            # Find the earliest start of any multi-line construct in the remainder
            next_ml_start = -1
            matched_state = STATE_NORMAL
            match_len = 0

            # Check for ML Comment Start
            if self.ml_comment_start:
                match = self.ml_comment_start.match(text, start_index)
                if match.hasMatch():
                    idx = match.capturedStart()
                    if next_ml_start == -1 or idx < next_ml_start:
                        next_ml_start = idx
                        matched_state = STATE_ML_COMMENT
                        match_len = match.capturedLength()

            # Check for ML String DQ Start
            if self.ml_string_dq_start:
                match = self.ml_string_dq_start.match(text, start_index)
                if match.hasMatch():
                    idx = match.capturedStart()
                    if next_ml_start == -1 or idx < next_ml_start:
                        next_ml_start = idx
                        matched_state = STATE_ML_STRING_DQ
                        match_len = match.capturedLength()

            # Check for ML String SQ Start
            if self.ml_string_sq_start:
                match = self.ml_string_sq_start.match(text, start_index)
                if match.hasMatch():
                    idx = match.capturedStart()
                    if next_ml_start == -1 or idx < next_ml_start:
                        next_ml_start = idx
                        matched_state = STATE_ML_STRING_SQ
                        match_len = match.capturedLength()

            # Process segment before the first multi-line start
            process_end_index = next_ml_start if next_ml_start != -1 else len(text)
            sub_text = text[start_index:process_end_index]
            if sub_text:
                for pattern, format in self.highlighting_rules:
                    match_iterator = pattern.globalMatch(sub_text)
                    while match_iterator.hasNext():
                        match = match_iterator.next()
                        # Adjust index relative to the original text string
                        self.setFormat(start_index + match.capturedStart(), match.capturedLength(), format)

            # Handle the start of a multi-line construct if found
            if next_ml_start != -1:
                current_state = matched_state # Set state
                ml_end_regex = None
                ml_format = self.comment_format # Default to comment

                if current_state == STATE_ML_COMMENT:
                    ml_end_regex = self.ml_comment_end
                    ml_format = self.comment_format
                elif current_state == STATE_ML_STRING_DQ:
                    ml_end_regex = self.ml_string_dq_end
                    ml_format = self.string_format
                elif current_state == STATE_ML_STRING_SQ:
                    ml_end_regex = self.ml_string_sq_end
                    ml_format = self.string_format

                # Check if the construct ALSO ends on this line
                end_match = None
                if ml_end_regex:
                    end_match = ml_end_regex.match(text, next_ml_start + match_len) # Search after start delimiter

                if end_match and end_match.hasMatch():
                    # Multi-line construct starts and ends on the same line
                    end_index = end_match.capturedStart()
                    end_len = end_match.capturedLength()
                    self.setFormat(next_ml_start, (end_index + end_len) - next_ml_start, ml_format)
                    # Continue processing *after* this construct on the same line
                    start_index = end_index + end_len
                    current_state = STATE_NORMAL # Reset state as it finished
                    # Need to re-run the single-line processing for the rest of the line
                    # Recursion suboptimal, refactor to use loop
                    self.highlightBlock(text[start_index:]) # Re-highlight tail

                else:
                    # Multi-line construct starts here and continues
                    self.setFormat(next_ml_start, len(text) - next_ml_start, ml_format)
                    # State is already set to matched_state

            # Set the final state for the next block if we didn't reset to NORMAL
            # and weren't already in a multi-line continuation handled at the top
            if previous_state == STATE_NORMAL:
                 self.setCurrentBlockState(current_state)