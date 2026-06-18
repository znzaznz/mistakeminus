"""S0 接口级测试：/health 契约。"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_200_and_contract():
    resp = client.get("/health")
    assert resp.status_code == 200

    body = resp.json()
    assert body["status"] in ("ok", "degraded")
    assert body["database"] in ("ok", "error")

    # 4 个关键配置项都应被报告（值为 bool，存在性而非内容）
    config = body["config"]
    for key in (
        "DASHSCOPE_API_KEY",
        "DASHSCOPE_BASE_URL",
        "QWEN_VL_MODEL",
        "QWEN_TEXT_MODEL",
    ):
        assert key in config
        assert isinstance(config[key], bool)


def test_health_never_leaks_key_value():
    """健康检查响应里不应出现任何真实 key 值。"""
    body = client.get("/health").json()
    text = str(body)
    # 配置里若填了 key，响应中也不该出现其明文
    from app.config import settings

    if settings.dashscope_api_key.strip():
        assert settings.dashscope_api_key not in text
