import hashlib
import hmac
import time
from datetime import date, datetime
import database as db
import extra_streamlit_components as stx
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Gestão de Pendências",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

db.init_db()


# ---------------------------------------------------------
# GERENCIADOR DE COOKIES E TOKEN
# ---------------------------------------------------------
def get_cookie_manager():
  return stx.CookieManager(key="auth_cookie_manager")


cookie_manager = get_cookie_manager()


def generate_auth_token(expiry_timestamp: int) -> str:
  """Gera token no formato: <timestamp_expiracao>:<assinatura_hmac>"""
  secret = st.secrets["auth"].get(
      "cookie_secret", st.secrets["auth"]["app_password"]
  ).encode()
  payload = f"{expiry_timestamp}".encode()
  signature = hmac.new(secret, payload, hashlib.sha256).hexdigest()
  return f"{expiry_timestamp}:{signature}"


def verify_auth_token(token: str) -> bool:
  """Valida autenticidade do HMAC e expiração temporal."""
  if not token or ":" not in token:
    return False
  try:
    exp_str, signature = token.split(":", 1)
    exp_timestamp = int(exp_str)

    if time.time() > exp_timestamp:
      return False

    expected_token = generate_auth_token(exp_timestamp)
    return hmac.compare_digest(token, expected_token)
  except Exception:
    return False


# ---------------------------------------------------------
# AUTENTICAÇÃO E CONTROLE DE ACESSO
# ---------------------------------------------------------
def check_password() -> bool:
  if "auth" not in st.secrets or "app_password" not in st.secrets["auth"]:
    st.error(
        "Configuração ausente: defina [auth.app_password] em"
        " .streamlit/secrets.toml"
    )
    st.stop()

  if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

  # 1. Validação por Sessão Ativa
  if st.session_state.authenticated:
    return True

  # 2. Validação por Cookie Persistente
  auth_token = cookie_manager.get("auth_session")
  if auth_token and verify_auth_token(auth_token):
    st.session_state.authenticated = True
    return True

  # 3. Formulário de Login
  col1, col2, col3 = st.columns([1, 2, 1])
  with col2:
    st.markdown("### Acesso Restrito")
    st.caption(
        "Insira a chave de acesso configurada para gerenciar as pendências."
    )
    with st.form("form_login"):
      pwd = st.text_input("Chave de acesso:", type="password")
      manter_conectado = st.checkbox("Manter conectado (30 dias)")
      btn_entrar = st.form_submit_button("Entrar", use_container_width=True)

      if btn_entrar:
        if hmac.compare_digest(pwd, st.secrets["auth"]["app_password"]):
          st.session_state.authenticated = True

          if manter_conectado:
            validade_dias = 30
            exp_timestamp = int(time.time() + (validade_dias * 86400))
            token = generate_auth_token(exp_timestamp)
            cookie_manager.set(
                "auth_session",
                token,
                expires_at=datetime.fromtimestamp(exp_timestamp),
            )
          st.rerun()
        else:
          st.error("Chave de acesso incorreta.")
  return False


if not check_password():
  st.stop()


# ---------------------------------------------------------
# INTERFACE PRINCIPAL
# ---------------------------------------------------------
st.title("Painel de Controle de Pendências")
st.caption(
    "Classificação multidimensional e controle de prazos por tempo,"
    " Chamado/Projeto, campanha e tipo."
)

# Indicadores Principais
todos_dados = db.get_filtered_pendencias(status="TODOS")
hoje = date.today()

total_abertas = sum(1 for p in todos_dados if p[7] == "PENDENTE")
total_concluidas = sum(1 for p in todos_dados if p[7] == "CONCLUIDO")
total_atrasadas = sum(
    1
    for p in todos_dados
    if p[7] == "PENDENTE" and datetime.strptime(p[6], "%Y-%m-%d").date() < hoje
)

col_m1, col_m2, col_m3, col_m4 = st.columns(4)
col_m1.metric("Pendências Abertas", total_abertas)
col_m2.metric(
    "Atrasadas",
    total_atrasadas,
    delta=f"-{total_atrasadas}" if total_atrasadas > 0 else "0",
    delta_color="inverse",
)
col_m3.metric("Concluídas", total_concluidas)
col_m4.metric("Total de Registros", len(todos_dados))

st.markdown("---")

tab_visualizacao, tab_cadastro = st.tabs(
    ["Consultar & Atualizar", "Nova Pendência"]
)


# ---------------------------------------------------------
# ABA 1: CONSULTA E AÇÕES
# ---------------------------------------------------------
with tab_visualizacao:
  with st.sidebar:
    st.header("Filtros de Classificação")

    filtro_status = st.selectbox(
        "Status", ["PENDENTE", "CONCLUIDO", "TODOS"], index=0
    )

    tipos_disponiveis = ["TODOS"] + db.get_distinct_values("tipo")
    filtro_tipo = st.selectbox("Tipo", tipos_disponiveis)

    # Identificador corrigido de "Chamado/Projeto" para "projeto"
    projetos_disponiveis = ["TODOS"] + db.get_distinct_values("projeto")
    filtro_projeto = st.selectbox("Chamado/Projeto", projetos_disponiveis)

    campanhas_disponiveis = ["TODOS"] + db.get_distinct_values("campanha")
    filtro_campanha = st.selectbox("Campanha", campanhas_disponiveis)

    filtro_busca = st.text_input("Buscar por título/descrição")

    st.markdown("---")
    if st.button("Encerrar Sessão", use_container_width=True):
      cookie_manager.delete("auth_session")
      st.session_state.authenticated = False
      st.rerun()

  registros = db.get_filtered_pendencias(
      status=filtro_status,
      tipo=filtro_tipo,
      projeto=filtro_projeto,
      campanha=filtro_campanha,
      busca=filtro_busca,
  )

  if not registros:
    st.info("Nenhuma pendência localizada para os critérios informados.")
  else:
    for reg in registros:
      (
          p_id,
          p_tit,
          p_desc,
          p_tipo,
          p_proj,
          p_camp,
          p_prazo,
          p_status,
          p_criacao,
          p_conclusao,
      ) = reg

      data_prazo = datetime.strptime(p_prazo, "%Y-%m-%d").date()
      em_atraso = p_status == "PENDENTE" and data_prazo < hoje

      with st.container():
        c_check, c_info, c_tags, c_meta = st.columns([1, 6, 3, 2])

        with c_check:
          concluido_check = st.checkbox(
              "Concluído",
              value=(p_status == "CONCLUIDO"),
              key=f"chk_{p_id}",
              label_visibility="collapsed",
          )
          if (p_status == "CONCLUIDO") != concluido_check:
            novo_st = "CONCLUIDO" if concluido_check else "PENDENTE"
            db.update_status(p_id, novo_st)
            st.rerun()

        with c_info:
          prefixo = (
              "🔴 "
              if em_atraso
              else ("✅ " if p_status == "CONCLUIDO" else "🟡 ")
          )
          st.markdown(f"**{prefixo}#{p_id} {p_tit}**")
          if p_desc:
            st.caption(p_desc)

        with c_tags:
          st.markdown(f"`{p_proj}` | `{p_camp}`")
          st.caption(f"Tipo: **{p_tipo}**")

        with c_meta:
          st.markdown(f"**Prazo:** {data_prazo.strftime('%d/%m/%Y')}")
          if p_status == "CONCLUIDO" and p_conclusao:
            st.caption(f"Concluído em: {p_conclusao[:10]}")

        st.divider()


# ---------------------------------------------------------
# ABA 2: CADASTRO
# ---------------------------------------------------------
with tab_cadastro:
  st.subheader("Cadastrar Nova Pendência / Correção")
  with st.form("form_nova_pendencia", clear_on_submit=True):
    f_titulo = st.text_input(
        "Título da Pendência / Item a Corrigir *",
        placeholder="Ex: Correção de validação no formulário",
    )
    f_desc = st.text_area(
        "Descrição Detalhada",
        placeholder="Requisitos, logs de erro, orientações ou links",
    )

    c1, c2, c3 = st.columns(3)
    with c1:
      f_tipo = st.text_input(
          "Tipo *", placeholder="Ex: Bug, Revisão, Schema, Relatório"
      )
    with c2:
      f_proj = st.text_input("Chamado/Projeto *", placeholder="Ex: Sistema X")
    with c3:
      f_camp = st.text_input("Campanha *", placeholder="Ex: 2026-Q3")

    f_prazo = st.date_input("Prazo Limite *", min_value=hoje)

    submetido = st.form_submit_button(
        "Salvar Registro", use_container_width=True
    )
    if submetido:
      if not f_titulo or not f_tipo or not f_proj or not f_camp:
        st.error("Campos marcados com asterisco (*) são obrigatórios.")
      else:
        db.add_pendencia(
            titulo=f_titulo,
            descricao=f_desc,
            tipo=f_tipo,
            projeto=f_proj,
            campanha=f_camp,
            prazo=str(f_prazo),
        )
        st.success(f"Pendência '{f_titulo}' cadastrada com sucesso.")
        st.rerun()
