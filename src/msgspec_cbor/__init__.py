"""CBOR encoding and decoding for msgspec, backed by cbor2."""

from __future__ import annotations

import datetime as _datetime
import decimal as _decimal
import uuid as _uuid
from typing import TYPE_CHECKING, Any, TypeVar, overload

import cbor2 as _cbor2
from msgspec import (
	DecodeError as _DecodeError,
	EncodeError as _EncodeError,
	convert as _convert,
	to_builtins as _to_builtins,
)

if TYPE_CHECKING:
	from collections.abc import Callable
	from typing import Final, Literal

	from typing_extensions import Buffer


_BUILTIN_TYPES: Final[tuple[type, ...]] = (
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
	order: Literal["deterministic", "sorted", "canonical"] | None = None,
) -> bytes:
	"""Serialize an object as CBOR.

	``order="canonical"`` sorts map keys length-first (shortest encoding first,
	then bytewise), matching cbor2's canonical mode; ``"deterministic"`` and
	``"sorted"`` apply msgspec's lexicographic orderings instead.

	Raises:
		msgspec.EncodeError: If the object cannot be represented as CBOR (e.g. a
			naive datetime, which cbor2 refuses without a default timezone).
	"""
	try:
		return _cbor2.dumps(
			_to_builtins(
				obj,
				builtin_types=_BUILTIN_TYPES,
				enc_hook=enc_hook,
				order=None if order == "canonical" else order,
			),
			canonical=order == "canonical",
		)
	except _cbor2.CBOREncodeError as exc:
		raise _EncodeError(str(exc)) from None


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
	"""Deserialize an object from CBOR.

	Raises:
		msgspec.DecodeError: If ``buf`` is not well-formed CBOR, or if it does not
			match ``type`` (as ``msgspec.ValidationError``).
	"""
	if not isinstance(buf, (bytes, bytearray)):
		buf = bytes(memoryview(buf))
	try:
		obj = _cbor2.loads(buf)
	except _cbor2.CBORDecodeError as exc:
		raise _DecodeError(str(exc)) from None
	if type is Any:
		return obj
	return _convert(obj, type, builtin_types=_BUILTIN_TYPES, strict=strict, dec_hook=dec_hook)
