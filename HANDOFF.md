# Handoff: `msgspec-cbor` — a CBOR bridge for msgspec

**Audience:** an autonomous coding agent. This is a complete build spec. Follow it top to bottom.
**Author of brief:** claude-opus-4-8 on behalf of JP Hutchins (she/her). All facts in the
Technical Appendix were verified empirically against `msgspec 0.21.2.dev` + `cbor2 6.1.3` — do not
treat them as speculative, but *do* re-run the verification in your own test suite.

---

## 1. Objective

Publish a small, well-tested PyPI package that lets [msgspec](https://github.com/msgspec/msgspec)
encode/decode **CBOR** (RFC 8949) by bridging to [cbor2](https://github.com/agronholm/cbor2). The
package mirrors the design of msgspec's own `msgspec.toml` / `msgspec.yaml` wrapper modules: a thin,
pure-Python layer that uses `msgspec.to_builtins` + `msgspec.convert` to move between msgspec's rich
type system and cbor2's native CBOR encoder.

**Why CBOR (context, not a task):** CBOR is an IETF Internet Standard (RFC 8949 / STD 94; foundation
of COSE, CWT, WebAuthn). MessagePack — msgspec's existing binary format — is an ungoverned community
spec. That standardization is the reason this bridge is worth shipping even though msgspec already
has a fast binary format.

**Scope for v0.1:** module-level `encode` / `decode` functions only (exactly like `msgspec.toml`).
No `Encoder`/`Decoder` classes. Keep it small.

**Non-goals:** a native/C CBOR codec, `Encoder`/`Decoder` classes, streaming. These can come later
behind the same public API; do not build them now.

---

## 2. Decisions to confirm with JP before/while starting

These are assumptions baked into this doc. Each is a trivial find/replace if JP wants otherwise.

| Decision | Assumed value | Notes |
|---|---|---|
| Dist name / import name | `msgspec-cbor` / `msgspec_cbor` | Reads as "CBOR for msgspec." Usage: `import msgspec_cbor; msgspec_cbor.encode(...)`. |
| License | **MIT** | Matches cbor2. (msgspec is BSD-3; either is fine — the bridge copies no code from either.) |
| GitHub repo | `github.com/JPHutchins/msgspec-cbor` | Under JP's personal account. |
| Task runner | **camas** (`JPHutchins/camas`) | JP's own runner. `uv tool install camas` or `uvx camas`. |
| Package manager / build | **uv** + `hatchling` (+ `hatch-vcs` for tag-based versioning) | |
| Min Python | **3.10** | Floor of both msgspec and cbor2. |
| Publish | PyPI **Trusted Publishing** (OIDC) on git tag | No stored token. |

---

## 3. Public API (implement exactly this)

Mirror `msgspec.toml` / `msgspec.yaml` signatures so the module is a drop-in sibling format.

```python
def encode(
    obj: Any,
    *,
    enc_hook: Callable[[Any], Any] | None = None,
    order: Literal["deterministic", "sorted"] | None = None,
) -> bytes: ...

def decode(
    buf: Buffer | bytes,
    *,
    type: Any = Any,          # a type in annotation form; default Any = untyped
    strict: bool = True,
    dec_hook: Callable[[type[Any], Any], Any] | None = None,
) -> Any: ...   # overloaded: returns _T when `type: type[_T]` is given
```

Semantics:
- `encode`: lower `obj` with `to_builtins` (passing the verified `_BUILTIN_TYPES`, `enc_hook`,
  `order`), then `cbor2.dumps`.
- `decode`: `cbor2.loads`, then — only if `type is not Any` — `convert` into `type` (passing
  `_BUILTIN_TYPES`, `strict`, `dec_hook`). When `type is Any`, return cbor2's output directly (one
  pass, no validation — same as `msgspec.toml`/`yaml`).
- Translate `cbor2.CBORDecodeError` → `msgspec.DecodeError` (mirrors how toml wraps
  `TOMLDecodeError` and yaml wraps `YAMLError`). Decide + test naive-datetime behavior on encode
  (see Appendix §A.4).

---

## 4. Reference implementation (`src/msgspec_cbor/__init__.py`)

This compiles and passes the roundtrips in the Appendix. Use it as the starting point; keep the
docstrings concise per JP's conventions (§9), not the verbose numpydoc style.

```python
from __future__ import annotations

import datetime as _datetime
import decimal as _decimal
import uuid as _uuid
from typing import TYPE_CHECKING, Any, TypeVar, overload

import cbor2 as _cbor2
from msgspec import (
    DecodeError as _DecodeError,
    convert as _convert,
    to_builtins as _to_builtins,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Literal

    from typing_extensions import Buffer

__all__ = ("encode", "decode")


def __dir__() -> tuple[str, ...]:
    return __all__


# Verified passthrough set: the intersection of "cbor2 encodes this via a native
# CBOR tag" and "msgspec.convert accepts this in builtin_types". See handoff §A.
_BUILTIN_TYPES: tuple[type, ...] = (
    _datetime.datetime,
    _datetime.date,
    bytes,
    bytearray,
    _decimal.Decimal,
    _uuid.UUID,
)


def encode(
    obj: Any,
    *,
    enc_hook: Callable[[Any], Any] | None = None,
    order: Literal["deterministic", "sorted"] | None = None,
) -> bytes:
    """Serialize an object as CBOR."""
    return _cbor2.dumps(
        _to_builtins(
            obj,
            builtin_types=_BUILTIN_TYPES,
            enc_hook=enc_hook,
            order=order,
        )
    )


_T = TypeVar("_T")


@overload
def decode(
    buf: Buffer | bytes,
    *,
    type: type[_T],
    strict: bool = True,
    dec_hook: Callable[[type[Any], Any], Any] | None = None,
) -> _T: ...
@overload
def decode(
    buf: Buffer | bytes,
    *,
    type: Any = ...,
    strict: bool = True,
    dec_hook: Callable[[type[Any], Any], Any] | None = None,
) -> Any: ...
def decode(
    buf: Buffer | bytes,
    *,
    type: Any = Any,
    strict: bool = True,
    dec_hook: Callable[[type[Any], Any], Any] | None = None,
) -> Any:
    """Deserialize an object from CBOR."""
    if not isinstance(buf, (bytes, bytearray)):
        buf = bytes(memoryview(buf))
    try:
        obj = _cbor2.loads(buf)
    except _cbor2.CBORDecodeError as exc:
        raise _DecodeError(str(exc)) from None
    if type is Any:
        return obj
    return _convert(
        obj,
        type,
        builtin_types=_BUILTIN_TYPES,
        strict=strict,
        dec_hook=dec_hook,
    )
```

Add an empty `src/msgspec_cbor/py.typed` marker so the annotations ship (this is a typed library).

---

## 5. Repository layout

```
msgspec-cbor/
├── src/msgspec_cbor/
│   ├── __init__.py        # the module above
│   └── py.typed           # empty marker
├── tests/
│   └── test_cbor.py       # see §7
├── tasks.py               # camas config, §6
├── pyproject.toml         # §8
├── .github/workflows/
│   ├── ci.yml             # test/lint/typecheck via camas
│   └── release.yml        # build + trusted-publish on tag
├── README.md              # §9
├── LICENSE                # MIT (JP Hutchins)
└── .gitignore
```

---

## 6. `tasks.py` (camas)

Canonical camas syntax (from `camas --init`). `matrix=` clones the subtree per axis value and
interpolates `{PY}` into the command. `github_task` runs under `GITHUB_ACTIONS=true`; camas
auto-switches to GitHub-formatted output there. `Claude(fix=...)` wires the Claude Code plugin's
post-edit autofix. Verify with `camas --check` (type-checks this file), `camas --list`, and
`camas --dry-run ci` before relying on it.

```python
# /// script
# requires-python = ">=3.10"
# dependencies = ["camas"]
# ///
"""Project tasks — run with ``camas``."""

from camas import Claude, Config, Parallel, Sequential, Task, run_cli

fmt_check = Task("uv run ruff format --check .", name="fmt_check")
lint = Task("uv run ruff check {paths}", paths=".", name="lint")
typecheck = Task("uv run mypy src", name="typecheck")

# Fast local gate: static checks in parallel, then a single-interpreter test run.
test_quick = Task("uv run pytest -q", name="test_quick")
static = Parallel(fmt_check, lint, typecheck, name="static")
check = Sequential(static, test_quick, name="check")

# Full matrix across supported Pythons (used in CI).
test_matrix = Parallel(
    Task("uv run --python {PY} --group test pytest -q"),
    matrix={"PY": ("3.10", "3.11", "3.12", "3.13", "3.14")},
    help="run the test suite across every supported Python",
    name="test_matrix",
)
ci = Sequential(static, test_matrix, name="ci")

# Deterministic autofixers for the Claude Code plugin's PostToolBatch hook.
autofix = Parallel(
    Task("uv run ruff format {paths}", mutates=True),
    Task("uv run ruff check --fix {paths}", mutates=True),
    paths=".",
    name="autofix",
)

_ = Config(default_task=check, github_task=ci, agent=Claude(fix=autofix))

if __name__ == "__main__":
    run_cli(globals())
```

> Confirm `uv run --python {PY} --group test` selects/downloads each interpreter and syncs the
> `test` dependency group. If it doesn't in your uv version, fall back to a tox-style approach or
> `uv sync --python {PY}` before the test call.

---

## 7. Test plan (`tests/test_cbor.py`)

Use `pytest`. Model structure on msgspec's own `tests/unit/test_toml.py` / `test_yaml.py`. Every
test below must pass; the ones marked **(regression)** guard the exact footguns this bridge exists
to prevent — do not delete them.

1. **Scalar roundtrips** — `int`, `float`, `bool`, `str`, `None`, `bytes`: typed and untyped.
2. **Rich-type roundtrips (regression)** — for tz-aware `datetime`, `date`, `Decimal`, `UUID`:
   `decode(encode(v), type=T) == v`. Additionally assert the wire used the native CBOR tag, not a
   text string, e.g. `encode(dt)[0] == 0xC0` (tag 0) and `encode(date)[:3] == bytes.fromhex("d903ec")`
   (tag 1004), `encode(Decimal(...))[0] == 0xC4` (tag 4), `encode(uuid)[:2] == bytes.fromhex("d825")`
   (tag 37). This is what proves bytes/datetime aren't being silently base64/ISO-stringified.
3. **`time` string fallback** — `datetime.time` is NOT natively encodable by cbor2; confirm it still
   roundtrips (as a text string) into a `time`-typed field.
4. **Struct roundtrip** — a `msgspec.Struct` with `datetime`/`bytes`/`Decimal`/`UUID` fields;
   `decode(encode(m), type=M) == m`. Confirm the top-level wire item is a CBOR map.
5. **Collections** — `list`, `dict`, and `set` (encodes as a CBOR array; decode into `set[int]`
   coerces back). Document that sets are arrays on the wire (not tag 258) — see §A.3.
6. **Untyped decode** — `decode(buf)` with no `type` returns plain cbor2 objects (dict/list/…).
7. **`enc_hook`** — a custom type serialized via `enc_hook`.
8. **`dec_hook`** — a custom type reconstructed via `dec_hook` on typed decode.
9. **`strict=False`** — a widened coercion (e.g. str→int) succeeds where `strict=True` fails.
10. **`order`** — `order="deterministic"` / `"sorted"` produce byte-stable output for dicts.
11. **Error wrapping (regression)** — feed malformed CBOR bytes; assert it raises
    `msgspec.DecodeError`, NOT `cbor2.CBORDecodeError`.
12. **ValidationError** — wrong shape for `type=` raises `msgspec.ValidationError`.
13. **Buffer inputs** — `bytearray` and `memoryview` accepted by `decode`.
14. **Naive datetime (regression)** — decide the behavior (§A.4) and pin it: either it raises a
    clean error, or you set a default tz. Test whichever you choose.

---

## 8. `pyproject.toml`

```toml
[build-system]
requires = ["hatchling", "hatch-vcs"]
build-backend = "hatchling.build"

[project]
name = "msgspec-cbor"
dynamic = ["version"]
description = "CBOR encoding and decoding for msgspec, backed by cbor2."
readme = "README.md"
license = "MIT"
license-files = ["LICENSE"]
requires-python = ">=3.10"
authors = [{ name = "JP Hutchins", email = "jp@intercreate.io" }]
keywords = ["CBOR", "msgspec", "cbor2", "serialization", "validation"]
classifiers = [
  "Development Status :: 4 - Beta",
  "License :: OSI Approved :: MIT License",
  "Programming Language :: Python :: 3.10",
  "Programming Language :: Python :: 3.11",
  "Programming Language :: Python :: 3.12",
  "Programming Language :: Python :: 3.13",
  "Programming Language :: Python :: 3.14",
  "Typing :: Typed",
]
dependencies = [
  "msgspec>=0.19",   # verify floor: needs convert(..., builtin_types=...)
  "cbor2>=5.6",      # verify floor: date=tag1004, Decimal=tag4, UUID=tag37 behavior
]

[project.urls]
Homepage = "https://github.com/JPHutchins/msgspec-cbor"
Issues = "https://github.com/JPHutchins/msgspec-cbor/issues"

[dependency-groups]
test = ["pytest>=8"]
dev = ["camas", "mypy", "ruff"]

[tool.hatch.version]
source = "vcs"

[tool.hatch.build.targets.wheel]
packages = ["src/msgspec_cbor"]

[tool.mypy]
strict = true
extra_checks = true
warn_unreachable = true

[tool.ruff]
# match msgspec's .ruff.toml conventions where reasonable
```

Confirm the two dependency floors by installing the oldest candidate and running the suite; bump if
an older release lacks `convert(builtin_types=...)` or differs on tag behavior.

---

## 9. Conventions (non-negotiable — from JP's global instructions)

The downstream agent may not inherit JP's global config, so it is restated here:

- **Functional style.** Prefer pure functions, immutability, inline calls over temp/alias vars.
  This bridge is naturally stateless — keep it that way.
- **Full type annotations on everything.** `mypy --strict` must pass with zero errors. The library
  ships `py.typed`.
- **No redundant comments; do not remove existing comments.** Docstrings must NOT restate the code
  (SSOT). Keep them short and non-redundant; if a docstring makes a specific claim, it must be
  testable (doctest) — otherwise keep it vague. Do **not** copy msgspec's long numpydoc blocks.
- **Follow the surrounding codebase style**, which here means: match `msgspec.toml`/`msgspec.yaml`
  structure and `msgspec`'s `.ruff.toml`.
- **3.10+**, modern generic syntax.
- **Commit authorship (required):** every commit an agent makes ends with
  `Co-Authored-By: <your-active-model-id> <noreply@<provider>>`
  (e.g. `Co-Authored-By: claude-opus-4-8 <noreply@anthropic.com>`).
- **LLM disclosure (required)** on anything posted under JP's auth (GitHub issues/PRs/comments).
  Use a GFM warning aside:
  > [!WARNING]
  > **LLM Disclosure**
  >
  > This post was authored by `<model-id>` on behalf of @JPhutchins. `<1–4 sentence summary of the
  > prompt that led here>`.

**README must include:** install (`pip install msgspec-cbor`), a 5-line usage example, the supported
type table (§A), an explicit "not affiliated with the msgspec project" note, and attribution to
msgspec (BSD-3) and cbor2 (MIT).

---

## 10. CI / release (GitHub Actions)

- **`ci.yml`** (on push/PR): checkout → install uv (`astral-sh/setup-uv`) → `uv sync` →
  run `uvx camas` (bare `camas` runs `github_task` = full matrix under `GITHUB_ACTIONS=true`, and
  camas emits GitHub-formatted output automatically). Optionally enable camas's per-leaf GitHub
  check runs.
- **`release.yml`** (on tag `v*`): `uv build` → publish with PyPI **Trusted Publishing** (OIDC;
  `id-token: write`, no stored token). Configure the trusted publisher on PyPI first.
- Version comes from the git tag via `hatch-vcs`.

---

## 11. Acceptance checklist

- [ ] `uv sync` clean; `camas --check` type-checks `tasks.py`; `camas --list` shows tasks.
- [ ] `camas` (default `check`) is green locally.
- [ ] `mypy --strict src` and `ruff check .` clean.
- [ ] All §7 tests pass, including the four **(regression)** tests.
- [ ] `import msgspec_cbor; msgspec_cbor.encode / .decode` work; `py.typed` present.
- [ ] Rich types verified on the wire as CBOR tags (not base64/ISO strings).
- [ ] `cbor2.CBORDecodeError` never escapes — always `msgspec.DecodeError`.
- [ ] CI green across Python 3.10–3.14; release workflow dry-run validated.
- [ ] README has usage, type table, affiliation disclaimer, and attributions.
- [ ] Commits carry the `Co-Authored-By` trailer.

---

## Appendix A — Verified technical facts (msgspec 0.21.2.dev, cbor2 6.1.3)

The whole reason this bridge is more than a one-liner. Verified by running the code.

### A.1 The `to_builtins` ↔ `convert` asymmetry (the crux)

- `msgspec.to_builtins(obj, builtin_types=...)` accepts **arbitrary** types in `builtin_types` and
  passes them through untouched.
- `msgspec.convert(obj, type, builtin_types=...)` accepts only the types it can natively decode and
  **raises `TypeError: Cannot treat <X> as a builtin type`** for others.

Measured `convert` acceptance:

| type | `convert` builtin_types |
|---|---|
| `datetime`, `date`, `time`, `timedelta` | accepted |
| `bytes`, `bytearray` | accepted |
| `Decimal`, `UUID` | accepted |
| `Fraction` | **REJECTED** |
| `set`, `frozenset` | **REJECTED** |

Therefore a *symmetric* passthrough set is only safe for the intersection with what cbor2 encodes
natively.

### A.2 Default `to_builtins` lowering (why the naive one-liner is wrong)

Without `builtin_types`, `to_builtins` lowers rich values to strings — silently destroying CBOR
semantics:

| value | `to_builtins` default | cbor2 native | in `_BUILTIN_TYPES`? |
|---|---|---|---|
| `datetime` | `'2024-01-01T12:00:00Z'` (str) | ✓ tag 0/1 | **yes** |
| `date` | `'2024-01-01'` (str) | ✓ tag 1004 | **yes** |
| `bytes` | `'AAE='` (**base64 str!**) | ✓ major-2 | **yes** |
| `bytearray` | base64 str | ✓ major-2 | **yes** |
| `Decimal` | `'1.5'` (str) | ✓ tag 4 | **yes** |
| `UUID` | str | ✓ tag 37 | **yes** |
| `time` | `'12:00:00'` (str) | ✗ (cbor2 can't encode) | no → string fallback |
| `Fraction` | **TypeError (raises)** | ✓ tag 30 | no (convert rejects) |
| `set` | `list` | ✓ tag 258 | no (convert rejects) |

So `cbor2.dumps(msgspec.to_builtins(obj))` — the naive version — base64-encodes bytes, stringifies
datetimes/Decimals, and throws on `Fraction`. `_BUILTIN_TYPES` is exactly the set that avoids this
AND survives the return trip through `convert`.

### A.3 Excluded types & rationale

- **`Fraction`**: cbor2 encodes (tag 30) but `convert` rejects it. Support only via `enc_hook`
  (encode) + `dec_hook` (decode) if a user needs it. Not in defaults.
- **`set`/`frozenset`**: cbor2 encodes (tag 258) but `convert` rejects. Default behavior: they lower
  to a CBOR **array**; decoding into a `set[...]`-typed field coerces the array back to a set. This
  is simpler and more interoperable than tag 258. Document it.
- **`timedelta`**: `convert` accepts it, but cbor2 has no native encoding — leave it out; it is not
  specially handled.

### A.4 Naive datetime (must decide + test)

cbor2 raises `CBOREncodeError` on **naive** (tz-less) `datetime` by default. Because such datetimes
are passed straight through `_BUILTIN_TYPES`, `encode(naive_dt)` will raise from cbor2. Choose one
and pin it with a test:
- (a) Let it surface as a clean `msgspec.EncodeError` (wrap `cbor2.CBOREncodeError` in `encode`), or
- (b) Configure a default timezone on a `cbor2.CBOREncoder` and document the coercion.
Recommendation: (a) — fail loudly; don't silently invent a timezone.

### A.5 Confirmed working (do not re-litigate, but re-test)

`decode(encode(v), type=T) == v` holds for tz-aware `datetime`, `date`, `bytes`, `Decimal`, `UUID`,
`time` (via string), and a `Struct` containing them. Native tags observed on the wire: datetime
`0xC0`, date `0xD903EC` (1004), Decimal `0xC4`, UUID `0xD825` (37), bytes major-type 2.
