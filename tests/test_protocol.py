import unittest

from src.protocol import (
    FunctionCode,
    ModbusResponseError,
    append_crc,
    build_read_request,
    build_write_multiple_request,
    crc16,
    parse_read_response,
    parse_write_response,
    scale_from_register,
    scale_to_register,
    status_bits_to_dict,
    verify_crc,
)


class ProtocolTests(unittest.TestCase):
    def test_crc_matches_manual_example(self):
        frame_without_crc = bytes.fromhex("01 04 03 e8 00 02")
        self.assertEqual(crc16(frame_without_crc), 0xBBF1)
        self.assertEqual(build_read_request(0x01, FunctionCode.READ_INPUT_REGISTERS, 1000, 2), bytes.fromhex("01 04 03 e8 00 02 f1 bb"))

    def test_write_multiple_matches_manual_example(self):
        request = build_write_multiple_request(0x01, 0x07D1, [0x0ED8, 0x0100])
        self.assertEqual(request, bytes.fromhex("01 10 07 d1 00 02 04 0e d8 01 00 9a 4c"))

    def test_parse_read_response(self):
        response = bytes.fromhex("01 04 04 0e d8 01 00 78 c7")
        values = parse_read_response(response, 0x01, FunctionCode.READ_INPUT_REGISTERS, 2)
        self.assertEqual(values, [0x0ED8, 0x0100])

    def test_parse_write_response(self):
        response = bytes.fromhex("01 10 07 e0 00 01 01 4b")
        parse_write_response(response, 0x01, FunctionCode.WRITE_MULTIPLE_REGISTERS, 0x07E0, 1)

    def test_exception_response_raises(self):
        response = append_crc(bytes([0x01, 0x84, 0x02]))
        with self.assertRaises(ModbusResponseError):
            parse_read_response(response, 0x01, FunctionCode.READ_INPUT_REGISTERS, 1)

    def test_crc_validation_and_scaling(self):
        frame = append_crc(bytes.fromhex("01 06 07 e0 00 00"))
        self.assertTrue(verify_crc(frame))
        self.assertEqual(scale_to_register(5.125), 5125)
        self.assertEqual(scale_from_register(1250), 1.25)

    def test_status_bits(self):
        decoded = status_bits_to_dict((1 << 15) | (1 << 5) | (1 << 1) | (1 << 0))
        self.assertTrue(decoded["output_on"])
        self.assertTrue(decoded["constant_current"])
        self.assertTrue(decoded["over_current"])
        self.assertTrue(decoded["fault"])


if __name__ == "__main__":
    unittest.main()
