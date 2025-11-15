from django import forms
from onlineshopfront.models import Product, Category, SubCategory
from django.contrib.auth.models import User, Group
from django.contrib.auth.forms import UserCreationForm
 
ROLE_CHOICES = [
    ('Admin', 'Admin'),
    ('Manager', 'Manager'),
    ('Merchandiser', 'Merchandiser'),
    ('Inventory', 'Inventory'),
    ('Support', 'Support'),
]

class BulkProductUploadForm(forms.Form):
    file = forms.FileField(help_text="CSV file (UTF-8)")
    update_existing = forms.BooleanField(required=False, initial=False, help_text="Update rows if SKU already exists.")

class SubCategoryChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.category.category_name} — {obj.subcategory_name}"

_HAS_CATEGORY_FIELD = any(f.name == 'category' for f in Product._meta.fields)

class ProductForm(forms.ModelForm):
    product_subcategory = SubCategoryChoiceField(queryset=SubCategory.objects.none(), empty_label="Select…")

    class Meta:
        model = Product
        exclude = ['category'] if _HAS_CATEGORY_FIELD else []
        widgets = {
            'product_description': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product_subcategory'].queryset = (
            SubCategory.objects.select_related('category')
            .order_by('category__category_name', 'subcategory_name')
        )

    def save(self, commit=True):
        instance = super().save(commit=False)
        # If the model has a separate 'category' FK, sync it from the chosen subcategory
        if _HAS_CATEGORY_FIELD and instance.product_subcategory_id:
            instance.category = instance.product_subcategory.category
        if commit:
            instance.save()
            self.save_m2m()
        return instance
         
class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['category_name']
        widgets = {
            'category_name': forms.TextInput(attrs={'class':'input','placeholder':'Category name'}),
        }

class SubCategoryForm(forms.ModelForm):
    class Meta:
        model = SubCategory
        fields = ['subcategory_name', 'category']
        widgets = {
            'subcategory_name': forms.TextInput(attrs={'class':'input','placeholder':'Subcategory name'}),
            'category': forms.Select(attrs={'class':'input'}),
        }

class StockUpdateForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['quantity_on_hand', 'reorder_quantity']
        widgets = {
            'quantity_on_hand': forms.NumberInput(attrs={'min': 0}),
            'reorder_quantity': forms.NumberInput(attrs={'min': 0}),
        }

class StaffUserCreationForm(UserCreationForm):
    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)
    email = forms.EmailField(required=True)
    role = forms.ChoiceField(choices=ROLE_CHOICES, required=True)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'role')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.email = self.cleaned_data['email']
        user.is_staff = True
        selected_role = self.cleaned_data['role']
        user.is_superuser = (selected_role == 'Admin')
        if commit:
            user.save()
            grp, _ = Group.objects.get_or_create(name=selected_role)
            user.groups.set([grp])
        return user

class StaffUserRoleForm(forms.ModelForm):
    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)
    email = forms.EmailField(required=True)
    role = forms.ChoiceField(choices=ROLE_CHOICES, required=True)

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'role']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        current = self.instance.groups.values_list('name', flat=True)
        self.initial['role'] = next((r for r in current if r in dict(ROLE_CHOICES)), '')

    def save(self, commit=True):
        user = super().save(commit=False)
        selected_role = self.cleaned_data['role']
        user.is_staff = True
        user.is_superuser = (selected_role == 'Admin')
        if commit:
            user.save()
            grp, _ = Group.objects.get_or_create(name=selected_role)
            user.groups.set([grp])
        return user