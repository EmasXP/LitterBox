# HIGH

* Properties of a folder: calculate disk usage
  * Needs to be made in a different thread
  * Show spinner while calculating
  * Update numbers as sizes are being calculated
* How come some `.py` files has a plain-text icon, and some has the Python logo?

# MEDIUM

* Padding between the path bar and the separator
* Make the last button in the path bar (the current folder) more distinct. Maybe bold or an alternate background color.
* Drag-and-drop
  * Files to folder
  * LitterBox to external application
  * External application to LitterBox
* Paste: Folder conflict: Prevent overwrite if Source and Target is the same
* When opening file, change CWD first

# LOW

* Show "[folder name] [long dash] LitterBox" in the Application title bar
* More rounding on the path buttons?
* When deep in tree, the path bar does not fit well
* Filter in "Open with..." dialog
* "Open with..." "Other application"
  * List all applications that accept a file path, group by category
  * Add option to browse a binary via a file picker
* When renaming file: it would be nice if the file row was still selected after rename
* The "raw" path bar (the text input one) could be wider
* Some test files are not proper test files, it seems like (at least test_copy_paste.py isn't)
* Feels like our testing structure is wonky, there must be a better way
* Close other tabs
* Close tabs to the left/right
* Middle-click to close tabs
* Paste: Folder conflict: "Replace" option. Deletes the target and replaces it with the source. Important to check if Source and Target are the same here.
* Clicking on folder in the path bar: Pre-select the used-to-be child
* Alt+Up/Down to scroll
* Cache "Open with..."? Or maybe cache wherever the source information comes from.
* Ranked sorting of the candidates in the "Open with" dialog - the application(s) most likely to be correct shall be placed first. Not sure if possible, but worth a shot.
* Application icons in the "Open with" dialog
