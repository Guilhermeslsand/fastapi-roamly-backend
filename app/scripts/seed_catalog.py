"""Popula destinos e pacotes de demonstração de forma idempotente.

Uso:
    python -m app.scripts.seed_catalog
    python -m app.scripts.seed_catalog --admin-email admin@example.com
    python -m app.scripts.seed_catalog --dry-run

O script não cria usuários. É necessário executar primeiro:
    python -m app.scripts.create_admin
"""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.connection_sync import SessionLocal
from app.domains.shared.enums import UserRole
import app.modules.models  # noqa: F401 - registra todos os relacionamentos ORM
from app.modules.destinations.models import DestinationModel
from app.modules.packages.models import TravelPackageModel
from app.modules.users.models import UserModel

logger = logging.getLogger("travel_api.seed_catalog")


@dataclass(frozen=True, slots=True)
class DestinationSeed:
    key: str
    name: str
    country: str
    state: str
    description: str


@dataclass(frozen=True, slots=True)
class PackageSeed:
    title: str
    description: str
    origin: str
    destination: str
    days_from_today: int
    nights: int
    price: str
    cost_price: str
    total_seats: int


DESTINATIONS: tuple[DestinationSeed, ...] = (
    DestinationSeed("sao-paulo", "São Paulo", "Brasil", "SP", "Principal centro econômico e cultural do país."),
    DestinationSeed("campinas", "Campinas", "Brasil", "SP", "Cidade do interior paulista com ampla infraestrutura e acesso rodoviário."),
    DestinationSeed("rio-de-janeiro", "Rio de Janeiro", "Brasil", "RJ", "Praias, paisagens famosas, cultura e gastronomia."),
    DestinationSeed("belo-horizonte", "Belo Horizonte", "Brasil", "MG", "Gastronomia, arquitetura e cultura mineira."),
    DestinationSeed("brasilia", "Brasília", "Brasil", "DF", "Capital federal conhecida pela arquitetura moderna."),
    DestinationSeed("curitiba", "Curitiba", "Brasil", "PR", "Parques, arquitetura e experiências gastronômicas."),
    DestinationSeed("foz-do-iguacu", "Foz do Iguaçu", "Brasil", "PR", "Destino das Cataratas do Iguaçu e de atrações naturais."),
    DestinationSeed("florianopolis", "Florianópolis", "Brasil", "SC", "Ilha com praias, trilhas e gastronomia açoriana."),
    DestinationSeed("porto-alegre", "Porto Alegre", "Brasil", "RS", "Cultura gaúcha, parques e vida urbana."),
    DestinationSeed("gramado", "Gramado", "Brasil", "RS", "Destino de serra com atrações, gastronomia e clima europeu."),
    DestinationSeed("salvador", "Salvador", "Brasil", "BA", "Centro histórico, cultura afro-brasileira e praias."),
    DestinationSeed("recife", "Recife", "Brasil", "PE", "Patrimônio histórico, cultura e litoral pernambucano."),
    DestinationSeed("maceio", "Maceió", "Brasil", "AL", "Praias de águas claras e piscinas naturais."),
    DestinationSeed("fortaleza", "Fortaleza", "Brasil", "CE", "Praias urbanas, cultura e gastronomia nordestina."),
    DestinationSeed("natal", "Natal", "Brasil", "RN", "Dunas, praias e passeios pelo litoral potiguar."),
    DestinationSeed("joao-pessoa", "João Pessoa", "Brasil", "PB", "Praias, centro histórico e paisagens do litoral paraibano."),
    DestinationSeed("manaus", "Manaus", "Brasil", "AM", "Porta de entrada para experiências na região amazônica."),
    DestinationSeed("belem", "Belém", "Brasil", "PA", "Culinária paraense, mercados e cultura amazônica."),
)

# As datas são calculadas a partir do dia em que o script é executado.
# A chave lógica do pacote é título + origem + destino; portanto, reexecutar
# o script não duplica os pacotes já criados nem altera pacotes existentes.
PACKAGES: tuple[PackageSeed, ...] = (
    PackageSeed(
        "Rio de Janeiro — Praias e cultura",
        "Pacote demonstrativo com hospedagem e roteiro livre para conhecer os principais pontos da cidade.",
        "sao-paulo", "rio-de-janeiro", 30, 4, "1890.00", "1280.00", 30,
    ),
    PackageSeed(
        "Salvador — História e litoral",
        "Experiência demonstrativa pelo Pelourinho, orla e gastronomia baiana.",
        "sao-paulo", "salvador", 45, 6, "2790.00", "1940.00", 24,
    ),
    PackageSeed(
        "Foz do Iguaçu — Cataratas",
        "Viagem para conhecer as Cataratas do Iguaçu e os atrativos da região.",
        "sao-paulo", "foz-do-iguacu", 60, 4, "2190.00", "1510.00", 22,
    ),
    PackageSeed(
        "Florianópolis — Praias da ilha",
        "Pacote de lazer com tempo para praias, trilhas e gastronomia local.",
        "sao-paulo", "florianopolis", 75, 5, "2450.00", "1720.00", 28,
    ),
    PackageSeed(
        "Gramado — Serra Gaúcha",
        "Roteiro demonstrativo por Gramado e atrações da Serra Gaúcha.",
        "sao-paulo", "gramado", 90, 5, "3190.00", "2290.00", 20,
    ),
    PackageSeed(
        "Recife — Cultura e praias",
        "Pacote para explorar Recife, Olinda e praias da região.",
        "sao-paulo", "recife", 105, 6, "2890.00", "2050.00", 24,
    ),
    PackageSeed(
        "Maceió — Piscinas naturais",
        "Viagem demonstrativa com praias e passeios pelas piscinas naturais.",
        "sao-paulo", "maceio", 120, 6, "3290.00", "2360.00", 20,
    ),
    PackageSeed(
        "Fortaleza — Sol e litoral",
        "Pacote de férias para conhecer Fortaleza e atrações do litoral cearense.",
        "sao-paulo", "fortaleza", 135, 7, "3490.00", "2490.00", 25,
    ),
    PackageSeed(
        "Natal — Dunas e praias",
        "Roteiro demonstrativo com praias, dunas e passeios pelo litoral potiguar.",
        "sao-paulo", "natal", 150, 6, "3090.00", "2190.00", 22,
    ),
    PackageSeed(
        "Belo Horizonte — Gastronomia mineira",
        "Viagem curta para conhecer a gastronomia e os espaços culturais da capital mineira.",
        "sao-paulo", "belo-horizonte", 165, 3, "1390.00", "920.00", 30,
    ),
    PackageSeed(
        "Curitiba — Cultura e natureza",
        "Pacote urbano com parques, arquitetura e gastronomia curitibana.",
        "sao-paulo", "curitiba", 180, 3, "1290.00", "850.00", 30,
    ),
    PackageSeed(
        "Brasília — Arquitetura moderna",
        "Roteiro demonstrativo pelos principais monumentos e espaços culturais da capital.",
        "sao-paulo", "brasilia", 195, 3, "1590.00", "1080.00", 25,
    ),
    PackageSeed(
        "Rio de Janeiro — Saída de Campinas",
        "Opção de viagem ao Rio de Janeiro com partida em Campinas.",
        "campinas", "rio-de-janeiro", 210, 4, "1990.00", "1370.00", 18,
    ),
    PackageSeed(
        "Salvador — Saída de Brasília",
        "Opção de viagem para aproveitar a cultura e as praias de Salvador.",
        "brasilia", "salvador", 225, 6, "2690.00", "1870.00", 18,
    ),
    PackageSeed(
        "Porto Alegre — Cultura gaúcha",
        "Pacote demonstrativo com atrações culturais e gastronômicas da capital gaúcha.",
        "sao-paulo", "porto-alegre", 240, 4, "2190.00", "1530.00", 20,
    ),
    PackageSeed(
        "Manaus — Experiência amazônica",
        "Viagem demonstrativa para conhecer a cultura e os atrativos da região amazônica.",
        "sao-paulo", "manaus", 255, 6, "3990.00", "2920.00", 16,
    ),
    PackageSeed(
        "João Pessoa — Litoral paraibano",
        "Pacote de lazer com praias e atrações históricas de João Pessoa.",
        "recife", "joao-pessoa", 270, 5, "2290.00", "1590.00", 18,
    ),
    PackageSeed(
        "Belém — Sabores da Amazônia",
        "Roteiro demonstrativo dedicado à culinária, aos mercados e à cultura paraense.",
        "brasilia", "belem", 285, 5, "3190.00", "2280.00", 16,
    ),
)


def _find_admin(db: Session, email: str | None) -> UserModel | None:
    statement = select(UserModel).where(
        UserModel.role == UserRole.ADMIN,
        UserModel.is_active.is_(True),
    )
    if email:
        statement = statement.where(func.lower(UserModel.email) == email.strip().lower())
    return db.scalar(statement.order_by(UserModel.created_at.asc()).limit(1))


def _find_destination(db: Session, seed: DestinationSeed) -> DestinationModel | None:
    return db.scalar(
        select(DestinationModel).where(
            func.lower(DestinationModel.name) == seed.name.lower(),
            func.lower(DestinationModel.country) == seed.country.lower(),
            func.coalesce(func.lower(DestinationModel.state), "") == seed.state.lower(),
        ).limit(1)
    )


def _get_or_create_destinations(db: Session) -> tuple[dict[str, DestinationModel], int]:
    destinations: dict[str, DestinationModel] = {}
    created_count = 0

    for seed in DESTINATIONS:
        destination = _find_destination(db, seed)
        if destination is None:
            destination = DestinationModel(
                name=seed.name,
                country=seed.country,
                state=seed.state,
                description=seed.description,
                is_active=True,
            )
            db.add(destination)
            db.flush()
            created_count += 1

        destinations[seed.key] = destination

    return destinations, created_count


def _package_exists(
    db: Session,
    *,
    title: str,
    origin_id,
    destination_id,
) -> bool:
    existing_id = db.scalar(
        select(TravelPackageModel.id)
        .where(
            func.lower(TravelPackageModel.title) == title.lower(),
            TravelPackageModel.origin_id == origin_id,
            TravelPackageModel.destination_id == destination_id,
        )
        .limit(1)
    )
    return existing_id is not None


def _get_or_create_packages(
    db: Session,
    *,
    destinations: dict[str, DestinationModel],
    admin_id: UUID,
    today: date,
) -> tuple[int, int, int]:
    created_count = 0
    existing_count = 0
    inactive_destination_count = 0

    for seed in PACKAGES:
        origin = destinations[seed.origin]
        destination = destinations[seed.destination]

        if not origin.is_active or not destination.is_active:
            inactive_destination_count += 1
            continue

        if _package_exists(
            db,
            title=seed.title,
            origin_id=origin.id,
            destination_id=destination.id,
        ):
            existing_count += 1
            continue

        departure_date = today + timedelta(days=seed.days_from_today)
        return_date = departure_date + timedelta(days=seed.nights)
        package = TravelPackageModel(
            title=seed.title,
            description=seed.description,
            origin_id=origin.id,
            destination_id=destination.id,
            departure_date=departure_date,
            return_date=return_date,
            price=Decimal(seed.price),
            cost_price=Decimal(seed.cost_price),
            total_seats=seed.total_seats,
            available_seats=seed.total_seats,
            is_active=True,
            created_by=admin_id,
        )
        db.add(package)
        created_count += 1

    db.flush()
    return created_count, existing_count, inactive_destination_count


def _invalidate_catalog_cache() -> None:
    """Invalida caches públicos; falha de Redis não desfaz o seed no PostgreSQL."""
    from redis.exceptions import RedisError

    from app.redis.cache import RedisCache
    from app.redis.connection import redis_client

    try:
        cache = RedisCache(redis_client)
        removed_destinations = cache.invalidate_prefix("destinations")
        removed_packages = cache.invalidate_prefix("packages")
        logger.info(
            "Cache invalidado: %s chaves de destinos e %s de pacotes.",
            removed_destinations,
            removed_packages,
        )
    except RedisError:
        logger.warning(
            "Não foi possível invalidar o cache Redis. As entradas antigas expirarão pelo TTL.",
            exc_info=True,
        )
    finally:
        redis_client.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Insere destinos e pacotes demonstrativos na Travel API."
    )
    parser.add_argument(
        "--admin-email",
        help="Email do administrador que será associado aos pacotes criados.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Executa as consultas e contagens, mas desfaz todas as alterações.",
    )
    args = parser.parse_args()

    today = date.today()
    try:
        today = datetime.now(ZoneInfo(settings.app_timezone)).date()
    except ZoneInfoNotFoundError:
        logger.warning("Timezone %s indisponível; usando date.today().", settings.app_timezone)

    with SessionLocal() as db:
        try:
            admin = _find_admin(db, args.admin_email)
            if admin is None:
                selector = f" com email {args.admin_email}" if args.admin_email else ""
                raise SystemExit(
                    "Nenhum administrador ativo encontrado" + selector + ". "
                    "Crie o primeiro administrador com `python -m app.scripts.create_admin`."
                )

            destinations, destinations_created = _get_or_create_destinations(db)
            packages_created, packages_existing, packages_skipped_inactive = _get_or_create_packages(
                db,
                destinations=destinations,
                admin_id=admin.id,
                today=today,
            )

            if args.dry_run:
                db.rollback()
                print("DRY RUN — nenhuma alteração foi persistida.")
            else:
                db.commit()

        except SystemExit:
            db.rollback()
            raise
        except IntegrityError as exc:
            db.rollback()
            raise SystemExit(
                "Falha de integridade ao inserir os dados. Confira as migrations e os registros existentes."
            ) from exc
        except Exception:
            db.rollback()
            raise

    print("\nSeed do catálogo concluído.")
    print(f"Administrador responsável: {admin.email} ({admin.id})")
    print(f"Destinos criados: {destinations_created}")
    print(f"Pacotes criados: {packages_created}")
    print(f"Pacotes já existentes (preservados): {packages_existing}")
    print(f"Pacotes ignorados por destino inativo: {packages_skipped_inactive}")
    print(f"Data-base usada para novas viagens: {today.isoformat()}")

    if not args.dry_run:
        _invalidate_catalog_cache()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    main()
