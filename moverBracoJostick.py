import pygame
import braco3d
import time

pygame.init()
pygame.joystick.init()

joystick = pygame.joystick.Joystick(0)
joystick.init()

braco = braco3d.Braco(base=90, hori=90, vert=90, garra=90)
braco3d.iniciar()

clock = pygame.time.Clock()

while True:
    pygame.event.pump()

    eixo_base = joystick.get_axis(0)   # analógico esquerdo X → rotação da base
    eixo_hori = joystick.get_axis(1)   # analógico esquerdo Y → ombro
    eixo_vert = joystick.get_axis(3)   # analógico direito  Y → antebraço

    braco.ajustar_base(int(eixo_base * 2))
    braco.ajustar_horizontal(int(eixo_hori * 2))
    braco.ajustar_vertical(int(eixo_vert * 2))

    if joystick.get_button(0):   # X → abre garra
        braco.ajustar_garra(1)
    if joystick.get_button(1):   # O → fecha garra
        braco.ajustar_garra(-1)

    braco3d.mover_servo(*braco.posicao())

    print(braco)

    if not braco3d.atualizar(*braco.posicao()):
        break

    clock.tick(50)

braco3d.fechar()
