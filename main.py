from kivy.core.audio import SoundLoader
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.widget import Widget
from kivy.graphics import Color, Ellipse
from kivy.clock import Clock
from kivy.properties import NumericProperty, ListProperty, BooleanProperty
from kivy.uix.slider import Slider
from kivy.uix.label import Label
import os
import json
import math

from jnius import autoclass, JavaException

try:
    PowerManager = autoclass('android.os.PowerManager')
    Context = autoclass('android.content.Context')
    PythonActivity = autoclass('org.kivy.android.PythonActivity')

    activity = PythonActivity.mActivity
    power_manager = activity.getSystemService(Context.POWER_SERVICE)

    wake_lock = power_manager.newWakeLock(PowerManager.SCREEN_BRIGHT_WAKE_LOCK, 'Breathe3:WakelockTag')
except JavaException as je:
    wake_lock = None
    print(f"Java Exception: {je}")
except Exception as e:
    wake_lock = None
    print(f"General Exception: {e}")


class AnimatedCircle(Widget):
    radius_f = NumericProperty(25)
    radius_b = NumericProperty(25)
    cycle_time = ListProperty([4, 8, 8, 0])
    animation_active = BooleanProperty(False)
    duration = NumericProperty(5*60)  # Start with infinity

    def __init__(self, duration_slider=None, duration_label=None, update_button_label=None, **kwargs):
        super(AnimatedCircle, self).__init__(**kwargs)
        self.duration_slider = duration_slider
        self.duration_label = duration_label
        self.update_button_label = update_button_label
        self.bind(size=self.update_canvas, pos=self.update_canvas)
        self.phase = 0
        self.last_phase = -1
        self.progress = 0
        self.initial_touch_pos = None  # To store the initial touch position
        self.animation_event = Clock.schedule_interval(self.animate_circle, 0.1)
        self.animation_event.cancel()  # Start with the animation paused
        self.sounds = {
            0: SoundLoader.load('assets/ding_inhale_to_hold.wav'),
            1: SoundLoader.load('assets/ding_hold_to_exhale.wav'),
            2: SoundLoader.load('assets/ding_exhale_to_hold.wav'),
            3: SoundLoader.load('assets/ding_hold_to_inhale.wav'),
            4: SoundLoader.load('assets/ding_end.wav')  # Add an end sound
        }

    def on_touch_down(self, touch):
        # Check if the touch is within the widget bounds
        if self.collide_point(*touch.pos):
            self.initial_touch_pos = touch.pos
            touch.grab(self)  # Important to track touch across movements
            return True
        return super(AnimatedCircle, self).on_touch_down(touch)

    def on_touch_move(self, touch):
        if touch.grab_current is self:
            # Process the touch movement only if it started within this widget
            self.handle_touch_movement(touch.pos)
            self.initial_touch_pos = touch.pos
            return True
        return super(AnimatedCircle, self).on_touch_move(touch)

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)  # Release the touch
            self.initial_touch_pos = None  # Reset initial position
            return True
        return super(AnimatedCircle, self).on_touch_up(touch)

    def handle_touch_movement(self, touch_pos):
        if self.initial_touch_pos:
            # Calculate vector from center to initial touch
            vec_initial = (
                self.initial_touch_pos[0] - self.center_x,
                self.initial_touch_pos[1] - self.center_y
            )
            # Calculate vector from center to current touch
            vec_current = (
                touch_pos[0] - self.center_x,
                touch_pos[1] - self.center_y
            )
            # Calculate angles
            angle_initial = math.atan2(vec_initial[1], vec_initial[0])
            angle_current = math.atan2(vec_current[1], vec_current[0])
            # TODO: need to consider the smaller (closest) change option, otherwise we wrap around
            if angle_initial - angle_current < - math.pi:
                angle_current -= 2 * math.pi
            elif angle_initial - angle_current > math.pi:
                angle_current += 2 * math.pi
            # Calculate change in angle (in radians)
            angle_change = angle_current - angle_initial
            # Convert angle change to degrees
            angle_change_deg = math.degrees(angle_change)

            # Calculate Duration change based on angle (360 degrees = 4 minutes)
            duration_change = - angle_change_deg / 360 * 4

            # Update Duration, ensuring it doesn't go below 0
            self.duration = max(0, self.duration + duration_change * 60)  # Convert minutes to seconds

            # Update UI elements if they exist
            if self.duration_slider and self.duration_label:
                if float(self.duration) == float('inf'):
                    self.duration_slider.value = 30*60+1
                    self.duration_label.text = f'Duration: infinity'
                else:
                    self.duration_slider.value = self.duration
                    minutes = int(min(self.duration,30*60+1)) // 60
                    seconds = int(min(self.duration,30*60+1)) - 60 * minutes
                    if minutes > 0:
                        self.duration_label.text = f'Duration: {minutes} minutes'
                    else:
                        self.duration_label.text = f'Duration: {seconds} seconds'

    def toggle_animation(self):
        if self.animation_active:
            self.animation_event.cancel()
            self.animation_active = False
        else:
            self.animation_event = Clock.schedule_interval(self.animate_circle, 0.1)
            self.animation_active = True

    def update_canvas(self, *args):
        self.canvas.clear()
        with self.canvas:
            Color(0.15, 0.26, 0.91, 1)  # Blue color for Back circle
            radius_b = (min(self.width, self.height) / 2) * (self.radius_b / 100.0)
            Ellipse(pos=(self.center_x - radius_b, self.center_y - radius_b), size=(radius_b * 2, radius_b * 2))

            Color(0.9, 0.8, 0.16, 1)  # Red color for Front circle
            radius_f = (min(self.width, self.height) / 2) * (self.radius_f / 100.0)
            Ellipse(pos=(self.center_x - radius_f, self.center_y - radius_f), size=(radius_f * 2, radius_f * 2))

    def animate_circle(self, dt):
        if self.duration != float('inf'):
            self.duration -= dt
            # Update the slider and label if they exist
            if self.duration_slider and self.duration_label:
                # Assuming the max value represents infinity and should not be used here
                self.duration_slider.value = max(0, min(self.duration, self.duration_slider.max - 1))

                minutes = int(self.duration) // 60
                seconds = int(self.duration) - 60 * minutes
                if minutes > 0:
                    self.duration_label.text = f'Duration: {minutes} minutes'
                else:
                    self.duration_label.text = f'Duration: {seconds} seconds'

            if self.duration <= 0:
                self.stop_animation_with_end_sound()
                return  # Stop the method here
        
        t1, t2, t3, t4, _ = self.cycle_time
        self.progress += dt
        if self.phase == 0:
            if t1 > 0:
                self.radius_f = self.radius_b = 75 - 50 * (1 - self.progress / t1)
            if self.progress > t1:
                self.phase = 1 
                self.progress -= t1
        if self.phase == 1:
            if t2 > 0:
                self.radius_f = 75
                self.radius_b = 75 + 10 * (1 - abs(self.progress / t2 - 0.5) * 2)  # Peaks at halfway
            if self.progress > t2:
                self.phase = 2
                self.progress -= t2
        if self.phase == 2:
            if t3 > 0:
                self.radius_f = self.radius_b = 75 - 50 * self.progress / t3
            if self.progress > t3:
                self.phase = 3
                self.progress -= t3
        if self.phase == 3:
            if t4 > 0:
                self.radius_b = 25
                self.radius_f = 25 - 10 * (1 - abs(self.progress / t4 - 0.5) * 2 )  # Dips at halfway
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
        self.animation_active = False
        sound = self.sounds.get(4)  # End sound
        if sound:
            sound.play()

        def release_wake_lock_callback(dt):  # 'dt' parameter is required by Clock.schedule_once but might not be used
            if wake_lock and wake_lock.isHeld():
                wake_lock.release()
            if self.update_button_label:
                self.update_button_label('Start')
            self.duration = 5*60
            self.duration_slider.value = 5*60
            self.duration_label.text = f'Duration: 5 minutes'

        Clock.schedule_once(release_wake_lock_callback, 2)


    

class MainAppLayout(BoxLayout):
    def __init__(self, **kwargs):
        super(MainAppLayout, self).__init__(**kwargs)
        self.orientation = 'vertical'

        duration_slider_label = Label(text='Duration: 5 minutes')
        duration_slider = Slider(min=0, max=30*60+1, value=5*60, size_hint_x=1.5)  # Assuming 30*60+1 represents infinity
        self.animated_circle = AnimatedCircle(size_hint=(1, 0.5), duration_slider=duration_slider, duration_label=duration_slider_label, update_button_label=self.update_start_stop_button_label)

        self.add_widget(self.animated_circle)

        bottom_layout = BoxLayout(size_hint=(1, 0.5), orientation='vertical')
        self.start_stop_button = Button(text='Start')
        self.start_stop_button.bind(on_press=self.toggle_animation)
        bottom_layout.add_widget(self.start_stop_button)

        self.sliders = []  # Store slider references

        # Modify slider creation loop to store references
        for i, label in enumerate(['Inhale', 'Hold 1', 'Exhale', 'Hold 2']):
            slider_layout = BoxLayout(orientation='horizontal')
            slider_label = Label(text=f'{label}: 5 seconds' if label not in ['Hold 1', 'Hold 2'] else f'{label}: 0 seconds')
            slider = Slider(min=0, max=20, value=5 if label not in ['Hold 1', 'Hold 2'] else 0, size_hint_x=1.5)
            slider.bind(value=self.update_slider_label(slider_label, label, i))
            slider_layout.add_widget(slider_label)
            slider_layout.add_widget(slider)
            self.sliders.append(slider)  # Store reference to slider
            bottom_layout.add_widget(slider_layout)

        self.add_widget(bottom_layout)

        duration_slider_layout = BoxLayout(orientation='horizontal')
        duration_slider.bind(value=self.update_duration_slider_label(duration_slider_label))
        duration_slider_layout.add_widget(duration_slider_label)
        duration_slider_layout.add_widget(duration_slider)
        self.sliders.append(duration_slider)  # Optional, depending on how you handle updates
        bottom_layout.add_widget(duration_slider_layout)

        self.load_presets()

    def load_presets(self):
        try:
            with open(self.preset_file_path(), 'r') as f:
                presets = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            presets = [4, 8, 8, 0]  # Default values

        for i, slider in enumerate(self.sliders[:-1]):  # Exclude the duration slider
            slider.value = presets[i]

        # Update the cycle_time directly after loading the presets
        self.animated_circle.cycle_time = presets

    def save_presets(self):
        presets = [slider.value for slider in self.sliders[:-1]]  # Exclude the duration slider
        with open(self.preset_file_path(), 'w') as f:
            json.dump(presets, f)

    def preset_file_path(self):
        return os.path.join(App.get_running_app().user_data_dir, 'slider_presets.json')

    def update_start_stop_button_label(self, new_label):
        self.start_stop_button.text = new_label

    def toggle_animation(self, instance):
        # Update the animation cycle_time before starting
        self.animated_circle.cycle_time = [slider.value for slider in self.sliders]
        self.animated_circle.toggle_animation()
        if self.animated_circle.animation_active:
            instance.text = 'Stop'
            if wake_lock:
                wake_lock.acquire()
        else:
            instance.text = 'Start'
            if wake_lock and wake_lock.isHeld():
                wake_lock.release()

    def update_slider_label(self, slider_label, label, index):
        def update_label(instance, value):
            slider_label.text = f'{label}: {int(value)} seconds'
            self.animated_circle.cycle_time[index] = value
            self.save_presets()  # Save presets whenever a slider value changes
        return update_label

    def update_duration_slider_label(self, slider_label):
        def update_label(instance, value):
            if float(value) == float('inf') or int(value) >= 30*60+1:  # Assuming 31 is the maximum value representing infinity
                slider_label.text = 'Duration: Infinity'
                self.animated_circle.duration = float('inf')
            else:
                minutes = int(value) // 60
                seconds = int(value) - 60 * minutes
                if minutes > 0:
                    slider_label.text = f'Duration: {minutes} minutes'
                else:
                    slider_label.text = f'Duration: {seconds} seconds'
                self.animated_circle.duration = value
        return update_label

class MainApp(App):
    def build(self):
        return MainAppLayout()

if __name__ == '__main__':
    MainApp().run()