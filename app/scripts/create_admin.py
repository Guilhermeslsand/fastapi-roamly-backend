"""Cria o primeiro administrador por CLI, sem expor cadastro ADMIN publicamente."""
from getpass import getpass

from sqlalchemy import func, select

from app.core.security import hash_password
from app.database.connection_sync import SessionLocal
from app.domains.shared.enums import UserRole
from app.modules.models import UserModel

def main() -> None:
    print("Bootstrap de administrador da Travel API")
    name = input("Nome: ").strip()
    email = input("Email: ").strip().lower()
    cpf = "".join(char for char in input("CPF (somente números): ") if char.isdigit())
    password = getpass("Senha (mínimo 8 caracteres): ")
    confirmation = getpass("Confirme a senha: ")

    if len(name) < 2 or len(cpf) != 11 or len(password) < 8:
        raise SystemExit("Nome, CPF ou senha inválidos.")
    if password != confirmation:
        raise SystemExit("As senhas não correspondem.")

    with SessionLocal() as db:
        existing_admin = db.scalar(
            select(UserModel.id).where(UserModel.role == UserRole.ADMIN).limit(1)
        )
        if existing_admin:
            raise SystemExit(
                "O administrador inicial já existe. A criação de novos administradores "
                "deve ocorrer pelo futuro endpoint protegido para ADMIN."
            )

        duplicate = db.scalar(
            select(UserModel.id).where(
                (func.lower(UserModel.email) == email) | (UserModel.cpf == cpf)
            ).limit(1)
        )
        if duplicate:
            raise SystemExit("Já existe usuário com esse email ou CPF.")

        admin = UserModel(
            name=name,
            email=email,
            cpf=cpf,
            password_hash=hash_password(password),
            role=UserRole.ADMIN,
            is_active=True,
        )
        db.add(admin)
        db.commit()
        print(f"Administrador criado: {admin.id}")


if __name__ == "__main__":
    main()
