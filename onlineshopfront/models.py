from django.db import models
# Create your models here.
class Customer(models.Model):
    GENDER = [
        ('Male', 'Male'),
        ('Female', 'Female')
    ]

    EMPLOYMENT_STATUS = [
        ('Part-time', 'Part-time'),
        ('Full-time', 'Full-time'),
        ('Student', 'Student'),
        ('Self-employed', 'Self-employed')
    ]

    EDUCATION = [
        ('Secondary', 'Secondary'),
        ('Diploma', 'Diploma'),
        ('Bachelor', 'Bachelor'),
        ('Master', 'Master'),
        ('Doctorate', 'Doctorate')
    ]


    id = models.AutoField(primary_key=True)
    first_name = models.CharField(max_length = 255, blank = True, null = True)
    last_name = models.CharField(max_length = 255, blank = True, null = True)
    phone = models.CharField(max_length=20, blank=True, null = True)
    email = models.CharField(max_length=50, blank=True, null = True)
    address = models.TextField(blank=True, null = True)
    postal_code = models.CharField(max_length=50, blank=True, null = True)
    age = models.IntegerField()
    gender = models.CharField(max_length=50, choices = GENDER)
    employment_status = models.CharField(max_length=50, choices = EMPLOYMENT_STATUS)
    occupation = models.CharField(max_length = 50)
    education = models.CharField(max_length=50, choices = EDUCATION)
    household_size = models.IntegerField()
    has_children = models.IntegerField()
    monthly_income = models.FloatField()
    preferred_category = models.CharField(max_length=50)
    
PRODUCT_CATEGORY = [
    ('Automotive', 'Automotive'),
    ('Beauty & Personal Care', 'Beauty & Personal Care'),
    ('Books', 'Books'),
    ('Electronics', 'Electronics'),
    ('Fashion - Men', 'Fashion - Men'),
    ('Fashion - Women', 'Fashion - Women'),
    ('Groceries & Gourmet', 'Groceries & Gourmet'),
    ('Health', 'Health'),
    ('Home & Kitchen', 'Home & Kitchen'),
    ('Pet Supplies', 'Pet Supplies'),
    ('Sports & Outdoors', 'Sports & Outdoors'),
    ('Toys & Games', 'Toys & Games'),
]

class Product(models.Model):
    sku = models.CharField(max_length=50, primary_key=True)
    product_name = models.CharField(max_length=255)
    product_description = models.TextField()
    product_category = models.CharField(max_length=50, choices = PRODUCT_CATEGORY)
    quantity_on_hand = models.IntegerField()
    reorder_quantity = models.IntegerField()
    unit_price = models.FloatField()
    product_rating = models.FloatField()

    product_subcategory = models.ForeignKey('Subcategory', on_delete=models.RESTRICT, related_name='products')

class Category(models.Model):
    category_id = models.AutoField(primary_key=True)
    category_name = models.CharField(max_length=50, choices = PRODUCT_CATEGORY)

class SubCategory(models.Model):
    subcategory_id = models.AutoField(primary_key=True)
    subcategory_name = models.CharField(max_length=50)

    category = models.ForeignKey(Category, on_delete=models.RESTRICT, related_name = 'category_subcategory')

class Cart(models.Model):
    cart_id = models.AutoField(primary_key=True)

    cart_customer = models.ForeignKey(Customer, on_delete=models.RESTRICT, default="x", related_name = 'customer_cart')

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='cart_items')
    quantity = models.IntegerField()

    class Meta:
        unique_together = ('cart', 'product')  

    @property
    def subtotal_price(self):
        return self.quantity * self.product.unit_price

class Employee(models.Model):
    employee_id = models.AutoField(primary_key=True)
    employee_name = models.CharField(max_length=255)
    employee_email = models.CharField(max_length=50)
    employee_phone = models.IntegerField()

class Order(models.Model):

    ORDER_STATUS = [
        ('Order Placed', 'Order Placed'),
        ('Shipped', 'Shipped'),
        ('Delivered', 'Delivered')
    ]

    order_id = models.AutoField(primary_key=True)
    order_status = models.CharField(max_length = 50, choices = ORDER_STATUS)
    order_date = models.DateField()
    order_price = models.FloatField(default=0.0)
    required_date = models.DateField()
    shipped_date = models.DateField(blank=True, null= True)
    shipping_fee = models.FloatField(default=0.0)

    customer = models.ForeignKey(Customer, on_delete=models.RESTRICT, related_name = 'customer_orders')
    
    def update_order_total(self):
        total = sum(item.subtotal for item in self.order_items.all())
        self.order_price = total
        self.save()

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='order_items')
    product = models.ForeignKey(Product, on_delete=models.RESTRICT, related_name='order_items')
    quantity = models.IntegerField()
    unit_price = models.FloatField()

    class Meta:
        unique_together = ('order', 'product')

    @property
    def subtotal(self):
        return self.quantity * self.unit_price

class Payment(models.Model):
    PAYMENT_METHOD = [
        ('Card', 'Card'),
        ('Paynow', 'Paynow'),
        ('Apple Pay', 'Apple Pay'),
    ]
    PAYMENT_STATUS = [
            ('Pending', 'Pending'),
            ('Completed', 'Completed'),
    ]

    payment_id = models.AutoField(primary_key=True)
    payment_date = models.DateField()
    total_price = models.FloatField()
    method = models.CharField(max_length=50, choices = PAYMENT_METHOD)
    status = models.CharField(max_length = 50, choices = PAYMENT_STATUS)
    transaction_ref = models.CharField(max_length=100, unique=True)

    order = models.ForeignKey(Order, on_delete = models.CASCADE, related_name = 'payments')

