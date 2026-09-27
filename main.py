import os
import sys
import random
import math
import traceback

os.environ['KIVY_NO_CONFIG'] = '1'
from kivy.config import Config
Config.set('graphics', 'multisamples', '0')

if os.name == 'nt':
    import subprocess
    subprocess.run('taskkill /f /im python.exe /fi "WINDOWTITLE eq МЕГАТРОНИК*"', stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=True)

# --- Базовые модули Kivy. Если их нет вообще — тут действительно нечего делать. ---
try:
    from kivy.app import App
    from kivy.uix.floatlayout import FloatLayout
    from kivy.uix.label import Label
    from kivy.uix.widget import Widget
    from kivy.clock import Clock
    from kivy.graphics import Color, Line, Ellipse, Rectangle, PushMatrix, PopMatrix, Rotate
    from kivy.core.text import Label as CoreLabel
    from kivy.core.window import Window
    from kivy.utils import platform
except ImportError:
    print("ERROR: Install Kivy engine via cmd: pip install kivy")
    sys.exit(1)

# --- Камера — отдельный, максимально изолированный импорт. На некоторых
# сборках (в т.ч. в Pydroid) сам импорт kivy.uix.camera может упасть НЕ
# с ImportError, а с другой ошибкой из-за отсутствующего провайдера камеры.
# Раньше это не перехватывалось и роняло всё приложение целиком. ---
try:
    from kivy.uix.camera import Camera
except Exception as e:
    Camera = None
    print(f"Модуль камеры недоступен на этом устройстве: {e}")

# Если картинка с камеры всё ещё повёрнута — поменяй это значение на 90 или 180
# Переход на портретную ориентацию: коррекция поворота (-90), нужная для
# ландшафтного режима, в портрете скорее всего не требуется — сенсор камеры
# обычно "естественно" смотрит как раз в портретную сторону. Если картинка
# всё же повёрнута — попробуй 90, -90 или 180.
CAMERA_ROTATION_ANGLE = 0

# --- Звук — тоже отдельно и безопасно ---
try:
    from kivy.core.audio import SoundLoader
except Exception as e:
    SoundLoader = None
    print(f"Звуковой модуль недоступен: {e}")

# --- Компас и гироскоп — напрямую через SensorManager Android (pyjnius).
# plyer.compass/plyer.gyroscope оказались ненадёжны (часто просто молчат),
# прямой доступ к Android API работает стабильнее. ---
try:
    from jnius import autoclass, PythonJavaClass, java_method
    ANDROID_SENSORS_AVAILABLE = True
except Exception as e:
    ANDROID_SENSORS_AVAILABLE = False
    print(f"pyjnius недоступен — компас/гироскоп будут в режиме симуляции: {e}")

if ANDROID_SENSORS_AVAILABLE:
    class _SensorListener(PythonJavaClass):
        __javainterfaces__ = ['android/hardware/SensorEventListener']
        __javacontext__ = 'app'

        def __init__(self, callback):
            super(_SensorListener, self).__init__()
            self.callback = callback

        @java_method('(Landroid/hardware/SensorEvent;)V')
        def onSensorChanged(self, event):
            try:
                values = event.values
                sensor_type = event.sensor.getType()
                self.callback(sensor_type, [values[0], values[1], values[2]])
            except Exception as e:
                print(f"Ошибка обработки данных датчика: {e}")

        @java_method('(Landroid/hardware/Sensor;I)V')
        def onAccuracyChanged(self, sensor, accuracy):
            pass

    class _LocationListener(PythonJavaClass):
        __javainterfaces__ = ['android/location/LocationListener']
        __javacontext__ = 'app'

        def __init__(self, callback):
            super(_LocationListener, self).__init__()
            self.callback = callback

        @java_method('(Landroid/location/Location;)V')
        def onLocationChanged(self, location):
            try:
                self.callback(location.getLatitude(), location.getLongitude())
            except Exception as e:
                print(f"Ошибка обработки координат: {e}")

        @java_method('(Ljava/lang/String;)V')
        def onProviderEnabled(self, provider):
            pass

        @java_method('(Ljava/lang/String;)V')
        def onProviderDisabled(self, provider):
            pass

        @java_method('(Ljava/lang/String;ILandroid/os/Bundle;)V')
        def onStatusChanged(self, provider, status, extras):
            pass

# --- GPS — через plyer (эта часть работала нормально) ---
try:
    from plyer import gps as plyer_gps
except Exception as e:
    plyer_gps = None
    print(f"plyer.gps недоступен: {e}")

# --- Запрос runtime-разрешений — работает ТОЛЬКО внутри собранного
# Android-приложения (buildozer/python-for-android). В Pydroid 3 этого
# модуля нет и не будет — это нормально, ниже есть отдельная ветка для этого. ---
try:
    from android.permissions import request_permissions, Permission
except Exception as e:
    request_permissions = None
    Permission = None

Window.clearcolor = (0.30, 0.30, 0.30, 1)


class ThumbButton(Widget):
    """Круглая кнопка под большой палец: своя отрисовка на canvas + touch-обработка."""

    def __init__(self, text, color, on_press, **kwargs):
        super(ThumbButton, self).__init__(**kwargs)
        self.callback = on_press
        self.base_color = color
        self.size_hint = (None, None)
        self.size = (230, 230)

        self._label = CoreLabel(text=text, font_size=50, bold=True, color=(1, 1, 1, 1))
        self._label.refresh()

        with self.canvas:
            self._color_inst = Color(*self.base_color)
            self._circle_inst = Ellipse(pos=self.pos, size=self.size)
            Color(1, 1, 1, 1)
            self._label_inst = Rectangle(texture=self._label.texture,
                                          pos=self._label_pos(), size=self._label.texture.size)

        self.bind(pos=self._redraw, size=self._redraw)

    def _label_pos(self):
        tex = self._label.texture
        return (self.center_x - tex.width / 2, self.center_y - tex.height / 2)

    def _redraw(self, *args):
        self._circle_inst.pos = self.pos
        self._circle_inst.size = self.size
        self._label_inst.pos = self._label_pos()

    def set_text(self, text):
        self._label = CoreLabel(text=text, font_size=50, bold=True, color=(1, 1, 1, 1))
        self._label.refresh()
        self._label_inst.texture = self._label.texture
        self._label_inst.size = self._label.texture.size
        self._label_inst.pos = self._label_pos()

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            touch.grab(self)
            r, g, b, a = self.base_color
            self._color_inst.rgba = (min(r + 0.25, 1), min(g + 0.25, 1), min(b + 0.25, 1), a)
            return True
        return super(ThumbButton, self).on_touch_down(touch)

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            self._color_inst.rgba = self.base_color
            if self.collide_point(*touch.pos):
                try:
                    self.callback()
                except Exception as e:
                    print(f"Ошибка в обработчике кнопки: {e}")
            return True
        return super(ThumbButton, self).on_touch_up(touch)


class ApocalypseReticleLayout(FloatLayout):
    def __init__(self, **kwargs):
        super(ApocalypseReticleLayout, self).__init__(**kwargs)

        # --- Данные датчиков ---
        self.sim_humidity = 64.15
        self.horizon_angle = 0.0
        self.target_dist = 450

        self.compass_heading = 124.5
        self._compass_live = False
        self._gyro_live = False

        self.gps_lat = None
        self.gps_lon = None

        self.target_degrees = [0, 90, 180, 270, 355]
        self.compass_map = {0: 'N', 90: 'E', 180: 'S', 270: 'W'}

        # --- Зум x1 / x2 / x3 ---
        self._zoom_levels = [1, 2, 3]
        self._zoom_index = 0
        self.zoom_level = self._zoom_levels[self._zoom_index]

        # --- Отдача при выстреле ---
        self._recoil_x = 0.0
        self._recoil_y = 0.0

        # --- Звук выстрела ---
        self.shot_sound = None
        if SoundLoader is not None:
            try:
                self.shot_sound = SoundLoader.load('bum.mp3')
                if self.shot_sound is None:
                    print("Файл bum.mp3 не найден рядом со скриптом")
            except Exception as e:
                print(f"Не удалось загрузить звук выстрела: {e}")

        # --- Текстуры цифр лимба ---
        self.deg_textures = {}
        for deg in self.target_degrees:
            cl = CoreLabel(text=str(deg), font_size=25, bold=True, color=(0, 1, 0, 15))
            cl.refresh()
            self.deg_textures[deg] = cl.texture

        # --- Текстуры букв компаса ---
        self.comp_textures = {}
        for ang, letter in self.compass_map.items():
            cl = CoreLabel(text=letter, font_size=40, bold=True, color=(0, 1, 0, 0.95))
            cl.refresh()
            self.comp_textures[ang] = cl.texture

        # --- Живой фон с камеры (создаётся позже, в start_sensors) ---
        self.camera_widget = None
        self._camera_error = None
        self._camera_retry_done = False

        # --- Отдельный слой для графики прицела. Раньше рисовалось в
        # self.canvas.after, а canvas.after ВСЕГДА рисуется поверх всех
        # дочерних виджетов — из-за этого прицел перекрывал кнопки. Теперь
        # рисуем на canvas обычного виджета, который лежит НИЖЕ кнопок
        # в порядке добавления (кнопки добавляются позже — значит, они сверху). ---
        self.hud_widget = Widget(size_hint=(1, 1))
        self.add_widget(self.hud_widget)

        # --- Телеметрия ---
        self.telemetry_label = Label(
            text="BOOTING VECTOR HUD ENGINE...",
            font_size='13sp',
            markup=True,
            size_hint=(None, None),
            size=(300, 150),
            pos=(20, 430),
            halign='left',
            valign='middle'
        )
        self.add_widget(self.telemetry_label)

        # --- Кнопка выстрела и кнопка зума ---
        self.fire_button = ThumbButton(text="FIRE", color=(0.82, 0.05, 0.05, 0.95), on_press=self.fire)
        self.add_widget(self.fire_button)

        self.zoom_button = ThumbButton(text="1x", color=(0.05, 0.3, 0.05, 0.85), on_press=self._cycle_zoom)
        self.add_widget(self.zoom_button)

        self.bind(size=self._reposition_controls, pos=self._reposition_controls)
        self._reposition_controls()

        # Компас и гироскоп не требуют диалога разрешений — включаем сразу
        try:
            self._init_android_sensors()
        except Exception as e:
            print(f"Ошибка инициализации датчиков Android: {e}")

        Clock.schedule_interval(self.update_tactical_frame, 1.0 / 30.0)

    # ------------------------------------------------------------------
    # Кнопки: позиционирование, выстрел, зум
    # ------------------------------------------------------------------
    def _reposition_controls(self, *args):
        if self.width <= 0 or self.height <= 0:
            return
        self.fire_button.pos = (self.width - self.fire_button.width - 420, 680)
        self.zoom_button.pos = (self.width - self.zoom_button.width - 20, self.fire_button.top + 0)

    def fire(self):
        try:
            if self.shot_sound is not None:
                self.shot_sound.stop()
                self.shot_sound.play()
        except Exception as e:
            print(f"Ошибка воспроизведения звука выстрела: {e}")
        # Резкий толчок вверх + небольшой случайный увод в сторону, дальше гасится в update_tactical_frame
        self._recoil_y = 20.0
        self._recoil_x = random.uniform(-8, 8)

    def _cycle_zoom(self):
        self._zoom_index = (self._zoom_index + 1) % len(self._zoom_levels)
        self.zoom_level = self._zoom_levels[self._zoom_index]
        self.zoom_button.set_text(f"{self.zoom_level}x")
        print(f"Зум переключён на {self.zoom_level}x")

    def _apply_zoom(self):
        if self.camera_widget is None:
            return
        factor = self.zoom_level
        # При повороте на 90°/270° прямоугольник камеры визуально "переворачивается" —
        # чтобы после поворота он снова точно закрывал весь экран, задаём ему
        # заранее размеры со свапнутыми шириной/высотой.
        rotated_90 = abs(CAMERA_ROTATION_ANGLE) % 180 == 90
        base_w, base_h = (self.height, self.width) if rotated_90 else (self.width, self.height)
        new_w, new_h = base_w * factor, base_h * factor
        self.camera_widget.size = (new_w, new_h)
        self.camera_widget.pos = (self.center_x - new_w / 2, self.center_y - new_h / 2)
        if hasattr(self, '_camera_rotate_inst'):
            self._camera_rotate_inst.origin = self.camera_widget.center

    # ------------------------------------------------------------------
    # Запуск камеры и GPS (после разрешений на Android; сразу — везде ещё)
    # ------------------------------------------------------------------
    def start_sensors(self):
        try:
            self._start_camera()
        except Exception as e:
            print(f"Ошибка запуска камеры: {e}")
        try:
            self._init_gps()
        except Exception as e:
            print(f"Ошибка запуска GPS: {e}")

    def _start_camera(self):
        if Camera is None or self.camera_widget is not None:
            return
        self._camera_error = None
        try:
            self.camera_widget = Camera(play=True, resolution=(1080, 1920), size_hint=(None, None))
            # ВАЖНО: у Camera/Image по умолчанию allow_stretch=False — картинка рисуется
            # в своём "естественном" размере текстуры и НЕ реагирует на camera_widget.size.
            # Именно из-за этого зум не работал. allow_stretch=True заставляет текстуру
            # реально масштабироваться под размер виджета, keep_ratio=False — заполнять
            # его целиком (без чёрных полос), а не вписываться с сохранением пропорций.
            self.camera_widget.allow_stretch = True
            self.camera_widget.keep_ratio = False
            with self.camera_widget.canvas.before:
                PushMatrix()
                self._camera_rotate_inst = Rotate(angle=CAMERA_ROTATION_ANGLE, origin=self.camera_widget.center)
            with self.camera_widget.canvas.after:
                PopMatrix()
            self.add_widget(self.camera_widget, index=len(self.children))
            self._apply_zoom()
        except Exception as e:
            self._camera_error = str(e)
            print(f"Камера недоступна ({e}), будет чёрный фон")
            self.camera_widget = None
            # Повторная попытка через 2 секунды — на случай, если разрешение
            # обрабатывается системой чуть дольше, чем успевает первая попытка
            if not getattr(self, '_camera_retry_done', False):
                self._camera_retry_done = True
                Clock.schedule_once(lambda dt: self._start_camera(), 2.0)
            self.camera_widget = None

    # ------------------------------------------------------------------
    # Датчики
    # ------------------------------------------------------------------
    def _init_compass(self):
        # Заменено на _init_android_sensors() — оставлено как заглушка для совместимости
        pass

    def _read_compass(self):
        if self._compass_live and hasattr(self, '_last_compass_heading'):
            return self._last_compass_heading
        return (self.compass_heading + random.uniform(-0.3, 0.4)) % 360

    def _init_gyroscope(self):
        # Заменено на _init_android_sensors() — оставлено как заглушка для совместимости
        pass

    def _read_horizon_delta(self, dt):
        if self._gyro_live and hasattr(self, '_last_gyro_z'):
            return math.degrees(self._last_gyro_z * dt)
        return random.uniform(-0.5, 0.5)

    def _init_android_sensors(self):
        """Компас и гироскоп напрямую через Android SensorManager (pyjnius) —
        надёжнее, чем plyer.compass/plyer.gyroscope, которые часто просто молчат."""
        if not ANDROID_SENSORS_AVAILABLE or platform != 'android':
            return
        try:
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            AndroidContext = autoclass('android.content.Context')
            SensorManagerCls = autoclass('android.hardware.SensorManager')
            Sensor = autoclass('android.hardware.Sensor')

            activity = PythonActivity.mActivity
            service = activity.getSystemService(AndroidContext.SENSOR_SERVICE)
            sensor_manager = SensorManagerCls.cast(service) if hasattr(SensorManagerCls, 'cast') else service

            self._type_orientation = Sensor.TYPE_ORIENTATION
            self._type_gyroscope = Sensor.TYPE_GYROSCOPE

            orientation_sensor = sensor_manager.getDefaultSensor(Sensor.TYPE_ORIENTATION)
            gyroscope_sensor = sensor_manager.getDefaultSensor(Sensor.TYPE_GYROSCOPE)

            self._sensor_listener = _SensorListener(self._on_android_sensor)

            if orientation_sensor is not None:
                sensor_manager.registerListener(self._sensor_listener, orientation_sensor, SensorManagerCls.SENSOR_DELAY_GAME)
                self._compass_live = True
            else:
                print("Датчик компаса (TYPE_ORIENTATION) не найден на этом устройстве")

            if gyroscope_sensor is not None:
                sensor_manager.registerListener(self._sensor_listener, gyroscope_sensor, SensorManagerCls.SENSOR_DELAY_GAME)
                self._gyro_live = True
            else:
                print("Гироскоп не найден на этом устройстве")

            self._android_sensor_manager = sensor_manager
        except Exception as e:
            print(f"Не удалось подключить датчики Android напрямую: {e}")

    def _on_android_sensor(self, sensor_type, values):
        if sensor_type == getattr(self, '_type_orientation', 3):
            self._last_compass_heading = values[0] % 360
            self._last_roll = values[2] % 360
        elif sensor_type == getattr(self, '_type_gyroscope', 4):
            self._last_gyro_z = values[2]

    def _init_gps(self):
        # Прямой доступ к LocationManager Android — надёжнее, чем plyer.gps
        # (та же история, что была с компасом/гироскопом). Плюс: используем
        # не только GPS-провайдер (спутники — долго ловит, не работает в
        # помещении), но и сетевой (по Wi-Fi/вышкам — быстрее и работает внутри).
        if ANDROID_SENSORS_AVAILABLE and platform == 'android':
            try:
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                AndroidContext = autoclass('android.content.Context')
                LocationManagerCls = autoclass('android.location.LocationManager')

                activity = PythonActivity.mActivity
                service = activity.getSystemService(AndroidContext.LOCATION_SERVICE)
                location_manager = LocationManagerCls.cast(service) if hasattr(LocationManagerCls, 'cast') else service

                self._location_listener = _LocationListener(self._on_android_location)

                providers_started = []
                for provider in (LocationManagerCls.GPS_PROVIDER, LocationManagerCls.NETWORK_PROVIDER):
                    try:
                        if location_manager.isProviderEnabled(provider):
                            location_manager.requestLocationUpdates(provider, 1000, 1.0, self._location_listener)
                            providers_started.append(provider)
                            last_known = location_manager.getLastKnownLocation(provider)
                            if last_known is not None:
                                self._on_android_location(last_known.getLatitude(), last_known.getLongitude())
                        else:
                            print(f"Провайдер геолокации {provider} выключен в настройках телефона")
                    except Exception as e:
                        print(f"Провайдер {provider} недоступен: {e}")

                if not providers_started:
                    print("Ни GPS, ни сетевая геолокация не включены на устройстве")

                self._android_location_manager = location_manager
                return
            except Exception as e:
                print(f"Не удалось подключить геолокацию напрямую: {e}")

        # Запасной вариант (не на Android или pyjnius недоступен)
        if plyer_gps is None:
            return
        try:
            plyer_gps.configure(on_location=self._on_gps_location)
            plyer_gps.start(minTime=1000, minDistance=1)
        except Exception as e:
            print(f"GPS недоступен: {e}")

    def _on_android_location(self, lat, lon):
        self.gps_lat = lat
        self.gps_lon = lon

    def _on_gps_location(self, **kwargs):
        self.gps_lat = kwargs.get('lat')
        self.gps_lon = kwargs.get('lon')

    @staticmethod
    def _format_coord(value, is_lat):
        if value is None:
            return "NO FIX"
        hemi = ('N' if value >= 0 else 'S') if is_lat else ('E' if value >= 0 else 'W')
        value = abs(value)
        deg = int(value)
        minutes_full = (value - deg) * 60
        minutes = int(minutes_full)
        seconds = (minutes_full - minutes) * 60
        return f"{deg}° {minutes}' {seconds:.0f}'' {hemi}"

    # ------------------------------------------------------------------
    # Отрисовка кадра
    # ------------------------------------------------------------------
    def update_tactical_frame(self, dt):
        self.hud_widget.canvas.clear()

        # Крен (наклон влево-вправо) — берём напрямую с датчика ориентации,
        # если он доступен: это абсолютное значение, а не накопленная дельта,
        # поэтому корректно отражает статичный наклон телефона, а не только его движение
        if self._compass_live and hasattr(self, '_last_roll'):
            self.horizon_angle = self._last_roll
        else:
            self.horizon_angle += self._read_horizon_delta(dt)
            self.horizon_angle %= 360
        self.sim_humidity += random.uniform(-0.01, 0.01)
        self.compass_heading = self._read_compass()

        # Гашение отдачи
        self._recoil_x *= 0.80
        self._recoil_y *= 0.80
        if abs(self._recoil_x) < 0.3:
            self._recoil_x = 0.0
        if abs(self._recoil_y) < 0.3:
            self._recoil_y = 0.0

        self._apply_zoom()

        air_factor = 1.0 - (self.sim_humidity / 1500.0)
        bullet_drop = (9.81 * (self.target_dist / 600.0) ** 2 * 40) * air_factor

        self.telemetry_label.text = (
            f".\n"
            f" \n"
            f"\n"
            f"                                     \n"
            f"                       ELEVATION: {bullet_drop:.2f} MOA\n"
            f"                       AZIMUTH: {self.compass_heading:.1f}°\n"
            f"                       BARO HUMID: {self.sim_humidity:.2f}%\n"
            f"                       RANGEFINDER: {self.target_dist}M"
        )

        cx = self.width / 2 + self._recoil_x
        cy = self.height / 1.37 + self._recoil_y
        radius = min(self.width, self.height) * 0.43

        with self.hud_widget.canvas:
            self._draw_soft_vignette(cx, cy, radius)
            self._draw_phosphor_noise(cx, cy, radius)
            self._draw_scope_body(cx, cy, radius)
            self._draw_crosshair(cx, cy, radius)
            self._draw_mil_dots(cx, cy, radius)
            self._draw_corner_brackets(cx, cy)
            self._draw_moving_limb(cx, cy, radius)
            self._draw_static_rim(cx, cy, radius)
            self._draw_compass_ribbon(cx, cy)
            self._draw_readouts(cx, cy, radius)

    def _draw_soft_vignette(self, cx, cy, radius):
        # Серый "размытый" фон вокруг прицела — растянут до самого дальнего
        # угла экрана (считается динамически, т.к. центр прицела может не
        # совпадать с центром экрана), а не только тонкой полосой у края круга.
        max_dist = max(
            math.hypot(cx - 0, cy - 0),
            math.hypot(self.width - cx, cy - 0),
            math.hypot(cx - 0, self.height - cy),
            math.hypot(self.width - cx, self.height - cy),
        )
        band = max(max_dist - radius + 20, 100)
        ring_count = 5
        gray = (0.10, 0.30, 0.30)
        fade_portion = 0.35  # первые ~35% ширины полосы — плавный переход ("размытие")
        for i in range(ring_count):
            t = i / (ring_count - 1)
            r = radius + 4 + t * band
            alpha = min(1.0, t / fade_portion) if t < fade_portion else 1.0
            Color(gray[0], gray[1], gray[2], alpha)
            Line(circle=(cx, cy, r), width=band / ring_count + 3)
        Color(0, 0, 0, 1)
        Line(circle=(cx, cy, radius + 3), width=8)

    def _draw_phosphor_noise(self, cx, cy, radius):
        Color(0, 1, 0, 0.05)
        for _ in range(15):
            rx = random.randint(int(cx - radius), int(cx + radius))
            ry = random.randint(int(cy - radius), int(cy + radius))
            Ellipse(pos=(rx, ry), size=(random.randint(2, 4), random.randint(2, 4)))
        Color(0, 0.35, 0, 0.40)
        Ellipse(pos=(cx - radius, cy - radius), size=(radius * 2, radius * 2))

    def _draw_scope_body(self, cx, cy, radius):
        Color(0, 0, 0, 1)
        Line(circle=(cx, cy, radius + 2), width=40)
        Color(0.5, 1, 0.5, 0.5)
        Line(circle=(cx, cy, radius - 4), width=6, angle_start=100, angle_end=160)
        Color(0.3, 0.7, 0.3, 0.3)
        Line(circle=(cx, cy, radius - 4), width=4, angle_start=200, angle_end=240)

    def _draw_crosshair(self, cx, cy, radius):
        Color(0, 1, 0, 0.9)
        # Шеврон вершиной ВВЕРХ (острый угол смотрит вверх — исправлено)
        Line(points=[cx - 12, cy, cx, cy + 10, cx + 12, cy], width=3)
        Line(points=[cx - radius, cy, cx - 20, cy], width=3)
        Line(points=[cx + 20, cy, cx + radius, cy], width=3)
        Line(points=[cx, cy - radius, cx, cy - 25], width=3)
        Line(points=[cx, cy + 25, cx, cy + radius], width=3)
        Line(circle=(cx, cy, radius * 0.4), width=2)

    def _draw_mil_dots(self, cx, cy, radius):
        Color(0, 1, 0, 0.9)
        for m in range(1, 8):
            offset = m * 24
            if offset < radius - 20:
                Ellipse(pos=(cx - offset - 5, cy - 5), size=(12, 12))
                Ellipse(pos=(cx + offset - 5, cy - 5), size=(12, 12))
                Ellipse(pos=(cx - 5, cy - offset - 5), size=(12, 12))
                Ellipse(pos=(cx - 5, cy + offset - 5), size=(12, 12))

    def _draw_corner_brackets(self, cx, cy):
        Color(0, 1, 0, 0.9)
        Line(points=[cx - 40, cy + 20, cx - 20, cy + 20, cx - 20, cy + 40], width=1.5)
        Line(points=[cx + 40, cy + 20, cx + 20, cy + 20, cx + 20, cy + 40], width=1.5)
        Line(points=[cx - 40, cy - 20, cx - 20, cy - 20, cx - 20, cy - 40], width=1.5)
        Line(points=[cx + 40, cy - 20, cx + 20, cy - 20, cx + 20, cy - 40], width=1.5)

    def _draw_moving_limb(self, cx, cy, radius):
        scale_radius = radius * 0.86
        Color(0, 5, 0, 0.90)
        Line(circle=(cx, cy, scale_radius), width=4)

        Color(0, 1, 0, 20)
        for degree in range(0, 360, 10):
            total_angle = degree - self.horizon_angle
            rad_angle = math.radians(90 + total_angle)

            is_target = degree in self.target_degrees
            tick_len = 26 if is_target else (28 if degree % 30 == 0 else 13)

            x_start = cx + scale_radius * math.cos(rad_angle)
            y_start = cy + scale_radius * math.sin(rad_angle)
            x_end = cx + (scale_radius - tick_len) * math.cos(rad_angle)
            y_end = cy + (scale_radius - tick_len) * math.sin(rad_angle)

            Line(points=[x_start, y_start, x_end, y_end], width=5 if is_target else 3)

            if is_target and degree in self.deg_textures:
                tex = self.deg_textures[degree]
                t_radius = scale_radius - 60
                tx = cx + t_radius * math.cos(rad_angle) - tex.width / 2
                ty = cy + t_radius * math.sin(rad_angle) - tex.height / 2

                if degree == 355:
                    Color(1, 0.3, 0.3, 0.95)
                else:
                    Color(0, 1, 0, 0.95)

                Rectangle(texture=tex, pos=(tx, ty), size=tex.size)
                Color(0, 1, 0, 0.7)

    def _draw_static_rim(self, cx, cy, radius):
        outer_scale_radius = radius * 0.92
        Color(0, 1, 0, 10)
        Line(circle=(cx, cy, outer_scale_radius), width=4)
        for o_deg in range(0, 360, 30):
            rad_o = math.radians(90 + o_deg)
            ox_start = cx + outer_scale_radius * math.cos(rad_o)
            oy_start = cy + outer_scale_radius * math.sin(rad_o)
            ox_end = cx + (outer_scale_radius + 20) * math.cos(rad_o)
            oy_end = cy + (outer_scale_radius + 20) * math.sin(rad_o)
            Line(points=[ox_start, oy_start, ox_end, oy_end], width=3)

        Color(1, 1, 0, 20)
        Line(points=[cx, cy + outer_scale_radius * 0.89 + 12, cx, cy + outer_scale_radius * 0.89 + 2], width=2.5)

    def _draw_compass_ribbon(self, cx, cy):
        compass_y = 1300
        Color(0, 1, 0, 9)
        Line(points=[cx - 180, compass_y, cx + 180, compass_y], width=3)
        Color(1, 1, 0, 1)
        Line(points=[cx, compass_y - 5, cx, compass_y + 15], width=2)

        Color(0, 1, 0, 0.8)
        for p_ang, letter in self.compass_map.items():
            diff_ang = p_ang - self.compass_heading
            if diff_ang > 180:
                diff_ang -= 360
            elif diff_ang < -180:
                diff_ang += 360

            p_x = cx + diff_ang * 2.5
            if (cx - 160) < p_x < (cx + 160) and p_ang in self.comp_textures:
                tex_c = self.comp_textures[p_ang]
                Color(0, 1, 0, 0.95)
                Rectangle(texture=tex_c, pos=(p_x - tex_c.width / 2, compass_y + 4), size=tex_c.size)
                Line(points=[p_x, compass_y, p_x, compass_y - 6], width=1.5)

    def _draw_readouts(self, cx, cy, radius):
        zoom_label = CoreLabel(text=f"{self.zoom_level}x  50", font_size=40, bold=True, color=(0, 1, 0, 0.9))
        zoom_label.refresh()
        tex = zoom_label.texture
        Color(0, 1, 0, 0.9)
        Rectangle(texture=tex, pos=(self.width - tex.width - 20, self.height - tex.height - 20), size=tex.size)

        coord_text = f"{self._format_coord(self.gps_lat, True)} - {self._format_coord(self.gps_lon, False)}"
        coord_label = CoreLabel(text=coord_text, font_size=30, bold=True, color=(0, 1, 0, 0.85))
        coord_label.refresh()
        ctex = coord_label.texture
        Color(0, 1, 0, 0.85)
        Rectangle(texture=ctex, pos=(cx - ctex.width / 2, 18), size=ctex.size)

        if self.camera_widget is None and self._camera_error:
            err_text = f"КАМЕРА: {self._camera_error}"
            err_label = CoreLabel(text=err_text, font_size=22, bold=True, color=(1, 0.3, 0.3, 0.95))
            err_label.refresh()
            etex = err_label.texture
            Color(1, 0.3, 0.3, 0.95)
            Rectangle(texture=etex, pos=(self.width / 2 - etex.width / 2, self.height - etex.height - 90), size=etex.size)


class MegatronicARApp(App):
    def build(self):
        self.layout = ApocalypseReticleLayout()
        return self.layout

    def on_start(self):
        try:
            if platform == 'android' and request_permissions is not None and Permission is not None:
                request_permissions(
                    [
                        Permission.CAMERA,
                        Permission.ACCESS_FINE_LOCATION,
                        Permission.ACCESS_COARSE_LOCATION,
                    ],
                    self._on_permissions_result
                )
                return
        except Exception as e:
            print(f"Запрос разрешений не сработал ({e}), продолжаю без него")

        # Pydroid и любые другие случаи без автозапроса разрешений — запускаем
        # сенсоры сразу. В Pydroid 3 доступ к камере/геолокации нужно выдать
        # вручную: Настройки Android -> Приложения -> Pydroid 3 -> Разрешения.
        self.layout.start_sensors()

    def _on_permissions_result(self, permissions, results):
        try:
            if all(results):
                print("Все разрешения выданы — включаю камеру и GPS")
            else:
                print("Часть разрешений не выдана — камера/GPS могут работать не полностью")
        finally:
            self.layout.start_sensors()


if __name__ == '__main__':
    try:
        MegatronicARApp().run()
    except Exception:
        # Чтобы приложение не просто "сбрасывалось" молча, а оставляло след
        crash_text = traceback.format_exc()
        try:
            with open('crash_log.txt', 'w', encoding='utf-8') as f:
                f.write(crash_text)
        except Exception:
            pass
        print("ПРОИЗОШЛА ОШИБКА. Подробности ниже и в файле crash_log.txt рядом со скриптом:")
        print(crash_text)
