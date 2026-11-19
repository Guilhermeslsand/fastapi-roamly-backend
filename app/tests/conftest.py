import os

# Configuração local isolada para testes que importam os módulos da aplicação.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5432/travel_db",
)
os.environ.setdefault("JWT_SECRET_KEY", "test-only-secret-key-with-at-least-32-characters")
