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


from joulescope_server.server import run as run_server
from joulescope_server.client import run as run_client
import argparse
import logging


def _run_server(p):
    return run_server()


def _run_client(p):
    return run_client()


def get_parser():
    """Run the ."""
    parser = argparse.ArgumentParser(description='Joulescope socket server and client')
    parser.set_defaults(func=_run_server)

    s = parser.add_subparsers(title='command', help='sub-command help')

    p = s.add_parser('server', help='Run the server')
    p.set_defaults(func=_run_server)

    p = s.add_parser('client', help='Run the client')
    p.set_defaults(func=_run_client)

    return parser


def run():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(asctime)s:%(filename)s:%(lineno)d:%(name)s:%(message)s")
    p = get_parser()
    args = p.parse_args()
    return args.func(args)


if __name__ == '__main__':
    run()
