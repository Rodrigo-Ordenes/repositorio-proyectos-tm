"""Minimal QR Code encoder (byte mode, error correction level M, versions 1–10) rendered as SVG, standard library only.

Enough for the exit-ticket links (up to 213 bytes). Follows ISO/IEC 18004: Reed–Solomon over GF(256) with 0x11D,
BCH-coded format and version information, and the mask with the lowest penalty score.
"""
from __future__ import annotations

# Level M: error-correction codewords per block, and the data codewords of each block.
_BLOCKS = {1: (10, [16]), 2: (16, [28]), 3: (26, [44]), 4: (18, [32] * 2), 5: (24, [43] * 2), 6: (16, [27] * 4),
           7: (18, [31] * 4), 8: (22, [38, 38, 39, 39]), 9: (22, [36, 36, 36, 37, 37]), 10: (26, [43, 43, 43, 43, 44])}
_ALIGN = {1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30], 6: [6, 34], 7: [6, 22, 38], 8: [6, 24, 42],
          9: [6, 26, 46], 10: [6, 28, 50]}

_EXP, _LOG = [0] * 512, [0] * 256
_value = 1
for _i in range(255):
    _EXP[_i], _LOG[_value] = _value, _i
    _value <<= 1
    if _value & 0x100: _value ^= 0x11D
for _i in range(255, 512): _EXP[_i] = _EXP[_i - 255]


def _mul(a, b):
    return 0 if a == 0 or b == 0 else _EXP[_LOG[a] + _LOG[b]]


def _ecc(data, degree):
    generator = [1]
    for i in range(degree):
        generator = [c ^ (_mul(generator[j - 1], _EXP[i]) if j else 0) for j, c in enumerate(generator + [0])]
    remainder = list(data) + [0] * degree
    for i in range(len(data)):
        factor = remainder[i]
        if factor:
            for j in range(1, degree + 1): remainder[i + j] ^= _mul(generator[j], factor)
    return remainder[len(data):]


def _codewords(data: bytes):
    for version in _BLOCKS:
        ec, blocks = _BLOCKS[version]
        capacity = sum(blocks)
        count_bits = 8 if version < 10 else 16
        if 4 + count_bits + 8 * len(data) <= capacity * 8: break
    else:
        raise ValueError("Texto demasiado largo para el código QR.")
    bits = []
    put = lambda value, length: bits.extend((value >> i) & 1 for i in reversed(range(length)))
    put(0b0100, 4); put(len(data), count_bits)
    for byte in data: put(byte, 8)
    put(0, min(4, capacity * 8 - len(bits)))
    bits.extend([0] * (-len(bits) % 8))
    words = [int("".join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8)]
    pad = 0xEC
    while len(words) < capacity:
        words.append(pad); pad ^= 0xEC ^ 0x11
    split, start = [], 0
    for size in blocks:
        split.append(words[start:start + size]); start += size
    corrections = [_ecc(block, ec) for block in split]
    result = [block[i] for i in range(max(blocks)) for block in split if i < len(block)]
    return version, result + [block[i] for i in range(ec) for block in corrections]


def _mask(mask, row, col):
    return [(row + col) % 2 == 0, row % 2 == 0, col % 3 == 0, (row + col) % 3 == 0, (row // 2 + col // 3) % 2 == 0,
            row * col % 2 + row * col % 3 == 0, (row * col % 2 + row * col % 3) % 2 == 0,
            ((row + col) % 2 + row * col % 3) % 2 == 0][mask]


def _build(version, words, mask):
    size = 17 + 4 * version
    grid = [[False] * size for _ in range(size)]
    fixed = [[False] * size for _ in range(size)]

    def put(row, col, dark):
        grid[row][col], fixed[row][col] = dark, True

    for top, left in ((0, 0), (0, size - 7), (size - 7, 0)):
        for dr in range(-1, 8):
            for dc in range(-1, 8):
                row, col = top + dr, left + dc
                if 0 <= row < size and 0 <= col < size:
                    ring = max(abs(dr - 3), abs(dc - 3))
                    put(row, col, ring != 2 and ring != 4)
    for i in range(8, size - 8):
        put(6, i, i % 2 == 0); put(i, 6, i % 2 == 0)
    centers = _ALIGN[version]
    corners = {(centers[0], centers[0]), (centers[0], centers[-1]), (centers[-1], centers[0])} if centers else set()
    for row in centers:
        for col in centers:
            if (row, col) in corners: continue
            for dr in range(-2, 3):
                for dc in range(-2, 3): put(row + dr, col + dc, max(abs(dr), abs(dc)) != 1)
    # Format information: level M (00) and the mask, BCH(15,5) and XOR mask 0x5412.
    data = mask
    remainder = data
    for _ in range(10): remainder = (remainder << 1) ^ ((remainder >> 9) * 0x537)
    bits = ((data << 10) | remainder) ^ 0x5412
    bit = lambda i: (bits >> i) & 1 == 1
    for i in range(6): put(i, 8, bit(i))
    put(7, 8, bit(6)); put(8, 8, bit(7)); put(8, 7, bit(8))
    for i in range(9, 15): put(8, 14 - i, bit(i))
    for i in range(8): put(8, size - 1 - i, bit(i))
    for i in range(8, 15): put(size - 15 + i, 8, bit(i))
    put(size - 8, 8, True)
    if version >= 7:
        remainder = version
        for _ in range(12): remainder = (remainder << 1) ^ ((remainder >> 11) * 0x1F25)
        version_bits = (version << 12) | remainder
        for i in range(18):
            dark = (version_bits >> i) & 1 == 1
            a, b = size - 11 + i % 3, i // 3
            put(b, a, dark); put(a, b, dark)
    index, total = 0, len(words) * 8
    right = size - 1
    while right >= 1:
        if right == 6: right = 5
        for vertical in range(size):
            for j in range(2):
                col = right - j
                upward = ((right + 1) & 2) == 0
                row = size - 1 - vertical if upward else vertical
                if not fixed[row][col] and index < total:
                    grid[row][col] = (words[index >> 3] >> (7 - (index & 7))) & 1 == 1
                    index += 1
        right -= 2
    for row in range(size):
        for col in range(size):
            if not fixed[row][col] and _mask(mask, row, col): grid[row][col] = not grid[row][col]
    return grid


def _penalty(grid):
    size, score = len(grid), 0
    lines = grid + [list(column) for column in zip(*grid)]
    for line in lines:
        run, previous = 0, None
        for dark in line:
            run = run + 1 if dark == previous else 1
            previous = dark
            if run == 5: score += 3
            elif run > 5: score += 1
        text = "".join("1" if dark else "0" for dark in line)
        score += 40 * (text.count("10111010000") + text.count("00001011101"))
    for row in range(size - 1):
        for col in range(size - 1):
            if grid[row][col] == grid[row][col + 1] == grid[row + 1][col] == grid[row + 1][col + 1]: score += 3
    dark = sum(map(sum, grid))
    return score + abs(dark * 20 - size * size * 10) // (size * size) * 10


def matrix(text: str):
    version, words = _codewords(text.encode("utf-8"))
    return min((_build(version, words, mask) for mask in range(8)), key=_penalty)


def svg(text: str) -> str:
    grid = matrix(text)
    size = len(grid) + 8
    path = "".join(f"M{col + 4},{row + 4}h1v1h-1z" for row, line in enumerate(grid) for col, dark in enumerate(line) if dark)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" shape-rendering="crispEdges">'
            f'<rect width="{size}" height="{size}" fill="#fff"/><path d="{path}" fill="#000"/></svg>')
