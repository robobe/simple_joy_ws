# from rome_client.utils import Singleton
import argparse
import json
import logging
import os
import time
from dataclasses import dataclass
from threading import Thread
from typing import List

import zenoh
from linux_joystick import AxisEvent, ButtonEvent
from linux_joystick import Joystick as JoySimple
from pycdr2 import IdlStruct
from pycdr2.types import array, float32, float64, int8, int32, uint8, uint32

from joystick_interface.msg import Joystick

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


@dataclass
class JoystickData(IdlStruct, typename="JoystickData"):
    axes: List[int8]
    buttons: List[int8]


class ZenohBackend:
    def __init__(self, ip, port) -> None:
        self.cfg = zenoh.Config.from_obj(self.build_config(ip, port))
        self.__session = None

    def build_config(self, ip, port):
        log.info(f"Try connect to server: {ip}:{port}")
        config_dict = {
            "mode": "client",
            "connect": {"endpoints": ["udp/{}:{}".format(ip, port)]},
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
                log.error(
                    "zenoh session open failed try again", exc_info=True
                )
                time.sleep(2)

    def pub(self, joy_state: JoystickData):
        self.__session.put("joystick", joy_state.serialize())

    @property
    def session(self):
        return self.__session


class JoystickManager:
    def __init__(self, cb, mapping):
        self.joy_state = JoystickData(axes=[0] * 8, buttons=[0] * 16)
        self.notify_thread = Thread(
            target=self.__notify, daemon=True, name="joy_notify"
        )
        self.notify_thread.start()
        self.notify = cb
        self.__mapping = self.__load_mapping(mapping)

    def __load_mapping(self, mapping):
        file_path = os.path.dirname(__file__)
        file_path = os.path.join(file_path, mapping + ".json")
        if not os.path.exists(file_path):
            log.error(f"joystick mapping not found: {mapping}")
        with open(file_path, "r") as f:
            data = json.load(f)
        return data

    def __resolve_mapping(self, type, id):
        id = str(id)
        if id not in self.__mapping[type]:
            raise Exception("Mapping not found")
        return self.__mapping[type][id]

    def map_axis(self, axis_value):
        value = axis_value / AxisEvent.MAX_AXIS_VALUE * Joystick.AXIS_MAX
        return int(value)

    def __notify(self):
        while True:
            time.sleep(1 / 10)
            self.notify(self.joy_state)

    def run(self):
        while True:
            try:
                js = JoySimple(0)
                while True:
                    event = js.poll()
                    if isinstance(event, AxisEvent):
                        value = self.map_axis(event.value)
                        id = self.__resolve_mapping("axes", event.id)
                        self.joy_state.axes[id] = value
                        # print(f"Axis {event.id} is {event.value}")
                    elif isinstance(event, ButtonEvent):
                        id = self.__resolve_mapping("buttons", event.id)
                        self.joy_state.buttons[id] = int(event.value)
                        print(id, int(event.value))
                        # print(f"Button {event.id} is {event.value}")
            except Exception as err:
                log.error(err)
                log.error("no device")
                time.sleep(1 / 2)


if __name__ == "__main__":
    log.info("simple joy :)")
    parser = argparse.ArgumentParser(description="joy client zenoh connect settings")
    parser.add_argument(
        "--server_ip",
        default="172.17.0.1",
        type=str,
        help="server address",
        required=False,
    )
    parser.add_argument(
        "--port", default=35407, type=int, help="server port", required=False
    )
    parser.add_argument(
        "--joy_type",
        default="logitech-extreme-3d",
        help="logitech-xbox, logitech-extreme-3d",
    )
    args = parser.parse_args()

    z = ZenohBackend(args.server_ip, args.port)
    z.open()
    joy_manager = JoystickManager(cb=z.pub, mapping=args.joy_type)
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
