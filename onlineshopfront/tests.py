from django.test import TestCase
from django.urls import reverse


class AuthSmokeTests(TestCase):
	def test_register_and_login(self):
		"""Smoke test: register a new user via create-account then login."""
		reg_url = reverse('onlineshopfront:create_account')
		login_url = reverse('onlineshopfront:login')
		email = 'smoketest@example.com'
		pwd = 'TestPass123!'

		# Register
		resp = self.client.post(reg_url, data={
			'first_name': 'Smoke',
			'last_name': 'Test',
			'email': email,
			'password': pwd,
			'confirm_password': pwd,
		}, follow=True)
		# After successful registration the user should be authenticated
		self.assertEqual(resp.status_code, 200)
		self.assertTrue(resp.wsgi_request.user.is_authenticated)

		# Log out
		self.client.get(reverse('onlineshopfront:logout'))

		# Login
		resp2 = self.client.post(login_url, data={'email': email, 'password': pwd}, follow=True)
		self.assertEqual(resp2.status_code, 200)
		self.assertTrue(resp2.wsgi_request.user.is_authenticated)
