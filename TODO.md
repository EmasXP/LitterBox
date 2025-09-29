# HIGH

_Such empty_

# MEDIUM

* Listen for events on the current folder, for new, updated and deleted files
* I want to implement Copy, Cut and Paste functionality:
  - When pasting, and target file already exist, the user shall be given three options: Overwrite, Rename or Cancel
  - On Rename: Suggest a new name, for example "file (2).txt"
  - On Overwrite: Give the option to "Apply for all"
  - Show progress bar
  - Several simultaneous Paste actions can happen at the "same time", meaning that files can already be in transfer when another Paste happens. Then another progress bar shall appear.
  - Cancel running file copy (per progress bar)
  - Each progress bar shall contain some information about what's being copied
  - Update the view as files are being copied over, so the new files appear (and their file sizes are being increased)
  - Maybe it's best to put all this in a new class/module, to make it easier to catch bugs

# LOW

* The icons are only Folder or File, does not show file type.
* Show "[folder name] [long dash] LitterBox" in the Application title bar
* Icons instead of buttons for "New folder" and "New file"
* Padding between the path bar and the separator
* More rounding on the path buttons?
* Make the last button in the path bar (the current folder) more distinct. Maybe bold or an alternate background color.
* When deep in tree, the path bar does not fit well
* Filter in "Open with..." dialog
* "Open with..." "Other application"
  * List all applications that accept a file path
  * Add option to browse a binary via a file picker
* When renaming file: it would be nice if the file row was still selected after rename
* The "raw" path bar (the text input one) could be wider
* When opening file, change CWD first
