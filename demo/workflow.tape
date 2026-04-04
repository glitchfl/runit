Output workflow.gif

Set Shell "bash"
Set FontSize 22
Set Width 1400
Set Height 800
Set Padding 30
Set Theme "Catppuccin Mocha"
Set TypingSpeed 35ms
Set FontFamily "Menlo"
Set Framerate 30

Sleep 500ms

Type "runit add tag '@rev git rev-parse --short HEAD' 'echo Creating {version} at {rev}' 'echo git tag -a {version} -m Release {version}'"
Enter
Sleep 1200ms

Type "runit tag v2.0"
Enter
Sleep 2500ms

Type "runit add push 'echo Pushing to {remote:origin}...' 'echo Done!'"
Enter
Sleep 1200ms

Type "runit push"
Enter
Sleep 1800ms

Type "runit push upstream"
Enter
Sleep 2500ms
