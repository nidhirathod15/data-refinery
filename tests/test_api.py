"""API tests. Need: pip install -r requirements-dev.txt"""
import io
import re

from fastapi.testclient import TestClient

from app import main

client = TestClient(main.app)
CSV = b"company,service,date\nAcme,react website,02/09/2024\nAcme,react website,02/09/2024\n"


def upload(name, content=CSV):
    return client.post("/process", files={"file": (name, io.BytesIO(content), "text/csv")})


def test_upload_returns_preview_and_download_link():
    r = upload("data.csv")
    assert r.status_code == 200 and "Data Preview" in r.text
    link = re.search(r'href="(/download/[^"]+)"', r.text).group(1)
    assert client.get(link).status_code == 200


def test_uppercase_extension_works():
    assert upload("DATA.CSV").status_code == 200


def test_unsupported_extension_rejected():
    assert upload("evil.exe").status_code == 400


def test_path_traversal_filename_is_harmless(tmp_path):
    r = upload("../../etc/passwd.csv")
    assert r.status_code == 200
    assert not (tmp_path.parent / "etc").exists()


def test_download_rejects_arbitrary_names():
    assert client.get("/download/main.py").status_code == 404
    assert client.get("/download/..%2Fmain.py").status_code == 404


def test_oversized_upload_rejected():
    big = b"a,b\n" + b"1,2\n" * (3 * 1024 * 1024)
    assert upload("big.csv", big).status_code == 413
