import cv2
import numpy as np

camera = cv2.VideoCapture(0)

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

    # vermelho faixa 1
    lower1 = np.array([0, 120, 70])
    upper1 = np.array([10, 255, 255])

    # vermelho faixa 2
    lower2 = np.array([170, 120, 70])
    upper2 = np.array([180, 255, 255])

    mask1 = cv2.inRange(hsv, lower1, upper1)
    mask2 = cv2.inRange(hsv, lower2, upper2)

    mask = mask1 + mask2

    # =========================
    # LIMPEZA DE RUÍDO
    # =========================

    kernel = np.ones((5, 5), np.uint8)

    # remove ruído pequeno
    mask = cv2.morphologyEx(
        mask,
        cv2.MORPH_OPEN,
        kernel
    )

    # fecha buracos
    mask = cv2.morphologyEx(
        mask,
        cv2.MORPH_CLOSE,
        kernel
    )

    # blur final
    mask = cv2.GaussianBlur(mask, (9, 9), 0)

    # =========================
    # ENCONTRAR CONTORNOS
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

            # ponto azul no centro
            cv2.circle(
                frame,
                (centro_x, centro_y),
                5,
                (255, 0, 0),
                -1
            )

            # texto
            cv2.putText(
                frame,
                f"X:{centro_x} Y:{centro_y}",
                (x, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2
            )

            print("Objeto detectado")
            print("X:", centro_x)
            print("Y:", centro_y)
            print("Area:", int(area))
            print("----------------")

    # =========================
    # MOSTRAR JANELAS
    # =========================

    cv2.imshow("camera", frame)

    # mostra máscara preto/branco
    cv2.imshow("mask", mask)

    # ESC fecha
    if cv2.waitKey(1) == 27:
        break

camera.release()
cv2.destroyAllWindows()