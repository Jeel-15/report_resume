import unittest

from app import app
from routes import admin as admin_routes
from routes import student as student_routes


class AdminPaginationHelperTests(unittest.TestCase):
    def test_no_params_returns_none_limit(self):
        with app.test_request_context('/api/admin/users'):
            limit, offset, requested = admin_routes._parse_pagination(default_limit=None, max_limit=500)
        self.assertIsNone(limit)
        self.assertEqual(offset, 0)
        self.assertFalse(requested)

    def test_negative_offset_is_normalized(self):
        with app.test_request_context('/api/admin/users?offset=-10'):
            limit, offset, requested = admin_routes._parse_pagination(default_limit=100, max_limit=500)
        self.assertEqual(limit, 100)
        self.assertEqual(offset, 0)
        self.assertTrue(requested)

    def test_huge_limit_is_clamped(self):
        with app.test_request_context('/api/admin/users?limit=999999'):
            limit, offset, requested = admin_routes._parse_pagination(default_limit=None, max_limit=500)
        self.assertEqual(limit, 500)
        self.assertEqual(offset, 0)
        self.assertTrue(requested)

    def test_offset_only_keeps_none_limit(self):
        with app.test_request_context('/api/admin/users?offset=30'):
            limit, offset, requested = admin_routes._parse_pagination(default_limit=None, max_limit=500)
        self.assertIsNone(limit)
        self.assertEqual(offset, 30)
        self.assertTrue(requested)


class StudentPaginationHelperTests(unittest.TestCase):
    def test_no_params_uses_default_when_provided(self):
        with app.test_request_context('/api/student/universities'):
            limit, offset = student_routes._parse_pagination(default_limit=50, max_limit=200)
        self.assertEqual(limit, 50)
        self.assertEqual(offset, 0)

    def test_negative_offset_is_normalized(self):
        with app.test_request_context('/api/student/universities?offset=-3'):
            limit, offset = student_routes._parse_pagination(default_limit=50, max_limit=200)
        self.assertEqual(limit, 50)
        self.assertEqual(offset, 0)

    def test_huge_limit_is_clamped(self):
        with app.test_request_context('/api/student/universities?limit=100000'):
            limit, offset = student_routes._parse_pagination(default_limit=None, max_limit=200)
        self.assertEqual(limit, 200)
        self.assertEqual(offset, 0)

    def test_offset_only_uses_default_limit_when_present(self):
        with app.test_request_context('/api/student/universities?offset=40'):
            limit, offset = student_routes._parse_pagination(default_limit=50, max_limit=200)
        self.assertEqual(limit, 50)
        self.assertEqual(offset, 40)


if __name__ == '__main__':
    unittest.main()
