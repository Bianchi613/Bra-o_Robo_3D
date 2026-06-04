"""
ia_braco.py — Controle inteligente do braço robótico com suporte a xadrez.

Arquitetura de threads:
  Thread principal  → loop pygame 30 fps (janela sempre responsiva)
  Thread IA         → input() + Ollama LLaMA (sem bloquear a janela)
  Thread servo      → movimento físico gradual (sem bloquear a janela)

Comandos especiais retornados pelo LLaMA:
  MOVER:E4          → pega o Rei Branco e deposita na casa E4
  _ANG_b,h,v,g      → ângulos diretos (uso interno do mover_peca)
"""

import json
import math
import re
import time
import threading
import queue
import braco3d

# =========================
# CONFIGURAÇÃO
# =========================

MODELO_IA = "llama3"   # llama3, mistral, phi3, gemma...

try:
    with open("prompts/prompt.txt", "r", encoding="utf-8") as f:
        SYSTEM_PROMPT = f.read()
except FileNotFoundError:
    SYSTEM_PROMPT = ""

try:
    with open("memoria.json", "r", encoding="utf-8") as f:
        MEMORIA = json.load(f)
except Exception:
    MEMORIA = []

braco = braco3d.Braco()

# fila de ações produzidas pela thread de IA
# None = sinal para encerrar o loop principal
_fila: queue.Queue = queue.Queue()
_VAZIO = object()

# =========================
# MEMÓRIA
# =========================

def salvar_memoria(comando: str, acao: str):
    MEMORIA.append({"comando": comando, "acao": acao})
    if len(MEMORIA) > 5:
        MEMORIA.pop(0)
    with open("memoria.json", "w", encoding="utf-8") as f:
        json.dump(MEMORIA, f, indent=4, ensure_ascii=False)


def gerar_historico() -> str:
    linhas = [f"Comando: {m['comando']} → {m['acao']}" for m in MEMORIA]
    return "\n".join(linhas)

# =========================
# CINEMÁTICA INVERSA (IK)
# =========================
# Constantes do braço (mesmas do braco3d)
_L_BASE   = 3.50
_L1       = 5.10
_L2       = 3.70
_GRIP_L   = 2.34
# O agarro é detectado pelo CENTRO da garra (midpoint entre os dedos),
# não pela ponta. Usar essa distância garante que o IK aponte o centro
# da garra para o alvo, ativando o agarro automático do braco3d.
_EXT = _L2 + 1.52 + _GRIP_L * 0.5   # elbow → centro da garra = 6.39 un


def ik_para_ponto(x_gl: float, y_gl: float, z_gl: float):
    """
    Cinemática inversa 2-link para posicionar a garra em (x, y, z) GL.

    Retorna (base, hori, vert) em graus inteiros, ou None se inalcançável.
    O cotovelo alto é preferido (braço arqueado por cima da peça).
    """
    # Ângulo de rotação da base (horizontal)
    base = max(0, min(180, int(math.degrees(math.atan2(x_gl, z_gl)) + 90)))

    # Distância horizontal total + altura relativa ao pivot do ombro
    d   = math.sqrt(x_gl**2 + z_gl**2)
    dx  = d - 0.16                    # desconta offset do pivot
    dy  = y_gl - (_L_BASE + 0.96)

    rxy = math.sqrt(dx**2 + dy**2)
    C   = (dx**2 + dy**2 + _EXT**2 - _L1**2) / (2.0 * _EXT)

    if rxy < 1e-6 or abs(C) > rxy:
        return None                   # ponto fora do workspace

    phi   = math.atan2(dy, dx)
    delta = math.acos(max(-1.0, min(1.0, C / rxy)))

    for sign in [-1, 1]:              # -1 = cotovelo alto (preferido)
        fr = phi + sign * delta
        sr = math.atan2(dy - _EXT * math.sin(fr),
                        dx - _EXT * math.cos(fr))
        h  = int(90.0 - math.degrees(sr))
        v  = int(90.0 - math.degrees(fr))
        if 0 <= h <= 180 and 0 <= v <= 180:
            return base, h, v

    return None

# =========================
# XADREZ — conversão e movimento
# =========================

def casa_para_gl(casa: str):
    """'E4' → (x_gl, z_gl) — centro da casa em coords OpenGL."""
    col = "ABCDEFGH".index(casa[0].upper())
    row = int(casa[1]) - 1
    return (braco3d._TAB_OX + (col + 0.5) * braco3d._TAB_TAM,
            braco3d._TAB_OZ + (row + 0.5) * braco3d._TAB_TAM)


def _enqueue_ang(x: float, y: float, z: float, garra: int) -> bool:
    """Calcula IK e insere '_ANG_b,h,v,g' na fila. False se inalcançável."""
    ang = ik_para_ponto(x, y, z)
    if ang is None:
        print(f"  [IK] inalcançável ({x:.2f}, {y:.2f}, {z:.2f})")
        return False
    b, h, v = ang
    _fila.put(f"_ANG_{b},{h},{v},{garra}")
    return True


def mover_peca(destino: str) -> bool:
    """
    Pega o Rei Branco da casa atual e deposita em 'destino'.
    Coloca a sequência de passos na fila — o loop principal anima cada um.

    Sequência exata (10 passos):
      1. Levantar o braço        → posição segura antes de qualquer movimento
      2. Ir acima da origem      → sobrevoar a peça com garra aberta
      3. Abrir a garra           → garantir garra aberta antes de descer
      4. Descer até a peça       → garra aberta, posicionar sobre o Rei
      5. Fechar a garra          → pegar a peça (agarro automático ativado)
      6. Levantar com a peça     → subir com o Rei preso na garra
      7. Voar até o destino      → mover horizontalmente em altitude segura
      8. Descer no destino       → baixar a garra com a peça sobre a casa
      9. Abrir a garra           → soltar a peça na casa destino
     10. Voltar à posição inicial → REPOUSO
    """
    origem = braco3d.get_rei_casa()
    if not origem:
        print("  [xadrez] Peça não está no tabuleiro.")
        return False

    destino = destino.upper().strip()
    if destino == origem:
        print(f"  [xadrez] Peça já está em {destino}.")
        return True

    if not re.match(r"^[A-H][1-8]$", destino):
        print(f"  [xadrez] Casa inválida: '{destino}'")
        return False

    ox, oz = casa_para_gl(origem)
    dx, dz = casa_para_gl(destino)

    TY   = 3.5   # y de trânsito: altura segura para se mover
    GY   = 0.50  # y de descida: centro da garra sobre a peça
    OPEN = 90    # garra aberta
    SHUT = 0     # garra fechada

    print(f"\n  ♟  Rei Branco: {origem} → {destino}")
    salvar_memoria(f"mover rei para {destino}", f"MOVER:{destino}")

    ok = True

    # ── Passo 1: levantar o braço antes de qualquer movimento ──────────────
    _fila.put("LEVANTAR_MAXIMO")

    # ── Passo 2: ir acima da peça (garra aberta) ───────────────────────────
    ok &= _enqueue_ang(ox, TY, oz, OPEN)

    # ── Passo 3: abrir a garra (garantia) ─────────────────────────────────
    ok &= _enqueue_ang(ox, TY, oz, OPEN)

    # ── Passo 4: descer até a peça (garra aberta) ─────────────────────────
    ok &= _enqueue_ang(ox, GY, oz, OPEN)

    # ── Passo 5: fechar a garra → pega a peça ────────────────────────────
    ok &= _enqueue_ang(ox, GY, oz, SHUT)

    # ── Passo 6: levantar com a peça ──────────────────────────────────────
    ok &= _enqueue_ang(ox, TY, oz, SHUT)

    # ── Passo 7: voar horizontalmente até o destino ───────────────────────
    ok &= _enqueue_ang(dx, TY, dz, SHUT)

    # ── Passo 8: descer no destino (peça ainda agarrada) ─────────────────
    ok &= _enqueue_ang(dx, GY, dz, SHUT)

    # ── Passo 9: abrir a garra → solta a peça ────────────────────────────
    ok &= _enqueue_ang(dx, GY, dz, OPEN)

    # ── Passo 10: voltar à posição inicial ───────────────────────────────
    _fila.put("REPOUSO")

    if not ok:
        print("  [xadrez] Atenção: algum ponto da sequência é inalcançável.")
    return ok

# =========================
# EXECUÇÃO DIRETA (camera.py usa isso)
# =========================

def executar_acao(nome_acao: str) -> bool:
    """Executa uma ação pelo nome. Usado por camera.py como módulo."""
    angulos = braco3d.obter_acao(nome_acao)
    if angulos is None:
        print(f"  [aviso] Ação desconhecida: {nome_acao}")
        return False
    braco.mover(*angulos)
    braco3d.mover_servo(*angulos)
    salvar_memoria(nome_acao, nome_acao)
    print(f"  [{nome_acao}]")
    return True


def executar_sequencia(acoes_texto: str, pausa: float = 0.8):
    for acao in acoes_texto.split(","):
        executar_acao(acao.strip().upper())
        time.sleep(pausa)


def listar_acoes():
    return braco3d.listar_acoes()

# =========================
# IA LOCAL (Ollama + LLaMA)
# =========================

def _ollama_disponivel() -> bool:
    try:
        import ollama  # noqa
        return True
    except ImportError:
        print("[erro] 'ollama' não instalado. Execute: pip install ollama")
        return False


def traduzir_para_acoes(texto: str) -> str:
    """Envia o texto ao LLaMA com contexto da posição atual da peça."""
    if not _ollama_disponivel():
        return ""
    import ollama

    historico = gerar_historico()

    # Informa ao LLaMA a posição atual do rei
    casa_atual = braco3d.get_rei_casa()
    contexto_xadrez = (
        f"Estado atual: Rei Branco está na casa {casa_atual}."
        if casa_atual else
        "Estado atual: Rei Branco está fora do tabuleiro."
    )

    partes = []
    if historico:
        partes.append(f"Histórico:\n{historico}")
    partes.append(contexto_xadrez)
    partes.append(f"Novo comando: {texto}")
    conteudo = "\n\n".join(partes)

    resposta = ollama.chat(
        model=MODELO_IA,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": conteudo},
        ],
        options={"temperature": 0.0},
    )
    return resposta["message"]["content"].strip().upper()

# =========================
# THREAD: input + IA
# =========================

def _thread_ia():
    print(f"\n=== Braço Robótico — IA Local ({MODELO_IA}) ===")
    print("Digite comandos em português.")
    print("Exemplo: 'mova o rei branco de E4 para A1'")
    print("ENTER vazio para sair.\n")

    while True:
        print(">> ", end="", flush=True)
        try:
            texto = input().strip()
        except (EOFError, KeyboardInterrupt):
            _fila.put(None)
            return

        if not texto:
            _fila.put(None)
            return

        print(f"Consultando {MODELO_IA}...", end=" ", flush=True)
        try:
            resposta = traduzir_para_acoes(texto)
        except Exception as e:
            print(f"\n[erro Ollama] {e}")
            print("Verifique: ollama serve")
            continue

        if not resposta:
            continue

        print(f"→ {resposta}")
        salvar_memoria(texto, resposta)

        for acao in resposta.split(","):
            acao = acao.strip()
            if not acao:
                continue

            # Comando de movimento de peça: MOVER:H5
            if acao.startswith("MOVER:"):
                destino = acao[6:].strip()
                mover_peca(destino)   # coloca sequência _ANG_ na fila

            else:
                _fila.put(acao)

# =========================
# LOOP PRINCIPAL (thread principal)
# Roda a 30 fps — janela sempre responsiva
# =========================

def main():
    braco3d.iniciar()

    threading.Thread(target=_thread_ia, daemon=True).start()

    PASSOS      = 25   # frames por movimento (~0.8 s a 30 fps)
    PAUSA_ACOES = 8    # frames de pausa entre ações consecutivas

    b0, h0, v0, g0                  = braco.posicao()
    b_alvo, h_alvo, v_alvo, g_alvo = braco.posicao()
    passo = PASSOS
    pausa = 0

    while True:
        if passo >= PASSOS and pausa <= 0:
            try:
                item = _fila.get_nowait()
            except queue.Empty:
                item = _VAZIO

            if item is None:
                break

            if item is not _VAZIO:
                angulos = None

                # ── Ângulos diretos do IK (MOVER interno) ────────────────
                if isinstance(item, str) and item.startswith("_ANG_"):
                    try:
                        parts  = item[5:].split(",")
                        angulos = tuple(int(x) for x in parts)
                        print(f"  [IK] base={angulos[0]} hori={angulos[1]}"
                              f" vert={angulos[2]} garra={angulos[3]}")
                    except Exception as e:
                        print(f"  [_ANG_ erro] {e}")

                # ── Ação pré-definida (LEVANTAR, REPOUSO, etc.) ──────────
                else:
                    angulos = braco3d.obter_acao(item)
                    if angulos:
                        print(f"  [{item}]")
                    else:
                        print(f"  [aviso] Ação desconhecida: {item}")

                if angulos and len(angulos) == 4:
                    b0, h0, v0, g0 = braco.posicao()
                    b_alvo, h_alvo, v_alvo, g_alvo = angulos
                    braco.mover(*angulos)
                    threading.Thread(
                        target=braco3d.mover_servo,
                        args=angulos,
                        daemon=True,
                    ).start()
                    passo = 0
                    pausa = PAUSA_ACOES

        if pausa > 0:
            pausa -= 1

        # Interpolação suave
        if passo < PASSOS:
            passo += 1
            t = passo / PASSOS
            b = int(b0 + (b_alvo - b0) * t)
            h = int(h0 + (h_alvo - h0) * t)
            v = int(v0 + (v_alvo - v0) * t)
            g = int(g0 + (g_alvo - g0) * t)
        else:
            b, h, v, g = b_alvo, h_alvo, v_alvo, g_alvo

        if not braco3d.atualizar(b, h, v, g):
            break

    braco3d.fechar()


if __name__ == "__main__":
    main()
