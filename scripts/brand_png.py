"""Read-only validation of the selected static 8-bit RGB/RGBA PNG profile."""
import struct
import zlib


def validate_png(raw):
    if len(raw) < 45 or len(raw) > 2_000_000 or raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("Expected a bounded selected-profile PNG")
    offset, header, ended, idat_ended = 8, None, False, False
    compressed = bytearray()
    while offset < len(raw):
        if offset + 12 > len(raw):
            raise ValueError("Truncated PNG chunk")
        length = struct.unpack(">I", raw[offset:offset + 4])[0]
        kind = raw[offset + 4:offset + 8]
        end = offset + 12 + length
        if end > len(raw) or not all(65 <= char <= 90 or 97 <= char <= 122 for char in kind):
            raise ValueError("Invalid PNG chunk length/type")
        data = raw[offset + 8:end - 4]
        if zlib.crc32(kind + data) & 0xffffffff != struct.unpack(">I", raw[end - 4:end])[0]:
            raise ValueError("PNG chunk checksum differs")
        if header is None:
            if kind != b"IHDR" or length != 13:
                raise ValueError("PNG needs its first IHDR")
            width, height, depth, color, compression, filtering, interlace = struct.unpack(">IIBBBBB", data)
            if not (0 < width <= 1600 and 0 < height <= 600) or depth != 8 or color not in (2, 6) or (compression, filtering, interlace) != (0, 0, 0):
                raise ValueError("PNG exceeds the selected static RGB/RGBA profile")
            header = (width, height, 3 if color == 2 else 4)
        elif kind == b"IDAT":
            if idat_ended:
                raise ValueError("PNG data chunks must be contiguous")
            compressed.extend(data)
        elif kind == b"IEND":
            if length or not compressed or end != len(raw):
                raise ValueError("PNG must end after its image data")
            ended = True
        elif kind in (b"IHDR", b"acTL", b"fcTL", b"fdAT") or (not kind[0] & 32 and kind != b"PLTE"):
            raise ValueError("Unsupported critical or animated PNG chunk")
        elif compressed:
            idat_ended = True
        offset = end
    if not ended or header is None:
        raise ValueError("Incomplete PNG")
    width, height, channels = header
    stride = 1 + width * channels
    expected = stride * height
    decoder = zlib.decompressobj()
    try:
        pixels = decoder.decompress(compressed, expected + 1)
    except zlib.error as error:
        raise ValueError("PNG image data does not decompress") from error
    if len(pixels) != expected or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail or any(pixels[i] > 4 for i in range(0, expected, stride)):
        raise ValueError("PNG image rows are incomplete or outside the profile")
    return raw
