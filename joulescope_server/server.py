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


"""
This server uses a simple tag-length-value (TLV) method to frame
each message.  The TLV format is:

3 bytes: tag.
1 byte: reserved for payload encoding.
4 bytes: payload length N, but current protocol max is 2**24.
N bytes: payload.
P bytes: 0 pad so next tag starts at multiple of 8 bytes.

The protocol currently defines two tags:

AJS: application-specific JSON format.
ABN: application-specific binary format

The AJS messages contain UTF-8, JSON-formatted data structures.
Each data structure has the following keys:

* type: The message type.
* phase: The message phase, one of [req, rsp, async].
  * req: Client request to the server
  * rsp: Server response to a client request
  * async: Server message generated asynchronously.
* id: The message id used to match rsp with req
* status: For rsp phase, 200 or error code.
* status_msg: For rsp phase, 'Success' or the error message.
* device: The name of the target device returned by "scan".
* data: The data, which is dependent upon type.


The available req/rsp message types are:

hello
scan
open
close
info
parameters
parameter_get
parameter_set
start
stop

The async message types are:

device_notify - Device inserted or removed, issue "scan" for details.
statistics
event
stop
"""


import asyncio
from joulescope_server import framer, PORT, __version__
import logging
import joulescope
from joulescope.usb import DeviceNotify
from joulescope.driver import Device
import weakref


def msg_status(msg, status_code, status_msg):
    msg['status'] = status_code
    msg['status_msg'] = status_msg


def _param_to_dict(p):
    return {
        'name': p.name,
        'default': p.default,
        'path': p.path,
        'options': p.options,
        'units': p.units,
        'brief': p.brief,
        'detail': p.detail,
        'flags': p.flags,
    }


class ClientManager:
    _instances = set()  # weakreaf to instances

    def __init__(self, reader, writer):
        self._devices = []
        self._reader = reader
        self._writer = writer
        self._async_queue = asyncio.Queue()
        self._async_task = asyncio.create_task(self._async_task())
        self._loop = asyncio.get_event_loop()
        self._log = logging.getLogger(__name__)
        ClientManager._instances.add(weakref.ref(self))

    @classmethod
    def cls_handle_device_notify(cls, inserted, info):
        invalid = set()
        for instance in ClientManager._instances:
            c = instance()
            if c is None:
                invalid.add(instance)
            else:
                c.handle_device_notify()
        cls._instances -= invalid

    def handle_device_notify(self):
        self._log.info('_handle_device_notify()')
        msg = {
            'type': 'device_notify',
            'phase': 'async',
        }
        self._async_queue_put_threadsafe(msg)

    def device_get(self, msg) -> Device:
        if 'device' not in msg:
            raise ValueError('device not specified')
        device = msg['device']
        for d in self._devices:
            if str(d) == device:
                return d
        raise ValueError('device not found')

    async def _on_hello(self, msg):
        msg['data'] = {
            'protocol_version': 1,
            'server_version': __version__,
            'joulescope_version': joulescope.__version__,
        }
        return msg

    def _async_queue_put_threadsafe(self, msg):
        self._loop.call_soon_threadsafe(self._async_queue.put_nowait, msg)

    async def _async_task(self):
        self._log.info('_async_task start')
        while True:
            try:
                msg = await self._async_queue.get()
                msg_type = msg['type']
                if msg_type == 'close':
                    break
                msg['phase'] = 'async'
                msg['status'] = 200
                msg['status_msg'] = 'Success'
                self._writer.write(framer.tpack(msg))
            except:
                self._log.exception('_async_task')
        self._log.info('_async_task done')

    async def _on_scan(self, msg):
        config = msg.get('config', 'auto')
        self._devices, _, _ = joulescope.scan_for_changes('joulescope', self._devices, config=config)
        msg['data'] = [str(d) for d in self._devices]
        return msg

    def _statistics_fn(self, device_name, data):
        self._log.info('_statistics_fn %s', device_name)
        msg = {
            'type': 'statistics',
            'phase': 'async',
            'device': device_name,
            'data': data,
        }
        self._async_queue_put_threadsafe(msg)

    def _event_fn(self, device_name, event, message):
        self._log.info('_event_fn %s', device_name)
        msg = {
            'type': 'event',
            'phase': 'async',
            'device': device_name,
            'data': {
                'event': event,
                'message': message,
            },
        }
        self._async_queue_put_threadsafe(msg)

    async def _on_open(self, msg):
        d = self.device_get(msg)
        dname = str(d)
        d.statistics_callback = lambda data: self._statistics_fn(dname, data)
        d.open(lambda event, message: self._event_fn(dname, event, message))
        return msg

    async def _on_close(self, msg):
        d = self.device_get(msg)
        d.close()
        return msg

    async def _on_parameters(self, msg):
        d = self.device_get(msg)
        params = d.parameters()
        msg['data'] = {p.name: _param_to_dict(p) for p in params}
        return msg

    async def _on_parameter_get(self, msg):
        d = self.device_get(msg)
        msg['data'] = d.parameter_get(msg['parameter'])
        return msg

    async def _on_parameter_set(self, msg):
        d = self.device_get(msg)
        d.parameter_get(msg['parameter'], msg['data'])
        return msg

    async def _on_info(self, msg):
        d = self.device_get(msg)
        msg['data'] = d.info()
        return msg

    def _stop_fn(self, device_name, event, message):
        self._log.info('_stop_fn %s', device_name)
        msg = {
            'type': 'stop',
            'phase': 'async',
            'device': device_name,
            'data': {
                'event': event,
                'message': message,
            },
        }
        self._async_queue_put_threadsafe(msg)

    async def _on_start(self, msg):
        d = self.device_get(msg)
        dname = str(d)
        msg['data'] = d.start(lambda event, message: self._stop_fn(dname, event, message))
        return msg

    async def _on_stop(self, msg):
        d = self.device_get(msg)
        msg['data'] = d.stop()
        return msg

    async def _on_unknown(self, msg):
        msg_status(msg, 404, 'Type not found')
        return msg

    async def run(self):
        self._log.info('ClientManager.run start')
        while True:
            try:
                msg = await framer.treceive(self._reader)
                phase = msg.get('phase', 'req')
                if phase != 'req':
                    msg['error'] = f'Invalid phase: {phase}'
                    self._writer.write(msg)
                    continue
                msg['phase'] = 'rsp'
                msg_status(msg, 200, 'Success')
                type_ = msg.get('type', None)
                # automatically bind type to method by name
                method_name = f'_on_{type_}'
                fn = getattr(self, method_name, self._on_unknown)
                try:
                    msg = await fn(msg)
                except Exception as ex:
                    self._log.exception(f'fn type {type_}')
                    msg_status(msg, 500, 'Error')
                if msg is not None:
                    self._writer.write(framer.tpack(msg))
            except asyncio.IncompleteReadError:
                self._log.info('Client closed socket')
                break
            except:
                self._log.exception('handle_client error')
                break
        await self._writer.drain()
        self._writer.close()
        await self._async_queue.put({'type': 'close'})
        await self._async_task
        self._log.info('ClientManager.run done')


async def handle_client(reader, writer):
    mgr = ClientManager(reader, writer)
    await mgr.run()


def run():
    loop = asyncio.get_event_loop()
    coro = asyncio.start_server(handle_client, '127.0.0.1', PORT, loop=loop)
    server = loop.run_until_complete(coro)

    # Serve requests until Ctrl+C is pressed
    print('Serving on {}'.format(server.sockets[0].getsockname()))
    device_notify = DeviceNotify(ClientManager.cls_handle_device_notify)
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    device_notify.close()

    # Close the server
    server.close()
    loop.run_until_complete(server.wait_closed())
    loop.close()


if __name__ == '__main__':
    logging.basicConfig()
    run()
