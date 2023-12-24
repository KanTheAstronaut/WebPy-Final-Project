import unittest

from main import app

class Test(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        pass

    def test_index_route(self):
        response = self.app.get("/")
        self.assertEqual(response.status_code, 302) # because youre not authenticated

    def test_login_route(self):
        response = self.app.get("/auth/login")
        self.assertEqual(response.status_code, 200)

    def test_signup_route(self):
        response = self.app.get("/auth/signup")
        self.assertEqual(response.status_code, 200)

    def test_profile_route(self):
        response = self.app.get("/profiles/profile")
        self.assertEqual(response.status_code, 302)