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


import struct
import json


TAG_AJS = b'AJS'    # json payload
TAG_ABN = b'ABN'    # binary payload
HEADER_LENGTH = 8   # tag + length


def payload_length_to_pad_length(payload_length):
    p = payload_length % 8
    if p > 0:
        p = 8 - p
    return p


def header_pack(tag, length):
    if len(tag) != 3:
        raise ValueError(f'invalid tag length {len(tag)}')
    if not isinstance(tag, bytes):
        raise ValueError(f'invalid tag type {type(tag)}')
    length = int(length)
    if length < 0 or length >= 2**24:
        raise ValueError(f'length out of range: {length}')
    length_bytes = struct.pack('<I', length)
    return tag + b'\x00' + length_bytes


def header_unpack(header):
    if len(header) < HEADER_LENGTH:
        raise ValueError('header is too short')
    tag = header[0:3]
    length_bytes = header[4:8]
    length = struct.unpack('<I', length_bytes)[0]
    return tag, length


def pack(tag, payload):
    if not isinstance(payload, bytes):
        raise ValueError(f'invalid payload type {type(tag)}')
    header_pack(tag, len(payload))
    length = len(payload)
    length_bytes = struct.pack('<I', len(payload))
    pad = payload_length_to_pad_length(length)
    pad_bytes = bytes([0] * pad)
    return tag + b'\x00' + length_bytes + payload + pad_bytes


def tpack(payload):
    if isinstance(payload, dict):
        return pack(TAG_AJS, json.dumps(payload).encode('utf-8'))
    else:
        return pack(TAG_ABN, payload)


async def receive(reader):
    header = await reader.readexactly(HEADER_LENGTH)
    tag, length = header_unpack(header)
    pad = payload_length_to_pad_length(length)
    data = await reader.readexactly(length + pad)
    if not pad:
        payload = data
    else:
        payload = data[:-pad]
    return tag, payload


def ajs_receive(payload):
    return json.loads(payload.decode('utf-8'))


async def treceive(reader):
    tag, payload = await receive(reader)
    if tag == TAG_AJS:
        return ajs_receive(payload)
    elif tag == TAG_ABN:
        return payload
    else:
        raise ValueError('unsupported tag')

