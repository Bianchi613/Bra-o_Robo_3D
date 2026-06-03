"""
ia_braco.py — Controle inteligente do braço robótico.

Arquitetura de threads:
  Thread principal  → loop pygame 30 fps (janela sempre responsiva)
  Thread IA         → input() + Ollama (sem bloquear a janela)
  Thread servo      → movimento físico gradual (sem bloquear a janela)
"""

import json
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
    return "\n".join(
        f"Comando: {m['comando']} → {m['acao']}"
        for m in MEMORIA
    )

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
# IA LOCAL (Ollama)
# =========================

def _ollama_disponivel() -> bool:
    try:
        import ollama  # noqa
        return True
    except ImportError:
        print("[erro] 'ollama' não instalado. Execute: pip install ollama")
        return False


def traduzir_para_acoes(texto: str) -> str:
    if not _ollama_disponivel():
        return ""
    import ollama
    historico = gerar_historico()
    conteudo = f"Histórico:\n{historico}\n\nNovo comando: {texto}" if historico else texto
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
# (nunca bloqueia o pygame)
# =========================

def _thread_ia():
    print(f"\n=== Braço Robótico — IA Local ({MODELO_IA}) ===")
    print("Digite comandos em linguagem natural. ENTER vazio para sair.\n")

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
            if acao:
                _fila.put(acao)

# =========================
# LOOP PRINCIPAL (thread principal)
# Roda a 30 fps — janela sempre responsiva
# =========================

def main():
    braco3d.iniciar()

    # inicia thread de IA em background
    threading.Thread(target=_thread_ia, daemon=True).start()

    # estado de animação
    PASSOS           = 25    # frames por movimento (~0.8 s a 30 fps)
    PAUSA_ACOES      = 8     # frames de pausa entre ações consecutivas

    b0, h0, v0, g0              = braco.posicao()
    b_alvo, h_alvo, v_alvo, g_alvo = braco.posicao()
    passo = PASSOS              # começa "parado" (sem animar)
    pausa = 0

    while True:
        # --- tenta buscar próxima ação quando parou de animar ---
        if passo >= PASSOS and pausa <= 0:
            try:
                item = _fila.get_nowait()
            except queue.Empty:
                item = _VAZIO

            if item is None:                    # sinal de encerrar
                break

            if item is not _VAZIO:              # nova ação
                angulos = braco3d.obter_acao(item)
                if angulos:
                    b0, h0, v0, g0 = braco.posicao()
                    b_alvo, h_alvo, v_alvo, g_alvo = angulos
                    braco.mover(*angulos)
                    # servo físico em thread separada (não bloqueia o loop)
                    threading.Thread(
                        target=braco3d.mover_servo,
                        args=angulos,
                        daemon=True,
                    ).start()
                    print(f"  [{item}]")
                    passo = 0
                    pausa = PAUSA_ACOES
                else:
                    print(f"  [aviso] Ação desconhecida: {item}")

        if pausa > 0:
            pausa -= 1

        # --- interpolação suave ---
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


# sentinela interna para distinguir "fila vazia" de "item None"
_VAZIO = object()


if __name__ == "__main__":
    main()
