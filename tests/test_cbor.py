from __future__ import annotations

import datetime
import decimal
import uuid
from typing import Any

import cbor2
import msgspec
import pytest
from typing_extensions import assert_type

import msgspec_cbor


class Record(msgspec.Struct):
	when: datetime.datetime
	blob: bytes
	amount: decimal.Decimal
	ident: uuid.UUID


def test_scalar_roundtrips_typed() -> None:
	assert msgspec_cbor.decode(msgspec_cbor.encode(42), type=int) == 42
	assert msgspec_cbor.decode(msgspec_cbor.encode(3.5), type=float) == 3.5
	assert msgspec_cbor.decode(msgspec_cbor.encode(True), type=bool) is True
	assert msgspec_cbor.decode(msgspec_cbor.encode("hi"), type=str) == "hi"
	assert msgspec_cbor.decode(msgspec_cbor.encode(None), type=None) is None
	assert msgspec_cbor.decode(msgspec_cbor.encode(b"\x00\x01"), type=bytes) == b"\x00\x01"


def test_scalar_roundtrips_untyped() -> None:
	for value in (42, 3.5, "hi", None, b"\x00\x01"):
		assert msgspec_cbor.decode(msgspec_cbor.encode(value)) == value


def test_rich_type_roundtrips_use_native_tags() -> None:
	when = datetime.datetime(2024, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
	day = datetime.date(2024, 1, 1)
	amount = decimal.Decimal("1.5")
	ident = uuid.uuid4()

	assert msgspec_cbor.decode(msgspec_cbor.encode(when), type=datetime.datetime) == when
	assert msgspec_cbor.decode(msgspec_cbor.encode(day), type=datetime.date) == day
	assert msgspec_cbor.decode(msgspec_cbor.encode(amount), type=decimal.Decimal) == amount
	assert msgspec_cbor.decode(msgspec_cbor.encode(ident), type=uuid.UUID) == ident

	assert msgspec_cbor.encode(when)[0] == 0xC0
	assert msgspec_cbor.encode(day)[:3] == bytes.fromhex("d903ec")
	assert msgspec_cbor.encode(amount)[0] == 0xC4
	assert msgspec_cbor.encode(ident)[:2] == bytes.fromhex("d825")
	assert msgspec_cbor.encode(b"\x00\x01")[0] >> 5 == 2


def test_time_string_fallback() -> None:
	value = datetime.time(12, 30, 0)
	assert msgspec_cbor.encode(value)[0] >> 5 == 3
	assert msgspec_cbor.decode(msgspec_cbor.encode(value), type=datetime.time) == value


def test_struct_roundtrip() -> None:
	record = Record(
		when=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
		blob=b"\xde\xad",
		amount=decimal.Decimal("9.99"),
		ident=uuid.UUID(int=0),
	)
	buf = msgspec_cbor.encode(record)
	assert buf[0] >> 5 == 5
	decoded = msgspec_cbor.decode(buf, type=Record)
	assert decoded == record
	assert_type(decoded, Record)


def test_collections() -> None:
	assert msgspec_cbor.decode(msgspec_cbor.encode([1, 2, 3]), type=list[int]) == [1, 2, 3]
	assert msgspec_cbor.decode(msgspec_cbor.encode({"a": 1}), type=dict[str, int]) == {"a": 1}

	buf = msgspec_cbor.encode({1, 2, 3})
	assert buf[0] >> 5 == 4
	assert msgspec_cbor.decode(buf, type=set[int]) == {1, 2, 3}


def test_untyped_decode_returns_plain_objects() -> None:
	result = msgspec_cbor.decode(msgspec_cbor.encode({"a": [1, 2], "b": "x"}))
	assert result == {"a": [1, 2], "b": "x"}
	assert isinstance(result, dict)


def test_enc_hook() -> None:
	def enc_hook(obj: Any) -> Any:
		if isinstance(obj, complex):
			return [obj.real, obj.imag]
		raise NotImplementedError

	buf = msgspec_cbor.encode(complex(1, 2), enc_hook=enc_hook)
	assert msgspec_cbor.decode(buf) == [1.0, 2.0]


def test_dec_hook() -> None:
	def dec_hook(typ: type[Any], obj: Any) -> Any:
		if typ is complex:
			return complex(obj[0], obj[1])
		raise NotImplementedError

	buf = msgspec_cbor.encode([1.0, 2.0])
	assert msgspec_cbor.decode(buf, type=complex, dec_hook=dec_hook) == complex(1, 2)


def test_strict_false_widens_coercion() -> None:
	buf = msgspec_cbor.encode("42")
	with pytest.raises(msgspec.ValidationError):
		msgspec_cbor.decode(buf, type=int)
	assert msgspec_cbor.decode(buf, type=int, strict=False) == 42


def test_order_is_byte_stable() -> None:
	for order in ("deterministic", "sorted"):
		first = msgspec_cbor.encode({"b": 1, "a": 2}, order=order)
		second = msgspec_cbor.encode({"a": 2, "b": 1}, order=order)
		assert first == second


def test_order_canonical_is_length_first() -> None:
	payload = {
		"hash": b"\x00",
		"slot": 0,
		"image": 0,
		"active": True,
		"pending": False,
		"version": "1.0",
		"bootable": True,
		"confirmed": True,
		"permanent": False,
	}
	length_first = [
		"hash",
		"slot",
		"image",
		"active",
		"pending",
		"version",
		"bootable",
		"confirmed",
		"permanent",
	]
	buf = msgspec_cbor.encode(payload, order="canonical")
	assert_type(buf, bytes)
	assert list(cbor2.loads(buf)) == length_first
	assert buf != msgspec_cbor.encode(payload, order="sorted")


def test_order_canonical_matches_cbor2_canonical() -> None:
	builtin_types = (
		datetime.datetime,
		datetime.date,
		bytes,
		bytearray,
		decimal.Decimal,
		uuid.UUID,
	)
	record = Record(
		when=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
		blob=b"\xde\xad",
		amount=decimal.Decimal("9.99"),
		ident=uuid.UUID(int=0),
	)
	assert msgspec_cbor.encode(record, order="canonical") == cbor2.dumps(
		msgspec.to_builtins(record, builtin_types=builtin_types), canonical=True
	)


def test_malformed_cbor_wraps_as_decode_error() -> None:
	with pytest.raises(msgspec.DecodeError) as excinfo:
		msgspec_cbor.decode(b"\x82\x01")
	assert not isinstance(excinfo.value, cbor2.CBORDecodeError)


def test_validation_error_on_wrong_shape() -> None:
	with pytest.raises(msgspec.ValidationError):
		msgspec_cbor.decode(msgspec_cbor.encode("abc"), type=int)


def test_buffer_inputs() -> None:
	buf = msgspec_cbor.encode([1, 2, 3])
	assert msgspec_cbor.decode(bytearray(buf), type=list[int]) == [1, 2, 3]
	assert msgspec_cbor.decode(memoryview(buf), type=list[int]) == [1, 2, 3]


def test_naive_datetime_wraps_as_encode_error() -> None:
	with pytest.raises(msgspec.EncodeError):
		msgspec_cbor.encode(datetime.datetime(2024, 1, 1, 12, 0, 0))
