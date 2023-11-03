# pylint: disable=missing-class-docstring,missing-function-docstring

### IMPORTS
### ============================================================================
## Standard Library

## Installed
import pytest

from nserver.util import is_unsigned_int_size

## Application


### TESTS
### ============================================================================
@pytest.mark.parametrize(
    "value,bits,expected",
    [
        (-1, 8, False),
        (0, 8, True),
        (1, 8, True),
        (2**8 - 1, 8, True),
        (2**8, 8, False),
        (-1, 16, False),
        (0, 16, True),
        (1, 16, True),
        (2**15, 16, True),
        (2**16 - 1, 16, True),
        (2**16, 16, False),
        (-1, 32, False),
        (0, 32, True),
        (1, 32, True),
        (2**31, 32, True),
        (2**32 - 1, 32, True),
        (2**32, 32, False),
        (-1, 64, False),
        (0, 64, True),
        (1, 64, True),
        (2**63, 64, True),
        (2**64 - 1, 64, True),
        (2**64, 64, False),
        (-1, 128, False),
        (0, 128, True),
        (1, 128, True),
        (2**127, 128, True),
        (2**128 - 1, 128, True),
        (2**128, 128, False),
    ],
)
def test_is_unsigned_int_size(value: int, bits: int, expected: bool):
    assert is_unsigned_int_size(value, bits) == expected

    if not expected:
        # Check also throws error correctly
        with pytest.raises(ValueError, match="xxx must be between 0 and"):
            is_unsigned_int_size(value, bits, throw_error=True, value_name="xxx")
    return


@pytest.mark.parametrize("bits", [-99, -1, 0])
def test_is_unsigned_int_size_invalid_bits(bits):
    with pytest.raises(ValueError, match="bits must be"):
        is_unsigned_int_size(0, bits)
    return
