from datetime import date

from fastapi import APIRouter, Depends, Query

from app.api.dependencies.permissions import require_roles
from app.domains.shared.enums import UserRole
from app.modules.calendar.dependencies import get_calendar_service
from app.modules.calendar.schemas import TravelCalendarResponse
from app.modules.calendar.service import CalendarService
from app.modules.users.models import UserModel

router = APIRouter(prefix="/purchases/me", tags=["My travel calendar"])


@router.get(
    "/calendar",
    response_model=TravelCalendarResponse,
    summary="Consultar calendário das minhas viagens",
    description=(
        "Retorna viagens confirmadas/concluídas que intersectam o período. "
        "A lista days marca cada data ocupada, incluindo o dia de partida e o de retorno. "
        "Sem datas, consulta o mês civil atual no fuso da aplicação."
    ),
)
def get_my_travel_calendar(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    current_user: UserModel = Depends(require_roles(UserRole.CLIENT)),
    service: CalendarService = Depends(get_calendar_service),
) -> TravelCalendarResponse:
    return service.get_calendar(
        user_id=current_user.id,
        start_date=start_date,
        end_date=end_date,
    )
