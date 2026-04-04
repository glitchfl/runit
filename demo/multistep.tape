Output multistep.gif

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

Type "runit add deploy 'echo Building...' 'echo Running tests...' 'echo Deploying to server...'"
Enter
Sleep 1200ms

Type "runit deploy"
Enter
Sleep 3000ms
