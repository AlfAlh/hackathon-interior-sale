from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.files import File
import os
import random

from item.models import Item


CATEGORY_KEYWORDS = {
    'Диваны и кресла': ['диван', 'кресло', 'кресла', 'кресло'],
    'Ковры и текстиль': ['ковер', 'плед', 'подушка'],
    'Столы и стулья': ['стол', 'стулья', 'стул'],
    'Шкафы и стеллажи': ['шкаф', 'стелаж', 'стеллаж'],
    'Кровати и матрасы': ['кровать', 'матрас'],
    'Освещение': ['лампа', 'светильник', 'торшер', 'люстра'],
    'Декор': ['картина', 'ваза', 'полка', 'декор'],
}


class Command(BaseCommand):
    help = 'Attach images from MEDIA_ROOT to items without images by matching filenames to category keywords.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Do not modify files, only report')

    def handle(self, *args, **options):
        media_root = getattr(settings, 'MEDIA_ROOT', None)
        if not media_root or not os.path.isdir(media_root):
            self.stdout.write(self.style.ERROR('MEDIA_ROOT not found or is not a directory'))
            return

        # collect all image files under media_root
        candidates = []
        for root, dirs, files in os.walk(media_root):
            for f in files:
                if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.svg')):
                    candidates.append(os.path.join(root, f))

        if not candidates:
            self.stdout.write(self.style.WARNING('No image files found under MEDIA_ROOT'))

        items = Item.objects.filter(image='') | Item.objects.filter(image__isnull=True)
        items = items.distinct()
        attached = 0
        for item in items:
            # try to find by category keywords
            chosen = None
            keywords = CATEGORY_KEYWORDS.get(item.category.name, []) if item.category else []
            if keywords:
                lower_candidates = [p for p in candidates if any(kw in os.path.basename(p).lower() for kw in keywords)]
                if lower_candidates:
                    chosen = random.choice(lower_candidates)

            if not chosen and candidates:
                chosen = random.choice(candidates)

            if chosen:
                self.stdout.write(f'Attaching {os.path.basename(chosen)} to item {item.id} ({item.name})')
                if not options.get('dry_run'):
                    try:
                        with open(chosen, 'rb') as f:
                            django_f = File(f)
                            fname = f'bulk_{item.id}_' + os.path.basename(chosen)
                            item.image.save(fname, django_f, save=True)
                        attached += 1
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(f'Failed to attach {chosen}: {e}'))

        self.stdout.write(self.style.SUCCESS(f'Done. Attached images to {attached} items.'))
