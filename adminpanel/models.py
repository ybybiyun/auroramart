from django.db import models
from onlineshopfront.models import Product

class HiddenProduct(models.Model):
    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name='hidden_flag')
    hidden_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Hidden: {self.product.sku}"