[app]

# Название приложения (как будет отображаться на телефоне)
title = МЕГАТРОНИК HUD

# Имя пакета (латиницей, без пробелов)
package.name = megatronichud
package.domain = org.megatronik

# Каталог с исходниками и точка входа
source.dir = .
source.main = main.py
# mp3 — обязательно, иначе звук выстрела не попадёт в сборку
source.include_exts = py,png,jpg,jpeg,kv,atlas,mp3

version = 1.0

# kivy обязателен; plyer — запасной вариант для GPS, если прямой доступ
# через pyjnius почему-то не сработает. Сам pyjnius добавлять не нужно —
# python-for-android подключает его автоматически для Android-сборок.
# Версия python3 ЗАКРЕПЛЕНА на 3.11 — без пина p4a подтягивает Python 3.14
# (самая свежая), а под неё ещё плохо работают Android-колёса некоторых
# пакетов (конкретно charset_normalizer из зависимостей plyer/requests
# ломается с ошибкой "not a supported wheel on this platform").
requirements = python3==3.11.9,kivy,plyer

# Ориентация экрана (landscape — подходит для HUD/прицела)
orientation = landscape

# Полноэкранный режим без строки состояния
fullscreen = 1

# Иконка и заставка (опционально, положи файлы рядом и раскомментируй)
# icon.filename = %(source.dir)s/icon.png
# presplash.filename = %(source.dir)s/presplash.png

# ВАЖНО: секции [app:android] в формате buildozer.spec не существует —
# buildozer читает android.* ключи ТОЛЬКО из [app]. Раньше они лежали в
# несуществующей секции [app:android] и тихо игнорировались, из-за чего
# сборка откатывалась на дефолт (в т.ч. на две архитектуры вместо одной).

# Минимальная и целевая версия Android API
android.minapi = 24
android.api = 34
android.ndk = 25b

# Одна архитектура — быстрее и легче собирать
android.archs = arm64-v8a

# Разрешения: камера (фон прицела), геолокация (GPS/сеть для координат)
android.permissions = CAMERA, ACCESS_FINE_LOCATION, ACCESS_COARSE_LOCATION

# Явно указываем, что приложению нужна камера
android.features = android.hardware.camera, android.hardware.camera.autofocus

[buildozer]

log_level = 2
