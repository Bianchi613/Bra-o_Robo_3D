import cv2

camera = cv2.VideoCapture(0)

while True:

    ret, frame = camera.read()

    if not ret:
        break

    cv2.imshow("camera", frame)

    # ESC fecha
    if cv2.waitKey(1) == 27:
        break

camera.release()
cv2.destroyAllWindows()