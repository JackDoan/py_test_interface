import logging
import socketserver
from typing import Any

from hm305.server_commands import CommandFactory, SetVoltageCommand, SetVoltageSetpointCommand, VoltageApplyCommand


class HM305pSerialQueueItem:
    def __init__(self, cmd):
        self.stale = False
        self.cmd = cmd
        self.result = None


class HM305pServer(socketserver.StreamRequestHandler):
    most_recent_voltage_cmd = None
    serial_q = None
    fast_q = None
    command_factory = CommandFactory()

    def __init__(self, request: Any, client_address: Any, base_server: socketserver.BaseServer):
        super().__init__(request, client_address, base_server)

    def handle(self):
        resp = ''
        msg = self.rfile.readline().strip().decode()
        logging.debug(f"REQ[{self.client_address[0]}]: {msg}")
        item = self.command_factory.parse(msg)
        if isinstance(item, SetVoltageCommand):
            logging.debug(f"processing {item} special case")
            setpt = SetVoltageSetpointCommand(item.arg)
            apply = VoltageApplyCommand()
            apply.stale |= setpt.stale  # pull this in to handle poorly formatted floats
            HM305pServer.fast_q.put(setpt)
            HM305pServer.fast_q.join()
            HM305pServer.serial_q.put(apply)
            resp = setpt.result_as_string()
        elif item is not None:
            if item.uses_serial_port:
                logging.debug(f"enqueing {item} in the serial queue")
                q = HM305pServer.serial_q
            else:
                logging.debug(f"enqueing {item} in the fast queue")
                q = HM305pServer.fast_q
            q.put(item)
            if item.wait_for_result:
                logging.debug(f"waiting on {item}")
                q.join()
                resp = item.result_as_string()
                logging.debug(f"{item}.result: {item.result}")
            else:
                resp = 'DONE\n'

        else:
            resp = 'error: cmd not found'
        self.wfile.write(resp.encode())