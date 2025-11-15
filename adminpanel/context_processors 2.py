def role_flags(request):
    user = request.user
    if not user.is_authenticated:
        return {
            'can_catalogue': False,
            'can_inventory': False,
            'can_customers': False,
            'can_staff': False,
        }
    names = set(user.groups.values_list('name', flat=True))
    is_admin = user.is_superuser or 'Admin' in names
    return {
        'can_catalogue': is_admin or 'Manager' in names or 'Merchandiser' in names,
        'can_inventory': is_admin or 'Manager' in names or 'Merchandiser' in names or 'Inventory' in names,
        'can_customers': is_admin or 'Manager' in names or 'Support' in names,
        'can_staff': is_admin,
    }