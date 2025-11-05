from django.contrib.auth.models import User
from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=255)

    class Meta:
        ordering = ('name',)
        verbose_name_plural = 'Categories'

    def __str__(self):
        return self.name


class Tag(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return self.name


class Item(models.Model):
    SIZE_CHOICES = (
        ('S', 'Small'),
        ('M', 'Medium'),
        ('L', 'Large'),
    )

    STYLE_CHOICES = (
        ('minimal', 'Минимал'),
        ('classic', 'Классик'),
        ('neoclassic', 'Неоклассик'),
        ('aristocrat', 'Аристократ'),
        ('hi-tech', 'Хай-тек'),
        ('modern', 'Модерн'),
        ('rustic', 'Рустик'),
        ('standard', 'Стандарт'),
        ('loft', 'Лофт'),
        ('ethnic', 'Этник'),
    )

    AGE_CHOICES = (
        ('adult', 'Adult'),
        ('kid', 'Kid'),
    )

    category = models.ForeignKey(Category, related_name='items', on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    # price in Tenge
    price_tg = models.FloatField(verbose_name='Price (KZT)', default=0.0)
    image = models.ImageField(upload_to='item_images', blank=True, null=True)
    is_sold = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, related_name='items', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    # additional attributes for filtering and recommendations
    style = models.CharField(max_length=30, choices=STYLE_CHOICES, blank=True, null=True)
    color = models.CharField(max_length=50, blank=True, null=True)
    size_category = models.CharField(max_length=1, choices=SIZE_CHOICES, blank=True, null=True)
    tags = models.ManyToManyField(Tag, related_name='items', blank=True)
    age_group = models.CharField(max_length=10, choices=AGE_CHOICES, blank=True, null=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return self.name
