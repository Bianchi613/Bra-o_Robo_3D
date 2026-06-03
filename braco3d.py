"""
Módulo braço robótico 3D — visualização + controle.
Importável em qualquer script: ia_braco.py, moverBracoJostick.py, etc.

Uso básico:
    import braco3d
    braco3d.iniciar()
    while True:
        ...  # sua lógica de controle
        if not braco3d.atualizar(base, hori, vert, garra):
            break
    braco3d.fechar()
"""

import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
import math

try:
    import servo as serv
    HAS_SERVO = True
except Exception:
    HAS_SERVO = False

# ═══════════════════════════════  CONSTANTES  ═══════════════════════════════

L_BASE  = 3.50
L1      = 5.10
L2      = 3.70
GRIP_L  = 2.34
GRIP_MAX= 0.90

SW   = 0.26   # semi-largura dos braços
PT   = 0.10   # espessura da chapa
AH   = 0.50   # altura do braço inferior
FH   = 0.90   # altura do antebraço
PY   = 0.38   # offset Y da barra do paralelogramo

ALPHA   = 0.68
LARANJA = (1.00, 0.45, 0.00, ALPHA)
PRETO   = (0.12, 0.12, 0.12, ALPHA)
ESCURO  = (0.05, 0.05, 0.05, ALPHA)
METAL   = (0.55, 0.56, 0.58, ALPHA)
SERVO_C = (0.14, 0.14, 0.20, ALPHA)

# Convenção de ângulos:
#   h < 90  →  braço sobe    |  h > 90  →  braço desce
#   v < 90  →  antebraço sobe|  v > 90  →  antebraço desce
ACOES = {
    "REPOUSO":           (90,  90,  90,   0),  # horizontal, centro
    "ESQUERDA":          (40,  80,  80,   0),  # base esquerda, altura de trabalho
    "DIREITA":           (140, 80,  80,   0),  # base direita
    "CENTRO":            (90,  80,  80,   0),  # centro, altura de trabalho
    "LEVANTAR":          (90,  50,  60,   0),  # braço levantado
    "ABAIXAR":           (90,  120, 110,  0),  # braço abaixado
    "LEVANTAR_MAXIMO":   (90,  30,  40,   0),  # braço totalmente erguido
    "ABAIXAR_MAXIMO":    (90,  140, 130,  0),  # braço totalmente abaixado
    "ABRIR_GARRA":       (90,  80,  80,  180), # garra aberta, altura de trabalho
    "FECHAR_GARRA":      (90,  80,  80,   0),  # garra fechada
    "ESQUERDA_SUAVE":    (60,  80,  80,   0),
    "DIREITA_SUAVE":     (120, 80,  80,   0),
    "OLHAR_CIMA":        (90,  50,  60,   0),  # braço erguido = olhar para cima
    "OLHAR_BAIXO":       (90,  120, 110,  0),  # braço baixo = olhar para baixo
    "PREPARAR_PEGA":     (90,  110, 100, 180),  # posição para pegar, garra aberta
    "PEGAR_OBJETO":      (90,  120, 110,  0),   # posição de pega, garra fechada
    "LEVANTAR_OBJETO":   (90,  50,  60,   0),   # erguer após pegar
    "SOLTAR_OBJETO":     (90,  110, 100, 180),  # soltar objeto
    "CUMPRIMENTAR":      (90,  40,  50,   0),   # braço alto = aceno
    "OBSERVAR":          (90,  70,  80,   0),   # ligeiramente erguido
    "PROCURAR":          (70,  70,  80,   0),   # esquerda, ligeiramente erguido
    "INVESTIGAR":        (110, 70,  80,   0),   # direita, ligeiramente erguido
    "EXTREMA_ESQUERDA":  (20,  80,  80,   0),
    "EXTREMA_DIREITA":   (160, 80,  80,   0),
    "RETRAIR":           (90,  50,  40,   0),   # braço recuado para cima
    "PROTEGER":          (90,  50,  60,   0),   # posição defensiva erguida
    "TOCAR_MESA":        (90,  140, 130,  0),   # braço totalmente abaixado
    "COLETAR":           (90,  140, 130, 180),  # braço baixo, garra aberta
    "MODO_ALERTA":       (90,  50,  60,   0),   # erguido, alerta
    "MODO_DESCANSO":     (90,  90,  90,   0),
    "MODO_CURIOSO":      (70,  60,  70,   0),  # esquerda, erguido
    "MODO_VIGIA":        (110, 60,  70,   0),  # direita, erguido
}

# Estado interno da janela e câmera
_clock     = None
_aberto    = False
_largura   = 920
_altura    = 660
_cam_yaw   = 45.0
_cam_pitch = 30.0
_cam_dist  = 28.0
_mouse_btn = False
_mouse_pos = (0, 0)
_fonte_hud = None

# Cubo interativo
_cubo_pos  = [0.0, 0.0, 9.5]
_cubo_agarro = False
_cubo_vy   = 0.0
_CUBO_TAM  = 0.30    # meia-aresta
_CUBO_RAIO = 2.2     # raio de captura e exibição


# ═══════════════════════════  Ciclo de vida  ═════════════════════════════════

def iniciar(largura=920, altura=660, titulo="Braço Robótico 3D  |  Arraste=girar  |  Scroll=zoom"):
    """Cria a janela pygame com contexto OpenGL. Deve ser chamado uma vez."""
    global _clock, _aberto, _largura, _altura, _fonte_hud
    pygame.init()
    pygame.font.init()
    _largura, _altura = largura, altura
    pygame.display.set_mode((largura, altura), DOUBLEBUF | OPENGL)
    pygame.display.set_caption(titulo)
    _init_gl(largura, altura)
    _clock = pygame.time.Clock()
    _aberto = True
    _fonte_hud = pygame.font.SysFont("Consolas", 15)


def atualizar(base, hori, vert, garra, fps=30):
    """
    Processa eventos pygame, renderiza o braço e limita o FPS.

    Retorna False quando a janela for fechada (deve encerrar o loop).
    """
    global _aberto
    if not _aberto:
        return False

    for ev in pygame.event.get():
        if ev.type == QUIT:
            fechar()
            return False
        if ev.type == KEYDOWN:
            if ev.key == K_ESCAPE:
                fechar()
                return False
            _mover_cubo_teclado(ev.key)
        _processar_mouse(ev)

    _verificar_agarro(base, hori, vert, garra)
    _render(base, hori, vert, garra)
    if _clock:
        _clock.tick(fps)
    return True


def mover_suave(braco_obj, base_alvo, hori_alvo, vert_alvo, garra_alvo,
               passos: int = 25, fps: int = 30) -> bool:
    """
    Anima o braço suavemente da posição atual até o alvo.
    Atualiza a janela 3D a cada passo (interpolação linear).
    Retorna False se a janela foi fechada durante a animação.
    """
    if not _aberto:
        braco_obj.mover(base_alvo, hori_alvo, vert_alvo, garra_alvo)
        return True

    b0, h0, v0, g0 = braco_obj.posicao()

    for i in range(1, passos + 1):
        t = i / passos
        b = int(b0 + (base_alvo  - b0) * t)
        h = int(h0 + (hori_alvo  - h0) * t)
        v = int(v0 + (vert_alvo  - v0) * t)
        g = int(g0 + (garra_alvo - g0) * t)
        braco_obj.mover(b, h, v, g)
        if not atualizar(b, h, v, g, fps=fps):
            return False

    return True


def fechar():
    """Fecha a janela pygame."""
    global _aberto
    _aberto = False
    pygame.quit()


def esta_aberto():
    """Retorna True se a janela ainda está ativa."""
    return _aberto


# ═══════════════════════════  Cubo interativo  ═══════════════════════════════

def set_cubo_pos(x_mm, y_mm):
    _cubo_pos[0] = x_mm / 25.0
    _cubo_pos[2] = y_mm / 25.0
    _cubo_pos[1] = 0.0

def get_cubo_pos():
    return (_cubo_pos[0] * 25.0, _cubo_pos[2] * 25.0)

def cubo_esta_agarrado():
    return _cubo_agarro

def _fingertip_gl(base_ang, hori_ang, vert_ang):
    """Ponta dos dedos em coords OpenGL (para HUD/distâncias)."""
    sr  = math.radians(90.0 - hori_ang)
    fr  = math.radians(90.0 - vert_ang)
    br  = math.radians(base_ang - 90.0)
    ext = L2 + 1.52 + GRIP_L + 0.64
    dy  = L1 * math.sin(sr) + ext * math.sin(fr)
    dz  = 0.16 + L1 * math.cos(sr) + ext * math.cos(fr)
    return dz * math.sin(br), L_BASE + 0.96 + dy, dz * math.cos(br)


def _finger_pos_gl(base_ang, hori_ang, vert_ang, garra_ang, lado):
    """Posição mundial de um dedo individual. lado = +1 (dir) ou -1 (esq)."""
    abertura  = (garra_ang / 180.0) * GRIP_MAX
    fx        = lado * (0.18 + abertura)
    fy        = 0.28
    fz_total  = L2 + 1.52 + GRIP_L * 0.5   # da escápula até o centro do dedo

    br = math.radians(base_ang - 90)
    θs = math.radians(hori_ang - 90)
    θf = math.radians(vert_ang - 90)

    # Pivo do ombro
    piv_x =  0.16 * math.sin(br)
    piv_y =  L_BASE + 0.96
    piv_z =  0.16 * math.cos(br)

    # Cotovelo
    arm_y  = -L1 * math.sin(θs)
    arm_z0 =  L1 * math.cos(θs)
    elb_x  = piv_x + arm_z0 * math.sin(br)
    elb_y  = piv_y + arm_y
    elb_z  = piv_z + arm_z0 * math.cos(br)

    # Offset do dedo no frame da base (após Rx(θf) e Ry(br))
    fg_x_b =  fx
    fg_y_b =  fy * math.cos(θf) - fz_total * math.sin(θf)
    fg_z_b =  fy * math.sin(θf) + fz_total * math.cos(θf)

    return (
        elb_x + fg_x_b * math.cos(br) + fg_z_b * math.sin(br),
        elb_y + fg_y_b,
        elb_z - fg_x_b * math.sin(br) + fg_z_b * math.cos(br),
    )


def _claw_center_gl(base_ang, hori_ang, vert_ang):
    """Posição exata do ponto médio entre os dedos via cinemática direta.

    A rotação líquida do antebraço em relação ao frame da base é vert-90
    (a rotação do ombro é desfeita pelo paralelogramo, deixando só o antebraço).
    """
    br = math.radians(base_ang - 90.0)
    θs = math.radians(hori_ang - 90.0)   # rotação do ombro
    θf = math.radians(vert_ang - 90.0)   # rotação líquida do antebraço

    # ── Pivo do ombro em coords mundo ─────────────────────────────────────────
    # O z=0.16 no frame da base rotaciona com o braço
    piv_x =  0.16 * math.sin(br)
    piv_y =  L_BASE + 0.96
    piv_z =  0.16 * math.cos(br)

    # ── Cotovelo: braço superior (L1) girado pelo ombro ───────────────────────
    arm_y  = -L1 * math.sin(θs)
    arm_z0 =  L1 * math.cos(θs)          # no frame da base
    elb_x  = piv_x + arm_z0 * math.sin(br)
    elb_y  = piv_y + arm_y
    elb_z  = piv_z + arm_z0 * math.cos(br)

    # ── Ponto médio dos dedos no frame do antebraço ────────────────────────────
    # Posição local: [0, 0.28, L2+CLAW_D+GRIP_L/2]  (GRIP_L/2 = meio do corpo dos dedos)
    fy = 0.28
    fz = L2 + 1.52 + GRIP_L * 0.5

    # Rotação do antebraço (Rx(θf)) sobre [0, fy, fz]:
    fg_y   = fy * math.cos(θf) - fz * math.sin(θf)
    fg_z0  = fy * math.sin(θf) + fz * math.cos(θf)   # no frame da base

    return (
        elb_x + fg_z0 * math.sin(br),
        elb_y + fg_y,
        elb_z + fg_z0 * math.cos(br),
    )

def _cubo_centro():
    return (_cubo_pos[0], _cubo_pos[1] + _CUBO_TAM, _cubo_pos[2])

def _mover_cubo_teclado(key):
    """Setas movem o cubo no chão (quando solto)."""
    if _cubo_agarro:
        return
    p = 0.5
    if   key == K_LEFT:  _cubo_pos[0] -= p
    elif key == K_RIGHT: _cubo_pos[0] += p
    elif key == K_UP:    _cubo_pos[2] -= p
    elif key == K_DOWN:  _cubo_pos[2] += p

def _verificar_agarro(base_ang, hori_ang, vert_ang, garra_ang):
    """Agarro simples e confiável: perto + fecha = agarra, abre = solta."""
    global _cubo_agarro, _cubo_pos, _cubo_vy

    θf = math.radians(vert_ang - 90)
    gx, gy, gz = _claw_center_gl(base_ang, hori_ang, vert_ang)
    cx, cy, cz = _cubo_centro()
    dist = math.sqrt((gx-cx)**2 + (gy-cy)**2 + (gz-cz)**2)

    if _cubo_agarro:
        # Arrastar: cubo segue o centro dos dedos
        fy_w = 0.28 * math.cos(θf)
        _cubo_pos[0] = gx
        _cubo_pos[1] = max(0.0, gy + fy_w - _CUBO_TAM)
        _cubo_pos[2] = gz
        # Soltar: garra abre
        # Soltar: dedos abertos além das laterais do cubo (> 24°)
        GARRA_TOQUE_SOL = int((_CUBO_TAM - 0.18) / GRIP_MAX * 180)
        if garra_ang > GARRA_TOQUE_SOL + 5:
            _cubo_agarro = False
            _cubo_vy = -0.06
    else:
        # Posições individuais de cada dedo em coords mundo
        lx, ly, lz = _finger_pos_gl(base_ang, hori_ang, vert_ang, garra_ang, -1)
        rx, ry, rz = _finger_pos_gl(base_ang, hori_ang, vert_ang, garra_ang,  1)
        RAIO_DEDO = _CUBO_TAM + 0.22   # raio de contato por dedo

        def _empurrar_de(fx, fy2, fz2):
            d = math.sqrt((fx-cx)**2 + (fy2-cy)**2 + (fz2-cz)**2)
            if d < RAIO_DEDO:
                ddx = cx - fx; ddz = cz - fz2
                mag = math.sqrt(ddx**2 + ddz**2) + 0.001
                pen = (RAIO_DEDO - d) * 0.30
                _cubo_pos[0] += (ddx / mag) * pen
                _cubo_pos[2] += (ddz / mag) * pen

        # Ângulo onde os dedos tocam as laterais do cubo (≈ 24°)
        GARRA_TOQUE = int(max(0, _CUBO_TAM - 0.18) / GRIP_MAX * 180)

        if garra_ang <= GARRA_TOQUE and dist < _CUBO_RAIO:
            # Dedos fechados sobre o cubo → agarra
            _cubo_agarro = True
            _cubo_vy = 0.0
        else:
            # Cada dedo empurra independentemente ao tocar
            _empurrar_de(lx, ly, lz)
            _empurrar_de(rx, ry, rz)
        # Gravidade
        _cubo_pos[1] = max(0.0, _cubo_pos[1] + _cubo_vy)
        _cubo_vy = 0.0 if _cubo_pos[1] <= 0.0 else _cubo_vy - 0.015

def _desenhar_cubo(base_ang, hori_ang, vert_ang):
    """Cubo transparente, rotacionado com o braço quando agarrado."""
    gx, gy, gz = _claw_center_gl(base_ang, hori_ang, vert_ang)

    dist_livre = math.sqrt(
        (gx - _cubo_centro()[0])**2 +
        (gy - _cubo_centro()[1])**2 +
        (gz - _cubo_centro()[2])**2
    ) if not _cubo_agarro else 0.0

    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glEnable(GL_DEPTH_TEST)
    glDepthMask(GL_FALSE)

    if _cubo_agarro:
        # Cubo entre os dedos: posicionado no grip center,
        # rotacionado para alinhar com a direção do braço
        cx = gx
        cy = gy + 0.28   # altura dos dedos (+0.28 acima do eixo do antebraço)
        cz = gz
        r, g, b, a = 0.4, 0.85, 1.0, 0.45   # azul claro, semi-transparente

        glPushMatrix()
        glTranslatef(cx, cy, cz)
        glRotatef(-(base_ang - 90), 0, 1, 0)  # alinha com rotação da base
        glEnable(GL_LIGHTING)
        glColor4f(r, g, b, a)
        _box(_CUBO_TAM*2, _CUBO_TAM*2, _CUBO_TAM*2)
        glDisable(GL_LIGHTING)
        glColor4f(0.0, 0.6, 1.0, a * 0.8)
        glLineWidth(1.5)
        glPolygonMode(GL_FRONT_AND_BACK, GL_LINE)
        _box(_CUBO_TAM*2+0.02, _CUBO_TAM*2+0.02, _CUBO_TAM*2+0.02)
        glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)
        glLineWidth(1.0)
        glPopMatrix()

    else:
        cx, cy, cz = _cubo_centro()
        em_alcance = dist_livre < _CUBO_RAIO
        if em_alcance:
            r, g, b, a = 0.2, 1.0, 0.3, 0.75  # verde
        else:
            r, g, b, a = 1.0, 0.55, 0.05, 0.90  # laranja

        glPushMatrix()
        glTranslatef(cx, cy, cz)
        glEnable(GL_LIGHTING)
        glColor4f(r, g, b, a)
        _box(_CUBO_TAM*2, _CUBO_TAM*2, _CUBO_TAM*2)
        glDisable(GL_LIGHTING)
        glColor4f(0.0, 0.0, 0.0, 0.6)
        glLineWidth(1.5)
        glPolygonMode(GL_FRONT_AND_BACK, GL_LINE)
        _box(_CUBO_TAM*2+0.02, _CUBO_TAM*2+0.02, _CUBO_TAM*2+0.02)
        glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)
        glLineWidth(1.0)
        glPopMatrix()

        # sombra no chão
        glDisable(GL_LIGHTING)
        glColor4f(0.0, 0.0, 0.0, 0.20)
        glPushMatrix()
        glTranslatef(cx, 0.01, cz)
        _box(_CUBO_TAM*2.5, 0.01, _CUBO_TAM*2.5)
        glPopMatrix()

        # linha ao grip center quando em alcance
        if em_alcance:
            t = 1.0 - dist_livre / _CUBO_RAIO
            glColor4f(0.2, 1.0, 0.3, t * 0.8)
            glLineWidth(2.0)
            glBegin(GL_LINES)
            glVertex3f(gx, gy, gz)
            glVertex3f(cx, cy, cz)
            glEnd()
            glLineWidth(1.0)

    glDepthMask(GL_TRUE)
    glDisable(GL_BLEND)
    glEnable(GL_LIGHTING)


# ═══════════════════════════  Câmera  ════════════════════════════════════════

def _processar_mouse(event):
    global _cam_yaw, _cam_pitch, _cam_dist, _mouse_btn, _mouse_pos
    if event.type == MOUSEBUTTONDOWN and event.button == 1:
        _mouse_btn = True
        _mouse_pos = event.pos
    elif event.type == MOUSEBUTTONUP and event.button == 1:
        _mouse_btn = False
    elif event.type == MOUSEMOTION and _mouse_btn:
        dx = event.pos[0] - _mouse_pos[0]
        dy = event.pos[1] - _mouse_pos[1]
        _cam_yaw  += dx * 0.4
        _cam_pitch = max(-10.0, min(80.0, _cam_pitch - dy * 0.4))
        _mouse_pos = event.pos
    elif event.type == MOUSEWHEEL:
        _cam_dist = max(4.0, min(50.0, _cam_dist - event.y * 0.6))


def get_camera():
    """Retorna (yaw, pitch, dist) da câmera."""
    return (_cam_yaw, _cam_pitch, _cam_dist)


def set_camera(yaw, pitch, dist):
    """Define posição da câmera."""
    global _cam_yaw, _cam_pitch, _cam_dist
    _cam_yaw, _cam_pitch, _cam_dist = yaw, pitch, dist


# ═══════════════════════════  Helpers  ═══════════════════════════════════════

def limitar_angulos(base, hori, vert, garra):
    """
    Garante ângulos em [0, 180] e impede que a ponta da garra
    ultrapasse o plano z=0 (o chão).
    """
    base  = max(0, min(180, int(base)))
    hori  = max(0, min(180, int(hori)))
    vert  = max(0, min(180, int(vert)))
    garra = max(0, min(180, int(garra)))

    # Comprimento total do braço até a ponta dos dedos
    ext = L2 + 1.52 + GRIP_L + 0.64

    # Ângulo mínimo do antebraço (fr) que mantém a ponta em z >= 0:
    #   (L_BASE + 0.96 + L1*sin(sr) + ext*sin(fr)) >= 0
    #   sin(fr) >= -(L_BASE + 0.96 + L1*sin(sr)) / ext
    shoulder_r  = math.radians(90.0 - hori)
    sin_fr_min  = -(L_BASE + 0.96 + L1 * math.sin(shoulder_r)) / ext
    sin_fr_min  = max(-1.0, sin_fr_min)        # clamp para domínio válido

    fr_min      = math.asin(sin_fr_min)         # ângulo mínimo do antebraço (rad)
    vert_max    = int(90.0 - math.degrees(fr_min))  # vert_ang máximo permitido

    vert = min(vert, vert_max)

    return base, hori, vert, garra


def obter_acao(nome):
    """Retorna (base, hori, vert, garra) de uma ação pré-definida, ou None."""
    return ACOES.get(nome.strip().upper())


def listar_acoes():
    """Retorna lista ordenada de nomes de ações."""
    return sorted(ACOES.keys())


def mover_servo(base, hori, vert, garra):
    """Envia posição para o servo físico. Ignora silenciosamente se não conectado."""
    if HAS_SERVO:
        try:
            serv.mover(base, hori, vert, garra)
        except Exception:
            pass


# ═══════════════════════════  OpenGL interno  ════════════════════════════════

def _init_gl(w, h):
    glEnable(GL_DEPTH_TEST)
    glEnable(GL_LIGHTING)
    glEnable(GL_LIGHT0); glEnable(GL_LIGHT1)
    glEnable(GL_COLOR_MATERIAL)
    glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
    glLightfv(GL_LIGHT0, GL_POSITION, [7.0, 15.0, 8.0, 1.0])
    glLightfv(GL_LIGHT0, GL_DIFFUSE,  [1.0,  1.0,  1.0, 1.0])
    glLightfv(GL_LIGHT0, GL_AMBIENT,  [0.28, 0.28, 0.28, 1.0])
    glLightfv(GL_LIGHT1, GL_POSITION, [-4.0, 5.0, -3.0, 1.0])
    glLightfv(GL_LIGHT1, GL_DIFFUSE,  [0.30, 0.30, 0.30, 1.0])
    glMaterialf(GL_FRONT_AND_BACK, GL_SHININESS, 40.0)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glMatrixMode(GL_PROJECTION); glLoadIdentity()
    gluPerspective(45.0, w / h, 0.1, 100.0)
    glMatrixMode(GL_MODELVIEW)
    glClearColor(0.07, 0.07, 0.10, 1.0)


def _cor(r, g, b, a=ALPHA):
    glColor4f(r, g, b, a)


def _box(w, h, d):
    x, y, z = w*.5, h*.5, d*.5
    faces = [
        ( 0, 0, 1,[(-x,-y,z),(x,-y,z),(x,y,z),(-x,y,z)]),
        ( 0, 0,-1,[(-x,-y,-z),(-x,y,-z),(x,y,-z),(x,-y,-z)]),
        ( 0, 1, 0,[(-x,y,-z),(-x,y,z),(x,y,z),(x,y,-z)]),
        ( 0,-1, 0,[(-x,-y,-z),(x,-y,-z),(x,-y,z),(-x,-y,z)]),
        ( 1, 0, 0,[(x,-y,-z),(x,y,-z),(x,y,z),(x,-y,z)]),
        (-1, 0, 0,[(-x,-y,-z),(-x,-y,z),(-x,y,z),(-x,y,-z)]),
    ]
    glBegin(GL_QUADS)
    for nx, ny, nz, verts in faces:
        glNormal3f(nx, ny, nz)
        for v in verts: glVertex3fv(v)
    glEnd()


def _cyl(r, h, sl=18):
    q = gluNewQuadric(); gluQuadricNormals(q, GLU_SMOOTH)
    gluCylinder(q, r, r, h, sl, 1)
    gluDisk(q, 0, r, sl, 1)
    glTranslatef(0, 0, h); glRotatef(180, 1, 0, 0)
    gluDisk(q, 0, r, sl, 1); glRotatef(180, 1, 0, 0)
    glTranslatef(0, 0, -h); gluDeleteQuadric(q)


def _sph(r, sl=14):
    q = gluNewQuadric(); gluQuadricNormals(q, GLU_SMOOTH)
    gluSphere(q, r, sl, sl); gluDeleteQuadric(q)


# ═══════════════════════════  Peças  ═════════════════════════════════════════

def _chapas(sw, h, L, n_furos=3):
    _cor(*LARANJA)
    bH = h * 0.14
    ez = max(L * 0.09, 0.28)
    dz = max(L * 0.05, 0.14)
    n_div = n_furos - 1
    furo_z = (L - 2*ez - n_div*dz) / max(n_furos, 1)

    segs = [(0.0, ez)]
    z = ez
    for i in range(n_furos):
        z += furo_z
        if i < n_furos - 1:
            segs.append((z, z + dz))
            z += dz
    segs.append((z, L))

    for sx in (-1, 1):
        xp = sx * sw
        for sy in (1, -1):
            glPushMatrix()
            glTranslatef(xp, sy * (h - bH) * .5, L * .5)
            _box(PT, bH, L)
            glPopMatrix()
        for z0, z1 in segs:
            glPushMatrix()
            glTranslatef(xp, 0, (z0 + z1) * .5)
            _box(PT, h, z1 - z0)
            glPopMatrix()

    for z0, z1 in segs:
        glPushMatrix()
        glTranslatef(0, 0, (z0 + z1) * .5)
        _box(sw * 2, h, z1 - z0)
        glPopMatrix()
    for sy in (1, -1):
        glPushMatrix()
        glTranslatef(0, sy * (h - bH) * .5, L * .5)
        _box(sw * 2, bH, L)
        glPopMatrix()


def _suporte_U(sw, h, prof):
    _cor(*LARANJA)
    ew = 0.09
    for sx in (-1, 1):
        glPushMatrix()
        glTranslatef(sx * (sw + ew*.5), 0, prof*.5)
        _box(ew, h, prof)
        glPopMatrix()
    glPushMatrix()
    glTranslatef(0, h*.5 + ew*.5, prof*.5)
    _box(sw*2 + ew*2, ew, prof)
    glPopMatrix()


def _servo():
    _cor(*SERVO_C)
    _box(0.86, 0.86, 0.46)
    _box(1.08, 0.18, 0.50)
    glColor4f(0.92, 0.92, 0.92, ALPHA)
    glPushMatrix()
    glTranslatef(0, 0.50, 0); glRotatef(-90, 1, 0, 0)
    _cyl(0.09, 0.14, 10)
    glPopMatrix()


def _engrenagem(r=0.56, n=10):
    _cor(*LARANJA)
    _cyl(r, 0.28, 20)
    for i in range(n):
        a = math.radians(i * (360.0 / n))
        glPushMatrix()
        glTranslatef(math.sin(a)*(r+0.07), math.cos(a)*(r+0.07), 0.08)
        _box(0.18, 0.18, 0.24)
        glPopMatrix()


def _maxila(lado, abertura):
    _cor(*PRETO)
    x = lado * (0.18 + abertura)
    glPushMatrix()
    glTranslatef(x, 0.28, 1.52 + GRIP_L * .5)
    _box(0.36, 0.56, GRIP_L)
    glPopMatrix()
    glPushMatrix()
    glTranslatef(x + lado * (-0.07), 0.18, 1.52 + GRIP_L + 0.34)
    glRotatef(lado * (-18), 0, 1, 0)
    _box(0.34, 0.50, 0.60)
    glPopMatrix()


def _letra(letra, ox, oy, oz, s=0.28):
    """Desenha letra X, Y ou Z como linhas 3D no plano horizontal."""
    glBegin(GL_LINES)
    if letra == 'X':
        glVertex3f(ox,     oy, oz);     glVertex3f(ox+s,   oy, oz+s)
        glVertex3f(ox+s,   oy, oz);     glVertex3f(ox,     oy, oz+s)
    elif letra == 'Y':
        glVertex3f(ox,     oy, oz);     glVertex3f(ox+s/2, oy, oz+s/2)
        glVertex3f(ox+s,   oy, oz);     glVertex3f(ox+s/2, oy, oz+s/2)
        glVertex3f(ox+s/2, oy, oz+s/2); glVertex3f(ox+s/2, oy, oz+s)
    elif letra == 'Z':
        glVertex3f(ox,     oy, oz);     glVertex3f(ox+s,   oy, oz)
        glVertex3f(ox+s,   oy, oz);     glVertex3f(ox,     oy, oz+s)
        glVertex3f(ox,     oy, oz+s);   glVertex3f(ox+s,   oy, oz+s)
    glEnd()


def _grid():
    glDisable(GL_LIGHTING)

    # Grade de fundo — 18x18 células
    glColor3f(0.17, 0.17, 0.21)
    glLineWidth(1.0)
    G = 14   # metade do tamanho do grid
    glBegin(GL_LINES)
    for i in range(-G, G + 1):
        glVertex3f(float(i), 0, float(-G)); glVertex3f(float(i), 0, float(G))
        glVertex3f(float(-G), 0, float(i)); glVertex3f(float(G),  0, float(i))
    glEnd()

    Y = 0.04   # ligeiramente acima do plano para evitar z-fighting
    AX = 8.0   # comprimento dos eixos

    glLineWidth(2.5)

    # Eixo X — vermelho (plano, horizontal)
    glColor3f(0.95, 0.25, 0.25)
    glBegin(GL_LINES)
    glVertex3f(0, Y, 0); glVertex3f(AX, Y, 0)
    glEnd()
    glBegin(GL_TRIANGLES)
    glVertex3f(AX + 0.5, Y,  0.0)
    glVertex3f(AX - 0.1, Y,  0.25)
    glVertex3f(AX - 0.1, Y, -0.25)
    glEnd()
    _letra('X', AX + 0.7, Y, -0.22)

    # Eixo Y — azul (plano, profundidade)
    glColor3f(0.25, 0.50, 0.95)
    glBegin(GL_LINES)
    glVertex3f(0, Y, 0); glVertex3f(0, Y, AX)
    glEnd()
    glBegin(GL_TRIANGLES)
    glVertex3f( 0.0,  Y, AX + 0.5)
    glVertex3f( 0.25, Y, AX - 0.1)
    glVertex3f(-0.25, Y, AX - 0.1)
    glEnd()
    _letra('Y', -0.22, Y, AX + 0.7)

    # Eixo Z — verde (vertical, para cima)
    glColor3f(0.20, 0.88, 0.30)
    glBegin(GL_LINES)
    glVertex3f(0, 0, 0); glVertex3f(0, AX, 0)
    glEnd()
    glBegin(GL_TRIANGLES)
    glVertex3f( 0.0,  AX + 0.5, 0.0)
    glVertex3f( 0.25, AX - 0.1, 0.0)
    glVertex3f(-0.25, AX - 0.1, 0.0)
    glEnd()
    # Letra Z no plano vertical XY (visível da câmera)
    s = 0.38
    ox, oy = -0.55, AX + 0.7
    glBegin(GL_LINES)
    glVertex3f(ox,     oy + s, 0); glVertex3f(ox + s, oy + s, 0)
    glVertex3f(ox + s, oy + s, 0); glVertex3f(ox,     oy,     0)
    glVertex3f(ox,     oy,     0); glVertex3f(ox + s, oy,     0)
    glEnd()

    glLineWidth(1.0)
    glEnable(GL_LIGHTING)


# ═══════════════════════════  Render principal  ══════════════════════════════

def _render(base_ang, hori_ang, vert_ang, garra_ang):
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glLoadIdentity()
    yr = math.radians(_cam_yaw);  pr = math.radians(_cam_pitch)
    FOCAL_Y = 4.0   # altura do pivô do ombro (L_BASE + 0.48 ≈ 4.0)
    ex = _cam_dist * math.cos(pr) * math.sin(yr)
    ey = _cam_dist * math.sin(pr) + FOCAL_Y
    ez = _cam_dist * math.cos(pr) * math.cos(yr)
    gluLookAt(ex, ey, ez, 0.0, FOCAL_Y, 0.0, 0.0, 1.0, 0.0)
    _grid()
    glDepthMask(GL_FALSE)
    glPushMatrix()

    # BASE
    _cor(*PRETO)
    glPushMatrix(); glRotatef(-90, 1, 0, 0); _cyl(1.44, 0.34, 32); glPopMatrix()
    glPushMatrix()
    glTranslatef(0, 0.34, 0); glRotatef(-90, 1, 0, 0); _cyl(1.10, L_BASE-0.34, 24)
    glPopMatrix()
    _cor(*METAL)
    for cx, cz in [(-1.05,-0.82),(1.05,-0.82),(-1.05,0.82),(1.05,0.82)]:
        glPushMatrix()
        glTranslatef(cx, 0.36, cz); glRotatef(-90, 1, 0, 0)
        _cyl(0.13, 0.10, 6)
        glPopMatrix()
    glTranslatef(0, L_BASE, 0)

    # ROTAÇÃO DA BASE
    glRotatef(base_ang - 90, 0, 1, 0)
    _cor(*LARANJA)
    glPushMatrix(); glTranslatef(0, 0.24, 0); _box(1.40, 0.48, 0.90); glPopMatrix()
    glTranslatef(0, 0.48, 0)

    # OMBRO
    _suporte_U(SW + 0.10, 1.0, 0.32)
    glPushMatrix()
    glTranslatef(SW + 0.44, 0.44, 0.12); glRotatef(90, 0, 1, 0); _servo()
    glPopMatrix()
    _cor(*METAL)
    for sx in (-1, 1):
        glPushMatrix()
        glTranslatef(sx * (SW + 0.19), 0.44, 0.16)
        glRotatef(-90, 0, 1, 0); _cyl(0.13, 0.12, 10)
        glPopMatrix()

    shoulder = 90.0 - hori_ang
    glTranslatef(0, 0.48, 0.16)
    glRotatef(-shoulder, 1, 0, 0)

    # BRAÇO INFERIOR
    _chapas(SW, AH, L1, n_furos=3)
    _cor(*LARANJA)
    glPushMatrix()
    glTranslatef(0, PY, L1*.50); _box(SW*2, 0.13, L1)
    glPopMatrix()
    for sx in (-SW + 0.04, SW - 0.04):
        glPushMatrix()
        glTranslatef(sx, PY, L1*.50); _box(PT, 0.20, L1)
        glPopMatrix()

    # COTOVELO
    glTranslatef(0, 0, L1)
    _cor(*LARANJA)
    glPushMatrix(); glTranslatef(0, 0.12, -0.16); _box(SW*2+PT, 0.56, 0.18); glPopMatrix()
    _cor(*METAL)
    for sx in (-1, 1):
        glPushMatrix()
        glTranslatef(sx * (SW + 0.04), 0.0, 0)
        glRotatef(-90, 0, 1, 0); _cyl(0.12, 0.10, 10)
        glPopMatrix()

    glRotatef(shoulder, 1, 0, 0)
    forearm = 90.0 - vert_ang
    glRotatef(-forearm, 1, 0, 0)

    # ANTEBRAÇO
    _chapas(SW * 0.84, FH, L2, n_furos=2)
    glTranslatef(0, 0, L2)

    abertura = (garra_ang / 180.0) * GRIP_MAX

    # SUPORTE PULSO
    CLAW_W = 2.16; CLAW_H = 1.00; CLAW_D = 1.52
    _cor(*LARANJA)
    glPushMatrix()
    glTranslatef(0, CLAW_H*0.5, CLAW_D*0.5); _box(CLAW_W, CLAW_H, CLAW_D)
    glPopMatrix()
    _cor(*METAL)
    for sx in (-1, 1):
        glPushMatrix()
        glTranslatef(sx * (CLAW_W*0.5 + 0.10), CLAW_H*0.5, CLAW_D*0.5)
        glRotatef(-90, 0, 1, 0); _cyl(0.10, 0.12, 10)
        glPopMatrix()

    # ENGRENAGEM
    glPushMatrix()
    glTranslatef(0, CLAW_H*0.5 + 0.20, CLAW_D*0.5 + 0.10); glRotatef(-90, 1, 0, 0)
    glRotatef(garra_ang * 2.0, 0, 0, 1)
    _engrenagem()
    glPopMatrix()

    # Pequena esfera no centro dos dedos (sem wireframe)
    _cx2, _cy2, _cz2 = _cubo_centro()
    _gx2, _gy2, _gz2 = _claw_center_gl(base_ang, hori_ang, vert_ang)
    _em_zona2 = math.sqrt((_gx2-_cx2)**2+(_gy2-_cy2)**2+(_gz2-_cz2)**2) < _CUBO_RAIO

    glPushMatrix()
    glTranslatef(0, 0.28, 1.52 + GRIP_L * 0.5)
    glDisable(GL_LIGHTING)
    if _cubo_agarro:
        glColor4f(0.2, 0.7, 1.0, 0.9)
    elif _em_zona2:
        glColor4f(0.1, 1.0, 0.2, 1.0)
    else:
        glColor4f(1.0, 0.85, 0.1, 0.7)
    _sph(0.10, 8)
    glEnable(GL_LIGHTING)
    glPopMatrix()

    # CUBO AGARRADO — antes dos dedos para dedos aparecerem na frente
    if _cubo_agarro:
        glPushMatrix()
        glTranslatef(0, 0.28, 1.52 + GRIP_L * 0.5)
        glColor4f(0.15, 0.50, 1.0, ALPHA)
        glEnable(GL_LIGHTING)
        _box(_CUBO_TAM*2, _CUBO_TAM*2, _CUBO_TAM*2)
        glPopMatrix()

    # MAXILAS — depois → aparecem na frente do cubo e da esfera
    _maxila(-1, abertura)
    _maxila( 1, abertura)

    glPopMatrix()
    glDepthMask(GL_TRUE)

    _desenhar_cubo(base_ang, hori_ang, vert_ang)
    _renderizar_hud(base_ang, hori_ang, vert_ang, garra_ang)

    pygame.display.flip()


# ═══════════════════════  Cinemática direta  ═════════════════════════════════

def calcular_posicao_garra(base_ang, hori_ang, vert_ang, garra_ang):
    """
    Posição da garra em mm. Referência: centro da base no plano XY.
      X, Y = posição no plano horizontal
      Z    = altura acima do plano XY  (0 = toca o chão)
      dist = distância 3D até a base
    """
    shoulder_r = math.radians(90.0 - hori_ang)
    forearm_r  = math.radians(90.0 - vert_ang)
    base_r     = math.radians(base_ang - 90.0)

    # ── Posição do PUNHO (fim de L2) → X, Y, Z de posição ──
    dy_punho = L1 * math.sin(shoulder_r) + L2 * math.sin(forearm_r)
    dz_punho = 0.16 + L1 * math.cos(shoulder_r) + L2 * math.cos(forearm_r)

    gl_x = dz_punho * math.sin(base_r)
    gl_z = dz_punho * math.cos(base_r)
    gl_y = L_BASE + 0.96 + dy_punho

    X = gl_x * 25
    Y = gl_z * 25
    Z = gl_y * 25          # coordenada Z do punho (sem garra)

    # ── Distância da PONTA DOS DEDOS até z=0 (plano XY) ──
    # L2 + suporte do pulso (1.52) + corpo dos dedos (GRIP_L)
    # + ponta inclinada: centro 0.34 + metade da caixa 0.30 = 0.64
    ext       = L2 + 1.52 + GRIP_L + 0.64
    dy_ponta  = L1 * math.sin(shoulder_r) + ext * math.sin(forearm_r)
    dist_plano = (L_BASE + 0.96 + dy_ponta) * 25   # 0 = ponta toca o plano XY

    return X, Y, Z, dist_plano


# ═══════════════════════  HUD (painel lateral)  ══════════════════════════════

def _renderizar_hud(base_ang, hori_ang, vert_ang, garra_ang):
    """Desenha painel de informações na lateral direita da janela."""
    if not _fonte_hud:
        return

    X, Y, Z, dist_plano = calcular_posicao_garra(
        base_ang, hori_ang, vert_ang, garra_ang)

    linhas = [
        ("── ÂNGULOS ──────────", (160, 200, 255)),
        (f"  Base     {base_ang:>7.1f} °",  (220, 220, 220)),
        (f"  Ombro    {hori_ang:>7.1f} °",  (220, 220, 220)),
        (f"  Cotovelo {vert_ang:>7.1f} °",  (220, 220, 220)),
        (f"  Garra    {garra_ang:>7.1f} °", (220, 220, 220)),
        ("", None),
        ("── POSIÇÃO (punho) ──", (160, 200, 255)),
        (f"  X  {X:>9.1f} mm", (255, 110, 110)),
        (f"  Y  {Y:>9.1f} mm", (110, 160, 255)),
        (f"  Z  {Z:>9.1f} mm", (110, 220, 130)),
        ("", None),
        ("── PONTA→PLANO XY ───", (160, 200, 255)),
        (f"  {dist_plano:>9.1f} mm",         (255, 220, 80)),
        (f"  (0 = toca o plano)", (110, 110, 110)),
        ("", None),
        ("── CUBO ─────────────", (255, 180, 50)),
        (f"  X {_cubo_pos[0]*25:>10.1f} mm", (255, 180, 50)),
        (f"  Y {_cubo_pos[2]*25:>10.1f} mm", (255, 180, 50)),
        (f"  Z {_cubo_pos[1]*25:>10.1f} mm", (255, 180, 50)),
    ]

    gx, gy, gz = _fingertip_gl(base_ang, hori_ang, vert_ang)
    cx, cy, cz = _cubo_centro()
    d_cubo = math.sqrt((gx-cx)**2 + (gy-cy)**2 + (gz-cz)**2) * 25
    if _cubo_agarro:
        status, cor_st = "AGARRADO", (80, 200, 255)
    elif d_cubo < _CUBO_RAIO * 25:
        status, cor_st = "EM ALCANCE", (80, 255, 100)
    else:
        status, cor_st = "livre", (150, 150, 150)
    linhas += [
        (f"  Dist {d_cubo:>7.1f} mm", (220, 220, 220)),
        (f"  {status}",               cor_st),
        (f"  Setas = mover cubo",     (80, 80, 80)),
    ]

    lh   = _fonte_hud.get_linesize() + 3
    pw   = 210
    ph   = len(linhas) * lh + 16
    surf = pygame.Surface((pw, ph), pygame.SRCALPHA)
    surf.fill((15, 18, 28, 200))

    y = 8
    for texto, cor in linhas:
        if texto and cor:
            surf.blit(_fonte_hud.render(texto, True, cor), (8, y))
        y += lh

    raw  = pygame.image.tostring(surf, "RGBA", True)
    tid  = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, tid)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, pw, ph, 0,
                 GL_RGBA, GL_UNSIGNED_BYTE, raw)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)

    # Mudar para projeção 2D ortográfica
    glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity()
    glOrtho(0, _largura, 0, _altura, -1, 1)
    glMatrixMode(GL_MODELVIEW);  glPushMatrix(); glLoadIdentity()

    glDisable(GL_DEPTH_TEST)
    glDisable(GL_LIGHTING)
    glEnable(GL_TEXTURE_2D)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glColor4f(1, 1, 1, 1)

    x0 = _largura - pw - 10
    y0 = _altura  - ph - 10
    glBegin(GL_QUADS)
    glTexCoord2f(0, 0); glVertex2f(x0,      y0)
    glTexCoord2f(1, 0); glVertex2f(x0 + pw, y0)
    glTexCoord2f(1, 1); glVertex2f(x0 + pw, y0 + ph)
    glTexCoord2f(0, 1); glVertex2f(x0,      y0 + ph)
    glEnd()

    glDisable(GL_TEXTURE_2D)
    glEnable(GL_DEPTH_TEST)
    glEnable(GL_LIGHTING)

    glMatrixMode(GL_PROJECTION); glPopMatrix()
    glMatrixMode(GL_MODELVIEW);  glPopMatrix()

    glDeleteTextures(1, [tid])


# ═════════════════════════════  Classe Braco  ════════════════════════════════

class Braco:
    """
    Estado e controle do braço. Pode ser usado com ou sem visualização 3D.

    Exemplo com visualização:
        braco = braco3d.Braco()
        braco3d.iniciar()
        while braco3d.atualizar(*braco.posicao()):
            braco.ajustar_base(delta)
            braco3d.mover_servo(*braco.posicao())

    Exemplo sem visualização (só servo):
        braco = braco3d.Braco()
        braco.mover(*braco3d.obter_acao("LEVANTAR"))
        braco3d.mover_servo(*braco.posicao())
    """

    def __init__(self, base=90, hori=90, vert=90, garra=0):
        self.base  = base
        self.hori  = hori
        self.vert  = vert
        self.garra = garra

    def mover(self, base, hori, vert, garra):
        self.base, self.hori, self.vert, self.garra = limitar_angulos(base, hori, vert, garra)

    def mover_acao(self, nome_acao):
        """Aplica uma ação pré-definida. Retorna True se encontrou a ação."""
        acao = obter_acao(nome_acao)
        if acao:
            self.mover(*acao)
            return True
        return False

    def posicao(self):
        """Retorna (base, hori, vert, garra)."""
        return (self.base, self.hori, self.vert, self.garra)

    def ajustar_base(self, delta):
        self.mover(self.base + delta, self.hori, self.vert, self.garra)

    def ajustar_horizontal(self, delta):
        self.mover(self.base, self.hori + delta, self.vert, self.garra)

    def ajustar_vertical(self, delta):
        self.mover(self.base, self.hori, self.vert + delta, self.garra)

    def ajustar_garra(self, delta):
        self.mover(self.base, self.hori, self.vert, self.garra + delta)

    def __repr__(self):
        return (f"Braco(base={self.base}, hori={self.hori}, "
                f"vert={self.vert}, garra={self.garra})")


# ═════════════════════════════  Entry point  ════════════════════════════════

if __name__ == "__main__":
    import cv2
    import json as _json

    try:
        with open("dados.json") as _f:
            _dados = _json.load(_f)
        _ini = {k: _dados[0][v] for k, v in [
            ("base",  "angInicial-base"),
            ("hori",  "angInicial-horizontal"),
            ("vert",  "angInicial-vertical"),
            ("garra", "angInicial-garra"),
        ]}
    except Exception:
        _ini = {"base": 90, "hori": 90, "vert": 90, "garra": 0}

    cv2.namedWindow("Controles")
    cv2.createTrackbar("Base",       "Controles", _ini["base"],  180, lambda _: None)
    cv2.createTrackbar("Horizontal", "Controles", _ini["hori"],  180, lambda _: None)
    cv2.createTrackbar("Vertical",   "Controles", _ini["vert"],  180, lambda _: None)
    cv2.createTrackbar("Garra",      "Controles", _ini["garra"], 180, lambda _: None)

    iniciar()

    while True:
        if cv2.waitKey(1) == 27:
            break
        try:
            _base  = cv2.getTrackbarPos("Base",       "Controles")
            _hori  = cv2.getTrackbarPos("Horizontal", "Controles")
            _vert  = cv2.getTrackbarPos("Vertical",   "Controles")
            _garra = cv2.getTrackbarPos("Garra",      "Controles")
        except cv2.error:
            break

        if not atualizar(_base, _hori, _vert, _garra):
            break

    cv2.destroyAllWindows()
    fechar()
