Output capture-chain.gif

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

Type "runit add pipeline '@branch git rev-parse --abbrev-ref HEAD' '@msg echo Deploying {branch}' 'echo {msg} at $(date +%H:%M)'"
Enter
Sleep 1200ms

Type "runit pipeline"
Enter
Sleep 3000ms
