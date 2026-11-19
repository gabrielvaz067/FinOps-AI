"""Generate local secrets without displaying them or replacing user configuration."""

import secrets

from backend.app.config import PROJECT_ROOT


def main():
    target = PROJECT_ROOT / ".env"
    if target.exists():
        print(".env existente preservado.")
        return
    content = (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")
    for key in ["FINOPS_ADMIN_KEY", "POSTGRES_PASSWORD", "N8N_ENCRYPTION_KEY"]:
        content = content.replace(f"{key}=\n", f"{key}={secrets.token_hex(24)}\n")
    # Exclusive creation prevents concurrent setup from overwriting the first secrets.
    with target.open("x", encoding="utf-8") as file:
        file.write(content)
    print(".env local criado; credenciais nao exibidas. Nao adicione este arquivo ao Git.")


if __name__ == "__main__":
    main()
