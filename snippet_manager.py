import sys
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple, Set

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QLineEdit, QTextEdit, QPlainTextEdit,
    QPushButton, QLabel, QSplitter, QComboBox, QFormLayout, QMessageBox,
    QStatusBar, QSizePolicy)

from PyQt6.QtGui import ( QFont, QAction, QPalette, QColor, QCloseEvent,
    QTextBlock, QPaintEvent, QResizeEvent, QPainter, QTextFormat)
from PyQt6.QtCore import Qt, QSettings, QByteArray, QRect, QSize

from syntax_highlighter import SyntaxHighlighter
from preferences_dialog import PreferencesDialog

try:
    import qt_material
    QT_MATERIAL_AVAILABLE = True
except ImportError:
    QT_MATERIAL_AVAILABLE = False

DATABASE_NAME = "snippets.db"
DEFAULT_LANGUAGES = sorted(["Python", "SQL", "Markdown", "Text", "C++", "C#", "HTML", "CSS", "JavaScript"])

# Database Functions
def init_db(db_path: str):
    """Initializes the SQLite database and creates the snippets table if it doesn't exist."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS snippets (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            code TEXT,
            language TEXT,
            tags TEXT,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Add triggers to update 'updated_at' timestamp automatically
    cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS update_snippet_timestamp
        AFTER UPDATE ON snippets
        FOR EACH ROW
        BEGIN
            UPDATE snippets SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
        END;
    ''')
    conn.commit()
    conn.close()

def load_snippets(db_path: str, search_term: str = "", tag_filter: Optional[str] = None,
                  language_filter: Optional[str] = None) -> List[Tuple[str, str]]:
    """Loads snippet IDs and titles from the database, filtered by search term and/or tag."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    base_query = "SELECT id, title FROM snippets"
    conditions = []
    params = []

    # Add search term condition
    if search_term:
        like_term = f"%{search_term}%"
        conditions.append("(title LIKE ? OR tags LIKE ? OR language LIKE ? OR description LIKE ? OR code LIKE ?)")
        params.extend([like_term] * 5)

    # Add tag filter condition
    if tag_filter and tag_filter != "All Tags":
        # Check for comma-separated tags
        conditions.append("(tags LIKE ? OR tags LIKE ? OR tags LIKE ? OR tags = ?)")
        params.append(f"%,{tag_filter},%") # Tag in the middle
        params.append(f"{tag_filter},%")   # Tag at the start
        params.append(f"%,{tag_filter}")   # Tag at the end
        params.append(tag_filter)          # Tag is the only one

    if language_filter and language_filter != "All Languages":
        conditions.append("language = ?")
        params.append(language_filter)

    # Construct the final query
    if conditions:
        query = f"{base_query} WHERE {' AND '.join(conditions)} ORDER BY updated_at DESC"
    else:
        query = f"{base_query} ORDER BY updated_at DESC"

    # print(f"Executing query: {query} with params: {params}")
    cursor.execute(query, params)
    snippets = cursor.fetchall()
    conn.close()
    return snippets # Returns list of (id, title) tuples

def get_snippet_details(db_path: str, snippet_id: str) -> Optional[Tuple]:
    """Fetches all details for a specific snippet ID."""
    conn = sqlite3.connect(db_path)
    # Use dictionary row factory for easier access by column name
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM snippets WHERE id = ?", (snippet_id,))
    snippet = cursor.fetchone()
    conn.close()
    return snippet # Returns a dictionary-like row object or None

def add_snippet(db_path: str, title: str, code: str, language: str, tags: str, description: str) -> str:
    """Adds a new snippet to the database and returns its generated ID."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    new_id = uuid.uuid4().hex
    now_utc = datetime.now(timezone.utc)
    timestamp_str_for_db = now_utc.strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('''
        INSERT INTO snippets (id, title, code, language, tags, description, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (new_id, title, code, language, tags, description, timestamp_str_for_db, timestamp_str_for_db))
    conn.commit()
    conn.close()
    return new_id

def update_snippet(db_path: str, snippet_id: str, title: str, code: str, language: str, tags: str, description: str):
    """Updates an existing snippet in the database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE snippets
        SET title = ?, code = ?, language = ?, tags = ?, description = ?
        WHERE id = ?
    ''', (title, code, language, tags, description, snippet_id))
    conn.commit() # The trigger will handle updated_at
    conn.close()

def delete_snippet(db_path: str, snippet_id: str):
    """Deletes a snippet from the database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM snippets WHERE id = ?", (snippet_id,))
    conn.commit()
    conn.close()

# Main Application Window
class SnippetManagerWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # Add QSettings
        self.settings = QSettings("Jasher", "SnippetManager")

        self.db_path = os.path.join(os.path.dirname(__file__), DATABASE_NAME)

        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(__file__)

        self.db_path = os.path.join(base_dir, DATABASE_NAME)
        self.current_snippet_id: Optional[str] = None
        self.highlighter: Optional[SyntaxHighlighter] = None

        self._apply_theme()

        init_db(self.db_path)
        self._setup_ui()
        self._load_initial_data()
        self._connect_signals()

        self.setWindowTitle("Code Snippet Manager")

        # Restore Geometry and State
        geometry_data = self.settings.value("MainWindow/geometry")
        if geometry_data and isinstance(geometry_data, QByteArray): # Check if data exists and is expected type
            if self.restoreGeometry(geometry_data):
                 pass
            else:
                 print("Failed to restore window geometry.")
                 self.resize(1000, 700) # Fallback size
        else:
            self.resize(1000, 700)

        state_data = self.settings.value("MainWindow/state")
        if state_data and isinstance(state_data, QByteArray):
             if self.restoreState(state_data):
                 pass
             else:
                 print("Failed to restore window state.")
        else:
             print("No state found.")

    # Theme Application Method
    def _apply_theme(self):
        """Applies the theme stored in settings."""
        if QT_MATERIAL_AVAILABLE:
            theme_file = self.settings.value("appearance/theme", "dark_purple.xml")
            try:
                qt_material.apply_stylesheet(QApplication.instance(), theme=theme_file)
            except Exception as e:
                print(f"Error applying theme '{theme_file}': {e}")
                # Fallback or log error
                try: # Try a default fallback
                     qt_material.apply_stylesheet(QApplication.instance(), theme='dark_teal.xml')
                     print("Applied fallback theme: dark_teal.xml")
                except Exception as fallback_e:
                     print(f"Failed to apply fallback theme: {fallback_e}")
        else:
            # Apply default Qt style if qt_material not available
            QApplication.instance().setStyleSheet("") # Reset to default
            print("qt_material not found, using default style.")

    def _setup_ui(self):
        # Central Widget & Main Layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget) # Horizontal layout for main panels

        # Use QSplitter for resizable panels
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        # Left Panel (List and Search)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(5, 5, 5, 5)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search Snippets...")
        left_layout.addWidget(self.search_input)

        # Filters layout
        filter_layout = QFormLayout()
        filter_layout.setContentsMargins(0, 5, 0, 5)

        # Tag Filter
        self.tag_filter_combo = QComboBox()
        self.tag_filter_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        filter_layout.addRow("Filter by Tag:", self.tag_filter_combo)

        # Language Filter
        self.language_filter_combo = QComboBox()
        self.language_filter_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        filter_layout.addRow("Filter by Language:", self.language_filter_combo)

        left_layout.addLayout(filter_layout)

        self.snippet_list_widget = QListWidget()
        self.snippet_list_widget.setFont(QFont("Arial", 10))
        left_layout.addWidget(self.snippet_list_widget)

        button_layout = QHBoxLayout()
        self.add_button = QPushButton("➕ New")
        self.delete_button = QPushButton("❌ Delete")
        self.delete_button.setEnabled(False) # Disable initially
        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.delete_button)
        left_layout.addLayout(button_layout)

        splitter.addWidget(left_panel)

        # Right Panel (Details and Code)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # Form layout for details
        details_form = QFormLayout()
        self.title_input = QLineEdit()
        self.language_combo = QComboBox()
        self.language_combo.addItems(DEFAULT_LANGUAGES)
        self.language_combo.setEditable(True) # Allow adding new languages
        self.tags_input = QLineEdit()
        self.tags_input.setPlaceholderText("Comma-separated tags")
        self.description_edit = QTextEdit()
        self.description_edit.setPlaceholderText("Optional description...")
        self.description_edit.setMaximumHeight(100) # Limit description height

        details_form.addRow("Title:", self.title_input)
        details_form.addRow("Language:", self.language_combo)
        details_form.addRow("Tags:", self.tags_input)
        details_form.addRow("Description:", self.description_edit)
        right_layout.addLayout(details_form)

        # Code editor
        self.code_edit = CodeEditorWithSpaces()
        self.code_edit.setPlaceholderText("Enter your code snippet here...")
        # Use a monospaced font for code
        font = QFont("Consolas", 11)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.code_edit.setFont(font)
        self.code_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap) # Disable line wrapping
        initial_tab_size = self.settings.value("editor/tab_size", 4, type=int)
        self.code_edit.set_tab_spaces(initial_tab_size)
        right_layout.addWidget(self.code_edit)

        # Action buttons for the right panel
        action_button_layout = QHBoxLayout()
        self.save_button = QPushButton("💾 Save Changes")
        self.copy_button = QPushButton("📋 Copy Code")
        self.save_button.setEnabled(False) # Disable initially
        self.copy_button.setEnabled(False) # Disable initially
        action_button_layout.addStretch() # Push buttons to the right
        action_button_layout.addWidget(self.copy_button)
        action_button_layout.addWidget(self.save_button)
        right_layout.addLayout(action_button_layout)

        self.last_updated_label = QLabel("Last Updated: -")
        self.last_updated_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        font = self.last_updated_label.font()
        font.setPointSize(font.pointSize() - 1)
        self.last_updated_label.setFont(font)
        palette = self.last_updated_label.palette()
        palette.setColor(QPalette.ColorRole.WindowText, QColor("gray"))
        self.last_updated_label.setPalette(palette)
        right_layout.addWidget(self.last_updated_label)

        splitter.addWidget(right_panel)

        # Adjust initial splitter size ratio
        splitter.setSizes([300, 700]) # Adjust widths: left panel, right panel

        # Status Bar
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("Ready", 3000) # Message disappears after 3 seconds

        self._create_menu_bar() # Create menu bar

        self._load_and_populate_tags()
        self._load_and_populate_languages()

    # MENU BAR
    def _create_menu_bar(self):
        """Creates the menu bar with options."""
        menu_bar = self.menuBar() # Get the main window's menu bar

        # File Menu
        file_menu = menu_bar.addMenu("&File")

        new_action = QAction("➕ &New Snippet", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self._add_new_snippet_ui)
        file_menu.addAction(new_action)

        save_action = QAction("💾 &Save Current", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self._save_snippet)
        file_menu.addAction(save_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close) # Close the main window
        file_menu.addAction(exit_action)

        # Edit Menu
        edit_menu = menu_bar.addMenu("&Edit")

        prefs_action = QAction("&Preferences...", self)
        prefs_action.setShortcut("Ctrl+,") # Common shortcut
        prefs_action.triggered.connect(self._open_preferences_dialog)
        edit_menu.addAction(prefs_action)

        # Add Copy action
        copy_menu_action = QAction("📋 &Copy Code", self)
        copy_menu_action.setShortcut("Ctrl+C") # NOTE: Editor might handle this better
        copy_menu_action.triggered.connect(self._copy_code_to_clipboard)
        edit_menu.addAction(copy_menu_action)

        # View Menu
        view_menu = menu_bar.addMenu("&View")

        self.toggle_status_action = QAction("Show &Status Bar", self)
        self.toggle_status_action.setCheckable(True)
        # Set initial checked state based on status bar visibility
        try:
             self.toggle_status_action.setChecked(self.statusBar.is_visible)
        except AttributeError: # statusBar might not exist yet if called too early
             self.toggle_status_action.setChecked(True) # Assume visible initially
        self.toggle_status_action.triggered.connect(self._toggle_status_bar)
        view_menu.addAction(self.toggle_status_action)

        # Toggle line numbers
        view_menu.addSeparator()
        self.toggle_ln_action = QAction("Show &Line Numbers", self)
        self.toggle_ln_action.setCheckable(True)
        # Set initial state from settings
        initial_ln_visible = self.settings.value("editor/line_numbers_visible", True, type=bool)
        self.toggle_ln_action.setChecked(initial_ln_visible)
        self.toggle_ln_action.triggered.connect(self._toggle_line_numbers)
        view_menu.addAction(self.toggle_ln_action)

        # Help Menu
        help_menu = menu_bar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about_dialog)
        help_menu.addAction(about_action)

    def _open_preferences_dialog(self):
        """Opens the Preferences dialog and connects its signal."""
        dialog = PreferencesDialog(self)
        # Connect the dialog's signal to a slot in the main window
        dialog.preferences_changed.connect(self._apply_preferences)
        dialog.exec() # Modal Dialog

    # Apply Changes
    def _apply_preferences(self):
        """Applies changes made in the preferences dialog."""
        self._apply_theme() # Re-apply the theme

        new_tab_size = self.settings.value("editor/tab_size", 4, type=int)
        self.code_edit.set_tab_spaces(new_tab_size)

        # Force the highlighter to re-read settings and re-highlight
        if self.current_snippet_id or self.code_edit.toPlainText(): # Only rehighlight if there's code visible
            current_lang = self.language_combo.currentText()
            self._update_highlighter(current_lang)

         # Refresh timestamp if snippet is loaded
        if self.current_snippet_id:
            details = get_snippet_details(self.db_path, self.current_snippet_id)
            if details:
                # Re-run the display logic for the current snippet to update the timestamp format
                self._display_snippet_details(details)
            else:
                self._clear_details_panel()

        self.statusBar.showMessage("Preferences updated.", 3000)

    def _show_about_dialog(self):
        """Shows a simple About message box."""
        about_text = """
        <b>Code Snippet Manager</b> v0.1.0
        <p>A simple desktop application to store and manage code snippets.</p>
        <p>Built with Python and PyQt6.</p>
        <p>By Jacob Asher.</p>
        """
        QMessageBox.about(self, "About Code Snippet Manager", about_text)

    def _toggle_status_bar(self):
        """Toggles the visibility of the status bar."""
        # Ensure statusBar exists before accessing isVisible
        if hasattr(self, 'statusBar') and self.statusBar:
            is_visible = self.statusBar.isVisible()
            self.statusBar.setVisible(not is_visible)
            # Keep the action's checked state in sync
            self.toggle_status_action.setChecked(not is_visible)

    def _toggle_line_numbers(self, checked: bool):
        """Slot to toggle line number visibility."""
        self.code_edit.setLineNumbersVisible(checked)
        # Save the setting
        self.settings.setValue("editor/line_numbers_visible", checked)
        self.settings.sync()

    def _load_initial_data(self):
        """Loads all snippets initially and populates the list."""
        self._refresh_snippet_list()
        self.statusBar.showMessage(f"Loaded {self.snippet_list_widget.count()} snippets.", 3000)

    def _populate_list(self, snippets: List[Tuple[str, str]]):
        """Clears and refills the snippet list widget."""
        self.snippet_list_widget.clear()
        if not snippets:
            self.snippet_list_widget.addItem("No snippets found.")
            self.snippet_list_widget.setEnabled(False) # Disable list if empty
            return

        self.snippet_list_widget.setEnabled(True)
        for snippet_id, title in snippets:
            item = QListWidgetItem(title)
            item.setData(Qt.ItemDataRole.UserRole, snippet_id) # Store ID with the item
            self.snippet_list_widget.addItem(item)

    def _connect_signals(self):
        """Connect UI element signals to their handler slots."""
        self.tag_filter_combo.currentTextChanged.connect(self._refresh_snippet_list)
        self.language_filter_combo.currentTextChanged.connect(self._refresh_snippet_list)

        self.search_input.textChanged.connect(self._refresh_snippet_list)
        self.snippet_list_widget.itemSelectionChanged.connect(self._on_list_selection_changed)
        self.add_button.clicked.connect(self._add_new_snippet_ui)
        self.delete_button.clicked.connect(self._delete_selected_snippet)
        self.save_button.clicked.connect(self._save_snippet)
        self.copy_button.clicked.connect(self._copy_code_to_clipboard)

        # Enable save button when details are edited
        self.title_input.textChanged.connect(lambda: self.save_button.setEnabled(True))
        self.language_combo.currentTextChanged.connect(lambda: self.save_button.setEnabled(True))
        self.tags_input.textChanged.connect(lambda: self.save_button.setEnabled(True))
        self.description_edit.textChanged.connect(lambda: self.save_button.setEnabled(True))
        self.code_edit.textChanged.connect(lambda: self.save_button.setEnabled(True))

        # Reapply highlighter when language changes
        self.language_combo.currentTextChanged.connect(self._update_highlighter)

    def _on_list_selection_changed(self):
        """Handles selection changes in the snippet list."""
        selected_items = self.snippet_list_widget.selectedItems()

        if selected_items:
            # Get the first selected item
            current = selected_items[0]
            snippet_id = current.data(Qt.ItemDataRole.UserRole)

            if snippet_id: # Check if it's a real snippet item
                self.current_snippet_id = snippet_id # Update the stored ID
                details = get_snippet_details(self.db_path, snippet_id)
                if details:
                    self._block_detail_signals(True)
                    self._display_snippet_details(details)
                    self._block_detail_signals(False)

                    self.delete_button.setEnabled(True)
                    self.copy_button.setEnabled(True)
                    self.save_button.setEnabled(False)
                else:
                    # Handle error case
                    self._clear_details_panel()
                    self.current_snippet_id = None # Reset ID on error
                    QMessageBox.warning(self, "Error", f"Could not load snippet details for ID: {snippet_id}")
                    self.delete_button.setEnabled(False)
                    self.copy_button.setEnabled(False)
            else:
                 # Handle the "No snippets found" item if it's somehow selectable
                 self._clear_details_panel(clear_language=False)
                 self.current_snippet_id = None
                 self.delete_button.setEnabled(False)
                 self.copy_button.setEnabled(False)

        else: # No items selected
            # Only clear if we weren't already in the "new snippet" state
             if self.current_snippet_id is not None:
                 self._clear_details_panel()

    def _display_snippet_details(self, details: sqlite3.Row):
        """Populates the right panel with snippet data."""
        self.title_input.setText(details["title"])
        # Find the index for the language, add if not present (for editable combo)
        lang_index = self.language_combo.findText(details["language"] or "", Qt.MatchFlag.MatchFixedString)
        if lang_index >= 0:
            self.language_combo.setCurrentIndex(lang_index)
        else:
            # Add the language if it came from DB but wasn't in default list
            if details["language"]:
                self.language_combo.addItem(details["language"])
                self.language_combo.setCurrentText(details["language"])
            else:
                 self.language_combo.setCurrentIndex(DEFAULT_LANGUAGES.index("Text")) # Default to Text if None/empty

        self.tags_input.setText(details["tags"] or "")
        self.description_edit.setPlainText(details["description"] or "")
        self.code_edit.setPlainText(details["code"] or "")

        timestamp_str = details["updated_at"]
        display_text = "Last Updated: -"
        if timestamp_str:
            try:
                dt_obj_naive = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')

                dt_obj_utc = dt_obj_naive.replace(tzinfo=timezone.utc)
                dt_obj_local = dt_obj_utc.astimezone(None) # None uses system's local timezone

                time_format_pref = self.settings.value("display/time_format", "12h") # Read setting
                if time_format_pref == "24h":
                    chosen_format = '%Y-%m-%d %H:%M:%S' # 24-hour format
                else:
                    chosen_format = '%Y-%m-%d %I:%M:%S %p' # 12-hour format (AM/PM)

                formatted_time = dt_obj_local.strftime(chosen_format)
                display_text = f"Last Updated: {formatted_time}"
            except ValueError as e:
                print(f"Error parsing timestamp '{timestamp_str}': {e}")
                display_text = "Last Updated: (Invalid Format)" # Indicate error
            except Exception as e: # Catch any other unexpected error
                 print(f"Unexpected error handling timestamp '{timestamp_str}': {e}")
                 display_text = "Last Updated: (Error)"

        self.last_updated_label.setText(display_text)

        self._update_highlighter(self.language_combo.currentText()) # Apply highlighter

    def _clear_details_panel(self, clear_language=True):
        """Clears all input fields in the right details panel."""
        self._block_detail_signals(True)
        self.title_input.clear()
        if clear_language:
             # Find 'Text' index or default to 0
            text_index = self.language_combo.findText("Text", Qt.MatchFlag.MatchFixedString)
            self.language_combo.setCurrentIndex(text_index if text_index >= 0 else 0)
        self.tags_input.clear()
        self.description_edit.clear()
        self.code_edit.clear()
        self._block_detail_signals(False)

        self.last_updated_label.setText("Last Updated: -")

        self._update_highlighter(self.language_combo.currentText() if not clear_language else "Text")
        self.save_button.setEnabled(False)
        self.copy_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        self.current_snippet_id = None # No snippet is actively selected for editing

    def _add_new_snippet_ui(self):
        """Clears the details panel to prepare for adding a new snippet."""
        # Block signals during programmatic changes
        self.snippet_list_widget.blockSignals(True)
        self.snippet_list_widget.clearSelection() # Deselect any current item
        self.snippet_list_widget.blockSignals(False)

        self._clear_details_panel(clear_language=True) # Clear all fields
        self.title_input.setFocus() # Set focus to title for easy entry
        self.current_snippet_id = None # Ensure we know it's a new one
        self.save_button.setEnabled(False) # Should be enabled on first edit
        self.copy_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        self.statusBar.showMessage("Enter details for new snippet...", 3000)

    def _save_snippet(self):
        """Saves the current snippet."""
        title = self.title_input.text().strip()
        if not title:
            QMessageBox.warning(self, "Input Error", "Snippet title cannot be empty.")
            return

        code = self.code_edit.toPlainText()
        language = self.language_combo.currentText()
        # Ensure tags are comma-separated
        tags = ",".join([t.strip() for t in self.tags_input.text().strip().split(',') if t.strip()])
        description = self.description_edit.toPlainText().strip()

        try:
            saved_id = self.current_snippet_id # Store potential ID before DB operation might clear it
            operation_type = "updated" # Assume update

            if self.current_snippet_id:
                # Update existing snippet
                update_snippet(self.db_path, self.current_snippet_id, title, code, language, tags, description)
                self.statusBar.showMessage(f"Snippet '{title}' updated.", 3000)
            else:
                # Add new snippet
                new_id = add_snippet(self.db_path, title, code, language, tags, description)
                saved_id = new_id # Store the newly generated ID
                operation_type = "added"
                self.statusBar.showMessage(f"Snippet '{title}' added.", 3000)

            # Refresh the main snippet list
            self._refresh_snippet_list()

            self._load_and_populate_tags()
            self._load_and_populate_languages()

            # Try to re-select the saved/added item in the list
            if saved_id:
                 self.snippet_list_widget.blockSignals(True)
                 found = False
                 for i in range(self.snippet_list_widget.count()):
                    item = self.snippet_list_widget.item(i)
                    if item and item.data(Qt.ItemDataRole.UserRole) == saved_id:
                        self.snippet_list_widget.setCurrentRow(i)
                        found = True
                        break
                 self.snippet_list_widget.blockSignals(False)

                 # If re-selected, update the details panel to reflect the saved state
                 if found:
                      self._on_list_selection_changed()
                 else:
                     # If not found, clear panel and ensure correct ID
                     self._clear_details_panel()
                     self.current_snippet_id = saved_id if operation_type == "added" else None # Keep ID if just added

            # If it was a new snippet add, ensure the ID is stored
            if operation_type == "added":
                self.current_snippet_id = saved_id

            # Disable save button after successful save
            self.save_button.setEnabled(False)

        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Could not save snippet:\n{e}")
            self.statusBar.showMessage("Error saving snippet!", 5000)

    def _delete_selected_snippet(self):
        """Deletes the currently selected snippet after confirmation."""
        if not self.current_snippet_id:
            return # Should not happen if button is enabled

        current_item = self.snippet_list_widget.currentItem()
        if not current_item: return

        title = current_item.text()

        reply = QMessageBox.warning(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete the snippet '{title}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No # Default to No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                delete_snippet(self.db_path, self.current_snippet_id)
                self.statusBar.showMessage(f"Snippet '{title}' deleted.", 3000)
                # Store current search before clearing panel (which resets current_snippet_id)

                self._load_and_populate_tags()
                self._load_and_populate_languages()

                self._clear_details_panel()

                # Refresh list
                self._refresh_snippet_list()

            except Exception as e:
                QMessageBox.critical(self, "Database Error", f"Could not delete snippet:\n{e}")
                self.statusBar.showMessage("Error deleting snippet!", 5000)

    def _copy_code_to_clipboard(self):
        """Copies the code from the code editor to the system clipboard."""
        code_to_copy = self.code_edit.toPlainText()
        if code_to_copy: # Check if there's actually code in the editor
            clipboard = QApplication.clipboard()
            clipboard.setText(code_to_copy)
            self.statusBar.showMessage("Code copied to clipboard!", 2000)
        else:
            self.statusBar.showMessage("Nothing to copy.", 2000)

    def _update_highlighter(self, language: str):
        """Creates or updates the syntax highlighter for the code editor."""
        # Pass the document and language, the highlighter handles colors
        self.highlighter = SyntaxHighlighter(self.code_edit.document(), language)
        self.highlighter.rehighlight()

    def _block_detail_signals(self, block: bool):
        """Blocks or unblocks signals for detail widgets to prevent unwanted triggers."""
        self.title_input.blockSignals(block)
        self.language_combo.blockSignals(block)
        self.tags_input.blockSignals(block)
        self.description_edit.blockSignals(block)
        self.code_edit.blockSignals(block)
    
    def _load_and_populate_tags(self):
        """Loads unique tags from DB and populates the filter combo box."""
        current_selection = self.tag_filter_combo.currentText() # Remember selection
        self.tag_filter_combo.blockSignals(True) # Prevent triggering refresh while populating
        try:
            self.tag_filter_combo.clear()
            self.tag_filter_combo.addItem("All Tags") # Add default option
            unique_tags = get_unique_tags(self.db_path)
            if unique_tags:
                self.tag_filter_combo.addItems(unique_tags)

            # Try to restore previous selection
            index = self.tag_filter_combo.findText(current_selection)
            if index != -1:
                self.tag_filter_combo.setCurrentIndex(index)
            else:
                self.tag_filter_combo.setCurrentIndex(0) # Default to "All Tags"

        except Exception as e:
            print(f"Error loading tags: {e}")
            QMessageBox.warning(self, "Tag Loading Error", f"Could not load tags:\n{e}")
        finally:
            self.tag_filter_combo.blockSignals(False) # Re-enable signals

    def _load_and_populate_languages(self):
        """Loads unique languages from DB and populates the language filter combo box."""
        current_selection = self.language_filter_combo.currentText()
        self.language_filter_combo.blockSignals(True)
        try:
            self.language_filter_combo.clear()
            self.language_filter_combo.addItem("All Languages")
            unique_langs = get_unique_languages(self.db_path)

            if unique_langs:
                self.language_filter_combo.addItems(unique_langs)

            # Restore selection
            index = self.language_filter_combo.findText(current_selection)
            if index != -1:
                self.language_filter_combo.setCurrentIndex(index)
            else:
                self.language_filter_combo.setCurrentIndex(0) # Default

        except Exception as e:
            print(f"Error loading/populating languages: {e}")
            QMessageBox.warning(self, "Language Loading Error", f"Could not load languages:\n{e}")
        finally:
            self.language_filter_combo.blockSignals(False)

    def _refresh_snippet_list(self):
        """Refreshes the snippet list based on current search, tag, and language filters."""
        search_term = self.search_input.text()
        tag_filter = self.tag_filter_combo.currentText()
        language_filter = self.language_filter_combo.currentText()

        # print(f"Refreshing list: Search='{search_term}', Tag='{tag_filter}', Lang='{language_filter}'")
        snippets = load_snippets(
            self.db_path,
            search_term=search_term,
            tag_filter=tag_filter,
            language_filter=language_filter
        )
        self._populate_list(snippets)

    def closeEvent(self, event: QCloseEvent):
        """Save window geometry and state on close."""
        self.settings.setValue("MainWindow/geometry", self.saveGeometry())
        self.settings.setValue("MainWindow/state", self.saveState())

        if hasattr(self, 'code_edit') and self.code_edit:
             self.settings.setValue("editor/line_numbers_visible", self.code_edit.areLineNumbersVisible())

        self.settings.sync() # Ensure settings are written
        super().closeEvent(event)

def get_unique_tags(db_path: str) -> List[str]:
    """Fetches all unique, non-empty tags from the database."""
    conn = None
    # Use a set to handle uniqueness during collection
    collected_tags: Set[str] = set()
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        # Select the tags column from all relevant rows
        cursor.execute("SELECT tags FROM snippets WHERE tags IS NOT NULL AND tags != ''")

        row_count = 0
        row = cursor.fetchone()
        while row:
            row_count += 1
            tags_in_snippet_str = row[0]
            # print(f"[get_unique_tags] Processing row {row_count}, tags string: '{tags_in_snippet_str}'")
            # Split, strip whitespace, filter empty strings
            tags_this_row = {tag.strip() for tag in tags_in_snippet_str.split(',') if tag.strip()}
            # Add unique tags found in this row to the overall set
            collected_tags.update(tags_this_row)
            row = cursor.fetchone() # Fetch the next row

    except Exception as e:
        print(f"[get_unique_tags] Error fetching unique tags: {e}")
    finally:
        if conn:
            conn.close()

    sorted_tag_list = sorted(list(collected_tags), key=str.lower) # Sort alphabetically, case-insensitive
    return sorted_tag_list

def get_unique_languages(db_path: str) -> List[str]:
    """Fetches all unique, non-empty languages from the database."""
    conn = None
    unique_langs = set()
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT DISTINCT language FROM snippets WHERE language IS NOT NULL AND language != ''")

        rows = cursor.fetchall()
        for row in rows:
            unique_langs.add(row[0]) # Add the language string to the set

    except Exception as e:
        print(f"[get_unique_languages] Error fetching unique languages: {e}")
    finally:
        if conn:
            conn.close()

    sorted_lang_list = sorted(list(unique_langs), key=str.lower) # Sort case-insensitively
    return sorted_lang_list

class LineNumberArea(QWidget):
    def __init__(self, editor: 'CodeEditorWithSpaces'):
        super().__init__(editor)
        self.codeEditor = editor

    def sizeHint(self) -> QSize:
        # Calculate width needed based on max line number digits
        digits = 1
        max_val = max(1, self.codeEditor.blockCount())
        while max_val >= 10:
            max_val //= 10
            digits += 1

        # Use font metrics to get accurate width
        space = 5 + self.codeEditor.fontMetrics().horizontalAdvance('9') * digits
        return QSize(space, 0)

    def paintEvent(self, event: 'QPaintEvent'):
        self.codeEditor.lineNumberAreaPaintEvent(event)

class CodeEditorWithSpaces(QPlainTextEdit):
    """A QPlainTextEdit subclass that inserts 4 spaces on Tab press."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = QSettings("Jasher", "SnippetManager")

        # Line Number Area Setup
        self.lineNumberArea = LineNumberArea(self)
        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)

        # Read initial tab size setting
        self.tab_spaces = self.settings.value("editor/tab_size", 4, type=int)

        # Read initial line number visibility
        self._line_numbers_visible = self.settings.value("editor/line_numbers_visible", True, type=bool)

        self.updateLineNumberAreaWidth(0)

        # Set initial visibility based on setting
        self.lineNumberArea.setVisible(self._line_numbers_visible)

    def set_tab_spaces(self, spaces: int):
        """Sets the number of spaces to insert for a tab."""
        self.tab_spaces = max(1, spaces) # Ensure at least 1 space

    def keyPressEvent(self, event):
        """Override key press event to handle Tab key."""
        if event.key() == Qt.Key.Key_Tab:
            # Tab key pressed
            cursor = self.textCursor()

            if cursor.hasSelection():
                cursor.insertText(" " * self.tab_spaces)
            else:
                cursor.insertText(" " * self.tab_spaces)

            event.accept()
        else:
            # Default handling for all other keys
            super().keyPressEvent(event)

    def lineNumberAreaWidth(self) -> int:
        if not self._line_numbers_visible:
            return 0
        return self.lineNumberArea.sizeHint().width()

    def updateLineNumberAreaWidth(self, newBlockCount: int):
        """Sets the left margin based on the calculated line number area width."""
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

    def updateLineNumberArea(self, rect: QRect, dy: int):
        """Scrolls the line number area or schedules update."""
        if dy:
            self.lineNumberArea.scroll(0, dy)
        else:
            # Update the specific rectangle, adding margin width
            self.lineNumberArea.update(0, rect.y(), self.lineNumberArea.width(), rect.height())

        if rect.contains(self.viewport().rect()):
            self.updateLineNumberAreaWidth(0) # Update width if viewport geometry changes

    def resizeEvent(self, event: 'QResizeEvent'):
        """Handles resizing of the editor, repositioning the line number area."""
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.lineNumberArea.setGeometry(QRect(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height()))

    def lineNumberAreaPaintEvent(self, event: 'QPaintEvent'):
        """Paints the line numbers in the line number area."""
        if not self._line_numbers_visible:
            return # Don't paint if hidden

        painter = QPainter(self.lineNumberArea)
        editor_bg = self.palette().color(self.backgroundRole())
        bg_color = editor_bg.darker(115) if editor_bg.lightnessF() > 0.5 else editor_bg.lighter(115)
        painter.fillRect(event.rect(), bg_color)

        block = self.firstVisibleBlock()
        blockNumber = block.blockNumber()
        # Get font metrics from the editor
        font_metrics = self.fontMetrics()
        # Use text color from editor's palette
        text_color = self.palette().color(QPalette.ColorRole.Text) # Use editor's text color
        painter.setPen(text_color)

        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(blockNumber + 1)
                painter.drawText(0, int(top), self.lineNumberArea.width() - 3, font_metrics.height(),
                                 Qt.AlignmentFlag.AlignRight, number)

            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            blockNumber += 1

    # Method to toggle visibility
    def setLineNumbersVisible(self, visible: bool):
        """Shows or hides the line number area."""
        self._line_numbers_visible = visible
        self.updateLineNumberAreaWidth(0) # Recalculate margin
        self.lineNumberArea.setVisible(visible) # Show/hide the widget

    def areLineNumbersVisible(self) -> bool:
        return self._line_numbers_visible

if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = SnippetManagerWindow()
    window.show()
    sys.exit(app.exec())