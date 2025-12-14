from pybricks.iodevices import XboxController
from pybricks.parameters import Button, Direction, Port
from pybricks.pupdevices import Motor
from pybricks.tools import wait

controller = XboxController()

motor_D = Motor(Port.D, Direction.CLOCKWISE)      # motor de la base
motor_F = Motor(Port.F, Direction.CLOCKWISE)     # motor de la muñeca
motor_B = Motor(Port.B, Direction.CLOCKWISE)      # motor del brazo
motor_C = Motor(Port.C, Direction.CLOCKWISE)      # motor de la garra

DEADZONE = 15

while True:

    buttons = controller.buttons.pressed()
    lx, ly = controller.joystick_left()
    rx, ry = controller.joystick_right()
    lt, rt = controller.triggers()

    #Movimiento de la base

    if Button.RB in buttons:
        motor_D.dc(30)
    elif Button.LB in buttons:
        motor_D.dc(-30)
    else:
        motor_D.stop()

    #Movimiento de la muñeca

    if ly > DEADZONE:
        motor_F.dc(60)
    elif ly < -DEADZONE:
        motor_F.dc(-40)
    else:
        motor_F.stop()

    #Movimiento del Brazo

    if ry > DEADZONE:
        motor_B.dc(30)
    elif ry < -DEADZONE:
        motor_B.dc(-30)
    else:
        motor_B.stop()

    #Movimiento de la garra

    if rt > 5:
        motor_C.dc(35)
    elif lt > 5:
        motor_C.dc(-35)
    else:
        motor_C.stop()

    wait(200)
