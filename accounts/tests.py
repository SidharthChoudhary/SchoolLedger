from django.test import TestCase
from django.contrib.auth.models import User, Permission
from .models import Role, UserRole, UserProfile


class RoleModelTests(TestCase):
    def setUp(self):
        self.role = Role.objects.create(
            name='accountant',
            display_name='Accountant',
            description='Can manage ledger'
        )
        self.user = User.objects.create_user(
            username='test_user',
            password='testpass123'
        )
    
    def test_role_creation(self):
        self.assertEqual(self.role.display_name, 'Accountant')
        self.assertTrue(self.role.is_active)
    
    def test_user_role_assignment(self):
        user_role = UserRole.objects.create(
            user=self.user,
            role=self.role
        )
        self.assertEqual(self.user.user_roles.count(), 1)
        self.assertEqual(user_role.role, self.role)


class UserProfileTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='profile_test',
            password='testpass123'
        )
        self.role = Role.objects.create(
            name='admin',
            display_name='Admin'
        )
    
    def test_user_profile_auto_creation(self):
        # Profile should be auto-created via signal
        self.assertTrue(hasattr(self.user, 'profile'))
        self.assertEqual(self.user.profile.full_name, 'profile_test')
    
    def test_has_role(self):
        UserRole.objects.create(user=self.user, role=self.role)
        self.assertTrue(self.user.profile.has_role('admin'))
        self.assertFalse(self.user.profile.has_role('accountant'))
    
    def test_has_any_role(self):
        UserRole.objects.create(user=self.user, role=self.role)
        self.assertTrue(self.user.profile.has_any_role(['admin', 'teacher']))
        self.assertFalse(self.user.profile.has_any_role(['teacher', 'accountant']))
