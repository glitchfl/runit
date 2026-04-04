Output capture-params.gif

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

Type "runit add release '@rev git rev-parse --short HEAD' 'echo Tagging {rev} as {tag}'"
Enter
Sleep 1200ms

Type "runit release v1.0"
Enter
Sleep 2000ms

Type "runit show release"
Enter
Sleep 2500ms
