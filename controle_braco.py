"""
Módulo de controle do braço robótico.
Reutilizável em qualquer script que queira controlar o braço.
"""

# ── Dimensões e constantes ─────────────────────────────────────────────────
L_BASE  = 3.50   # basement  87.46 mm / 25
L1      = 5.10   # horizontal_arm 127.5 mm / 25
L2      = 3.70   # forward_drive_arm 92.46 mm / 25
GRIP_L  = 2.34   # finger 58.42 mm / 25
GRIP_MAX= 0.90   # abertura máxima por lado

# Limites dos ângulos
ANGULOS_LIMITES = {
    "base": (0, 180),
    "horizontal": (0, 180),
    "vertical": (0, 180),
    "garra": (0, 180)
}

# Ações pré-definidas
ACOES = {
    "REPOUSO": (90, 90, 90, 0),
    "ESQUERDA": (40, 110, 100, 0),
    "DIREITA": (140, 110, 100, 0),
    "CENTRO": (90, 110, 100, 0),
    "LEVANTAR": (90, 130, 140, 0),
    "ABAIXAR": (90, 80, 60, 0),
    "LEVANTAR_MAXIMO": (90, 140, 140, 0),
    "ABAIXAR_MAXIMO": (90, 70, 50, 0),
    "ABRIR_GARRA": (90, 100, 90, 180),
    "FECHAR_GARRA": (90, 100, 90, 0),
    "ESQUERDA_SUAVE": (60, 110, 100, 0),
    "DIREITA_SUAVE": (120, 110, 100, 0),
    "OLHAR_CIMA": (90, 130, 120, 0),
    "OLHAR_BAIXO": (90, 80, 70, 0),
    "PREPARAR_PEGA": (90, 100, 70, 180),
    "PEGAR_OBJETO": (90, 80, 60, 0),
    "LEVANTAR_OBJETO": (90, 130, 130, 0),
    "SOLTAR_OBJETO": (90, 90, 70, 180),
    "CUMPRIMENTAR": (90, 140, 120, 0),
    "OBSERVAR": (90, 120, 110, 0),
    "PROCURAR": (70, 120, 100, 0),
    "INVESTIGAR": (110, 120, 90, 0),
    "EXTREMA_ESQUERDA": (20, 110, 100, 0),
    "EXTREMA_DIREITA": (160, 110, 100, 0),
    "RETRAIR": (90, 140, 140, 0),
    "PROTEGER": (90, 130, 120, 0),
    "TOCAR_MESA": (90, 70, 50, 0),
    "COLETAR": (90, 75, 55, 180),
    "MODO_ALERTA": (90, 140, 100, 0),
    "MODO_DESCANSO": (90, 90, 90, 0),
    "MODO_CURIOSO": (70, 130, 110, 0),
    "MODO_VIGIA": (110, 140, 120, 0)
}


def limitar_angulos(base, hori, vert, garra):
    """
    Limita os ângulos dentro dos ranges permitidos.
    
    Args:
        base: ângulo da base
        hori: ângulo horizontal
        vert: ângulo vertical
        garra: ângulo da garra
        
    Returns:
        (base_limitado, hori_limitado, vert_limitado, garra_limitado)
    """
    return (
        max(0, min(180, base)),
        max(0, min(180, hori)),
        max(0, min(180, vert)),
        max(0, min(180, garra))
    )


def obter_acao(nome_acao):
    """
    Retorna os ângulos para uma ação pré-definida.
    
    Args:
        nome_acao: nome da ação (ex: "REPOUSO", "ESQUERDA")
        
    Returns:
        (base, hori, vert, garra) ou None se ação não existir
    """
    return ACOES.get(nome_acao.upper())


def listar_acoes():
    """Retorna lista de todas as ações disponíveis."""
    return list(ACOES.keys())


class ControladorBraco:
    """Classe para gerenciar o estado do braço."""
    
    def __init__(self, base=90, hori=90, vert=90, garra=0):
        """Inicializa posição do braço."""
        self.base = base
        self.hori = hori
        self.vert = vert
        self.garra = garra
        self.historico = []
    
    def mover(self, base, hori, vert, garra):
        """Move o braço para nova posição."""
        self.base, self.hori, self.vert, self.garra = limitar_angulos(base, hori, vert, garra)
        self.historico.append({
            "base": self.base,
            "hori": self.hori,
            "vert": self.vert,
            "garra": self.garra
        })
    
    def mover_acao(self, nome_acao):
        """Move o braço para uma ação pré-definida."""
        acao = obter_acao(nome_acao)
        if acao:
            self.mover(*acao)
            return True
        return False
    
    def obter_posicao(self):
        """Retorna posição atual: (base, hori, vert, garra)"""
        return (self.base, self.hori, self.vert, self.garra)
    
    def ajustar_base(self, delta):
        """Ajusta base por delta graus."""
        self.mover(self.base + delta, self.hori, self.vert, self.garra)
    
    def ajustar_horizontal(self, delta):
        """Ajusta horizontal por delta graus."""
        self.mover(self.base, self.hori + delta, self.vert, self.garra)
    
    def ajustar_vertical(self, delta):
        """Ajusta vertical por delta graus."""
        self.mover(self.base, self.hori, self.vert + delta, self.garra)
    
    def ajustar_garra(self, delta):
        """Ajusta garra por delta graus."""
        self.mover(self.base, self.hori, self.vert, self.garra + delta)
    
    def limpar_historico(self):
        """Limpa histórico de movimentos."""
        self.historico = []
    
    def obter_historico(self):
        """Retorna histórico de movimentos."""
        return self.historico.copy()
