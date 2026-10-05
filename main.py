"""Chompy — приложение с пиксельным питомцем, который растёт, когда ты читаешь.

Использует sprites.py для процедурной отрисовки персонажа.
"""
import os
import sys
import json

# --- Windows: фиксируем размер окна 9:16 ---
if sys.platform == 'win32':
    from kivy.config import Config
    Config.set('graphics', 'width', '405')
    Config.set('graphics', 'height', '720')
    Config.set('graphics', 'resizable', False)

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics.texture import Texture
from kivy.metrics import dp
from kivy.properties import NumericProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition
from kivy.utils import platform

import sprites


# ---------- Константы ----------
DATA_FILE = "chompy_pet.json"
MAX_TIER = 4
READS_PER_TIER = 5


# ---------- Виджет питомца ----------
class PetWidget(FloatLayout):
    """Показывает пиксельного питомца Chompy с анимацией."""
    tier = NumericProperty(0)
    anim = StringProperty("idle")
    face = NumericProperty(1)
    scale = NumericProperty(6)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._texture = None
        self._frame_idx = 0
        self._frame_timer = 0.0
        self._anim_clock = None
        self.bind(size=self._redraw, pos=self._redraw,
                  tier=self._on_param_change,
                  anim=self._on_anim_change,
                  face=self._redraw)
        self._start_anim()

    def _on_param_change(self, *args):
        self._redraw()

    def _on_anim_change(self, *args):
        self._frame_idx = 0
        self._frame_timer = 0.0
        self._redraw()

    def _start_anim(self):
        if self._anim_clock:
            self._anim_clock.cancel()
        self._anim_clock = Clock.schedule_interval(self._tick, 1 / 30)

    def _tick(self, dt):
        anim = self.anim
        if anim not in sprites.ANIMS:
            return
        self._frame_timer += dt
        fps = sprites.FPS.get(anim, 6)
        frame_dur = 1.0 / fps
        if self._frame_timer >= frame_dur:
            self._frame_timer -= frame_dur
            self._frame_idx = (self._frame_idx + 1) % sprites.ANIMS[anim]
            self._redraw()

    def _make_texture(self, frame):
        tex = Texture.create(size=(frame.w, frame.h), colorfmt='rgba')
        tex.blit_buffer(frame.rgba, colorfmt='rgba', bufferfmt='ubyte')
        tex.mag_filter = 'nearest'
        tex.min_filter = 'nearest'
        return tex

    def _redraw(self, *args):
        f = sprites.frame(self.tier, self.anim, self._frame_idx, self.face)
        self._texture = self._make_texture(f)

        w = f.w * self.scale
        h = f.h * self.scale
        cx = self.center_x
        base_y = self.y + dp(40)

        self.canvas.clear()
        from kivy.graphics import Rectangle, Color
        with self.canvas:
            Color(1, 1, 1, 1)
            Rectangle(
                texture=self._texture,
                pos=(cx - w / 2, base_y),
                size=(w, h),
            )


# ---------- Экран питомца ----------
class PetScreen(Screen):
    reads = NumericProperty(0)
    tier = NumericProperty(0)
    anim = StringProperty("idle")
    face = NumericProperty(1)
    status = StringProperty("Читай — и Chompy растёт")

    def on_pre_enter(self, *args):
        self.load()

    def load(self):
        app = App.get_running_app()
        self.tier = app.tier
        self.reads = app.reads
        self.update_status()

    def update_status(self):
        if self.tier >= MAX_TIER:
            self.status = "Максимальный уровень! Chompy доволен 🏆"
        else:
            left = READS_PER_TIER - (self.reads % READS_PER_TIER)
            self.status = f"Ещё {left} слов(а) до уровня {self.tier + 1}"

    def on_read(self):
        app = App.get_running_app()
        app.reads += 1
        self.reads = app.reads

        new_tier = min(app.reads // READS_PER_TIER, MAX_TIER)
        if new_tier > app.tier:
            app.tier = new_tier
            self.tier = new_tier
            self.anim = "happy"
            Clock.schedule_once(lambda dt: self._back_to_idle(), 1.5)
        else:
            self.anim = "eat"
            Clock.schedule_once(lambda dt: self._back_to_idle(), 1.0)

        self.face = 1 if self.face == -1 else -1
        app.save()
        self.update_status()

    def _back_to_idle(self):
        self.anim = "idle"

    def toggle_anim(self, name):
        self.anim = name


# ---------- Приложение ----------
class ChompyApp(App):
    tier = NumericProperty(0)
    reads = NumericProperty(0)

    @property
    def data_path(self):
        os.makedirs(self.user_data_dir, exist_ok=True)
        return os.path.join(self.user_data_dir, DATA_FILE)

    def build(self):
        self.title = "Chompy"
        Window.clearcolor = (0.078, 0.071, 0.122, 1)

        self.load()

        sm = ScreenManager(transition=FadeTransition(duration=0.25))
        sm.add_widget(PetScreen(name="pet"))
        self.sm = sm
        return sm

    def load(self):
        if os.path.exists(self.data_path):
            try:
                with open(self.data_path, encoding='utf-8') as f:
                    data = json.load(f)
                self.tier = int(data.get('tier', 0))
                self.reads = int(data.get('reads', 0))
            except Exception:
                pass

    def save(self):
        try:
            with open(self.data_path, 'w', encoding='utf-8') as f:
                json.dump({'tier': self.tier, 'reads': self.reads}, f)
        except Exception:
            pass


if __name__ == '__main__':
    ChompyApp().run()