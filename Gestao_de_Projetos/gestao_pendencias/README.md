# Sistema de Gestão de Pendências e Correções

Aplicação Web desenvolvida com Streamlit e arquitetura modular, persistência SQLite (modo WAL), autenticação via `secrets.toml`, segregação estrita de dados no `.gitignore` e serviço de lembrete diário às 15:00 de segunda a sexta-feira.

---

## 📁 Estrutura de Arquivos

```text
gestao_pendencias/
├── .gitignore                      # Protege banco local, logs, caches e segredos
├── requirements.txt                # Dependências do projeto
├── database.py                     # Camada relacional SQLite com consultas parametrizadas
├── app.py                          # Frontend Streamlit com controle de acesso e filtros
├── worker.py                       # Daemon de lembretes desacoplado (15h Seg-Sex)
├── README.md                       # Documentação técnica de instalação e execução
└── .streamlit/
    ├── config.toml                 # Configurações visuais e segurança de servidor
    └── secrets.toml.example        # Template para definição segura de senhas
```

---

## 🚀 Como Executar

### 1. Criar e ativar o ambiente virtual
```bash
python -m venv venv
# Linux / macOS:
source venv/bin/activate
# Windows:
venv\Scripts\activate
```

### 2. Instalar dependências
```bash
pip install -r requirements.txt
```

### 3. Configurar Segredos e Senha de Acesso
```bash
# Linux / macOS:
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Windows:
copy .streamlit\secrets.toml.example .streamlit\secrets.toml
```
Abra `.streamlit/secrets.toml` e defina sua senha em `app_password`.

### 4. Iniciar a Aplicação Web
```bash
streamlit run app.py
```

### 5. Iniciar o Daemon de Notificações
Em um terminal separado:
```bash
python worker.py
```
