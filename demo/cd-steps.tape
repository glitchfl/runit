Output cd-steps.gif

Set Shell "bash"
Set FontSize 22
Set Width 1400
Set Height 700
Set Padding 30
Set Theme "Catppuccin Mocha"
Set TypingSpeed 35ms
Set FontFamily "Menlo"
Set Framerate 30

Sleep 500ms

Type "mkdir -p src/frontend"
Enter
Sleep 800ms

Type "runit add frontend 'cd src/frontend' 'echo Building in $(pwd)...' 'cd ..' 'echo Back to $(pwd)'"
Enter
Sleep 1200ms

Type "runit frontend"
Enter
Sleep 3000ms
