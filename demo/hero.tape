Output hero.gif

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

Type "runit add build 'echo Compiling...' 'echo Done!'"
Enter
Sleep 1200ms

Type "runit build"
Enter
Sleep 1500ms

Type "runit list"
Enter
Sleep 2500ms
