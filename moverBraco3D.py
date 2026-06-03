import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
import cv2
import json
import math

try:
    import servo as serv
    HAS_SERVO = True
except Exception as e:
    print(f"Aviso: Arduino não conectado ({e}). Rodando apenas visualização.")
    HAS_SERVO = False

# ── Dimensões  (1 un ≈ 25 mm) — medidas dos STL ──────────────────────────────
# basement 87.46 mm / round_plate ø72 mm / horizontal_arm 127.5×15×8 mm
# forward_drive_arm 92.46×29×15 mm / fingers 58.42×14×9 mm
L_BASE  = 3.50   # basement  87.46 mm / 25
L1      = 5.10   # horizontal_arm 127.5 mm / 25
L2      = 3.70   # forward_drive_arm 92.46 mm / 25
GRIP_L  = 2.34   # finger 58.42 mm / 25
GRIP_MAX= 0.90   # abertura máxima por lado

# Geometria das chapas do braço
SW   = 0.30   # semi-largura (arm depth 8 mm / 2 / 25 ≈ 0.16, incl. folga = 0.30)
PT   = 0.10   # espessura da chapa
AH   = 0.60   # altura do braço inferior  15 mm / 25
FH   = 1.16   # altura do antebraço       29 mm / 25
PY   = 0.42   # offset Y da barra do paralelogramo (acima de AH/2)

# Cores (R, G, B, A) — alpha 0.68 = semitransparente
ALPHA   = 0.68
LARANJA = (1.00, 0.45, 0.00, ALPHA)
PRETO   = (0.12, 0.12, 0.12, ALPHA)
ESCURO  = (0.05, 0.05, 0.05, ALPHA)
METAL   = (0.55, 0.56, 0.58, ALPHA)
SERVO_C = (0.14, 0.14, 0.20, ALPHA)

_cam_yaw   = 45.0   # visão diagonal frontal
_cam_pitch = 22.0   # ligeiramente acima do braço
_cam_dist  = 24.0   # distância maior para acomodar braço mais alto
_mouse_btn = False
_mouse_pos = (0, 0)


# ═══════════════════════════  OpenGL utils  ══════════════════════════════════

def _init_gl(w, h):
    glEnable(GL_DEPTH_TEST)
    glEnable(GL_LIGHTING)
    glEnable(GL_LIGHT0); glEnable(GL_LIGHT1)
    glEnable(GL_COLOR_MATERIAL)
    glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
    glLightfv(GL_LIGHT0, GL_POSITION, [7.0, 15.0, 8.0, 1.0])
    glLightfv(GL_LIGHT0, GL_DIFFUSE,  [1.0,  1.0,  1.0,  1.0])
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


def _cor(r, g, b, a=ALPHA): glColor4f(r, g, b, a)


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
    for nx,ny,nz,verts in faces:
        glNormal3f(nx,ny,nz)
        for v in verts: glVertex3fv(v)
    glEnd()


def _cyl(r, h, sl=18):
    q = gluNewQuadric(); gluQuadricNormals(q, GLU_SMOOTH)
    gluCylinder(q, r, r, h, sl, 1)
    gluDisk(q, 0, r, sl, 1)
    glTranslatef(0,0,h); glRotatef(180,1,0,0)
    gluDisk(q, 0, r, sl, 1); glRotatef(180,1,0,0)
    glTranslatef(0,0,-h); gluDeleteQuadric(q)


def _sph(r, sl=14):
    q = gluNewQuadric(); gluQuadricNormals(q, GLU_SMOOTH)
    gluSphere(q, r, sl, sl); gluDeleteQuadric(q)


# ═══════════════════════════  Peças do braço  ════════════════════════════════

def _chapas(sw, h, L, n_furos=3):
    """
    Chapas com furos REAIS: frame tipo escada.
    Trilhos horizontais contínuos + pilares sólidos em tampos/divisores.
    Os furos são vazios reais — sem overlay escuro.
    """
    _cor(*LARANJA)

    bH = h  * 0.14                    # espessura dos trilhos horizontal
    ez = max(L * 0.09, 0.28)          # comprimento dos tampos (end caps)
    dz = max(L * 0.05, 0.14)          # largura de cada divisor

    # Calcula comprimento de cada furo
    n_div = n_furos - 1
    furo_z = (L - 2*ez - n_div*dz) / max(n_furos, 1)

    # Lista de segmentos sólidos: (z_início, z_fim)
    segs = [(0.0, ez)]
    z = ez
    for i in range(n_furos):
        z += furo_z
        if i < n_furos - 1:
            segs.append((z, z + dz))
            z += dz
    segs.append((z, L))

    # ── Faces laterais (X = ±sw) ──────────────────────────────────────────
    for sx in (-1, 1):
        xp = sx * sw
        # Trilhos horizontais completos (top e bottom) — ligam tudo
        for sy in (1, -1):
            glPushMatrix()
            glTranslatef(xp, sy * (h - bH) * .5, L * .5)
            _box(PT, bH, L)
            glPopMatrix()
        # Pilares sólidos (tampos + divisores)
        for z0, z1 in segs:
            glPushMatrix()
            glTranslatef(xp, 0, (z0 + z1) * .5)
            _box(PT, h, z1 - z0)
            glPopMatrix()

    # ── Entre as faces: preenchimento só nos segmentos sólidos ───────────
    for z0, z1 in segs:
        glPushMatrix()
        glTranslatef(0, 0, (z0 + z1) * .5)
        _box(sw * 2, h, z1 - z0)
        glPopMatrix()
    # Trilhos entre as faces (top e bottom, comprimento total)
    for sy in (1, -1):
        glPushMatrix()
        glTranslatef(0, sy * (h - bH) * .5, L * .5)
        _box(sw * 2, bH, L)
        glPopMatrix()


def _suporte_U(sw, h, prof):
    """Suporte em U: duas paredes verticais + placa de topo."""
    _cor(*LARANJA)
    ew = 0.09                           # espessura da parede
    # paredes laterais
    for sx in (-1, 1):
        glPushMatrix()
        glTranslatef(sx * (sw + ew*.5), 0, prof*.5)
        _box(ew, h, prof)
        glPopMatrix()
    # placa de topo
    glPushMatrix()
    glTranslatef(0, h*.5 + ew*.5, prof*.5)
    _box(sw*2 + ew*2, ew, prof)
    glPopMatrix()


def _servo():
    """Corpo SG90: caixa escura + flange + corno branco."""
    _cor(*SERVO_C)
    _box(0.86, 0.86, 0.46)   # corpo
    _box(1.08, 0.18, 0.50)   # abas
    glColor4f(0.92, 0.92, 0.92, ALPHA)
    glPushMatrix()
    glTranslatef(0, 0.50, 0)
    glRotatef(-90, 1, 0, 0)
    _cyl(0.09, 0.14, 10)     # corno
    glPopMatrix()


def _engrenagem(r=0.56, n=10):
    """Disco com n dentes — driven_gear: ø28 mm → r=0.56, espessura 7 mm → 0.28."""
    _cor(*LARANJA)
    _cyl(r, 0.28, 20)
    for i in range(n):
        a = math.radians(i * (360.0/n))
        glPushMatrix()
        glTranslatef(math.sin(a)*(r+0.07), math.cos(a)*(r+0.07), 0.08)
        _box(0.18, 0.18, 0.24)
        glPopMatrix()


def _maxila(lado, abertura):
    """Maxila preta — finger STL: 58.42×14×9 mm → 2.34×0.56×0.36 un."""
    _cor(*PRETO)
    x = lado * (0.18 + abertura)
    # corpo principal — começa após claw_support (CLAW_D=1.52)
    glPushMatrix()
    glTranslatef(x, 0.28, 1.52 + GRIP_L * .5)
    _box(0.36, 0.56, GRIP_L)
    glPopMatrix()
    # ponta inclinada para dentro
    glPushMatrix()
    glTranslatef(x + lado * (-0.07), 0.18, 1.52 + GRIP_L + 0.34)
    glRotatef(lado * (-18), 0, 1, 0)
    _box(0.34, 0.50, 0.60)
    glPopMatrix()


def _grid():
    glDisable(GL_LIGHTING)
    glColor3f(0.17, 0.17, 0.21)
    glBegin(GL_LINES)
    for i in range(-9, 10):
        glVertex3f(float(i), 0, -9.0); glVertex3f(float(i), 0, 9.0)
        glVertex3f(-9.0, 0, float(i)); glVertex3f(9.0, 0, float(i))
    glEnd()
    glEnable(GL_LIGHTING)


# ═══════════════════════════════  Cena  ══════════════════════════════════════

def _render(base_ang, hori_ang, vert_ang, garra_ang):
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glLoadIdentity()
    yr = math.radians(_cam_yaw);  pr = math.radians(_cam_pitch)
    ex = _cam_dist * math.cos(pr) * math.sin(yr)
    ey = _cam_dist * math.sin(pr) + 5.5
    ez = _cam_dist * math.cos(pr) * math.cos(yr)
    gluLookAt(ex, ey, ez, 0.0, 5.5, 0.0, 0.0, 1.0, 0.0)
    _grid()
    glDepthMask(GL_FALSE)   # transparentes não bloqueiam uns aos outros
    glPushMatrix()

    # ── BASE: flange plana + pedestal ────────────────────────────────────────
    # round_plate: ø72 mm → r=1.44, h=0.34 | basement: 87.46 mm alto, ø~55 mm → r=1.10
    _cor(*PRETO)
    glPushMatrix(); glRotatef(-90,1,0,0); _cyl(1.44, 0.34, 32); glPopMatrix()  # flange
    glPushMatrix()
    glTranslatef(0, 0.34, 0); glRotatef(-90,1,0,0); _cyl(1.10, L_BASE-0.34, 24)
    glPopMatrix()
    # parafusos de montagem (dentro do raio 1.44)
    _cor(*METAL)
    for cx, cz in [(-1.05,-0.82),(1.05,-0.82),(-1.05,0.82),(1.05,0.82)]:
        glPushMatrix()
        glTranslatef(cx, 0.36, cz); glRotatef(-90,1,0,0)
        _cyl(0.13, 0.10, 6)
        glPopMatrix()
    glTranslatef(0, L_BASE, 0)

    # ── ROTAÇÃO DA BASE ──────────────────────────────────────────────────────
    glRotatef(base_ang - 90, 0, 1, 0)

    # Peça giratória laranja (suporte base)
    _cor(*LARANJA)
    glPushMatrix(); glTranslatef(0, 0.24, 0); _box(1.40, 0.48, 0.90); glPopMatrix()
    glTranslatef(0, 0.48, 0)

    # ── SUPORTE EM U DO OMBRO ────────────────────────────────────────────────
    _suporte_U(SW + 0.10, 1.0, 0.32)

    # Servo de ombro na lateral direita
    glPushMatrix()
    glTranslatef(SW + 0.44, 0.44, 0.12); glRotatef(90, 0, 1, 0); _servo()
    glPopMatrix()
    # pivôs do ombro (cilindros curtos nas duas laterais)
    _cor(*METAL)
    for sx in (-1, 1):
        glPushMatrix()
        glTranslatef(sx * (SW + 0.19), 0.44, 0.16)
        glRotatef(-90, 0, 1, 0); _cyl(0.13, 0.12, 10)
        glPopMatrix()

    # ── CINEMÁTICA DO OMBRO ── (não alterar) ─────────────────────────────────
    shoulder = 90.0 - hori_ang
    glTranslatef(0, 0.48, 0.16)
    glRotatef(-shoulder, 1, 0, 0)   # negativo → braço sobe (+Z → +Y)

    # ── BRAÇO INFERIOR — chapas duplas com 3 furos ───────────────────────────
    _chapas(SW, AH, L1, n_furos=3)

    # ── BRAÇO SUPERIOR — barra plana do paralelogramo ────────────────────────
    # (uma barra única larga + duas barrinhas laterais para dar profundidade)
    _cor(*LARANJA)
    glPushMatrix()
    glTranslatef(0, PY, L1*.50); _box(SW*2, 0.13, L1)
    glPopMatrix()
    for sx in (-SW + 0.04, SW - 0.04):
        glPushMatrix()
        glTranslatef(sx, PY, L1*.50); _box(PT, 0.20, L1)
        glPopMatrix()

    # ── COTOVELO ─────────────────────────────────────────────────────────────
    glTranslatef(0, 0, L1)
    _cor(*LARANJA)
    glPushMatrix(); glTranslatef(0, 0.12, -0.16); _box(SW*2+PT, 0.56, 0.18); glPopMatrix()
    # pivôs cilíndricos integrados (curtos, dentro das chapas)
    _cor(*METAL)
    for sx in (-1, 1):
        glPushMatrix()
        glTranslatef(sx * (SW + 0.04), 0.0, 0)
        glRotatef(-90, 0, 1, 0)
        _cyl(0.12, 0.10, 10)
        glPopMatrix()

    # ── CINEMÁTICA DO ANTEBRAÇO (paralelogramo) ── (não alterar) ─────────────
    glRotatef(shoulder, 1, 0, 0)        # desfaz rotação do ombro
    forearm = 90.0 - vert_ang
    glRotatef(-forearm, 1, 0, 0)        # ângulo absoluto do antebraço

    # ── ANTEBRAÇO — chapas com 2 furos ───────────────────────────────────────
    _chapas(SW * 0.84, FH, L2, n_furos=2)

    glTranslatef(0, 0, L2)

    abertura = (garra_ang / 180.0) * GRIP_MAX

    # ── SUPORTE PULSO — claw_support: 54×25×38 mm → 2.16×1.00×1.52 un ─────────
    CLAW_W = 2.16; CLAW_H = 1.00; CLAW_D = 1.52
    _cor(*LARANJA)
    glPushMatrix()
    glTranslatef(0, CLAW_H*0.5, CLAW_D*0.5); _box(CLAW_W, CLAW_H, CLAW_D)
    glPopMatrix()

    # pivôs laterais
    _cor(*METAL)
    for sx in (-1, 1):
        glPushMatrix()
        glTranslatef(sx * (CLAW_W*0.5 + 0.10), CLAW_H*0.5, CLAW_D*0.5)
        glRotatef(-90, 0, 1, 0); _cyl(0.10, 0.12, 10)
        glPopMatrix()

    # ── ENGRENAGEM — driven_gear ø28×7 mm → r=0.56, gira com garra_ang ──────
    glPushMatrix()
    glTranslatef(0, CLAW_H*0.5 + 0.20, CLAW_D*0.5 + 0.10); glRotatef(-90, 1, 0, 0)
    glRotatef(garra_ang * 2.0, 0, 0, 1)
    _engrenagem()
    glPopMatrix()

    # ── MAXILAS ───────────────────────────────────────────────────────────────
    _maxila(-1, abertura)
    _maxila( 1, abertura)

    glPopMatrix()
    glDepthMask(GL_TRUE)
    pygame.display.flip()


# ════════════════════════════  Loop principal  ═══════════════════════════════

def main():
    global _cam_yaw, _cam_pitch, _cam_dist, _mouse_btn, _mouse_pos

    with open("dados.json") as f:
        dados = json.load(f)
    ini = {k: dados[0][v] for k, v in [
        ("base","angInicial-base"), ("hori","angInicial-horizontal"),
        ("vert","angInicial-vertical"), ("garra","angInicial-garra"),
    ]}

    cv2.namedWindow("Controles")
    cv2.createTrackbar("Base",       "Controles", ini["base"],  180, lambda _: None)
    cv2.createTrackbar("Horizontal", "Controles", ini["hori"],  180, lambda _: None)
    cv2.createTrackbar("Vertical",   "Controles", ini["vert"],  180, lambda _: None)
    cv2.createTrackbar("Garra",      "Controles", ini["garra"], 180, lambda _: None)

    pygame.init()
    pygame.display.set_mode((920, 660), DOUBLEBUF | OPENGL)
    pygame.display.set_caption("Braço Robótico 3D  |  Arraste=girar  |  Scroll=zoom")
    _init_gl(920, 660)
    clock = pygame.time.Clock()

    while True:
        for ev in pygame.event.get():
            if ev.type == QUIT:
                pygame.quit(); cv2.destroyAllWindows(); return
            elif ev.type == MOUSEBUTTONDOWN and ev.button == 1:
                _mouse_btn = True;  _mouse_pos = ev.pos
            elif ev.type == MOUSEBUTTONUP and ev.button == 1:
                _mouse_btn = False
            elif ev.type == MOUSEMOTION and _mouse_btn:
                dx = ev.pos[0] - _mouse_pos[0]
                dy = ev.pos[1] - _mouse_pos[1]
                _cam_yaw  += dx * 0.4
                _cam_pitch = max(-10.0, min(80.0, _cam_pitch - dy * 0.4))
                _mouse_pos = ev.pos
            elif ev.type == MOUSEWHEEL:
                _cam_dist = max(4.0, min(30.0, _cam_dist - ev.y * 0.5))

        if cv2.waitKey(1) == 27:
            break
        try:
            base  = cv2.getTrackbarPos("Base",       "Controles")
            hori  = cv2.getTrackbarPos("Horizontal", "Controles")
            vert  = cv2.getTrackbarPos("Vertical",   "Controles")
            garra = cv2.getTrackbarPos("Garra",      "Controles")
        except cv2.error:
            break

        if HAS_SERVO:
            serv.mover(base, hori, vert, garra)

        _render(base, hori, vert, garra)
        clock.tick(30)

    pygame.quit()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
