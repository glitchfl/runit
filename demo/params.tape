Output params.gif

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

Type "runit add deploy 'echo Deploying to {env}...' 'echo {env} deploy complete'"
Enter
Sleep 1200ms

Type "runit deploy staging"
Enter
Sleep 1800ms

Type "runit deploy"
Enter
Sleep 2500ms
