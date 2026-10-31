"""Lossless signed-int32 geometry stream encoding; no topology changes."""


def encode_signed32(values):
    output = bytearray()
    for value in values:
        if not -(1 << 31) <= value < (1 << 31):
            raise ValueError("Value outside signed32")
        unsigned = (value << 1) ^ (value >> 31)
        while unsigned >= 128:
            output.append((unsigned & 127) | 128)
            unsigned >>= 7
        output.append(unsigned)
    return output


def decode_signed32(blocks, maximum_values):
    unsigned = shift = count = 0
    for block in blocks:
        for byte in block:
            if shift == 28 and byte > 15:
                raise ValueError("Value outside signed32 or too long")
            unsigned |= (byte & 127) << shift
            if byte & 128:
                shift += 7
                continue
            if shift and byte == 0:
                raise ValueError("Noncanonical integer")
            count += 1
            if count > maximum_values:
                raise ValueError("Too many values")
            yield (unsigned >> 1) ^ -(unsigned & 1)
            unsigned = shift = 0
    if shift:
        raise ValueError("Truncated integer")
