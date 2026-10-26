from fastapi.testclient import TestClient


TEST_PASSWORD = "A-long-test-password-123!"


class AuthenticatedTestClient(TestClient):
    def __init__(self, app, *, email="test@example.ch", register=True):
        super().__init__(app, base_url="https://testserver")
        token = self.get("/api/v1/auth/csrf").json()["csrf_token"]
        if register:
            response = super().post(
                "/api/v1/auth/register",
                headers={"X-CSRF-Token": token},
                json={
                    "email": email,
                    "password": TEST_PASSWORD,
                    "first_name": "Test",
                    "last_name": "Employer",
                },
            )
            assert response.status_code == 201
        else:
            response = super().post(
                "/api/v1/auth/login",
                headers={"X-CSRF-Token": token},
                json={"email": email, "password": TEST_PASSWORD},
            )
            assert response.status_code == 200

    def post(self, url, *args, **kwargs):
        if url in {"/api/v1/setup", "/api/v1/monthly-payroll"}:
            token = self.get("/api/v1/auth/csrf").json()["csrf_token"]
            kwargs["headers"] = {**kwargs.get("headers", {}), "X-CSRF-Token": token}
        return super().post(url, *args, **kwargs)
