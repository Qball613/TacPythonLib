"""SLIP (Serial Line Internet Protocol) framing for LoRa Mesh TAK.

Implements RFC 1055 SLIP encoding/decoding for wrapping protobuf packets
over serial communication.
"""

from typing import Optional, Tuple

# SLIP special bytes
SLIP_END = 0xC0
SLIP_ESC = 0xDB
SLIP_ESC_END = 0xDC
SLIP_ESC_ESC = 0xDD


def slip_encode(data: bytes) -> bytes:
    """Encode data with SLIP framing.
    
    Args:
        data: Raw bytes to encode (typically serialized protobuf).
        
    Returns:
        SLIP-framed bytes with END delimiter at start and end.
        
    Example:
        >>> slip_encode(b'\\xC0\\xDB')
        b'\\xC0\\xDB\\xDC\\xDB\\xDD\\xC0'
    """
    result = bytearray([SLIP_END])
    for byte in data:
        if byte == SLIP_END:
            result.extend([SLIP_ESC, SLIP_ESC_END])
        elif byte == SLIP_ESC:
            result.extend([SLIP_ESC, SLIP_ESC_ESC])
        else:
            result.append(byte)
    result.append(SLIP_END)
    return bytes(result)


def slip_decode(data: bytes) -> bytes:
    """Decode SLIP-framed data.
    
    Args:
        data: SLIP-framed bytes (with or without END delimiters).
        
    Returns:
        Decoded raw bytes.
        
    Raises:
        ValueError: If invalid escape sequence encountered.
        
    Example:
        >>> slip_decode(b'\\xC0\\xDB\\xDC\\xDB\\xDD\\xC0')
        b'\\xC0\\xDB'
    """
    result = bytearray()
    i = 0
    while i < len(data):
        byte = data[i]
        if byte == SLIP_ESC:
            i += 1
            if i >= len(data):
                raise ValueError("Incomplete escape sequence at end of data")
            next_byte = data[i]
            if next_byte == SLIP_ESC_END:
                result.append(SLIP_END)
            elif next_byte == SLIP_ESC_ESC:
                result.append(SLIP_ESC)
            else:
                raise ValueError(f"Invalid escape sequence: 0xDB 0x{next_byte:02X}")
        elif byte != SLIP_END:
            result.append(byte)
        i += 1
    return bytes(result)


class SlipReader:
    """Stateful SLIP packet reader for streaming data.
    
    Buffers incoming bytes and extracts complete SLIP packets.
    Useful for reading from serial ports where data arrives in chunks.
    
    Example:
        >>> reader = SlipReader()
        >>> reader.feed(b'\\xC0\\x08\\x01')
        >>> reader.feed(b'\\x12\\x02\\x0A\\x00\\xC0')
        >>> packet = reader.get_packet()
        >>> packet
        b'\\x08\\x01\\x12\\x02\\x0A\\x00'
    """
    
    def __init__(self) -> None:
        self._buffer = bytearray()
        self._in_packet = False
        self._packets: list[bytes] = []
    
    def feed(self, data: bytes) -> None:
        """Feed raw bytes into the reader.
        
        Args:
            data: Raw bytes received from serial port.
        """
        for byte in data:
            if byte == SLIP_END:
                if self._in_packet and self._buffer:
                    # End of packet - decode and store
                    try:
                        decoded = slip_decode(bytes(self._buffer))
                        self._packets.append(decoded)
                    except ValueError:
                        pass  # Discard malformed packets
                # Start new packet
                self._in_packet = True
                self._buffer.clear()
            elif self._in_packet:
                self._buffer.append(byte)
    
    def get_packet(self) -> Optional[bytes]:
        """Get the next complete packet if available.
        
        Returns:
            Decoded packet bytes, or None if no complete packet ready.
        """
        if self._packets:
            return self._packets.pop(0)
        return None
    
    def has_packet(self) -> bool:
        """Check if a complete packet is available.
        
        Returns:
            True if at least one packet is ready to read.
        """
        return len(self._packets) > 0
    
    def clear(self) -> None:
        """Clear all buffered data and pending packets."""
        self._buffer.clear()
        self._packets.clear()
        self._in_packet = False
