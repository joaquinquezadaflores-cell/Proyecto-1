from pybricks.iodevices import XboxController
from pybricks.parameters import Button, Direction, Port
from pybricks.pupdevices import Motor
from pybricks.tools import wait

controller = XboxController()

motor_D = Motor(Port.D, Direction.CLOCKWISE)      # RB / LB
motor_F = Motor(Port.F, Direction.CLOCKWISE)      # Stick izquierdo
motor_B = Motor(Port.B, Direction.CLOCKWISE)      # Stick derecho
motor_C = Motor(Port.C, Direction.CLOCKWISE)      # Gatillos

DEADZONE = 15
potencia = 60
hola = -40
while True:
    buttons = controller.buttons.pressed()
    lx, ly = controller.joystick_left()
    rx, ry = controller.joystick_right()
    lt, rt = controller.triggers()

    print("Buttons:", buttons)         # lista de botones reconocidos
    print("Left stick:", (lx, ly))
    print("Right stick:", (rx, ry))
    print("Triggers (LT,RT):", (lt, rt))
    print("----")
    # --- BOTONES RB / LB ---
    buttons = controller.buttons.pressed()

    if Button.RB in buttons:
        motor_D.dc(30)
    elif Button.LB in buttons:
        motor_D.dc(-30)
    else:
        motor_D.stop()

    # --- STICK IZQUIERDO (motor F) ---
    lx, ly = controller.joystick_left()

    if ly > DEADZONE:
        motor_F.dc(potencia)
        print(f"potencia: {potencia}")
    elif ly < -DEADZONE:
        motor_F.dc(hola)
        print(f"-potencia: {hola}")
    else:
        motor_F.stop()

    # --- STICK DERECHO (motor B) ---
    rx, ry = controller.joystick_right()

    if ry > DEADZONE:
        motor_B.dc(30)
    elif ry < -DEADZONE:
        motor_B.dc(-30)
    else:
        motor_B.stop()

    # --- GATILLOS RT / LT (motor C) ---
    lt, rt = controller.triggers()

    if rt > 5:
        motor_C.dc(35)
    elif lt > 5:
        motor_C.dc(-35)
    else:
        motor_C.stop()

    wait(200)
