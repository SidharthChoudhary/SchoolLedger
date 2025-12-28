from django.core.management.base import BaseCommand
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from accounts.models import Role


class Command(BaseCommand):
    help = 'Initialize roles and permissions for the School Ledger System'

    def handle(self, *args, **options):
        # Define permissions
        permissions_config = {
            'Expense Permissions': [
                ('view_expense', 'Can view expenses'),
                ('add_expense', 'Can add expenses'),
                ('edit_expense', 'Can edit expenses'),
                ('delete_expense', 'Can delete expenses'),
                ('export_expense', 'Can export expenses'),
            ],
            'Income Permissions': [
                ('view_income', 'Can view income'),
                ('add_income', 'Can add income'),
                ('edit_income', 'Can edit income'),
                ('delete_income', 'Can delete income'),
                ('export_income', 'Can export income'),
            ],
            'Head Permissions': [
                ('view_head', 'Can view account heads'),
                ('add_head', 'Can add account heads'),
                ('edit_head', 'Can edit account heads'),
                ('delete_head', 'Can delete account heads'),
                ('export_head', 'Can export account heads'),
            ],
            'Employee Permissions': [
                ('view_employee', 'Can view employees'),
                ('add_employee', 'Can add employees'),
                ('edit_employee', 'Can edit employees'),
                ('delete_employee', 'Can delete employees'),
                ('export_employee', 'Can export employees'),
            ],
            'User Permissions': [
                ('manage_users', 'Can manage users'),
                ('manage_roles', 'Can manage roles'),
            ],
        }
        
        # Create permissions
        app_label = 'accounts'
        content_type = ContentType.objects.get_or_create(app_label=app_label, model='permission')[0]
        
        created_permissions = {}
        for category, perms in permissions_config.items():
            for codename, name in perms:
                perm, created = Permission.objects.get_or_create(
                    codename=codename,
                    content_type=content_type,
                    defaults={'name': name}
                )
                created_permissions[codename] = perm
                status = 'Created' if created else 'Already exists'
                self.stdout.write(f'{status}: {name}')
        
        # Define roles and their permissions
        roles_config = [
            {
                'name': 'super_admin',
                'display_name': 'Super Admin',
                'description': 'Full access to all system features',
                'permissions': list(created_permissions.keys()),  # All permissions
            },
            {
                'name': 'admin',
                'display_name': 'Admin',
                'description': 'Administrative access to ledger and user management',
                'permissions': [
                    'view_expense', 'add_expense', 'edit_expense', 'delete_expense', 'export_expense',
                    'view_income', 'add_income', 'edit_income', 'delete_income', 'export_income',
                    'view_head', 'add_head', 'edit_head', 'delete_head', 'export_head',
                    'view_employee', 'add_employee', 'edit_employee',
                    'manage_users', 'manage_roles',
                ],
            },
            {
                'name': 'principal',
                'display_name': 'Principal',
                'description': 'Principal access - can view and manage finances',
                'permissions': [
                    'view_expense', 'view_income', 'view_head',
                    'view_employee', 'manage_users',
                ],
            },
            {
                'name': 'accountant',
                'display_name': 'Accountant',
                'description': 'Can manage all ledger entries and reports',
                'permissions': [
                    'view_expense', 'add_expense', 'edit_expense', 'export_expense',
                    'view_income', 'add_income', 'edit_income', 'export_income',
                    'view_head', 'add_head', 'edit_head',
                ],
            },
            {
                'name': 'teacher',
                'display_name': 'Teacher',
                'description': 'Limited access to employee and student information',
                'permissions': [
                    'view_employee',
                ],
            },
            {
                'name': 'support_staff',
                'display_name': 'Support Staff',
                'description': 'Basic access to system',
                'permissions': [
                    'view_employee',
                ],
            },
        ]
        
        # Create roles
        self.stdout.write('\n--- Creating Roles ---')
        for role_config in roles_config:
            role, created = Role.objects.get_or_create(
                name=role_config['name'],
                defaults={
                    'display_name': role_config['display_name'],
                    'description': role_config['description'],
                    'is_active': True,
                }
            )
            
            # Add permissions to role
            perm_objs = [
                created_permissions[codename]
                for codename in role_config['permissions']
                if codename in created_permissions
            ]
            role.permissions.set(perm_objs)
            
            status = 'Created' if created else 'Already exists'
            self.stdout.write(f'{status}: {role.display_name} with {len(perm_objs)} permissions')
        
        self.stdout.write(self.style.SUCCESS('\n✓ Roles and permissions initialized successfully!'))
