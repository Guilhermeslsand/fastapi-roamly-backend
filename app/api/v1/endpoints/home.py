from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(
    tags=["home"],
)

@router.get("/", summary="Página inicial")
def home():
    html_content = """
    <html>
        <head>
            <title>Travel API</title>
        </head>
        <body>
            <h1>Bem-vindo à API de pacotes de viagem!</h1>
            <p>API está funcionando corretamente.</p>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)