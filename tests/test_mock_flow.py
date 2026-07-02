"""
test_mock_flow.py — MOCK 模式下的整条流程冒烟测试（不发真实 HTTP）。

走 Flask test client：/config → /api/connect → /api/balance，断言：
  - MOCK=1 时无需真实 Broker 凭证即可跑通
  - 连接成功 ok=True，apiKey 打码返回
  - secretKey / passphrase 等敏感字段不出现在任何响应里
  - 余额结构含 totalEq / details 字段
"""
import importlib

import pytest


@pytest.fixture()
def client(monkeypatch):
    # 开启 MOCK，并清掉可能影响默认值的环境变量
    monkeypatch.setenv("MOCK", "1")
    monkeypatch.delenv("CLIENT_ID", raising=False)
    monkeypatch.delenv("CLIENT_SECRET", raising=False)
    # app.py 在模块加载时读取环境变量，需在设置 MOCK 后重新导入
    import app as app_module
    importlib.reload(app_module)
    app_module.app.config.update(TESTING=True)
    with app_module.app.test_client() as c:
        yield c


def test_config_reports_mock(client):
    cfg = client.get("/config").get_json()
    assert cfg["mock"] is True
    assert cfg["simulated"] is True  # 默认仍是模拟盘


def test_full_mock_flow_and_no_secret_leak(client):
    # 1) 连接：用任意假 code 即可（MOCK 不校验上游）
    connect = client.post("/api/connect", json={"code": "mock-code"})
    body = connect.get_json()
    assert connect.status_code == 200
    assert body["ok"] is True
    assert body["perm"] == "read_only"
    assert body["simulated"] is True
    # apiKey 应被打码（含 ****），且原始 secret 不出现
    assert "****" in body["api_key_masked"]

    raw = connect.get_data(as_text=True)
    assert "mock-secret" not in raw
    assert "secretKey" not in raw
    assert "passphrase" not in raw

    # 2) 查询余额（test client 自动携带 connect 设置的 demo_sid cookie）
    bal = client.get("/api/balance")
    bal_body = bal.get_json()
    assert bal.status_code == 200
    assert bal_body["ok"] is True
    data = bal_body["raw"]["data"][0]
    assert "totalEq" in data
    assert any(d["ccy"] == "USDT" for d in data["details"])

    # 余额响应里也不应泄露 secret（balance 不返回凭证）
    assert "mock-secret" not in bal.get_data(as_text=True)


def test_balance_requires_connect_first(client):
    # 未连接（无 cookie）直接查余额应被拒
    fresh = client.get("/api/balance")
    assert fresh.status_code == 400
    assert fresh.get_json()["ok"] is False


def test_balance_ccy_filter(client):
    client.post("/api/connect", json={"code": "mock-code"})
    bal = client.get("/api/balance?ccy=BTC").get_json()
    details = bal["raw"]["data"][0]["details"]
    assert [d["ccy"] for d in details] == ["BTC"]
