# msgspec-cbor

CBOR ([RFC 8949](https://www.rfc-editor.org/rfc/rfc8949)) encoding and decoding for
[msgspec](https://github.com/jcrist/msgspec), backed by [cbor2](https://github.com/agronholm/cbor2).

`msgspec-cbor` is a thin, pure-Python bridge that mirrors the `msgspec.toml` / `msgspec.yaml`
wrapper modules: it lowers objects with `msgspec.to_builtins`, hands them to cbor2's native
encoder, and validates decoded output back into your types with `msgspec.convert`. Rich types
(`datetime`, `bytes`, `Decimal`, `UUID`, …) travel as real CBOR tags — never base64 or ISO strings.

## Install

```sh
pip install msgspec-cbor
```

## Usage

```python
import msgspec
import msgspec_cbor

class Point(msgspec.Struct):
    x: int
    y: int

data = msgspec_cbor.encode(Point(1, 2))        # -> bytes
point = msgspec_cbor.decode(data, type=Point)  # -> Point(x=1, y=2)
```

Omit `type=` to decode into plain CBOR/Python objects with no validation.

## Supported types

The default type table is the intersection of what cbor2 encodes as a native CBOR tag and what
`msgspec.convert` accepts back — so every rich type round-trips losslessly.

| Python type | On the wire | Notes |
|---|---|---|
| `int`, `float`, `bool`, `str`, `None` | native CBOR scalar | |
| `bytes`, `bytearray` | byte string (major type 2) | not base64 |
| `list`, `tuple` | array (major type 4) | |
| `dict`, `msgspec.Struct`, dataclass, `attrs` | map (major type 5) | |
| `datetime.datetime` | tag 0 | tz-aware only; naive raises `msgspec.EncodeError` |
| `datetime.date` | tag 1004 | |
| `decimal.Decimal` | tag 4 | |
| `uuid.UUID` | tag 37 | |
| `datetime.time` | text string | not natively CBOR; string fallback |
| `set`, `frozenset` | array (major type 4) | decode into a `set[...]`-typed field to coerce back |
| `fractions.Fraction`, `datetime.timedelta` | not built in | supply `enc_hook` / `dec_hook` if needed |

Malformed input raises `msgspec.DecodeError`; a shape mismatch against `type=` raises
`msgspec.ValidationError`. cbor2's own exceptions never escape the public API.

## API

```python
def encode(obj, *, enc_hook=None, order=None) -> bytes: ...
def decode(buf, *, type=Any, strict=True, dec_hook=None) -> Any: ...
```

The signatures mirror `msgspec.toml` / `msgspec.yaml`, so this is a drop-in sibling format.

`order` accepts msgspec's `"deterministic"` / `"sorted"` (lexicographic) plus `"canonical"`, which
emits CBOR canonical length-first key ordering (cbor2's `canonical=True`) for byte-exact wire formats.

## Not affiliated

This is an independent bridge and is **not affiliated with or endorsed by the msgspec project**.

## Attribution

- [msgspec](https://github.com/jcrist/msgspec) — BSD-3-Clause
- [cbor2](https://github.com/agronholm/cbor2) — MIT

`msgspec-cbor` is MIT licensed and copies no code from either project.
