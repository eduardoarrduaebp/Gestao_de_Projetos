import streamlit as st
import pandas as pd
from datetime import date, datetime
import hmac
import database as db

st.set_page_config(
    page_title="Gestão de Pendências",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inicialização do banco
db.init_db()


# ---------------------------------------------------------
# AUTENTICAÇÃO E CONTROLE DE ACESSO
# ---------------------------------------------------------
def check_password() -> bool:
    """Verifica credencial configurada em .streamlit/secrets.toml com tempo constante."""
    if "auth" not in st.secrets or "app_password" not in st.secrets["auth"]:
        st.error("Configuração de segurança ausente: defina [auth.app_password] em .streamlit/secrets.toml")
        st.info("Utilize .streamlit/secrets.toml.example como modelo.")
        st.stop()

    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return True

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("### Acesso Restrito")
        st.caption("Insira a chave de acesso configurada para gerenciar as pendências.")
        with st.form("form_login"):
            pwd = st.text_input("Chave de acesso:", type="password")
            btn_entrar = st.form_submit_button("Entrar", use_container_width=True)
            if btn_entrar:
                if hmac.compare_digest(pwd, st.secrets["auth"]["app_password"]):
                    st.session_state.authenticated = True
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
st.caption("Classificação multidimensional e controle de prazos por tempo, projeto, campanha e tipo.")

# Indicadores Principais
todos_dados = db.get_filtered_pendencias(status="TODOS")
hoje = date.today()

total_abertas = sum(1 for p in todos_dados if p[7] == "PENDENTE")
total_concluidas = sum(1 for p in todos_dados if p[7] == "CONCLUIDO")
total_atrasadas = sum(
    1 for p in todos_dados 
    if p[7] == "PENDENTE" and datetime.strptime(p[6], "%Y-%m-%d").date() < hoje
)

col_m1, col_m2, col_m3, col_m4 = st.columns(4)
col_m1.metric("Pendências Abertas", total_abertas)
col_m2.metric("Atrasadas", total_atrasadas, delta=f"-{total_atrasadas}" if total_atrasadas > 0 else "0", delta_color="inverse")
col_m3.metric("Concluídas", total_concluidas)
col_m4.metric("Total de Registros", len(todos_dados))

st.markdown("---")

tab_visualizacao, tab_cadastro = st.tabs(["Consultar & Atualizar", "Nova Pendência"])


# ---------------------------------------------------------
# ABA 1: CONSULTA E AÇÕES
# ---------------------------------------------------------
with tab_visualizacao:
    with st.sidebar:
        st.header("Filtros de Classificação")
        
        filtro_status = st.selectbox("Status", ["PENDENTE", "CONCLUIDO", "TODOS"], index=0)
        
        tipos_disponiveis = ["TODOS"] + db.get_distinct_values("tipo")
        filtro_tipo = st.selectbox("Tipo", tipos_disponiveis)
        
        projetos_disponiveis = ["TODOS"] + db.get_distinct_values("Chamado/Projeto")
        filtro_projeto = st.selectbox("Chamado/Projeto", projetos_disponiveis)
        
        campanhas_disponiveis = ["TODOS"] + db.get_distinct_values("campanha")
        filtro_campanha = st.selectbox("Campanha", campanhas_disponiveis)
        
        filtro_busca = st.text_input("Buscar por título/descrição")
        
        st.markdown("---")
        if st.button("Encerrar Sessão", use_container_width=True):
            st.session_state.authenticated = False
            st.rerun()

    registros = db.get_filtered_pendencias(
        status=filtro_status,
        tipo=filtro_tipo,
        projeto=filtro_projeto,
        campanha=filtro_campanha,
        busca=filtro_busca
    )

    if not registros:
        st.info("Nenhuma pendência localizada para os critérios informados.")
    else:
        for reg in registros:
            p_id, p_tit, p_desc, p_tipo, p_proj, p_camp, p_prazo, p_status, p_criacao, p_conclusao = reg
            
            data_prazo = datetime.strptime(p_prazo, "%Y-%m-%d").date()
            em_atraso = (p_status == "PENDENTE" and data_prazo < hoje)
            
            with st.container():
                c_check, c_info, c_tags, c_meta = st.columns([1, 6, 3, 2])
                
                with c_check:
                    concluido_check = st.checkbox(
                        "Concluído",
                        value=(p_status == "CONCLUIDO"),
                        key=f"chk_{p_id}",
                        label_visibility="collapsed"
                    )
                    if (p_status == "CONCLUIDO") != concluido_check:
                        novo_st = "CONCLUIDO" if concluido_check else "PENDENTE"
                        db.update_status(p_id, novo_st)
                        st.rerun()

                with c_info:
                    prefixo = "🔴 " if em_atraso else ("✅ " if p_status == "CONCLUIDO" else "🟡 ")
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
        f_titulo = st.text_input("Título da Pendência / Item a Corrigir *", placeholder="Ex: Correção de validação no formulário")
        f_desc = st.text_area("Descrição Detalhada", placeholder="Requisitos, logs de erro, orientações ou links")
        
        c1, c2, c3 = st.columns(3)
        with c1:
            f_tipo = st.text_input("Tipo *", placeholder="Ex: Bug, Revisão, Schema, Relatório")
        with c2:
            f_proj = st.text_input("Chamado/Projeto *", placeholder="Ex: Sistema X")
        with c3:
            f_camp = st.text_input("Campanha *", placeholder="Ex: 2026-Q3")

        f_prazo = st.date_input("Prazo Limite *", min_value=hoje)

        submetido = st.form_submit_button("Salvar Registro", use_container_width=True)
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
                    prazo=str(f_prazo)
                )
                st.success(f"Pendência '{f_titulo}' cadastrada com sucesso.")
                st.rerun()
