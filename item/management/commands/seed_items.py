from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.files import File

import random
import os
import glob

from item.models import Category, Tag, Item


COLORS = ['black', 'white', 'blue', 'green', 'red', 'gray', 'beige', 'brown', 'orange', 'yellow']
STYLES = ['minimal', 'classic', 'hi-tech', 'modern', 'loft', 'ethnic']
SIZE_MAP = {'S': 'Small', 'M': 'Medium', 'L': 'Large'}
PRICE_GROUPS = ['cheap', 'medium', 'expensive']
AGE = ['adult', 'kid']

CATEGORIES = [
    ('sofas', 'Диваны и кресла'),
    ('rugs', 'Ковры и текстиль'),
    ('tables', 'Столы и стулья'),
    ('cabinets', 'Шкафы и стеллажи'),
    ('beds', 'Кровати и матрасы'),
    ('lighting', 'Освещение'),
    ('decor', 'Декор'),
]


ADJECTIVES = ['Nordic', 'Cozy', 'Modern', 'Classic', 'Urban', 'Soft', 'Elegant', 'Rustic', 'Compact']
ITEM_NAMES = {
    'sofas': ['Диван', 'Кресло', 'Секция'],
    'rugs': ['Ковер', 'Плед', 'Подушка'],
    'tables': ['Стол', 'Обеденный стол', 'Туалетный стол'],
    'cabinets': ['Шкаф', 'Стеллаж', 'Комод'],
    'beds': ['Кровать', 'Матрас', 'Спальное место'],
    'lighting': ['Люстра', 'Торшер', 'Настольная лампа'],
    'decor': ['Картина', 'Ваза', 'Полка'],
}


def random_price(group):
    if group == 'cheap':
        return random.randint(10000, 50000)
    if group == 'medium':
        return random.randint(50001, 200000)
    return random.randint(200001, 800000)


class Command(BaseCommand):
    help = 'Seed database with many items, categories and tags for Cozy YU (for dev)'

    def add_arguments(self, parser):
        parser.add_argument('--count', type=int, default=300, help='Number of items to create')

    @transaction.atomic
    def handle(self, *args, **options):
        count = options.get('count') or 300
        User = get_user_model()
        user, created = User.objects.get_or_create(username='seeduser')
        if created:
            user.set_password('password')
            user.email = 'seeduser@example.local'
            user.save()

        # Create categories
        category_objs = {}
        for code, title in CATEGORIES:
            obj, _ = Category.objects.get_or_create(name=title)
            category_objs[code] = obj

        # Create tag pool
        tag_objs = {}
        for color in COLORS:
            t, _ = Tag.objects.get_or_create(name=color)
            tag_objs[color] = t
        for style in STYLES:
            t, _ = Tag.objects.get_or_create(name=style)
            tag_objs[style] = t
        for pg in PRICE_GROUPS:
            t, _ = Tag.objects.get_or_create(name=pg)
            tag_objs[pg] = t
        for ag in AGE:
            t, _ = Tag.objects.get_or_create(name=ag)
            tag_objs[ag] = t

        created_items = 0
        self.stdout.write(self.style.NOTICE(f'Starting seeding {count} items...'))
        # prepare media images pool if exists; also map images by category code folder
        media_pool = []
        media_by_cat = {}
        media_dir = getattr(settings, 'MEDIA_ROOT', None)
        if media_dir:
            base_search = os.path.join(media_dir, 'item_images')
            if os.path.isdir(base_search):
                # global pool
                for ext in ('*.jpg', '*.jpeg', '*.png', '*.webp', '*.svg'):
                    media_pool.extend(glob.glob(os.path.join(base_search, ext)))

                # per-category pools: look into base_search/<code>/
                for code, _ in CATEGORIES:
                    cat_dir = os.path.join(base_search, code)
                    media_by_cat[code] = []
                    if os.path.isdir(cat_dir):
                        for ext in ('*.jpg', '*.jpeg', '*.png', '*.webp', '*.svg'):
                            media_by_cat[code].extend(glob.glob(os.path.join(cat_dir, ext)))

                # Also collect any files in subdirectories that match common category names
                # (in case user placed files in named folders different from codes)
                for root, dirs, files in os.walk(base_search):
                    for f in files:
                        if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.svg')):
                            full = os.path.join(root, f)
                            # if root ends with a category code, ensure it's in that pool
                            tail = os.path.basename(root).lower()
                            for code, _ in CATEGORIES:
                                if tail == code and full not in media_by_cat.get(code, []):
                                    media_by_cat.setdefault(code, []).append(full)

        codes = list(category_objs.keys())
        for i in range(count):
            code = random.choice(codes)
            cat = category_objs[code]
            name = f"{random.choice(ADJECTIVES)} {random.choice(ITEM_NAMES.get(code, ['Товар']))}"
            price_group = random.choices(PRICE_GROUPS, weights=(50, 35, 15), k=1)[0]
            price = random_price(price_group)
            style = random.choice(STYLES)
            color = random.choice(COLORS)
            size = random.choice(list(SIZE_MAP.keys()))
            age = random.choice(AGE)

            item = Item.objects.create(
                category=cat,
                name=name,
                description=f"{style} стиль, цвет {color}, размер {SIZE_MAP[size]}.",
                price_tg=price,
                created_by=user,
                style=style,
                color=color,
                size_category=size,
                age_group=age,
            )

            # attach an image: prefer category pool, else global pool
            chosen_img = None
            cat_pool = media_by_cat.get(code) if media_by_cat else None
            if cat_pool:
                if len(cat_pool) > 0:
                    chosen_img = random.choice(cat_pool)
            if not chosen_img and media_pool:
                chosen_img = random.choice(media_pool)

            if chosen_img:
                try:
                    with open(chosen_img, 'rb') as f:
                        django_file = File(f)
                        fname = f'seed_{i}_' + os.path.basename(chosen_img)
                        item.image.save(fname, django_file, save=True)
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'Could not attach image {chosen_img}: {e}'))

            # attach tags: color, style, price_group, age
            item.tags.add(tag_objs[color])
            item.tags.add(tag_objs[style])
            item.tags.add(tag_objs[price_group])
            item.tags.add(tag_objs[age])

            created_items += 1

            if created_items % 50 == 0:
                self.stdout.write(self.style.SUCCESS(f'Created {created_items} items...'))

        self.stdout.write(self.style.SUCCESS(f'Done. Created {created_items} items.'))
