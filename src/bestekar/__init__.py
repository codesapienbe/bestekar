#!/usr/bin/env python3
"""
Bestekar - Türkçe şarkı sözlerini müziğe dönüştüren AI besteci
"""

import os
import sys
import time
import torch
import warnings
from pathlib import Path
from typing import Optional, Any
from abc import ABC, abstractmethod
import math
import shutil
import requests
from datetime import datetime

try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv()
except ImportError:
    pass  # .env loading is optional; continue silently if python-dotenv absent


# System tray imports - required for tray functionality
try:
    import pystray  # type: ignore
    from PIL import Image  # type: ignore
except ImportError:  # pragma: no cover
    print("❌ System tray dependencies not found. Please install with: uv add pystray pillow")
    sys.exit(1)

# Import Celery tasks from bestewk module
from bestewk import (
    generate_music_task, 
    open_help_task, 
    exit_app_task, 
    get_active_generation_tasks,
    app_init_task,
    celery_app
)

# Kivy GUI imports - ONLY LOADED WHEN NEEDED
# These will be imported only in the main() function to prevent worker from loading GUI
KIVY_LOADED = False
App = Builder = StringProperty = BooleanProperty = NumericProperty = None
BoxLayout = FileChooserIconView = Popup = ProgressBar = ScrollView = None  
TextInput = Button = Label = Clock = Config = None

def _load_kivy_for_gui():
    """Load Kivy components only when GUI is needed."""
    global KIVY_LOADED, App, Builder, StringProperty, BooleanProperty, NumericProperty
    global BoxLayout, FileChooserIconView, Popup, ProgressBar, ScrollView
    global TextInput, Button, Label, Clock, Config
    
    if KIVY_LOADED:
        return True
        
    try:
        # Configure Kivy BEFORE importing to prevent auto window opening
        os.environ.setdefault("KIVY_NO_CONSOLELOG", "1")  # Reduce console spam
        os.environ.setdefault("KIVY_LOG_LEVEL", "warning")  # Only show warnings
        os.environ.setdefault("KIVY_NO_ARGS", "1")  # Don't process command line args
        os.environ.setdefault("KIVY_WINDOW_MINIMIZE", "1")  # Don't auto-show window
        os.environ.setdefault("KIVY_WINDOW", "sdl2")  # Use SDL2 window provider
        os.environ.setdefault("KIVY_TEXT", "pil")  # Use PIL text provider
        
        # Set Windows-specific GL backend for better compatibility
        if sys.platform == "win32":
            os.environ.setdefault("KIVY_GL_BACKEND", "angle_sdl2")
            
        # Import Kivy config first to set window properties
        from kivy.config import Config  # type: ignore
        # Configure Kivy to not show window automatically
        Config.set('graphics', 'width', '800')
        Config.set('graphics', 'height', '600')
        Config.set('graphics', 'resizable', True)
        Config.set('graphics', 'show_cursor', True)
        Config.set('graphics', 'show_taskbar_icon', True)
        Config.set('graphics', 'minimum_width', '400')
        Config.set('graphics', 'minimum_height', '300')
        # Critical: prevent auto window creation
        Config.set('kivy', 'exit_on_escape', '0')
        Config.set('kivy', 'desktop', '1')
        
        # Now safely import other Kivy modules
        from kivy.app import App  # type: ignore
        from kivy.lang import Builder  # type: ignore
        from kivy.properties import StringProperty, BooleanProperty, NumericProperty  # type: ignore
        from kivy.uix.boxlayout import BoxLayout  # type: ignore
        from kivy.uix.filechooser import FileChooserIconView  # type: ignore
        from kivy.uix.popup import Popup  # type: ignore
        from kivy.uix.progressbar import ProgressBar  # type: ignore
        from kivy.uix.scrollview import ScrollView  # type: ignore
        from kivy.uix.textinput import TextInput  # type: ignore
        from kivy.uix.button import Button  # type: ignore
        from kivy.uix.label import Label  # type: ignore
        from kivy.clock import Clock  # type: ignore
        
        KIVY_LOADED = True
        
        # Create Kivy classes after successful import
        _create_kivy_classes()
        
        return True
        
    except ImportError:  # pragma: no cover
        print("❌ Kivy not found. Please install with: uv add kivy")
        return False

def _safe_schedule_once(callback, delay=0):
    """Safely schedule a Clock callback if Kivy is loaded."""
    if Clock:
        Clock.schedule_once(callback, delay)

# Kivy-dependent classes - will be defined when Kivy is loaded
ProgressDialog = None  # type: ignore
RootWidget = None  # type: ignore
BestekarKivyApp = None  # type: ignore

def _create_kivy_classes():
    """Create Kivy-dependent classes after Kivy is loaded."""
    global ProgressDialog, RootWidget, BestekarKivyApp
    
    if not KIVY_LOADED:
        return False
        
    class ProgressDialog(Popup):  # type: ignore
        """Progress dialog for showing music generation progress with logs."""
        
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.celery_task_id = None
            self.celery_result = None
            self.task_monitor_event = None
            self.start_time = None
            
        def start_celery_task_monitoring(self, task_id: str):
            """Start monitoring a Celery task."""
            if not Clock:
                return  # Kivy not loaded
                
            self.celery_task_id = task_id
            from celery.result import AsyncResult
            self.celery_result = AsyncResult(task_id, app=celery_app)
            
            # Start monitoring task progress
            if self.task_monitor_event:
                self.task_monitor_event.cancel()
            
            self.task_monitor_event = Clock.schedule_interval(self.update_celery_progress, 1.0)
            logger.info(f"Started monitoring Celery task {task_id}")

        def update_celery_progress(self, dt):
            """Update progress based on Celery task status."""
            if not self.celery_result:
                return False
                
            try:
                # Check task state
                state = self.celery_result.state
                
                if state == 'PENDING':
                    self.update_progress(5, "Task queued...")
                elif state == 'PROGRESS':
                    # Get progress info from task
                    info = self.celery_result.info
                    if isinstance(info, dict):
                        progress = info.get('progress', 0)
                        message = info.get('message', 'Processing...')
                        self.update_progress(progress, message)
                elif state == 'SUCCESS':
                    self.update_progress(100, "Generation completed!")
                    if self.task_monitor_event:
                        self.task_monitor_event.cancel()
                    return False  # Stop scheduling
                elif state == 'FAILURE':
                    self.update_progress(0, f"Generation failed: {self.celery_result.info}")
                    if self.task_monitor_event:
                        self.task_monitor_event.cancel()
                    return False  # Stop scheduling
                    
            except Exception as e:
                logger.error(f"Error monitoring task: {e}")
                return False  # Stop scheduling
                
            return True  # Continue scheduling

        def cancel_generation(self):
            """Cancel the current generation task."""
            try:
                if self.celery_result:
                    # Revoke the task
                    celery_app.control.revoke(self.celery_task_id, terminate=True)
                    self.add_log("🛑 Generation cancelled by user")
                    self.update_progress(0, "Generation cancelled")
                    
                if self.task_monitor_event:
                    self.task_monitor_event.cancel()
                    
            except Exception as e:
                logger.error(f"Error cancelling task: {e}")
                self.add_log(f"❌ Error cancelling: {str(e)}")

        def update_progress(self, progress: float, message: str = ""):
            """Update progress bar and message."""
            if not Clock:
                return  # Kivy not loaded
                
            def _update_ui(dt):
                self.ids.progress_bar.value = progress
                if message:
                    self.ids.progress_label.text = message
                    
                # Update time estimation
                if self.start_time and progress > 0:
                    elapsed = time.time() - self.start_time
                    if progress < 100:
                        estimated_total = elapsed / (progress / 100)
                        remaining = estimated_total - elapsed
                        self.ids.time_label.text = f"Estimated time remaining: {int(remaining // 60)}m {int(remaining % 60)}s"
                    else:
                        self.ids.time_label.text = "Generation completed!"
                        self.ids.cancel_button.disabled = True
                        self.ids.close_button.disabled = False
                        
            _safe_schedule_once(_update_ui)

        def add_log(self, message: str):
            """Add a log message to the log display."""
            if not Clock:
                return  # Kivy not loaded
                
            def _add_log(dt):
                current_text = self.ids.log_text.text
                timestamp = time.strftime("%H:%M:%S")
                new_line = f"[{timestamp}] {message}\n"
                self.ids.log_text.text = current_text + new_line
                
                # Auto-scroll to bottom
                self.ids.log_scroll.scroll_to(self.ids.log_text)
                
            _safe_schedule_once(_add_log)

        def start_progress_tracking(self, duration: int):
            """Start tracking progress for generation."""
            self.start_time = time.time()
            self.setup_log_capture()
            self.add_log("🎵 Starting music generation...")
            
        def setup_log_capture(self):
            """Set up log capture to show progress in the dialog."""
            
            import logging as stdlib_logging
            
            class ProgressLogHandler(stdlib_logging.Handler):
                def __init__(self, progress_dialog):
                    super().__init__()
                    self.progress_dialog = progress_dialog
                    
                def emit(self, record):
                    try:
                        msg = self.format(record)
                        if any(keyword in msg.lower() for keyword in ['generating', 'progress', 'completed', 'error', 'failed']):
                            self.progress_dialog.add_log(msg)
                    except Exception:
                        pass
                        
            # Set up stdout capture for generation progress
            import sys
            
            class ProgressCapture:
                def __init__(self, progress_dialog):
                    self.progress_dialog = progress_dialog
                    self.original_stdout = sys.stdout
                    
                def write(self, text):
                    self.original_stdout.write(text)
                    if text.strip() and any(keyword in text.lower() for keyword in ['generating', 'progress', '%']):
                        self.progress_dialog.add_log(text.strip())
                        
                def flush(self):
                    self.original_stdout.flush()
                    
            # Install handlers
            handler = ProgressLogHandler(self)
            logger.add(handler, level="INFO")
            
    class RootWidget(BoxLayout):  # type: ignore
        """Kivy root widget for the song generation form with RVC integration."""
        
        lyrics_path = StringProperty("") if StringProperty else ""  # type: ignore
        style_text = StringProperty("Turkish emotional pop ballad WITH FEMALE VOCALS, acoustic guitar, piano") if StringProperty else ""  # type: ignore
        duration = NumericProperty(30) if NumericProperty else 30  # type: ignore
        instrumental = BooleanProperty(False) if BooleanProperty else False  # type: ignore
        rvc_model_path = StringProperty("") if StringProperty else ""  # type: ignore
        generation_mode = StringProperty("Complete Song (RVC)") if StringProperty else "Complete Song (RVC)"  # type: ignore

        def __init__(self, **kwargs):
            super().__init__(**kwargs)

        def open_filechooser(self):
            """Open file chooser dialog for lyrics file."""
            if FileChooserIconView is None or Popup is None:
                return
            
            # Create a container for the file chooser and buttons
            from kivy.uix.boxlayout import BoxLayout  # type: ignore
            from kivy.uix.button import Button  # type: ignore
            from kivy.uix.label import Label  # type: ignore
            
            container = BoxLayout(orientation='vertical', spacing=10, padding=10)
            
            # File chooser
            chooser = FileChooserIconView(
                path=str(Path.cwd()),
                filters=['*.txt', '*.md', '*.text'],  # Filter for text files
                size_hint=(1, 0.8)
            )
            container.add_widget(chooser)
            
            # Selected file label
            selected_label = Label(
                text="No file selected",
                size_hint=(1, 0.1),
                text_size=(None, None),
                halign='left'
            )
            container.add_widget(selected_label)
            
            # Buttons layout
            button_layout = BoxLayout(
                orientation='horizontal',
                spacing=10,
                size_hint=(1, 0.1)
            )
            
            cancel_btn = Button(text="Cancel", size_hint=(0.5, 1))
            select_btn = Button(text="Select", size_hint=(0.5, 1))
            
            button_layout.add_widget(cancel_btn)
            button_layout.add_widget(select_btn)
            container.add_widget(button_layout)
            
            popup = Popup(
                title="Select lyrics file",
                content=container,
                size_hint=(0.9, 0.9),
                auto_dismiss=False
            )

            def _on_file_select(instance, selection):
                """Update label when file is selected."""
                if selection:
                    selected_label.text = f"Selected: {Path(selection[0]).name}"
                else:
                    selected_label.text = "No file selected"

            def _on_select_button(instance):
                """Handle Select button press."""
                if chooser.selection:
                    self.lyrics_path = chooser.selection[0]
                    # Update the UI text input if it exists
                    if hasattr(self, 'ids') and 'lyrics_path' in self.ids:
                        self.ids.lyrics_path.text = self.lyrics_path
                    popup.dismiss()
                else:
                    selected_label.text = "Please select a file first"

            def _on_double_tap(instance, touch):
                """Handle double-click on file chooser."""
                if chooser.selection and touch.is_double_tap:
                    _on_select_button(instance)
                    return True
                return False

            def _on_cancel_button(instance):
                """Handle Cancel button press."""
                popup.dismiss()

            # Bind events
            chooser.bind(selection=_on_file_select)
            chooser.bind(on_touch_down=_on_double_tap)
            select_btn.bind(on_press=_on_select_button)
            cancel_btn.bind(on_press=_on_cancel_button)
            
            popup.open()

        def open_rvc_filechooser(self):
            """Open file chooser dialog for RVC model file."""
            if FileChooserIconView is None or Popup is None:
                return
            
            from kivy.uix.boxlayout import BoxLayout  # type: ignore
            from kivy.uix.button import Button  # type: ignore
            from kivy.uix.label import Label  # type: ignore
            
            container = BoxLayout(orientation='vertical', spacing=10, padding=10)
            
            # File chooser for .pth files
            chooser = FileChooserIconView(
                path=str(Path.cwd()),
                filters=['*.pth', '*.pt'],  # RVC model files
                size_hint=(1, 0.8)
            )
            container.add_widget(chooser)
            
            selected_label = Label(
                text="No RVC model selected (optional)",
                size_hint=(1, 0.1),
                text_size=(None, None),
                halign='left'
            )
            container.add_widget(selected_label)
            
            button_layout = BoxLayout(orientation='horizontal', spacing=10, size_hint=(1, 0.1))
            cancel_btn = Button(text="Cancel", size_hint=(0.5, 1))
            select_btn = Button(text="Select", size_hint=(0.5, 1))
            
            button_layout.add_widget(cancel_btn)
            button_layout.add_widget(select_btn)
            container.add_widget(button_layout)
            
            popup = Popup(
                title="Select RVC Model (.pth file)",
                content=container,
                size_hint=(0.9, 0.9),
                auto_dismiss=False
            )

            def _on_rvc_select(instance, selection):
                if selection:
                    selected_label.text = f"Selected: {Path(selection[0]).name}"
                else:
                    selected_label.text = "No RVC model selected (optional)"

            def _on_rvc_select_button(instance):
                if chooser.selection:
                    self.rvc_model_path = chooser.selection[0]
                    if hasattr(self, 'ids') and 'rvc_model_path' in self.ids:
                        self.ids.rvc_model_path.text = self.rvc_model_path
                    popup.dismiss()
                else:
                    # Allow empty selection for optional RVC
                    self.rvc_model_path = ""
                    if hasattr(self, 'ids') and 'rvc_model_path' in self.ids:
                        self.ids.rvc_model_path.text = ""
                    popup.dismiss()

            def _on_rvc_cancel_button(instance):
                popup.dismiss()

            chooser.bind(selection=_on_rvc_select)
            select_btn.bind(on_press=_on_rvc_select_button)
            cancel_btn.bind(on_press=_on_rvc_cancel_button)
            
            popup.open()

        async def _run_rvc_generation(self, params):
            """Run RVC generation pipeline with progress tracking."""
            lyrics_text, style_text, duration, rvc_model_path, mode, progress_dialog = params
            
            try:
                progress_dialog.add_log("🎵 Starting RVC generation pipeline...")
                progress_dialog.update_progress(5, "Initializing RVC components...")
                
                # Check if generation was cancelled
                if progress_dialog.generation_cancelled:
                    return
                
                progress_dialog.add_log(f"📝 Processing lyrics ({len(lyrics_text)} characters)")
                progress_dialog.add_log(f"🎨 Style: {style_text}")
                progress_dialog.add_log(f"⏱️ Duration: {duration} seconds")
                progress_dialog.add_log(f"🎤 Mode: {mode}")
                
                progress_dialog.update_progress(10, "Setting up RVC generator...")
                
                # Create generator with RVC support
                generator = TurkishSongGeneratorWithRVC(
                    model_name=None,  # Use automatic resource-based selection
                    rvc_model_path=rvc_model_path if rvc_model_path else None
                )
                
                progress_dialog.update_progress(15, "Loading AI models...")
                progress_dialog.add_log("🔄 Loading optimal MusicGen model based on system resources...")
                
                # Check if generation was cancelled
                if progress_dialog.generation_cancelled:
                    return
                
                if mode == "Complete Song (RVC)":
                    progress_dialog.add_log("🎼 Generating complete song with vocals...")
                    progress_dialog.update_progress(20, "Generating instrumental backing track...")
                    
                    output_file = await generator.generate_complete_song(
                        lyrics=lyrics_text,
                        style=style_text,
                        duration=duration,
                        output_name=f"music/bestekar_rvc_{int(time.time())}",
                        add_vocals=True
                    )
                    
                elif mode == "Instrumental Only":
                    progress_dialog.add_log("🎼 Generating instrumental track...")
                    progress_dialog.update_progress(30, "Creating instrumental music...")
                    
                    output_file = generator.generate_song(
                        lyrics=lyrics_text,
                        style=style_text,
                        duration=duration,
                        output_name=f"music/bestekar_instrumental_{int(time.time())}",
                        instrumental=True
                    )
                    
                elif mode == "Vocals Only (RVC)":
                    progress_dialog.add_log("🎤 Generating vocals with RVC...")
                    progress_dialog.update_progress(30, "Creating vocal track...")
                    
                    # Generate vocals only using RVC
                    rvc_singer = RVCSinger(rvc_model_path, None)
                    output_file = await rvc_singer.generate_singing_voice(
                        lyrics=lyrics_text,
                        output_path=f"music/bestekar_vocals_{int(time.time())}.wav"
                    )
                
                progress_dialog.update_progress(95, "Finalizing...")
                
                # Check if generation was cancelled
                if progress_dialog.generation_cancelled:
                    progress_dialog.add_log("❌ Generation cancelled by user")
                    return
                
                if output_file and Path(output_file).exists():
                    progress_dialog.update_progress(100, "Generation completed successfully!")
                    progress_dialog.add_log(f"✅ Song generated: {Path(output_file).name}")
                    progress_dialog.add_log(f"📁 Location: {output_file}")
                    
                    # Show success notification
                    def show_success(dt):
                        self._notify(f"🎵 Song generated successfully!\n{Path(output_file).name}")
                    _safe_schedule_once(show_success, 0)
                    
                else:
                    progress_dialog.update_progress(0, "Generation failed")
                    progress_dialog.add_log("❌ Generation failed - no output file created")
                    
                    def show_error(dt):
                        self._notify("❌ Generation failed. Check logs for details.")
                    _safe_schedule_once(show_error, 0)
                    
            except Exception as e:
                progress_dialog.update_progress(0, f"Error: {str(e)}")
                progress_dialog.add_log(f"❌ Error during generation: {str(e)}")
                logger.exception("RVC generation failed", error=str(e))
                
                def show_error(dt):
                    self._notify(f"❌ Generation error: {str(e)}")
                _safe_schedule_once(show_error, 0)

        def start_rvc_generation(self):
            """Start RVC-enhanced song generation with progress dialog."""
            # Get values from UI
            lyrics_path = self.ids.lyrics_path.text if hasattr(self, 'ids') and 'lyrics_path' in self.ids else self.lyrics_path
            style_text = self.ids.style_input.text if hasattr(self, 'ids') and 'style_input' in self.ids else self.style_text
            duration = int(self.ids.dur_input.text) if hasattr(self, 'ids') and 'dur_input' in self.ids and self.ids.dur_input.text.isdigit() else int(self.duration)
            rvc_model_path = self.ids.rvc_model_path.text if hasattr(self, 'ids') and 'rvc_model_path' in self.ids else self.rvc_model_path
            mode = self.ids.generation_mode.text if hasattr(self, 'ids') and 'generation_mode' in self.ids else self.generation_mode
            
            if not lyrics_path or not Path(lyrics_path).exists():
                self._notify("Please select a valid lyrics file")
                return

            with open(lyrics_path, "r", encoding="utf-8") as f:
                lyrics_text = f.read()

            # Create and show progress dialog
            progress_dialog = ProgressDialog()
            progress_dialog.start_progress_tracking(duration)
            progress_dialog.open()
            
            params = (lyrics_text, style_text, duration, rvc_model_path, mode, progress_dialog)

            import threading
            
            def run_async_generation():
                import asyncio
                try:
                    # Create new event loop for this thread
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(self._run_rvc_generation(params))
                finally:
                    loop.close()

            gen_thread = threading.Thread(target=run_async_generation, name="RVCGeneration", daemon=True)
            progress_dialog.generation_thread = gen_thread
            gen_thread.start()

        def start_generation(self):
            """Start song generation process using Celery tasks."""
            # Get values from the actual UI widgets
            lyrics_path = self.ids.lyrics_path.text if hasattr(self, 'ids') and 'lyrics_path' in self.ids else self.lyrics_path
            style_text = self.ids.style_input.text if hasattr(self, 'ids') and 'style_input' in self.ids else self.style_text
            duration = int(self.ids.dur_input.text) if hasattr(self, 'ids') and 'dur_input' in self.ids and self.ids.dur_input.text.isdigit() else int(self.duration)
            instrumental = self.ids.instrumental_cb.active if hasattr(self, 'ids') and 'instrumental_cb' in self.ids else self.instrumental
            rvc_model_path = self.ids.rvc_model_path.text if hasattr(self, 'ids') and 'rvc_model_path' in self.ids else self.rvc_model_path
            generation_mode = self.ids.mode_spinner.text if hasattr(self, 'ids') and 'mode_spinner' in self.ids else self.generation_mode
            
            if not lyrics_path or not Path(lyrics_path).exists():
                self._notify("Please select a valid lyrics file")
                return

            with open(lyrics_path, "r", encoding="utf-8") as f:
                lyrics_text = f.read()

            # Create and show progress dialog
            progress_dialog = ProgressDialog()
            progress_dialog.open()
            progress_dialog.start_progress_tracking(duration)
            
            # Submit Celery task
            try:
                task = celery_app.send_task(
                    'bestewk.generate_music',
                    kwargs={
                        'lyrics_text': lyrics_text,
                        'style_text': style_text,
                        'duration': duration,
                        'rvc_model_path': rvc_model_path,
                        'mode': generation_mode,
                    },
                )
                
                # Start monitoring the task
                progress_dialog.start_celery_task_monitoring(task.id)
                logger.info(f"Submitted music generation task {task.id} to generate_music queue")
                
            except Exception as e:
                logger.error(f"Error submitting Celery task: {e}")
                self._notify(f"Error starting task: {e}")
                progress_dialog.dismiss()
                return

        def _notify(self, msg: str):
            """Show notification popup."""
            if Popup is None or Builder is None:
                return
            Popup(title="Bestekar", content=Builder.load_string(f"Label:\n    text: '{msg}'"), size_hint=(0.6, 0.3)).open()
            
    class BestekarKivyApp(App):  # type: ignore
        """Kivy generation window application."""
        
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.title = "🎵 Bestekar - Turkish AI Composer"
            
        def build(self):
            """Build the Kivy application."""
            
            kv_layout = '''
<RootWidget>:
    orientation: 'vertical'
    padding: 20
    spacing: 15
    
    Label:
        text: '🎵 Bestekar - Turkish AI Song Generator'
        size_hint_y: None
        height: '40dp'
        font_size: '18sp'
        bold: True
        color: 0.2, 0.6, 1, 1
        
    GridLayout:
        cols: 2
        spacing: 10
        size_hint_y: None
        height: '250dp'
        
        Label:
            text: 'Generation Mode:'
            size_hint_x: 0.3
            text_size: self.size
            halign: 'left'
            valign: 'middle'
            
        Spinner:
            id: mode_spinner
            text: root.generation_mode
            values: ['Complete Song (RVC)', 'Instrumental Only']
            size_hint_x: 0.7
            on_text: root.generation_mode = self.text
            
        Label:
            text: 'Lyrics File:'
            size_hint_x: 0.3
            text_size: self.size
            halign: 'left'
            valign: 'middle'
            
        BoxLayout:
            size_hint_x: 0.7
            
            TextInput:
                id: lyrics_input
                text: root.lyrics_path
                hint_text: 'Select lyrics file (.txt)'
                multiline: False
                readonly: True
                
            Button:
                text: 'Browse'
                size_hint_x: None
                width: '80dp'
                on_release: root.open_filechooser()
                
        Label:
            text: 'RVC Model (Optional):'
            size_hint_x: 0.3
            text_size: self.size
            halign: 'left'
            valign: 'middle'
            
        BoxLayout:
            size_hint_x: 0.7
            
            TextInput:
                id: rvc_input
                text: root.rvc_model_path
                hint_text: 'Select RVC model (.pth) for voice synthesis'
                multiline: False
                readonly: True
                
            Button:
                text: 'Browse'
                size_hint_x: None
                width: '80dp'
                on_release: root.open_rvc_filechooser()
                
        Label:
            text: 'Style Description:'
            size_hint_x: 0.3
            text_size: self.size
            halign: 'left'
            valign: 'middle'
            
        TextInput:
            id: style_input
            text: root.style_text
            multiline: True
            size_hint_x: 0.7
            
        Label:
            text: 'Duration (seconds):'
            size_hint_x: 0.3
            text_size: self.size
            halign: 'left'
            valign: 'middle'
            
        BoxLayout:
            size_hint_x: 0.7
            
            Slider:
                id: duration_slider
                min: 10
                max: 300
                value: root.duration
                step: 5
                on_value: root.duration = int(self.value)
                
            Label:
                text: str(int(root.duration)) + 's'
                size_hint_x: None
                width: '50dp'
                
        Label:
            text: 'Instrumental Only:'
            size_hint_x: 0.3
            text_size: self.size
            halign: 'left'
            valign: 'middle'
            
        CheckBox:
            id: instrumental_check
            active: root.instrumental
            size_hint_x: 0.7
            on_active: root.instrumental = self.active
            
    BoxLayout:
        orientation: 'horizontal'
        size_hint_y: None
        height: '50dp'
        spacing: 10
        
        Button:
            text: '🎵 Generate Song'
            on_release: root.start_generation()
            
        Button:
            text: '🎤 RVC Generation'
            on_release: root.start_rvc_generation()
            
<ProgressDialog>:
    title: "🎵 Generating Music..."
    size_hint: 0.8, 0.7
    auto_dismiss: False
    
    BoxLayout:
        orientation: 'vertical'
        padding: 20
        spacing: 15
        
        Label:
            id: progress_label
            text: "Preparing generation..."
            size_hint_y: None
            height: '30dp'
            
        ProgressBar:
            id: progress_bar
            max: 100
            value: 0
            size_hint_y: None
            height: '20dp'
            
        Label:
            id: time_label
            text: "Estimated time: calculating..."
            size_hint_y: None
            height: '30dp'
            
        ScrollView:
            id: log_scroll
            
            TextInput:
                id: log_text
                text: ""
                readonly: True
                multiline: True
                size_hint_y: None
                text_size: self.width, None
                height: max(self.minimum_height, log_scroll.height)
                
        BoxLayout:
            orientation: 'horizontal'
            size_hint_y: None
            height: '40dp'
            spacing: 10
            
            Button:
                id: cancel_button
                text: "Cancel"
                on_release: root.cancel_generation()
                
            Button:
                id: close_button
                text: "Close"
                disabled: True
                on_release: root.dismiss()
'''
            
            try:
                if Builder:
                    Builder.load_string(kv_layout)
                else:
                    raise RuntimeError("Kivy Builder not available")
            except Exception as e:
                logger.error(f"Error loading Kivy layout: {e}")
                
            return RootWidget()
            
        def on_stop(self):
            """Called when the app stops."""
            try:
                logger.info("Kivy app stopping")
            except Exception:
                pass
                
    # Update global references
    globals()['ProgressDialog'] = ProgressDialog
    globals()['RootWidget'] = RootWidget  
    globals()['BestekarKivyApp'] = BestekarKivyApp
    
    return True

# Suppress common non-critical warnings
warnings.filterwarnings("ignore")

__version__ = "0.1.0"
__author__ = "Yilmaz Mustafa"
__email__ = "ymus@tuta.io"

# ---------- Logging Configuration ----------
from loguru import logger

def _configure_logging():
    """Configure loguru for console, file and optional JSON output."""
    logger.remove()

    # Log level can be overridden with BESTEKAR_LOG_LEVEL (default INFO)
    level = os.getenv("BESTEKAR_LOG_LEVEL", "INFO").upper()

    # Suppress common non-critical warnings
    import logging
    
    # Suppress FFmpeg warnings from torchaudio
    logging.getLogger("torchaudio._extension").setLevel(logging.ERROR)
    
    # Suppress xFormers warnings
    logging.getLogger("xformers").setLevel(logging.ERROR)
    
    # Suppress matplotlib debug messages
    logging.getLogger("matplotlib").setLevel(logging.WARNING)
    
    # Suppress PIL debug messages
    logging.getLogger("PIL").setLevel(logging.WARNING)

    # Console sink with filtering
    def message_filter(record):
        """Filter out known non-critical messages."""
        message = record["message"].lower()
        # Skip FFmpeg and xFormers warnings
        if any(keyword in message for keyword in ["ffmpeg", "xformers", "avutil", "cuda"]):
            return False
        return True

    logger.add(
        sys.stdout, 
        level=level, 
        colorize=True, 
        backtrace=False, 
        diagnose=False,
        filter=message_filter
    )

    # File sink (rotating) - keep all messages for debugging
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    logger.add(log_dir / "bestekar.log", rotation="100 MB", retention="10 days", level="DEBUG")

    # Optional JSON sink for monitoring
    if os.getenv("BESTEKAR_LOG_JSON", "0") in {"1", "true", "True"}:
        logger.add(sys.stdout, serialize=True, level=level, filter=message_filter)

_configure_logging()

# --------------------------------------------------
# System Resource Detection Functions
# --------------------------------------------------

def get_system_memory_gb() -> float:
    """Get total system RAM in GB with input validation."""
    try:
        import psutil
        # Get total physical memory in bytes, convert to GB
        total_memory_bytes = psutil.virtual_memory().total
        if total_memory_bytes <= 0:
            logger.warning("Invalid memory reading, defaulting to safe minimum")
            return 4.0  # Conservative fallback
        
        total_memory_gb = total_memory_bytes / (1024**3)
        # Validate reasonable range (1GB - 1TB)
        if not (1.0 <= total_memory_gb <= 1024.0):
            logger.warning(f"Unusual memory reading: {total_memory_gb}GB, defaulting to safe minimum")
            return 4.0
            
        logger.info(f"System RAM detected: {total_memory_gb:.1f}GB")
        return total_memory_gb
    except ImportError:
        logger.warning("psutil not available, defaulting to safe memory estimate")
        return 8.0  # Conservative default when psutil unavailable
    except Exception as e:
        logger.warning(f"Memory detection failed: {e}, using safe default")
        return 4.0  # Conservative fallback

def get_cpu_info() -> dict:
    """Get CPU information with secure validation."""
    try:
        import psutil
        cpu_info = {
            "cores": psutil.cpu_count(logical=False) or 1,  # Physical cores
            "threads": psutil.cpu_count(logical=True) or 1,  # Logical cores
            "frequency": 0.0  # Will try to get frequency safely
        }
        
        # Validate core counts
        if cpu_info["cores"] <= 0 or cpu_info["cores"] > 256:
            cpu_info["cores"] = 1  # Safe minimum
        if cpu_info["threads"] <= 0 or cpu_info["threads"] > 1024:
            cpu_info["threads"] = cpu_info["cores"]  # Fallback to physical cores
            
        # Try to get CPU frequency safely
        try:
            freq_info = psutil.cpu_freq()
            if freq_info and freq_info.max:
                cpu_info["frequency"] = freq_info.max / 1000.0  # Convert to GHz
                # Validate frequency range (0.5GHz - 10GHz)
                if not (0.5 <= cpu_info["frequency"] <= 10.0):
                    cpu_info["frequency"] = 0.0
        except (AttributeError, OSError):
            pass  # Frequency detection not available on all platforms
            
        logger.info(f"CPU detected: {cpu_info['cores']} cores, {cpu_info['threads']} threads")
        return cpu_info
    except ImportError:
        logger.warning("psutil not available for CPU detection")
        return {"cores": 2, "threads": 4, "frequency": 0.0}  # Conservative default
    except Exception as e:
        logger.warning(f"CPU detection failed: {e}")
        return {"cores": 1, "threads": 1, "frequency": 0.0}  # Safe minimum

def get_gpu_info() -> dict:
    """Get GPU information with error handling."""
    gpu_info = {
        "available": False,
        "memory_gb": 0.0,
        "name": "None",
        "compute_capability": None
    }
    
    try:
        if torch.cuda.is_available():
            gpu_count = torch.cuda.device_count()
            if gpu_count > 0:
                # Get primary GPU (device 0)
                gpu_info["available"] = True
                
                # Memory information with validation
                memory_bytes = torch.cuda.get_device_properties(0).total_memory
                if memory_bytes > 0:
                    gpu_info["memory_gb"] = memory_bytes / (1024**3)
                    # Validate GPU memory range (0.5GB - 128GB)
                    if not (0.5 <= gpu_info["memory_gb"] <= 128.0):
                        gpu_info["memory_gb"] = 0.0
                
                # GPU name with sanitization
                try:
                    raw_name = torch.cuda.get_device_name(0)
                    # Basic sanitization: only alphanumeric, spaces, and common GPU chars
                    import re
                    safe_name = re.sub(r'[^a-zA-Z0-9\s\-_().]', '', raw_name)[:64]
                    gpu_info["name"] = safe_name if safe_name else "Unknown GPU"
                except Exception:
                    gpu_info["name"] = "Unknown GPU"
                
                # Compute capability
                try:
                    props = torch.cuda.get_device_properties(0)
                    if hasattr(props, 'major') and hasattr(props, 'minor'):
                        gpu_info["compute_capability"] = f"{props.major}.{props.minor}"
                except Exception:
                    pass
                    
                logger.info(f"GPU detected: {gpu_info['name']} with {gpu_info['memory_gb']:.1f}GB VRAM")
            else:
                logger.info("CUDA available but no GPU devices found")
        else:
            logger.info("CUDA not available - using CPU mode")
    except Exception as e:
        logger.warning(f"GPU detection failed: {e}")
    
    return gpu_info

def choose_optimal_musicgen_model() -> str:
    """Choose the best MusicGen model based on system resources."""
    # Check for environment variable override (highest priority)
    env_model = os.getenv("BESTEKAR_MODEL")
    if env_model:
        # Validate and sanitize environment variable
        import re
        safe_model = re.sub(r'[^a-zA-Z0-9\-_/.]', '', env_model)[:64]
        if safe_model and "/" in safe_model:  # Must contain namespace
            logger.info(f"Using model from environment: {safe_model}")
            return safe_model
        else:
            logger.warning(f"Invalid BESTEKAR_MODEL environment variable: {env_model}")
    
    # Get system resources
    memory_gb = get_system_memory_gb()
    cpu_info = get_cpu_info()
    gpu_info = get_gpu_info()
    
    # Decision matrix based on resources
    model_requirements = {
        "facebook/musicgen-small": {"min_ram": 4, "min_cores": 1, "min_gpu_vram": 0},
        "facebook/musicgen-medium": {"min_ram": 8, "min_cores": 2, "min_gpu_vram": 0},
        "facebook/musicgen-large": {"min_ram": 12, "min_cores": 4, "min_gpu_vram": 0}
    }
    
    # Start with the highest quality model and work down
    for model in ["facebook/musicgen-large", "facebook/musicgen-medium", "facebook/musicgen-small"]:
        req = model_requirements[model]
        
        # Check RAM requirement
        if memory_gb < req["min_ram"]:
            continue
            
        # Check CPU cores
        if cpu_info["cores"] < req["min_cores"]:
            continue
            
        # GPU is optional but helpful for large models
        if model == "facebook/musicgen-large" and not gpu_info["available"]:
            # Large model on CPU requires more RAM
            if memory_gb < 16:
                continue
                
        logger.info(f"Selected model: {model} based on system resources")
        logger.info(f"System: {memory_gb:.1f}GB RAM, {cpu_info['cores']} cores, GPU: {gpu_info['available']}")
        return model
    
    # Fallback to small model if nothing else works
    logger.warning("System resources are very limited, using smallest model")
    return "facebook/musicgen-small"

def install_requirements():
    """Gerekli kütüphaneleri kontrol et ve yükle"""
    try:
        import audiocraft  # noqa: F401
        import torchaudio  # noqa: F401
        logger.debug("Gerekli kütüphaneler zaten yüklü")
        return True
    except ImportError:
        print("❌ audiocraft kütüphanesi bulunamadı!")
        print("Lütfen şu komutu çalıştırın: uv add audiocraft")
        return False

# --------------------------------------------------
# Generator abstraction
# --------------------------------------------------

class BaseSongGenerator(ABC):
    """Abstract base class for language-specific song generators."""

    @abstractmethod
    def setup_model(self) -> bool:  # pragma: no cover
        """Download / load model weights. Return True on success."""

    @abstractmethod
    def generate_song(
        self,
        lyrics: str,
        style: str,
        duration: int = 180,
        output_name: Optional[str] = None,
        instrumental: bool = False,
    ) -> Optional[str]:  # pragma: no cover
        """Generate a song file and return its path or None on error."""

# --------------------------------------------------
# Turkish implementation
# --------------------------------------------------

class TurkishSongGenerator(BaseSongGenerator):
    def __init__(self, model_name: Optional[str] = None):
        # System resource-aware model selection for optimal performance
        import platform

        if model_name is None:
            # Automatically choose the best model based on system resources
            model_name = choose_optimal_musicgen_model()
            logger.info(f"Auto-selected model based on system resources: {model_name}")
        elif "/" not in model_name:
            # Add facebook prefix if not provided
            model_name = f"facebook/musicgen-{model_name}"

        self.requested_model = model_name
        self.model: Any = None  # MusicGen instance
        
    def setup_model(self):
        """MusicGen modelini kurar"""
        if not install_requirements():
            return False
        try:
            # Suppress warnings during model loading
            import warnings
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=UserWarning)
                warnings.filterwarnings("ignore", message=".*xFormers.*")
                warnings.filterwarnings("ignore", message=".*FFmpeg.*")
                
                from audiocraft.models import MusicGen  # type: ignore
                logger.info("Model yüklemesi başlıyor", model=self.requested_model)
                
                # Show user-friendly message
                print(f"🔄 Loading {self.requested_model} model (this may take a few minutes)...")
                
                self.model = MusicGen.get_pretrained(self.requested_model)  # type: ignore
                self.model.set_generation_params(
                    duration=180,
                    temperature=1.0,
                    top_k=250,
                    top_p=0.0,
                    cfg_coef=3.0,
                    # Enable compression for better memory efficiency
                    use_sampling=True,
                    two_step_cfg=True
                )
                
            logger.success("Model başarıyla yüklendi", model=self.requested_model)
            print(f"✅ Model loaded successfully!")
            return True
        except Exception as e:
            logger.exception("Model yüklenirken hata", error=str(e))
            print(f"❌ Failed to load model: {str(e)}")
            return False
    
    def generate_song(self, lyrics, style="Turkish emotional pop ballad WITH FEMALE VOCALS, acoustic guitar, piano", duration=180, output_name=None, instrumental: bool = False):
        """Şarkı üretir"""
        if not self.model and not self.setup_model():
            return None
        
        try:
            from audiocraft.data.audio import audio_write
            
            # Enhanced vocal prompts for better vocal generation
            if instrumental:
                description = f"{style}, instrumental, no vocals, beautiful Turkish melody"
            else:
                # More specific vocal descriptions for better results
                vocal_keywords = [
                    "WITH CLEAR FEMALE VOCALS",
                    "singing in Turkish",
                    "expressive voice",
                    "melodic vocals",
                    "beautiful voice"
                ]
                
                # Add vocal keywords if not already present
                style_enhanced = style
                if not any(keyword.lower() in style.lower() for keyword in ["vocal", "sing", "voice"]):
                    style_enhanced += f", {vocal_keywords[0]}, {vocal_keywords[1]}"
                
                description = f"{style_enhanced}, beautiful Turkish melody with emotional singing"
            
            logger.info("Şarkı üretimi başladı", instrumental=instrumental, duration=duration)
            print(f"🎼 Şarkı üretiliyor...")
            print(f"📝 Sözler: {len(lyrics)} karakter")
            print(f"🎨 Stil: {description}")
            print(f"🎤 Enstrümantal: {'Evet' if instrumental else 'Hayır'}")
            print(f"⏱️  Süre: {duration} saniye")
            print(f"🔧 Model: {self.requested_model}")
            
            # Model recommendations based on auto-selected model
            if not instrumental and "small" in self.requested_model:
                print("🎵 Using small model - optimized for your system resources")
                print("💡 Tip: For better quality, consider upgrading RAM or using GPU acceleration")
            elif not instrumental and "medium" in self.requested_model:
                print("🎵 Using medium model - balanced quality and performance for your system")
                print("💡 Good balance of quality and resource usage")
            elif not instrumental and "large" in self.requested_model:
                print("🎯 Using LARGE model - your system has excellent resources!")
                print("🎤 Best vocal quality with optimal performance")
            
            # Dynamic parameters optimized for the selected model
            if not instrumental:
                # Adjust parameters based on model size for optimal performance
                if "large" in self.requested_model:
                    self.model.set_generation_params(
                        duration=duration,
                        temperature=1.1,  # Higher creativity for large model
                        top_k=300,  # More diverse sampling with large model
                        top_p=0.95,  # Better nucleus sampling for vocals
                        cfg_coef=5.0,  # Higher guidance for better prompt following
                        use_sampling=True,
                        two_step_cfg=True  # Better quality with large model
                    )
                else:
                    self.model.set_generation_params(
                        duration=duration,
                        temperature=1.0,  # Standard creativity for smaller models
                        top_k=250,  # Balanced sampling
                        top_p=0.9,  # Good nucleus sampling
                        cfg_coef=4.0,  # Balanced guidance
                        use_sampling=True,
                        two_step_cfg=True
                    )
            else:
                # Instrumental parameters adjusted for model size
                if "large" in self.requested_model:
                    self.model.set_generation_params(
                        duration=duration,
                        temperature=1.0,  # Balanced creativity for instrumental
                        top_k=300,
                        top_p=0.85,  # Good nucleus sampling for instrumental variety
                        cfg_coef=4.0,  # Optimized guidance for large model
                        use_sampling=True,
                        two_step_cfg=True
                    )
                else:
                    self.model.set_generation_params(
                        duration=duration,
                        temperature=0.9,  # Slightly lower for smaller models
                        top_k=250,
                        top_p=0.8,  # Conservative sampling
                        cfg_coef=3.5,  # Lower guidance for efficiency
                        use_sampling=True,
                        two_step_cfg=True
                    )
            
            if duration > 30:
                waveform = _safe_generate(self.model, description, duration, base_output=output_name or "musicgen_chunk")
            else:
                waveform = self.model.generate([description], progress=True)
            
            if output_name is None:
                output_name = f"bestekar_song_{hash(lyrics) % 10000}"
            
            audio_write(
                output_name, 
                waveform[0].cpu(), 
                self.model.sample_rate, 
                strategy="loudness"
            )
            
            output_file = f"{output_name}.wav"
            logger.success("Şarkı oluşturuldu", file=os.path.abspath(output_file))
            print(f"✅ Şarkı oluşturuldu: {output_file}")
            print(f"📁 Konum: {os.path.abspath(output_file)}")
            
            if not instrumental:
                print("⚠️  IMPORTANT: MusicGen creates vocal-like sounds but doesn't sing actual lyrics!")
                print("🎤 Generated vocals will be humming/wordless singing, not your text lyrics")
                print("💡 For actual lyric singing, consider:")
                print("   • Generate instrumental backing track (set instrumental=True)")
                print("   • Use AI singing tools like Suno AI, RVC, or SoVITS-SVC")
                print("   • Record vocals yourself over the backing track")
            else:
                print("🎼 Generating instrumental backing track - perfect for adding vocals later!")
            
            return output_file
            
        except Exception as e:
            logger.exception("Üretim sırasında hata", error=str(e))
            return None

# ---------------- Utility ----------------

def _safe_generate(
    model,
    description: str,
    duration: int,
    *,
    base_output: str = "musicgen_chunk",
    overlap: int = 5,
):
    """Generate audio safely by chunking into 30-second parts.

    MusicGen models are only trained for up-to-30 s generations.  Asking for
    much longer samples on CPU frequently leads to segfaults (observed on
    Windows).  This utility slices the request into max-30 s chunks and
    stitches them together with ``generate_continuation`` using *overlap*
    seconds of cross-fade to keep continuity.
    """

    # Guard: negative or zero durations would hang MusicGen internals.
    if duration <= 0:
        raise ValueError("Duration must be > 0 seconds")

    segment_max = 30  # hard limit for a single forward-pass

    model.set_generation_params(duration=min(duration, segment_max))

    # Generate first segment
    waveform = model.generate([description], progress=True)

    # Immediately persist first chunk to disk
    from audiocraft.data.audio import audio_write  # late import

    chunk_idx = 1
    chunk_path = f"{base_output}_part{chunk_idx:02d}.wav"
    audio_write(chunk_path, waveform[0].cpu(), model.sample_rate, strategy="loudness")
    logger.success("Chunk saved", file=os.path.abspath(chunk_path))

    total_generated = min(duration, segment_max)

    # Continue until requested length reached
    while total_generated < duration:
        logger.debug("Continuing generation", generated=total_generated)
        remaining = duration - total_generated

        next_len = min(remaining, segment_max)

        # Pick last *overlap* seconds from current audio to maintain coherence
        last_audio = waveform[:, :, -overlap * model.sample_rate :]
        model.set_generation_params(duration=next_len)
        cont = model.generate_continuation(last_audio, model.sample_rate, [description], progress=True)

        # Immediately persist continuation chunk before stitching (for recovery)
        chunk_idx += 1
        chunk_path = f"{base_output}_part{chunk_idx:02d}.wav"
        audio_write(chunk_path, cont[0].cpu(), model.sample_rate, strategy="loudness")
        logger.success("Chunk saved", file=os.path.abspath(chunk_path))

        # Stitch – drop the overlapped head from continuation to avoid duplicate
        waveform = torch.cat([waveform[:, :, : -overlap * model.sample_rate], cont], dim=2)
        total_generated += next_len

    return waveform

# ------------------------------------------------------------------
# RVC Setup Functions
# ------------------------------------------------------------------

def download_default_rvc_model():
    """Download a real Turkish RVC model if not exists."""
    try:
        import requests
    except ImportError:
        logger.warning("requests library not available, creating placeholder files")
        return _create_placeholder_rvc_model()
    
    from datetime import datetime
    
    models_dir = Path("rvc/models")
    indices_dir = Path("rvc/indices")
    models_dir.mkdir(parents=True, exist_ok=True)
    indices_dir.mkdir(parents=True, exist_ok=True)
    
    model_file = models_dir / "turkish_female.pth"
    index_file = indices_dir / "turkish_female.index"
    
    # If model already exists, don't download
    if model_file.exists() and index_file.exists():
        logger.info("RVC model already exists, skipping download")
        return str(model_file), str(index_file)
    
    try:
        logger.info("Downloading Turkish RVC model...")
        
        # Try multiple model sources for better reliability
        model_sources = [
            {
                "name": "TITAN Base Model",
                "model_url": "https://huggingface.co/blaise-tk/TITAN/resolve/main/G_48000.pth",
                "index_url": "https://huggingface.co/blaise-tk/TITAN/resolve/main/added_IVF256_Flat_nprobe_1.index"
            },
            {
                "name": "RVC Pretrained v2",
                "model_url": "https://huggingface.co/lj1995/VoiceConversionWebUI/resolve/main/pretrained_v2/G_48000.pth",
                "index_url": "https://huggingface.co/lj1995/VoiceConversionWebUI/resolve/main/pretrained_v2/added_IVF256_Flat_nprobe_1.index"
            }
        ]
        
        # Try each source until one works
        for source in model_sources:
            try:
                logger.info(f"Trying to download {source['name']}...")
                
                # Download model file
                logger.info("Downloading model file...")
                response = requests.get(source["model_url"], stream=True, timeout=60)
                response.raise_for_status()
                
                with open(model_file, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                # Download index file
                logger.info("Downloading index file...")
                response = requests.get(source["index_url"], stream=True, timeout=60)
                response.raise_for_status()
                
                with open(index_file, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                logger.success(f"RVC model downloaded successfully from {source['name']}")
                return str(model_file), str(index_file)
                
            except Exception as e:
                logger.warning(f"Failed to download from {source['name']}: {e}")
                # Clean up partial files
                if model_file.exists():
                    model_file.unlink()
                if index_file.exists():
                    index_file.unlink()
                continue
        
        # If all sources failed, create placeholder
        raise Exception("All download sources failed")
        
    except Exception as e:
        logger.warning(f"Failed to download RVC model: {e}")
        return _create_placeholder_rvc_model()

def _create_placeholder_rvc_model():
    """Create placeholder RVC model files."""
    from datetime import datetime
    
    models_dir = Path("rvc/models")
    indices_dir = Path("rvc/indices")
    models_dir.mkdir(parents=True, exist_ok=True)
    indices_dir.mkdir(parents=True, exist_ok=True)
    
    model_file = models_dir / "turkish_female.pth"
    index_file = indices_dir / "turkish_female.index"
    
    logger.info("Creating placeholder model files...")
    
    # Create placeholder files if download fails
    with open(model_file, 'w') as f:
        f.write("# Placeholder Turkish RVC model\n")
        f.write("# Replace this with a real .pth model file\n")
        f.write("# Download from: https://huggingface.co/models?search=rvc\n")
        f.write("# Recommended sources:\n")
        f.write("#   - https://huggingface.co/blaise-tk/TITAN\n")
        f.write("#   - https://huggingface.co/lj1995/VoiceConversionWebUI\n")
        f.write("#   - Train your own with RVC-WebUI\n")
        f.write(f"# Created: {datetime.now()}\n")
    
    with open(index_file, 'w') as f:
        f.write("# Placeholder Turkish RVC index\n")
        f.write("# Replace this with a real .index file\n")
        f.write("# This file should be generated alongside the .pth model\n")
        f.write("# Use RVC-WebUI or similar tools to create proper index files\n")
        f.write(f"# Created: {datetime.now()}\n")
    
    logger.info("Placeholder model files created")
    return str(model_file), str(index_file)

def get_default_rvc_model():
    """Get the default RVC model, downloading if necessary."""
    models_dir = Path("rvc/models")
    indices_dir = Path("rvc/indices")
    
    # Look for existing models
    model_files = list(models_dir.glob("*.pth")) if models_dir.exists() else []
    index_files = list(indices_dir.glob("*.index")) if indices_dir.exists() else []
    
    if model_files and index_files:
        # Use the first available model
        model_file = model_files[0]
        # Try to find matching index file
        model_name = model_file.stem
        matching_index = indices_dir / f"{model_name}.index"
        
        if matching_index.exists():
            return str(model_file), str(matching_index)
        else:
            # Use any available index file
            return str(model_file), str(index_files[0])
    
    # No models found, download default
    logger.info("No RVC models found, downloading default model...")
    return download_default_rvc_model()

def setup_rvc_integration():
    """Set up RVC integration with real model downloading."""
    logger.info("Setting up RVC integration...")
    
    # Create RVC directory structure
    rvc_dir = Path("rvc")
    models_dir = rvc_dir / "models"
    indices_dir = rvc_dir / "indices"
    
    rvc_dir.mkdir(exist_ok=True)
    models_dir.mkdir(exist_ok=True)
    indices_dir.mkdir(exist_ok=True)
    
    # Create README with instructions
    readme_path = rvc_dir / "README.md"
    readme_content = """# RVC Models Directory

This directory contains RVC (Retrieval-based Voice Conversion) models for Turkish singing voice generation.

## Structure
- `models/` - Contains .pth model files
- `indices/` - Contains .index feature files

## Default Model
The application will automatically download a default Turkish female voice model if none exists.

## Adding Custom Models
1. Place your .pth model files in the `models/` directory
2. Place corresponding .index files in the `indices/` directory
3. Ensure file names match (e.g., `singer.pth` and `singer.index`)

## Model Sources
- Hugging Face: https://huggingface.co/models?search=rvc
- RVC Community: Various Discord servers and GitHub repositories
- Train your own: Use RVC-WebUI to train custom models

## Supported Formats
- Models: .pth files (PyTorch checkpoints)
- Indices: .index files (FAISS indices for retrieval)

## Note
The default model is a general-purpose Turkish voice model.
For best results with Turkish songs, consider using models trained specifically on Turkish singers.
"""
    
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme_content)
    
    # Download default model if no models exist
    model_files = list(models_dir.glob("*.pth"))
    if not model_files:
        logger.info("No RVC models found, downloading default...")
        download_default_rvc_model()
    
    logger.success("RVC integration setup complete")

# RVC Integration for Local AI Singing
try:
    import edge_tts
    import asyncio
    import tempfile
    import subprocess
    from pathlib import Path
    import soundfile as sf
    import librosa
    RVC_AVAILABLE = True
except ImportError:
    RVC_AVAILABLE = False

class RVCSinger:
    """Turkish RVC Singer for converting TTS to singing voice."""

    def __init__(self, rvc_model_path: Optional[str] = None, index_path: Optional[str] = None):
        # If no model specified, try to use default model
        if rvc_model_path is None:
            rvc_model_path, index_path = get_default_rvc_model()
        
        self.rvc_model_path = rvc_model_path
        self.index_path = index_path
        self.rvc_loaded = False
        
        # Ensure RVC directory structure exists
        models_dir = Path("rvc")
        models_dir.mkdir(exist_ok=True)
        (models_dir / "models").mkdir(exist_ok=True)
        (models_dir / "indices").mkdir(exist_ok=True)

    def setup_rvc_environment(self):
        """Setup RVC environment and dependencies (managed by uv)."""
        if not self.rvc_loaded:
            logger.warning("RVC dependencies not available. Install with: uv sync")
            return False
            
        # Check if RVC is installed (managed by uv via pyproject.toml)
        try:
            import rvc_python  # RVC Python wrapper
            return True
        except ImportError:
            logger.warning("RVC Python wrapper not found - install with: uv sync")
            logger.info("Dependencies are managed in pyproject.toml")
            return False
    
    async def text_to_speech(self, text: str, voice: str = "tr-TR-EmelNeural", output_path: str = "temp_tts.wav") -> str:
        """Convert text to speech using Edge TTS."""
        try:
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(output_path)
            return output_path
        except Exception as e:
            logger.exception("TTS generation failed", error=str(e))
            return None
    
    def convert_voice_with_rvc(self, input_audio: str, output_audio: str, f0_method: str = "harvest") -> bool:
        """Convert voice using RVC model."""
        if not self.rvc_model_path or not Path(self.rvc_model_path).exists():
            logger.error("RVC model not found", path=self.rvc_model_path)
            return False
            
        try:
            import rvc_python
            
            # Load RVC model
            rvc = rvc_python.RVC(
                model_path=self.rvc_model_path,
                index_path=self.index_path,
                device="cpu"  # Use CPU for compatibility
            )
            
            # Convert voice
            rvc.convert(
                input_path=input_audio,
                output_path=output_audio,
                f0_method=f0_method,
                f0_up_key=0,  # Pitch adjustment
                filter_radius=3,
                index_rate=0.75,
                volume_envelope=1.0,
                protect=0.33
            )
            
            return Path(output_audio).exists()
            
        except Exception as e:
            logger.exception("RVC conversion failed", error=str(e))
            return False
    
    async def generate_singing_voice(self, lyrics: str, output_path: str, voice: str = "tr-TR-EmelNeural") -> Optional[str]:
        """Generate singing voice from lyrics using TTS + RVC pipeline."""
        if not self.setup_rvc_environment():
            return None
            
        try:
            # Step 1: Generate TTS
            temp_tts = tempfile.mktemp(suffix=".wav")
            tts_result = await self.text_to_speech(lyrics, voice, temp_tts)
            
            if not tts_result:
                return None
            
            # Step 2: Convert with RVC if model available
            if self.rvc_model_path:
                rvc_success = self.convert_voice_with_rvc(temp_tts, output_path)
                if rvc_success:
                    # Cleanup temp file
                    try:
                        os.unlink(temp_tts)
                    except:
                        pass
                    return output_path
            
            # Fallback: Use original TTS
            import shutil
            shutil.move(temp_tts, output_path)
            return output_path
            
        except Exception as e:
            logger.exception("Singing voice generation failed", error=str(e))
            return None

# Enhanced Song Generator with RVC Integration
class TurkishSongGeneratorWithRVC(TurkishSongGenerator):
    """Turkish song generator with integrated RVC singing."""
    
    def __init__(self, model_name: Optional[str] = None, rvc_model_path: Optional[str] = None, rvc_index_path: Optional[str] = None):
        super().__init__(model_name)
        self.rvc_singer = RVCSinger(rvc_model_path, rvc_index_path)
        
    async def generate_complete_song(self, lyrics: str, style: str = "Turkish emotional pop ballad", duration: int = 180, output_name: str = None, add_vocals: bool = True) -> Optional[str]:
        """Generate complete song with backing track and vocals."""
        
        try:
            print("🎵 Starting complete song generation pipeline...")
            print(f"📝 Lyrics: {len(lyrics)} characters")
            print(f"🎤 Add vocals: {'Yes' if add_vocals else 'No (instrumental only)'}")
            
            # Step 1: Generate instrumental backing track
            print("🎼 Step 1: Generating instrumental backing track...")
            instrumental_file = self.generate_song(
                lyrics=lyrics,
                style=style,
                duration=duration,
                output_name=f"{output_name}_instrumental" if output_name else None,
                instrumental=True
            )
            
            if not instrumental_file:
                print("❌ Failed to generate instrumental track")
                return None
                
            print(f"✅ Instrumental track ready: {instrumental_file}")
            
            if not add_vocals:
                return instrumental_file
            
            # Step 2: Generate singing vocals
            print("🎤 Step 2: Generating singing vocals with RVC...")
            vocal_file = f"{output_name}_vocals.wav" if output_name else "bestekar_vocals.wav"
            
            vocal_result = await self.rvc_singer.generate_singing_voice(lyrics, vocal_file)
            
            if not vocal_result:
                print("⚠️  Vocal generation failed, returning instrumental only")
                return instrumental_file
                
            print(f"✅ Vocals ready: {vocal_result}")
            
            # Step 3: Mix vocals with instrumental
            print("🎚️  Step 3: Mixing vocals with instrumental...")
            final_file = await self.mix_audio_tracks(instrumental_file, vocal_result, output_name)
            
            if final_file:
                print(f"🎉 Complete song ready: {final_file}")
                return final_file
            else:
                print("⚠️  Mixing failed, returning instrumental")
                return instrumental_file
                
        except Exception as e:
            logger.exception("Complete song generation failed", error=str(e))
            return None
    
    async def mix_audio_tracks(self, instrumental_path: str, vocal_path: str, output_name: str = None) -> Optional[str]:
        """Mix instrumental and vocal tracks."""
        try:
            import librosa
            import soundfile as sf
            import numpy as np
            
            # Load audio files
            instrumental, sr1 = librosa.load(instrumental_path, sr=None)
            vocals, sr2 = librosa.load(vocal_path, sr=None)
            
            # Ensure same sample rate
            if sr1 != sr2:
                vocals = librosa.resample(vocals, orig_sr=sr2, target_sr=sr1)
                sr2 = sr1
            
            # Ensure same length (pad shorter one or trim longer one)
            min_length = min(len(instrumental), len(vocals))
            instrumental = instrumental[:min_length]
            vocals = vocals[:min_length]
            
            # Mix with appropriate levels
            # Reduce instrumental volume slightly to make room for vocals
            mixed = (instrumental * 0.7) + (vocals * 0.8)
            
            # Normalize to prevent clipping
            mixed = mixed / np.max(np.abs(mixed)) * 0.95
            
            # Save mixed audio
            output_file = f"{output_name}_complete.wav" if output_name else "bestekar_complete_song.wav"
            sf.write(output_file, mixed, sr1)
            
            return output_file
            
        except Exception as e:
            logger.exception("Audio mixing failed", error=str(e))
            return None

def main():
    """Main entry point - launches system tray application."""
    
    # Load Kivy components for GUI functionality
    if not _load_kivy_for_gui():
        print("❌ Failed to load GUI components")
        sys.exit(1)

    # ------------------------------------------------------------------
    # Minimum disk-space guard (model + temp wavs require ~2 GB)
    # ------------------------------------------------------------------

    def _check_disk_space(min_gb: int = 5) -> None:
        """Exit if the drive holding the current working directory has
        less than *min_gb* gigabytes free.
        Increased requirement for large model optimization.
        """

        total, used, free = shutil.disk_usage(os.getcwd())
        free_gb = free / (1024 ** 3)
        if free_gb < min_gb:
            logger.error(
                "Not enough disk space", required=f"{min_gb} GB", available=f"{free_gb:.1f} GB"
            )
            print(
                f"❌ Bestekar needs at least {min_gb} GB free storage for model downloads and output."
                " Please free up space and try again."
            )
            sys.exit(2)

    _check_disk_space()

    # Optimize threading for detected system
    cpu_info = get_cpu_info()
    thread_count = str(min(cpu_info["threads"], 16))  # Cap at 16 threads for stability
    os.environ["OMP_NUM_THREADS"] = thread_count
    os.environ["MKL_NUM_THREADS"] = thread_count
    os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "max_split_size_mb:512"  # Better memory management

    logger.info("🎵 Bestekar - Turkish AI Composer")
    logger.info("Starting system tray...")
    
    # Inform user about optimization and potential warnings
    print("🎵 Bestekar - Turkish AI Composer with Smart Resource Detection")
    print("🚀 Automatically optimizes model selection based on your system resources")
    print("🎯 Dynamic model selection: small/medium/large based on available RAM/CPU/GPU")
    print("📌 Note: You may see some technical warnings about FFmpeg or xFormers.")
    print("   These are normal and don't affect functionality.")
    
    # ------------------------------------------------------------------
    # Launch RVC/model setup in background (keeps UI responsive)
    # ------------------------------------------------------------------

    try:
        celery_app.send_task('bestewk.app_init')
        logger.info("Submitted app_init task to ui_actions queue")
    except Exception as e:
        # Fallback: run synchronously if Celery broker not available
        logger.warning(f"Celery not available – running setup inline: {e}")
        setup_rvc_integration()

    print("🔧 System tray started. Right-click the tray icon to generate songs.")

    # Global variables for thread management
    generation_app = None
    active_threads = []
    # Thread-safe queue for scheduling GUI actions from background threads
    import queue
    task_queue: "queue.Queue[str]" = queue.Queue()

    def cleanup_threads():
        """Kill all active threads before exit."""
        import threading
        logger.info("Cleaning up threads...")
        
        # Stop Kivy app if running
        if generation_app:
            try:
                if hasattr(generation_app, 'stop'):
                    generation_app.stop()
                if hasattr(generation_app, '_app_window') and generation_app._app_window:
                    generation_app._app_window.close()
            except Exception as e:
                logger.debug(f"Error stopping Kivy app: {e}")
        
        # Force stop any Kivy instances that might be running
        try:
            from kivy.app import App
            # Stop all running Kivy apps
            running_app = App.get_running_app()
            if running_app:
                try:
                    running_app.stop()
                except:
                    pass
        except ImportError:
            pass
        
        # Wait for active threads to finish
        for thread in active_threads:
            if thread.is_alive():
                logger.debug(f"Waiting for thread {thread.name} to finish...")
                thread.join(timeout=1.0)
                if thread.is_alive():
                    logger.warning(f"Thread {thread.name} did not finish gracefully")
        
        # Clear thread list
        active_threads.clear()

    def on_generate(icon, item):
        """Open Kivy generation window."""
        nonlocal generation_app
        
        try:
            # Ensure Kivy is loaded for GUI functionality
            if not _load_kivy_for_gui():
                logger.error("Failed to load Kivy for GUI")
                if hasattr(icon, 'notify'):
                    icon.notify("Bestekar", "Failed to load GUI components")
                return
                
            import platform, threading

            # On Windows the Kivy UI must run on the main thread. If we're not on
            # the main thread, enqueue the request so the main-thread loop can
            # launch the GUI safely. Otherwise run it directly.
            if platform.system() == "Windows" and threading.current_thread().name != "MainThread":
                task_queue.put("generate")
            else:
                generation_app = BestekarKivyApp()
                generation_app.run()
            
        except Exception as e:
            logger.exception("Error opening generation window", error=str(e))
            if hasattr(icon, 'notify'):
                icon.notify("Bestekar", "Failed to open generation window")

    def on_help(icon, item):
        """Open help in web browser using Celery task."""
        try:
            task = celery_app.send_task('bestewk.open_help')
            logger.info(f"Submitted help task {task.id} to ui_actions queue")
        except Exception as e:
            logger.error(f"Error submitting help task: {e}")
            # Fallback to direct execution
            import webbrowser
            webbrowser.open("https://github.com/codesapien/bestekar")

    def on_exit(icon, item):
        """Exit application and cleanup threads using Celery task."""
        logger.info("Uygulama kapatılıyor")
        print("👋 Bestekar kapatılıyor...")
        
        try:
            # Submit exit task
            task = celery_app.send_task('bestewk.exit_app')
            logger.info(f"Submitted exit task {task.id} to ui_actions queue")
            
            # Wait briefly for task to start
            import time
            time.sleep(0.5)
            
        except Exception as e:
            logger.error(f"Error submitting exit task: {e}")
        
        try:
            # Cleanup regardless of Celery
            cleanup_threads()
            
            # Hide and stop icon
            icon.visible = False
            icon.stop()
            
            # Give processes time to clean up
            import time
            time.sleep(0.3)
            
        except Exception as e:
            logger.error(f"Exit cleanup error: {e}")
        finally:
            print("✅ Uygulama kapatıldı")
            # Force exit to ensure clean shutdown
            import os
            os._exit(0)

    def on_view_tasks(icon, item):
        """View all tasks in the generate_music group."""
        try:
            tasks = get_active_generation_tasks()
            if tasks:
                print("\n📋 Active Music Generation Tasks:")
                print("=" * 50)
                for task in tasks:
                    print(f"Task ID: {task['id']}")
                    print(f"State: {task['state']}")
                    print(f"Worker: {task.get('worker', 'Unknown')}")
                    if 'eta' in task:
                        print(f"ETA: {task['eta']}")
                    print("-" * 30)
                logger.info(f"Found {len(tasks)} active music generation tasks")
            else:
                print("📋 No active music generation tasks found")
                logger.info("No active music generation tasks")
                
            if hasattr(icon, 'notify'):
                icon.notify("Bestekar", f"Found {len(tasks)} active music generation tasks")
                
        except Exception as e:
            logger.error(f"Error viewing tasks: {e}")
            print(f"❌ Error viewing tasks: {e}")
            if hasattr(icon, 'notify'):
                icon.notify("Bestekar", "Error viewing tasks")

    # Create tray icon menu
    tray_menu = pystray.Menu(
        pystray.MenuItem("Generate Song", on_generate),
        pystray.MenuItem("View Music Tasks", on_view_tasks),
        pystray.MenuItem("Help", on_help),
        pystray.MenuItem("Exit", on_exit),
    )

    # ------------------------------------------------------------------
    # Create tray icon with SVG to PNG conversion
    # ------------------------------------------------------------------

    def _svg_to_icon(svg_str: str):
        """Convert SVG string to PIL Image for tray icon."""
        try:
            import cairosvg  # type: ignore
            from io import BytesIO

            png_bytes = cairosvg.svg2png(bytestring=svg_str.encode(), output_width=64, output_height=64)
            if png_bytes:
                return Image.open(BytesIO(png_bytes))
            else:
                raise ValueError("Failed to convert SVG to PNG")
        except Exception:
            # Fallback: create simple colored square
            color = (50, 150, 250) if "note" in svg_str else (255, 200, 0)
            img = Image.new("RGB", (16, 16), color=color)
            return img

    note_svg = """
<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'>
  <rect width='64' height='64' rx='8' ry='8' fill='white'/>
  <path d='M44 10v28.7c-2.1-1-4.6-1.7-7.3-1.7-8 0-14.7 4.5-14.7 10s6.7 10 14.7 10 14.7-4.5 14.7-10V22h10V10H44z' fill='black'/>
</svg>"""

    tray_icon = _svg_to_icon(note_svg)
    icon = pystray.Icon("Bestekar", tray_icon, "Bestekar - AI Music Composer", tray_menu)

    logger.info("System tray started. Right-click to generate songs.")

    # ------------------------------------------------------------------
    # Platform-specific tray execution with thread safety
    # ------------------------------------------------------------------
    
    import platform, threading, time

    def _run_icon():
        """Run the tray icon."""
        try:
            icon.run()
        except Exception as e:
            logger.exception("Tray icon error", error=str(e))

    if platform.system() == "Windows":
        # Windows: Run tray in separate thread to avoid GIL issues
        tray_thread = threading.Thread(target=_run_icon, name="SystemTray", daemon=False)
        tray_thread.start()
        active_threads.append(tray_thread)
        
        try:
            import queue as _queue  # alias to avoid shadowing
            while tray_thread.is_alive():
                try:
                    task = task_queue.get(timeout=0.5)
                except _queue.Empty:
                    task = None

                if task == "generate":
                    generation_app = BestekarKivyApp()
                    generation_app.run()
                time.sleep(0.5)
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
            cleanup_threads()
            icon.stop()
            tray_thread.join(timeout=2.0)
    else:
        # Linux/macOS: Direct execution
        try:
            _run_icon()
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
            cleanup_threads()

    return 0

if __name__ == "__main__":
    sys.exit(main())

