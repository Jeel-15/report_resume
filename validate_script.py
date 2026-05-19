import inspect
from flask import Flask, jsonify
from app import app
from routes import admin

def validate():
    endpoints = {
        'get_payments': admin.get_payments,
        'get_departments': admin.get_departments,
        'get_universities': admin.get_universities,
        'get_industries': admin.get_industries
    }
    
    class DummyUser:
        pass

    print("--- Endpoint Validation ---")
    for name, func in endpoints.items():
        try:
            unwrapped = inspect.unwrap(func)
            with app.test_request_context(query_string={'limit': 2, 'offset': 1, 'q': 'a'}):
                # Pass a dummy user to the function
                response = unwrapped(current_user=DummyUser())
                
                if hasattr(response, 'get_json'):
                    data = response.get_json()
                elif isinstance(response, tuple):
                    data = response[0].get_json() if hasattr(response[0], 'get_json') else response[0]
                else:
                    data = response
                
                shape = "dict(items/total)" if isinstance(data, dict) and 'items' in data else f"list({len(data)})" if isinstance(data, list) else str(type(data))
                print(f"{name}: {shape}")
        except Exception as e:
            print(f"{name} failed: {e}")

    print("\n--- Serialization Validation ---")
    try:
        class Dummy:
            def __init__(self, data):
                self._data = data
            def __getattr__(self, name):
                raise AttributeError(name)

        industry_data = {'id': 1, 'name': 'Tech'}
        dummy_industry = Dummy(industry_data)
        
        serialized = admin._serialize_industry(dummy_industry)
        print(f"Serialized keys: {list(serialized.keys())}")
        print("Success: True")
    except Exception as e:
        print(f"Serialization failed: {e}")

if __name__ == '__main__':
    validate()
