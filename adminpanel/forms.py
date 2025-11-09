# ...existing code...
from django import forms
from onlineshopfront.models import Product, Category, SubCategory
from django.contrib.auth.models import User, Group
from django.contrib.auth.forms import UserCreationForm
 
class ProductForm(forms.ModelForm):
     class Meta:
         model = Product
         fields = '__all__'
         widgets = {
            'product_description': forms.Textarea(attrs={'rows': 3}),
        }
         
class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['category_name']

class SubCategoryForm(forms.ModelForm):
    class Meta:
        model = SubCategory
        fields = ['subcategory_name', 'category']

class StockUpdateForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['quantity_on_hand', 'reorder_quantity']
        widgets = {
            'quantity_on_hand': forms.NumberInput(attrs={'min': 0}),
            'reorder_quantity': forms.NumberInput(attrs={'min': 0}),
        }

class StaffUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(required=False)
    last_name = forms.CharField(required=False)
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email', 'first_name', 'last_name',)

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data.get('first_name', '')
        user.last_name = self.cleaned_data.get('last_name', '')
        user.is_staff = True
        if commit:
            user.save()
            user.groups.set(self.cleaned_data.get('groups', []))
        return user

