import hashlib
import hmac
import io
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
# GERENCIADOR DE COOKIES E TOKEN MULTIUSUÁRIO
# ---------------------------------------------------------
def get_cookie_manager():
  return stx.CookieManager(key="auth_cookie_manager")


cookie_manager = get_cookie_manager()


def generate_auth_token(username: str, expiry_timestamp: int) -> str:
  """Gera token estruturado: <username>:<timestamp_expiracao>:<assinatura_hmac>"""
  secret = st.secrets["auth"].get("cookie_secret", "").encode()
  payload = f"{username}:{expiry_timestamp}".encode()
  signature = hmac.new(secret, payload, hashlib.sha256).hexdigest()
  return f"{username}:{expiry_timestamp}:{signature}"


def verify_auth_token(token: str) -> tuple[bool, str | None]:
  """Valida se o usuário existe, se o HMAC é legítimo e se não expirou."""
  if not token or token.count(":") != 2:
    return False, None
  try:
    username, exp_str, signature = token.split(":", 2)
    exp_timestamp = int(exp_str)

    if time.time() > exp_timestamp:
      return False, None

    # Valida se o usuário ainda existe nas configurações
    users_dict = st.secrets.get("users", {})
    if username not in users_dict:
      return False, None

    expected_token = generate_auth_token(username, exp_timestamp)
    if hmac.compare_digest(token, expected_token):
      return True, username
    return False, None
  except Exception:
    return False, None


# ---------------------------------------------------------
# AUTENTICAÇÃO MULTIUSUÁRIO
# ---------------------------------------------------------
def check_password() -> bool:
  if (
      "auth" not in st.secrets
      or "users" not in st.secrets
      or "cookie_secret" not in st.secrets["auth"]
  ):
    st.error(
        "Configuração de segurança ausente: defina [auth.cookie_secret] e"
        " [users] em .streamlit/secrets.toml"
    )
    st.stop()

  if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.username = None

  # 1. Validação via Session State
  if st.session_state.authenticated:
    return True

  # 2. Validação via Cookie Persistente
  auth_token = cookie_manager.get("auth_session")
  if auth_token:
    is_valid, user_logged = verify_auth_token(auth_token)
    if is_valid:
      st.session_state.authenticated = True
      st.session_state.username = user_logged
      return True

  # 3. Formulário de Login
  col1, col2, col3 = st.columns([1, 2, 1])
  with col2:
    st.markdown("### Acesso ao Sistema")
    st.caption("Insira suas credenciais individuais para prosseguir.")
    with st.form("form_login"):
      usuario_input = st.text_input("Usuário:").strip().lower()
      senha_input = st.text_input("Senha:", type="password")
      manter_conectado = st.checkbox("Manter conectado (30 dias)")
      btn_entrar = st.form_submit_button("Entrar", use_container_width=True)

      if btn_entrar:
        users = st.secrets.get("users", {})
        if (
            usuario_input in users
            and isinstance(users[usuario_input], str)
            and hmac.compare_digest(senha_input, users[usuario_input])
        ):
          st.session_state.authenticated = True
          st.session_state.username = usuario_input

          if manter_conectado:
            exp_timestamp = int(time.time() + (30 * 86400))
            token = generate_auth_token(usuario_input, exp_timestamp)
            cookie_manager.set(
                "auth_session",
                token,
                expires_at=datetime.fromtimestamp(exp_timestamp),
            )
          st.rerun()
        else:
          st.error("Usuário ou senha incorretos.")
  return False


if not check_password():
  st.stop()


# ---------------------------------------------------------
# GERADOR DE RELATÓRIO EXCEL
# ---------------------------------------------------------
def gerar_excel_bytes(dados: list, titulo_aba: str) -> bytes:
  colunas = [
      "ID",
      "Título",
      "Descrição",
      "Tipo",
      "Chamado/Projeto",
      "Campanha",
      "Data de Abertura",
      "Status",
      "Data de Registro",
      "Data de Conclusão",
  ]
  df = pd.DataFrame(dados, columns=colunas)

  hoje_calc = date.today()

  def calcular_duracao(row):
    try:
      dt_abertura = datetime.strptime(
          row["Data de Abertura"], "%Y-%m-%d"
      ).date()
      if row["Status"] == "PENDENTE":
        return (hoje_calc - dt_abertura).days
      elif row["Data de Conclusão"]:
        dt_conc = datetime.strptime(
            row["Data de Conclusão"][:10], "%Y-%m-%d"
        ).date()
        return (dt_conc - dt_abertura).days
    except Exception:
      return None
    return None

  df["Dias Decorridos / Resolução"] = df.apply(calcular_duracao, axis=1)

  output = io.BytesIO()
  with pd.ExcelWriter(output, engine="openpyxl") as writer:
    df.to_excel(writer, index=False, sheet_name=titulo_aba[:30])
  return output.getvalue()


# ---------------------------------------------------------
# MODAL DE EDIÇÃO
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
      salvar = st.form_submit_button(
          "Salvar Alterações", use_container_width=True
      )
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
    "Controle operacional, rastreamento de prazos e métricas de chamados."
)

todos_dados = db.get_filtered_pendencias(status="TODOS")
hoje = date.today()

total_abertas = sum(1 for p in todos_dados if p[7] == "PENDENTE")
total_concluidas = sum(1 for p in todos_dados if p[7] == "CONCLUIDO")

col_m1, col_m2, col_m3 = st.columns(3)
col_m1.metric("Pendências em Aberto", total_abertas)
col_m2.metric("Concluídas", total_concluidas)
col_m3.metric("Total Geral", len(todos_dados))

st.markdown("---")

tab_visualizacao, tab_cadastro, tab_relatorios = st.tabs(
    ["Consultar & Atualizar", "Nova Pendência", "Exportar Relatórios"]
)


# ---------------------------------------------------------
# ABA 1: CONSULTA E AÇÕES
# ---------------------------------------------------------
with tab_visualizacao:
  with st.sidebar:
    st.markdown(f"👤 Conectado como: **{st.session_state.username}**")
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
      st.session_state.username = None
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
            dt_conc_fmt = datetime.strptime(
                p_conclusao[:10], "%Y-%m-%d"
            ).strftime("%d/%m/%Y")
            st.caption(f"🏁 **Concluído em:** {dt_conc_fmt}")

        with c_edit:
          if st.button("✏️", key=f"btn_edit_{p_id}", help="Editar pendência"):
            modal_editar_pendencia(reg)

        st.divider()


# ---------------------------------------------------------
# ABA 2: CADASTRO
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


# ---------------------------------------------------------
# ABA 3: EXPORTAÇÃO EXCEL (.XLSX)
# ---------------------------------------------------------
with tab_relatorios:
  st.subheader("Exportação de Dados em Excel (.xlsx)")
  st.caption(
      "Selecione o escopo desejado para compilar a planilha com cálculo"
      " automático de dias decorridos."
  )

  escopo_exportacao = st.radio(
      "Selecione os registros para exportação:",
      [
          "Todas as Pendências",
          "Apenas Pendentes (Em Aberto)",
          "Apenas Concluídas",
      ],
      horizontal=True,
  )

  # Mapeamento do filtro para consulta no banco
  filtro_status_map = {
      "Todas as Pendências": "TODOS",
      "Apenas Pendentes (Em Aberto)": "PENDENTE",
      "Apenas Concluídas": "CONCLUIDO",
  }

  status_selecionado = filtro_status_map[escopo_exportacao]
  dados_exportar = db.get_filtered_pendencias(status=status_selecionado)

  st.write(f"Total de registros encontrados: **{len(dados_exportar)}**")

  if dados_exportar:
    excel_bin = gerar_excel_bytes(dados_exportar, escopo_exportacao)
    nome_arquivo = (
        f"relatorio_pendencias_{status_selecionado.lower()}_{hoje.isoformat()}.xlsx"
    )

    st.download_button(
        label=f"📥 Baixar Arquivo Excel ({escopo_exportacao})",
        data=excel_bin,
        file_name=nome_arquivo,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
  else:
    st.warning("Não há dados disponíveis para o escopo selecionado.")