### IMPORTS
### ============================================================================
## Standard Library

## Installed

## Application


### FUNCTIONS
### ============================================================================
def is_unsigned_int_size(
    value: int, bits: int, *, throw_error: bool = False, value_name: str = "value"
) -> bool:
    """Check if a given integer fits within an unsigned integer of `bits` bits.

    Args:
        value: integer to check
        bits: number of bits, must be `>0`.
        throw_error: throw a `ValueError` if the result is `False`
        value_name: name to use when throwing an error

    Raises:
        ValueError: if invalid `bits` provided
        ValueError: if `throw_error` is `True` and the result would be `False`.
    """
    if bits < 1:
        raise ValueError("bits must be > 0")

    if value < 0:
        result = False
    else:
        result = value.bit_length() <= bits

    if not result and throw_error:
        raise ValueError(f"{value_name} must be between 0 and {2**bits-1} inclusive ({bits} bits)")
    return result
