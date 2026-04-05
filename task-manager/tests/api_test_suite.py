import urllib.request
import json
import os
import unittest

BASE_URL = os.environ.get("TASK_MANAGER_TEST_URL", "http://localhost:6543")
API_KEY = os.environ.get("TASK_MANAGER_API_KEY", "dev_local_key")

class TestTaskManagerAPI(unittest.TestCase):
    def request(self, method, path, body=None):
        url = f"{BASE_URL}{path}"
        headers = {"x-api-key": API_KEY}
        data = None
        if body:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req) as response:
                return response.getcode(), json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode("utf-8"))
        except Exception as e:
            print(f"Error connecting to {url}: {e}")
            raise

    def test_health(self):
        code, data = self.request("GET", "/api/health")
        self.assertEqual(code, 200)
        self.assertEqual(data["status"], "ok")

    def test_project_crud(self):
        # CREATE
        payload = {"name": "Test Project", "description": "A project for testing"}
        code, p = self.request("POST", "/api/projects", body=payload)
        self.assertEqual(code, 200)
        p_id = p["id"]

        # UPDATE
        update_payload = {"name": "Test Project Updated"}
        code, p_updated = self.request("PUT", f"/api/projects/{p_id}", body=update_payload)
        self.assertEqual(code, 200)

        # DELETE
        code, res = self.request("DELETE", f"/api/projects/{p_id}")
        self.assertEqual(code, 200)
        self.assertEqual(res, {"ok": True})

    def test_lifecycle(self):
        # 1. Project
        _, p = self.request("POST", "/api/projects", {"name": "LifeCycle"})
        p_id = p["id"]
        
        # 2. Group
        _, g = self.request("POST", "/api/groups", {"name": "G1", "project_id": p_id})
        g_id = g["id"]

        # 3. Task
        _, t = self.request("POST", "/api/tasks", {"title": "T1", "group_id": g_id, "project_id": p_id})
        t_id = t["id"]
        
        # 4. Verify in Data
        _, data = self.request("GET", "/api/data")
        self.assertTrue(any(x["id"] == g_id for x in data["groups"]))
        
        # 5. Delete Project (Cascade)
        self.request("DELETE", f"/api/projects/{p_id}")
        
        # 6. Verify Gone
        _, data2 = self.request("GET", "/api/data")
        self.assertFalse(any(x["id"] == g_id for x in data2["groups"]))

if __name__ == "__main__":
    unittest.main()
