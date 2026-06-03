# Controle de Braço Robótico

Projeto de controle de braço robótico com Arduino, visualização 3D em OpenGL e controle por IA local (LLaMA via Ollama).

## Arquitetura

```
prompts/prompt.txt ──→ ia_braco.py (IA Ollama / LLaMA)
                              ↓
camera.py ────────────→ executar_acao()  ←──── moverBracoJostick.py
                              ↓
                         braco3d.py (visualização 3D OpenGL)
                              ↓
                          servo.py (Arduino via pyFirmata)

controle_braco.py ─────→ uso direto (sem visualização, lógica pura)
moverBraco3D.py ───────→ 3D standalone com sliders (auto-contido)
```

## Dependências

```powershell
pip install -r requirements.txt
pip install ollama
```

`requirements.txt` inclui: numpy, opencv-python, pygame, pyFirmata, pyserial, PyOpenGL, ollama

## Arquivos

| Arquivo | Descrição |
|---|---|
| `braco3d.py` | Módulo central: visualização 3D OpenGL + estado do braço + ações pré-definidas |
| `controle_braco.py` | Módulo de lógica pura: ACOES, ControladorBraco, funções utilitárias (sem OpenGL) |
| `ia_braco.py` | Controle por linguagem natural via LLaMA (Ollama) com visualização 3D |
| `moverBraco3D.py` | Script standalone: visualização 3D com sliders OpenCV (auto-contido, não depende de braco3d) |
| `moverBracoJostick.py` | Controle por joystick com visualização 3D |
| `moverBraco.py` | Controle manual por sliders OpenCV (requer Arduino) |
| `camera.py` | Rastreamento de objeto vermelho pela câmera; aciona sequências automáticas de pega |
| `servo.py` | Driver do Arduino: movimento gradual suave dos servos via pyFirmata (inicialização lazy) |
| `dados.json` | Configuração: porta COM, pinos e ângulos iniciais |
| `memoria.json` | Histórico dos últimos 5 comandos (gerado automaticamente) |
| `prompts/prompt.txt` | System prompt do LLaMA: traduz linguagem natural em nomes de ação |

## Modos de uso

### Visualização 3D + sliders (modo demonstração)
```powershell
python braco3d.py
```
Abre janela OpenGL com sliders OpenCV. Arraste o mouse para girar a câmera, scroll para zoom.

### Visualização 3D standalone
```powershell
python moverBraco3D.py
```
Versão auto-contida da visualização 3D com sliders. Não depende do módulo `braco3d`. Conecta ao Arduino se disponível.

### Controle por IA local (linguagem natural)
```powershell
# 1. Tenha o Ollama instalado e rodando: https://ollama.com
ollama pull llama3        # ou: phi3, mistral, gemma
# 2. Inicie o agente
python ia_braco.py
```
Digite comandos em português: `"pega o objeto"`, `"vá para a esquerda"`, `"cumprimenta"`.  
O LLaMA traduz para sequências de ação usando o `prompts/prompt.txt`.

### Controle por joystick
```powershell
python moverBracoJostick.py
```
Analógico esquerdo: base e ombro. Analógico direito Y: antebraço. Botões X/O: abrir/fechar garra.

### Controle por câmera (rastreamento automático)
```powershell
python camera.py
```
Detecta objeto vermelho e move o braço para segui-lo. Quando centralizado e próximo, executa sequência de pega automática.

### Controle por sliders (com Arduino)
```powershell
python moverBraco.py
```
Requer Arduino conectado. Controla os servos diretamente via sliders OpenCV sem visualização 3D.

## Módulo `braco3d`

O `braco3d.py` é um módulo reutilizável. Exemplo de integração:

```python
import braco3d

braco3d.iniciar()                          # abre janela OpenGL
braco = braco3d.Braco()                    # estado do braço

while braco3d.atualizar(*braco.posicao()): # loop 30 fps
    braco.mover_acao("LEVANTAR")
    braco3d.mover_servo(*braco.posicao())  # envia ao Arduino (se conectado)
```

### Ações pré-definidas (ACOES)

Convenção de ângulos: `h < 90` → braço sobe | `h > 90` → braço desce

| Categoria | Ações |
|---|---|
| Posição | `REPOUSO`, `CENTRO`, `LEVANTAR`, `ABAIXAR`, `LEVANTAR_MAXIMO`, `ABAIXAR_MAXIMO` |
| Direção | `ESQUERDA`, `DIREITA`, `ESQUERDA_SUAVE`, `DIREITA_SUAVE`, `EXTREMA_ESQUERDA`, `EXTREMA_DIREITA` |
| Garra | `ABRIR_GARRA`, `FECHAR_GARRA` |
| Interação | `PREPARAR_PEGA`, `PEGAR_OBJETO`, `LEVANTAR_OBJETO`, `SOLTAR_OBJETO`, `TOCAR_MESA`, `COLETAR` |
| Comportamento | `OBSERVAR`, `PROCURAR`, `INVESTIGAR`, `CUMPRIMENTAR`, `OLHAR_CIMA`, `OLHAR_BAIXO` |
| Modos | `MODO_ALERTA`, `MODO_DESCANSO`, `MODO_CURIOSO`, `MODO_VIGIA`, `RETRAIR`, `PROTEGER` |

### API do módulo

```python
braco3d.iniciar(largura, altura, titulo)     # cria janela
braco3d.atualizar(base, hori, vert, garra)   # renderiza + processa eventos; retorna False ao fechar
braco3d.mover_suave(braco, b, h, v, g)       # animação interpolada até a posição alvo
braco3d.mover_servo(base, hori, vert, garra) # envia ao Arduino (silencioso se não conectado)
braco3d.fechar()                             # fecha janela
braco3d.esta_aberto()                        # True se janela ativa
braco3d.obter_acao("LEVANTAR")               # retorna (base, hori, vert, garra) ou None
braco3d.listar_acoes()                       # lista de nomes de ações
braco3d.limitar_angulos(b, h, v, g)          # clampa em [0, 180]
```

### Classe `Braco`

```python
braco = braco3d.Braco(base=90, hori=90, vert=90, garra=0)
braco.mover(base, hori, vert, garra)   # move com clamping
braco.mover_acao("LEVANTAR")           # ação pré-definida
braco.posicao()                        # retorna (base, hori, vert, garra)
braco.ajustar_base(delta)              # incrementa/decrementa
braco.ajustar_horizontal(delta)
braco.ajustar_vertical(delta)
braco.ajustar_garra(delta)
```

## Módulo `controle_braco`

O `controle_braco.py` contém a lógica de controle sem dependências de visualização. Útil para scripts que controlam o Arduino diretamente sem abrir janela OpenGL.

```python
import controle_braco

# Funções utilitárias
controle_braco.obter_acao("LEVANTAR")        # retorna (base, hori, vert, garra) ou None
controle_braco.listar_acoes()                # lista de nomes de ações
controle_braco.limitar_angulos(b, h, v, g)   # clampa em [0, 180]
```

### Classe `ControladorBraco`

```python
ctrl = controle_braco.ControladorBraco(base=90, hori=90, vert=90, garra=0)
ctrl.mover(base, hori, vert, garra)    # move com clamping + registra no histórico
ctrl.mover_acao("LEVANTAR")            # ação pré-definida; retorna True/False
ctrl.obter_posicao()                   # retorna (base, hori, vert, garra)
ctrl.ajustar_base(delta)               # incrementa/decrementa
ctrl.ajustar_horizontal(delta)
ctrl.ajustar_vertical(delta)
ctrl.ajustar_garra(delta)
ctrl.obter_historico()                 # lista de posições registradas
ctrl.limpar_historico()
```

## Visualização 3D

- **Câmera**: arraste o mouse para orbitar, scroll para zoom
- **Eixos**: X vermelho (plano), Y azul (plano), Z verde (vertical/cima)
- **Grid**: 18×18 células no plano XY
- **Braço**: renderizado em OpenGL com peças detalhadas (chapas com furos, servos, engrenagem, maxilas)
- **Transparência**: alfa 0.68 para visualizar a estrutura interna

## Configuração do Arduino (`dados.json`)

```json
[{
    "porta-com": "COM3",
    "pin-base": 9,
    "pin-horizontal": 10,
    "pin-vertical": 11,
    "pin-garra": 6,
    "angInicial-base": 90,
    "angInicial-horizontal": 90,
    "angInicial-vertical": 90,
    "angInicial-garra": 0
}]
```

## Configuração do modelo de IA (`ia_braco.py`)

Edite a linha no topo do arquivo:
```python
MODELO_IA = "llama3"   # ou: phi3, mistral, gemma:2b
```
Modelos menores (`phi3`, `gemma:2b`) respondem mais rápido para esta tarefa de tradução de comandos.

## Notas

- O Arduino é opcional em `braco3d.py`, `ia_braco.py`, `moverBracoJostick.py` e `camera.py`: sem ele, o modo de visualização funciona normalmente
- `moverBraco.py` requer Arduino conectado (importação direta de `servo`)
- `servo.py` usa inicialização lazy: conecta ao Arduino apenas na primeira chamada a `mover()`
- `memoria.json` é criado automaticamente e mantém os últimos 5 comandos como contexto para a IA
- O `servo.py` move cada servo gradualmente (1° por vez, 30ms entre passos) para suavidade
- A thread de IA e a thread do servo são separadas do loop pygame — a janela 3D nunca trava durante consultas ao LLaMA
