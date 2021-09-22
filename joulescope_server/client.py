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


import asyncio
from joulescope_server import framer, PORT
import logging


class Client:

    def __init__(self, reader, writer):
        self._id = 0
        self._reader = reader
        self._writer = writer
        self._rsp_queue = asyncio.Queue()
        self._log = logging.getLogger(__name__)

    def _on_streaming_data(self, data):
        self._log.debug('streaming data')
        t1, p1, data = framer.unpack(data)
        if t1 != framer.TAG_AJS:
            self._log.warning('streaming data does not start with AJS')
            return
        info = framer.ajs_receive(p1)
        for field in info['data']['fields']:
            t, p, data = framer.unpack(data)
            # p contains the binary data for field
            # current, voltage, power are float32

    async def receiver(self):
        while True:
            try:
                tag, payload = await framer.receive(self._reader)
                if tag == framer.TAG_ABN:
                    self._on_streaming_data(payload)
                elif tag == framer.TAG_AJS:
                    msg = framer.ajs_receive(payload)
                    phase = msg.get('phase')
                    if phase == 'rsp':
                        # self._log.info('rsp: %s', msg)
                        await self._rsp_queue.put(msg)
                    elif phase == 'async':
                        self._log.info('async: %s', msg)
                        pass  # todo - handle async messages
                else:
                    self._log.warning('invalid phase %s', phase)
            except asyncio.IncompleteReadError:
                break
            except Exception:
                self._log.exception('handle_client error')
                return

    async def transact(self, type_, **kwargs):
        id_, self._id = self._id, self._id + 1
        req = {'id': id_, 'type': type_, 'phase': 'req'}
        req.update(**kwargs)
        self._log.info('req: %s', req)
        self._writer.write(framer.tpack(req))
        while True:
            rsp = await self._rsp_queue.get()
            if rsp['id'] != id_:
                self._log.warning('response id mismatch: expected %s, received %s',
                                  id_, rsp['id'])
                continue
            if rsp['status'] != 200:
                raise RuntimeError(rsp['status_msg'])
            break
        self._log.info('rsp: %s', rsp)
        return rsp


async def client_test_01():
    reader, writer = await asyncio.open_connection('127.0.0.1', PORT)
    client = Client(reader, writer)
    receiver_task = asyncio.create_task(client.receiver())

    rsp = await client.transact('hello')
    rsp = await client.transact('scan', config='auto')
    if not len(rsp['data']):
        print('Device not found')
        writer.close()
        return
    device = rsp['data'][0]

    rsp = await client.transact('open', device=device)
    rsp = await client.transact('parameters', device=device)
    rsp = await client.transact('parameter_set', device=device, data={'name': 'i_range', 'value': 'off'})
    rsp = await client.transact('parameter_get', device=device, data={'name': 'i_range'})
    rsp = await client.transact('info', device=device)
    rsp = await client.transact('start', device=device, data={'fields': ['current', 'voltage']})
    await asyncio.sleep(3.0)  # receive statistics and streaming data
    rsp = await client.transact('stop', device=device)
    rsp = await client.transact('close', device=device)
    print('Close the socket')
    writer.close()
    await receiver_task


async def client_test_02():
    reader, writer = await asyncio.open_connection('127.0.0.1', PORT)
    client = Client(reader, writer)
    receiver_task = asyncio.create_task(client.receiver())
    rsp = await client.transact('hello')
    await asyncio.sleep(10.0)
    print('Close the socket')
    writer.close()
    await receiver_task


def run():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(client_test_01())
    loop.close()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(asctime)s:%(filename)s:%(lineno)d:%(name)s:%(message)s")
    run()
