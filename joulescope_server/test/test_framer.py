# Copyright 2020 Jetperch LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from joulescope_server import framer
import unittest


class TestFramer(unittest.TestCase):

    def test_pad(self):
        a = [0, 7, 6, 5, 4, 3, 2, 1, 0, 7, 6, 5, 4, 3, 2, 1, 0, 7, 6, 5, 4, 3, 2, 1, 0]
        for length, k in enumerate(a):
            self.assertEqual(k, framer.payload_length_to_pad_length(length))

    def test_header(self):
        tag1, len1 = b'ABN', 8
        header = framer.header_pack(tag1, len1)
        self.assertEqual(b'ABN\x00\x08\x00\x00\x00', header)
        tag2, len2 = framer.header_unpack(header)
        self.assertEqual(tag1, tag2)
        self.assertEqual(len1, len2)

    def test_pack_no_pad(self):
        payload = b'12345678'
        data = framer.pack(framer.TAG_ABN, b'12345678')
        self.assertEqual(b'ABN\x00\x08\x00\x00\x0012345678', data)
        tag, length = framer.header_unpack(data)
        self.assertEqual(b'ABN', tag)
        self.assertEqual(8, len(payload))

    def test_pack_with_pad(self):
        data = framer.pack(framer.TAG_ABN, b'hello')
        self.assertEqual(b'ABN\x00\x05\x00\x00\x00hello\x00\x00\x00', data)
