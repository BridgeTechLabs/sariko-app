"""One seller name rule (docs/dev/seller-full-name N2, N6): the bank holder and the signature must have
the same words as the full name, any order; a full name is letters, spaces and - ' . only.
seller_name_cases.json is the shared case table: it runs here through core/seller_kyc.py and through
frontend/src/utils/sellerName.js (joinStore's copy, with node), and the admin repo keeps the same file
for its copy in utils/seller_completion.py. Change the rule = change all three and this table.

Run from tests/backend:  pytest unit/test_seller_name_rule.py
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

import core.seller_kyc as kyc

CASES = json.loads(Path(__file__).with_name("seller_name_cases.json").read_text(encoding="utf-8"))
SRC = Path(kyc.__file__).resolve().parent.parent            # backend/src locally, /www in CI
FRONTEND = Path(__file__).resolve().parents[3] / "frontend" / "src"   # not in the CI image


def backend(case):
    if case["rule"] == "clean":
        return kyc.clean_full_name(case["text"])
    return kyc.name_matches(case["typed"], case["full_name"], ignore_accents=case["rule"] == "holder")


@pytest.mark.parametrize("case", CASES, ids=lambda c: f'{c["rule"]}:{c.get("typed", c.get("text"))!r}')
def test_backend_rule(case):
    assert backend(case) == case["expect"]


NODE_RUN = """
import { readFileSync } from 'fs'
const [rule, cases] = [await import(process.argv[1]), JSON.parse(readFileSync(process.argv[2], 'utf8'))]
console.log(JSON.stringify(cases.map(c => c.rule === 'clean' ? rule.cleanFullName(c.text)
    : rule.nameMatches(c.typed, c.full_name, c.rule === 'holder'))))
"""


@pytest.mark.skipif(not (FRONTEND.exists() and shutil.which("node")), reason="frontend + node only outside the CI image")
def test_frontend_rule_gives_the_same_answers():
    out = subprocess.run(
        ["node", "--input-type=module", "-e", NODE_RUN, (FRONTEND / "utils" / "sellerName.js").as_uri(),
         str(Path(__file__).with_name("seller_name_cases.json"))],
        capture_output=True, text=True, check=True,
    ).stdout
    got = json.loads(out)
    wrong = [(c, g) for c, g in zip(CASES, got) if g != c["expect"]]
    assert not wrong and len(got) == len(CASES)


# N1, N3: no code reads or writes first_name / last_name any more. What is left: the request fields an
# older client still sends (schemas, and the request attribute body.first_name), joined into full_name.
NAME = re.compile(r"(?<![\w.])(first_name|last_name)\b")


def test_backend_no_longer_reads_first_last_name():
    found = [f"{p.relative_to(SRC)}:{n}: {line.strip()}"
             for p in sorted(SRC.rglob("*.py")) if "__pycache__" not in p.parts and p.parent.name != "schemas"
             for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1) if NAME.search(line)]
    assert found == []


@pytest.mark.skipif(not FRONTEND.exists(), reason="frontend is not in the CI image")
def test_frontend_no_longer_reads_first_last_name():
    found = sorted({str(p.relative_to(FRONTEND)) for p in FRONTEND.rglob("*")
                    if p.suffix in (".js", ".vue") and re.search(r"first_name|last_name", p.read_text(encoding="utf-8"))})
    assert found == ["stores/join/joinStore.js"]   # only: an old draft's name moves into the one box
