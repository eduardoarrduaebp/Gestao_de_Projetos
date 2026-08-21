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
# GERENCIADOR DE COOKIES E SESSÃO
# ---------------------------------------------------------
def get_cookie_manager():
  return stx.CookieManager(key="auth_cookie_manager")


cookie_manager = get_cookie_manager()


def generate_auth_token(expiry_timestamp: int) -> str:
  secret = st.secrets["auth"].get(
      "cookie_secret", st.secrets["auth"]["app_password"]
  ).encode()
  payload = f"{expiry_timestamp}".encode()
  signature = hmac.new(secret, payload, hashlib.sha256).hexdigest()
  return f"{expiry_timestamp}:{signature}"


def verify_auth_token(token: str) -> bool:
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


def check_password() -> bool:
  if "auth" not in st.secrets or "app_password" not in st.secrets["auth"]:
    st.error("Defina [auth.app_password] em .streamlit/secrets.toml")
    st.stop()

  if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

  if st.session_state.authenticated:
    return True

  auth_token = cookie_manager.get("auth_session")
  if auth_token and verify_auth_token(auth_token):
    st.session_state.authenticated = True
    return True

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
            exp_timestamp = int(time.time() + (30 * 86400))
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
# FUNÇÃO DE DIALOG/MODAL PARA EDIÇÃO
# ---------------------------------------------------------
@st.dialog("Editar Pendência")
def modal_editar_pendencia(registro):
  (
      p_id,
      p_tit,
      p_desc,
      p_tipo,
      p_proj,
      p_camp,
      p_abertura,
      p_status,
      p_criacao,
      p_conclusao,
  ) = registro
  dt_abertura_obj = datetime.strptime(p_abertura, "%Y-%m-%d").date()

  with st.form(f"form_edit_{p_id}"):
    e_titulo = st.text_input("Título *", value=p_tit)
    e_desc = st.text_area("Descrição", value=p_desc or "")

    c1, c2, c3 = st.columns(3)
    with c1:
      e_tipo = st.text_input("Tipo *", value=p_tipo)
    with c2:
      e_proj = st.text_input("Chamado/Projeto *", value=p_proj)
    with c3:
      e_camp = st.text_input("Campanha *", value=p_camp)

    e_data_abertura = st.date_input("Data de Abertura *", value=dt_abertura_obj)

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
      salvar = st.form_submit_button("Salvar Alterações", use_container_width=True)
    with col_btn2:
      cancelar = st.form_submit_button("Cancelar", use_container_width=True)

    if salvar:
      if not e_titulo or not e_tipo or not e_proj or not e_camp:
        st.error("Campos com (*) são obrigatórios.")
      else:
        db.update_pendencia(
            p_id=p_id,
            titulo=e_titulo,
            descricao=e_desc,
            tipo=e_tipo,
            projeto=e_proj,
            campanha=e_camp,
            data_abertura=str(e_data_abertura),
        )
        st.success("Registro atualizado com sucesso!")
        st.rerun()


# ---------------------------------------------------------
# INTERFACE PRINCIPAL
# ---------------------------------------------------------
st.title("Painel de Controle de Pendências")
st.caption(
    "Controle operacional, rastreamento de tempo decorrido e gestão de"
    " chamados."
)

todos_dados = db.get_filtered_pendencias(status="TODOS")
hoje = date.today()

total_abertas = sum(1 for p in todos_dados if p[7] == "PENDENTE")
total_concluidas = sum(1 for p in todos_dados if p[7] == "CONCLUIDO")

# Métricas principais
col_m1, col_m2, col_m3 = st.columns(3)
col_m1.metric("Pendências em Aberto", total_abertas)
col_m2.metric("Concluídas", total_concluidas)
col_m3.metric("Total de Registros", len(todos_dados))

st.markdown("---")

tab_visualizacao, tab_cadastro = st.tabs(
    ["Consultar & Atualizar", "Nova Pendência"]
)

# ---------------------------------------------------------
# ABA 1: CONSULTA, EDIÇÃO E STATUS
# ---------------------------------------------------------
with tab_visualizacao:
  with st.sidebar:
    st.header("Filtros de Classificação")
    filtro_status = st.selectbox(
        "Status", ["PENDENTE", "CONCLUIDO", "TODOS"], index=0
    )
    filtro_tipo = st.selectbox(
        "Tipo", ["TODOS"] + db.get_distinct_values("tipo")
    )
    filtro_projeto = st.selectbox(
        "Chamado/Projeto", ["TODOS"] + db.get_distinct_values("projeto")
    )
    filtro_campanha = st.selectbox(
        "Campanha", ["TODOS"] + db.get_distinct_values("campanha")
    )
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
          p_abertura,
          p_status,
          p_criacao,
          p_conclusao,
      ) = reg
      data_abertura = datetime.strptime(p_abertura, "%Y-%m-%d").date()

      # Cálculo de tempo decorrido / resolução
      if p_status == "PENDENTE":
        dias_decorridos = (hoje - data_abertura).days
        if dias_decorridos == 0:
          info_tempo = "Aberto hoje"
        elif dias_decorridos == 1:
          info_tempo = "Aberto há 1 dia"
        else:
          info_tempo = f"Aberto há {dias_decorridos} dias"
        prefixo = "🔴 " if dias_decorridos > 7 else "🟡 "
      else:
        prefixo = "✅ "
        if p_conclusao:
          dt_conc = datetime.strptime(p_conclusao[:10], "%Y-%m-%d").date()
          duracao = (dt_conc - data_abertura).days
          info_tempo = (
              f"Resolvido em {duracao} dias"
              if duracao > 0
              else "Resolvido no mesmo dia"
          )
        else:
          info_tempo = "Concluído"

      with st.container():
        c_check, c_info, c_tags, c_meta, c_edit = st.columns([1, 5, 2, 3, 1])

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
          st.markdown(f"**{prefixo}#{p_id} {p_tit}**")
          if p_desc:
            st.caption(p_desc)

        with c_tags:
          st.markdown(f"`{p_proj}` | `{p_camp}`")
          st.caption(f"Tipo: **{p_tipo}**")

        with c_meta:
          st.markdown(f"**Aberto em:** {data_abertura.strftime('%d/%m/%Y')}")
          st.caption(f"⏱️ {info_tempo}")
          if p_status == "CONCLUIDO" and p_conclusao:
            dt_conc_formatada = datetime.strptime(
                p_conclusao[:10], "%Y-%m-%d"
            ).strftime("%d/%m/%Y")
            st.caption(f"🏁 **Concluído em:** {dt_conc_formatada}")

        with c_edit:
          if st.button("✏️", key=f"btn_edit_{p_id}", help="Editar pendência"):
            modal_editar_pendencia(reg)

        st.divider()

# ---------------------------------------------------------
# ABA 2: CADASTRO COM DATA DE ABERTURA
# ---------------------------------------------------------
with tab_cadastro:
  st.subheader("Cadastrar Nova Pendência / Chamado")
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

    f_data_abertura = st.date_input(
        "Data de Abertura do Chamado *", value=hoje, max_value=hoje
    )

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
            data_abertura=str(f_data_abertura),
        )
        st.success(f"Pendência '{f_titulo}' cadastrada com sucesso.")
        st.rerun()