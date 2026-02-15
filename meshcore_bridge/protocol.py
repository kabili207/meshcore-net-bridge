"""MeshCore RS232 bridge protocol framing and checksum.

Frame format:
    [0xC0][0x3E][len_high][len_low][payload...][checksum_high][checksum_low]

- Magic: 0xC03E (2 bytes, big-endian)
- Length: 2 bytes, big-endian - length of payload only
- Payload: Raw mesh packet bytes
- Checksum: Fletcher-16 over payload only, 2 bytes big-endian
"""

FRAME_MAGIC = b"\xc0\x3e"
HEADER_SIZE = 4  # magic (2) + length (2)
CHECKSUM_SIZE = 2


def fletcher16(data: bytes) -> int:
    """Calculate Fletcher-16 checksum over data."""
    sum1, sum2 = 0, 0
    for b in data:
        sum1 = (sum1 + b) % 255
        sum2 = (sum2 + sum1) % 255
    return (sum2 << 8) | sum1


def encode_frame(payload: bytes) -> bytes:
    """Encode a payload into a framed packet."""
    length = len(payload)
    checksum = fletcher16(payload)
    return (
        FRAME_MAGIC
        + length.to_bytes(2, "big")
        + payload
        + checksum.to_bytes(2, "big")
    )


class FrameDecoder:
    """Stateful decoder for extracting frames from a byte stream."""

    def __init__(self) -> None:
        self._buffer = bytearray()

    def feed(self, data: bytes) -> list[bytes]:
        """Feed bytes into decoder, return list of complete payloads."""
        self._buffer.extend(data)
        frames = []

        while True:
            # Look for magic bytes
            try:
                start = self._buffer.index(FRAME_MAGIC[0])
            except ValueError:
                self._buffer.clear()
                break

            # Discard bytes before magic
            if start > 0:
                del self._buffer[:start]

            # Check for complete magic
            if len(self._buffer) < 2:
                break
            if self._buffer[1] != FRAME_MAGIC[1]:
                # False positive, skip this byte
                del self._buffer[:1]
                continue

            # Need full header to get length
            if len(self._buffer) < HEADER_SIZE:
                break

            length = (self._buffer[2] << 8) | self._buffer[3]
            frame_size = HEADER_SIZE + length + CHECKSUM_SIZE

            # Wait for complete frame
            if len(self._buffer) < frame_size:
                break

            # Extract and validate
            payload = bytes(self._buffer[HEADER_SIZE : HEADER_SIZE + length])
            received_checksum = (
                self._buffer[HEADER_SIZE + length] << 8
            ) | self._buffer[HEADER_SIZE + length + 1]

            expected_checksum = fletcher16(payload)
            if received_checksum == expected_checksum:
                frames.append(payload)
            # else: checksum mismatch, discard frame silently

            # Remove processed frame
            del self._buffer[:frame_size]

        return frames
