from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login as auth_login
from django.db.models import Q

from item.models import Item, Category
from django.conf import settings
import os
import re


@login_required
def index(request):
    items = Item.objects.filter(created_by=request.user)

    return render(request, 'dashboard/index.html', {
        'items': items,
    })


def cozy_index(request):
    """Public homepage for Cozy YU. Supports search (?q=) and category (?category=).

    Context: categories, products, recommendations, random_products
    """
    q = request.GET.get('q', '').strip()
    category_id = request.GET.get('category')

    categories = Category.objects.all()
    # build category cards: prefer using MEDIA_ROOT filenames (user-provided images)
    category_cards = []
    media_root = getattr(settings, 'MEDIA_ROOT', None)
    if media_root and os.path.isdir(media_root):
        tokens = {}
        for root, dirs, files in os.walk(media_root):
            for fn in files:
                if not fn.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.svg')):
                    continue
                name = os.path.splitext(fn)[0].lower()
                # normalize: remove digits and punctuation, split on non-letters
                cleaned = re.sub(r'[^\w\s\-а-яё]', ' ', name)
                cleaned = re.sub(r'\d+', '', cleaned)
                parts = re.split(r'[\s_\-]+', cleaned.strip())
                if not parts:
                    continue
                key = parts[0]
                rel = os.path.relpath(os.path.join(root, fn), media_root).replace('\\', '/')
                url = settings.MEDIA_URL + rel
                if key not in tokens:
                    tokens[key] = url
        for k, url in tokens.items():
            # Skip "cozy" and "декор" categories
            if k.lower() in ['cozy', 'декор']:
                continue
            label = k.capitalize()
            category_cards.append({'token': k, 'name': label, 'image_url': url})
    else:
        # fallback to categories from DB with representative images
        for cat in categories:
            rep = cat.items.filter(image__isnull=False).first()
            img_url = rep.image.url if rep and getattr(rep, 'image') else None
            category_cards.append({'token': str(cat.id), 'name': cat.name, 'image_url': img_url})
    # optimize queries: select_related for FK and prefetch tags to avoid N+1
    products_qs = Item.objects.filter(is_sold=False).select_related('category', 'created_by').prefetch_related('tags')
    if q:
        products_qs = products_qs.filter(
            Q(name__icontains=q) | Q(description__icontains=q) | Q(tags__name__icontains=q)
        ).distinct()
    if category_id:
        try:
            products_qs = products_qs.filter(category_id=int(category_id))
        except (ValueError, TypeError):
            pass

    products = products_qs[:18]

    # simple recommendations: use tags/style of first visible product
    recommendations = []
    if products:
        base = products[0]
        tags = base.tags.all()
        if tags.exists():
            recommendations = Item.objects.filter(tags__in=tags, is_sold=False).exclude(id=base.id).distinct()[:6]
        elif base.style:
            recommendations = Item.objects.filter(style=base.style, is_sold=False).exclude(id=base.id)[:6]

    # avoid expensive random ordering on larger datasets; use recent items instead
    random_products = Item.objects.filter(is_sold=False).select_related('category', 'created_by').prefetch_related('tags').order_by('-created_at')[:6]

    return render(request, 'cozyyu/index.html', {
        'categories': categories,
        'category_cards': category_cards,
        'products': products,
        'recommendations': recommendations,
        'random_products': random_products,
    })


def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            email = request.POST.get('email')
            if email:
                user.email = email
                user.save()
            auth_login(request, user)
            return redirect('home')
    else:
        form = UserCreationForm()
    return render(request, 'registration/register.html', {'form': form})
