Links:
- Python Documentation: https://github.com/chris-siedell/PeekPoke/wiki/PeekPoke-Python-Documentation/
- Spin Documentation: https://github.com/chris-siedell/PeekPoke/wiki/PeekPoke-Spin-Documentation/
- pip command: `pip install peekpoke` or `pip3 install peekpoke`
- On PyPI: https://pypi.org/project/peekpoke/
- Project Homepage: http://siedell.com/projects/PeekPoke/

# PeekPoke
Status: _experimental_

PeekPoke is a tool for reading and writing a Propeller's hub memory from a PC. It consists of two parts: a Python module for sending commands from the PC, and a Propeller program for responding to commands.

The Python module has methods to read and write hub memory as bytes, strings, integers, and lists of integers.

The Propeller program can be configured to restrict reads and writes to specific ranges, or to disable writes altogether.

PeekPoke has these additional features:
- the PAR register may be used to pass a value to the PC,
- the PC can set the baudrate remotely,
- the PC can reset the baudrate with a break condition,
- the Propeller can support baudrates as fast as 26 clocks per bit period,
- there is a four-byte `identifier` constant that can read by the PC,
- a four-byte `token` variable is 0 on launch and can be set by the PC,
- the PC can send PASM code to be executed (disabled by default),
- the Propeller program is completely cog-contained after launch.

## Installation

PeekPoke requires Python 3. It can be installed with the command `pip install peekpoke` (or `pip3 install peekpoke`). Alternatively, the package may be downloaded from <https://pypi.org/project/peekpoke/>. PeekPoke also requires the <https://pypi.org/project/crow-serial/> and <https://pypi.org/project/pyserial/> packages (pip automatically handles these dependencies).

To run PeekPoke on the Propeller include `PeekPoke.spin`  in your project, and use the Spin methods to set up and launch a PeekPoke instance. The latest version of `PeekPoke.spin` can be found at <https://github.com/chris-siedell/PeekPoke>.

## Documentation

Python: https://github.com/chris-siedell/PeekPoke/wiki/PeekPoke-Python-Documentation

Spin: https://github.com/chris-siedell/PeekPoke/wiki/PeekPoke-Spin-Documentation

