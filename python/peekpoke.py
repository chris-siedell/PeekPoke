
class PeekPokeError(RuntimeError):
    pass

class PeekPoke():

    
    def __init__(self):
        self.host = None

        self.address = 1
        self.port = 112
        self.propcr_order = True

        self.max_read = 400
        self.max_write = 400


    def _check_twobyte(self, value, name):
        if value < 0 or value > 65535:
            raise ValueError(name + ' must be in the range [0, 65535]')


    def _check_longaligned_twobyte(self, value, name):
        if value < 0 or value > 65532 or value%4 != 0:
            raise ValueError(name + ' must be in the range [0, 65532] and divisible by four')


    def read_hub(self, address, count):

        self._check_twobyte(address, 'address')

        if count < 0 or count > 65536:
            raise ValueError("count must be in the range [0, 65536].")

        result = bytearray()

        while count > 0:
            atomic_count = min(count, self.max_read)
            count -= atomic_count
            result += self._atomic_read_hub(address, atomic_count)
            address = (address + atomic_count)%65536
        
        return result


    def _atomic_read_hub(self, address, count):
        
        # todo: try command again for UnrecognizedCommand, toggling propcr_order

        self._check_twobyte(address, 'address')

        if count < 0 or count > 65536:
            raise ValueError("count must be in the range [0, 65536].")

        arguments = address.to_bytes(2, 'little') + count.to_bytes(2, 'little')
        payload = self._send_command(1, 4 + count, arguments)

        return payload[4:]


    def write_hub(self, address, data):

        self._check_twobyte(address, 'address')

        count = len(data)

        if count > 65536:
            raise ValueError('the amount of data must not exceed 65536 bytes')

        index = 0

        while count > 0:
            atomic_count = min(count, self.max_write)
            count -= atomic_count
            self._atomic_write_hub(address, data[index:index+atomic_count])
            address = (address + atomic_count)%65536
            index += atomic_count


    def _atomic_write_hub(self, address, data):

        self._check_twobyte(address, 'address')

        count = len(data)

        if count > 65536:
            raise ValueError('the amount of data must not exceed 65536 bytes')

        arguments = address.to_bytes(2, 'little') + (len(data)).to_bytes(2, 'little') + data
        self._send_command(2, 4, arguments)


    def payload_exec(self, code):
        return self._send_command(3, arguments=code)



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

    def get_basic_info(self):
        
        payload = self._send_command(0, 8)
        
        info = {}
        info['par'] = int.from_bytes(payload[4:6], 'little')
        info['read_hub_available'] = bool(payload[6] & 0b0010)
        info['write_hub_available'] = bool(payload[6] & 0b0100)
        info['payload_exec_available'] = bool(payload[6] & 0b1000)
        info['cog_id'] = payload[7]
        return info


    def _send_command(self, code, expected_rsp_size=None, arguments=None):

        if self.host is None:
            raise RuntimeError("The host property must be defined to send PeekPoke commands.")

        command = bytearray(b'\x70\x70') + code.to_bytes(2, 'little')
        if arguments is not None:
            command += arguments

        response = self.host.send_command(address=self.address, port=self.port, payload=command, propcr_order=self.propcr_order)

        if len(response) < 4:
            raise PeekPokeError("The response has fewer than four bytes.")
        if response[0] != 0x70 or response[1] != 0x70:
            raise PeekPokeError("The response identifier is incorrect.")
        if response[2] != code:
            raise PeekPokeError("The response code is incorrect.")
        if response[3] == 1:
            raise PeekPokeError("The command is not available on the device.")
        if response[3] == 2:
            raise PeekPokeError("The device reports that the command had missing parameters.")
        if response[3] == 3:
            raise PeekPokeError("The requested response would be too large for the device.")
        if response[3] > 3:
            raise PeekPokeError("The device returned an unknown error code (" + str(response[3]) + ").")
        if expected_rsp_size is not None:
            if len(response) != expected_rsp_size:
                raise PeekPokeError("The response does not have the expected size.")
            
        return response

