# Puddle | Django

Learn how to build a simple online market place website using Django.

This repository is a part of a video tutorial I created for FreeCodeCamp

My channel:
[CodeWithStein](https://www.youtube.com/channel/UCfVoYvY8BfTDeF63JQmQJvg/?sub_confirmation=1)

## Author
This repository and video is created by CodeWithStein. Check out my website for more information.

[Code With Stein - Website](https://codewithstein.com)

## Cozy YU — локальный запуск и примечания для разработки

Ниже краткая инструкция, как запустить проект локально в Windows PowerShell после получения изменений (модели `item` были расширены).

1) Установите зависимости и виртуальное окружение (пример):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt  # если есть requirements.txt
pip install django pillow
```

2) Примените миграции (создайте миграции для приложения `item`):

```powershell
python manage.py makemigrations item
python manage.py migrate
```

3) Создайте суперпользователя (для доступа в админку):

```powershell
python manage.py createsuperuser
```

4) Запустите dev-сервер и зайдите на http://127.0.0.1:8000/

```powershell
python manage.py runserver
```

5) Заметки:
- Статические файлы (css/js/images) находятся в `static/cozyyu/`.
- Для корректной работы `ImageField` установите Pillow (`pip install pillow`).
- Если после изменения `item/models.py` вы хотите сгенерировать фиксации миграций вручную, используйте `makemigrations` как указано.

Если хотите, я могу подготовить фиктивные миграции для вас, но рекомендуем запускать `makemigrations` в вашей среде, чтобы избежать проблем с путями окружения.

### Наполнение базы (seed)

Для быстрой генерации большого количества тестовых товаров в проекте добавлена команда управления:

```powershell
python manage.py seed_items --count 300
```

Параметр `--count` задаёт количество создаваемых товаров (по умолчанию 300). Команда создаёт категории, теги (цвета, стили, ценовые группы, возрастные группы) и товары, которые будут использованы в главной странице и для демонстрации рекомендаций.

Команда также пытается привязать изображения к товарам, если вы заранее загрузили фотографии в папку `MEDIA_ROOT/item_images` (например `media/item_images/`). В этом случае изображения будут случайным образом распределены по товарам при сидировании.


