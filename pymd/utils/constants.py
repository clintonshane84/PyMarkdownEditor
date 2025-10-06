APP_ORG = "QuickTools"
APP_NAME = "PyQt Markdown Editor"

CSS_PREVIEW = """
:root { --bg:#ffffff; --fg:#111; --muted:#555; --code:#f4f6f8; --border:#ddd; --link:#0b6bfd; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#0f1115; --fg:#e7e9ee; --muted:#a0a4ae; --code:#1a1d24; --border:#2a2f3a; --link:#7aa2ff; }
}
html,body { background:var(--bg); color:var(--fg); }
body { font-family: -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif; margin: 1.25rem; line-height: 1.55; }
h1,h2,h3,h4,h5 { margin-top: 1.2em; }
pre { padding:.75rem; overflow:auto; border-radius:8px; background:var(--code); }
code { background:var(--code); padding:.15rem .3rem; border-radius:6px; }
blockquote { border-left:4px solid var(--border); margin:1em 0; padding:.25em .75em; color:var(--muted); }
table { border-collapse: collapse; }
th, td { border:1px solid var(--border); padding:.4rem .6rem; }
a { color:var(--link); text-decoration:none; } a:hover { text-decoration:underline; }
hr { border:none; border-top:1px solid var(--border); margin:1.5rem 0; }
ul,ol { padding-left:1.5rem; }
"""

HTML_TEMPLATE = """<!doctype html>
<html>
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<style>{css}</style>
</head>
<body>
{body}
</body>
</html>
"""

SETTINGS_GEOMETRY = "window/geometry"
SETTINGS_SPLITTER = "window/splitter"
SETTINGS_RECENTS = "file/recent"
MAX_RECENTS = 8
