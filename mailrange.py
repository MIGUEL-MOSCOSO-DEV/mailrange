import argparse
import getpass
import json
import re
import smtplib
import ssl
import uuid
from email import policy
from email.message import EmailMessage
from email.parser import BytesHeaderParser
from pathlib import Path


def inspect(path, receiver, token):
    with path.open("rb") as source:
        raw = source.read(262145)
    if len(raw) > 262144:
        raise ValueError("El EML supera 256 KiB.")
    message = BytesHeaderParser(policy=policy.default).parsebytes(raw)
    if message.get_all("X-MailRange-ID") != [token]:
        raise ValueError("El mensaje no coincide con la prueba.")
    matching = []
    for header in message.get_all("Authentication-Results", []):
        server, _, evidence = header.partition(";")
        if server.strip().lower() == receiver.lower():
            matching.append(evidence)
    if len(matching) != 1:
        raise ValueError("Se requiere un único Authentication-Results del receptor esperado.")
    evidence = matching[0]
    return {method: re.findall(r"(?:^|;)\s*" + method + r"\s*=\s*([a-z]+)", evidence, re.I)
            for method in ("spf", "dkim", "dmarc")}


def send(host, port, sender, recipient):
    for address in (sender, recipient):
        if not re.fullmatch(r"[A-Za-z0-9._+%-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}", address):
            raise ValueError("Indica una dirección de correo simple y válida.")
    token = uuid.uuid4().hex
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = f"MailRange {token}"
    message["X-MailRange-ID"] = token
    message.set_content("Mensaje de prueba de autenticación enviado por el titular de los buzones.")
    password = getpass.getpass("Contraseña de aplicación SMTP: ")
    with smtplib.SMTP_SSL(host, port, timeout=15, context=ssl.create_default_context()) as smtp:
        smtp.login(sender, password)
        smtp.send_message(message, from_addr=sender, to_addrs=[recipient])
    return token


def main():
    parser = argparse.ArgumentParser(description="Prueba de entrega entre tus buzones.")
    commands = parser.add_subparsers(dest="command", required=True)
    submit = commands.add_parser("send")
    submit.add_argument("--smtp", required=True)
    submit.add_argument("--port", type=int, default=465)
    submit.add_argument("--sender", required=True)
    submit.add_argument("--recipient", required=True)
    submit.add_argument("--authorized", action="store_true")
    analyze = commands.add_parser("inspect")
    analyze.add_argument("eml", type=Path)
    analyze.add_argument("--receiver", required=True)
    analyze.add_argument("--token", required=True)
    args = parser.parse_args()
    try:
        if args.command == "send":
            if not args.authorized:
                parser.error("Confirma que controlas ambos buzones.")
            print(json.dumps({"submitted": True, "token": send(args.smtp, args.port, args.sender, args.recipient)}))
            return 0
        results = inspect(args.eml, args.receiver, args.token)
        print(json.dumps(results, indent=2))
        verdict = results["dmarc"]
        return 0 if verdict == ["pass"] else 1 if verdict == ["fail"] else 2
    except (OSError, ValueError, smtplib.SMTPException) as error:
        parser.exit(2, f"Error de prueba ({type(error).__name__}). Revisa la configuración y el EML.\n")


if __name__ == "__main__":
    raise SystemExit(main())
