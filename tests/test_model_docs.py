"""The generated ERD has to be mermaid a renderer will accept.

GitHub renders `docs/data-model.md` and silently drops a block that does not parse, so
a syntax slip in the generator is invisible until someone looks at the page.
The rule this guards is the one that broke it: mermaid entity attributes are
`type name "comment"`, and a line missing the type reads the quoted sentence
as the attribute name and fails the whole diagram.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from model_docs import erd  # noqa: E402

from lakehouse.spec import load_all  # noqa: E402

ATTRIBUTE = re.compile(r'^ {8}\w+ \w+ "[^"]*"$')
RELATIONSHIP = re.compile(r'^ {4}\w+ \}o--\|\| \w+ : "\w+"$')


def test_erd_lines_are_parseable_mermaid() -> None:
    lines = erd(load_all()).splitlines()
    assert lines[0] == "```mermaid"
    assert lines[1] == "erDiagram"
    assert lines[-1] == "```"

    for line in lines[2:-1]:
        if line.endswith("{") or line == "    }":
            continue
        assert ATTRIBUTE.match(line) or RELATIONSHIP.match(line), line
