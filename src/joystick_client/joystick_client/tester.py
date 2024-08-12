from linux_joystick import AxisEvent, ButtonEvent, Joystick as JoySimple

def run():
    while True:
        try:
            js = JoySimple(0)
            while True:
                event = js.poll()
                if isinstance(event, AxisEvent):
                    print(f"Axis {event.id} is {event.value}")
                elif isinstance(event, ButtonEvent):

                    print(f"Button {event.id} is {event.value}")
        except Exception as err:
            print(err)
            print("no device")
    

if __name__ == "__main__":
    run()