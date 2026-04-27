"""
Shared UI style constants and helpers.

Centralizes spacing, sizing and stylesheet snippets so the application has a
consistent visual rhythm. Use these constants instead of hardcoding pixel
values throughout the UI code.
"""

# 4px spacing scale ----------------------------------------------------------
SPACING_XS = 2   # tight gaps between tightly-grouped widgets
SPACING_SM = 4   # default inter-widget spacing on a 4px grid
SPACING_MD = 8   # default container padding / row breathing room
SPACING_LG = 12  # generous separation between dialog sections

# Standard icon sizes (px)
ICON_SIZE_LIST = 16     # row icons in detailed list view
ICON_SIZE_TOOLBAR = 20  # toolbar action icons

# Stylesheet snippets -------------------------------------------------------
# A red, clearly-destructive button look for "permanently delete" confirms.
DESTRUCTIVE_BUTTON_QSS = """
QPushButton {
    background-color: #c62828;
    color: white;
    border: 1px solid #8e1c1c;
    padding: 4px 12px;
    border-radius: 3px;
}
QPushButton:hover { background-color: #b71c1c; }
QPushButton:pressed { background-color: #8e1c1c; }
QPushButton:disabled { background-color: #888; color: #ddd; }
"""
