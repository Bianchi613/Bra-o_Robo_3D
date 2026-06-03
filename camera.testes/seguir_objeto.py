import cv2
import numpy as np
import time
import sys
import os

# =========================
# IMPORTAR servo.py
# =========================

sys.path.append(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    )
)

import servo as serv

# =========================
# CÂMERA
# =========================

camera = cv2.VideoCapture(0)

# =========================
# ESTADO DO BRAÇO
# =========================

base = 90
horizontal = 110
vertical = 100
garra = 0

# =========================
# LIMITES
# =========================

BASE_MIN = 20
BASE_MAX = 160

H_MIN = 70
H_MAX = 140

V_MIN = 60
V_MAX = 140

# =========================
# CONTROLE
# =========================

ultimo_movimento = time.time()

# =========================
# FUNÇÃO MOVIMENTO SEGURO
# =========================

def mover_seguro():

    global base
    global horizontal
    global vertical
    global garra

    # =========================
    # RESTRIÇÕES CINEMÁTICAS
    # =========================

    # evita colisão frontal
    if horizontal < 80 and vertical < 70:
        vertical = 70

    # evita dobra extrema
    if horizontal > 135 and vertical > 120:
        horizontal = 135

    # limites físicos
    base = max(BASE_MIN, min(BASE_MAX, base))

    horizontal = max(H_MIN, min(H_MAX, horizontal))

    vertical = max(V_MIN, min(V_MAX, vertical))

    # movimento real
    serv.mover(
        base,
        horizontal,
        vertical,
        garra
    )

    print()
    print("===================")
    print("BASE:", base)
    print("HORIZONTAL:", horizontal)
    print("VERTICAL:", vertical)
    print("===================")

# =========================
# LOOP PRINCIPAL
# =========================

while True:

    ret, frame = camera.read()

    if not ret:
        print("Erro ao acessar câmera")
        break

    # =========================
    # SUAVIZA IMAGEM
    # =========================

    frame = cv2.GaussianBlur(frame, (5, 5), 0)

    # =========================
    # CONVERTE PARA HSV
    # =========================

    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    # =========================
    # DETECÇÃO VERMELHO
    # =========================

    lower1 = np.array([0, 120, 70])
    upper1 = np.array([10, 255, 255])

    lower2 = np.array([170, 120, 70])
    upper2 = np.array([180, 255, 255])

    mask1 = cv2.inRange(hsv, lower1, upper1)
    mask2 = cv2.inRange(hsv, lower2, upper2)

    mask = mask1 + mask2

    # =========================
    # LIMPEZA DE RUÍDO
    # =========================

    kernel = np.ones((5, 5), np.uint8)

    mask = cv2.morphologyEx(
        mask,
        cv2.MORPH_OPEN,
        kernel
    )

    mask = cv2.morphologyEx(
        mask,
        cv2.MORPH_CLOSE,
        kernel
    )

    mask = cv2.GaussianBlur(mask, (9, 9), 0)

    # =========================
    # CONTORNOS
    # =========================

    contours, _ = cv2.findContours(
        mask,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    for cnt in contours:

        area = cv2.contourArea(cnt)

        # ignora ruído pequeno
        if area > 1000:

            x, y, w, h = cv2.boundingRect(cnt)

            centro_x = x + w // 2
            centro_y = y + h // 2

            # =========================
            # DESENHOS
            # =========================

            # quadrado verde
            cv2.rectangle(
                frame,
                (x, y),
                (x + w, y + h),
                (0, 255, 0),
                2
            )

            # ponto azul
            cv2.circle(
                frame,
                (centro_x, centro_y),
                5,
                (255, 0, 0),
                -1
            )

            # coordenadas
            cv2.putText(
                frame,
                f"X:{centro_x} Y:{centro_y}",
                (x, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2
            )

            print()
            print("OBJETO DETECTADO")
            print("X:", centro_x)
            print("Y:", centro_y)
            print("AREA:", int(area))

            # =========================
            # CONTROLE TEMPORAL
            # =========================

            agora = time.time()

            # evita mover toda frame
            if agora - ultimo_movimento > 0.08:

                # =========================
                # SEGUIR HORIZONTAL
                # =========================

                if centro_x < 260:

                    base -= 2

                elif centro_x > 380:

                    base += 2

                # =========================
                # SEGUIR VERTICAL
                # =========================

                # objeto alto na imagem
                if centro_y < 180:

                    vertical += 2

                # objeto baixo na imagem
                elif centro_y > 300:

                    vertical -= 2

                # =========================
                # MOVIMENTO SEGURO
                # =========================

                mover_seguro()

                ultimo_movimento = agora

    # =========================
    # MOSTRAR JANELAS
    # =========================

    cv2.imshow("camera", frame)

    cv2.imshow("mask", mask)

    # ESC fecha
    if cv2.waitKey(1) == 27:
        break

camera.release()
cv2.destroyAllWindows()