import json
import time
from pyfirmata import Arduino, SERVO

board = None
pinBase = None
pinHorizontal = None
pinVertical = None
pinGarra = None

atual_base = 0
atual_horizontal = 0
atual_vertical = 0
atual_garra = 0


def _load_config():
    with open("dados.json", "r", encoding="utf-8") as jsondados:
        dados = json.load(jsondados)

    if not dados or not isinstance(dados, list):
        raise ValueError("dados.json deve conter uma lista com configuração do servo")

    config = dados[0]

    global pinBase, pinHorizontal, pinVertical, pinGarra
    pinBase = config["pin-base"]
    pinHorizontal = config["pin-horizontal"]
    pinVertical = config["pin-vertical"]
    pinGarra = config["pin-garra"]

    return config.get("porta-com", "COM3")


def _ensure_board():
    global board
    if board is not None:
        return

    porta_com = _load_config()
    board = Arduino(porta_com)
    board.digital[pinBase].mode = SERVO
    board.digital[pinHorizontal].mode = SERVO
    board.digital[pinVertical].mode = SERVO
    board.digital[pinGarra].mode = SERVO
    time.sleep(1)


def _clamp_angle(angle):
    return max(0, min(180, int(angle)))


def rotateServo(pin, angle):
    _ensure_board()
    board.digital[pin].write(_clamp_angle(angle))
    time.sleep(0.03)


def _move_servo(pin, current, target):
    target = _clamp_angle(target)
    if current == target:
        return

    _ensure_board()
    step = 1 if target > current else -1

    for angle in range(current, target, step):
        board.digital[pin].write(angle)
        time.sleep(0.03)

    board.digital[pin].write(target)
    time.sleep(0.03)


def mover(val_base, val_horizontal, val_vertical, val_garra):
    global atual_base, atual_horizontal, atual_vertical, atual_garra

    _ensure_board()

    if val_base != atual_base:
        _move_servo(pinBase, atual_base, val_base)

    if val_horizontal != atual_horizontal:
        _move_servo(pinHorizontal, atual_horizontal, val_horizontal)

    if val_vertical != atual_vertical:
        _move_servo(pinVertical, atual_vertical, val_vertical)

    if val_garra != atual_garra:
        _move_servo(pinGarra, atual_garra, val_garra)

    atual_base = val_base
    atual_horizontal = val_horizontal
    atual_vertical = val_vertical
    atual_garra = val_garra


# print('passo1')
# mover(90,0,80,0)
# time.sleep(2)
# print('passo2')
# mover(90, 50, 100, 0)
# time.sleep(2)
# print('passo3')
# mover(0, 0, 0, 0)

