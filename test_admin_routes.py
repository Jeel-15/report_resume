import inspect
import json
from flask import Flask, request
from app import app
import routes.admin as admin_routes

class FakeUser:
    def __init__(self, role, id):
        self.role = role
        self.id = id
        self.is_authenticated = True

def test_endpoint(name, func, query_string):
    print(f"Testing {name} with {query_string}...")
    try:
        unwrapped = inspect.unwrap(func)
        fake_user = FakeUser(role='admin', id='test')
        with app.test_request_context(query_string=query_string):
            # Pass fake_user as current_user argument since the route expects it
            response = unwrapped(current_user=fake_user)
            
            if isinstance(response, tuple):
                data = response[0]
            elif hasattr(response, 'get_json'):
                data = response.get_json()
            else:
                data = response

            if hasattr(data, 'decode'): data = data.decode('utf-8')
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except:
                    pass

            if isinstance(data, dict):
                keys = ["items", "total", "limit", "offset"]
                present = [k for k in keys if k in data]
                item_count = len(data.get("items", []))
                print(f"  Result: dict, keys {present}, items: {item_count}")
            else:
                print(f"  Result: Not a dict, type: {type(data)}")
    except Exception as e:
        print(f"  Error: {e}")

if __name__ == '__main__':
    test_endpoint("get_users", admin_routes.get_users, "limit=2&offset=1")
    test_endpoint("get_reports", admin_routes.get_reports, "limit=2&offset=1")
    test_endpoint("get_work_keywords", admin_routes.get_work_keywords, "limit=2&offset=1&q=a")
