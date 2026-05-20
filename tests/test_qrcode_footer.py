from fastapi.testclient import TestClient

import app as survey_app


def test_survey_footer_includes_qrcode_and_follow_prompt():
    client = TestClient(survey_app.app)

    response = client.get("/")

    assert response.status_code == 200
    assert 'src="/QRcode.png"' in response.text
    assert 'alt="公众号二维码"' in response.text
    assert "欢迎关注公众号，了解更多详情。" in response.text


def test_qrcode_image_is_served():
    client = TestClient(survey_app.app)

    response = client.get("/QRcode.png")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG")
