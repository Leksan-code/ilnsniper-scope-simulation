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
# ВАЖНО: python3 и hostpython3 обязаны совпадать по версии (p4a требует
# этого явно) — поэтому закрепляем ОБЕ версии одинаково. Без hostpython3
# в списке p4a брал 3.14.2 по умолчанию, а python3 был закреплён на 3.11.9,
# из-за чего сборка падала с "python3 should have same version as hostpython3".
requirements = python3==3.11.9,hostpython3==3.11.9,kivy,plyer

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

# android.features убран: эта версия python-for-android не принимает флаг
# --feature на финальном шаге сборки APK (unrecognized arguments). Это была
# необязательная декларация "устройству нужна камера" — без неё приложение
# всё равно нормально запрашивает и использует камеру в рантайме.

[buildozer]

log_level = 2
