# Make locale boundaries explicit

Locale handling will be explicit at every Qt, project-persistence, and R-analysis boundary. Project JSON stores numeric values as JSON numbers and temporal values in defined ISO representations; user input and display use deliberate `QLocale` parsing and formatting; R-bound values are normalized independently of the operating-system locale. Release tests include both an English dot-decimal locale and a comma-decimal locale and must prove equivalent project round trips and Analysis Behavior.
