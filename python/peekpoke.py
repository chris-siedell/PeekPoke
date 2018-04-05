
import serial
import sys
from crow import crowhost


if len(sys.argv) < 2:
    sys.exit("Please provide the serial port name as a command line argument.")


s = serial.Serial(sys.argv[1])
s.baudrate = 115200

host = crowhost.CrowHost()
host.serial = s

class PeekPoke():

    def __init__(self):
        self.host = None

        self.address = 7
        self.port = 0xafaf
        self.propcr_order = True

    def cog_init(self):
        pass

    def cog_stop(self, id):
        pass

    def get_basic_info(self):
       
        payload = self._send_command(0x00)
        if len(payload) < 12:
            raise RuntimeError("Response is too short.")
        info = {}
        info['par'] = int.from_bytes(payload[4:6], 'little')
        info['cog_id'] = payload[6]
        info['available_groups'] = int.from_bytes(payload[8:12], 'little')
        return info

    def _send_command(self, code, arguments=None):

        if self.host is None:
            raise RuntimeError("The crow host must be defined to send peek poke commands.")

        payload = bytearray(b'\x50\x70') + code.to_bytes(2, 'little')
        if arguments is not None:
            payload += arguments
        print("payload " + payload.hex())
        results = self.host.send_command(address=self.address, port=self.port, payload=payload, propcr_order=self.propcr_order)

        # find the final response packet
        for item in results:
            if item['type'] == 'response':
                if item['is_final']:
                    payload = item['payload']
                    if len(payload) >= 4:
                        if payload[0] == 0x50 and payload[1] == 0x70:
                            response_code = int.from_bytes(payload[2:4], 'little')
                            if response_code == code:
                                # correct response start
                                return payload
                            elif responseCode == code | 0x8000:
                                # possible error response
                                if len(payload) >= 5:
                                    raise RuntimeError("Remote error number " + str(payload[4]))
                    raise RuntimeError("Invalid response format.")
                else:
                    raise RuntimeError("Unexpected intermediate response.")
        raise RuntimeError("Did not receive expected response.")


p = PeekPoke()
p.host = host

info = p.get_basic_info()

print(info)
