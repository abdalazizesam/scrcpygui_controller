import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
import sys
import os
import json
import atexit

# A modern theme for tkinter is used.
# You must install it first: pip install sv-ttk
try:
    import sv_ttk
except ImportError:
    messagebox.showerror(
        "Dependency Missing",
        "The 'sv-ttk' library is not installed.\nPlease install it using: pip install sv-ttk"
    )
    sys.exit(1)


class ScrollableFrame(ttk.Frame):
    """A scrollable frame widget that can contain other widgets."""
    
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        
        # Create canvas and scrollbar
        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        
        # Configure canvas scrolling
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        # Create window in canvas
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        
        # Configure canvas to update scrollable frame width
        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfig(self.canvas_window, width=e.width)
        )
        
        # Configure scrollbar
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        # Pack canvas and scrollbar
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        
        # Bind mouse wheel to canvas
        self.bind_mousewheel()
    
    def bind_mousewheel(self):
        """Bind mouse wheel events to the canvas."""
        def _on_mousewheel(event):
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        
        def _bind_to_mousewheel(event):
            self.canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        def _unbind_from_mousewheel(event):
            self.canvas.unbind_all("<MouseWheel>")
        
        # Bind mouse wheel when mouse enters the widget
        self.canvas.bind('<Enter>', _bind_to_mousewheel)
        self.canvas.bind('<Leave>', _unbind_from_mousewheel)


class ScrcpyController(tk.Tk):
    """
    A Tkinter-based GUI for scrcpy with a modern theme, providing an
    intuitive interface for basic and advanced command-line options.
    """

    # --- Constants for configuration and UI elements ---
    CONSTANTS = {
        "font_family": "Segoe UI",
        "font_size": 10,
        "header_font_size": 16,
        "accent_button_font_size": 11,
        "info_label_color": "gray",
        "command_font": ("Courier New", 9),
        "max_size_options": ["Device Native", "1920", "1280", "1080", "720"],
        "video_codec_options": ["Default", "h264", "h265", "av1"],
        "audio_codec_options": ["Default", "opus", "aac", "flac", "raw"],
        "audio_bit_rate_options": ["64", "96", "128", "192", "256"],
        "camera_facing_options": ["back", "front"],
        "camera_size_options": ["Default", "1920x1080", "1280x720", "640x480"],
        "camera_orientation_options": ["Default", "0°", "90°", "180°", "270°"],
        "default_bit_rate": 8,
        "default_max_fps": 60,
        "default_max_size": "1080",
        "default_audio_bit_rate": "128",
        "default_video_buffer_ms": 0,
    }

    def __init__(self):
        super().__init__()

        self.settings_file = os.path.join(os.path.expanduser("~"), ".scrcpy_gui_settings.json")
        self._initialize_variables()
        self.load_settings()

        self._configure_window()
        self._setup_styles()
        self._create_widgets()

        self._update_ui_from_loaded_settings()

        atexit.register(self.save_settings)

    def _configure_window(self):
        """Sets up the main window properties."""
        self.title("Scrcpy GUI Controller")
        self.geometry("610x1000")
        self.minsize(500, 400)  # Reduced minimum height since we now have scrolling
        self.resizable(True, True)  # Allow resizing in both directions

        # --- Cross-Platform Icon Handling ---
        try:
            # For .png, works on Windows, macOS, Linux
            icon_path = "assets/icon.png"
            if os.path.exists(icon_path):
                self.icon = tk.PhotoImage(file=icon_path)
                self.iconphoto(True, self.icon)
            else:
                # Fallback for .ico on Windows if .png is not found
                icon_path_ico = "assets/icon.ico"
                if os.path.exists(icon_path_ico):
                    self.iconbitmap(icon_path_ico)
        except Exception as e:
            print(f"Error setting icon: {e}")
            # The app will still run, just with a default icon.


    def _create_fullscreen_options_frame(self, master):
        """Frame for fullscreen behavior options."""
        frame = ttk.LabelFrame(master, text="Fullscreen Options", padding="10")
        frame.pack(fill="x", expand=True, pady=10)
        
        # Add fullscreen exit method selection
        self.fullscreen_exit_method = tk.StringVar(value="ESC Key")
        
        ttk.Label(frame, text="Exit Fullscreen Method:").grid(row=0, column=0, sticky="w", padx=5)
        
        exit_methods = ["ESC Key", "Alt+Tab", "Windows Key", "Custom Hotkey", "All Methods"]
        exit_combo = ttk.Combobox(frame, textvariable=self.fullscreen_exit_method, 
                                values=exit_methods, state="readonly", width=15)
        exit_combo.grid(row=0, column=1, sticky="w", padx=5)
        
        # Add option to show exit instructions
        self.show_fullscreen_help = tk.BooleanVar(value=True)
        ttk.Checkbutton(frame, text="Show fullscreen exit instructions", 
                    variable=self.show_fullscreen_help, 
                    style="Switch.TCheckbutton").grid(row=1, column=0, columnspan=2, sticky="w", padx=5, pady=5)
        
        # Add always on top option when not fullscreen
        self.windowed_on_top = tk.BooleanVar()
        ttk.Checkbutton(frame, text="Keep window on top when not fullscreen", 
                    variable=self.windowed_on_top, 
                    style="Switch.TCheckbutton").grid(row=2, column=0, columnspan=2, sticky="w", padx=5, pady=5)


    def _initialize_variables(self):
        """Initializes all Tkinter variables with default values."""
        self.dark_mode = tk.BooleanVar(value=True)
        self.scrcpy_path = tk.StringVar()
        self.generated_command = tk.StringVar(value="Please select the scrcpy executable...")

        # Basic settings
        self.bit_rate = tk.IntVar(value=self.CONSTANTS["default_bit_rate"])
        self.max_fps = tk.IntVar(value=self.CONSTANTS["default_max_fps"])
        self.max_size = tk.StringVar(value=self.CONSTANTS["default_max_size"])
        self.fullscreen = tk.BooleanVar()
        self.always_on_top = tk.BooleanVar()
        self.show_touches = tk.BooleanVar()
        self.turn_screen_off = tk.BooleanVar()
        self.stay_awake = tk.BooleanVar()
        self.audio_forward = tk.BooleanVar(value=True)
        self.record_screen = tk.BooleanVar()
        self.record_file_path = tk.StringVar()

        # Camera settings
        self.mirror_camera = tk.BooleanVar()
        self.camera_facing = tk.StringVar(value="back")
        self.camera_size = tk.StringVar(value="Default")
        self.camera_orientation = tk.StringVar(value="Default")

        # Advanced settings
        self.video_codec = tk.StringVar(value="Default")
        self.audio_codec = tk.StringVar(value="Default")
        self.video_buffer = tk.IntVar(value=self.CONSTANTS["default_video_buffer_ms"])
        self.v4l2_sink_path = tk.StringVar()
        self.audio_bit_rate = tk.StringVar(value=self.CONSTANTS["default_audio_bit_rate"])

    def _setup_styles(self):
        """Configures ttk styles for the application."""
        style = ttk.Style(self)
        default_font = self.CONSTANTS["font_family"]
        font_size = self.CONSTANTS["font_size"]
        try:
            self.tk.call("font", "create", "AppDefaultFont", "-family", default_font, "-size", font_size)
            self.tk.call("font", "create", "AppBoldFont", "-family", default_font, "-size", font_size, "-weight", "bold")
            style.configure(".", font="AppDefaultFont")
        except tk.TclError:
            # Fallback font if Segoe UI is not available
            style.configure(".", font=("Calibri", font_size))

        style.configure("TLabel", padding=5)
        style.configure("TButton", padding=5)
        style.configure("TEntry", padding=5)
        style.configure("TCombobox", padding=5)
        style.configure("Header.TLabel", font=(default_font, self.CONSTANTS["header_font_size"], "bold"))
        style.configure("Accent.TButton", font=(default_font, self.CONSTANTS["accent_button_font_size"], "bold"))
        style.configure("Info.TLabel", foreground=self.CONSTANTS["info_label_color"])

    def _create_widgets(self):
        """Creates and arranges all GUI elements in the window."""
        # Create main container
        container = ttk.Frame(self)
        container.pack(fill="both", expand=True)
        
        # Create scrollable frame
        self.scrollable_frame = ScrollableFrame(container)
        self.scrollable_frame.pack(fill="both", expand=True)
        
        # Create main content frame inside scrollable frame
        main_frame = ttk.Frame(self.scrollable_frame.scrollable_frame, padding="20")
        main_frame.pack(expand=True, fill="both")

        self._create_header(main_frame)
        self._create_path_selector(main_frame)
        self._create_notebook_tabs(main_frame)
        self._create_command_display(main_frame)
        self._create_connect_button(main_frame)
        self._bind_variables_to_command_update()

    def _create_header(self, master):
        """Creates the header with the title and theme toggle."""
        header_frame = ttk.Frame(master)
        header_frame.pack(fill="x", pady=(0, 15))
        header_frame.grid_columnconfigure(0, weight=1)

        ttk.Label(header_frame, text="Scrcpy Controller", style="Header.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(
            header_frame, text="Dark Mode", variable=self.dark_mode, style="Switch.TCheckbutton", command=self._toggle_theme
        ).grid(row=0, column=1, sticky="e")

    def _create_path_selector(self, master):
        """Creates the scrcpy executable path selection widgets."""
        path_frame = ttk.LabelFrame(master, text="1. Scrcpy Executable Path", padding="10")
        path_frame.pack(fill="x", pady=(0, 15))
        path_frame.grid_columnconfigure(0, weight=1)

        ttk.Entry(path_frame, textvariable=self.scrcpy_path, state="readonly").grid(row=0, column=0, sticky="ew", padx=(0, 10))
        ttk.Button(path_frame, text="Browse...", command=self._browse_for_scrcpy).grid(row=0, column=1, sticky="e")

    def _create_notebook_tabs(self, master):
        """Creates the notebook for settings tabs."""
        notebook = ttk.Notebook(master)
        notebook.pack(expand=True, fill="both", pady=5)

        basic_tab = ttk.Frame(notebook, padding="15")
        advanced_tab = ttk.Frame(notebook, padding="15")

        notebook.add(basic_tab, text=" Basic Settings ")
        notebook.add(advanced_tab, text=" Advanced Settings ")

        self._create_basic_settings_tab(basic_tab)
        self._create_advanced_settings_tab(advanced_tab)

    def _create_basic_settings_tab(self, master):
        """Creates the content for the 'Basic Settings' tab."""
        master.grid_columnconfigure(1, weight=1)
        self._create_video_display_frame(master)
        self._create_general_options_frame(master)
        self._create_recording_camera_frame(master)

    def _create_video_display_frame(self, master):
        """Frame for video bit rate, FPS, and resolution."""
        frame = ttk.LabelFrame(master, text="Video & Display", padding="10")
        frame.pack(fill="x", expand=True, pady=(0, 10))
        frame.grid_columnconfigure(1, weight=1)

        self.bit_rate_scale = self._create_slider(frame, self.bit_rate, 1, 50)
        self._create_labeled_widget_row(frame, 0, "Video Bit Rate (Mbps):", self.bit_rate_scale, label_var=self.bit_rate)

        self.max_fps_scale = self._create_slider(frame, self.max_fps, 5, 120)
        self._create_labeled_widget_row(frame, 1, "Max FPS:", self.max_fps_scale, label_var=self.max_fps)

        self.max_size_combo = ttk.Combobox(frame, textvariable=self.max_size, values=self.CONSTANTS["max_size_options"], state="readonly")
        self._create_labeled_widget_row(frame, 2, "Max Resolution:", self.max_size_combo)

    def _create_general_options_frame(self, master):
        """Frame for general boolean options like fullscreen and show touches."""
        frame = ttk.LabelFrame(master, text="General Options", padding="10")
        frame.pack(fill="x", expand=True, pady=10)

        options = [
            ("Fullscreen", self.fullscreen), ("Always on Top", self.always_on_top),
            ("Show Touches", self.show_touches), ("Turn Screen Off", self.turn_screen_off),
            ("Stay Awake", self.stay_awake), ("Forward Audio", self.audio_forward)
        ]

        for i, (text, var) in enumerate(options):
            ttk.Checkbutton(
                frame, text=text, variable=var, style="Switch.TCheckbutton"
            ).grid(row=i // 2, column=i % 2, sticky="w", padx=5, pady=8)

    def _create_recording_camera_frame(self, master):
        """Frame containing both the recording and camera mirroring sections."""
        bottom_frame = ttk.Frame(master)
        bottom_frame.pack(fill="x", expand=True, pady=10)
        bottom_frame.grid_columnconfigure(0, weight=1)
        bottom_frame.grid_columnconfigure(1, weight=1)

        self._create_recording_frame(bottom_frame)
        self._create_camera_mirroring_frame(bottom_frame)

    def _create_recording_frame(self, master):
        """Frame for screen recording options."""
        frame = ttk.LabelFrame(master, text="Recording", padding="10")
        frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        frame.grid_columnconfigure(0, weight=1)

        ttk.Checkbutton(
            frame, text="Record Screen", variable=self.record_screen,
            command=self._toggle_record_file_entry, style="Switch.TCheckbutton"
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=5, pady=(0, 5))

        self.record_file_entry = ttk.Entry(frame, textvariable=self.record_file_path, state="disabled")
        self.record_file_entry.grid(row=1, column=0, sticky="ew", padx=5, pady=(5, 0))

        self.record_browse_button = ttk.Button(frame, text="Save As...", command=self._browse_for_record_file, state="disabled")
        self.record_browse_button.grid(row=1, column=1, sticky="e", padx=(5, 0), pady=(5, 0))

    def _create_camera_mirroring_frame(self, master):
        """Frame for camera mirroring options."""
        frame = ttk.LabelFrame(master, text="Camera Mirroring", padding="10")
        frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        frame.grid_columnconfigure(1, weight=1)

        ttk.Checkbutton(
            frame, text="Mirror Camera", variable=self.mirror_camera,
            command=self._toggle_camera_options, style="Switch.TCheckbutton"
        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=5, pady=(0, 5))

        self.camera_facing_combo = ttk.Combobox(frame, textvariable=self.camera_facing, values=self.CONSTANTS["camera_facing_options"], state="disabled", width=10)
        self.camera_facing_label = self._create_labeled_widget_row(frame, 1, "Facing:", self.camera_facing_combo, pady=2)

        self.camera_size_combo = ttk.Combobox(frame, textvariable=self.camera_size, values=self.CONSTANTS["camera_size_options"], state="disabled")
        self.camera_size_label = self._create_labeled_widget_row(frame, 2, "Size:", self.camera_size_combo, pady=2)

        self.camera_orientation_combo = ttk.Combobox(frame, textvariable=self.camera_orientation, values=self.CONSTANTS["camera_orientation_options"], state="disabled", width=10)
        self.camera_orientation_label = self._create_labeled_widget_row(frame, 3, "Orientation:", self.camera_orientation_combo, pady=2)

        ttk.Label(frame, text="Stuttering? Disable audio or lower bit rates.", style="Info.TLabel").grid(row=4, column=0, columnspan=3, sticky="w", padx=5, pady=(8, 0))

    def _create_advanced_settings_tab(self, master):
        """Creates the content for the 'Advanced Settings' tab."""
        master.grid_columnconfigure(1, weight=1)
        self._create_codec_frame(master)
        self._create_audio_performance_frame(master)
        self._create_buffering_frame(master)

    def _create_codec_frame(self, master):
        """Frame for video and audio codec selection."""
        frame = ttk.LabelFrame(master, text="Codecs", padding="10")
        frame.pack(fill="x", expand=True, pady=(0, 10))
        frame.grid_columnconfigure(1, weight=1)

        video_codec_combo = ttk.Combobox(frame, textvariable=self.video_codec, values=self.CONSTANTS["video_codec_options"], state="readonly")
        self._create_labeled_widget_row(frame, 0, "Video Codec:", video_codec_combo)

        audio_codec_combo = ttk.Combobox(frame, textvariable=self.audio_codec, values=self.CONSTANTS["audio_codec_options"], state="readonly")
        self._create_labeled_widget_row(frame, 1, "Audio Codec:", audio_codec_combo)

    def _create_audio_performance_frame(self, master):
        """Frame for audio bit rate selection."""
        frame = ttk.LabelFrame(master, text="Audio Performance", padding="10")
        frame.pack(fill="x", expand=True, pady=10)
        frame.grid_columnconfigure(1, weight=1)

        audio_bit_rate_combo = ttk.Combobox(frame, textvariable=self.audio_bit_rate, values=self.CONSTANTS["audio_bit_rate_options"], state="readonly")
        self._create_labeled_widget_row(frame, 0, "Audio Bit Rate (kbps):", audio_bit_rate_combo)

    def _create_buffering_frame(self, master):
        """Frame for video buffering and other advanced options."""
        frame = ttk.LabelFrame(master, text="Buffering & Other", padding="10")
        frame.pack(fill="x", expand=True, pady=10)
        frame.grid_columnconfigure(1, weight=1)

        video_buffer_slider = self._create_slider(frame, self.video_buffer, 0, 200)
        self._create_labeled_widget_row(frame, 0, "Video Buffer (ms):", video_buffer_slider, label_var=self.video_buffer)

        v4l2_sink_entry = ttk.Entry(frame, textvariable=self.v4l2_sink_path)
        self._create_labeled_widget_row(frame, 1, "V4L2 Sink (Linux):", v4l2_sink_entry)

    def _create_command_display(self, master):
        """Creates the read-only display for the generated scrcpy command."""
        command_frame = ttk.LabelFrame(master, text="Generated Command", padding="10")
        command_frame.pack(fill="x", pady=(15, 5))
        ttk.Label(
            command_frame, textvariable=self.generated_command,
            wraplength=500, font=self.CONSTANTS["command_font"]
        ).pack(fill="x", padx=5, pady=5)

    def _create_connect_button(self, master):
        """Creates the main button to launch scrcpy."""
        self.connect_button = ttk.Button(
            master, text="Connect", command=self._launch_scrcpy,
            state="disabled", style="Accent.TButton"
        )
        self.connect_button.pack(pady=(15, 0), ipady=8, fill="x")

    def _create_labeled_widget_row(self, master, row, label_text, widget, label_var=None, pady=5):
        """Helper to add a labeled widget row to a grid."""
        label = ttk.Label(master, text=label_text)
        label.grid(row=row, column=0, sticky="w", pady=pady, padx=5)
        widget.grid(row=row, column=1, sticky="ew", padx=5, pady=pady)
        if label_var:
            ttk.Label(master, textvariable=label_var, width=4).grid(row=row, column=2, sticky="w", padx=5)
        else:
            # Add a spacer to align with slider rows that have a value label
            ttk.Frame(master, width=30).grid(row=row, column=2)
        return label

    def _create_slider(self, master, variable, from_, to):
        """Helper to create a styled slider."""
        # The lambda ensures the variable is set with an integer value
        return ttk.Scale(master, from_=from_, to=to, orient="horizontal", variable=variable, command=lambda v: variable.set(int(float(v))))

    def _bind_variables_to_command_update(self):
        """Binds all Tkinter variables to update the command preview on change."""
        for attribute_name in dir(self):
            attribute = getattr(self, attribute_name)
            if isinstance(attribute, tk.Variable):
                attribute.trace_add("write", lambda *args: self._update_command_preview())

    def _update_ui_from_loaded_settings(self):
        """Update UI state after loading settings from the JSON file."""
        self._toggle_theme()
        self._toggle_camera_options()
        self._toggle_record_file_entry()
        self._update_command_preview()
        if self.scrcpy_path.get():
            self.connect_button.config(state="normal")

    def _toggle_theme(self):
        """Toggles between light and dark mode using sv-ttk."""
        sv_ttk.set_theme("dark" if self.dark_mode.get() else "light")

    def _browse_for_scrcpy(self):
        """Opens a file dialog to select the scrcpy executable."""
        filetypes = [("Scrcpy Executable", "scrcpy.exe" if sys.platform == "win32" else "scrcpy"), ("All files", "*.*")]
        path = filedialog.askopenfilename(title="Select scrcpy executable", filetypes=filetypes)
        if path:
            self.scrcpy_path.set(path)
            self.connect_button.config(state="normal")
            self._update_command_preview()

    def _browse_for_record_file(self):
        """Opens a file dialog to select a path for the screen recording."""
        path = filedialog.asksaveasfilename(
            title="Save recording as...",
            defaultextension=".mp4",
            filetypes=[("MP4 video", "*.mp4"), ("Matroska video", "*.mkv"), ("All files", "*.*")]
        )
        if path:
            self.record_file_path.set(path)

    def _toggle_record_file_entry(self):
        """Enables or disables the recording file path entry based on the checkbox."""
        state = "normal" if self.record_screen.get() else "disabled"
        self.record_file_entry.config(state=state)
        self.record_browse_button.config(state=state)
        self._update_command_preview()

    def _toggle_camera_options(self):
        """Enables/disables camera or screen mirroring options based on selection."""
        is_camera_mode = self.mirror_camera.get()
        camera_state = "normal" if is_camera_mode else "disabled"
        screen_state = "disabled" if is_camera_mode else "normal"

        # Toggle screen-related widgets
        self.bit_rate_scale.config(state=screen_state)
        self.max_fps_scale.config(state=screen_state)
        self.max_size_combo.config(state=screen_state)

        # Toggle camera-related widgets and their labels
        self.camera_facing_combo.config(state=camera_state)
        self.camera_facing_label.config(state=camera_state)
        self.camera_size_combo.config(state=camera_state)
        self.camera_size_label.config(state=camera_state)
        self.camera_orientation_combo.config(state=camera_state)
        self.camera_orientation_label.config(state=camera_state)

        self._update_command_preview()

    def _update_command_preview(self):
        """Updates the command display text by building the command string."""
        command_list = self._build_scrcpy_command()
        if command_list:
            self.generated_command.set(" ".join(command_list))
        else:
            self.generated_command.set("Please select the scrcpy executable...")

    def _build_scrcpy_command(self):
        """Constructs the list of scrcpy command arguments based on UI settings."""
        path = self.scrcpy_path.get()
        if not path:
            return None

        command = [f'"{path}"']

        if self.mirror_camera.get():
            command.append("--video-source=camera")
            command.append(f"--camera-facing={self.camera_facing.get()}")
            if self.camera_size.get() != "Default":
                command.append(f"--camera-size={self.camera_size.get().strip()}")
            orientation_map = {"0°": "0", "90°": "1", "180°": "2", "270°": "3"}
            if self.camera_orientation.get() in orientation_map:
                command.append(f"--capture-orientation={orientation_map[self.camera_orientation.get()]}")
        else:
            command.append(f"--video-bit-rate={self.bit_rate.get()}M")
            command.append(f"--max-fps={self.max_fps.get()}")
            if self.max_size.get() != "Device Native":
                command.append(f"--max-size={self.max_size.get()}")

        if self.fullscreen.get(): command.append("--fullscreen")
        if self.always_on_top.get(): command.append("--always-on-top")
        if self.show_touches.get(): command.append("--show-touches")
        if self.turn_screen_off.get(): command.append("--turn-screen-off")
        if self.stay_awake.get(): command.append("--stay-awake")

        if not self.audio_forward.get():
            command.append("--no-audio")
        elif self.audio_bit_rate.get() != self.CONSTANTS["default_audio_bit_rate"]:
             command.append(f"--audio-bit-rate={self.audio_bit_rate.get()}k")

        if self.record_screen.get() and self.record_file_path.get().strip():
            command.append(f'--record="{self.record_file_path.get().strip()}"')

        if self.video_codec.get() != "Default": command.append(f"--video-codec={self.video_codec.get()}")
        if self.audio_codec.get() != "Default": command.append(f"--audio-codec={self.audio_codec.get()}")
        if self.video_buffer.get() > 0: command.append(f"--video-buffer={self.video_buffer.get()}")
        if self.v4l2_sink_path.get().strip(): command.append(f"--v4l2-sink={self.v4l2_sink_path.get().strip()}")

        return command

    def _launch_scrcpy(self):
        """Builds and executes the scrcpy command in a subprocess."""
        command_to_run = self._build_scrcpy_command()
        if not command_to_run:
            messagebox.showerror("Error", "Scrcpy executable path is not set.")
            return

        self.connect_button.config(state="disabled", text="Connecting...")
        self.update_idletasks()
        final_command_str = " ".join(command_to_run)
        print(f"Executing: {final_command_str}")

        try:
            scrcpy_dir = os.path.dirname(self.scrcpy_path.get())
            subprocess.Popen(final_command_str, shell=True, cwd=scrcpy_dir)
        except Exception as e:
            messagebox.showerror("Execution Error", f"Failed to launch scrcpy:\n{e}")
        finally:
            self.after(3000, self._reset_connect_button)

    def _reset_connect_button(self):
        """Resets the connect button to its default state."""
        self.connect_button.config(state="normal", text="Connect")

    def save_settings(self):
        """Saves the current UI settings to a JSON file."""
        settings_to_save = {
            var_name: getattr(self, var_name).get()
            for var_name in dir(self)
            if isinstance(getattr(self, var_name, None), tk.Variable)
        }
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(settings_to_save, f, indent=4)
        except IOError as e:
            print(f"Error saving settings: {e}")

    def load_settings(self):
        """Loads settings from the JSON file if it exists."""
        try:
            with open(self.settings_file, 'r') as f:
                settings = json.load(f)
            for key, value in settings.items():
                if hasattr(self, key):
                    var = getattr(self, key)
                    if isinstance(var, tk.Variable):
                        var.set(value)
        except (FileNotFoundError, json.JSONDecodeError, TypeError):
            # Ignore if file doesn't exist, is empty, or is corrupted.
            pass


if __name__ == "__main__":
    app = ScrcpyController()
    app.mainloop()