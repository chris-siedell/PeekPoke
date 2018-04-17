
import serial
import random
import sys
import hubsim
import peekpoke
from crow import crowhost


if len(sys.argv) < 2:
    sys.exit('Please provide the serial port name as a command line argument.')

s = serial.Serial(sys.argv[1])
s.baudrate = 460800

h = crowhost.CrowHost()
h.serial = s

p = peekpoke.PeekPoke()
p.host = h
p.address = 10

# this is a short pasm program to make the pin corresponding to the cog id (0-7)
#  a high output (the program sleeps forever after setting up the pin)
with open('cogidOutput.dat', mode='rb') as f:
    cogid_test_program = f.read()

# this is a short pasm program to make the pin corresponding to par (bits 2-6)
#  a high output (the program sleeps forever after setting up the pin)
with open('parOutput.dat', mode='rb') as f:
    par_test_program = f.read()

cogid_test_address = 20000
par_test_address = 22000

p.write_hub(cogid_test_address, cogid_test_program)
p.write_hub(par_test_address, par_test_program)

basic_info = p.get_basic_info()

# after initialization we should have:
#  cog 0 - original spin launching cog
#  cog 1 - peekpoke
#  cog 2 - blinky program (blinks pin 26 quickly)

p.cognew(cogid_test_address) # should use cog 3, and make pin 3 high
p.cognew(cogid_test_address) # should use cog 4, and make pin 4 high
p.cognew(cogid_test_address) # should use cog 5, and make pin 5 high

# this will surplant the program already in cog 0 -- the original
#  initializing spin code which was holding pin 27 steady high
# it should make pin 7 a steady output
p.coginit(0, par_test_address, 28)  # 28 = pin 7

# this should turn off the cog blinking pin 26
p.cogstop(2)

sim = hubsim.HubSim()
rom = p.read_hub(32768, 32768)
sim.set_rom(rom)
u = sim.read(32767, 3)

def random_address():
    return random.randint(0, 65535)



def verify_full_hub(test_label):
    # pick a random location to start (shouldn't matter)
    addr = random_address()
    full_prop = p.read_hub(addr, 65536)
    full_sim = sim.read(addr, 65536)
    if full_prop != full_sim:
        for ind in range(0, 65536):
            if full_prop[ind] != full_sim[ind]:
                break
        u = sim.read(32767, 3)
        raise RuntimeError('Full hub verification failed at index ' + str(ind) + ' (address ' + str((addr+ind)%65535) + '). Reported value: ' + str(full_prop[ind]) + ', sim value: ' + str(full_sim[ind]) + '. ' + test_label)


def test1():
    name = "Test 1: Hub Fill 256x"
    # Procedure:
    #   - create a list of the bytes 0x00 to 0xff in random order
    #   - for each byte:
    #     - fill an entire 65k bytearray with that byte
    #     - pick a random hub address
    #     - write the 65k bytearray starting at that address
    #     - call verify_full_hub
    test_values = random.sample(range(0, 256), 256)
    for value in test_values:
        filled65k = bytearray(65536)
        for ind in range(0, 65536):
            filled65k[ind] = value
        address = random_address()
        p.write_hub(address, filled65k)
        sim.write(address, filled65k)
        verify_full_hub(name + ', byte: ' + hex(value) + '.')
    print('Passed -- ' + name)

test1()

print("All tests passed.")






