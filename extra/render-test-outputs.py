#! /usr/bin/env python3

from ansi2html import Ansi2HTMLConverter
from jinja2 import Template
import json
from pathlib import Path
import re

outdir = Path("ui_render")
outdir.mkdir(exist_ok=True)

outputs = []

template = Template(
"""<!DOCTYPE html>
<html>
<head>
    <style>
        .terminal {
            width: 800px;
        }
        .test {
            margin-top: 0px;
            margin-bottom: 40px;
        }
        .sep {
            color: grey;
        }
        .test-name {
            font-family: Consolas,Monaco,Lucida Console,Liberation Mono,DejaVu Sans Mono,Bitstream Vera Sans Mono,Courier New, monospace;
        }
    </style>
    {{ headers }}
</head>
    <body>
        {{ content }}
    </body>
</html>
"""
)

term_template = Template(
"""
<div class="test">
    <h2 class="test-name">{{ file }}<span class="sep"> :: </span>{{ cls }}<span class="sep"> :: </span>{{ func }}</h2>
    <div class="body_foreground body_background terminal">
        <pre class="ansi2html-content">{{ content }}</pre>
    </div>
</div>
"""
)

name_pattern = re.compile(
    "^test/(?P<file>test_[^:]+\.py)::(?P<cls>[^:]+)::(?P<func>[^:]+)$"
)

with open(outdir / "log.json") as f:
    for line in f:
        report = json.loads(line)
        if report.get("when") != "call" or "sections" not in report:
            continue

        name = report["nodeid"]
        name_parts = name_pattern.match(name)
        for section, content in report["sections"]:
            if "stdout" in section and content:
                conv = Ansi2HTMLConverter()
                html = conv.convert(content, full=False)
                outputs.append(
                    term_template.render(
                        file=name_parts.group("file"),
                        cls=name_parts.group("cls"),
                        func=name_parts.group("func"),
                        content=html
                    )
                )

with open(outdir / "index.html", "w") as fhtml:
    html = template.render(
        headers = conv.produce_headers(),
        content="\n".join(outputs),
    )
    fhtml.write(html)
