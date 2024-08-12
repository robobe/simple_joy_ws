# from rome_client.utils import Singleton
import zenoh
import logging
from typing import List
import time
from threading import Thread
from linux_joystick import AxisEvent, ButtonEvent, Joystick as JoySimple
from pycdr2 import IdlStruct
from pycdr2.types import int8, int32, uint32, float64, float32, uint8, array
from dataclasses import dataclass
from joystick_interface.msg import Joystick 
import argparse
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


@dataclass
class JoystickData(IdlStruct, typename="JoystickData"):
    axes: List[int8]
    buttons: List[int8]

class ZenohBackend():
    def __init__(self, ip, port) -> None:
        self.cfg = zenoh.Config.from_obj(self.build_config(ip, port))
        self.__session = None

    def build_config(self, ip, port):
        log.info(f"Try connect to server: {ip}:{port}")
        config_dict = {
            "mode": "client",
            "connect": {
                "endpoints": ["udp/{}:{}".format(ip, port)]
            }
        }
        return config_dict
    
    def open(self):
        while True:
            try:
                log.info("try open zenoh session")
                self.__session = zenoh.open(self.cfg)
                log.info("Zenoh session created")
                break
            except Exception:
                log.error("zenoh session open failed try again", exc_info=True)
                time.sleep(2)


    def pub(self, joy_state: JoystickData):
        self.__session.put("joystick", joy_state.serialize())


    @property
    def session(self):
        return self.__session
    

class JoystickManager():
    def __init__(self, cb):
        self.joy_state = JoystickData(axes=[0]*8, buttons=[0]*16)
        self.notify_thread = Thread(target=self.__notify, daemon=True, name="joy_notify")
        self.notify_thread.start()
        self.notify = cb

    def map_axis(self, axis_value):
        value = axis_value / AxisEvent.MAX_AXIS_VALUE * Joystick.AXIS_MAX
        return int(value)

    def __notify(self):
        while True:
            time.sleep(1/10)
            self.notify(self.joy_state)

    def run(self):
        while True:
            try:
                js = JoySimple(0)
                while True:
                    event = js.poll()
                    if isinstance(event, AxisEvent):
                        value = self.map_axis(event.value)
                        self.joy_state.axes[event.id] = value
                        # print(f"Axis {event.id} is {event.value}")
                    elif isinstance(event, ButtonEvent):
                        self.joy_state.buttons[event.id] = int(event.value)
                        # print(f"Button {event.id} is {event.value}")
            except Exception as err:
                log.error(err)
                log.error("no device")
                time.sleep(1/2)

if __name__ == "__main__":
    log.info("simple joy :)")
    parser=argparse.ArgumentParser(description="joy client zenoh connect settings")
    parser.add_argument("--server_ip", default="172.17.0.1", type=str, help="server address", required=False)
    parser.add_argument("--port", default=35407, type=int, help="server port", required=False)
    args = parser.parse_args()

    z = ZenohBackend(args.server_ip, args.port)
    z.open()
    joy_manager = JoystickManager(cb=z.pub)
    joy_manager.run()
    
    # p = z.create_publisher("joystick")
    # buf = Joystick([0]*8, [0]*8)
    # counter = 1
    # while True:
    #     buf.buttons[2] = counter
    #     z.session.put("joystick", buf.serialize())
    #     counter+=1
    #     time.sleep(1)
    #     print(counter)
