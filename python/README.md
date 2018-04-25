# PeekPoke

PeekPoke is a utility for reading and writing a Propeller's hub RAM from a PC.
It consists of two parts: a python package for sending commands from the PC, and
a PASM program for responding to commands.

The PASM program is entirely cog-contained after launch. It can be obtained from
the source page at <https://github.com/chris-siedell/PeekPoke>.

A PeekPoke object has these properties:

- `serial_port_name`, e.g. COM1 or /dev/cu.usbserial-XXX
- `address`, the Crow protocol address used by the Propeller, defaults to 1
- `port`, the Crow port used by the PeekPoke service, defaults to 112
- `baudrate`, the local baudrate (see also the `switch_baudrate` and `revert_baudrate` methods)

These are the methods:

- `get_par()`, returns the value of the PAR register used when launching the PeekPoke instance
- `read_hub(hub_address, count)`, reads hub RAM and returns a bytearray
- `write_hub(hub_address, data)`, writes hub RAM
- `atomic_read_hub` and `atomic_write_hub`, like the similarly named methods above, but will not use more than one packet
- `switch_baudrate(baudrate)`, sets both the local and remote baudrates; use the optional `clkfreq` argument 
to specify the Propeller's system clock frequency (recommended), or set the `use_hub_clkfreq` argument to True to use the
first long of hub memory as the clock frequency (second best option), or allow PeekPoke to estimate the clock frequency
using the current baudrate (works, but may introduce errors that grow after multiple switches)
- `revert_baudrate()`, changes the local baudrate back to the last known good value, and sends a break
condition to the Propeller to instruct it to do the same

Example:

```Python
import peekpoke
p = peekpoke.PeekPoke(port_name)
x = p.read_hub(0, 4)
x.hex()
# -> '00b4c404'
int.from_bytes(x, 'little')
# -> 80000000
p.read_hub(20000, 10)
# -> bytearray(b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00')
p.write_hub(20002, b'hello')
p.read_hub(20000, 10)
# -> bytearray(b'\x00\x00hello\x00\x00\x00')
```
