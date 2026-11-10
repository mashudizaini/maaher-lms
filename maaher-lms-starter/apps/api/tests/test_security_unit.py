import unittest
from uuid import uuid4

from app.security import Principal, authorize, new_token, token_digest


class SecurityTests(unittest.TestCase):
    def test_session_tokens_are_independent_and_not_stored_raw(self):
        a, b = new_token(), new_token()
        self.assertNotEqual(a, b)
        self.assertGreaterEqual(len(a), 32)
        self.assertNotEqual(token_digest(a), a)
        self.assertEqual(len(token_digest(a)), 64)
        self.assertEqual(token_digest(a), token_digest(a))

    def test_role_matrix_and_unknown_roles_fail_closed(self):
        for role in ("student", "teacher", "admin", "operator", "", "ADMIN"):
            with self.subTest(role=role):
                actor = Principal(uuid4(), uuid4(), role)
                self.assertEqual(authorize(actor, {"admin"}), role == "admin")
                self.assertEqual(authorize(actor, {"teacher", "admin"}),
                                 role in {"teacher", "admin"})
                self.assertFalse(authorize(actor, set()))


if __name__ == "__main__":
    unittest.main()
