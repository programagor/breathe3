from kivy.core.audio import SoundLoader
from kivy.core.image import Image as CoreImage
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.widget import Widget
from kivy.graphics import Color, Ellipse, Rectangle
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
    radius_a = 75
    radius_b = 25
    radius_c = 25
    radius_d = 20
    radius_e = 20
    cycle_time = [4, 8, 8, 0]
    animation_active = BooleanProperty(False)
    duration = NumericProperty(5*60)  # Start with 5 minutes
    selected_duration = 5*60  # Default to 5 minutes

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
        self.initial_touch_pos = None  # To store the initial touch position
        self.animation_event = Clock.schedule_interval(self.animate_circle, self.framerate)
        self.animation_event.cancel()  # Start with the animation paused
        self.sounds = {
            0: SoundLoader.load('assets/ding_inhale.wav'),
            1: SoundLoader.load('assets/ding_hold1.wav'),
            2: SoundLoader.load('assets/ding_exhale.wav'),
            3: SoundLoader.load('assets/ding_hold2.wav'),
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
            if angle_initial - angle_current < - math.pi:
                angle_current -= 2 * math.pi
            elif angle_initial - angle_current > math.pi:
                angle_current += 2 * math.pi
            # Calculate change in angle (in radians)
            angle_change = angle_current - angle_initial
            # Convert angle change to degrees
            angle_change_deg = math.degrees(angle_change)
            # Calculate Duration change based on angle (360 degrees = 4 minutes)
            duration_change = - angle_change_deg / 360 * 4 * 60 

            # Update Duration, handling the maximum as infinity.
            if ( (self.duration == float('inf') or self.duration >= 30*60+1) and duration_change < 0 ) :
                self.duration = 30*60+1 + duration_change
            elif ( (self.duration == float('inf') or self.duration >= 30*60+1 and duration_change > 0) ):
                self.duration = float('inf')
            else:
                self.duration += duration_change
            self.duration = max(0,self.duration)
            if self.duration >= 30*60+1:
                self.duration = float('inf')

            if self.animation_active == False:
                self.selected_duration = max(0, self.selected_duration + duration_change * 60)  # Update selected_duration as well

            # Update UI elements if they exist
            if self.duration_slider and self.duration_label:
                if self.duration == float('inf') or self.duration >= 30*60+1:
                    self.duration_slider.value = 30*60+1
                    self.duration_label.text = f'Time: Infinity'
                else:
                    self.duration_slider.value = self.duration
                    minutes, seconds = divmod(int(self.duration), 60)
                    self.duration_label.text = f'Time: {minutes} minutes' if minutes else f'Time: {seconds} seconds'

    def toggle_animation(self,enable):
        if not enable:
            self.animation_event.cancel()
            self.animation_active = False
        else:
            self.animation_event = Clock.schedule_interval(self.animate_circle, self.framerate)
            self.animation_active = True

    def update_canvas(self, *args):
        self.canvas.clear()
        with self.canvas:
            Color(0.094, 0.004, 0.114, 0.25)  # Reference maximum
            radius_a = (min(self.width, self.height) / 2) * (self.radius_a / 100.0)
            Ellipse(pos=(self.center_x - radius_a, self.center_y - radius_a), size=(radius_a * 2, radius_a * 2))

            Color(0.95, 0.95, 0.95, 0.75)  # White, shows only during hold inhale
            radius_b = (min(self.width, self.height) / 2) * (self.radius_b / 100.0)
            Ellipse(pos=(self.center_x - radius_b, self.center_y - radius_b), size=(radius_b * 2, radius_b * 2))

            Color(0.988, 0.667, 0.992, 1)  # Outer edge
            radius_c = (min(self.width, self.height) / 2) * (self.radius_c / 100.0)
            Ellipse(pos=(self.center_x - radius_c, self.center_y - radius_c), size=(radius_c * 2, radius_c * 2))

            Color(0.95, 0.95, 0.95, 1)  # Second frontmost (white, shows only during hold exhaled)
            radius_d = (min(self.width, self.height) / 2) * (self.radius_d / 100.0)
            Ellipse(pos=(self.center_x - radius_d, self.center_y - radius_d), size=(radius_d * 2, radius_d * 2))

            Color(0.231, 0.051, 0.286, 1)  # Frontmost (little one, forms inner edge during most, shrinks to zero during hold exhaled)
            radius_e = (min(self.width, self.height) / 2) * (self.radius_e / 100.0)
            Ellipse(pos=(self.center_x - radius_e, self.center_y - radius_e), size=(radius_e * 2, radius_e * 2))

    def animate_circle(self, dt):
        if self.duration != float('inf') and self.duration < 30*60+1:
            self.duration -= dt
            # Update the slider and label if they exist
            if self.duration_slider and self.duration_label:
                # Assuming the max value represents infinity and should not be used here
                self.duration_slider.value = max(0, min(self.duration, self.duration_slider.max - 1))
                
                minutes, seconds = divmod(int(self.duration), 60)
                self.duration_label.text = f'Time: {minutes} minutes' if minutes else f'Time: {seconds} seconds'

            if self.duration <= 0:
                self.stop_animation_with_end_sound()
                return  # Stop the method here
        
        t1, t2, t3, t4, _ = self.cycle_time
        self.progress += dt
        if self.phase == 0:
            if t1 > 0:
                self.radius_b = self.radius_c = 75 - 50 * (1 - self.progress / t1)
                self.radius_d = self.radius_e = self.radius_b - 5
            if self.progress > t1:
                self.phase = 1 
                self.progress -= t1
        if self.phase == 1:
            if t2 > 0:
                self.radius_b = 75 + 10 * (1 - abs(self.progress / t2 - 0.5) * 2)  # Peaks at halfway
                self.radius_c = 75
                self.radius_d = self.radius_e = 75 - 5
            if self.progress > t2:
                self.phase = 2
                self.progress -= t2
        if self.phase == 2:
            if t3 > 0:
                self.radius_b = self.radius_c = 75 - 50 * self.progress / t3
                self.radius_d = self.radius_e = self.radius_b - 5
            if self.progress > t3:
                self.phase = 3
                self.progress -= t3
        if self.phase == 3:
            if t4 > 0:
                self.radius_b = self.radius_c = 25
                self.radius_d = self.radius_b - 5
                self.radius_e = 20 - 10 * (1 - abs(self.progress / t4 - 0.5) * 2 )  # Dips at halfway
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
        sound = self.sounds.get(4)  # End sound
        if sound:
            sound.play()

        def release_wake_lock_callback(dt):  # 'dt' parameter is required by Clock.schedule_once but might not be used
            self.animation_active = False
            if wake_lock and wake_lock.isHeld():
                wake_lock.release()
            if self.update_button_label:
                self.update_button_label('Start')
            self.duration = self.selected_duration
            if self.duration == float('inf') or self.duration >= 30*60+1:
                self.duration_slider.value = 30*60+1
                self.duration_label.text = f'Time: Infinity'
            else:
                self.duration_slider.value = self.selected_duration
                minutes, seconds = divmod(int(self.selected_duration), 60)
                self.duration_label.text = f'Time: {minutes} minutes' if minutes else f'Time: {seconds} seconds'

        Clock.schedule_once(release_wake_lock_callback, 2)


    

class MainAppLayout(BoxLayout):
    def _update_rect(self, instance, value):
        self.rect.size = instance.size
        self.rect.pos = instance.pos

    def apply_preset(self, preset_name):
        cycle_times, duration = self.get_presets()[preset_name]
        # Update cycle time sliders
        for i, slider in enumerate(self.sliders[:-1]):  # Exclude the duration slider
            slider.value = cycle_times[i]
        # Update duration slider and labels accordingly
        self.sliders[-1].value = duration
        self.animated_circle.selected_duration = duration  # Update selected_duration


    def __init__(self, **kwargs):
        super(MainAppLayout, self).__init__(**kwargs)

        with self.canvas.before:
            self.bg = CoreImage("assets/background.png").texture
            self.rect = Rectangle(texture=self.bg, size=self.size, pos=self.pos)
        self.bind(size=self._update_rect, pos=self._update_rect)

        self.orientation = 'vertical'

        self.duration_label = Label(text='Time: 5 minutes', bold=True, width=350, size_hint_x=None)
        self.duration_slider = Slider(min=0, max=30*60+1, value=5*60, size_hint_x=1.5)  # Assuming 30*60+1 represents infinity
        self.animated_circle = AnimatedCircle(size_hint=(1, 0.4), duration_slider=self.duration_slider, duration_label=self.duration_label, update_button_label=self.update_start_stop_button_label)

        self.add_widget(self.animated_circle)

        self.bottom_layout = BoxLayout(size_hint=(1, 0.6), orientation='vertical')

        self.timer_label = Label(text='', bold=True, size_hint_y=None ,height=75)
        self.bottom_layout.add_widget(self.timer_label)

        self.sequence_label = Label(text='0-0-0-0', bold=True, size_hint_y=None ,height=75)
        self.bottom_layout.add_widget(self.sequence_label)

        start_button_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=75)

        settings_button = Button(text='Settings', size_hint_x=0.2)
        settings_button.background_color = (0.1,0.1,0.1,0.75)
        
        settings_button.bind(on_press=self.toggle_settings)

        start_button_layout.add_widget(settings_button)

        self.start_stop_button = Button(text='Start', bold=True)
        self.start_stop_button.bind(on_press=self.toggle_animation)
        self.start_stop_button.background_color = (0.1,0.1,0.1,0.75)

        start_button_layout.add_widget(self.start_stop_button)

        self.bottom_layout.add_widget(start_button_layout)

        self.settings_layout = BoxLayout(orientation='vertical')
        self.settings_visible = True

        self.bottom_layout.add_widget(self.settings_layout)

        preset_buttons_layout = BoxLayout(size_hint_y=None, height=150)  # Adjust size_hint_y and height as needed

        for preset_name, preset_values in self.get_presets().items():
            cycle_times, duration_seconds = preset_values
            duration_minutes = duration_seconds // 60
            # Format the button text to include cycle times and duration
            button_text = f"{preset_name}\n{'-'.join(map(str, cycle_times))}/{duration_minutes}"
            btn = Button(text=button_text, halign="center", bold=True)
            btn.bind(on_press=lambda instance, name=preset_name: self.apply_preset(name))
            btn.background_color = (0.1,0.1,0.1,0.75)
            preset_buttons_layout.add_widget(btn)

        self.settings_layout.add_widget(preset_buttons_layout)  # Add this before the duration slider is added

        self.sliders = []  # Store slider references

        # Modify slider creation loop to store references
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

    def load_saved(self):
        try:
            with open(self.save_file_path(), 'r') as f:
                saved = json.load(f)
            cycle_times = saved.get('cycle_times', [4, 8, 8, 0])  # Default values if not found
            selected_duration = saved.get('selected_duration', 5*60)  # Default to 5 minutes if not found
        except (FileNotFoundError, json.JSONDecodeError):
            cycle_times = [4, 8, 8, 0]  # Default values
            selected_duration = 5*60  # Default to 5 minutes

        for i, slider in enumerate(self.sliders[:-1]):  # Exclude the duration slider
            slider.value = cycle_times[i]

        if selected_duration == float('inf') or selected_duration >= 30*60+1:
            selected_duration = float('inf')
            self.sliders[-1].value = 30*60+1
            self.duration_label.text = f'Time: Infinity'
        else:
            selected_duration = max(0,selected_duration)
            self.sliders[-1].value = selected_duration
            minutes, seconds = divmod(int(selected_duration), 60)
            self.duration_label.text = f'Time: {minutes} minutes' if minutes else f'Time: {seconds} seconds'
        self.animated_circle.selected_duration = selected_duration
        self.animated_circle.duration = selected_duration


    def save_state(self):
        state = {
            'cycle_times': [slider.value for slider in self.sliders[:-1]],  # Exclude the duration slider
            'selected_duration': self.animated_circle.selected_duration,
        }
        with open(self.save_file_path(), 'w') as f:
            json.dump(state, f)


    def save_file_path(self):
        return os.path.join(App.get_running_app().user_data_dir, 'previous_state.json')

    def get_presets(self):
        return {
            'Chill': ([4, 9, 9, 0], 30*60),  # Preset values: cycle times and duration in seconds
            'Sleep': ([4, 7, 8, 0], 20*60),
            # Add more presets here
        }

    def update_start_stop_button_label(self, new_label):
        self.start_stop_button.text = new_label

    def toggle_animation(self, instance):
        # Update the animation cycle_time before starting
        self.animated_circle.cycle_time = [slider.value for slider in self.sliders]
        if instance.text == 'Start':
            instance.text = 'Stop'
            if wake_lock:
                wake_lock.acquire()
            # TODO: Insert countdown (the timer_label needs to go 5 to 1 before the animation starts.
            
            self.animated_circle.toggle_animation(True)
            
        else:
            self.animated_circle.toggle_animation(False)
            instance.text = 'Start'
            if wake_lock and wake_lock.isHeld():
                wake_lock.release()

    def toggle_settings(self, instance):
        if self.settings_visible:
            # Settings are currently visible, remove the layout
            self.bottom_layout.remove_widget(self.settings_layout)
            self.settings_visible = False  # Update visibility state
            self.animated_circle.size_hint_y = 0.8
        else:
            # Settings are hidden, reattach the layout
            self.bottom_layout.add_widget(self.settings_layout)
            self.settings_visible = True  # Update visibility state
            self.animated_circle.size_hint_y = 0.4


    def update_slider_label(self, slider_label, label, index):
        def update_label(instance, value):
            slider_label.text = f'{label}: {int(value)} seconds'
            self.animated_circle.cycle_time[index] = value
            self.save_state()  # Save slider state whenever a slider value changes
            # break into pieces by the "-" symbol, change the index-th element to a new value, then reassemble into a string.
            self.sequence_label.text = "-".join(str(int(value)) if i == index else part for i, part in enumerate(self.sequence_label.text.split("-")))

        return update_label

    def update_duration_slider_label(self, slider_label):
        def update_label(instance, value):
            if value == float('inf') or value >= 30*60+1:  # Assuming >30 is the maximum value representing infinity
                slider_label.text = 'Time: Infinity'
                self.animated_circle.duration = float('inf')
                self.timer_label.text = ''
            else:
                minutes, seconds = divmod(int(value), 60)
                slider_label.text = f'Time: {minutes} minutes' if minutes else f'Time: {seconds} seconds'
                if self.animated_circle.animation_active == False:
                    seconds=0
                self.timer_label.text = f'{minutes}:{seconds:02d}'
                self.animated_circle.duration = value
            if self.animated_circle.animation_active == False:
                self.animated_circle.selected_duration = value
            self.save_state()  # Save slider state to file whenever a slider value changes

        return update_label

class MainApp(App):
    def build(self):
        return MainAppLayout()

if __name__ == '__main__':
    MainApp().run()