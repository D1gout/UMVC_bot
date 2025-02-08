# Направления
DIRECTIONS = {
    "press": "Пресса",
    "photo": "Фотографы",
    "video": "Видеографы",
    "coord": "Координаторы",
    "guest": "Я гость"
}

# Модули с ограничениями
MODULES = {
    "interview": ("Интервью и редактура", ["press"]),
    "speech": ("Работа с речью", ["press"]),
    "photo": ("Фото", ["photo"]),
    "promotion": ("Продвижение контента", ["photo", "video"]),
    "video": ("Видео", ["video"]),
    "directing": ("Режиссура", ["video"]),
    "inclusion": ("Инклюзия", ["coord"]),
    "events": ("Организация мероприятий", ["coord"]),
    "tech": ("Техники", []),
    "first_aid": ("Первая Помощь", ["press", "photo", "video", "coord", "guest"]),
    "psych": ("Психология", ["press", "photo", "video", "coord", "guest"])
}

# Обязательные модули
REQUIRED_MODULES = ["Первая Помощь", "Психология"]