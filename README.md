
# Joulescope Server

Welcome to the pyjoulescope_server package!  This package enables Joulescopes
and [pyjoulescope](https://github.com/jetperch/pyjoulescope) to communicate 
over a network and interface with other programming languages using sockets.


## Quick start

Install Python for your platform.  See the 
[installation instructions](https://joulescope.readthedocs.io/en/latest/user/install.html)
for pyjoulescope for details.  Then:

    pip3 install -U joulescope_server

You should then be able to run the server:

    joulescope_server
    
If you would prefer to run directly from the clone git repo:

    python3 -m joulescope_server

To demonstrate the server, you can run the example client from
another terminal:

    python3 -m joulescope_server client


## License

All pyjoulescope_server code is released under the permissive Apache 2.0 license.
See the [License File](LICENSE.txt) for details.
