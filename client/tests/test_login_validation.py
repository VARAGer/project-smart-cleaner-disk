import unittest

from client.gui.login_window import validate_auth_input


class LoginValidationTestCase(unittest.TestCase):
    def test_login_allows_short_password_to_reach_backend(self):
        self.assertIsNone(validate_auth_input("login", "ghost", "123"))

    def test_register_rejects_short_password_before_backend_request(self):
        message = validate_auth_input("register", "ghost", "123")

        self.assertEqual(
            message,
            "Пароль должен быть не короче 10 символов и содержать хотя бы одну букву и одну цифру.",
        )


if __name__ == "__main__":
    unittest.main()
