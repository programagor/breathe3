import os
import sys
import json
import math
import time

from kivy.core.audio import SoundLoader
from kivy.core.image import Image as CoreImage
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.widget import Widget
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.uix.textinput import TextInput
from kivy.graphics import Color, Ellipse, Rectangle
from kivy.clock import Clock
from kivy.properties import NumericProperty, ListProperty, BooleanProperty
from kivy.uix.slider import Slider
from kivy.uix.label import Label

ALLOW_INF = False

wake_lock = None

try:
    from jnius import autoclass, JavaException
    PowerManager = autoclass('android.os.PowerManager')
    Context = autoclass('android.content.Context')
    PythonActivity = autoclass('org.kivy.android.PythonActivity')

    activity = PythonActivity.mActivity
    power_manager = activity.getSystemService(Context.POWER_SERVICE)

    wake_lock = power_manager.newWakeLock(PowerManager.SCREEN_BRIGHT_WAKE_LOCK, 'Breathe3:WakelockTag')
except ImportError:
    print("Jnius is not available. Wakelock functionality will be disabled.")
except Exception as e:
    print(f"Exception: {e}")

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def sin_intp(x):
    return (1-math.cos(x*math.pi))/2

def cub_intp(x):
    if x > 1:
        x = 2-x
    return -2*x**3+3*x**2

# ============================================================================
# AnimatedCircle
# ----------------------------------------------------------------------------
# We no longer use a single cycle_time; instead we store separate start
# and end values. In animate_circle() we compute the effective cycle times
# via linear interpolation over the session.
# ============================================================================
class AnimatedCircle(Widget):
    radius_a = 75
    radius_b = 25
    radius_c = 25
    radius_d = 20
    radius_e = 20
    # (Note: the old “cycle_time” property is no longer used.)

    def __init__(self, duration_slider=None, duration_label=None, update_button_label=None, **kwargs):
        super(AnimatedCircle, self).__init__(**kwargs)
        self.framerate = 1/60
        self.duration_slider = duration_slider
        self.duration_label = duration_label
        self.update_button_label = update_button_label
        self.bind(size=self.update_canvas, pos=self.update_canvas)
        self.phase = 0
        self.last_phase = -1
        self.progress = 0
        self.initial_touch_pos = None  # For touch–drag duration adjustment
        self.animation_event = Clock.schedule_interval(self.animate_circle, self.framerate)
        self.animation_event.cancel()  # start paused
        self.sounds = {
            0: SoundLoader.load(resource_path('assets/ding_inhale.wav')),
            1: SoundLoader.load(resource_path('assets/ding_hold1.wav')),
            2: SoundLoader.load(resource_path('assets/ding_exhale.wav')),
            3: SoundLoader.load(resource_path('assets/ding_hold2.wav')),
            4: SoundLoader.load(resource_path('assets/ding_end.wav'))
        }
        self.duration = 5 * 60
        self.selected_duration = 5 * 60
        # Default start and end cycle times (if you want a static cycle, keep them identical)
        self.start_cycle_time = [4, 8, 8, 0]
        self.end_cycle_time = [4, 8, 8, 0]

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.initial_touch_pos = touch.pos
            self.touch_start = touch.pos
            self.touch_start_time = time.time()
            touch.grab(self)
            return True
        return super(AnimatedCircle, self).on_touch_down(touch)

    def on_touch_move(self, touch):
        if touch.grab_current is self:
            self.handle_touch_movement(touch.pos)
            self.initial_touch_pos = touch.pos
            return True
        return super(AnimatedCircle, self).on_touch_move(touch)

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            final_touch_pos = touch.pos
            dx = final_touch_pos[0] - self.touch_start[0]
            dy = final_touch_pos[1] - self.touch_start[1]
            distance_moved = math.sqrt(dx ** 2 + dy ** 2)
            touch_duration = time.time() - self.touch_start_time
            if distance_moved < 10 and touch_duration < 0.5:
                self.handle_tap()
            self.touch_start = None
            return True
        return super(AnimatedCircle, self).on_touch_up(touch)

    def handle_tap(self):
        from kivy.app import App
        app = App.get_running_app()
        main_layout = app.root
        start_stop_button = main_layout.start_stop_button
        main_layout.toggle_animation(start_stop_button)

    def handle_touch_movement(self, touch_pos):
        if self.initial_touch_pos:
            vec_initial = (self.initial_touch_pos[0] - self.center_x, self.initial_touch_pos[1] - self.center_y)
            vec_current = (touch_pos[0] - self.center_x, touch_pos[1] - self.center_y)
            angle_initial = math.atan2(vec_initial[1], vec_initial[0])
            angle_current = math.atan2(vec_current[1], vec_current[0])
            if angle_initial - angle_current < -math.pi:
                angle_current -= 2 * math.pi
            elif angle_initial - angle_current > math.pi:
                angle_current += 2 * math.pi
            angle_change = angle_current - angle_initial
            angle_change_deg = math.degrees(angle_change)
            duration_change = - angle_change_deg / 360 * 4 * 60 
            if ((self.duration == float('inf') or self.duration >= 30*60+1) and duration_change < 0):
                self.duration = 30*60+1 + duration_change
            elif ((self.duration == float('inf') or self.duration >= 30*60+1) and duration_change > 0):
                self.duration = float('inf') if ALLOW_INF else 30*60+1
            else:
                self.duration += duration_change
            self.duration = max(0, self.duration)
            if self.duration >= 30*60+1:
                self.duration = float('inf') if ALLOW_INF else 30*60+1
            if not self.animation_event.is_triggered:
                self.selected_duration = max(0, self.selected_duration + duration_change * 60)
            if self.duration_slider and self.duration_label:
                if self.duration == float('inf') or self.duration >= 30*60+1 and not ALLOW_INF:
                    self.duration = 30*60
                if self.duration == float('inf') or self.duration >= 30*60+1:
                    self.duration_slider.value = 30*60+1
                    self.duration_label.text = f'Time: ∞' if ALLOW_INF else "30"
                else:
                    self.duration_slider.value = self.duration
                    minutes, seconds = divmod(int(self.duration), 60)
                    if minutes:
                        minutes = int((self.duration+30)//60)
                    self.duration_label.text = f'Time: {minutes} minutes' if minutes else f'Time: {seconds} seconds'

    def toggle_animation(self, enable):
        if not enable:
            self.animation_event.cancel()
            self.animation_active = False
        else:
            self.animation_event = Clock.schedule_interval(self.animate_circle, self.framerate)
            self.animation_active = True

    def update_canvas(self, *args):
        self.canvas.clear()
        with self.canvas:
            Color(0.094, 0.004, 0.114, 0.25)
            radius_a = (min(self.width, self.height) / 2) * (self.radius_a / 100.0)
            Ellipse(pos=(self.center_x - radius_a, self.center_y - radius_a), size=(radius_a * 2, radius_a * 2))

            Color(0.95, 0.95, 0.95, 0.75)
            radius_b = (min(self.width, self.height) / 2) * (self.radius_b / 100.0)
            Ellipse(pos=(self.center_x - radius_b, self.center_y - radius_b), size=(radius_b * 2, radius_b * 2))

            Color(0.988, 0.667, 0.992, 1)
            radius_c = (min(self.width, self.height) / 2) * (self.radius_c / 100.0)
            Ellipse(pos=(self.center_x - radius_c, self.center_y - radius_c), size=(radius_c * 2, radius_c * 2))

            Color(0.95, 0.95, 0.95, 1)
            radius_d = (min(self.width, self.height) / 2) * (self.radius_d / 100.0)
            Ellipse(pos=(self.center_x - radius_d, self.center_y - radius_d), size=(radius_d * 2, radius_d * 2))

            Color(0.231, 0.051, 0.286, 1)
            radius_e = (min(self.width, self.height) / 2) * (self.radius_e / 100.0)
            Ellipse(pos=(self.center_x - radius_e, self.center_y - radius_e), size=(radius_e * 2, radius_e * 2))

    def animate_circle(self, dt):
        # Update the duration countdown
        if (self.duration != float('inf') and self.duration < 30*60+1) or not ALLOW_INF:
            self.duration -= dt
            if self.duration_slider and self.duration_label:
                self.duration_slider.value = max(0, min(self.duration, self.duration_slider.max - 1))
                minutes, seconds = divmod(int(self.duration), 60)
                if minutes:
                    minutes = int((self.duration+30)//60)
                self.duration_label.text = f'Time: {minutes} minutes' if minutes else f'Time: {seconds} seconds'
            if self.duration <= 0:
                self.stop_animation_with_end_sound()
                return

        # Compute an interpolation factor from 0 to 1 over the session:
        if self.selected_duration == float('inf') or self.selected_duration <= 0:
            factor = 0
        else:
            factor = (self.selected_duration - self.duration) / self.selected_duration
        # Compute effective cycle times by linearly interpolating between start and end values.
        effective_cycle_time = [
            s + (e - s) * factor for s, e in zip(self.start_cycle_time, self.end_cycle_time)
        ]
        t1, t2, t3, t4 = effective_cycle_time
        self.progress += dt

        if self.phase == 0:
            if t1 > 0:
                self.radius_b = self.radius_c = 75 - 50 * (1 - cub_intp(self.progress / t1))
                self.radius_d = self.radius_e = self.radius_b - 5
            if self.progress > t1:
                self.phase = 1 
                self.progress -= t1
        if self.phase == 1:
            if t2 > 0:
                self.radius_b = 75 + 15 * cub_intp(self.progress / t2 * 2)
                self.radius_c = 75
                self.radius_d = self.radius_e = 75 - 5
            if self.progress > t2:
                self.phase = 2
                self.progress -= t2
        if self.phase == 2:
            if t3 > 0:
                self.radius_b = self.radius_c = 75 - 50 * cub_intp(self.progress / t3)
                self.radius_d = self.radius_e = self.radius_b - 5
            if self.progress > t3:
                self.phase = 3
                self.progress -= t3
        if self.phase == 3:
            if t4 > 0:
                self.radius_b = self.radius_c = 25
                self.radius_d = self.radius_b - 5
                self.radius_e = 20 - 10 * cub_intp(self.progress / t4 * 2)
            if self.progress > t4:
                self.phase = 0
                self.progress -= t4

        if self.phase != self.last_phase:
            sound = self.sounds.get(self.phase)
            if sound:
                sound.play()
            self.last_phase = self.phase

        self.update_canvas()

    def stop_animation_with_end_sound(self):
        self.animation_event.cancel()
        sound = self.sounds.get(4)
        if sound:
            sound.play()

        def release_wake_lock_callback(dt):
            self.animation_active = False
            if wake_lock and wake_lock.isHeld():
                wake_lock.release()
            if self.update_button_label:
                self.update_button_label('Start')
            self.duration = self.selected_duration
            if (self.duration == float('inf') or self.duration >= 30*60+1) and ALLOW_INF:
                self.duration_slider.value = 30*60+1
                self.duration_label.text = f'Time: ∞'
            else:
                self.duration_slider.value = self.selected_duration
                minutes, seconds = divmod(int(self.selected_duration), 60)
                if minutes:
                    minutes = int((self.duration+30)//60)
                self.duration_label.text = f'Time: {minutes} minutes' if minutes else f'Time: {seconds} seconds'
        Clock.schedule_once(release_wake_lock_callback, 2)

# ============================================================================
# EditPresetsPopup
# ----------------------------------------------------------------------------
# Now each preset row lets you edit a name, the duration (in minutes), the
# start cycle times and the end cycle times (each entered as a string such as
# "4-8-8-0").
# ============================================================================
class EditPresetsPopup(Popup):
    def __init__(self, presets, on_save=None, **kwargs):
        super().__init__(**kwargs)
        self.presets = presets
        self.on_save = on_save  # Callback when presets are saved
        self.layout = BoxLayout(orientation='vertical')
        self.scrollable = ScrollView(size_hint=(1, 1), do_scroll_x=False, do_scroll_y=True, bar_width=10)
        self.rows = BoxLayout(orientation='vertical', size_hint=(1, None), height=150 * len(presets))
        self.scrollable.add_widget(self.rows)
        self.layout.add_widget(self.scrollable)
        self.add_row_button = Button(text='Add Row', size_hint_y=None, height=40)
        self.add_row_button.bind(on_press=self.add_row)
        self.layout.add_widget(self.add_row_button)
        self.save_button = Button(text='Save', size_hint_y=None, height=40)
        self.save_button.bind(on_press=self.save_presets)
        self.layout.add_widget(self.save_button)
        self.title = 'Edit Presets'
        self.content = self.layout
        self.size_hint = (0.9, 0.6)
        self.pos_hint = {'top': 1}
        self.populate_initial_rows()

    def populate_initial_rows(self):
        for preset_name, preset_values in self.presets.items():
            self.add_row(preset_name=preset_name, preset_values=preset_values)

    def add_row(self, instance=None, preset_name='New preset', preset_values=([4, 8, 8, 0], [4, 8, 8, 0], 10*60)):
        row = BoxLayout(orientation='vertical', size_hint_y=None, height=150)
        # Row 1: Name and Duration
        row1 = BoxLayout(orientation='horizontal', size_hint_y=None, height=40)
        row1.add_widget(Label(text='Name:', size_hint_x=None, width=100))
        name_input = TextInput(text=preset_name, multiline=False)
        row1.add_widget(name_input)
        row1.add_widget(Label(text='Time (min):', size_hint_x=None, width=100))
        duration_input = TextInput(text=str(int(preset_values[2] // 60)), multiline=False)
        row1.add_widget(duration_input)
        row.add_widget(row1)
        # Row 2: Start Values
        row2 = BoxLayout(orientation='horizontal', size_hint_y=None, height=40)
        row2.add_widget(Label(text='Start Values (Inhale-Hold1-Exhale-Hold2):', size_hint_x=None, width=250))
        start_input = TextInput(text='-'.join(map(str, preset_values[0])), multiline=False)
        row2.add_widget(start_input)
        row.add_widget(row2)
        # Row 3: End Values
        row3 = BoxLayout(orientation='horizontal', size_hint_y=None, height=40)
        row3.add_widget(Label(text='End Values (Inhale-Hold1-Exhale-Hold2):', size_hint_x=None, width=250))
        end_input = TextInput(text='-'.join(map(str, preset_values[1])), multiline=False)
        row3.add_widget(end_input)
        row.add_widget(row3)
        # Row 4: Delete button
        row4 = BoxLayout(orientation='horizontal', size_hint_y=None, height=30)
        delete_button = Button(text='Delete', size_hint_x=None, width=100)
        delete_button.bind(on_press=lambda x: self.delete_row(row))
        row4.add_widget(delete_button)
        row.add_widget(row4)
        # Save references to the text inputs on the row
        row.preset_widgets = {
            'name': name_input,
            'duration': duration_input,
            'start': start_input,
            'end': end_input,
        }
        self.rows.add_widget(row)
        self.rows.height = 150 * len(self.rows.children)

    def delete_row(self, row):
        self.rows.remove_widget(row)
        self.rows.height = 150 * len(self.rows.children)

    def save_presets(self, instance):
        new_presets = {}
        for row in self.rows.children:
            widgets = row.preset_widgets
            preset_name = widgets['name'].text.strip()
            start_values_str = widgets['start'].text.strip()
            end_values_str = widgets['end'].text.strip()
            duration_str = widgets['duration'].text.strip()
            try:
                start_values = [int(v) for v in start_values_str.split('-')]
                end_values = [int(v) for v in end_values_str.split('-')]
                if len(start_values) != 4 or len(end_values) != 4 or any(v < 0 for v in start_values + end_values):
                    raise ValueError('Invalid cycle values')
                duration = int(duration_str) * 60  # Convert minutes to seconds
                if duration < 0:
                    raise ValueError('Invalid duration')
                original_name = preset_name
                suffix = 1
                while preset_name in new_presets:
                    preset_name = f"{original_name} ({suffix})"
                    suffix += 1
                new_presets[preset_name] = (start_values, end_values, duration)
            except Exception as e:
                print(f"Error saving preset: {e}")
                continue
        from kivy.app import App
        presets_path = os.path.join(App.get_running_app().user_data_dir, 'presets.json')
        with open(presets_path, 'w') as f:
            json.dump(new_presets, f)
        self.presets.update(new_presets)
        if self.on_save:
            self.on_save(new_presets)
        self.dismiss()

# ============================================================================
# MainAppLayout
# ----------------------------------------------------------------------------
# In addition to the usual UI elements, we now have:
#   • When a preset is applied, both the start and end cycle times (and the session
#     duration) are updated.
#   • The slider area (for cycle times) now controls the “start” values; when changed
#     manually the “end” values are set to the same value.
# ============================================================================
class MainAppLayout(BoxLayout):
    def _update_rect(self, instance, value):
        self.rect.size = instance.size
        self.rect.pos = instance.pos

    def apply_preset(self, preset_name):
        start_values, end_values, duration_seconds = self.presets[preset_name]
        for i, slider in enumerate(self.sliders[:-1]):  # cycle time sliders
            slider.value = start_values[i]
        self.sliders[-1].value = duration_seconds
        self.animated_circle.start_cycle_time = start_values[:]
        self.animated_circle.end_cycle_time = end_values[:]
        self.animated_circle.selected_duration = duration_seconds
        self.animated_circle.duration = duration_seconds

    def update_presets(self, new_presets):
        self.presets = new_presets
        self.create_preset_buttons()

    def load_or_init_presets(self):
        # Default presets now include both start and end cycle times.
        default_presets = {
            'Chill': ([4, 8, 8, 0], [6, 10, 10, 0], 30 * 60),
            'Sleep': ([3, 7, 7, 0], [5, 9, 9, 0], 20 * 60),
            'Slerp': ([4, 8, 8, 0], [4, 8, 8, 0], 15 * 60),
        }
        from kivy.app import App
        presets_path = os.path.join(App.get_running_app().user_data_dir, 'presets.json')
        try:
            with open(presets_path, 'r') as f:
                presets = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, ValueError):
            presets = default_presets
            with open(presets_path, 'w') as f:
                json.dump(presets, f)
        return presets

    def create_preset_buttons(self):
        self.preset_buttons_layout.clear_widgets()
        min_button_width = 350
        num_buttons = len(self.presets) + 1  # +1 for the "Edit" button
        self.preset_buttons_layout.width = max(self.width, min_button_width * num_buttons)
        for preset_name, preset_values in self.presets.items():
            start_values, end_values, duration_seconds = preset_values
            duration_minutes = int((duration_seconds + 30) // 60)
            button_text = f"{preset_name}\n{'-'.join(map(str, start_values))}→{'-'.join(map(str, end_values))}/{duration_minutes}"
            btn = Button(text=button_text, halign="center", bold=True, size_hint_x=None, width=min_button_width)
            btn.bind(on_press=lambda instance, name=preset_name: self.apply_preset(name))
            btn.background_color = (0.1, 0.1, 0.1, 0.75)
            self.preset_buttons_layout.add_widget(btn)
        self.edit_presets_btn = Button(text="Edit", bold=True, size_hint_x=None, width=min_button_width)
        self.edit_presets_btn.bind(on_press=lambda instance: self.open_edit_presets_popup())
        self.edit_presets_btn.background_color = (0.1, 0.1, 0.1, 0.75)
        self.preset_buttons_layout.add_widget(self.edit_presets_btn)

    def open_edit_presets_popup(self):
        popup = EditPresetsPopup(presets=self.presets, on_save=self.update_presets)
        popup.open()

    def __init__(self, **kwargs):
        super(MainAppLayout, self).__init__(**kwargs)
        with self.canvas.before:
            self.bg = CoreImage(resource_path('assets/background.png')).texture
            self.rect = Rectangle(texture=self.bg, size=self.size, pos=self.pos)
        self.bind(size=self._update_rect, pos=self._update_rect)
        self.orientation = 'vertical'
        self.presets = self.load_or_init_presets()
        self.duration_label = Label(text='Time: 5 minutes', bold=True, width=350, size_hint_x=None)
        self.duration_slider = Slider(min=0, max=30 * 60 + 1, value=5 * 60, size_hint_x=1.5)
        self.animated_circle = AnimatedCircle(size_hint=(1, 0.8), duration_slider=self.duration_slider,
                                              duration_label=self.duration_label,
                                              update_button_label=self.update_start_stop_button_label)
        self.add_widget(self.animated_circle)
        self.bottom_layout = BoxLayout(size_hint=(1, 0.6), orientation='vertical')
        self.timer_label = Label(text='', bold=True, size_hint_y=None, height=75, font_size=72)
        self.bottom_layout.add_widget(self.timer_label)
        self.sequence_label = Label(text='0-0-0-0', bold=True, size_hint_y=None, height=75)
        self.bottom_layout.add_widget(self.sequence_label)
        start_button_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=150)
        settings_button = Button(text='Settings', bold=True, size_hint_x=0.2)
        settings_button.background_color = (0.1, 0.1, 0.1, 0.75)
        settings_button.bind(on_press=self.toggle_settings)
        start_button_layout.add_widget(settings_button)
        self.start_stop_button = Button(text='Start', bold=True)
        self.start_stop_button.bind(on_press=self.toggle_animation)
        self.start_stop_button.background_color = (0.1, 0.1, 0.1, 0.75)
        start_button_layout.add_widget(self.start_stop_button)
        test_ding_button = Button(text='Test\nsound', bold=True, size_hint_x=0.2, halign="center")
        test_ding_button.bind(on_press=self.test_ding)
        test_ding_button.background_color = (0.1, 0.1, 0.1, 0.75)
        start_button_layout.add_widget(test_ding_button)
        self.bottom_layout.add_widget(start_button_layout)
        self.settings_layout = BoxLayout(orientation='vertical')
        self.settings_visible = False
        preset_buttons_scrollview = ScrollView(size_hint=(1, None), height=150, do_scroll_x=True, do_scroll_y=False, bar_width=10)
        self.preset_buttons_layout = BoxLayout(size_hint=(None, None), height=150)
        preset_buttons_scrollview.add_widget(self.preset_buttons_layout)
        self.settings_layout.add_widget(preset_buttons_scrollview)
        self.create_preset_buttons()
        self.sliders = []
        # Create one slider per cycle phase – these control the "start" values.
        for i, label in enumerate(['Inhale', 'Hold 1', 'Exhale', 'Hold 2']):
            slider_layout = BoxLayout(orientation='horizontal')
            slider_label = Label(text=f'{label}: 0 seconds', bold=True, width=350, size_hint_x=None)
            slider = Slider(min=0 if label in ['Hold 1', 'Hold 2'] else 2, max=20, value=0)
            slider.bind(value=self.update_slider_label(slider_label, label, i))
            slider_layout.add_widget(slider_label)
            slider_layout.add_widget(slider)
            self.sliders.append(slider)
            self.settings_layout.add_widget(slider_layout)
        duration_slider_layout = BoxLayout(orientation='horizontal')
        self.duration_slider.bind(value=self.update_duration_slider_label(self.duration_label))
        duration_slider_layout.add_widget(self.duration_label)
        duration_slider_layout.add_widget(self.duration_slider)
        self.sliders.append(self.duration_slider)
        self.settings_layout.add_widget(duration_slider_layout)
        self.add_widget(self.bottom_layout)
        self.load_saved()

        self.countdown_schedule = None
        self.countdown_from = 5

    def load_saved(self):
        try:
            with open(self.save_file_path(), 'r') as f:
                saved = json.load(f)
            start_cycle_times = saved.get('start_cycle_times', [4, 8, 8, 0])
            end_cycle_times = saved.get('end_cycle_times', start_cycle_times)
            selected_duration = saved.get('selected_duration', 5 * 60)
        except (FileNotFoundError, json.JSONDecodeError):
            start_cycle_times = [4, 8, 8, 0]
            end_cycle_times = [4, 8, 8, 0]
            selected_duration = 5 * 60
        for i, slider in enumerate(self.sliders[:-1]):
            slider.value = start_cycle_times[i]
        if (selected_duration == float('inf') or selected_duration >= 30 * 60 + 1) and ALLOW_INF:
            selected_duration = float('inf')
            self.sliders[-1].value = 30 * 60 + 1
            self.duration_label.text = f'Time: ∞'
        else:
            selected_duration = max(0, selected_duration)
            self.sliders[-1].value = selected_duration
            minutes, seconds = divmod(int(selected_duration), 60)
            if minutes:
                minutes = int((selected_duration + 30) // 60)
            self.duration_label.text = f'Time: {minutes} minutes' if minutes else f'Time: {seconds} seconds'
        self.animated_circle.start_cycle_time = start_cycle_times
        self.animated_circle.end_cycle_time = end_cycle_times
        self.animated_circle.selected_duration = selected_duration
        self.animated_circle.duration = selected_duration

    def save_state(self):
        state = {
            'start_cycle_times': [slider.value for slider in self.sliders[:-1]],
            'end_cycle_times': self.animated_circle.end_cycle_time,
            'selected_duration': self.animated_circle.selected_duration,
        }
        with open(self.save_file_path(), 'w') as f:
            json.dump(state, f)

    def save_file_path(self):
        from kivy.app import App
        return os.path.join(App.get_running_app().user_data_dir, 'previous_state.json')

    def update_start_stop_button_label(self, new_label):
        self.start_stop_button.text = new_label

    def toggle_animation(self, instance):
        if instance.text == 'Start':
            self.animated_circle.phase = 0
            self.animated_circle.last_phase = -1
            self.animated_circle.progress = 0
            instance.text = 'Stop'
            self.countdown_from = 5
            self.update_countdown_label(self.countdown_from)
            self.perform_countdown(instance)
        else:
            self.animated_circle.toggle_animation(False)
            if self.countdown_schedule:
                self.countdown_schedule.cancel()
                if (self.animated_circle.duration == float('inf') or self.animated_circle.duration > 30 * 60 + 1) and ALLOW_INF:
                    self.timer_label.text = '∞'
                else:
                    self.timer_label.text = f'{int((self.animated_circle.duration + 30) // 60)}:00'
            instance.text = 'Start'
            if wake_lock and wake_lock.isHeld():
                wake_lock.release()

    def update_countdown_label(self, number):
        if number > 0:
            self.timer_label.text = str(number)
        else:
            if (self.animated_circle.duration == float('inf') or self.animated_circle.duration >= 30 * 60 + 1) and ALLOW_INF:
                self.timer_label.text = '∞'
            else:
                self.timer_label.text = ''

    def perform_countdown(self, instance):
        if self.countdown_from > 0:
            self.update_countdown_label(self.countdown_from)
            self.countdown_schedule = Clock.schedule_once(lambda dt: self.countdown_step(instance), 1)

    def countdown_step(self, instance):
        self.countdown_from -= 1
        if self.countdown_from > 0:
            self.perform_countdown(instance)
        else:
            self.update_countdown_label(self.countdown_from)
            if wake_lock:
                wake_lock.acquire()
            self.animated_circle.toggle_animation(True)

    def toggle_settings(self, instance):
        if self.settings_visible:
            self.bottom_layout.remove_widget(self.settings_layout)
            self.settings_visible = False
            self.animated_circle.size_hint_y = 0.8
        else:
            self.bottom_layout.add_widget(self.settings_layout)
            self.settings_visible = True
            self.animated_circle.size_hint_y = 0.2

    def update_slider_label(self, slider_label, label, index):
        def update_label(instance, value):
            slider_label.text = f'{label}: {int(value)} seconds'
            # When manually adjusting the slider, assume a static cycle:
            self.animated_circle.start_cycle_time[index] = value
            self.animated_circle.end_cycle_time[index] = value
            self.save_state()
            parts = self.sequence_label.text.split("-")
            if len(parts) == 4:
                parts[index] = str(int(value))
                self.sequence_label.text = "-".join(parts)
        return update_label

    def update_duration_slider_label(self, slider_label):
        def update_label(instance, value):
            if (value == float('inf') or value >= 30 * 60 + 1) and ALLOW_INF:
                slider_label.text = 'Time: ∞'
                self.animated_circle.duration = float('inf')
                self.timer_label.text = '∞'
            else:
                minutes, seconds = divmod(int(value), 60)
                slider_label.text = f'Time: {minutes} minutes' if minutes else f'Time: {seconds} seconds'
                if not self.animated_circle.animation_active:
                    seconds = 0
                    minutes = int((value + 30) // 60)
                self.timer_label.text = f'{minutes}:{seconds:02d}'
                self.animated_circle.duration = value
            if not self.animated_circle.animation_active:
                self.animated_circle.selected_duration = value
            self.save_state()
        return update_label

    def test_ding(self, instance):
        self.animated_circle.sounds[4].play()

if __name__ == '__main__':
    if not os.environ.get('CI'):
        print("Shibboleth - Breathe3")
        from kivy.app import App
        class MainApp(App):
            def build(self):
                return MainAppLayout()
        MainApp().run()