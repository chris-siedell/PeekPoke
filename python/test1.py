
import serial
import sys
from crow import crowhost
import peekpoke

if len(sys.argv) < 2:
    sys.exit('Please provide the serial port name as a command line argument.')

s = serial.Serial(sys.argv[1])
s.baudrate = 115200

h = crowhost.CrowHost()
h.serial = s

p = peekpoke.PeekPoke()
p.host = h

info = p.get_basic_info()

print(info)

info = p.cogstop(11)

print(info)


test = b'Hello there!'

x = p.read_hub(0, 4)
print("clkfreq: " + str(int.from_bytes(x[0:4], 'little')))
print(len(x))

p.write_hub(20001, test)

x = p.read_hub(19999, 20)
print("at 20000: " + str(x))



