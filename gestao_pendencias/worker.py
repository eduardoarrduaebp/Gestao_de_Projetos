import time
import schedule
from datetime import datetime, date
import requests
from plyer import notification
import database as db


def get_webhook_url() -> str:
    """Tenta recuperar URL de webhook a partir de .streamlit/secrets.toml se existir."""
    try:
        import toml
        with open(".streamlit/secrets.toml", "r") as f:
            sec = toml.load(f)
            return sec.get("notifications", {}).get("webhook_url", "")
    except Exception:
        return ""


def emitir_webhook(webhook_url: str, titulo: str, mensagem: str) -> None:
    """Dispara alerta via webhook HTTP POST para integração externa (Teams/Slack/Discord)."""
    try:
        payload = {"text": f"*{titulo}*\n{mensagem}"}
        requests.post(webhook_url, json=payload, timeout=5)
    except Exception as e:
        print(f"[ERRO WEBHOOK] Falha no disparo: {e}")


def verificar_e_notificar() -> None:
    """Executa a checagem das pendências abertas e dispara alertas de Seg a Sex."""
    if datetime.today().weekday() > 4:
        return

    hoje_str = str(date.today())
    pendencias_abertas = db.get_filtered_pendencias(status="PENDENTE")
    total_abertas = len(pendencias_abertas)
    
    if total_abertas == 0:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Nenhuma pendência em aberto.")
        return

    atrasadas = [p for p in pendencias_abertas if p[6] < hoje_str]
    total_atrasadas = len(atrasadas)

    titulo = "Lembrete de Pendências (15:00)"
    msg = f"Você possui {total_abertas} pendência(s) em aberto."
    if total_atrasadas > 0:
        msg += f" ({total_atrasadas} em atraso!)"

    # Alerta local desktop
    try:
        notification.notify(
            title=titulo,
            message=msg,
            app_name="Gestão de Pendências",
            timeout=10
        )
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Notificação desktop emitida.")
    except Exception as e:
        print(f"[AVISO] Interface gráfica não suportou notificação desktop: {e}")

    # Alerta via webhook se configurado
    webhook = get_webhook_url()
    if webhook:
        emitir_webhook(webhook, titulo, msg)


def main():
    db.init_db()
    
    # Configura o agendamento de Seg a Sex às 15:00
    for dia in [
        schedule.every().monday,
        schedule.every().tuesday,
        schedule.every().wednesday,
        schedule.every().thursday,
        schedule.every().friday
    ]:
        dia.at("15:00").do(verificar_e_notificar)

    print("[WORKER] Agendador ativo para Seg-Sex às 15:00.")
    print("Pressione Ctrl+C para encerrar.")
    
    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
