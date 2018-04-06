

class HubSim():


    def __init__(self):
        self._hub = bytearray(65536)


    def read(self, addr, count):

        if addr < 0 or addr > 65535:
            raise RuntimeError('read address must be in the range [0, 65535]')

        if count < 0 or count > 65536:
            raise RuntimeError('number of requested bytes must be in range [0, 65536]')
       
        # there are potentially two parts to the result: up to the address limit, and then the wraparound 

        result = bytearray()

        start_count = min(count, 65536-addr)

        result = self._hub[addr:addr+start_count]

        if start_count != count:
            result += self._hub[0:count-start_count]

        return result
        
        
    def write(self, addr, data):

        if addr < 0 or addr > 65535:
            raise RuntimeError('write address must be in the range [0, 65535]')

        count = len(data)
        
        if count > 65536:
            raise RuntimeError('too much data passed to write (requires 65536 or fewer bytes)')

        if addr < 32768:
            # starts in ram
            
            ram_start_count = min(count, 32768-addr)
            self._hub[addr:addr+ram_start_count] = data[0:ram_start_count]

            wraparound_count = count - ram_start_count - 32768

            if wraparound_count > 0:
                data_wraparound = ram_start_count + 32768
                self._hub[0:wraparound_count] = data[data_wraparound:data_wraparound+wraparound_count]

        else:
            # starts in rom

            rom_start_count = min(count, 65536-addr)

            wraparound_count = min(count - rom_start_count, 32768)

            if wraparound_count > 0:
                data_wraparound = rom_start_count
                self._hub[0:wraparound_count] = data[data_wraparound:data_wraparound+wraparound_count]



    def set_rom(self, rom):

        if len(rom) != 32768:
            raise RuntimeError('set_rom requires exactly 32768 bytes')

        self._hub[32768:65536] = rom
    
