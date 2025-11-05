from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.files import File
import os
import re
from item.models import Category, Tag, Item


# Маппинг русских стилей на английские ключи модели
STYLE_MAPPING = {
    'стандарт': 'standard',
    'неоклассик': 'neoclassic',
    'неоклассика': 'neoclassic',
    'аристократ': 'aristocrat',
    'модерн': 'modern',
    'рустик': 'rustic',
    'классик': 'classic',
    'хай-тек': 'hi-tech',
    'минимал': 'minimal',
    'лофт': 'loft',
    'этник': 'ethnic',
}

# Маппинг типов товаров на категории
CATEGORY_MAPPING = {
    'диван': 'Диваны и кресла',
    'кресло': 'Диваны и кресла',
    'ковер': 'Ковры и текстиль',
    'плед': 'Ковры и текстиль',
    'стол': 'Столы и стулья',
    'стул': 'Столы и стулья',
    'шкаф': 'Шкафы и стеллажи',
    'стеллаж': 'Шкафы и стеллажи',
    'стелаж': 'Шкафы и стеллажи',
    'тумбочка': 'Шкафы и стеллажи',
    'комод': 'Шкафы и стеллажи',
    'кровать': 'Кровати и матрасы',
    'матрас': 'Кровати и матрасы',
    'лампа': 'Освещение',
    'светильник': 'Освещение',
    'торшер': 'Освещение',
}


def parse_filename(filename):
    """
    Парсит имя файла и извлекает тип товара, стиль и цвет.
    Примеры:
    - "кровать1 Стандарт Белый.jpg" -> ('кровать', 'стандарт', 'белый')
    - "диван2 аристократ синий.jpg" -> ('диван', 'аристократ', 'синий')
    - "детям1 тумбочка неоклассик оранжевый.jpg" -> ('тумбочка', 'неоклассик', 'оранжевый')
    """
    # Убираем расширение
    name = os.path.splitext(filename)[0]
    
    # Убираем "детям" в начале если есть
    name = re.sub(r'^детям\d*\s*', '', name, flags=re.IGNORECASE)
    
    # Убираем цифры в начале названия типа товара
    name = re.sub(r'^(\w+?)(\d+)\s+', r'\1 ', name, flags=re.IGNORECASE)
    
    # Разбиваем по пробелам
    parts = [p.strip().lower() for p in name.split() if p.strip()]
    
    if len(parts) < 2:
        return None, None, None
    
    # Первая часть - тип товара
    item_type = parts[0]
    
    # Ищем стиль (второй элемент обычно)
    style = None
    color = None
    
    if len(parts) >= 2:
        if parts[1] in STYLE_MAPPING:
            style = parts[1]
    
    # Последняя часть обычно цвет
    if len(parts) >= 3:
        color = parts[-1]
    elif len(parts) == 2:
        # Если только 2 части, вторая может быть цветом
        if style is None:
            color = parts[1]
    
    return item_type, style, color


class Command(BaseCommand):
    help = 'Загружает товары из файлов в директории media, парсит названия файлов'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Удалить все существующие товары перед загрузкой'
        )

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        user, created = User.objects.get_or_create(username='admin')
        if created:
            user.set_password('admin')
            user.is_staff = True
            user.is_superuser = True
            user.email = 'admin@example.com'
            user.save()
            self.stdout.write(self.style.SUCCESS('Создан пользователь admin/admin'))

        # Очистка если нужно
        if options.get('clear'):
            Item.objects.all().delete()
            self.stdout.write(self.style.WARNING('Удалены все существующие товары'))

        # Получаем директорию media
        media_root = getattr(settings, 'MEDIA_ROOT', None)
        if not media_root or not os.path.isdir(media_root):
            self.stdout.write(self.style.ERROR('MEDIA_ROOT не найдена'))
            return

        # Получаем все изображения
        image_files = []
        for ext in ('*.jpg', '*.jpeg', '*.png', '*.webp'):
            for root, dirs, files in os.walk(media_root):
                for file in files:
                    if file.lower().endswith(tuple(ext[1:].split('|'))):
                        # Пропускаем файлы из item_images (это уже загруженные товары)
                        if 'item_images' not in root:
                            full_path = os.path.join(root, file)
                            image_files.append((file, full_path))

        self.stdout.write(self.style.NOTICE(f'Найдено {len(image_files)} изображений'))

        # Создаем категории заранее
        categories = {}
        for cat_name in set(CATEGORY_MAPPING.values()):
            cat, _ = Category.objects.get_or_create(name=cat_name)
            categories[cat_name] = cat

        created_count = 0
        skipped_count = 0

        for filename, filepath in image_files:
            item_type, style, color = parse_filename(filename)
            
            if not item_type:
                self.stdout.write(self.style.WARNING(f'Не удалось распарсить: {filename}'))
                skipped_count += 1
                continue

            # Определяем категорию
            category_name = CATEGORY_MAPPING.get(item_type)
            if not category_name:
                self.stdout.write(self.style.WARNING(f'Неизвестный тип товара "{item_type}" в файле: {filename}'))
                skipped_count += 1
                continue

            category = categories[category_name]

            # Формируем название товара
            item_name_parts = [item_type.capitalize()]
            if style:
                item_name_parts.append(style.capitalize())
            
            item_name = ' '.join(item_name_parts)

            # Определяем стиль для модели (на английском)
            style_en = STYLE_MAPPING.get(style) if style else None

            # Генерируем случайную цену
            import random
            price = random.randint(50000, 500000)

            # Проверяем, не существует ли уже такой товар
            existing = Item.objects.filter(
                name=item_name,
                category=category,
                color=color
            ).first()

            if existing:
                self.stdout.write(self.style.WARNING(f'Товар уже существует: {item_name} ({color})'))
                skipped_count += 1
                continue

            # Создаем товар
            item = Item.objects.create(
                category=category,
                name=item_name,
                description=f'{item_name} в стиле {style if style else "стандарт"}',
                price_tg=price,
                created_by=user,
                style=style_en,
                color=color,
            )

            # Прикрепляем изображение
            try:
                with open(filepath, 'rb') as f:
                    django_file = File(f)
                    # Используем оригинальное имя файла
                    item.image.save(filename, django_file, save=True)
                
                # Создаем теги
                if style:
                    tag_style, _ = Tag.objects.get_or_create(name=style)
                    item.tags.add(tag_style)
                
                if color:
                    tag_color, _ = Tag.objects.get_or_create(name=color)
                    item.tags.add(tag_color)
                
                # Добавляем тег типа товара
                tag_type, _ = Tag.objects.get_or_create(name=item_type)
                item.tags.add(tag_type)

                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'✓ Создан товар: {item_name} ({color})'))
            
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Ошибка при создании товара {item_name}: {e}'))
                item.delete()
                skipped_count += 1

        self.stdout.write(self.style.SUCCESS(f'\nГотово! Создано товаров: {created_count}, пропущено: {skipped_count}'))
