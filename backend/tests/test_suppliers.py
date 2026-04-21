def login_headers(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "ouyang", "password": "ouyang123"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_supplier_register_list_review_flow(client):
    register_payload = {
        "company_name": "湖北联德钢材有限公司",
        "unified_credit_code": "91420100MA4K123456",
        "legal_person": "张三",
        "founded_date": "2020-05-01",
        "registered_address": "湖北省随州市高新区",
        "registered_capital": "500.00",
        "company_type": "有限责任公司",
        "taxpayer_type": "general",
        "business_intro": "主营钢材与紧固件供应。",
        "contact_name": "李四",
        "contact_phone": "13900000001",
        "contact_email": "supplier@example.com",
        "contact_position": "销售经理",
        "wechat": "steel-li",
        "landline": "0722-1234567",
        "login_password": "abc12345",
        "categories": ["steel", "fasteners"],
        "qualifications": [{"type": "business_license", "url": "./uploads/license.pdf"}],
    }
    register_response = client.post("/api/v1/suppliers/register", json=register_payload)
    assert register_response.status_code == 201
    body = register_response.json()
    assert body["status"] == "pending"
    assert body["code"].startswith("SUP")

    headers = login_headers(client)

    list_response = client.get("/api/v1/suppliers", headers=headers)
    assert list_response.status_code == 200
    list_body = list_response.json()
    assert list_body["total"] == 1
    assert list_body["items"][0]["status"] == "pending"

    supplier_id = body["id"]
    review_response = client.post(
        f"/api/v1/suppliers/{supplier_id}/review",
        headers=headers,
        json={"action": "approve", "grade": "A", "note": "资料齐全，审核通过"},
    )
    assert review_response.status_code == 200
    assert review_response.json()["status"] == "approved"
    assert review_response.json()["grade"] == "A"

    approved_list_response = client.get("/api/v1/suppliers?status=approved", headers=headers)
    assert approved_list_response.status_code == 200
    approved_items = approved_list_response.json()["items"]
    assert len(approved_items) == 1
    assert approved_items[0]["status"] == "approved"
