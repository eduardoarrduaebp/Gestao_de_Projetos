import sqlite3
from datetime import date
from typing import Any, List, Optional, Tuple

DB_NAME = "gestao_pendencias.db"


def get_connection():
  return sqlite3.connect(DB_NAME, check_same_thread=False)


def init_db():
  """Inicializa o banco de dados e aplica migrações de colunas se necessário."""
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
                data_abertura TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDENTE',
                data_criacao TEXT NOT NULL,
                data_conclusao TEXT
            )
        """)
    conn.commit()


def add_pendencia(
    titulo: str,
    descricao: str,
    tipo: str,
    projeto: str,
    campanha: str,
    data_abertura: str,
) -> int:
  hoje_str = date.today().isoformat()
  with get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute(
        """
            INSERT INTO pendencias (
                titulo, descricao, tipo, projeto, campanha, data_abertura, status, data_criacao, data_conclusao
            ) VALUES (?, ?, ?, ?, ?, ?, 'PENDENTE', ?, NULL)
        """,
        (
            titulo.strip(),
            descricao.strip() if descricao else "",
            tipo.strip(),
            projeto.strip(),
            campanha.strip(),
            data_abertura,
            hoje_str,
        ),
    )
    conn.commit()
    return cursor.lastrowid


def update_pendencia(
    p_id: int,
    titulo: str,
    descricao: str,
    tipo: str,
    projeto: str,
    campanha: str,
    data_abertura: str,
):
  """Atualiza todos os dados de uma pendência existente."""
  with get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute(
        """
            UPDATE pendencias
            SET titulo = ?, descricao = ?, tipo = ?, projeto = ?, campanha = ?, data_abertura = ?
            WHERE id = ?
        """,
        (
            titulo.strip(),
            descricao.strip() if descricao else "",
            tipo.strip(),
            projeto.strip(),
            campanha.strip(),
            data_abertura,
            p_id,
        ),
    )
    conn.commit()


def update_status(p_id: int, novo_status: str):
  """Atualiza o status e grava a data de conclusão quando finalizado."""
  data_conclusao = date.today().isoformat() if novo_status == "CONCLUIDO" else None
  with get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute(
        """
            UPDATE pendencias
            SET status = ?, data_conclusao = ?
            WHERE id = ?
        """,
        (novo_status, data_conclusao, p_id),
    )
    conn.commit()


def get_distinct_values(coluna: str) -> List[str]:
  colunas_permitidas = ["tipo", "projeto", "campanha", "status"]
  if coluna not in colunas_permitidas:
    raise ValueError(
        f"Coluna '{coluna}' inválida para recuperação de valores distintos."
    )

  with get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute(f"""
            SELECT DISTINCT {coluna} 
            FROM pendencias 
            WHERE {coluna} IS NOT NULL AND {coluna} != ''
            ORDER BY {coluna} ASC
        """)
    return [row[0] for row in cursor.fetchall()]


def get_filtered_pendencias(
    status: str = "TODOS",
    tipo: str = "TODOS",
    projeto: str = "TODOS",
    campanha: str = "TODOS",
    busca: str = "",
) -> List[Tuple]:
  query = """
        SELECT id, titulo, descricao, tipo, projeto, campanha, data_abertura, status, data_criacao, data_conclusao
        FROM pendencias
        WHERE 1=1
    """
  params: List[Any] = []

  if status != "TODOS":
    query += " AND status = ?"
    params.append(status)

  if tipo != "TODOS":
    query += " AND tipo = ?"
    params.append(tipo)

  if projeto != "TODOS":
    query += " AND projeto = ?"
    params.append(projeto)

  if campanha != "TODOS":
    query += " AND campanha = ?"
    params.append(campanha)

  if busca.strip():
    query += " AND (titulo LIKE ? OR descricao LIKE ?)"
    termo = f"%{busca.strip()}%"
    params.extend([termo, termo])

  query += " ORDER BY status DESC, data_abertura ASC"

  with get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute(query, params)
    return cursor.fetchall()