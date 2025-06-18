import sys
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget, QLabel,
    QComboBox, QListWidget, QPushButton, QColorDialog, QDialogButtonBox,
    QGroupBox, QRadioButton, QApplication, QSpinBox
)
from PyQt6.QtGui import QColor, QPalette, QFont
from PyQt6.QtCore import QSettings, pyqtSignal, Qt

try:
    import qt_material
    QT_MATERIAL_AVAILABLE = True
except ImportError:
    QT_MATERIAL_AVAILABLE = False
    DEFAULT_THEMES = ['light_blue.xml', 'dark_teal.xml']

# Define the syntax elements user can customize
# Map Display Name -> Settings Key
SYNTAX_ELEMENTS = {
    "Keyword": "keyword",
    "Comment": "comment",
    "String": "string",
    "Number": "number",
    "Function/Method": "function",
    "Class/Type": "class_type",
    "Operator/Brace": "operator_brace",
    "Preprocessor/Decorator": "preprocessor_decorator",
    "HTML/XML Tag": "tag",
    "HTML/XML Attribute": "attribute",
    "CSS Selector": "selector",
    "CSS Property": "property",
}

# Default colors (used if setting is missing)
DEFAULT_COLORS = {
    "keyword": "#C586C0",
    "comment": "#6A9955",
    "string": "#CE9178",
    "number": "#B5CEA8",
    "function": "#DCDCAA",
    "class_type": "#4EC9B0",
    "operator_brace": "#D4D4D4",
    "preprocessor_decorator": "#808080",
    "tag": "#569CD6",
    "attribute": "#9CDCFE",
    "selector": "#D7BA7D",
    "property": "#9CDCFE",
}

class PreferencesDialog(QDialog):
    # Signal emitted when preferences are applied
    preferences_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.setMinimumWidth(500)
        self.settings = QSettings("Jasher", "SnippetManager")

        # Store current color choices temporarily
        self._current_syntax_colors = {}
        self._load_syntax_colors() # Load initial/saved colors

        main_layout = QVBoxLayout(self)
        tab_widget = QTabWidget()
        main_layout.addWidget(tab_widget)

        # Appearance Tab
        appearance_widget = QWidget()
        appearance_layout = QVBoxLayout(appearance_widget)
        theme_label = QLabel("Application Theme:")
        self.theme_combo = QComboBox()

        if QT_MATERIAL_AVAILABLE:
            available_themes = qt_material.list_themes()
            self.theme_combo.addItems(available_themes)
            current_theme = self.settings.value("appearance/theme", "dark_purple.xml")
            if current_theme in available_themes:
                self.theme_combo.setCurrentText(current_theme)
            else:
                self.theme_combo.setCurrentIndex(0) # Default if saved theme invalid
        else:
            theme_label.setText("Application Theme (qt_material not installed):")
            self.theme_combo.addItems(DEFAULT_THEMES)
            self.theme_combo.setEnabled(False)

        # Time Format Selection
        time_format_group = QGroupBox("Time Display Format")
        time_format_layout = QHBoxLayout(time_format_group) # Horizontal layout for radio buttons

        self.radio_12h = QRadioButton("12-hour (AM/PM)")
        self.radio_24h = QRadioButton("24-hour")

        time_format_layout.addWidget(self.radio_12h)
        time_format_layout.addWidget(self.radio_24h)
        time_format_layout.addStretch() # Push buttons to left

        # Load saved preference
        saved_format = self.settings.value("display/time_format", "12h") # Default to 12h
        if saved_format == "24h":
            self.radio_24h.setChecked(True)
        else:
            self.radio_12h.setChecked(True)

        appearance_layout.addWidget(time_format_group)

        # Tab Size Configuration
        tab_size_group = QGroupBox("Editor Settings")
        tab_size_layout = QHBoxLayout(tab_size_group)
        tab_size_label = QLabel("Tab Size (spaces):")
        self.tab_size_spinbox = QSpinBox()
        self.tab_size_spinbox.setMinimum(1)  # Minimum 1 space
        self.tab_size_spinbox.setMaximum(16)
        self.tab_size_spinbox.setValue(self.settings.value("editor/tab_size", 4, type=int)) # Load setting, default 4

        tab_size_layout.addWidget(tab_size_label)
        tab_size_layout.addWidget(self.tab_size_spinbox)
        tab_size_layout.addStretch()
        appearance_layout.addWidget(tab_size_group)

        appearance_layout.addWidget(theme_label)
        appearance_layout.addWidget(self.theme_combo)
        appearance_layout.addStretch()
        tab_widget.addTab(appearance_widget, "Appearance & Editor")

        # Syntax Highlighting Tab
        syntax_widget = QWidget()
        syntax_layout = QHBoxLayout(syntax_widget) # Horizontal layout

        # Left side: List of elements
        self.syntax_list = QListWidget()
        self.syntax_list.addItems(SYNTAX_ELEMENTS.keys())
        self.syntax_list.currentItemChanged.connect(self._update_color_button_display)
        syntax_layout.addWidget(self.syntax_list, 1) # Stretch factor 1

        # Right side: Color selection
        color_layout = QVBoxLayout()
        color_layout.addWidget(QLabel("Element Color:"))
        self.color_button = QPushButton("Click to change")
        self.color_button.clicked.connect(self._change_color)
        self.color_button.setMinimumHeight(40)
        self.color_button.setEnabled(False) # Enable when item selected
        color_layout.addWidget(self.color_button)

        # Reset button
        reset_button = QPushButton("Reset to Default")
        reset_button.clicked.connect(self._reset_current_color)
        reset_button.setEnabled(False) # Enable when item selected
        self.reset_color_button = reset_button # Keep reference
        color_layout.addWidget(reset_button)

        color_layout.addStretch()
        syntax_layout.addLayout(color_layout, 2) # Stretch factor 2

        tab_widget.addTab(syntax_widget, "Syntax Colors")

        # Dialog Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Apply
        )
        button_box.accepted.connect(self.accept) # OK clicked
        button_box.rejected.connect(self.reject) # Cancel clicked
        button_box.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self._apply_changes)

        main_layout.addWidget(button_box)

        # Select first item initially if possible
        if self.syntax_list.count() > 0:
            self.syntax_list.setCurrentRow(0)

    def _load_syntax_colors(self):
        """Load colors from settings into temporary dictionary."""
        self._current_syntax_colors = {}
        for display_name, key in SYNTAX_ELEMENTS.items():
            default_color = DEFAULT_COLORS.get(key, "#ffffff") # Default to white if not in defaults
            color_str = self.settings.value(f"syntax_colors/{key}", default_color)
            self._current_syntax_colors[key] = color_str

    def _update_color_button_display(self, current_item, previous_item):
        """Update color button when list selection changes."""
        if not current_item:
            self.color_button.setEnabled(False)
            self.reset_color_button.setEnabled(False)
            return

        display_name = current_item.text()
        key = SYNTAX_ELEMENTS.get(display_name)
        if not key:
            return

        color_str = self._current_syntax_colors.get(key, DEFAULT_COLORS.get(key, "#ffffff"))
        color = QColor(color_str)

        # Set button background and text color for contrast
        palette = self.color_button.palette()
        palette.setColor(QPalette.ColorRole.Button, color)
        self.color_button.setPalette(palette)
        self.color_button.setAutoFillBackground(True)
        self.color_button.setStyleSheet(f"background-color: {color.name()}; color: {'white' if color.lightnessF() < 0.5 else 'black'};")
        self.color_button.setText(color.name())
        self.color_button.setEnabled(True)
        self.reset_color_button.setEnabled(True)

    def _change_color(self):
        """Open color dialog and update selected element's color."""
        current_item = self.syntax_list.currentItem()
        if not current_item:
            return

        display_name = current_item.text()
        key = SYNTAX_ELEMENTS.get(display_name)
        if not key:
            return

        current_color = QColor(self._current_syntax_colors.get(key, DEFAULT_COLORS.get(key, "#ffffff")))
        new_color = QColorDialog.getColor(current_color, self, f"Select Color for {display_name}")

        if new_color.isValid():
            self._current_syntax_colors[key] = new_color.name()
            # Update button display
            self._update_color_button_display(current_item, None)

    def _reset_current_color(self):
        """Resets the currently selected element's color to default."""
        current_item = self.syntax_list.currentItem()
        if not current_item:
            return
        display_name = current_item.text()
        key = SYNTAX_ELEMENTS.get(display_name)
        if not key:
            return

        default_color = DEFAULT_COLORS.get(key, "#ffffff")
        self._current_syntax_colors[key] = default_color
        # Update button display
        self._update_color_button_display(current_item, None)


    def _save_settings(self):
        """Save current UI selections to QSettings."""
        # Save Theme
        if QT_MATERIAL_AVAILABLE:
            self.settings.setValue("appearance/theme", self.theme_combo.currentText())

        time_format = "24h" if self.radio_24h.isChecked() else "12h"
        self.settings.setValue("display/time_format", time_format)

        self.settings.setValue("editor/tab_size", self.tab_size_spinbox.value())

        # Save Syntax Colors
        for key, color_str in self._current_syntax_colors.items():
            self.settings.setValue(f"syntax_colors/{key}", color_str)

        self.settings.sync() # Ensure changes are written

    def _apply_changes(self):
        """Save settings and emit signal."""
        self._save_settings()
        self.preferences_changed.emit()

    def accept(self):
        """Apply changes and close."""
        self._apply_changes()
        super().accept()

    def reject(self):
        """Discard changes and close."""
        super().reject()