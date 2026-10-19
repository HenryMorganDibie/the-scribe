"""Compatibility checks for security-sensitive dependency upgrades."""
from datetime import timedelta
from io import BytesIO

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.testclient import TestClient
import jwt
from pypdf import PdfReader, PdfWriter

from app.core.config import settings
from app.core.security import create_access_token


def test_pyjwt_round_trip():
    token = create_access_token(
        {"sub": "dependency-check-user"},
        expires_delta=timedelta(minutes=5),
    )

    payload = jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
    )

    assert payload["sub"] == "dependency-check-user"


def test_python_multipart_parses_login_forms_and_file_uploads():
    app = FastAPI()

    @app.post("/login")
    async def login(username: str = Form(...), password: str = Form(...)):
        return {"username": username, "password_length": len(password)}

    @app.post("/upload")
    async def upload(file: UploadFile = File(...)):
        content = await file.read()
        return {"filename": file.filename, "size": len(content)}

    with TestClient(app) as client:
        login_response = client.post(
            "/login",
            data={"username": "author@example.com", "password": "secret"},
        )
        upload_response = client.post(
            "/upload",
            files={"file": ("sermon.txt", b"sermon content", "text/plain")},
        )

    assert login_response.status_code == 200
    assert login_response.json() == {
        "username": "author@example.com",
        "password_length": 6,
    }
    assert upload_response.status_code == 200
    assert upload_response.json() == {"filename": "sermon.txt", "size": 14}


def test_pypdf_reads_generated_pdf():
    output = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.write(output)

    reader = PdfReader(BytesIO(output.getvalue()))

    assert len(reader.pages) == 1
