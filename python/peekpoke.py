
class PeekPokeError(RuntimeError):
    pass

class PeekPoke():

    
    def __init__(self):
        self.host = None

        self.address = 1
        self.port = 112
        self.propcr_order = True

        self._max_atomic_read = 260
        self._max_atomic_write = 256

        self._break_duration_ms = 400


    def _check_twobyte(self, value, name):
        if value < 0 or value > 65535:
            raise ValueError(name + ' must be in the range [0, 65535]')


    def _check_longaligned_twobyte(self, value, name):
        if value < 0 or value > 65532 or value%4 != 0:
            raise ValueError(name + ' must be in the range [0, 65532] and divisible by four')


    def get_par(self):
        response = self._send_command(0, 6)
        return int.from_bytes(response[4:6], 'little')


    def read_hub(self, address, count):

        self._check_twobyte(address, 'address')

        if count < 0 or count > 65536:
            raise ValueError("count must be in the range [0, 65536].")

        result = bytearray()

        while count > 0:
            atomic_count = min(count, self._max_atomic_read)
            count -= atomic_count
            result += self._atomic_read_hub(address, atomic_count)
            address = (address + atomic_count)%65536
        
        return result


    def _atomic_read_hub(self, address, count):
        
        self._check_twobyte(address, 'address')

        if count < 0 or count > self._max_atomic_read:
            raise ValueError("Atomic hub reads may not exceed " + str(self._max_atomic_read) + " bytes.")

        arguments = address.to_bytes(2, 'little') + count.to_bytes(2, 'little')
        payload = self._send_command(1, 4 + count, arguments)

        return payload[4:]


    def write_hub(self, address, data):

        self._check_twobyte(address, 'address')

        count = len(data)

        if count > 65536:
            raise ValueError('Writes can not exceed 65536 bytes.')

        index = 0

        while count > 0:
            atomic_count = min(count, self._max_atomic_write)
            count -= atomic_count
            self._atomic_write_hub(address, data[index:index+atomic_count])
            address = (address + atomic_count)%65536
            index += atomic_count


    def _atomic_write_hub(self, address, data):

        self._check_twobyte(address, 'address')

        count = len(data)

        if count > self._max_atomic_write:
            raise ValueError("Atomic hub writes may not exceed " + str(self._max_atomic_write) + " bytes.")

        arguments = address.to_bytes(2, 'little') + (len(data)).to_bytes(2, 'little') + data
        self._send_command(2, 4, arguments)


    def get_baudrate(self):
        return self.host.serial.baudrate


    def set_baudrate(self, baudrate, clkfreq=None):
        curr_baudrate = self.host.serial.baudrate
        if curr_baudrate == baudrate:
            return
        if clkfreq is None:
            # When clkfreq is inferred from the current timings it introduces errors that
            # may be amplified when multiple baudrate changes are made. One solution would
            # be to maintain a table of known good timings for each baudrate so they would
            # not need to be recalculated, but the table would only exist for the life
            # of the python PeekPoke object, unless stored on the device in the StaticBuffer.
            # Another solution is to ask the user to provide clkfreq.
            timings = self._get_serial_timings()
            clkfreq = ((timings['bit_period_0'] + timings['bit_period_1']) * curr_baudrate) / 2
        timings = {}
        two_bit_period = int((2 * clkfreq) / baudrate)
        if two_bit_period < 52:
            raise ValueError("The baudrate " + str(baudrate) + " can not be supported by the device given a clkfreq of " + str(clkfreq) + ".")
        timings['bit_period_0'] = two_bit_period >> 1
        timings['bit_period_1'] = timings['bit_period_0'] + (two_bit_period & 1)
        timings['start_bit_wait'] = max((timings['bit_period_0'] >> 1) - 10, 5)
        timings['stop_bit_duration'] = int((10*clkfreq) / baudrate) - 5*timings['bit_period_0'] - 4*timings['bit_period_1'] + 1
        timings['interbyte_timeout'] = max(int(clkfreq/1000), two_bit_period)    # max of 1ms or 2 bit periods
        timings['recovery_time'] = two_bit_period << 3                      # 16 bit periods
        # For the break multiple, we use 1/2 of self._break_duration_ms for dependable detection.
        timings['break_multiple'] = int((self._break_duration_ms * clkfreq/2000) / timings['recovery_time'])
        self._set_serial_timings(timings)
        self.host.serial.baudrate = baudrate


    def _get_serial_timings(self):

        response = self._send_command(3, 32)

        timings = {}
        timings['bit_period_0'] = int.from_bytes(response[4:8], 'little')
        timings['bit_period_1'] = int.from_bytes(response[8:12], 'little')
        timings['start_bit_wait'] = int.from_bytes(response[12:16], 'little')
        timings['stop_bit_duration'] = int.from_bytes(response[16:20], 'little')
        timings['interbyte_timeout'] = int.from_bytes(response[20:24], 'little')
        timings['recovery_time'] = int.from_bytes(response[24:28], 'little')
        timings['break_multiple'] = int.from_bytes(response[28:32], 'little')
        return timings


    def _set_serial_timings(self, timings):

        arguments = bytearray()
        arguments += timings['bit_period_0'].to_bytes(4, 'little')
        arguments += timings['bit_period_1'].to_bytes(4, 'little')
        arguments += timings['start_bit_wait'].to_bytes(4, 'little')
        arguments += timings['stop_bit_duration'].to_bytes(4, 'little')
        arguments += timings['interbyte_timeout'].to_bytes(4, 'little')
        arguments += timings['recovery_time'].to_bytes(4, 'little')
        arguments += timings['break_multiple'].to_bytes(4, 'little')

        self._send_command(4, 4, arguments)


    def payload_exec(self, code):

        if len(code) < 4:
            raise ValueError("There must be at least 4 bytes of code for payload_exec.")

        return self._send_command(5, arguments=code)



#    def _pasm_coginit(self, any_cog, cog_id, asm_addr, par):
#        
#        if cog_id < 0 or cog_id > 7:
#            raise ValueError('cog_id must be in the range [0, 7]')
#
#        if asm_addr < 0 or asm_addr > 65532 or asm_addr%4 != 0:
#            raise ValueError('asm_addr must be in the range [0, 65532] and divisible by four')
#
#        if par < 0 or par > 65532 or par%4 != 0:
#            raise ValueError('par must be in the range [0, 65532] and divisible by four')
#        
#        # refer to coginit entry in the assembly language reference (table 3-1 in manual v1.2)
#        any_flag = 0b1000 if any_cog else 0b0000
#        arg_int = par << 16 | asm_addr << 2 | any_flag | cog_id
#        arg = arg_int.to_bytes(4, 'little')
#
#        return self._send_command(0x03, 5, arguments=arg)
#
#
#    def coginit(self, cog_id, asm_addr, par=0):
#
#        payload = self._pasm_coginit(False, cog_id, asm_addr, par)
#
#        info = {}
#        info['no_cog_available'] = bool(payload[4] & 0x80)
#        if payload[4] & 0x40:
#            payload[4] |= 0x80
#        else:
#            payload[4] &= 0x7f
#        info['cog_id_would_have_used'] = payload[4]
#        return info
#
#
#    def cognew(self, asm_addr, par=0):
#
#        payload = self._pasm_coginit(True, 3, asm_addr, par)
#
#        info = {}
#        info['no_cog_available'] = bool(payload[4] & 0x80)
#        if payload[4] & 0x40:
#            payload[4] |= 0x80
#        else:
#            payload[4] &= 0x7f
#        info['cog_id'] = payload[4]
#        return info
#
#
#    def cogstop(self, cog_id):
#
#        payload = self._send_command(0x23, 5, arguments=cog_id.to_bytes(1, 'little'))
#        
#        info = {}
#        info['all_running'] = bool(payload[4] & 0x80)
#        if payload[4] & 0x40:
#            payload[4] |= 0x80
#        else:
#            payload[4] &= 0x7f
#        info['cog_id'] = payload[4]
#        return info
#



    def _send_command(self, code, expected_rsp_size=None, arguments=None):

        if self.host is None:
            raise RuntimeError("The host property must be defined to send PeekPoke commands.")

        command = bytearray(b'\x70\x70\x00') + code.to_bytes(1, 'little')
        if arguments is not None:
            command += arguments

        response = self.host.send_command(address=self.address, port=self.port, payload=command, propcr_order=self.propcr_order)

        if len(response) < 4:
            raise PeekPokeError("The response has fewer than four bytes.")
        if response[0] != 0x70 or response[1] != 0x70:
            raise PeekPokeError("The response identifier is incorrect.")
        if response[3] != code:
            raise PeekPokeError("The response code is incorrect.")
        if response[2] == 1:
            raise PeekPokeError("The command is not available on the device.")
        if response[2] == 2:
            raise PeekPokeError("The command did not have the correct size.")
        if response[2] == 3:
            raise PeekPokeError("The requested response would be too large for the device.")
        if response[2] > 3:
            raise PeekPokeError("The device returned an unknown error code (" + str(response[2]) + ").")
        if expected_rsp_size is not None:
            if len(response) != expected_rsp_size:
                raise PeekPokeError("The response does not have the expected size.")
            
        return response

