import sqlite3
from datetime import datetime
from typing import List, Tuple, Optional

DB_NAME = "pendencias.db"


def get_connection() -> sqlite3.Connection:
    """Cria conexão isolada com o SQLite e ativa o modo Write-Ahead Logging."""
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db() -> None:
    """Inicializa as tabelas e índices necessários para consultas eficientes."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pendencias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titulo TEXT NOT NULL,
                descricao TEXT,
                tipo TEXT NOT NULL,
                projeto TEXT NOT NULL,
                campanha TEXT NOT NULL,
                prazo DATE NOT NULL,
                status TEXT CHECK(status IN ('PENDENTE', 'CONCLUIDO')) DEFAULT 'PENDENTE',
                data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP,
                data_conclusao DATETIME
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON pendencias(status);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_prazo ON pendencias(prazo);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_filtros ON pendencias(tipo, projeto, campanha);")
        conn.commit()


def add_pendencia(titulo: str, descricao: str, tipo: str, projeto: str, campanha: str, prazo: str) -> None:
    """Insere registro com sanitização estrita e query parametrizada."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO pendencias (titulo, descricao, tipo, projeto, campanha, prazo)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            titulo.strip(),
            descricao.strip() if descricao else "",
            tipo.strip().upper(),
            projeto.strip().upper(),
            campanha.strip().upper(),
            prazo
        ))
        conn.commit()


def update_status(pendencia_id: int, novo_status: str) -> None:
    """Atualiza o status da pendência e registra a data/hora de conclusão quando aplicável."""
    data_conclusao = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if novo_status == "CONCLUIDO" else None
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE pendencias 
            SET status = ?, data_conclusao = ?
            WHERE id = ?
        """, (novo_status, data_conclusao, pendencia_id))
        conn.commit()


def get_filtered_pendencias(
    status: Optional[str] = None,
    tipo: Optional[str] = None,
    projeto: Optional[str] = None,
    campanha: Optional[str] = None,
    busca: Optional[str] = None
) -> List[Tuple]:
    """Recupera registros com filtros combinados e ordenação por prazo de entrega."""
    query = """
        SELECT id, titulo, descricao, tipo, projeto, campanha, prazo, status, data_criacao, data_conclusao 
        FROM pendencias 
        WHERE 1=1
    """
    params = []

    if status and status != "TODOS":
        query += " AND status = ?"
        params.append(status)
    if tipo and tipo != "TODOS":
        query += " AND tipo = ?"
        params.append(tipo)
    if projeto and projeto != "TODOS":
        query += " AND projeto = ?"
        params.append(projeto)
    if campanha and campanha != "TODOS":
        query += " AND campanha = ?"
        params.append(campanha)
    if busca:
        query += " AND (titulo LIKE ? OR descricao LIKE ?)"
        termo_busca = f"%{busca.strip()}%"
        params.extend([termo_busca, termo_busca])

    query += " ORDER BY prazo ASC, data_criacao DESC"

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()


def get_distinct_values(column: str) -> List[str]:
    """Retorna valores únicos existentes para popular seletores na interface."""
    colunas_validas = {"tipo", "projeto", "campanha"}
    if column not in colunas_validas:
        raise ValueError("Coluna inválida para recuperação de valores distintos.")

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"SELECT DISTINCT {column} FROM pendencias ORDER BY {column} ASC")
        return [row[0] for row in cursor.fetchall() if row[0]]
