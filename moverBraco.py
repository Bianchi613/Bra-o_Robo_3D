import cv2
import json
import sys
import servo as serv


def load_initial_angles():
    try:
        with open("dados.json", "r", encoding="utf-8") as jsondados:
            dados = json.load(jsondados)
    except Exception as exc:
        print("Erro ao carregar dados.json:", exc)
        sys.exit(1)

    if not dados or not isinstance(dados, list):
        print("dados.json deve conter uma lista com configuração de inicialização.")
        sys.exit(1)

    config = dados[0]

    return (
        config.get("angInicial-base", 90),
        config.get("angInicial-horizontal", 90),
        config.get("angInicial-vertical", 90),
        config.get("angInicial-garra", 0),
    )


def main():
    angBase, angHorizontal, angVertical, angGarra = load_initial_angles()

    cv2.namedWindow("controls")
    cv2.createTrackbar("Base", "controls", angBase, 180, lambda x: None)
    cv2.createTrackbar("Horizontal", "controls", angHorizontal, 180, lambda x: None)
    cv2.createTrackbar("Vertical", "controls", angVertical, 180, lambda x: None)
    cv2.createTrackbar("Garra", "controls", angGarra, 180, lambda x: None)

    try:
        while True:
            base = int(cv2.getTrackbarPos("Base", "controls"))
            horizontal = int(cv2.getTrackbarPos("Horizontal", "controls"))
            vertical = int(cv2.getTrackbarPos("Vertical", "controls"))
            garra = int(cv2.getTrackbarPos("Garra", "controls"))

            serv.mover(base, horizontal, vertical, garra)

            if cv2.waitKey(1) & 0xFF == 27:
                break
    except KeyboardInterrupt:
        print("Interrupção recebida. Encerrando.")
    finally:
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

