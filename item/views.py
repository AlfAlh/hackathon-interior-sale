from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse

from .forms import NewItemForm, EditItemForm
from .models import Category, Item, Tag


# mapping of category code/name to complementary categories (by name)
COMPLEMENTARY = {
    'Диваны и кресла': ['Столы и стулья', 'Ковры и текстиль'],
    'Ковры и текстиль': ['Диваны и кресла', 'Кровати и матрасы'],
    'Столы и стулья': ['Диваны и кресла', 'Освещение'],
    'Шкафы и стеллажи': ['Освещение'],
    'Кровати и матрасы': ['Ковры и текстиль'],
    'Освещение': ['Столы и стулья'],
}

def items(request):
    query = request.GET.get('query', '')
    category_id = request.GET.get('category', 0)
    category_name = request.GET.get('category_name')
    categories = Category.objects.all()
    items = Item.objects.filter(is_sold=False)

    # filter by explicit category id or by category_name token (derived from image filenames or labels)
    if category_id:
        items = items.filter(category_id=category_id)
    if category_name:
        # match by image filename, item name, or tags
        items = items.filter(
            Q(image__icontains=category_name) | Q(name__icontains=category_name) | Q(tags__name__icontains=category_name)
        ).distinct()

    if query:
        # Поиск по названию, описанию, стилю, цвету и тегам
        items = items.filter(
            Q(name__icontains=query) | 
            Q(description__icontains=query) |
            Q(style__icontains=query) |
            Q(color__icontains=query) |
            Q(tags__name__icontains=query) |
            Q(image__icontains=query)
        ).distinct()

    return render(request, 'item/items.html', {
        'items': items,
        'query': query,
        'categories': categories,
        'category_id': int(category_id)
    })

def detail(request, pk):
    item = get_object_or_404(Item, pk=pk)

    # Recommendation algorithm: find complementary items rather than just same-category
    candidates = Item.objects.filter(is_sold=False).exclude(pk=pk).select_related('category')

    # narrow candidates to those that share style or tags or price-group tag or same color
    base_tags = set([t.name for t in item.tags.all()])
    base_style = item.style
    base_color = (item.color or '').lower()
    base_price = item.price_tg or 0

    # helper: color complementarity
    NEUTRALS = {'black', 'white', 'gray', 'beige', 'brown'}
    COMPLEMENTS = {
        'blue': ['orange', 'beige'],
        'orange': ['blue', 'beige'],
        'red': ['green', 'beige'],
        'green': ['red', 'beige'],
        'yellow': ['blue', 'beige'],
        'beige': ['blue', 'orange', 'brown'],
    }

    def color_compat_score(a, b):
        if not a or not b:
            return 0
        a = a.lower(); b = b.lower()
        if a == b:
            return 10
        if a in NEUTRALS or b in NEUTRALS:
            return 6
        if b in COMPLEMENTS.get(a, []):
            return 7
        return 0

    # size compatibility: same size preferred, adjacent size OK
    SIZE_PREF = {
        ('S', 'S'): 8,
        ('M', 'M'): 8,
        ('L', 'L'): 8,
        ('S', 'M'): 4,
        ('M', 'S'): 4,
        ('M', 'L'): 4,
        ('L', 'M'): 4,
    }

    scored = []
    for cand in candidates:
        score = 0
        comp = COMPLEMENTARY.get(item.category.name, []) if item.category else []

        # complementary category bonus
        if item.category and cand.category and cand.category.name in comp:
            score += 40

        # style match
        if base_style and cand.style == base_style:
            score += 20

        # shared tags
        cand_tags = set([t.name for t in cand.tags.all()])
        inter = base_tags.intersection(cand_tags)
        score += len(inter) * 8

        # color compatibility
        score += color_compat_score(base_color, cand.color)

        # size compatibility
        if item.size_category and cand.size_category:
            score += SIZE_PREF.get((item.size_category, cand.size_category), 0)

        # price proximity
        if cand.price_tg and base_price > 0:
            diff = abs(cand.price_tg - base_price)
            if diff < max(1, base_price * 0.1):
                score += 8
            elif diff < max(1, base_price * 0.25):
                score += 4

        # minor boost if different category (but not complementary)
        if item.category and cand.category and cand.category != item.category and cand.category.name not in comp:
            score += 5

        if score > 0:
            scored.append((score, cand))

    scored.sort(key=lambda x: x[0], reverse=True)
    related_items = [c for s, c in scored[:6]]

    return render(request, 'item/detail.html', {
        'item': item,
        'related_items': related_items
    })


def cart_view(request):
    cart = request.session.get('cart', {})
    item_ids = list(cart.keys())
    items = Item.objects.filter(id__in=item_ids)
    total = 0
    cart_items = []
    for it in items:
        qty = cart.get(str(it.id), 0)
        subtotal = (it.price_tg or 0) * qty
        total += subtotal
        cart_items.append({'item': it, 'qty': qty, 'subtotal': subtotal})

    return render(request, 'item/cart.html', {'cart_items': cart_items, 'total': total})


def cart_add(request, pk):
    # add one item to cart and redirect back
    item = get_object_or_404(Item, pk=pk)
    cart = request.session.get('cart', {})
    cart[str(item.id)] = cart.get(str(item.id), 0) + 1
    request.session['cart'] = cart
    return redirect('item:detail', pk=pk)


def cart_remove(request, pk):
    cart = request.session.get('cart', {})
    cart.pop(str(pk), None)
    request.session['cart'] = cart
    return redirect('item:cart')


def cart_update(request, pk):
    qty = int(request.POST.get('qty', 1))
    cart = request.session.get('cart', {})
    if qty <= 0:
        cart.pop(str(pk), None)
    else:
        cart[str(pk)] = qty
    request.session['cart'] = cart
    return redirect('item:cart')

@login_required
def new(request):
    if request.method == 'POST':
        form = NewItemForm(request.POST, request.FILES)

        if form.is_valid():
            item = form.save(commit=False)
            item.created_by = request.user
            item.save()

            return redirect('item:detail', pk=item.id)
    else:
        form = NewItemForm()

    return render(request, 'item/form.html', {
        'form': form,
        'title': 'New item',
    })

@login_required
def edit(request, pk):
    item = get_object_or_404(Item, pk=pk, created_by=request.user)

    if request.method == 'POST':
        form = EditItemForm(request.POST, request.FILES, instance=item)

        if form.is_valid():
            form.save()

            return redirect('item:detail', pk=item.id)
    else:
        form = EditItemForm(instance=item)

    return render(request, 'item/form.html', {
        'form': form,
        'title': 'Edit item',
    })

@login_required
def delete(request, pk):
    item = get_object_or_404(Item, pk=pk, created_by=request.user)
    item.delete()

    return redirect('dashboard:index')


def search_autocomplete(request):
    """
    API endpoint для автодополнения поиска.
    Возвращает список предложений на основе введенного запроса.
    """
    query = request.GET.get('q', '').strip().lower()
    
    if not query or len(query) < 1:
        return JsonResponse({'suggestions': []})
    
    suggestions = []
    seen = set()
    
    # Определённые стили
    STYLES = ['стандарт', 'неоклассик', 'неоклассика', 'аристократ', 'модерн', 'рустик', 'классик']
    
    # 1. Поиск типов товаров (извлекаем первые слова из названий)
    items = Item.objects.all().values_list('name', flat=True).distinct()
    product_types = set()
    for name in items:
        if name:
            first_word = name.split()[0].lower()
            # Очищаем от цифр
            cleaned = ''.join([c for c in first_word if not c.isdigit()]).strip()
            if cleaned:
                product_types.add(cleaned)
    
    # Добавляем типы товаров, начинающиеся с запроса
    for ptype in sorted(product_types):
        if ptype.startswith(query) and ptype not in seen:
            suggestions.append({'text': ptype.capitalize(), 'type': 'товар'})
            seen.add(ptype)
            if len(suggestions) >= 8:
                break
    
    # 2. Поиск по стилям
    if len(suggestions) < 8:
        for style in STYLES:
            if style.lower().startswith(query) and style.lower() not in seen:
                suggestions.append({'text': style.capitalize(), 'type': 'стиль'})
                seen.add(style.lower())
                if len(suggestions) >= 8:
                    break
    
    # 3. Поиск по тегам (цвета и другие характеристики)
    if len(suggestions) < 8:
        tags = Tag.objects.filter(name__istartswith=query).values_list('name', flat=True).distinct()[:10]
        for tag_name in tags:
            tag_lower = tag_name.lower()
            if tag_lower not in seen and tag_lower not in STYLES:
                # Если это не стиль, вероятно цвет или другая характеристика
                suggestions.append({'text': tag_name.capitalize(), 'type': 'цвет'})
                seen.add(tag_lower)
                if len(suggestions) >= 8:
                    break
    
    # 4. Если ничего не найдено, попробуем частичное совпадение
    if len(suggestions) == 0:
        # Частичное совпадение для типов товаров
        for ptype in sorted(product_types):
            if query in ptype and ptype not in seen:
                suggestions.append({'text': ptype.capitalize(), 'type': 'товар'})
                seen.add(ptype)
                if len(suggestions) >= 5:
                    break
        
        # Частичное совпадение для стилей
        if len(suggestions) < 5:
            for style in STYLES:
                if query in style.lower() and style.lower() not in seen:
                    suggestions.append({'text': style.capitalize(), 'type': 'стиль'})
                    seen.add(style.lower())
                    if len(suggestions) >= 5:
                        break
    
    return JsonResponse({'suggestions': suggestions})


def recommendations(request):
    """
    Страница рекомендаций. Пользователь выбирает товар,
    затем алгоритм показывает товары с совпадающим стилем и цветом.
    """
    selected_item_id = request.GET.get('item_id')
    query = request.GET.get('query', '')
    
    # Получаем все доступные товары для выбора
    available_items = Item.objects.filter(is_sold=False)
    
    # Применяем фильтр поиска если есть
    if query:
        available_items = available_items.filter(
            Q(name__icontains=query) | 
            Q(description__icontains=query) |
            Q(style__icontains=query) |
            Q(color__icontains=query) |
            Q(tags__name__icontains=query) |
            Q(image__icontains=query)
        ).distinct()
    
    selected_item = None
    recommended_items = []
    
    # Если товар выбран, показываем рекомендации
    if selected_item_id:
        try:
            selected_item = Item.objects.get(pk=selected_item_id, is_sold=False)
            
            # Извлекаем стиль и цвет из выбранного товара
            # Данные берутся из описания изображений в папке media
            item_style = selected_item.style
            item_color = selected_item.color
            
            # Ищем товары с совпадающим стилем и/или цветом
            if item_style or item_color:
                candidates = Item.objects.filter(is_sold=False).exclude(pk=selected_item.pk)
                
                for item in candidates:
                    score = 0
                    
                    # Проверяем совпадение стиля
                    if item_style and item.style == item_style:
                        score += 10
                    
                    # Проверяем совпадение цвета
                    if item_color and item.color:
                        if item.color.lower() == item_color.lower():
                            score += 10
                    
                    # Добавляем только товары с совпадениями
                    if score > 0:
                        recommended_items.append((score, item))
                
                # Сортируем по убыванию релевантности
                recommended_items.sort(key=lambda x: x[0], reverse=True)
                # Берем топ-12 рекомендаций
                recommended_items = [item for score, item in recommended_items[:12]]
        
        except Item.DoesNotExist:
            pass
    
    return render(request, 'item/recommendations.html', {
        'available_items': available_items[:50],  # Ограничиваем для производительности
        'selected_item': selected_item,
        'recommended_items': recommended_items,
        'query': query,
    })
